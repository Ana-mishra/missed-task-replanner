import test from "node:test";
import assert from "node:assert/strict";

import {
  companionMood,
  dayKeyInZone,
  EYE_TRACK_BOUNDS,
  eyeTrackingOffset,
  growthTimeline,
  isNewUser,
  journeyLine,
  littleMoment,
  NEW_USER_WELCOME,
  recentDaysStrip,
  recoveredToday,
  resolveDisplayStage,
} from "./plantCompanion.mjs";

test("completed today after an absence is RETURNING", () => {
  assert.equal(
    companionMood({ completed_today: true, vitality: "healthy", showedUpYesterday: false }).id,
    "RETURNING",
  );
});

test("completed today is HAPPY without history or with momentum", () => {
  assert.equal(
    companionMood({ completed_today: true, vitality: "healthy" }).id,
    "HAPPY",
  );
  assert.equal(
    companionMood({ completed_today: true, vitality: "healthy", showedUpYesterday: true }).id,
    "HAPPY",
  );
});

test("droopy vitality without completion is NEEDS_CARE, never punitive", () => {
  assert.equal(
    companionMood({ completed_today: false, vitality: "droopy" }).id,
    "NEEDS_CARE",
  );
  assert.equal(
    companionMood({ completed_today: false, vitality: "very_droopy" }).id,
    "NEEDS_CARE",
  );
  assert.ok(
    companionMood({ completed_today: false, vitality: "droopy" }).message.length > 0,
  );
});

test("waiting vitality without completion is GROWING", () => {
  assert.equal(
    companionMood({ completed_today: false, vitality: "waiting" }).id,
    "GROWING",
  );
  assert.equal(
    companionMood({ completed_today: false, vitality: "healthy" }).id,
    "GROWING",
  );
});

test("IST day keys match backend growth-day bucketing", () => {
  // 2026-09-22T19:00:00Z is 2026-09-23 00:30 IST.
  assert.equal(dayKeyInZone("2026-09-22T19:00:00Z"), "2026-09-23");
  assert.equal(dayKeyInZone("2026-09-22T18:00:00Z"), "2026-09-22");
});

test("strip covers 7 IST days ending today from real completed events", () => {
  const now = new Date("2026-09-23T10:00:00Z"); // 15:30 IST
  const events = [
    { event_type: "completed", timestamp: "2026-09-23T05:00:00Z" },
    { event_type: "completed", timestamp: "2026-09-21T10:00:00Z" },
    { event_type: "missed", timestamp: "2026-09-22T10:00:00Z" },
    { event_type: "completed", timestamp: "2026-09-24T10:00:00Z" },
  ];
  const strip = recentDaysStrip(events, now);
  assert.equal(strip.length, 7);
  assert.equal(strip[6].label, "Today");
  assert.ok(strip[6].isToday && strip[6].showedUp);
  const byKey = new Map(strip.map((day) => [day.key, day]));
  assert.ok(byKey.get("2026-09-21").showedUp);
  assert.ok(!byKey.get("2026-09-22").showedUp);
  assert.ok(!strip.some((day) => day.key === "2026-09-24"));
});

test("strip handles missing history without inventing days", () => {
  const strip = recentDaysStrip(null, new Date("2026-09-23T10:00:00Z"));
  assert.equal(strip.length, 7);
  assert.ok(strip.every((day) => !day.showedUp));
});

test("journey line describes togetherness without streak language", () => {
  const lit = (n) =>
    Array.from({ length: 7 }, (_, i) => ({ showedUp: i < n }));
  assert.equal(journeyLine(lit(6)), "You've been showing up this week.");
  assert.equal(journeyLine(lit(3)), "A few good days together.");
  assert.equal(journeyLine(lit(1)), "You're finding your rhythm.");
  assert.equal(journeyLine(lit(0)), "Every day is a fresh start.");
  for (const text of [journeyLine(lit(6)), journeyLine(lit(0))]) {
    assert.ok(!/streak/i.test(text));
  }
});

test("recoveredToday detects real recovery events on today's IST date", () => {
  const now = new Date("2026-09-23T10:00:00Z");
  assert.ok(
    recoveredToday(
      [{ event_type: "recovered", timestamp: "2026-09-23T05:00:00Z" }],
      now,
    ),
  );
  assert.ok(
    !recoveredToday(
      [{ event_type: "recovered", timestamp: "2026-09-22T05:00:00Z" }],
      now,
    ),
  );
  assert.ok(
    !recoveredToday(
      [{ event_type: "completed", timestamp: "2026-09-23T05:00:00Z" }],
      now,
    ),
  );
  assert.ok(!recoveredToday(null, now));
});

test("little moment prioritizes return, care, recovery, quiet", () => {
  assert.equal(
    littleMoment({ completed_today: true, showedUpYesterday: false }),
    "You came back today. Your plant is happy to see you.",
  );
  assert.equal(
    littleMoment({ completed_today: true, showedUpYesterday: true }),
    "You took care of things today.",
  );
  assert.equal(
    littleMoment({ completed_today: false, didRecoverToday: true }),
    "You made some progress today.",
  );
  assert.equal(
    littleMoment({ completed_today: false }),
    "A slower day is okay. I'm still here.",
  );
});

test("growth timeline maps backend stages without numbers", () => {
  const sprout = growthTimeline("sprout", false);
  assert.deepEqual(
    sprout.map((node) => node.state),
    ["done", "current", "todo", "current"],
  );
  const mature = growthTimeline("mature", true);
  assert.ok(mature.slice(0, 3).every((node) => node.state === "done"));
  assert.equal(mature[3].state, "done");
  const unknown = growthTimeline("nope", false);
  assert.equal(unknown[0].state, "current");
  for (const node of mature) {
    assert.ok(!/[0-9%]/.test(node.label));
  }
});

