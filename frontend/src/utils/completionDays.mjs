// Per-day scheduled-completion details for the Completion Trend tooltip.
//
// Mirrors the backend ReflectionService.calculate cohort rule (read-only,
// no backend changes): within the selected period, each task's earliest
// "scheduled" event is its anchor; only the first "completed" event at or
// after that anchor counts, bucketed by completion date ("year"/"all"
// collapse to month buckets, exactly like backend bucket_for).
//
// Anything else (unscheduled completions, completions before the anchor,
// out-of-period events, later duplicate completions) is excluded so the
// tooltip can never disagree with the bar counts.

function toISODate(value) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function startOfDay(value) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

export function periodWindow(period, now = new Date()) {
  const endExclusive = startOfDay(now);
  endExclusive.setDate(endExclusive.getDate() + 1);
  if (period === "week") {
    const mondayOffset = (now.getDay() + 6) % 7;
    const start = startOfDay(now);
    start.setDate(start.getDate() - mondayOffset);
    const end = new Date(start);
    end.setDate(end.getDate() + 7);
    return { start, endExclusive: end };
  }
  if (period === "month") {
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 1);
    return { start, endExclusive: end };
  }
  if (period === "year") {
    const start = new Date(now.getFullYear(), 0, 1);
    const end = new Date(now.getFullYear() + 1, 0, 1);
    return { start, endExclusive: end };
  }
  return { start: null, endExclusive };
}

function bucketKey(period, value) {
  if (period === "year" || period === "all") {
    return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-01`;
  }
  return toISODate(value);
}

// Monday grouping identical to StatsPage chartEntries (month display).
export function mondayGroupKey(dateStr) {
  const current = new Date(`${dateStr}T00:00:00`);
  const mondayOffset = (current.getDay() + 6) % 7;
  current.setDate(current.getDate() - mondayOffset);
  return current.toISOString().slice(0, 10);
}

function compareStamp(a, b) {
  if (a.timestampMs !== b.timestampMs) return a.timestampMs - b.timestampMs;
  return a.id - b.id;
}

export function scheduledCompletionsByDay(records, period, now = new Date()) {
  const details = new Map();
  if (!Array.isArray(records) || records.length === 0) return details;
  const { start, endExclusive } = periodWindow(period, now);
  const nowMs = now.getTime();

  const inWindow = (timestampMs) =>
    timestampMs <= nowMs &&
    (start === null || timestampMs >= start.getTime()) &&
    timestampMs < endExclusive.getTime();

  const anchors = new Map();
  for (const record of records) {
    if (record?.event_type !== "scheduled") continue;
    const timestampMs = new Date(record.timestamp).getTime();
    if (Number.isNaN(timestampMs) || !inWindow(timestampMs)) continue;
    const candidate = { timestampMs, id: Number(record.id) || 0 };
    const current = anchors.get(record.task_id);
    if (!current || compareStamp(candidate, current) < 0) {
      anchors.set(record.task_id, candidate);
    }
  }

  const firstCompletions = new Map();
  for (const record of records) {
    if (record?.event_type !== "completed") continue;
    const anchor = anchors.get(record.task_id);
    if (!anchor) continue;
    const timestampMs = new Date(record.timestamp).getTime();
    if (Number.isNaN(timestampMs) || !inWindow(timestampMs)) continue;
    const candidate = {
      timestampMs,
      id: Number(record.id) || 0,
      taskId: record.task_id,
      title: record.task_title ?? "Deleted task",
    };
    if (compareStamp(candidate, anchor) < 0) continue;
    const current = firstCompletions.get(record.task_id);
    if (!current || compareStamp(candidate, current) < 0) {
      firstCompletions.set(record.task_id, candidate);
    }
  }

  for (const completion of firstCompletions.values()) {
    const key = bucketKey(period, new Date(completion.timestampMs));
    if (!details.has(key)) details.set(key, []);
    details.get(key).push(completion);
  }
  for (const items of details.values()) {
    items.sort(compareStamp);
  }
  return details;
}

// Aggregate per-date details onto the displayed chart keys (month display
// groups days into Monday weeks, exactly like chartEntries).
export function trendDetailsByDisplayKey(records, period, now = new Date()) {
  const byDate = scheduledCompletionsByDay(records, period, now);
  if (period !== "month") return byDate;
  const grouped = new Map();
  for (const [dateStr, items] of byDate) {
    const key = mondayGroupKey(dateStr);
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(...items);
  }
  for (const items of grouped.values()) {
    items.sort(compareStamp);
  }
  return grouped;
}

export function formatCompletionTime(timestampMs) {
  return new Date(timestampMs).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}
