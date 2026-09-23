// Resolve which Bad Day value a planning run should use. Only an explicit
// boolean override (the Bad Day toggle) wins; anything else — including the
// React click event that button onClick handlers receive as their first
// argument — falls back to current state so manual Plan clicks keep working.
export function resolveEffectiveBadDayMode(badDayOverride, badDayMode) {
  return typeof badDayOverride === "boolean" ? badDayOverride : badDayMode;
}

// Build the POST /plan request body from the browser's clock.
// The backend stores and compares naive wall-clock schedule values that the
// browser displays as local time, so the request carries the browser's IANA
// timezone name for interpreting the aware timestamps in that same frame.
export function browserTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || undefined;
  } catch {
    return undefined;
  }
}

export function buildPlanPayload({ availableStart, availableEnd, badDayMode }) {
  const timezone = browserTimezone();
  return {
    available_start: availableStart.toISOString(),
    available_end: availableEnd.toISOString(),
    energy_level: badDayMode ? "low" : undefined,
    bad_day: badDayMode,
    ...(timezone ? { timezone } : {}),
  };
}
