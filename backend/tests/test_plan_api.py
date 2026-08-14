import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.planning import ScheduledTask


class PlanEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_plan_returns_a_schedule_for_current_tasks(self):
        task_response = self.client.post(
            "/tasks",
            json={
                "title": "Plan endpoint test task",
                "duration_minutes": 30,
                "deadline": "2040-01-01T10:00:00",
                "priority": "high",
            },
        )
        self.assertEqual(task_response.status_code, 201)
        task_id = task_response.json()["id"]

        try:
            scheduled_task = ScheduledTask(
                task_id=task_id,
                title="Plan endpoint test task",
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
            planned_task = next(item for item in schedule if item["task_id"] == task_id)
            self.assertEqual(planned_task["scheduled_start"], "2040-01-01T09:00:00")
            self.assertEqual(planned_task["scheduled_end"], "2040-01-01T09:30:00")
            tasks_passed_to_engine = generate_schedule.call_args.args[0]
            self.assertIn(task_id, [task.id for task in tasks_passed_to_engine])
        finally:
            self.client.delete(f"/tasks/{task_id}")

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
