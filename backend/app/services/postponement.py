from dataclasses import dataclass
from datetime import datetime

from app.models.task_history import TaskHistory


@dataclass(frozen=True)
class PostponementResult:
    task_id: int
    postponement_count: int
    last_postponed_at: datetime | None
    needs_review: bool


class PostponementService:
    """Analyzes missed-and-replanned cycles for one task."""

    default_review_threshold = 3

    def analyze(
        self,
        task_id: int,
        history_records: list[TaskHistory],
        review_threshold: int | None = None,
    ) -> PostponementResult:
        threshold = review_threshold or self.default_review_threshold
        if threshold <= 0:
            raise ValueError("review_threshold must be greater than zero")

        ordered_records = sorted(history_records, key=lambda record: (record.timestamp, record.id))
        unmatched_missed_event = None
        postponement_count = 0
        last_postponed_at = None

        for record in ordered_records:
            if record.event_type == "missed":
                unmatched_missed_event = record
            elif record.event_type == "replanned" and unmatched_missed_event is not None:
                postponement_count += 1
                last_postponed_at = record.timestamp
                unmatched_missed_event = None

        return PostponementResult(
            task_id=task_id,
            postponement_count=postponement_count,
            last_postponed_at=last_postponed_at,
            needs_review=postponement_count >= threshold,
        )
