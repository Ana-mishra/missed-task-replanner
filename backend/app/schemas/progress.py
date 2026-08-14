from pydantic import BaseModel


class ProgressResponse(BaseModel):
    completed_tasks: int
    completed_minutes: int
    estimated_completed_minutes: int
    completion_rate: float
    current_streak_days: int
    progress_level: int
    progress_percent: float
