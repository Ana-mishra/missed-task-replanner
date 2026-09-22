import os
import re

from dotenv import load_dotenv
from sqlalchemy import create_engine, exc as sa_exc, inspect, text
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


def normalize_database_url(url: str) -> str:
    """Return the SQLAlchemy URL for a raw DATABASE_URL value.

    Hosting platforms (including Railway) commonly provide ``postgres://``
    or ``postgresql://`` URLs. Both are normalized to the psycopg (v3)
    driver used by this project. Already-qualified URLs and SQLite URLs
    (local development / tests) pass through unchanged. Surrounding
    whitespace and quotes — a common paste artifact in dashboard editors —
    are stripped so prefix detection never silently misses.
    """
    cleaned = url.strip().strip("\"'")
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg://" + cleaned[len("postgres://"):]
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg://" + cleaned[len("postgresql://"):]
    return cleaned


def ensure_production_database(url: str) -> None:
    """Fail fast if a deployed environment would silently run on SQLite.

    Railway always sets RAILWAY_ENVIRONMENT. If it is present while the
    resolved URL is SQLite, the platform's DATABASE_URL never reached the
    app (e.g. an unlinked variable reference) — crash loudly here instead
    of booting against a throwaway SQLite file and corrupting data.
    Local development and tests never set RAILWAY_ENVIRONMENT, so their
    SQLite setups are unaffected.
    """
    if url.startswith("sqlite") and os.getenv("RAILWAY_ENVIRONMENT"):
        raise RuntimeError(
            "DATABASE_URL resolved to SQLite on Railway (RAILWAY_ENVIRONMENT is set). "
            "The platform's PostgreSQL DATABASE_URL is not reaching the app — "
            "check the service variable reference (e.g. ${{Postgres.DATABASE_URL}} "
            "requires a Postgres service literally named 'Postgres')."
        )


DATABASE_URL = normalize_database_url(DATABASE_URL)
ensure_production_database(DATABASE_URL)

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


def _timeout_setting(name: str, default: str) -> str:
    """Return a validated PostgreSQL timeout setting (e.g. ``'15s'``).

    Falls back to the default when the environment override is malformed,
    so a typo can never brick application startup.
    """
    value = os.getenv(name, default)
    if re.fullmatch(r"\d+(ms|s|min|h)?", value or ""):
        return value
    return default


# Bounded migration timeouts (PostgreSQL only): a blocked deployment must
# fail fast with an explicit error, never hang forever inside app import.
_MIGRATION_LOCK_TIMEOUT = _timeout_setting("PLANORA_MIGRATION_LOCK_TIMEOUT", "15s")
_MIGRATION_STATEMENT_TIMEOUT = _timeout_setting(
    "PLANORA_MIGRATION_STATEMENT_TIMEOUT", "120s"
)
_MIGRATION_READ_TIMEOUT = _timeout_setting("PLANORA_MIGRATION_READ_TIMEOUT", "30s")

# Advisory-lock key serializing the task_history rebuild across instances.
_TASK_HISTORY_UPGRADE_LOCK = "planora_task_history_upgrade"


def _migration_timeouts(connection) -> None:
    """Bound DDL/DML in a migration transaction (PostgreSQL only).

    Must be the first statement(s) of the transaction so every later
    statement inherits the bounds.
    """
    if not _is_postgresql():
        return
    connection.execute(text(f"SET LOCAL lock_timeout = '{_MIGRATION_LOCK_TIMEOUT}'"))
    connection.execute(text(f"SET LOCAL statement_timeout = '{_MIGRATION_STATEMENT_TIMEOUT}'"))


def _add_column_if_supported() -> str:
    """Return ``IF NOT EXISTS`` for dialects supporting it on ADD COLUMN."""
    return "IF NOT EXISTS " if _is_postgresql() else ""


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
        _migration_timeouts(connection)
        maybe_exists = _add_column_if_supported()
        for name, definition in columns_to_add.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {maybe_exists}{name} {definition}"))


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
        _migration_timeouts(connection)
        maybe_exists = _add_column_if_supported()
        if "user_id" not in existing_columns:
            connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {maybe_exists}user_id INTEGER"))

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
                connection.execute(
                    text(f"ALTER TABLE task_history ADD COLUMN {maybe_exists}user_id INTEGER")
                )
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


def _task_history_columns() -> set[str]:
    """Return the current task_history column names (fresh read, no writes)."""
    inspector = inspect(engine)
    if "task_history" not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns("task_history")}


def _fetch_constraint_definition(connection) -> str | None:
    """Fetch this table's CHECK definition on the given connection.

    A single targeted pg_catalog lookup for the one named constraint —
    never the broad ``Inspector.get_check_constraints()`` reflection,
    whose ``pg_get_constraintdef`` evaluation runs on a separate pooled
    connection and blocks behind table locks.
    """
    if engine.dialect.name == "sqlite":
        return connection.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'task_history'")
        ).scalar() or ""
    return connection.execute(
        text(
            "SELECT pg_get_constraintdef(c.oid, true) "
            "FROM pg_catalog.pg_constraint c "
            "JOIN pg_catalog.pg_class t ON t.oid = c.conrelid "
            "WHERE t.relname = 'task_history' "
            "AND c.conname = 'valid_task_history_event_type'"
        )
    ).scalar()


def _definition_is_current(definition: str | None) -> bool:
    if not definition:
        return False
    return "rescheduled" in definition and "recovered" in definition and "overdue" in definition


