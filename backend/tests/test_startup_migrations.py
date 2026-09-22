"""Startup migration safety: the task_history upgrade must never reflect
from inside its own write transaction.

Production hung because ``upgrade_task_history_table()`` opened a write
transaction, ran ``ALTER TABLE`` (holding an exclusive lock), then called
``Inspector.get_check_constraints()`` on a *separate* pooled connection.
That reflection evaluates ``pg_get_constraintdef``, which needs a lock on
the very table the transaction is altering: a cross-connection
self-deadlock that PostgreSQL cannot detect, so startup hung forever.
"""

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as database
from app.database import Base, upgrade_task_history_table


def _scratch_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def _legacy_history_table(engine):
    """Recreate a pre-upgrade task_history: old CHECK, no new columns."""
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS task_history"))
        connection.execute(
            text(
                "CREATE TABLE task_history ("
                "id INTEGER NOT NULL PRIMARY KEY, "
                "task_id INTEGER NOT NULL, "
                "user_id INTEGER, "
                "event_type VARCHAR NOT NULL, "
                "timestamp DATETIME NOT NULL, "
                "scheduled_start DATETIME, "
                "scheduled_end DATETIME, "
                "CONSTRAINT valid_task_history_event_type CHECK "
                "(event_type IN ('created', 'completed')))"
            )
        )
        connection.execute(
            text(
                "INSERT INTO task_history (id, task_id, user_id, event_type, timestamp) "
                "VALUES (1, 10, 7, 'created', '2026-01-01 10:00:00')"
            )
        )


class StartupMigrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = _scratch_engine()
        self.patch_engine = patch.object(database, "engine", self.engine)
        self.patch_engine.start()
        self.session_local = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.patch_engine.stop()
        self.engine.dispose()

    def test_fresh_database_needs_no_upgrade(self):
        self.assertTrue(database._history_constraint_is_current())
        with self.session_local() as db:
            before = db.execute(text("SELECT COUNT(*) FROM task_history")).scalar()
        upgrade_task_history_table()
        with self.session_local() as db:
            after = db.execute(text("SELECT COUNT(*) FROM task_history")).scalar()
        self.assertEqual(before, after)

    def test_legacy_table_is_upgraded_without_data_loss(self):
        _legacy_history_table(self.engine)
        self.assertFalse(database._history_constraint_is_current())

        upgrade_task_history_table()

        with self.session_local() as db:
            columns = {
                row[1] for row in db.execute(text("PRAGMA table_info(task_history)"))
            }
            for expected in (
                "old_start",
                "old_end",
                "new_start",
                "new_end",
                "reason",
                "completed_at",
                "task_title",
            ):
                self.assertIn(expected, columns)
            rows = db.execute(
                text("SELECT id, task_id, user_id, event_type FROM task_history")
            ).all()
            self.assertEqual(rows, [(1, 10, 7, "created")])
            # The expanded constraint now permits the newer event types.
            db.execute(
                text(
                    "INSERT INTO task_history (task_id, event_type, timestamp) "
                    "VALUES (10, 'recovered', '2026-01-02 10:00:00')"
                )
            )
            db.commit()
        self.assertTrue(database._history_constraint_is_current())

        # Rerunning the upgrade is a safe no-op.
        upgrade_task_history_table()
        with self.session_local() as db:
            self.assertEqual(
                db.execute(text("SELECT COUNT(*) FROM task_history")).scalar(), 2
            )

    def test_upgrade_never_uses_broad_check_constraint_reflection(self):
        """The old hang came from Inspector.get_check_constraints()."""
        _legacy_history_table(self.engine)
        with patch(
            "sqlalchemy.engine.reflection.Inspector.get_check_constraints",
            side_effect=AssertionError("broad reflection must not be used"),
        ):
            upgrade_task_history_table()
        with self.session_local() as db:
            self.assertEqual(
                db.execute(text("SELECT COUNT(*) FROM task_history")).scalar(), 1
            )


if __name__ == "__main__":
    unittest.main()
