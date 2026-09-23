import test from "node:test";
import assert from "node:assert/strict";

import {
  companionMood,
  dayKeyInZone,
  recentDaysStrip,
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
