// Current-vs-historical recovery state for task display.
//
// Backend `was_replanned` means "this task closed a missed→recovered cycle
// at some point in its history" — it stays true forever, even after the
// recovered slot itself elapses and the task becomes missed again. UI that
// claims a task is *currently* recovered must therefore also check the live
// task state: not done, not currently missed, and actually holding a
// scheduled slot from Plan My Day.
export function isCurrentlyRecovered(task) {
  if (!task || task.completed || task.status === "completed") return false;
  if (!task.was_replanned) return false;
  if (task.status === "missed") return false;
  return Boolean(task.scheduled_start && task.scheduled_end);
}
