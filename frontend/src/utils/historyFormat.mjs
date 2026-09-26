export function formatHistoryTime(timestamp, timeZone = "Asia/Kolkata") {
  if (!timestamp) return "";
  return new Date(timestamp).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    ...(timeZone ? { timeZone } : {}),
  }).toLowerCase();
}

// Event instants (history/Recorded Journey timestamps) arrive as unambiguous
// UTC (e.g. "2026-09-26T08:19:00Z") and are shown in the user's timezone.
// The en-GB locale preserves the panel's established "26 Sept, 1:49 pm"
// style. Schedule/deadline wall-clock values must NOT use this: they keep
// their existing local display.
export function formatEventDateTime(timestamp, timeZone = "Asia/Kolkata") {
  if (!timestamp) return "";
  return new Date(timestamp).toLocaleString("en-GB", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    ...(timeZone ? { timeZone } : {}),
  });
}
