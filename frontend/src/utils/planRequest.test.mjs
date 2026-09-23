import test from "node:test";
import assert from "node:assert/strict";

import { buildPlanPayload, browserTimezone } from "./planRequest.mjs";

test("payload includes the browser IANA timezone", () => {
  const payload = buildPlanPayload({
    availableStart: new Date("2040-05-06T10:52:00Z"),
    availableEnd: new Date("2040-05-06T14:52:00Z"),
    badDayMode: false,
  });
  assert.equal(payload.available_start, "2040-05-06T10:52:00.000Z");
  assert.equal(payload.available_end, "2040-05-06T14:52:00.000Z");
  assert.ok(
    typeof payload.timezone === "string" && payload.timezone.length > 0,
    "expected a non-empty IANA timezone name",
  );
  assert.equal(payload.timezone, browserTimezone());
  assert.equal(payload.bad_day, false);
});

test("bad day mode maps energy level", () => {
  const payload = buildPlanPayload({
    availableStart: new Date("2040-05-06T10:52:00Z"),
    availableEnd: new Date("2040-05-06T14:52:00Z"),
    badDayMode: true,
  });
  assert.equal(payload.energy_level, "low");
  assert.equal(payload.bad_day, true);
  assert.ok(typeof payload.timezone === "string");
});

test("payload survives a JSON round trip", () => {
  const payload = buildPlanPayload({
    availableStart: new Date("2040-05-06T10:52:00Z"),
    availableEnd: new Date("2040-05-06T14:52:00Z"),
    badDayMode: false,
  });
  const revived = JSON.parse(JSON.stringify(payload));
  assert.equal(revived.timezone, payload.timezone);
  assert.equal(revived.available_start, payload.available_start);
});
