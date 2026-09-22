// Plan Stability tooltip math: which task names to show and what the
// "+N more" line must say. Pure helper so the rule is unit-testable:
//   node src/utils/stabilityTooltip.test.mjs
//
// remaining = totalTasks - displayedTasks.length, using the authoritative
// category count and the actually rendered slice. The line renders only
// when something is displayed and something remains.
export const STABILITY_TOOLTIP_VISIBLE_TASKS = 4;

export function stabilityTooltip(count, tasks, visibleLimit = STABILITY_TOOLTIP_VISIBLE_TASKS) {
  const list = Array.isArray(tasks) ? tasks : [];
  const total = Number(count) || 0;
  const visible = list.slice(0, visibleLimit);
  return {
    visible,
    more: visible.length > 0 ? Math.max(0, total - visible.length) : 0,
  };
}

// Map a pointer angle to a donut category, independent of SVG hit-testing.
// angleFraction is clockwise from the top in [0, 1). Zero-count categories
// are skipped exactly like the painted segments. Returns null when there
// is nothing to hover.
export function stabilitySegmentAtAngle(counts, orderedKeys, angleFraction) {
  const keys = Array.isArray(orderedKeys) ? orderedKeys : [];
  const total = keys.reduce((sum, key) => sum + (Number(counts?.[key]) || 0), 0);
  if (!(total > 0)) return null;
  let angle = Number(angleFraction) % 1;
  if (!Number.isFinite(angle)) return null;
  if (angle < 0) angle += 1;
  const nonzero = keys.filter((key) => (Number(counts[key]) || 0) > 0);
  let start = 0;
  for (const key of nonzero) {
    const fraction = Number(counts[key]) / total;
    if (angle >= start && angle < start + fraction) return key;
    start += fraction;
  }
  // Floating-point dust at the final boundary belongs to the last segment.
  return nonzero.length > 0 ? nonzero[nonzero.length - 1] : null;
}
