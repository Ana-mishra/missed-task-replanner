"""Plant growth service — My Plant feature.

Growth Days are the count of distinct IST calendar dates on which the user
completed at least one task.  They are derived entirely from TaskHistory
records with event_type == "completed"; no separate Plant table is needed.

GROWTH is permanent and never decreases.
VITALITY is temporary and reflects recency of care.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from app.models.task_history import TaskHistory
from app.services.browser_reminders import planora_now, REMINDER_TIMEZONE

# ---------------------------------------------------------------------------
# Stage configuration — centralised so thresholds can be adjusted without
# touching any other part of the system.
# ---------------------------------------------------------------------------

PlantStage = Literal["seed", "sprout", "young_plant", "growing", "flourishing", "mature"]
PlantVitality = Literal["healthy", "waiting", "droopy", "very_droopy"]

# List of (min_growth_days_inclusive, stage_name, next_stage_threshold).
# The last entry has next_threshold=None (terminal stage).
_STAGE_CONFIG: list[tuple[int, PlantStage, int | None]] = [
    (0,  "seed",         1),
    (1,  "sprout",       3),
    (3,  "young_plant",  7),
    (7,  "growing",      14),
    (14, "flourishing",  30),
    (30, "mature",       None),
]


def _stage_for(growth_days: int) -> tuple[PlantStage, float]:
    """Return (stage_name, stage_progress_0_to_100).

    stage_progress represents progress toward the NEXT stage threshold.
    For 'mature' (terminal), progress is fixed at 100.
    """
    selected_stage: PlantStage = "seed"
    selected_threshold_low = 0
    selected_threshold_high: int | None = 1

    for low, name, high in _STAGE_CONFIG:
        if growth_days >= low:
            selected_stage = name
            selected_threshold_low = low
            selected_threshold_high = high

    if selected_threshold_high is None:
        # Terminal stage — always 100 %.
        return selected_stage, 100.0

    span = selected_threshold_high - selected_threshold_low
    progress_within = growth_days - selected_threshold_low
    stage_progress = (progress_within / span) * 100.0
    return selected_stage, round(stage_progress, 2)


def _vitality_for(days_since_last_growth: int, completed_today: bool) -> PlantVitality:
    """Derive vitality from recency only — no stored state needed.

    completed_today=True always means healthy regardless of the gap,
    because the user just acted.  The scale is intentionally gentle:
    the plant communicates "Your plant is waiting", not "you failed".

    States are neutral internal identifiers; user-facing copy is the
    frontend's responsibility.
    """
    if completed_today:
        return "healthy"
    if days_since_last_growth <= 1:
        return "waiting"
    if days_since_last_growth <= 4:
        return "droopy"
    return "very_droopy"


@dataclass(frozen=True)
class PlantResult:
    growth_days: int
    stage: PlantStage
    stage_progress: float
    current_streak_days: int
    days_since_last_growth: int
    completed_today: bool
    grew_today: bool
    vitality: PlantVitality


class PlantService:
    """Read-only plant analytics derived from task completion history.

    All Growth Day calculations use IST (Asia/Kolkata) calendar dates so
    that midnight IST is the day boundary, consistent with the rest of
    Planora's reminder and planning logic.

    The service accepts an optional `now` parameter (an IST-aware datetime)
    so that tests can pin the clock without patching globals.
    """

    def calculate(
        self,
        history_records: list[TaskHistory],
        now: datetime | None = None,
    ) -> PlantResult:
        """Compute the full plant state from raw history records.

        Parameters
        ----------
        history_records:
            All TaskHistory rows for the user where event_type == "completed".
            The caller is responsible for pre-filtering to completed events.
        now:
            The current moment in IST (aware datetime).  If None, the real
            current time is used.
        """
        ist_now = planora_now(now)
        today_ist: date = ist_now.date()

        # Build the set of unique IST calendar dates on which a genuine
        # task completion occurred.  This is different from ProgressService
        # which uses naive server-local timestamps.
        growth_dates: set[date] = {
            planora_now(record.timestamp).date()
            for record in history_records
            if record.event_type == "completed"
            and planora_now(record.timestamp) <= ist_now
        }

        growth_days: int = len(growth_dates)

        # --- completed_today / grew_today -----------------------------------
        # These are intentionally separate concepts even though they currently
        # resolve to the same boolean.  Keep the derivations independent so
        # future logic (e.g. a grace-period or a persisted first-completion
        # event) can diverge them without touching the other field.
        #
        # completed_today: at least one genuine task completion has occurred
        #   on today's IST calendar date, observed at or before `now`.
        completed_today: bool = today_ist in growth_dates
        #
        # grew_today: today's Growth Day has been established — i.e. today is
        #   already counted as one of the user's accumulated Growth Days.
        #   Derived from growth_dates independently of completed_today.
        grew_today: bool = today_ist in growth_dates

        # --- days_since_last_growth ----------------------------------------
        if not growth_dates:
            # No completions ever — treat as a very long absence (> 5 days)
            # so vitality shows "neglected" appropriately, but the exact
            # number is capped to avoid overflow in display.
            days_since_last_growth = 999
        else:
            last_growth = max(growth_dates)
            days_since_last_growth = (today_ist - last_growth).days
            # If completed today, days_since_last_growth is 0.

        # --- current_streak_days -------------------------------------------
        # Walk backward from today.  An incomplete current day does NOT break
        # the streak — we check yesterday first if today has no growth.
        # This mirrors the ProgressService logic but operates on IST dates.
        current_streak_days = 0
        streak_date = today_ist
        if streak_date not in growth_dates:
            streak_date -= timedelta(days=1)
        while streak_date in growth_dates:
            current_streak_days += 1
            streak_date -= timedelta(days=1)

        # --- stage & stage_progress ----------------------------------------
        stage, stage_progress = _stage_for(growth_days)

        # --- vitality -------------------------------------------------------
        vitality = _vitality_for(days_since_last_growth, completed_today)

        return PlantResult(
            growth_days=growth_days,
            stage=stage,
            stage_progress=stage_progress,
            current_streak_days=current_streak_days,
            days_since_last_growth=days_since_last_growth,
            completed_today=completed_today,
            grew_today=grew_today,
            vitality=vitality,
        )
