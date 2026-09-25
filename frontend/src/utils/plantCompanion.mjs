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

// One contextual line for the recent-days journey. Counts lit days only;
// never streak language, never a score.
export function journeyLine(strip) {
  const lit = (strip ?? []).filter((day) => day.showedUp).length;
  if (lit >= 5) return "You've been showing up this week.";
  if (lit >= 3) return "A few good days together.";
  if (lit >= 1) return "You're finding your rhythm.";
  return "Every day is a fresh start.";
}

// Was there a genuine recovery (missed task brought back into the plan)
// on today's IST date? Derived from real history events only.
export function recoveredToday(historyEvents, now = new Date()) {
  const todayKey = dayKeyInZone(now);
  return (historyEvents ?? []).some(
    (event) =>
      event?.event_type === "recovered" &&
      event?.timestamp &&
      dayKeyInZone(event.timestamp) === todayKey,
  );
}

// First-time greeting for genuinely new users. Shown through the same
// speech-bubble system as every other companion message.
export const NEW_USER_WELCOME = "Hi! Let's grow together. 🌱";

// Is this a brand-new user who has never completed a single task? The test
// is completion-based, not event-based: a user with tasks but zero
// completions is still new. "No completions" must never be treated as a
// slow day, missed day, or recovery day — those states require actual
// completion history to be established. Unknown history (still loading)
// is never "new" so the intro can't flash incorrectly.
export function countCompletions(historyEvents) {
  return (historyEvents ?? []).filter(
    (event) => event?.event_type === "completed",
  ).length;
}

export function isNewUser({ historyEvents, growthDays = 0, completedToday = false } = {}) {
  if (historyEvents == null) return false;
  if (completedToday) return false;
  if (Number(growthDays) > 0) return false;
  return countCompletions(historyEvents) === 0;
}

// Which backend stage should the visual render? New users persistently see
// the seed — growth must come from completion history, never from page
// visits or the intro. The intro may transiently show the sprout while its
// grow-in plays (introSprouting), then the visual settles back to seed.
// Everyone else always sees the real backend stage.
export function resolveDisplayStage({ isNewUser, introSprouting, backendStage }) {
  if (!isNewUser) return backendStage;
  return introSprouting ? "sprout" : "seed";
}

// A small deterministic note from the companion. Priority: returning after
// a missed day, then today's care, then recovery progress, then quiet.
export function littleMoment({
  completed_today,
  showedUpYesterday,
  didRecoverToday,
}) {
  if (completed_today && showedUpYesterday === false) {
    return "You came back today. Your plant is happy to see you.";
  }
  if (completed_today) {
    return "You took care of things today.";
  }
  if (didRecoverToday) {
    return "You made some progress today.";
  }
  return "A slower day is okay. I'm still here.";
}

// Cursor eye-tracking offset for the open-eye moods (HAPPY, GROWING, RETURNING).
// Returns a bounded {dx, dy} translation (px, SVG units) pointing
// from the face center toward the cursor. NEEDS_CARE keeps sleepy expression.
export const EYE_TRACK_BOUNDS = { x: 4.5, y: 3.5 };
const EYE_TRACK_RANGE_PX = 150;

export function eyeTrackingOffset(cursorX, cursorY, centerX, centerY) {
  const clamp = (value, bound) =>
    Math.max(-bound, Math.min(bound, value));
  return {
    dx: clamp(((cursorX - centerX) / EYE_TRACK_RANGE_PX) * EYE_TRACK_BOUNDS.x, EYE_TRACK_BOUNDS.x),
    dy: clamp(((cursorY - centerY) / EYE_TRACK_RANGE_PX) * EYE_TRACK_BOUNDS.y, EYE_TRACK_BOUNDS.y),
  };
}

// Visual growth timeline: seed → sprout → growing → today. Backend stages
// map onto the first three nodes by order; "today" simply marks where the
// user is (lit when today was a growth day). No numbers, no percentages.
const STAGE_ORDER = {
  seed: 0,
  sprout: 1,
  young_plant: 2,
  growing: 3,
  flourishing: 4,
  mature: 5,
};

export function growthTimeline(stage, completedToday) {
  const index = STAGE_ORDER[stage] ?? 0;
  const reached = (threshold) => {
    if (index > threshold) return "done";
    if (index === threshold) return "current";
    return "todo";
  };
  return [
    { id: "seed", label: "seed", state: reached(0) },
    { id: "sprout", label: "sprout", state: reached(1) },
    { id: "growing", label: "growing", state: reached(2) },
    {
      id: "today",
      label: "today",
      state: completedToday ? "done" : "current",
    },
  ];
}
