export const DEFAULT_AVAILABLE_MINUTES = 360

/**
 * Returns a read-only workload summary for the tasks selected in today's plan.
 * Deadline dates are intentionally not filtered here: the planner decides which
 * tasks belong today, including any useful future-deadline work.
 */
export function getPlannedWorkload(plannedTasks, availableMinutes = DEFAULT_AVAILABLE_MINUTES) {
  const taskCount = plannedTasks.length
  const estimatedMinutes = plannedTasks.reduce(
    (total, task) => total + task.duration_minutes,
    0,
  )

  return {
    taskCount,
    estimatedMinutes,
    availableMinutes,
    isOverloaded: estimatedMinutes > availableMinutes,
  }
}

export function getTodayOverloadStatus(
  tasks,
  availableMinutes,
  currentTime = new Date(),
) {
  const relevantTasks = tasks.filter(
    (task) =>
      !task.completed &&
      task.status !== "completed" &&
      Number.isFinite(task.duration_minutes) &&
      task.duration_minutes > 0,
  );

  const totalTodayMinutes = relevantTasks.reduce(
    (total, task) => total + task.duration_minutes,
    0,
  );

  const remainingMinutes = availableMinutes - totalTodayMinutes;

  return {
    totalTodayMinutes,
    availableMinutes,
    remainingMinutes,
    overloadedByMinutes: Math.max(0, -remainingMinutes),
    isOverloaded: totalTodayMinutes > availableMinutes,
  };
}
