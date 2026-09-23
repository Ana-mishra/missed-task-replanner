// Phase 1 companion state model for the My Plant page.
//
// Pure helpers only — no React, no fetching — so Phase 2 animation and the
// existing visuals can build on top without touching this logic.
//
// All day bucketing uses Asia/Kolkata calendar dates, mirroring the backend
// PlantService (Growth Days are distinct IST dates with a genuine task
// completion). Nothing here invents data: moods derive from /plant fields
// and the recent-days strip derives from real /task-history completed
// events.

export const IST_TIME_ZONE = "Asia/Kolkata";

export const COMPANION_MOODS = {
  HAPPY: {
    id: "HAPPY",
    message: "You showed up today. That's enough. 💚",
  },
  GROWING: {
    id: "GROWING",
    message: "You're making progress. Keep going.",
  },
  NEEDS_CARE: {
    id: "NEEDS_CARE",
    message: "Looks like today was a little heavy. That's okay.",
  },
  RETURNING: {
    id: "RETURNING",
    message: "You're back. Let's start small. 🌱",
  },
};

// Derive the companion mood from already-available /plant fields plus
// whether yesterday (IST) was a growth day. A missed day never destroys
// anything here — it only selects a gentler message.
export function companionMood({ completed_today, vitality, showedUpYesterday }) {
  if (completed_today) {
    // showedUpYesterday === undefined means the caller has no day-level
    // history; fall back to HAPPY rather than guessing.
    if (showedUpYesterday === false) return COMPANION_MOODS.RETURNING;
    return COMPANION_MOODS.HAPPY;
  }
  if (vitality === "droopy" || vitality === "very_droopy") {
    return COMPANION_MOODS.NEEDS_CARE;
  }
  return COMPANION_MOODS.GROWING;
}

// "YYYY-MM-DD" key of an instant in the given IANA timezone.
export function dayKeyInZone(value, timeZone = IST_TIME_ZONE) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(value));
  const get = (type) => parts.find((part) => part.type === type).value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function addDaysKey(key, offset) {
  const [y, m, d] = key.split("-").map(Number);
  const date = new Date(Date.UTC(y, m - 1, d));
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toISOString().slice(0, 10);
}

function weekdayLabel(key, timeZone = IST_TIME_ZONE) {
  return new Intl.DateTimeFormat("en-US", { timeZone, weekday: "short" }).format(
    new Date(`${key}T12:00:00Z`),
  );
}

// Build a 7-day strip ending today (IST) from real completed history events.
// Each event needs a `timestamp` parseable by Date; only event_type ===
// "completed" entries count, and future-dated entries are ignored, exactly
// like the backend Growth Day derivation.
export function recentDaysStrip(historyEvents, now = new Date(), count = 7) {
  const todayKey = dayKeyInZone(now);
  const growthKeys = new Set();
  for (const event of historyEvents ?? []) {
    if (event?.event_type !== "completed" || !event?.timestamp) continue;
    const key = dayKeyInZone(event.timestamp);
    if (key <= todayKey) growthKeys.add(key);
  }
  const days = [];
  for (let offset = -(count - 1); offset <= 0; offset += 1) {
    const key = addDaysKey(todayKey, offset);
    const isToday = offset === 0;
    days.push({
      key,
      label: isToday ? "Today" : weekdayLabel(key),
      showedUp: growthKeys.has(key),
      isToday,
    });
  }
  return days;
}
