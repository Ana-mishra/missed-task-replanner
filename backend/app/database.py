from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./missed_task_replanner.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
    """Add new Task columns when upgrading an existing SQLite database."""
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
    columns_to_add = {
        "status": "VARCHAR NOT NULL DEFAULT 'pending'",
        "scheduled_start": "DATETIME",
        "scheduled_end": "DATETIME",
        "energy_level": "VARCHAR NOT NULL DEFAULT 'medium'",
        "actual_duration_minutes": "INTEGER",
        "deadline_conflicted": "BOOLEAN NOT NULL DEFAULT 0",
        "schedule_needs_refresh": "BOOLEAN NOT NULL DEFAULT 1",
    }

    with engine.begin() as connection:
        for name, definition in columns_to_add.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {definition}"))


def upgrade_task_history_table():
    """Safely expand the append-only history table without losing existing rows.

    SQLite cannot alter a CHECK constraint in place.  Older installations only
    allow the original lifecycle event types, so their table is rebuilt once
    with the expanded constraint after copying every historical record.
    """
    inspector = inspect(engine)
    if "task_history" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("task_history")}
    new_columns = {
        "old_start": "DATETIME",
        "old_end": "DATETIME",
        "new_start": "DATETIME",
        "new_end": "DATETIME",
        "reason": "VARCHAR",
    }
    with engine.begin() as connection:
        for name, definition in new_columns.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE task_history ADD COLUMN {name} {definition}"))

        table_sql = connection.execute(
            text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'task_history'")
        ).scalar() or ""
        if "rescheduled" in table_sql and "recovered" in table_sql:
            return

        connection.execute(
            text(
                """
                CREATE TABLE task_history__upgrade (
                    id INTEGER NOT NULL PRIMARY KEY,
                    task_id INTEGER NOT NULL,
                    event_type VARCHAR NOT NULL,
                    timestamp DATETIME NOT NULL,
                    scheduled_start DATETIME,
                    scheduled_end DATETIME,
                    old_start DATETIME,
                    old_end DATETIME,
                    new_start DATETIME,
                    new_end DATETIME,
                    reason VARCHAR,
                    CONSTRAINT valid_task_history_event_type CHECK (
                        event_type IN (
                            'created', 'scheduled', 'missed', 'completed',
                            'replanned', 'rescheduled', 'recovered', 'deleted'
                        )
                    ),
                    FOREIGN KEY(task_id) REFERENCES tasks (id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO task_history__upgrade (
                    id, task_id, event_type, timestamp, scheduled_start,
                    scheduled_end, old_start, old_end, new_start, new_end, reason
                )
                SELECT id, task_id, event_type, timestamp, scheduled_start,
                    scheduled_end, old_start, old_end, new_start, new_end, reason
                FROM task_history
                """
            )
        )
        connection.execute(text("DROP TABLE task_history"))
        connection.execute(text("ALTER TABLE task_history__upgrade RENAME TO task_history"))
