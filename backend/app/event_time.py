"""Unambiguous instants for append-only history event timestamps.

Storage contract (deliberately unchanged, no DDL migration):
``task_history.timestamp`` and the event-used ``completed_at`` values are
persisted as naive datetimes holding **UTC wall-clock** time. Production
(Railway) runs in UTC, so every existing row already has this shape; new
writes keep the identical byte format.

API contract (the actual fix): at the serialization boundary, a naive event
timestamp is interpreted as UTC and emitted with explicit timezone
information (``...Z``), so JavaScript parses it as the correct instant
instead of mistaking it for local wall-clock time.

Schedule fields (``scheduled_start/end``, ``old/new_start/end``,
``deadline``) are a separate user wall-clock frame and must never pass
through these helpers.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current instant as timezone-aware UTC."""
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    """Return the current UTC instant as a naive datetime for storage.

    Event-timestamp columns are naive ``TIMESTAMP``/``DATETIME`` (UTC
    wall-clock, no migration). Handing an *aware* value to such a column is
    dialect-dependent: SQLite keeps the wall-clock, but PostgreSQL converts
    to the session ``TimeZone`` (e.g. Asia/Kolkata on a local machine),
    silently shifting the stored instant. Stripping the tz here keeps the
    stored bytes identical UTC wall-clock on every backend.
    """
    return utc_now().replace(tzinfo=None)


def as_utc_aware(value: datetime | None) -> datetime | None:
    """Express an event timestamp as an aware UTC datetime.

    Naive values are legacy/ORM rows holding UTC wall-clock time, so UTC is
    attached without shifting the instant. Aware values are converted to UTC.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
