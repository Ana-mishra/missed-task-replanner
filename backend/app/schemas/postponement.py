from datetime import datetime

from pydantic import BaseModel


class PostponementResponse(BaseModel):
    task_id: int
    postponement_count: int
    last_postponed_at: datetime | None
    needs_review: bool
