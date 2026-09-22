from pydantic import BaseModel
from typing import Literal


PlantStage = Literal["seed", "sprout", "young_plant", "growing", "flourishing", "mature"]

PlantVitality = Literal["healthy", "waiting", "droopy", "very_droopy"]


class PlantResponse(BaseModel):
    growth_days: int
    stage: PlantStage
    stage_progress: float
    current_streak_days: int
    days_since_last_growth: int
    completed_today: bool
    grew_today: bool
    vitality: PlantVitality
