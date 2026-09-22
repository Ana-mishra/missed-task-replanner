import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, upgrade_task_history_task_fk
from app.main import app
from app.models.task import Task
from app.models.task_history import TaskHistory


def enforce_sqlite_foreign_keys(dbapi_connection, _):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class TaskDeleteApiTests(unittest.TestCase):
    """Deleting a task with history must succeed without orphans.

    SQLite does not enforce foreign keys by default, so this engine turns
    enforcement on: it reproduces the PostgreSQL behavior where deleting a
    task still referenced by task_history used to raise IntegrityError.
    """

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(self.engine, "connect", enforce_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_delete_task_with_history_succeeds_and_preserves_audit(self):
        created = self.client.post("/tasks", json={
            "title": "Doomed task", "duration_minutes": 30,
            "deadline": "2040-01-01T10:00:00", "priority": "medium",
        })
        self.assertEqual(created.status_code, 201)
        task_id = created.json()["id"]

        with self.session_local() as db:
            history_before = db.query(TaskHistory).filter(
                TaskHistory.task_id == task_id
            ).count()
        self.assertGreaterEqual(history_before, 1)

        deleted = self.client.delete(f"/tasks/{task_id}")

        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get(f"/tasks/{task_id}").status_code, 404)
        self.assertNotIn(
            task_id, [task["id"] for task in self.client.get("/tasks").json()]
        )

        with self.session_local() as db:
            remaining_rows = db.query(TaskHistory).all()
            # No row may reference a task that no longer exists.
            dangling = [
                row for row in remaining_rows
                if row.task_id is not None
                and db.query(Task).filter_by(id=row.task_id).count() == 0
            ]
            self.assertEqual(dangling, [])
            # The audit trail (including the deleted event) survives with a
            # cleared task reference instead of vanishing or breaking keys.
            self.assertTrue(any(row.event_type == "deleted" for row in remaining_rows))

        history_response = self.client.get("/task-history")
        self.assertEqual(history_response.status_code, 200)

    def test_deleted_event_preserves_task_title_snapshot(self):
        created = self.client.post("/tasks", json={
            "title": "Doomed task", "duration_minutes": 30,
            "deadline": "2040-01-01T10:00:00", "priority": "medium",
        })
        self.assertEqual(created.status_code, 201)
        task_id = created.json()["id"]

        with self.session_local() as db:
            created_event = db.query(TaskHistory).filter(
                TaskHistory.task_id == task_id, TaskHistory.event_type == "created"
            ).one()
            self.assertEqual(created_event.task_title, "Doomed task")

        self.assertEqual(self.client.delete(f"/tasks/{task_id}").status_code, 204)

        with self.session_local() as db:
            # The task row is gone but its history keeps the title snapshot.
            self.assertIsNone(db.query(Task).filter_by(id=task_id).first())
            deleted_event = db.query(TaskHistory).filter(
                TaskHistory.event_type == "deleted"
            ).one()
            self.assertIsNone(deleted_event.task_id)
            self.assertEqual(deleted_event.task_title, "Doomed task")

    def test_upgrade_helper_is_a_noop_on_sqlite(self):
        upgrade_task_history_task_fk()
        with self.session_local() as db:
            self.assertEqual(
                db.execute(text("SELECT COUNT(*) FROM task_history")).scalar(), 0
            )


if __name__ == "__main__":
    unittest.main()
