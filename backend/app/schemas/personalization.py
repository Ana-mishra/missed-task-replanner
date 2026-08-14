from typing import Literal

from pydantic import BaseModel


class PersonalizationInsightResponse(BaseModel):
    type: Literal["estimation", "postponement", "duration_pattern", "energy_pattern"]
    message: str
    evidence_count: int
    confidence: Literal["low", "medium", "high"]


class PersonalizationResponse(BaseModel):
    insights: list[PersonalizationInsightResponse]
