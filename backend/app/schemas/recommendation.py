from pydantic import BaseModel

from app.schemas.task import TaskResponse


class RecommendationResponse(BaseModel):
    recommended_task: TaskResponse | None
    reason: str
