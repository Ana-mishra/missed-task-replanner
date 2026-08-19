"""Small, shared helpers for interpreting append-only task history."""

from sqlalchemy.orm import Session

from app.models.task_history import TaskHistory


def recovery_state_by_task_id(
    db: Session, task_ids: list[int] | None = None
) -> tuple[set[int], set[int]]:
    """Return ``(recovered, outstanding_missed)`` task ids.

    A miss opens one recovery opportunity. An explicit ``recovered`` event
    closes it. The retired ``replanned`` event closes one opportunity only for
    legacy compatibility; later duplicate legacy rows do not create additional
    recovery cycles.
    """
    query = db.query(TaskHistory.task_id, TaskHistory.event_type)
    query = query.filter(TaskHistory.event_type.in_(("missed", "recovered", "replanned")))
    if task_ids is not None:
        query = query.filter(TaskHistory.task_id.in_(task_ids))

    outstanding: set[int] = set()
    recovered: set[int] = set()
    for task_id, event_type in query.order_by(TaskHistory.timestamp, TaskHistory.id):
        if event_type == "missed":
            outstanding.add(task_id)
        elif event_type in {"recovered", "replanned"} and task_id in outstanding:
            outstanding.remove(task_id)
            recovered.add(task_id)
    return recovered, outstanding
