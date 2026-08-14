from datetime import date

from pydantic import BaseModel


class WeeklyReflectionResponse(BaseModel):
    week_start: date
    week_end: date
    tasks_created: int
    tasks_completed: int
    tasks_missed: int
    tasks_replanned: int
    completion_rate: float
    estimated_completed_minutes: int
    actual_completed_minutes: int
    average_estimation_difference_minutes: float | None
    postponement_cycles: int
    most_productive_day: date | None
    daily_completed_tasks: dict[str, int]
    progress_level: int
    progress_percent: float
