from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class WeeklyReflectionResponse(BaseModel):
    week_start: date
    week_end: date
    tasks_created: int
    tasks_completed: int
    tasks_missed: int
    tasks_replanned: int
    tasks_recovered: int
    tasks_scheduled: int
    tasks_scheduled_completed: int
    plan_stability: dict[str, int]
    recovery_overview_missed: int
    recovery_overview_recovered: int
    deadline_behavior: dict[str, int]
    completion_rate: float
    estimated_completed_minutes: int
    actual_completed_minutes: int
    average_estimation_difference_minutes: float | None
    postponement_cycles: int
    most_productive_day: date | None
    daily_completed_tasks: dict[str, int]
    daily_scheduled_completed_tasks: dict[str, int] = Field(default_factory=dict)
    daily_planned_minutes: dict[str, int]
    daily_estimated_minutes: dict[str, int]
    daily_actual_minutes: dict[str, int]
    progress_level: int
    progress_percent: float
    previous_tasks_completed: int | None = None
    previous_completion_rate: float | None = None
    previous_tasks_missed: int | None = None
    previous_tasks_recovered: int | None = None


Mood = Literal["tough", "okay", "neutral", "good", "great"]


class DailyReflectionInput(BaseModel):
    mood: Mood | None = None
    went_well: str = Field(default="", max_length=500)
    could_be_better: str = Field(default="", max_length=500)
    note_to_self: str = Field(default="", max_length=500)
    tomorrow_step: str = Field(default="", max_length=500)


class ReflectionStreakDay(BaseModel):
    date: date
    reflected: bool


class DailyReflectionResponse(DailyReflectionInput):
    date: date
    completed: int
    missed: int
    recovered: int
    planned_work_minutes: int
    available_minutes: int | None = None
    streak_days: int
    recent_streak_days: list[ReflectionStreakDay]
