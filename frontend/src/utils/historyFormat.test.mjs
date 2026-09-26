import test from "node:test";
import assert from "node:assert/strict";
import { formatEventDateTime, formatHistoryTime } from "./historyFormat.mjs";

test("converts UTC 2026-09-26T07:44:00Z to 1:14 pm in Asia/Kolkata", () => {
  const result = formatHistoryTime("2026-09-26T07:44:00Z", "Asia/Kolkata");
  assert.equal(result, "1:14 pm");
});

test("converts UTC 2026-09-26T08:12:00Z to 1:42 pm in Asia/Kolkata", () => {
  const result = formatHistoryTime("2026-09-26T08:12:00Z", "Asia/Kolkata");
  assert.equal(result, "1:42 pm");
});

test("converts UTC 2026-09-26T09:48:00Z to 3:18 pm in Asia/Kolkata", () => {
  const result = formatHistoryTime("2026-09-26T09:48:00Z", "Asia/Kolkata");
  assert.equal(result, "3:18 pm");
});

test("two distinct UTC timestamps produce two distinct displayed times", () => {
  const time1 = formatHistoryTime("2026-09-26T08:12:00Z", "Asia/Kolkata");
  const time2 = formatHistoryTime("2026-09-26T09:48:00Z", "Asia/Kolkata");
  assert.equal(time1, "1:42 pm");
  assert.equal(time2, "3:18 pm");
  assert.notEqual(time1, time2);
});

test("converts UTC 2026-09-26T08:19:00Z to 1:49 pm in Asia/Kolkata (full path)", () => {
  // Backend emits the 1:49 PM IST event as 08:19Z; the UI must show 1:49 pm.
  const result = formatHistoryTime("2026-09-26T08:19:00Z", "Asia/Kolkata");
  assert.equal(result, "1:49 pm");
});

test("formatEventDateTime renders UTC instants in Asia/Kolkata date style", () => {
  assert.equal(
    formatEventDateTime("2026-09-26T08:19:00Z", "Asia/Kolkata"),
    "26 Sept, 1:49 pm",
  );
  assert.equal(
    formatEventDateTime("2026-09-26T08:12:00Z", "Asia/Kolkata"),
    "26 Sept, 1:42 pm",
  );
  assert.equal(
    formatEventDateTime("2026-09-26T09:48:00Z", "Asia/Kolkata"),
    "26 Sept, 3:18 pm",
  );
});

test("formatEventDateTime returns empty string for missing timestamps", () => {
  assert.equal(formatEventDateTime(null), "");
  assert.equal(formatEventDateTime(undefined), "");
});
