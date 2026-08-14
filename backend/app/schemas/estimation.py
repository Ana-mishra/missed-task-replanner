from typing import Literal

from pydantic import BaseModel


class EstimationResponse(BaseModel):
    completed_tasks: int
    estimated_minutes: int
    actual_minutes: int
    total_difference_minutes: int
    average_difference_minutes: float
    average_accuracy_percent: float
    tendency: Literal["underestimate", "overestimate", "accurate", "insufficient_data"]
