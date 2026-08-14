import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.planning import ScheduledTask


class PlanEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def create_task(self, title, duration_minutes=30):
        response = self.client.post(
            "/tasks",
            json={
                "title": title,
                "duration_minutes": duration_minutes,
                "deadline": "2040-01-01T10:00:00",
                "priority": "high",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_plan_returns_and_persists_generated_schedule(self):
        included_task = self.create_task("Included plan task")
        skipped_task = self.create_task("Skipped plan task")

        try:
            scheduled_task = ScheduledTask(
                task_id=included_task["id"],
                title=included_task["title"],
                scheduled_start=datetime(2040, 1, 1, 9, 0),
                scheduled_end=datetime(2040, 1, 1, 9, 30),
            )
            with patch(
                "app.api.planning.PlanningEngine.generate_schedule",
                return_value=[scheduled_task],
            ) as generate_schedule:
                response = self.client.post(
                    "/plan",
                    json={
                        "available_start": "2040-01-01T09:00:00",
                        "available_end": "2040-01-01T10:00:00",
                    },
                )

            self.assertEqual(response.status_code, 200)
            schedule = response.json()["schedule"]
            self.assertEqual(len(schedule), 1)
            planned_task = schedule[0]
            self.assertEqual(planned_task["scheduled_start"], "2040-01-01T09:00:00")
            self.assertEqual(planned_task["scheduled_end"], "2040-01-01T09:30:00")
            self.assertTrue(generate_schedule.called)

            saved_task = self.client.get(f"/tasks/{included_task['id']}").json()
            skipped_task_after_plan = self.client.get(f"/tasks/{skipped_task['id']}").json()
            self.assertEqual(saved_task["scheduled_start"], "2040-01-01T09:00:00")
            self.assertEqual(saved_task["scheduled_end"], "2040-01-01T09:30:00")
            self.assertIsNone(skipped_task_after_plan["scheduled_start"])
            self.assertIsNone(skipped_task_after_plan["scheduled_end"])
        finally:
            self.client.delete(f"/tasks/{included_task['id']}")
            self.client.delete(f"/tasks/{skipped_task['id']}")

    def test_plan_rejects_an_invalid_time_range(self):
        response = self.client.post(
            "/plan",
            json={
                "available_start": "2040-01-01T10:00:00",
                "available_end": "2040-01-01T09:00:00",
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
