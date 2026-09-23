// Merge per-task planning reasons from a /plan schedule response into the
// task objects used for rendering. Task objects from GET /tasks carry no
// `reason`; the planning reason belongs to a particular planning result, so
// it is joined here by task_id without touching the underlying Task model.
export function mergeScheduleReasons(tasks, schedule) {
  const reasonById = new Map(
    (schedule ?? []).map((item) => [String(item.task_id), item.reason || ""]),
  );
  return (tasks ?? []).map((task) => {
    const reason = reasonById.get(String(task.id));
    return reason ? { ...task, reason } : task;
  });
}
