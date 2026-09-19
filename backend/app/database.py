import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Load backend/.env for local development. In production the platform
# supplies real environment variables; load_dotenv never overrides those.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Set it to a PostgreSQL URL, e.g. "
        "DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/planora "
        "(see backend/.env.example)."
    )

# Hosting platforms commonly provide postgres:// or postgresql:// URLs.
# Normalize to the psycopg (v3) driver used by this project.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

# SQLite needs check_same_thread=False for FastAPI/TestClient usage.
# PostgreSQL (psycopg) must NOT receive this option.
_connect_args = {} if not DATABASE_URL.startswith("sqlite") else {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _is_postgresql() -> bool:
    return engine.dialect.name == "postgresql"


def _timestamp_type() -> str:
    return "TIMESTAMP" if _is_postgresql() else "DATETIME"


def _boolean_false_literal() -> str:
    return "FALSE" if _is_postgresql() else "0"


def _boolean_true_literal() -> str:
    return "TRUE" if _is_postgresql() else "1"


class Base(DeclarativeBase):
    """Base class for all database models."""


def get_db():
    """Provide one database session for each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def add_task_planning_columns():
    """Add new Task columns when upgrading an existing database."""
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    timestamp = _timestamp_type()
    false_literal = _boolean_false_literal()
    true_literal = _boolean_true_literal()
    existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
    columns_to_add = {
        "status": "VARCHAR NOT NULL DEFAULT 'pending'",
        "scheduled_start": timestamp,
        "scheduled_end": timestamp,
        "energy_level": "VARCHAR NOT NULL DEFAULT 'medium'",
        "actual_duration_minutes": "INTEGER",
        "completed_at": timestamp,
        "deadline_conflicted": f"BOOLEAN NOT NULL DEFAULT {false_literal}",
        "schedule_needs_refresh": f"BOOLEAN NOT NULL DEFAULT {true_literal}",
        "schedule_refresh_reason": "VARCHAR",
    }

    with engine.begin() as connection:
        for name, definition in columns_to_add.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {definition}"))


def add_task_ownership_column():
    """Safely attach pre-auth tasks to one deterministic dev account.

    Existing rows are first given a nullable column and then backfilled
    without deleting or rewriting task/history records.
    """
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names() or "users" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
    with engine.begin() as connection:
        if "user_id" not in existing_columns:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN user_id INTEGER"))

        legacy_email = "legacy-development@planora.local"
        legacy_user_id = connection.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": legacy_email}
        ).scalar()
        if legacy_user_id is None:
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            if "name_confirmed" in user_columns:
                connection.execute(
                    text(
                        "INSERT INTO users (name, email, password_hash, name_confirmed) "
                        "VALUES (:name, :email, :password_hash, "
                        f"{_boolean_false_literal()})"
                    ),
                    {
                        "name": "Legacy Development Data",
                        "email": legacy_email,
                        # Deliberately not a usable password. This account is only
                        # a deterministic owner for rows created before accounts.
                        "password_hash": "legacy-development-data-no-login",
                    },
                )
            else:
                connection.execute(
                    text(
                        "INSERT INTO users (name, email, password_hash) "
                        "VALUES (:name, :email, :password_hash)"
                    ),
                    {
                        "name": "Legacy Development Data",
                        "email": legacy_email,
                        # Deliberately not a usable password. This account is only
                        # a deterministic owner for rows created before accounts.
                        "password_hash": "legacy-development-data-no-login",
                    },
                )
            legacy_user_id = connection.execute(
                text("SELECT id FROM users WHERE email = :email"), {"email": legacy_email}
            ).scalar()

        connection.execute(
            text("UPDATE tasks SET user_id = :user_id WHERE user_id IS NULL"),
            {"user_id": legacy_user_id},
        )
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks (user_id)"))

        if "task_history" in inspector.get_table_names():
            history_columns = {
                column["name"] for column in inspector.get_columns("task_history")
            }
            if "user_id" not in history_columns:
                connection.execute(text("ALTER TABLE task_history ADD COLUMN user_id INTEGER"))
            connection.execute(
                text(
                    "UPDATE task_history SET user_id = COALESCE("
                    "(SELECT tasks.user_id FROM tasks WHERE tasks.id = task_history.task_id), "
                    ":legacy_user_id) WHERE user_id IS NULL"
                ),
                {"legacy_user_id": legacy_user_id},
            )
            connection.execute(
                text("CREATE INDEX IF NOT EXISTS ix_task_history_user_id ON task_history (user_id)")
            )


def _history_constraint_is_current(inspector, connection) -> bool:
    """Return True when the history CHECK constraint already allows all events."""
    try:
        checks = inspector.get_check_constraints("task_history")
    except NotImplementedError:
        checks = []
    for check in checks:
        sql = str(check.get("sqltext", ""))
        if "rescheduled" in sql and "recovered" in sql and "overdue" in sql:
            return True
    if checks:
        return False
    # SQLite fallback for dialects/drivers without check-constraint reflection.
    if engine.dialect.name == "sqlite":
        table_sql = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'task_history'")
        ).scalar() or ""
        return "rescheduled" in table_sql and "recovered" in table_sql and "overdue" in table_sql
    return False


def upgrade_task_history_table():
    """Safely expand the append-only history table without losing existing rows.

    CHECK constraints cannot be altered in place, so older installations that
    only allow the original lifecycle event types have their table rebuilt once
    with the expanded constraint after copying every historical record.
    """
    inspector = inspect(engine)
    if "task_history" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("task_history")}
    timestamp = _timestamp_type()
    new_columns = {
    "old_start": timestamp,
    "old_end": timestamp,
    "new_start": timestamp,
    "new_end": timestamp,
    "reason": "VARCHAR",
    "completed_at": timestamp,
}
    with engine.begin() as connection:
        for name, definition in new_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE task_history ADD COLUMN {name} {definition}"))

        if _history_constraint_is_current(inspector, connection):
         return

        id_definition = (
            "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY"
            if _is_postgresql()
            else "INTEGER NOT NULL PRIMARY KEY"
        )
        connection.execute(
            text(
                f"""
                CREATE TABLE task_history__upgrade (
                    id {id_definition},
                    task_id INTEGER NOT NULL,
                    user_id INTEGER,
                    event_type VARCHAR NOT NULL,
                    timestamp {timestamp} NOT NULL,
                    scheduled_start {timestamp},
                    scheduled_end {timestamp},
                    completed_at {timestamp},
                    old_start {timestamp},
                    old_end {timestamp},
                    new_start {timestamp},
                    new_end {timestamp},
                    reason VARCHAR,
                    CONSTRAINT valid_task_history_event_type CHECK (
                        event_type IN (
    'created', 'scheduled', 'missed', 'overdue', 'completed',
    'replanned', 'rescheduled', 'recovered', 'deleted'
)
                    ),
                    FOREIGN KEY(task_id) REFERENCES tasks (id),
                    FOREIGN KEY(user_id) REFERENCES users (id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO task_history__upgrade (
    id, task_id, user_id, event_type, timestamp, scheduled_start,
    scheduled_end, completed_at, old_start, old_end, new_start, new_end, reason
)
                SELECT id, task_id, user_id, event_type, timestamp, scheduled_start,
    scheduled_end, completed_at, old_start, old_end, new_start, new_end, reason
FROM task_history
                """
            )
        )
        connection.execute(text("DROP TABLE task_history"))
        connection.execute(text("ALTER TABLE task_history__upgrade RENAME TO task_history"))
def add_user_name_confirmation_column():
    """Add name confirmation state to existing user accounts."""
    inspector = inspect(engine)

    if "users" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("users")
    }

    if "name_confirmed" in existing_columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE users "
                f"ADD COLUMN name_confirmed BOOLEAN NOT NULL DEFAULT {_boolean_false_literal()}"
            )
        )        
           
