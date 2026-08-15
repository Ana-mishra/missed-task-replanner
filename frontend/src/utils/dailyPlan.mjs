const PRIORITY_RANK = { high: 0, medium: 1, low: 2 }

function isProtected(task, now, endOfToday) {
  const deadline = new Date(task.deadline)
  return deadline <= endOfToday
}

export function createDailyPlan(tasks, availableMinutes, now = new Date()) {
  const endOfToday = new Date(now)
  endOfToday.setHours(23, 59, 59, 999)
  const rankedTasks = [...tasks]
    .filter((task) => !task.completed && task.status !== 'completed')
    .sort((firstTask, secondTask) => {
      const firstDeadline = new Date(firstTask.deadline)
      const secondDeadline = new Date(secondTask.deadline)
      const firstOverdue = firstDeadline < now
      const secondOverdue = secondDeadline < now
      const firstProtected = isProtected(firstTask, now, endOfToday)
      const secondProtected = isProtected(secondTask, now, endOfToday)
      if (firstOverdue !== secondOverdue) return firstOverdue ? -1 : 1
      if (firstProtected !== secondProtected) return firstProtected ? -1 : 1
      if (firstDeadline - secondDeadline !== 0) return firstDeadline - secondDeadline
      if ((PRIORITY_RANK[firstTask.priority] ?? 3) !== (PRIORITY_RANK[secondTask.priority] ?? 3)) return (PRIORITY_RANK[firstTask.priority] ?? 3) - (PRIORITY_RANK[secondTask.priority] ?? 3)
      return firstTask.duration_minutes - secondTask.duration_minutes
    })
  const protectedMinutes = rankedTasks.filter((task) => isProtected(task, now, endOfToday)).reduce((total, task) => total + task.duration_minutes, 0)
  let plannedMinutes = 0
  const plan = []
  for (const task of rankedTasks) {
    if (isProtected(task, now, endOfToday) || plannedMinutes + task.duration_minutes <= availableMinutes) {
      plan.push(task)
      plannedMinutes += task.duration_minutes
    }
  }
  return { plan, plannedMinutes, isOverloaded: protectedMinutes > availableMinutes }
}
