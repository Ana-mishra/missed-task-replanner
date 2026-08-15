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

export function getTodayOverloadStatus(tasks, availableMinutes, currentTime = new Date()) {
  const endOfToday = new Date(currentTime)
  endOfToday.setHours(23, 59, 59, 999)
  const relevantTasks = tasks.filter((task) => {
    const deadline = new Date(task.deadline)
    return !task.completed && task.status !== 'completed' && !Number.isNaN(deadline.getTime()) && deadline <= endOfToday
  })
  const totalTodayMinutes = relevantTasks.reduce((total, task) => total + task.duration_minutes, 0)
  const remainingMinutes = availableMinutes - totalTodayMinutes
  return {
    totalTodayMinutes,
    availableMinutes,
    remainingMinutes,
    overloadedByMinutes: Math.max(0, -remainingMinutes),
    isOverloaded: totalTodayMinutes > availableMinutes,
  }
}
