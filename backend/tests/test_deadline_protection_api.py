import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.task_history import TaskHistory


class DeadlineProtectionEndpointTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
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

    def create_task(self, title, deadline, status="pending"):
        response = self.client.post(
            "/tasks",
            json={
                "title": title,
                "duration_minutes": 30,
                "deadline": deadline.isoformat(),
                "priority": "medium",
                "status": status,
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    @staticmethod
    def update_payload(task, **changes):
        payload = {
            "title": task["title"],
            "description": task["description"],
            "duration_minutes": task["duration_minutes"],
            "deadline": task["deadline"],
            "priority": task["priority"],
            "completed": task["completed"],
            "status": task["status"],
            "scheduled_start": task["scheduled_start"],
            "scheduled_end": task["scheduled_end"],
            "energy_level": task["energy_level"],
            "actual_duration_minutes": task["actual_duration_minutes"],
            "deadline_conflicted": task["deadline_conflicted"],
        }
        payload.update(changes)
        return payload

    def history_count(self, task_id):
        with self.session_local() as db:
            return db.query(TaskHistory).filter(TaskHistory.task_id == task_id).count()

    def test_pending_future_task_can_change_deadline(self):
        task = self.create_task("Future task", datetime.now() + timedelta(days=3))
        new_deadline = datetime.now() + timedelta(days=5)

        response = self.client.put(
            f"/tasks/{task['id']}",
            json=self.update_payload(task, deadline=new_deadline.isoformat()),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deadline"], new_deadline.isoformat())

    def test_missed_or_overdue_task_cannot_change_deadline_but_can_edit_details(self):
        for title, status in (("Missed task", "missed"), ("Overdue task", "pending")):
            deadline = datetime.now() - timedelta(hours=1)
            task = self.create_task(title, deadline, status=status)
            history_before = self.history_count(task["id"])

            blocked = self.client.put(
                f"/tasks/{task['id']}",
                json=self.update_payload(
                    task,
                    deadline=(datetime.now() + timedelta(days=4)).isoformat(),
                ),
            )
            self.assertEqual(blocked.status_code, 409)

            edited = self.client.put(
                f"/tasks/{task['id']}",
                json=self.update_payload(task, title=f"Updated {title}", priority="high"),
            )
            self.assertEqual(edited.status_code, 200)
            self.assertEqual(edited.json()["title"], f"Updated {title}")
            self.assertEqual(edited.json()["priority"], "high")
            self.assertEqual(edited.json()["deadline"], deadline.isoformat())
            self.assertEqual(self.history_count(task["id"]), history_before)

    def test_replanned_task_cannot_change_deadline_but_keeps_other_edits(self):
        deadline = datetime.now() + timedelta(days=2)
        task = self.create_task("Replanned task", deadline)
        with self.session_local() as db:
            db.add(TaskHistory(task_id=task["id"], event_type="missed"))
            db.add(TaskHistory(task_id=task["id"], event_type="replanned"))
            db.commit()

        fetched = self.client.get(f"/tasks/{task['id']}").json()
        self.assertTrue(fetched["was_replanned"])
        blocked = self.client.put(
            f"/tasks/{task['id']}",
            json=self.update_payload(
                fetched,
                deadline=(datetime.now() + timedelta(days=8)).isoformat(),
            ),
        )
        self.assertEqual(blocked.status_code, 409)

        edited = self.client.put(
            f"/tasks/{task['id']}",
            json=self.update_payload(fetched, duration_minutes=45, energy_level="high"),
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["duration_minutes"], 45)
        self.assertEqual(edited.json()["energy_level"], "high")
        self.assertEqual(edited.json()["deadline"], deadline.isoformat())


if __name__ == "__main__":
    unittest.main()
