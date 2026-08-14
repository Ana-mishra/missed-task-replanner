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
    }

    with engine.begin() as connection:
        for name, definition in columns_to_add.items():
            if name not in existing_columns:
                connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {definition}"))
