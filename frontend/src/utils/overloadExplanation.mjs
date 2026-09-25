// Capacity-overload explanation, derived from the backend planner result.
//
// Detection lives in the backend: POST /plan returns `is_overloaded` and
// `unscheduled_minutes` (PlanningEngine counts exactly the minutes it
// skipped for lack of remaining capacity; see backend/app/services/planning.py).
// This module duplicates no scheduling logic — it only derives display
// numbers from those planner outputs:
//
//   total candidate demand = planned minutes + backend unscheduled minutes
//   shortfall            = max(0, demand - available)
//   remaining capacity   = max(0, available - planned)
//
// For example: 39 available with two 45-minute tasks left unscheduled gives
// demand = 0 + 90 = 90 and shortfall = 90 - 39 = 51.
export function getOverloadExplanation({
  availableMinutes = 0,
  plannedMinutes = 0,
  unscheduledMinutes = 0,
  isOverloaded = false,
} = {}) {
  const available = Number.isFinite(availableMinutes) ? availableMinutes : 0;
  const planned = Number.isFinite(plannedMinutes) ? plannedMinutes : 0;
  const unscheduled = Number.isFinite(unscheduledMinutes) ? unscheduledMinutes : 0;
  const totalDemandMinutes = planned + unscheduled;
  const shortfallMinutes = Math.max(0, totalDemandMinutes - available);
  const remainingCapacityMinutes = Math.max(0, available - planned);
  // The overload verdict itself stays backend-driven; the shortfall guard
  // only prevents rendering a "0 minutes over capacity" notice from a stale
  // persisted plan whose leftover no longer exceeds current capacity.
  const showOverload =
    Boolean(isOverloaded) && unscheduled > 0 && shortfallMinutes > 0;
  return {
    totalDemandMinutes,
    shortfallMinutes,
    remainingCapacityMinutes,
    showOverload,
  };
}

// Zero-scheduled overload state: a plan was generated, the backend reports
// overload, but no task received a slot. In this state the orange capacity
// notice is the sole explanation, so the standalone "Plan was reshaped."
// note is suppressed and Today's plan uses the calm empty-state card.
export function isZeroScheduledOverload({
  hasPlanned = false,
  planIsOverloaded = false,
  scheduledCount = 0,
} = {}) {
  return (
    Boolean(hasPlanned) &&
    Boolean(planIsOverloaded) &&
    scheduledCount === 0
  );
}

// Tasks the planner left out for capacity: incomplete, without a slot, and
// with a positive duration. The planner never counts completed or
// zero-duration tasks in `unscheduled_minutes`, so those are excluded here
// to avoid misattributing other planner outcomes to capacity.
export function getCapacityUnscheduledTasks(tasks) {
  return (tasks ?? []).filter(
    (task) =>
      !task.completed &&
      task.status !== "completed" &&
      (!task.scheduled_start || !task.scheduled_end) &&
      Number(task.duration_minutes) > 0,
  );
}
