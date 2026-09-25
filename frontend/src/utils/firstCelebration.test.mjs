import test from "node:test";
import assert from "node:assert/strict";

import {
  celebrateFirstTask,
  isFirstCompletionToday,
} from "./firstCelebration.mjs";

test("incomplete task with zero completions today is first", () => {
  assert.equal(
    isFirstCompletionToday({ id: 1, completed: false, status: "pending" }, []),
    true,
  );
});

test("already-completed task is never a first completion", () => {
  assert.equal(
    isFirstCompletionToday({ id: 1, completed: true, status: "completed" }, []),
    false,
  );
  assert.equal(
    isFirstCompletionToday({ id: 2, completed: false, status: "completed" }, []),
    false,
  );
});

test("non-empty today list means not first, even for a fresh task", () => {
  assert.equal(
    isFirstCompletionToday({ id: 2, completed: false, status: "pending" }, ["1"]),
    false,
  );
});

test("missing task or ids never celebrate", () => {
  assert.equal(isFirstCompletionToday(null, []), false);
  assert.equal(
    isFirstCompletionToday({ id: 1, completed: false }, null),
    true,
  );
});

test("same task only celebrates once per day", () => {
  const now = new Date("2026-09-25T10:00:00");
  assert.equal(celebrateFirstTask(101, now), true);
  assert.equal(celebrateFirstTask(101, now), false);
  assert.equal(celebrateFirstTask(102, now), true);
});

test("same task may celebrate again on another day", () => {
  assert.equal(celebrateFirstTask(103, new Date("2026-09-25T10:00:00")), true);
  assert.equal(celebrateFirstTask(103, new Date("2026-09-26T10:00:00")), true);
});
