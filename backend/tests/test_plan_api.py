import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.task_history import TaskHistory
from app.models.task import Task
from app.services.planning import PlanningResult, ScheduledTask


class PlanEndpointTests(unittest.TestCase):
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
        app.dependency_overrides.pop(get_current_user, None)
        self.client = TestClient(app)
        self.client.headers.update(
            self.register_and_login("plan-api-tests@planora.local")
        )

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def register_and_login(self, email):
        password = "secure-pass-123"
        registration = self.client.post(
            "/auth/register",
            json={"name": "Plan API Tests", "email": email, "password": password},
        )
        self.assertEqual(registration.status_code, 201)
        login = self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(login.status_code, 200)
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    def create_task(
        self,
        title,
        duration_minutes=30,
        deadline="2040-01-01T10:00:00",
        priority="high",
    ):
        response = self.client.post(
            "/tasks",
            json={
                "title": title,
                "duration_minutes": duration_minutes,
                "deadline": deadline,
                "priority": priority,
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def history_event_count(self, task_id, event_type):
        with self.session_local() as db:
            return db.query(TaskHistory).filter(
                TaskHistory.task_id == task_id,
                TaskHistory.event_type == event_type,
            ).count()

    def latest_history_event(self, task_id, event_type):
        with self.session_local() as db:
            return db.query(TaskHistory).filter(
                TaskHistory.task_id == task_id,
                TaskHistory.event_type == event_type,
            ).order_by(TaskHistory.id.desc()).first()

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
            result = PlanningResult(
                schedule=[scheduled_task],
                is_overloaded=True,
                unscheduled_minutes=30,
                bad_day=True,
            )
            with patch(
                "app.api.planning.PlanningEngine.generate_schedule",
                return_value=result,
            ) as generate_schedule:
                response = self.client.post(
                    "/plan",
                    json={
                        "available_start": "2040-01-01T09:00:00",
                        "available_end": "2040-01-01T10:00:00",
                        "energy_level": "low",
                        "bad_day": True,
                    },
                )

            self.assertEqual(response.status_code, 200)
            schedule = response.json()["schedule"]
            self.assertEqual(len(schedule), 1)
            self.assertTrue(response.json()["is_overloaded"])
            self.assertEqual(response.json()["unscheduled_minutes"], 30)
            self.assertTrue(response.json()["bad_day"])
            planned_task = schedule[0]
            self.assertEqual(planned_task["scheduled_start"], "2040-01-01T09:00:00")
            self.assertEqual(planned_task["scheduled_end"], "2040-01-01T09:30:00")
            self.assertTrue(generate_schedule.called)
            self.assertEqual(generate_schedule.call_args.args[3], "low")
            self.assertTrue(generate_schedule.call_args.args[4])

            saved_task = self.client.get(f"/tasks/{included_task['id']}").json()
            skipped_task_after_plan = self.client.get(f"/tasks/{skipped_task['id']}").json()
            self.assertEqual(saved_task["scheduled_start"], "2040-01-01T09:00:00")
            self.assertEqual(saved_task["scheduled_end"], "2040-01-01T09:30:00")
            self.assertIsNone(skipped_task_after_plan["scheduled_start"])
            self.assertIsNone(skipped_task_after_plan["scheduled_end"])
            self.assertFalse(skipped_task_after_plan["completed"])
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

    def test_bad_day_uses_low_energy_policy_and_persists_a_deadline_reason(self):
        task = self.create_task(
            "Tomorrow deadline",
            duration_minutes=30,
            deadline="2040-01-02T17:00:00",
        )
        result = PlanningResult(
            schedule=[
                ScheduledTask(
                    task["id"],
                    task["title"],
                    datetime(2040, 1, 1, 9),
                    datetime(2040, 1, 1, 9, 30),
                )
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
            bad_day=True,
        )

        with patch(
            "app.api.planning.PlanningEngine.generate_schedule",
            return_value=result,
        ) as generate_schedule:
            response = self.client.post(
                "/plan",
                json={
                    "available_start": "2040-01-01T09:00:00",
                    "available_end": "2040-01-01T11:00:00",
                    "bad_day": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["bad_day"])
        self.assertEqual(generate_schedule.call_args.args[3], None)
        self.assertTrue(generate_schedule.call_args.args[4])
        event = self.latest_history_event(task["id"], "scheduled")
        self.assertIsNotNone(event)
        self.assertEqual(event.reason, "Kept because the deadline is tomorrow.")

    def test_repeating_an_unchanged_plan_preserves_persisted_times_and_history(self):
        task = self.create_task("Stable plan")
        first = PlanningResult(
            schedule=[
                ScheduledTask(
                    task["id"], task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30)
                )
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        plan_request = {
            "available_start": "2040-01-01T09:00:00",
            "available_end": "2040-01-01T11:00:00",
        }
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=first) as generate_schedule:
            self.assertEqual(self.client.post("/plan", json=plan_request).status_code, 200)
            self.assertEqual(generate_schedule.call_count, 1)

        with self.session_local() as db:
            before_history_count = db.query(TaskHistory).filter(
                TaskHistory.task_id == task["id"],
                TaskHistory.event_type == "rescheduled",
            ).count()

        shifted = PlanningResult(
            schedule=[
                ScheduledTask(
                    task["id"], task["title"], datetime(2040, 1, 1, 10), datetime(2040, 1, 1, 10, 30)
                )
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=shifted) as generate_schedule:
            response = self.client.post(
                "/plan",
                json={
                    "available_start": "2040-01-01T09:15:00",
                    "available_end": "2040-01-01T11:00:00",
                },
            )
            self.assertEqual(generate_schedule.call_count, 0)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["schedule"][0]["scheduled_start"], "2040-01-01T09:00:00")
        stored_task = self.client.get(f"/tasks/{task['id']}").json()
        self.assertEqual(stored_task["scheduled_start"], "2040-01-01T09:00:00")
        self.assertEqual(stored_task["scheduled_end"], "2040-01-01T09:30:00")
        with self.session_local() as db:
            after_history_count = db.query(TaskHistory).filter(
                TaskHistory.task_id == task["id"],
                TaskHistory.event_type == "rescheduled",
            ).count()
        self.assertEqual(after_history_count, before_history_count)

    def test_repeated_plan_with_an_advancing_reference_creates_no_lifecycle_events(self):
        task = self.create_task("Stable while time advances")
        first_request = {
            "available_start": "2040-01-01T09:00:00",
            "available_end": "2040-01-01T11:00:00",
        }
        second_request = {
            "available_start": "2040-01-01T09:15:00",
            "available_end": "2040-01-01T11:15:00",
        }

        first_response = self.client.post("/plan", json=first_request)
        self.assertEqual(first_response.status_code, 200)
        first_schedule = first_response.json()["schedule"]
        with self.session_local() as db:
            history_before = db.query(TaskHistory).filter(
                TaskHistory.task_id == task["id"]
            ).count()

        with patch("app.api.planning.PlanningEngine.generate_schedule") as generate_schedule:
            second_response = self.client.post("/plan", json=second_request)

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(
            [{k: v for k, v in item.items() if k != "reason"} for item in second_response.json()["schedule"]],
            [{k: v for k, v in item.items() if k != "reason"} for item in first_schedule],
        )
        self.assertEqual(generate_schedule.call_count, 0)
        with self.session_local() as db:
            self.assertEqual(
                db.query(TaskHistory).filter(TaskHistory.task_id == task["id"]).count(),
                history_before,
            )

    def test_partially_elapsed_slot_is_preserved_without_lifecycle_events(self):
        task = self.create_task("Currently in progress")
        planning_reference = datetime(2040, 1, 1, 9, 15)
        slot_start = datetime(2040, 1, 1, 9)
        slot_end = datetime(2040, 1, 1, 9, 30)

        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.scheduled_start = slot_start
            stored.scheduled_end = slot_end
            stored.schedule_needs_refresh = False
            stored.schedule_refresh_reason = None
            db.commit()
            history_before = db.query(TaskHistory).filter(
                TaskHistory.task_id == task["id"]
            ).count()

        with patch("app.api.planning.PlanningEngine.generate_schedule") as generate_schedule:
            response = self.client.post(
                "/plan",
                json={
                    "available_start": planning_reference.isoformat(),
                    "available_end": (planning_reference + timedelta(hours=2)).isoformat(),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate_schedule.call_count, 0)
        self.assertEqual(response.json()["schedule"][0]["scheduled_start"], slot_start.isoformat())
        self.assertEqual(response.json()["schedule"][0]["scheduled_end"], slot_end.isoformat())
        stored = self.client.get(f"/tasks/{task['id']}").json()
        self.assertEqual(stored["status"], "pending")
        with self.session_local() as db:
            self.assertEqual(
                db.query(TaskHistory).filter(TaskHistory.task_id == task["id"]).count(),
                history_before,
            )

    def test_force_replan_only_records_a_reschedule_when_the_schedule_changes(self):
        task = self.create_task("Capacity changed")
        initial = PlanningResult(
            schedule=[
                ScheduledTask(task["id"], task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30))
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        request = {"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"}
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=initial):
            self.assertEqual(self.client.post("/plan", json=request).status_code, 200)

        with self.session_local() as db:
            before_history_count = db.query(TaskHistory).filter(
                TaskHistory.task_id == task["id"], TaskHistory.event_type == "rescheduled"
            ).count()

        # Capacity changed, so the frontend may request a replan. An identical
        # resulting schedule must still be history-idempotent.
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=initial) as generate_schedule:
            response = self.client.post("/plan", json={**request, "force_replan": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate_schedule.call_count, 1)

        with self.session_local() as db:
            self.assertEqual(
                db.query(TaskHistory).filter(
                    TaskHistory.task_id == task["id"], TaskHistory.event_type == "rescheduled"
                ).count(),
                before_history_count,
            )

    def test_first_persisted_schedule_creates_one_scheduled_event(self):
        task = self.create_task("First scheduled task")
        request = {
            "available_start": "2040-01-01T09:00:00",
            "available_end": "2040-01-01T11:00:00",
        }

        self.assertEqual(self.client.post("/plan", json=request).status_code, 200)
        self.assertEqual(self.history_event_count(task["id"], "scheduled"), 1)
        scheduled_event = self.latest_history_event(task["id"], "scheduled")
        self.assertEqual(scheduled_event.new_start, datetime(2040, 1, 1, 9))
        self.assertEqual(scheduled_event.reason, "Added to your plan")

        self.assertEqual(self.client.post("/plan", json=request).status_code, 200)
        self.assertEqual(self.history_event_count(task["id"], "scheduled"), 1)
        self.assertEqual(self.history_event_count(task["id"], "rescheduled"), 0)

    def test_multiple_new_tasks_each_receive_one_scheduled_event(self):
        first = self.create_task("First new task")
        second = self.create_task("Second new task")
        request = {
            "available_start": "2040-01-01T09:00:00",
            "available_end": "2040-01-01T11:00:00",
        }

        self.assertEqual(self.client.post("/plan", json=request).status_code, 200)
        self.assertEqual(self.history_event_count(first["id"], "scheduled"), 1)
        self.assertEqual(self.history_event_count(second["id"], "scheduled"), 1)

        self.assertEqual(self.client.post("/plan", json=request).status_code, 200)
        self.assertEqual(self.history_event_count(first["id"], "scheduled"), 1)
        self.assertEqual(self.history_event_count(second["id"], "scheduled"), 1)

    def test_an_unscheduled_new_task_allows_the_planner_to_update_the_plan(self):
        scheduled_task = self.create_task("Already planned")
        first = PlanningResult(
            schedule=[
                ScheduledTask(
                    scheduled_task["id"], scheduled_task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30)
                )
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=first):
            self.assertEqual(
                self.client.post(
                    "/plan",
                    json={"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"},
                ).status_code,
                200,
            )

        new_task = self.create_task("New task")
        updated = PlanningResult(
            schedule=[
                ScheduledTask(
                    new_task["id"], new_task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30)
                ),
                ScheduledTask(
                    scheduled_task["id"], scheduled_task["title"], datetime(2040, 1, 1, 9, 30), datetime(2040, 1, 1, 10)
                ),
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=updated) as generate_schedule:
            response = self.client.post(
                "/plan",
                json={"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate_schedule.call_count, 1)
        self.assertEqual(len(response.json()["schedule"]), 2)

    def test_refresh_after_adding_a_task_keeps_the_existing_plan_start(self):
        first_task = self.create_task("First planned task")
        second_task = self.create_task("Second planned task")
        first_start = datetime(2040, 1, 1, 9)
        first_end = datetime(2040, 1, 1, 9, 30)
        second_end = datetime(2040, 1, 1, 10)
        initial_plan = PlanningResult(
            schedule=[
                ScheduledTask(first_task["id"], first_task["title"], first_start, first_end),
                ScheduledTask(second_task["id"], second_task["title"], first_end, second_end),
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        request = {"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"}
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=initial_plan):
            self.assertEqual(self.client.post("/plan", json=request).status_code, 200)

        new_task = self.create_task("New planning work")
        refreshed_plan = PlanningResult(
            schedule=[
                ScheduledTask(first_task["id"], first_task["title"], first_start, first_end),
                ScheduledTask(second_task["id"], second_task["title"], first_end, second_end),
                ScheduledTask(new_task["id"], new_task["title"], second_end, datetime(2040, 1, 1, 10, 30)),
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=refreshed_plan) as generate_schedule:
            response = self.client.post(
                "/plan",
                json={**request, "available_start": "2040-01-01T09:20:00"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate_schedule.call_count, 1)
        self.assertEqual(generate_schedule.call_args.args[1], first_start)
        self.assertEqual(
            self.client.get(f"/tasks/{first_task['id']}").json()["scheduled_start"],
            "2040-01-01T09:00:00",
        )

    def test_stale_persisted_schedule_enters_missed_then_recovered_lifecycle(self):
        task = self.create_task(
            "Expired slot", deadline="2040-01-03T12:00:00"
        )
        requested_start = datetime(2040, 1, 2, 9)
        requested_end = datetime(2040, 1, 2, 11)
        stale_start = requested_start - timedelta(days=1, hours=1)
        stale_end = stale_start + timedelta(minutes=30)

        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.scheduled_start = stale_start
            stored.scheduled_end = stale_end
            stored.schedule_needs_refresh = True
            stored.schedule_refresh_reason = "added"
            db.commit()

        response = self.client.post(
            "/plan",
            json={
                "available_start": requested_start.isoformat(),
                "available_end": requested_end.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        scheduled = response.json()["schedule"]
        self.assertEqual(scheduled[0]["scheduled_start"], requested_start.isoformat())
        self.assertGreaterEqual(
            datetime.fromisoformat(scheduled[0]["scheduled_end"]), requested_start
        )
        event = self.latest_history_event(task["id"], "rescheduled")
        self.assertIsNone(event)
        self.assertEqual(self.history_event_count(task["id"], "missed"), 1)
        recovered = self.latest_history_event(task["id"], "recovered")
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered.new_start, requested_start)
        self.assertEqual(self.client.get(f"/tasks/{task['id']}").json()["status"], "pending")
        self.assertEqual(self.history_event_count(task["id"], "scheduled"), 0)

        summary = self.client.get("/history/summary?range=all").json()
        self.assertEqual(summary["missed"], 1)
        self.assertEqual(summary["recovered"], 1)
        self.assertEqual(summary["rescheduled"], 0)

        # The recovered task now has a persisted plan, so reopening that plan
        # must not start another missed/recovered cycle.
        self.assertEqual(
            self.client.post(
                "/plan",
                json={
                    "available_start": requested_start.isoformat(),
                    "available_end": requested_end.isoformat(),
                },
            ).status_code,
            200,
        )
        self.assertEqual(self.history_event_count(task["id"], "missed"), 1)
        self.assertEqual(self.history_event_count(task["id"], "recovered"), 1)

    def test_schedule_ending_at_the_planning_reference_is_missed_once(self):
        requested_start = datetime(2040, 1, 2, 9)
        task = self.create_task(
            "Expired at the reference", deadline="2040-01-03T12:00:00"
        )
        expired_start = requested_start - timedelta(minutes=30)

        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.scheduled_start = expired_start
            stored.scheduled_end = requested_start
            stored.schedule_needs_refresh = False
            db.commit()

        response = self.client.post(
            "/plan",
            json={
                "available_start": requested_start.isoformat(),
                "available_end": (requested_start + timedelta(hours=1)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        missed = self.latest_history_event(task["id"], "missed")
        self.assertIsNotNone(missed)
        self.assertEqual(missed.old_start, expired_start)
        self.assertEqual(missed.old_end, requested_start)
        self.assertEqual(self.history_event_count(task["id"], "missed"), 1)
        self.assertEqual(self.history_event_count(task["id"], "recovered"), 1)
        self.assertEqual(self.history_event_count(task["id"], "scheduled"), 0)
        self.assertEqual(self.history_event_count(task["id"], "rescheduled"), 0)

        self.assertEqual(
            self.client.post(
                "/plan",
                json={
                    "available_start": requested_start.isoformat(),
                    "available_end": (requested_start + timedelta(hours=1)).isoformat(),
                },
            ).status_code,
            200,
        )
        self.assertEqual(self.history_event_count(task["id"], "missed"), 1)
        self.assertEqual(self.history_event_count(task["id"], "recovered"), 1)

    def test_stale_persisted_schedule_stays_missed_when_it_cannot_fit(self):
        task = self.create_task(
            "Expired and too long",
            duration_minutes=90,
            deadline="2040-01-03T12:00:00",
        )
        requested_start = datetime(2040, 1, 2, 9)
        stale_start = requested_start - timedelta(days=1, hours=1)

        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.scheduled_start = stale_start
            stored.scheduled_end = stale_start + timedelta(minutes=90)
            stored.schedule_needs_refresh = False
            db.commit()

        response = self.client.post(
            "/plan",
            json={
                "available_start": requested_start.isoformat(),
                "available_end": (requested_start + timedelta(hours=1)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["schedule"], [])
        stored = self.client.get(f"/tasks/{task['id']}").json()
        self.assertEqual(stored["status"], "missed")
        self.assertIsNone(stored["scheduled_start"])
        self.assertIsNone(stored["scheduled_end"])
        self.assertEqual(self.history_event_count(task["id"], "missed"), 1)
        self.assertEqual(self.history_event_count(task["id"], "recovered"), 0)
        self.assertEqual(self.history_event_count(task["id"], "rescheduled"), 0)
        self.assertEqual(self.history_event_count(task["id"], "scheduled"), 0)

        # The open missed cycle prevents repeated Plan My Day calls from
        # manufacturing another missed event.
        self.assertEqual(
            self.client.post(
                "/plan",
                json={
                    "available_start": requested_start.isoformat(),
                    "available_end": (requested_start + timedelta(hours=1)).isoformat(),
                },
            ).status_code,
            200,
        )
        self.assertEqual(self.history_event_count(task["id"], "missed"), 1)

    def test_deadline_overdue_without_a_schedule_does_not_become_missed(self):
        requested_start = datetime(2040, 1, 2, 9)
        task = self.create_task(
            "Overdue but never scheduled",
            deadline=(requested_start - timedelta(hours=1)).isoformat(),
        )

        response = self.client.post(
            "/plan",
            json={
                "available_start": requested_start.isoformat(),
                "available_end": (requested_start + timedelta(hours=1)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.history_event_count(task["id"], "missed"), 0)
        self.assertEqual(self.history_event_count(task["id"], "scheduled"), 1)
        self.assertEqual(self.client.get(f"/tasks/{task['id']}").json()["status"], "pending")

    def test_mixed_stale_and_future_slots_use_distinct_history_lifecycles(self):
        requested_start = datetime(2040, 1, 2, 9)
        stale = self.create_task(
            "Expired opportunity", deadline="2040-01-03T09:00:00"
        )
        future = self.create_task(
            "Still valid", deadline="2040-01-04T09:00:00"
        )
        later_future = self.create_task(
            "Also still valid", deadline="2040-01-05T09:00:00"
        )

        with self.session_local() as db:
            stale_task = db.get(Task, stale["id"])
            future_task = db.get(Task, future["id"])
            stale_task.scheduled_start = requested_start - timedelta(hours=1)
            stale_task.scheduled_end = requested_start - timedelta(minutes=30)
            stale_task.schedule_needs_refresh = False
            future_task.scheduled_start = requested_start + timedelta(minutes=30)
            future_task.scheduled_end = requested_start + timedelta(hours=1)
            future_task.schedule_needs_refresh = False
            later_future_task = db.get(Task, later_future["id"])
            later_future_task.scheduled_start = requested_start + timedelta(hours=1)
            later_future_task.scheduled_end = requested_start + timedelta(hours=1, minutes=30)
            later_future_task.schedule_needs_refresh = False
            db.commit()

        response = self.client.post(
            "/plan",
            json={
                "available_start": requested_start.isoformat(),
                "available_end": (requested_start + timedelta(hours=2)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        schedule = {item["task_id"]: item for item in response.json()["schedule"]}
        self.assertEqual(schedule[stale["id"]]["scheduled_start"], requested_start.isoformat())
        self.assertEqual(
            schedule[future["id"]]["scheduled_start"],
            (requested_start + timedelta(minutes=30)).isoformat(),
        )
        self.assertEqual(
            schedule[later_future["id"]]["scheduled_start"],
            (requested_start + timedelta(hours=1)).isoformat(),
        )
        self.assertEqual(self.history_event_count(stale["id"], "missed"), 1)
        self.assertEqual(self.history_event_count(stale["id"], "recovered"), 1)
        self.assertEqual(self.history_event_count(stale["id"], "rescheduled"), 0)
        self.assertEqual(self.history_event_count(future["id"], "rescheduled"), 0)
        self.assertEqual(self.history_event_count(later_future["id"], "rescheduled"), 0)

    def test_new_task_only_moves_the_existing_task_its_rank_displaces(self):
        first_task = self.create_task(
            "First", deadline="2040-01-01T09:45:00"
        )
        later_task = self.create_task(
            "Later", deadline="2040-01-01T10:30:00"
        )
        original_request = {
            "available_start": "2040-01-01T09:00:00",
            "available_end": "2040-01-01T11:00:00",
        }
        self.assertEqual(self.client.post("/plan", json=original_request).status_code, 200)

        inserted_task = self.create_task(
            "Inserted", deadline="2040-01-01T10:00:00"
        )
        response = self.client.post(
            "/plan",
            json={**original_request, "available_start": "2040-01-01T09:20:00"},
        )

        self.assertEqual(response.status_code, 200)
        schedule = {item["task_id"]: item for item in response.json()["schedule"]}
        self.assertEqual(schedule[first_task["id"]]["scheduled_start"], "2040-01-01T09:00:00")
        self.assertEqual(schedule[inserted_task["id"]]["scheduled_start"], "2040-01-01T09:30:00")
        self.assertEqual(schedule[later_task["id"]]["scheduled_start"], "2040-01-01T10:00:00")
        self.assertEqual(self.history_event_count(inserted_task["id"], "scheduled"), 1)
        self.assertEqual(self.history_event_count(first_task["id"], "scheduled"), 1)
        self.assertEqual(self.history_event_count(later_task["id"], "scheduled"), 1)
        self.assertEqual(self.history_event_count(first_task["id"], "rescheduled"), 0)
        self.assertEqual(self.history_event_count(later_task["id"], "rescheduled"), 1)
        self.assertEqual(
            self.latest_history_event(later_task["id"], "rescheduled").reason,
            "Schedule changed after adding a task",
        )

    def test_edit_keeps_the_previous_schedule_until_the_refresh_runs(self):
        task = self.create_task("Keep schedule while editing")
        initial = PlanningResult(
            schedule=[
                ScheduledTask(task["id"], task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30))
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        request = {"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"}
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=initial):
            self.assertEqual(self.client.post("/plan", json=request).status_code, 200)

        edited = self.client.get(f"/tasks/{task['id']}").json()
        edited["priority"] = "medium"
        self.assertEqual(self.client.put(f"/tasks/{task['id']}", json=edited).status_code, 200)

        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            self.assertEqual(stored.scheduled_start, datetime(2040, 1, 1, 9))
            self.assertEqual(stored.scheduled_end, datetime(2040, 1, 1, 9, 30))
            self.assertTrue(stored.schedule_needs_refresh)

    def test_planning_relevant_task_edit_invalidates_the_saved_plan(self):
        task = self.create_task("Edited task")
        initial = PlanningResult(
            schedule=[
                ScheduledTask(task["id"], task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30))
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        request = {"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"}
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=initial):
            self.assertEqual(self.client.post("/plan", json=request).status_code, 200)

        edited_task = self.client.get(f"/tasks/{task['id']}").json()
        edited_task["duration_minutes"] = 45
        self.assertEqual(self.client.put(f"/tasks/{task['id']}", json=edited_task).status_code, 200)

        updated = PlanningResult(
            schedule=[
                ScheduledTask(task["id"], task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 45))
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=updated) as generate_schedule:
            response = self.client.post("/plan", json=request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate_schedule.call_count, 1)
        self.assertEqual(
            self.latest_history_event(task["id"], "rescheduled").reason,
            "Schedule changed after editing a task",
        )

    def test_manual_replan_uses_the_generic_plan_reshaped_reason(self):
        task = self.create_task("Manual reshape")
        request = {"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"}
        first = PlanningResult(
            schedule=[
                ScheduledTask(task["id"], task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30))
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=first):
            self.assertEqual(self.client.post("/plan", json=request).status_code, 200)

        reshaped = PlanningResult(
            schedule=[
                ScheduledTask(task["id"], task["title"], datetime(2040, 1, 1, 9, 30), datetime(2040, 1, 1, 10))
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=reshaped):
            response = self.client.post("/plan", json={**request, "force_replan": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.latest_history_event(task["id"], "rescheduled").reason,
            "Plan reshaped",
        )

    def test_overloaded_plan_is_idempotent_when_some_tasks_are_intentionally_unscheduled(self):
        scheduled_task = self.create_task("Fits today", duration_minutes=60)
        unscheduled_task = self.create_task("Later work", duration_minutes=195)
        first_plan = PlanningResult(
            schedule=[
                ScheduledTask(
                    scheduled_task["id"],
                    scheduled_task["title"],
                    datetime(2040, 1, 1, 9),
                    datetime(2040, 1, 1, 10),
                )
            ],
            is_overloaded=True,
            unscheduled_minutes=195,
        )
        request = {"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"}
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=first_plan) as generate_schedule:
            first_response = self.client.post("/plan", json=request)
            self.assertEqual(generate_schedule.call_count, 1)

        self.assertTrue(first_response.json()["is_overloaded"])
        self.assertEqual(
            self.client.get(f"/tasks/{unscheduled_task['id']}").json()["scheduled_start"],
            None,
        )
        with self.session_local() as db:
            history_before = db.query(TaskHistory).filter(
                TaskHistory.event_type == "rescheduled"
            ).count()

        shifted_plan = PlanningResult(
            schedule=[
                ScheduledTask(
                    scheduled_task["id"],
                    scheduled_task["title"],
                    datetime(2040, 1, 1, 9, 30),
                    datetime(2040, 1, 1, 10, 30),
                )
            ],
            is_overloaded=True,
            unscheduled_minutes=195,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=shifted_plan) as generate_schedule:
            second_response = self.client.post(
                "/plan",
                json={"available_start": "2040-01-01T09:20:00", "available_end": "2040-01-01T11:00:00"},
            )
            self.assertEqual(generate_schedule.call_count, 0)

        self.assertTrue(second_response.json()["is_overloaded"])
        self.assertEqual(second_response.json()["unscheduled_minutes"], 195)
        self.assertEqual(second_response.json()["schedule"][0]["scheduled_start"], "2040-01-01T09:00:00")
        with self.session_local() as db:
            history_after = db.query(TaskHistory).filter(
                TaskHistory.event_type == "rescheduled"
            ).count()
        self.assertEqual(history_after, history_before)

    def test_missed_event_preserves_task_title_snapshot(self):
        requested_start = datetime(2040, 1, 2, 9)
        task = self.create_task(
            "A missed opportunity",
            deadline="2040-01-03T12:00:00",
        )
        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.scheduled_start = requested_start - timedelta(minutes=30)
            stored.scheduled_end = requested_start
            stored.schedule_needs_refresh = False
            db.commit()

        response = self.client.post(
            "/plan",
            json={
                "available_start": requested_start.isoformat(),
                "available_end": (requested_start + timedelta(hours=2)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.history_event_count(task["id"], "missed"), 1)
        with self.session_local() as db:
            missed = db.query(TaskHistory).filter(
                TaskHistory.task_id == task["id"],
                TaskHistory.event_type == "missed",
            ).one()
            self.assertEqual(missed.task_title, "A missed opportunity")

    def test_plan_recovers_an_outstanding_missed_task_only_when_it_is_scheduled(self):
        task = self.create_task("Needs a reset")
        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.status = "missed"
            stored.schedule_needs_refresh = True
            db.add(TaskHistory(task_id=task["id"], user_id=stored.user_id, event_type="missed"))
            db.commit()

        plan = PlanningResult(
            schedule=[ScheduledTask(task["id"], task["title"], datetime(2040, 1, 1, 9), datetime(2040, 1, 1, 9, 30))],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        request = {"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T10:00:00"}
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=plan):
            self.assertEqual(self.client.post("/plan", json=request).status_code, 200)

        stored = self.client.get(f"/tasks/{task['id']}").json()
        self.assertEqual(stored["status"], "pending")
        self.assertTrue(stored["was_replanned"])
        with self.session_local() as db:
            recovered = db.query(TaskHistory).filter(
                TaskHistory.task_id == task["id"], TaskHistory.event_type == "recovered"
            ).one()
            self.assertEqual(recovered.reason, "Missed task was included in Plan My Day")
            self.assertEqual(recovered.new_start, datetime(2040, 1, 1, 9))
            self.assertEqual(
                db.query(TaskHistory).filter(
                    TaskHistory.task_id == task["id"],
                    TaskHistory.event_type == "rescheduled",
                ).count(),
                0,
            )

        # The persisted plan short-circuits before creating another recovery.
        self.assertEqual(self.client.post("/plan", json=request).status_code, 200)
        with self.session_local() as db:
            self.assertEqual(db.query(TaskHistory).filter(TaskHistory.task_id == task["id"], TaskHistory.event_type == "recovered").count(), 1)

    def test_recovered_slot_can_open_a_new_missed_cycle_before_its_deadline(self):
        requested_start = datetime(2040, 1, 2, 9)
        task = self.create_task(
            "A second opportunity",
            deadline="2040-01-03T12:00:00",
        )
        first_expired_start = requested_start - timedelta(minutes=30)

        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.scheduled_start = first_expired_start
            stored.scheduled_end = requested_start
            stored.schedule_needs_refresh = False
            db.commit()

        first = self.client.post(
            "/plan",
            json={
                "available_start": requested_start.isoformat(),
                "available_end": (requested_start + timedelta(hours=2)).isoformat(),
            },
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.history_event_count(task["id"], "missed"), 1)
        self.assertEqual(self.history_event_count(task["id"], "recovered"), 1)

        recovered_slot = self.client.get(f"/tasks/{task['id']}").json()
        second_reference = datetime.fromisoformat(recovered_slot["scheduled_end"])
        second = self.client.post(
            "/plan",
            json={
                "available_start": second_reference.isoformat(),
                "available_end": (second_reference + timedelta(hours=2)).isoformat(),
            },
        )

        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.history_event_count(task["id"], "missed"), 2)
        self.assertEqual(self.history_event_count(task["id"], "recovered"), 2)
        self.assertEqual(self.history_event_count(task["id"], "scheduled"), 0)
        self.assertEqual(self.history_event_count(task["id"], "rescheduled"), 0)


    def test_recovery_takes_precedence_while_other_tasks_can_reschedule(self):
        recovered_task = self.create_task("Recover this task")
        moved_task = self.create_task("Move this task")
        recovered_old_start = datetime(2040, 1, 1, 9)
        recovered_old_end = datetime(2040, 1, 1, 9, 30)
        moved_old_start = datetime(2040, 1, 1, 9, 30)
        moved_old_end = datetime(2040, 1, 1, 10)
        moved_new_start = datetime(2040, 1, 1, 9)
        moved_new_end = datetime(2040, 1, 1, 9, 30)
        recovered_new_start = datetime(2040, 1, 1, 9, 30)
        recovered_new_end = datetime(2040, 1, 1, 10)

        with self.session_local() as db:
            missed = db.get(Task, recovered_task["id"])
            moved = db.get(Task, moved_task["id"])
            missed.status = "missed"
            missed.scheduled_start = recovered_old_start
            missed.scheduled_end = recovered_old_end
            missed.schedule_needs_refresh = True
            moved.scheduled_start = moved_old_start
            moved.scheduled_end = moved_old_end
            moved.schedule_needs_refresh = True
            db.add(
                TaskHistory(
                    task_id=missed.id,
                    user_id=missed.user_id,
                    event_type="missed",
                    old_start=recovered_old_start,
                    old_end=recovered_old_end,
                )
            )
            db.commit()

        plan = PlanningResult(
            schedule=[
                ScheduledTask(moved_task["id"], moved_task["title"], moved_new_start, moved_new_end),
                ScheduledTask(
                    recovered_task["id"],
                    recovered_task["title"],
                    recovered_new_start,
                    recovered_new_end,
                ),
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=plan):
            response = self.client.post(
                "/plan",
                json={"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T11:00:00"},
            )

        self.assertEqual(response.status_code, 200)
        recovered_event = self.latest_history_event(recovered_task["id"], "recovered")
        self.assertEqual(recovered_event.new_start, recovered_new_start)
        self.assertEqual(self.history_event_count(recovered_task["id"], "rescheduled"), 0)
        moved_event = self.latest_history_event(moved_task["id"], "rescheduled")
        self.assertEqual(moved_event.old_start, moved_old_start)
        self.assertEqual(moved_event.old_end, moved_old_end)
        self.assertEqual(moved_event.new_start, moved_new_start)
        self.assertEqual(moved_event.new_end, moved_new_end)

    def test_plan_leaves_an_outstanding_missed_task_unrecovered_when_it_does_not_fit(self):
        task = self.create_task("Still needs a reset", duration_minutes=90)
        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.status = "missed"
            stored.schedule_needs_refresh = True
            db.add(TaskHistory(task_id=task["id"], user_id=stored.user_id, event_type="missed"))
            db.commit()

        plan = PlanningResult(schedule=[], is_overloaded=True, unscheduled_minutes=90)
        with patch("app.api.planning.PlanningEngine.generate_schedule", return_value=plan):
            self.assertEqual(self.client.post("/plan", json={"available_start": "2040-01-01T09:00:00", "available_end": "2040-01-01T10:00:00"}).status_code, 200)

        stored = self.client.get(f"/tasks/{task['id']}").json()
        self.assertEqual(stored["status"], "missed")
        self.assertFalse(stored["was_replanned"])
        with self.session_local() as db:
            self.assertEqual(db.query(TaskHistory).filter(TaskHistory.task_id == task["id"], TaskHistory.event_type == "recovered").count(), 0)

    def test_recovery_never_persists_a_slot_that_is_already_past(self):
        task = self.create_task(
            "Never recover into the past",
            deadline="2040-01-03T12:00:00",
        )

        planning_reference = datetime(2040, 1, 2, 11, 28)
        stale_start = datetime(2040, 1, 2, 10, 30)
        stale_end = datetime(2040, 1, 2, 11, 0)

        with self.session_local() as db:
            stored = db.get(Task, task["id"])
            stored.status = "missed"
            stored.scheduled_start = stale_start
            stored.scheduled_end = stale_end
            stored.schedule_needs_refresh = True

            db.add(
                TaskHistory(
                    task_id=stored.id,
                    user_id=stored.user_id,
                    event_type="missed",
                    old_start=stale_start,
                    old_end=stale_end,
                )
            )
            db.commit()

        # The planner must never return a recovered slot that has
        # already ended before the current planning reference.
        valid_start = planning_reference
        valid_end = planning_reference + timedelta(minutes=30)

        plan = PlanningResult(
            schedule=[
                ScheduledTask(
                    task["id"],
                    task["title"],
                    valid_start,
                    valid_end,
                )
            ],
            is_overloaded=False,
            unscheduled_minutes=0,
        )

        with patch(
            "app.api.planning.PlanningEngine.generate_schedule",
            return_value=plan,
        ):
            response = self.client.post(
                "/plan",
                json={
                    "available_start": planning_reference.isoformat(),
                    "available_end": (
                        planning_reference + timedelta(hours=2)
                    ).isoformat(),
                },
            )

        self.assertEqual(response.status_code, 200)

        scheduled = response.json()["schedule"]
        self.assertEqual(len(scheduled), 1)

        recovered_start = datetime.fromisoformat(
            scheduled[0]["scheduled_start"]
        )
        recovered_end = datetime.fromisoformat(
            scheduled[0]["scheduled_end"]
        )

        self.assertGreaterEqual(recovered_start, planning_reference)
        self.assertGreater(recovered_end, recovered_start)

        stored = self.client.get(
            f"/tasks/{task['id']}"
        ).json()

        self.assertEqual(
            stored["scheduled_start"],
            valid_start.isoformat(),
        )
        self.assertEqual(
            stored["scheduled_end"],
            valid_end.isoformat(),
        )
        self.assertEqual(stored["status"], "pending")

        self.assertEqual(
            self.history_event_count(task["id"], "missed"),
            1,
        )
        self.assertEqual(
            self.history_event_count(task["id"], "recovered"),
            1,
        )
        self.assertEqual(
            self.history_event_count(task["id"], "rescheduled"),
            0,
        )
        self.assertEqual(
            self.history_event_count(task["id"], "scheduled"),
            0,
        )           


if __name__ == "__main__":
    unittest.main()
