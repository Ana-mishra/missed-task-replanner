import test from "node:test";
import assert from "node:assert/strict";

import { isCurrentlyRecovered } from "./taskRecovery.mjs";

test("missed + unscheduled with a historical recovery is NOT recovered", () => {
  assert.equal(
    isCurrentlyRecovered({
      status: "missed",
      completed: false,
      was_replanned: true,
      scheduled_start: null,
      scheduled_end: null,
    }),
    false,
  );
});

test("recovered task holding its new slot IS recovered", () => {
  assert.equal(
    isCurrentlyRecovered({
      status: "pending",
      completed: false,
      was_replanned: true,
      scheduled_start: "2040-01-02T09:00:00",
      scheduled_end: "2040-01-02T09:30:00",
    }),
    true,
  );
});

test("historical recovery without a current slot is NOT recovered", () => {
  assert.equal(
    isCurrentlyRecovered({
      status: "pending",
      completed: false,
      was_replanned: true,
      scheduled_start: null,
      scheduled_end: null,
    }),
    false,
  );
});

test("normal scheduled task without recovery history is NOT recovered", () => {
  assert.equal(
    isCurrentlyRecovered({
      status: "pending",
      completed: false,
      was_replanned: false,
      scheduled_start: "2040-01-02T09:00:00",
      scheduled_end: "2040-01-02T09:30:00",
    }),
    false,
  );
});

test("completed previously-recovered task is NOT actively recovered", () => {
  assert.equal(
    isCurrentlyRecovered({
      status: "completed",
      completed: true,
      was_replanned: true,
      scheduled_start: "2040-01-02T09:00:00",
      scheduled_end: "2040-01-02T09:30:00",
    }),
    false,
  );
});

test("missed task is NOT recovered even if a stale slot lingered", () => {
  assert.equal(
    isCurrentlyRecovered({
      status: "missed",
      completed: false,
      was_replanned: true,
      scheduled_start: "2040-01-02T09:00:00",
      scheduled_end: "2040-01-02T09:30:00",
    }),
    false,
  );
});