test("eye tracking stays neutral at the face center", () => {
  assert.deepEqual(eyeTrackingOffset(100, 100, 100, 100), { dx: 0, dy: 0 });
});

test("eye tracking follows the cursor direction within bounds", () => {
  const right = eyeTrackingOffset(220, 100, 100, 100);
  assert.ok(right.dx > 0 && right.dx <= EYE_TRACK_BOUNDS.x);
  assert.equal(right.dy, 0);
  const upLeft = eyeTrackingOffset(40, 40, 100, 100);
  assert.ok(upLeft.dx < 0 && upLeft.dy < 0);
});

test("brand-new user with no history is new, never slow-day", () => {
  assert.equal(
    isNewUser({ historyEvents: [], growthDays: 0, completedToday: false }),
    true,
  );
  assert.ok(NEW_USER_WELCOME.length > 0);
  assert.ok(!/slower day/i.test(NEW_USER_WELCOME));
});

test("unknown (loading) history is never treated as new", () => {
  assert.equal(
    isNewUser({ historyEvents: null, growthDays: 0, completedToday: false }),
    false,
  );
  assert.equal(
    isNewUser({ historyEvents: undefined, growthDays: 0, completedToday: false }),
    false,
  );
});

test("tasks but zero completions is still a new user", () => {
  assert.equal(
    isNewUser({
      historyEvents: [
        { event_type: "created", timestamp: "2026-09-20T10:00:00Z" },
        { event_type: "scheduled", timestamp: "2026-09-20T11:00:00Z" },
        { event_type: "missed", timestamp: "2026-09-21T10:00:00Z" },
      ],
      growthDays: 0,
      completedToday: false,
    }),
    true,
  );
});

test("any completion keeps existing users out of the new-user state", () => {
  const completed = [{ event_type: "completed", timestamp: "2026-09-20T10:00:00Z" }];
  assert.equal(
    isNewUser({ historyEvents: completed, growthDays: 0, completedToday: false }),
    false,
  );
  assert.equal(
    isNewUser({
      historyEvents: [
        { event_type: "created", timestamp: "2026-09-20T10:00:00Z" },
        { event_type: "completed", timestamp: "2026-09-21T10:00:00Z" },
      ],
      growthDays: 0,
      completedToday: false,
    }),
    false,
  );
  assert.equal(
    isNewUser({ historyEvents: [], growthDays: 3, completedToday: false }),
    false,
  );
  assert.equal(
    isNewUser({ historyEvents: [], growthDays: 0, completedToday: true }),
    false,
  );
});

test("slow-day copy is never the new-user welcome", () => {
  // The quiet fallback belongs to established slow/recovery days only.
  assert.ok(!/slower day/i.test(NEW_USER_WELCOME));
  assert.ok(/grow together/i.test(NEW_USER_WELCOME));
});

test("new users persist on seed; sprout shows only mid-intro", () => {
  assert.equal(
    resolveDisplayStage({ isNewUser: true, introSprouting: false, backendStage: "seed" }),
    "seed",
  );
  assert.equal(
    resolveDisplayStage({ isNewUser: true, introSprouting: true, backendStage: "seed" }),
    "sprout",
  );
  assert.equal(
    resolveDisplayStage({ isNewUser: false, introSprouting: true, backendStage: "growing" }),
    "growing",
  );
  assert.equal(
    resolveDisplayStage({ isNewUser: false, introSprouting: false, backendStage: "mature" }),
    "mature",
  );
});

test("zero completions light no days, including Today", () => {
  const strip = recentDaysStrip([], new Date("2026-09-25T10:00:00Z"));
  assert.ok(strip.length > 0);
  assert.ok(strip.every((day) => day.showedUp === false));
  assert.equal(strip.find((day) => day.isToday).showedUp, false);
});

test("a previous-day completion does not light Today", () => {
  const strip = recentDaysStrip(
    [{ event_type: "completed", timestamp: "2026-09-23T10:00:00Z" }],
    new Date("2026-09-25T10:00:00Z"),
  );
  const today = strip.find((day) => day.isToday);
  const lit = strip.filter((day) => day.showedUp);
  assert.equal(today.showedUp, false);
  assert.equal(lit.length, 1);
  assert.equal(
    isNewUser({
      historyEvents: [{ event_type: "completed", timestamp: "2026-09-23T10:00:00Z" }],
      growthDays: 1,
      completedToday: false,
    }),
    false,
  );
});

test("today completed lights Today and exits the new-user state", () => {
  const strip = recentDaysStrip(
    [{ event_type: "completed", timestamp: "2026-09-25T08:00:00Z" }],
    new Date("2026-09-25T10:00:00Z"),
  );
  assert.equal(strip.find((day) => day.isToday).showedUp, true);
  assert.equal(
    isNewUser({
      historyEvents: [{ event_type: "completed", timestamp: "2026-09-25T08:00:00Z" }],
      growthDays: 0,
      completedToday: false,
    }),
    false,
  );
});

test("eye tracking clamps far cursors to the bounds", () => {
  assert.deepEqual(eyeTrackingOffset(10000, 100, 100, 100), {
    dx: EYE_TRACK_BOUNDS.x,
    dy: 0,
  });
  assert.deepEqual(eyeTrackingOffset(100, -10000, 100, 100), {
    dx: 0,
    dy: -EYE_TRACK_BOUNDS.y,
  });
});
