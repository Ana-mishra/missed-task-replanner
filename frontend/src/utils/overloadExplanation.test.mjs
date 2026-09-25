import test from "node:test";
import assert from "node:assert/strict";

import {
  getCapacityUnscheduledTasks,
  getOverloadExplanation,
  isZeroScheduledOverload,
} from "./overloadExplanation.mjs";

// Case 1: 39 available + one 45-minute task → 6-minute shortfall.
test("one task slightly over capacity reports a 6-minute shortfall", () => {
  const explanation = getOverloadExplanation({
    availableMinutes: 39,
    plannedMinutes: 0,
    unscheduledMinutes: 45,
    isOverloaded: true,
  });
  assert.equal(explanation.totalDemandMinutes, 45);
  assert.equal(explanation.shortfallMinutes, 6);
  assert.equal(explanation.remainingCapacityMinutes, 39);
  assert.equal(explanation.showOverload, true);
});

// Case 2: 39 available + two 45-minute tasks → 90 needed, 51 over.
test("two tasks over capacity report 90 needed and 51 over", () => {
  const explanation = getOverloadExplanation({
    availableMinutes: 39,
    plannedMinutes: 0,
    unscheduledMinutes: 90,
    isOverloaded: true,
  });
  assert.equal(explanation.totalDemandMinutes, 90);
  assert.equal(explanation.shortfallMinutes, 51);
  assert.equal(explanation.showOverload, true);
});

// Case 3: 120 available + two 45-minute tasks → no overload.
test("enough capacity shows no overload", () => {
  const explanation = getOverloadExplanation({
    availableMinutes: 120,
    plannedMinutes: 90,
    unscheduledMinutes: 0,
    isOverloaded: false,
  });
  assert.equal(explanation.totalDemandMinutes, 90);
  assert.equal(explanation.shortfallMinutes, 0);
  assert.equal(explanation.showOverload, false);
});

// Case 4: 60 available + two 45-minute tasks → one fits, 15 remaining.
test("partial fit reports remaining capacity for the leftover task", () => {
  const explanation = getOverloadExplanation({
    availableMinutes: 60,
    plannedMinutes: 45,
    unscheduledMinutes: 45,
    isOverloaded: true,
  });
  assert.equal(explanation.totalDemandMinutes, 90);
  assert.equal(explanation.shortfallMinutes, 30);
  assert.equal(explanation.remainingCapacityMinutes, 15);
  assert.equal(explanation.showOverload, true);
});

// Case 5: Bad Day mode uses the same derivation on the mode's own numbers;
// the UI keeps the existing Bad Day strip, so the helper must stay neutral.
test("bad-day planner numbers derive without special-casing", () => {
  const explanation = getOverloadExplanation({
    availableMinutes: 36,
    plannedMinutes: 0,
    unscheduledMinutes: 90,
    isOverloaded: true,
  });
  assert.equal(explanation.totalDemandMinutes, 90);
  assert.equal(explanation.shortfallMinutes, 54);
  assert.equal(explanation.showOverload, true);
});

// Case 6: no tasks → no overload explanation.
test("no tasks shows no overload", () => {
  const explanation = getOverloadExplanation({
    availableMinutes: 39,
    plannedMinutes: 0,
    unscheduledMinutes: 0,
    isOverloaded: false,
  });
  assert.equal(explanation.showOverload, false);
  assert.equal(explanation.shortfallMinutes, 0);
});

// Case 7: only capacity-skipped tasks are listed — completed and
// zero-duration tasks are never attributed to capacity.
test("capacity list excludes completed and zero-duration tasks", () => {
  const tasks = [
    { id: 1, title: "French", duration_minutes: 45, scheduled_start: null, scheduled_end: null },
    { id: 2, title: "Done", completed: true, duration_minutes: 45, scheduled_start: null, scheduled_end: null },
    { id: 3, title: "Zero", duration_minutes: 0, scheduled_start: null, scheduled_end: null },
    { id: 4, title: "Planned", duration_minutes: 30, scheduled_start: "2026-01-01T09:00", scheduled_end: "2026-01-01T09:30" },
  ];
  const unfit = getCapacityUnscheduledTasks(tasks);
  assert.deepEqual(unfit.map((task) => task.title), ["French"]);
});

// Zero-scheduled overload presentation gate: reshaped-note suppression and
// the calm Today's-plan card apply only to this exact state.
test("zero scheduled + overloaded identifies the calm-empty state", () => {
  assert.equal(
    isZeroScheduledOverload({ hasPlanned: true, planIsOverloaded: true, scheduledCount: 0 }),
    true,
  );
});

test("partially scheduled + overloaded keeps existing behavior", () => {
  assert.equal(
    isZeroScheduledOverload({ hasPlanned: true, planIsOverloaded: true, scheduledCount: 2 }),
    false,
  );
});

test("normal scheduled plan is untouched", () => {
  assert.equal(
    isZeroScheduledOverload({ hasPlanned: true, planIsOverloaded: false, scheduledCount: 2 }),
    false,
  );
});

test("not-yet-planned state is untouched", () => {
  assert.equal(
    isZeroScheduledOverload({ hasPlanned: false, planIsOverloaded: false, scheduledCount: 0 }),
    false,
  );
});

test("no-task state is untouched", () => {
  assert.equal(
    isZeroScheduledOverload({ hasPlanned: false, planIsOverloaded: false, scheduledCount: 0 }),
    false,
  );
  assert.equal(
    isZeroScheduledOverload({ hasPlanned: true, planIsOverloaded: false, scheduledCount: 0 }),
    false,
  );
});

test("backend overload verdict is required — unscheduled minutes alone do not show it", () => {
  const explanation = getOverloadExplanation({
    availableMinutes: 39,
    plannedMinutes: 0,
    unscheduledMinutes: 0,
    isOverloaded: false,
  });
  assert.equal(explanation.showOverload, false);
});
