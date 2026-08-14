import unittest

from fastapi.testclient import TestClient

from app.main import app


class TaskCrudEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_task_crud_endpoints_work(self):
        created = self.client.post(
            "/tasks",
            json={
                "title": "CRUD verification task",
                "duration_minutes": 20,
                "deadline": "2040-01-01T10:00:00",
                "priority": "medium",
            },
        )
        self.assertEqual(created.status_code, 201)
        task_id = created.json()["id"]

        try:
            listed = self.client.get("/tasks")
            self.assertEqual(listed.status_code, 200)
            self.assertIn(task_id, [task["id"] for task in listed.json()])

            fetched = self.client.get(f"/tasks/{task_id}")
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.json()["title"], "CRUD verification task")

            updated = self.client.put(
                f"/tasks/{task_id}",
                json={
                    "title": "Updated CRUD verification task",
                    "description": None,
                    "duration_minutes": 25,
                    "deadline": "2040-01-01T11:00:00",
                    "priority": "high",
                    "completed": False,
                    "status": "pending",
                    "scheduled_start": None,
                    "scheduled_end": None,
                    "energy_level": "medium",
                },
            )
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.json()["title"], "Updated CRUD verification task")
        finally:
            deleted = self.client.delete(f"/tasks/{task_id}")
            self.assertEqual(deleted.status_code, 204)


if __name__ == "__main__":
    unittest.main()
