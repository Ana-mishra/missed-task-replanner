"""Unit tests for PlantService.

All tests pin the clock via the `now` parameter — no real wall-clock usage.
The `now` values are IST-aware datetimes so the service receives pre-tagged
timestamps that it can trust.
"""

import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models.task_history import TaskHistory
from app.services.plant import PlantService, _stage_for

IST = ZoneInfo("Asia/Kolkata")


def ist(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime:
    """Return an IST-aware datetime for convenience."""
    return datetime(year, month, day, hour, minute, tzinfo=IST)


def completed_event(record_id: int, ts: datetime) -> TaskHistory:
    """Build a minimal completed TaskHistory row."""
    return TaskHistory(
        id=record_id,
        task_id=1,
        event_type="completed",
        timestamp=ts,
    )


def other_event(record_id: int, ts: datetime, event_type: str = "scheduled") -> TaskHistory:
    """Build a non-completion history row to verify it is ignored."""
    return TaskHistory(
        id=record_id,
        task_id=1,
        event_type=event_type,
        timestamp=ts,
    )


class PlantServiceGrowthDaysTests(unittest.TestCase):
    """Growth Day counting — distinct IST calendar dates."""

    def setUp(self):
        self.service = PlantService()
        self.now = ist(2026, 9, 23)

    # --- Test 1: no completed tasks ----------------------------------------

    def test_no_completed_tasks_returns_zero_growth_days(self):
        result = self.service.calculate([], self.now)
        self.assertEqual(result.growth_days, 0)
        self.assertEqual(result.stage, "seed")
        self.assertFalse(result.completed_today)
        self.assertFalse(result.grew_today)

    # --- Test 2: one completed task today ----------------------------------

    def test_one_completion_today_gives_one_growth_day(self):
        records = [completed_event(1, ist(2026, 9, 23, 10))]
        result = self.service.calculate(records, self.now)

        self.assertEqual(result.growth_days, 1)
        self.assertEqual(result.stage, "sprout")
        self.assertTrue(result.completed_today)
        self.assertTrue(result.grew_today)

    # --- Test 3: five completions on same day = still 1 Growth Day ---------

    def test_five_completions_same_day_count_as_one_growth_day(self):
        records = [
            completed_event(i, ist(2026, 9, 23, 9 + i))
            for i in range(5)
        ]
        result = self.service.calculate(records, self.now)
        self.assertEqual(result.growth_days, 1)

    # --- Test 4: one completion on each of three different days = 3 --------

    def test_one_completion_on_three_days_gives_three_growth_days(self):
        records = [
            completed_event(1, ist(2026, 9, 21, 10)),
            completed_event(2, ist(2026, 9, 22, 10)),
            completed_event(3, ist(2026, 9, 23, 10)),
        ]
        result = self.service.calculate(records, self.now)
        self.assertEqual(result.growth_days, 3)

    # --- Test 5: midnight IST boundary — two completions = two Growth Days -

    def test_midnight_ist_boundary_counts_as_two_growth_days(self):
        # 23:59 IST on one day, 00:01 IST on the next
        before_midnight = ist(2026, 9, 22, 23, 59)
        after_midnight = ist(2026, 9, 23, 0, 1)
        records = [
            completed_event(1, before_midnight),
            completed_event(2, after_midnight),
        ]
        result = self.service.calculate(records, self.now)
        self.assertEqual(result.growth_days, 2)

    # --- Test 6: missed day does not decrease growth days ------------------

    def test_missed_day_does_not_decrease_growth_days(self):
        # Completions on days 1 and 3; day 2 is missed.
        records = [
            completed_event(1, ist(2026, 9, 21, 10)),
            completed_event(2, ist(2026, 9, 23, 10)),
        ]
        # Observe on day 4 — day 2 was missed, growth should be 2 not 1.
        result = self.service.calculate(records, ist(2026, 9, 24))
        self.assertEqual(result.growth_days, 2)

    # --- Test 7: multiple missed days, growth_days unchanged, gap increases -

    def test_multiple_missed_days_growth_unchanged_gap_increases(self):
        records = [completed_event(1, ist(2026, 9, 15, 10))]
        # Observe 8 days later — many missed days.
        now = ist(2026, 9, 23)
        result = self.service.calculate(records, now)
        self.assertEqual(result.growth_days, 1)
        self.assertEqual(result.days_since_last_growth, 8)

    # --- Test 8: completion after missed days increments growth by exactly 1

    def test_completion_after_missed_days_increments_growth_by_one(self):
        past = ist(2026, 9, 15, 10)
        today_completion = ist(2026, 9, 23, 9)
        records = [
            completed_event(1, past),
            completed_event(2, today_completion),
        ]
        result = self.service.calculate(records, ist(2026, 9, 23))
        self.assertEqual(result.growth_days, 2)
        self.assertEqual(result.days_since_last_growth, 0)
        self.assertEqual(result.vitality, "healthy")

    # --- Non-completion events must not count as growth days ---------------

    def test_non_completion_events_are_ignored(self):
        records = [
            other_event(1, ist(2026, 9, 23, 10), "scheduled"),
            other_event(2, ist(2026, 9, 23, 11), "missed"),
            other_event(3, ist(2026, 9, 23, 12), "rescheduled"),
            other_event(4, ist(2026, 9, 23, 13), "recovered"),
            other_event(5, ist(2026, 9, 23, 14), "overdue"),
        ]
        result = self.service.calculate(records, self.now)
        self.assertEqual(result.growth_days, 0)
        self.assertEqual(result.stage, "seed")

    # --- Future completions must not be counted ----------------------------

    def test_future_completion_not_counted(self):
        future = ist(2026, 9, 24, 10)  # tomorrow
        records = [completed_event(1, future)]
        result = self.service.calculate(records, self.now)
        self.assertEqual(result.growth_days, 0)


class PlantServiceStageTests(unittest.TestCase):
    """Stage boundaries — covers every threshold in the spec."""

    def _growth_days_result(self, growth_days: int):
        """Build artificial history producing exactly `growth_days` growth days."""
        from datetime import date as date_t, timedelta
        from zoneinfo import ZoneInfo
        _IST = ZoneInfo("Asia/Kolkata")
        base = datetime(2026, 1, 1, 10, 0, tzinfo=_IST)
        records = [
            completed_event(i + 1, base + timedelta(days=i))
            for i in range(growth_days)
        ]
        # Pin clock to a day well after all records so no future-filtering.
        now = base + timedelta(days=growth_days + 10)
        return PlantService().calculate(records, now)

    def test_stage_0_growth_days_is_seed(self):
        result = self._growth_days_result(0)
        self.assertEqual(result.stage, "seed")
        self.assertEqual(result.stage_progress, 0.0)

    def test_stage_1_growth_day_is_sprout(self):
        result = self._growth_days_result(1)
        self.assertEqual(result.stage, "sprout")

    def test_stage_2_growth_days_is_sprout(self):
        result = self._growth_days_result(2)
        self.assertEqual(result.stage, "sprout")

    def test_stage_3_growth_days_is_young_plant(self):
        result = self._growth_days_result(3)
        self.assertEqual(result.stage, "young_plant")

    def test_stage_6_growth_days_is_young_plant(self):
        result = self._growth_days_result(6)
        self.assertEqual(result.stage, "young_plant")

    def test_stage_7_growth_days_is_growing(self):
        result = self._growth_days_result(7)
        self.assertEqual(result.stage, "growing")

    def test_stage_13_growth_days_is_growing(self):
        result = self._growth_days_result(13)
        self.assertEqual(result.stage, "growing")

    def test_stage_14_growth_days_is_flourishing(self):
        result = self._growth_days_result(14)
        self.assertEqual(result.stage, "flourishing")

    def test_stage_29_growth_days_is_flourishing(self):
        result = self._growth_days_result(29)
        self.assertEqual(result.stage, "flourishing")

    def test_stage_30_growth_days_is_mature(self):
        result = self._growth_days_result(30)
        self.assertEqual(result.stage, "mature")
        self.assertEqual(result.stage_progress, 100.0)

    def test_stage_progress_seed_halfway(self):
        # Seed: 0/1 threshold, so 0 of 1 → 0 %
        stage, progress = _stage_for(0)
        self.assertEqual(stage, "seed")
        self.assertEqual(progress, 0.0)

    def test_stage_progress_sprout_one_of_two(self):
        # Sprout: threshold 1→3, span 2; at 1 → 0/2 = 0 %
        stage, progress = _stage_for(1)
        self.assertEqual(stage, "sprout")
        self.assertEqual(progress, 0.0)

    def test_stage_progress_sprout_two_of_two(self):
        # At 2 → 1/2 = 50 %
        stage, progress = _stage_for(2)
        self.assertEqual(stage, "sprout")
        self.assertEqual(progress, 50.0)

    def test_stage_progress_mature_is_100(self):
        stage, progress = _stage_for(30)
        self.assertEqual(stage, "mature")
        self.assertEqual(progress, 100.0)

    def test_stage_progress_mature_deep_is_still_100(self):
        stage, progress = _stage_for(100)
        self.assertEqual(stage, "mature")
        self.assertEqual(progress, 100.0)


class PlantServiceVitalityTests(unittest.TestCase):
    """Vitality derivation from recency."""

    def setUp(self):
        self.service = PlantService()

    def test_completed_today_is_healthy(self):
        now = ist(2026, 9, 23, 12)
        records = [completed_event(1, ist(2026, 9, 23, 9))]
        result = self.service.calculate(records, now)
        self.assertEqual(result.vitality, "healthy")

    def test_no_completion_today_previous_yesterday_is_waiting(self):
        now = ist(2026, 9, 23, 12)
        # Last growth was yesterday
        records = [completed_event(1, ist(2026, 9, 22, 10))]
        result = self.service.calculate(records, now)
        self.assertEqual(result.vitality, "waiting")
        self.assertFalse(result.completed_today)

    def test_two_missed_days_is_droopy(self):
        now = ist(2026, 9, 23, 12)
        records = [completed_event(1, ist(2026, 9, 21, 10))]
        result = self.service.calculate(records, now)
        self.assertEqual(result.vitality, "droopy")
        self.assertEqual(result.days_since_last_growth, 2)

    def test_four_missed_days_is_droopy(self):
        now = ist(2026, 9, 23, 12)
        records = [completed_event(1, ist(2026, 9, 19, 10))]
        result = self.service.calculate(records, now)
        self.assertEqual(result.vitality, "droopy")
        self.assertEqual(result.days_since_last_growth, 4)

    def test_five_missed_days_is_very_droopy(self):
        now = ist(2026, 9, 23, 12)
        records = [completed_event(1, ist(2026, 9, 18, 10))]
        result = self.service.calculate(records, now)
        self.assertEqual(result.vitality, "very_droopy")

    def test_no_completions_ever_is_very_droopy(self):
        result = self.service.calculate([], ist(2026, 9, 23))
        self.assertEqual(result.vitality, "very_droopy")


class PlantServiceStreakTests(unittest.TestCase):
    """current_streak_days is IST-date-based and independent of growth_days."""

    def setUp(self):
        self.service = PlantService()

    def test_no_completions_streak_is_zero(self):
        result = self.service.calculate([], ist(2026, 9, 23))
        self.assertEqual(result.current_streak_days, 0)

    def test_consecutive_streak_counted_correctly(self):
        records = [
            completed_event(1, ist(2026, 9, 21, 10)),
            completed_event(2, ist(2026, 9, 22, 10)),
            completed_event(3, ist(2026, 9, 23, 10)),
        ]
        result = self.service.calculate(records, ist(2026, 9, 23, 12))
        self.assertEqual(result.current_streak_days, 3)

    def test_gap_day_breaks_streak_but_not_growth(self):
        # Growth on day 1 and day 3, gap on day 2.
        records = [
            completed_event(1, ist(2026, 9, 21, 10)),
            completed_event(2, ist(2026, 9, 23, 10)),
        ]
        result = self.service.calculate(records, ist(2026, 9, 23, 12))
        # Streak: today(23) is in growth_dates, yesterday(22) is not → streak=1
        self.assertEqual(result.current_streak_days, 1)
        # Growth days: 2 (days 21 and 23)
        self.assertEqual(result.growth_days, 2)

    def test_user_can_have_growth_without_current_streak(self):
        """growth_days=20, current_streak_days=0 is a valid state."""
        # 20 completions all more than 2 days ago
        records = [
            completed_event(i + 1, ist(2026, 9, 1 + i, 10))
            for i in range(20)
        ]
        # Now observe 3 days after the last completion — streak is broken.
        now = ist(2026, 9, 23)  # last was sep 20
        result = self.service.calculate(records, now)
        self.assertEqual(result.growth_days, 20)
        self.assertEqual(result.current_streak_days, 0)

    def test_incomplete_today_does_not_break_streak(self):
        """If the user has not completed a task yet today, we check yesterday."""
        # Completions yesterday and the day before — no completion today yet.
        records = [
            completed_event(1, ist(2026, 9, 22, 10)),
            completed_event(2, ist(2026, 9, 21, 10)),
        ]
        now = ist(2026, 9, 23, 8)  # early morning, nothing done yet today
        result = self.service.calculate(records, now)
        self.assertFalse(result.completed_today)
        self.assertEqual(result.current_streak_days, 2)


class PlantServiceAnimationTriggerTests(unittest.TestCase):
    """Verify grew_today / completed_today semantics for animation support."""

    def setUp(self):
        self.service = PlantService()

    def test_before_first_completion_both_false(self):
        now = ist(2026, 9, 23, 8)
        result = self.service.calculate([], now)
        self.assertFalse(result.completed_today)
        self.assertFalse(result.grew_today)

    def test_after_first_completion_both_true(self):
        now = ist(2026, 9, 23, 10)
        records = [completed_event(1, ist(2026, 9, 23, 9))]
        result = self.service.calculate(records, now)
        self.assertTrue(result.completed_today)
        self.assertTrue(result.grew_today)

    def test_after_second_completion_both_still_true_no_double_growth(self):
        now = ist(2026, 9, 23, 11)
        records = [
            completed_event(1, ist(2026, 9, 23, 9)),
            completed_event(2, ist(2026, 9, 23, 10)),
        ]
        result = self.service.calculate(records, now)
        self.assertTrue(result.completed_today)
        self.assertTrue(result.grew_today)
        # Crucially, growth_days is still 1 (not 2).
        self.assertEqual(result.growth_days, 1)
