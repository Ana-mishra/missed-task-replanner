// Tooltip-math regression tests. Plain Node, no runner needed:
//   node src/utils/stabilityTooltip.test.mjs
import { stabilityTooltip, stabilitySegmentAtAngle } from "./stabilityTooltip.mjs";

let failures = 0;
function check(name, cond, detail = "") {
  console.log(`${cond ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failures += 1;
}

function named(n) {
  return Array.from({ length: n }, (_, i) => ({ id: i + 1, title: `Task ${i + 1}` }));
}

// 1 task with title -> title shown, no "+1 more".
{
  const tip = stabilityTooltip(1, named(1));
  check("1 task shows its title", tip.visible.length === 1 && tip.visible[0].title === "Task 1");
  check("1 task has no +N more", tip.more === 0);
}

// 4 tasks with titles -> all four shown, no "+N more".
{
  const tip = stabilityTooltip(4, named(4));
  check("4 tasks all visible", tip.visible.length === 4);
  check("4 tasks have no +N more", tip.more === 0);
}

// 6 tasks with titles -> first four + "+2 more".
{
  const tip = stabilityTooltip(6, named(6));
  check("6 tasks show 4 names", tip.visible.length === 4);
  check("6 tasks say +2 more", tip.more === 2);
}

// Actual titles flow through untouched.
{
  const tip = stabilityTooltip(2, [{ id: 7, title: "Learning French" }, { id: 9, title: "Submit expense report" }]);
  check("actual titles appear", tip.visible[0].title === "Learning French" && tip.visible[1].title === "Submit expense report");
  check("2 named tasks have no +N more", tip.more === 0);
}

// Missing records never fabricate a "+N more" line on their own: with no
// displayed titles the tooltip falls back to its unavailable message.
{
  const tip = stabilityTooltip(6, []);
  check("empty names yield no +N more", tip.more === 0);
  check("empty names yield no visible titles", tip.visible.length === 0);
}

// Angle mapping mirrors the painted SVG segments: fractions of the ring
// measured clockwise from the top. Counts 1/1/6 over total 8 give
// stayed [0, .125), adjusted [.125, .25), missed [.25, 1).
{
  const counts = { stayed_as_planned: 1, adjusted: 1, missed: 6 };
  const keys = ["stayed_as_planned", "adjusted", "missed"];
  const at = (angle) => stabilitySegmentAtAngle(counts, keys, angle);
  check("angle 0 selects stayed", at(0) === "stayed_as_planned");
  check("angle inside stayed selects stayed", at(0.124) === "stayed_as_planned");
  check("boundary selects adjusted", at(0.125) === "adjusted");
  check("angle inside adjusted selects adjusted", at(0.2) === "adjusted");
  check("boundary selects missed", at(0.25) === "missed");
  check("angle inside missed selects missed", at(0.5) === "missed");
  check("angle near full circle selects missed", at(0.9999) === "missed");
  check("negative angle wraps", at(-0.5) === "missed");
  check("zero-count category is skipped", stabilitySegmentAtAngle(
    { stayed_as_planned: 0, adjusted: 2, missed: 0 }, keys, 0,
  ) === "adjusted");
  check("empty counts select nothing", stabilitySegmentAtAngle(
    { stayed_as_planned: 0, adjusted: 0, missed: 0 }, keys, 0.5,
  ) === null);
}

if (failures > 0) {
  console.error(`${failures} FAILURE(S)`);
  process.exit(1);
} else {
  console.log("ALL ANGLE TESTS PASSED");
}