def _history_constraint_is_current() -> bool:
    """Return True when the history CHECK constraint already allows all events.

    Runs on its own short-lived connection with a bounded statement
    timeout — never inside a write transaction holding DDL locks.
    """
    if engine.dialect.name == "sqlite":
        with engine.connect() as connection:
            return _definition_is_current(_fetch_constraint_definition(connection))
    with engine.begin() as connection:
        connection.execute(text(f"SET LOCAL statement_timeout = '{_MIGRATION_READ_TIMEOUT}'"))
        return _definition_is_current(_fetch_constraint_definition(connection))


def upgrade_task_history_table():
    """Safely expand the append-only history table without losing existing rows.

    CHECK constraints cannot be altered in place, so older installations that
    only allow the original lifecycle event types have their table rebuilt once
    with the expanded constraint after copying every historical record.

    All schema reads happen before any write transaction opens: reflecting
    from inside a transaction that already holds DDL locks self-deadlocks,
    because ``pg_get_constraintdef`` needs a lock on the very table the
    transaction is altering. Healthy databases therefore perform reads only
    and open no write transaction at all.
    """
    inspector = inspect(engine)
    if "task_history" not in inspector.get_table_names():
        return

    timestamp = _timestamp_type()
    new_columns = {
    "old_start": timestamp,
    "old_end": timestamp,
    "new_start": timestamp,
    "new_end": timestamp,
    "reason": "VARCHAR",
    "completed_at": timestamp,
    "task_title": "VARCHAR",
}
    existing_columns = _task_history_columns()
    missing_columns = {
        name: definition for name, definition in new_columns.items() if name not in existing_columns
    }
    needs_rebuild = not _history_constraint_is_current()
    if not missing_columns and not needs_rebuild:
        # Healthy database: reads only, no write transaction at all.
        return

    try:
        with engine.begin() as connection:
            _migration_timeouts(connection)
            maybe_exists = _add_column_if_supported()
            for name, definition in missing_columns.items():
                connection.execute(
                    text(f"ALTER TABLE task_history ADD COLUMN {maybe_exists}{name} {definition}")
                )

            if not needs_rebuild:
                return
            if _is_postgresql():
                # Serialize concurrent rebuilders; released at commit/rollback.
                # The re-check below runs on this same connection, so it can
                # never block on locks held by this transaction itself.
                connection.execute(
                    text(f"SELECT pg_advisory_xact_lock(hashtext('{_TASK_HISTORY_UPGRADE_LOCK}'))")
                )
                if _definition_is_current(_fetch_constraint_definition(connection)):
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
                        task_title VARCHAR,
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
        scheduled_end, completed_at, old_start, old_end, new_start, new_end, reason,
        task_title
    )
                    SELECT id, task_id, user_id, event_type, timestamp, scheduled_start,
        scheduled_end, completed_at, old_start, old_end, new_start, new_end, reason,
        task_title
    FROM task_history
                    """
                )
            )
            connection.execute(text("DROP TABLE task_history"))
            connection.execute(text("ALTER TABLE task_history__upgrade RENAME TO task_history"))
            if _is_postgresql():
                # Explicit-id copies do not advance the identity sequence;
                # without this the next history write would collide.
                connection.execute(
                    text(
                        "SELECT setval(pg_get_serial_sequence('task_history', 'id'), "
                        "COALESCE(MAX(id), 0)) FROM task_history"
                    )
                )
    except sa_exc.DBAPIError:
        # A concurrent instance may have won a DDL race (duplicate column /
        # table). Re-verify the desired end state: if another instance
        # completed the upgrade, there is nothing left to do.
        if _task_history_fully_upgraded():
            return
        raise


def _task_history_fully_upgraded() -> bool:
    """Return True when task_history needs no further upgrade work."""
    expected = {
        "old_start",
        "old_end",
        "new_start",
        "new_end",
        "reason",
        "completed_at",
        "task_title",
    }
    return expected <= _task_history_columns() and _history_constraint_is_current()
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
        _migration_timeouts(connection)
        maybe_exists = _add_column_if_supported()
        connection.execute(
            text(
                "ALTER TABLE users "
                f"ADD COLUMN {maybe_exists}name_confirmed BOOLEAN NOT NULL DEFAULT {_boolean_false_literal()}"
            )
        )


def upgrade_task_history_task_fk():
    """Let deleted tasks keep their append-only history on PostgreSQL.

    Task deletion records a ``deleted`` event and then removes the task row.
    The surviving history rows must stay queryable by owner, so the
    ``task_history.task_id`` foreign key uses ON DELETE SET NULL and the
    column is nullable.  Fresh databases get this from ``create_all``;
    existing PostgreSQL databases are altered idempotently below.
    SQLite is left untouched (it does not enforce foreign keys, and fresh
    SQLite databases already receive the new definition).
    """
    if engine.dialect.name != "postgresql":
        return
    inspector = inspect(engine)
    if "task_history" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("task_history")}
    task_id_column = columns.get("task_id")
    if task_id_column is None:
        return
    fk_names = [
        fk.get("name")
        for fk in inspector.get_foreign_keys("task_history")
        if (fk.get("constrained_columns") or []) == ["task_id"]
    ]
    already_migrated = bool(task_id_column.get("nullable", False)) and any(
        (fk.get("options") or {}).get("ondelete") == "SET NULL"
        for fk in inspector.get_foreign_keys("task_history")
        if (fk.get("constrained_columns") or []) == ["task_id"]
    )
    if already_migrated:
        return

    with engine.begin() as connection:
        _migration_timeouts(connection)
        for name in fk_names:
            if name:
                connection.execute(
                    text(f'ALTER TABLE task_history DROP CONSTRAINT IF EXISTS "{name}"')
                )
        connection.execute(text("ALTER TABLE task_history ALTER COLUMN task_id DROP NOT NULL"))
        connection.execute(
            text(
                "ALTER TABLE task_history ADD CONSTRAINT task_history_task_id_fkey "
                "FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE SET NULL"
            )
        )
           
