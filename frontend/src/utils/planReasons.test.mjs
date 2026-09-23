import test from "node:test";
import assert from "node:assert/strict";

import { mergeScheduleReasons } from "./planReasons.mjs";

test("merges reasons onto matching tasks by task_id", () => {
  const tasks = [
    { id: 1, title: "One" },
    { id: 2, title: "Two" },
  ];
  const schedule = [
    { task_id: 2, reason: "Kept because the deadline is today." },
    { task_id: 1, reason: "Scheduled by deadline and priority." },
  ];
  const merged = mergeScheduleReasons(tasks, schedule);
  assert.equal(merged.find((t) => t.id === 1).reason, "Scheduled by deadline and priority.");
  assert.equal(merged.find((t) => t.id === 2).reason, "Kept because the deadline is today.");
});

test("leaves tasks without a schedule entry untouched", () => {
  const merged = mergeScheduleReasons([{ id: 1, title: "One" }], []);
  assert.ok(!("reason" in merged[0]));
});

test("does not overwrite with an empty reason", () => {
  const merged = mergeScheduleReasons(
    [{ id: 1, title: "One", reason: "Kept because the deadline is today." }],
    [{ task_id: 1, reason: "" }],
  );
  assert.equal(merged[0].reason, "Kept because the deadline is today.");
});

test("does not mutate the input tasks", () => {
  const tasks = [{ id: 1, title: "One" }];
  mergeScheduleReasons(tasks, [{ task_id: 1, reason: "Some reason." }]);
  assert.ok(!("reason" in tasks[0]));
});
