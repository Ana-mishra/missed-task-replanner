// Recovery mutation sequence, factored out of App.handleRecover so the
// concurrency behavior is deterministically testable in plain Node.
//
// Concurrency contract: `lock` is a synchronous instance-local mutex
// ({ current: bool }, e.g. a React ref object). It is CHECKED and SET
// synchronously below, BEFORE the first await, so two synchronous
// invocations in the same tick cannot both start the mutation sequence.
// It is released in `finally`, so success AND failure paths unlock.

export function createRecoveryLock() {
  return { current: false };
}

export async function runRecoverySequence({
  lock,
  taskId,
  window,
  isBusy,
  replanTask,
  planDay,
  getTasks,
}) {
  if (!taskId || (typeof isBusy === "function" && isBusy())) {
    return { started: false };
  }
  if (lock && lock.current) {
    return { started: false };
  }
  if (lock) {
    lock.current = true;
  }
  try {
    await replanTask(taskId, window);
    await planDay(window);
    const tasks = await getTasks();
    return { started: true, tasks };
  } finally {
    if (lock) {
      lock.current = false;
    }
  }
}
