// Deterministic recovery-race test. Plain Node, no runner needed:
//   node src/utils/recovery.race.test.mjs
// Fires two SYNCHRONOUS runRecoverySequence invocations (same tick, no
// render/commit between them — exactly the React stale-closure window)
// with mocked deferred APIs, then asserts a single mutation sequence.
import { runRecoverySequence, createRecoveryLock } from "./recovery.mjs";

let failures = 0;
function check(name, cond, detail = "") {
  console.log(`${cond ? "PASS" : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failures += 1;
}

function deferred() {
  let resolve;
  const promise = new Promise((res) => { resolve = res; });
  return { promise, resolve };
}

function mocks({ failReplan = false, failPlan = false } = {}) {
  const calls = { replan: 0, plan: 0, getTasks: 0 };
  const gates = [];
  const api = {
    replanTask: async () => {
      calls.replan += 1;
      if (failReplan) throw new Error("replan failed");
      const g = deferred();
      gates.push(g);
      await g.promise;
    },
    planDay: async () => {
      calls.plan += 1;
      if (failPlan) throw new Error("plan failed");
    },
    getTasks: async () => {
      calls.getTasks += 1;
      return [{ id: 8 }];
    },
  };
  return { calls, gates, api };
}

const WINDOW = { available_start: "t0", available_end: "t1" };

// React render-closure simulation: the committed UI flag does NOT update
// between two synchronous invocations (no render commit in between).
const staleNotBusy = () => false;

// TEST 1 — the race: two sync invocations must yield ONE mutation sequence.
{
  const { calls, gates, api } = mocks();
  const lock = createRecoveryLock();
  const p1 = runRecoverySequence({ lock, taskId: 8, window: WINDOW, isBusy: staleNotBusy, ...api });
  const p2 = runRecoverySequence({ lock, taskId: 8, window: WINDOW, isBusy: staleNotBusy, ...api });
  check("T1 single replan (sync observation)", calls.replan === 1, `replan=${calls.replan}`);
  check("T1 single plan (sync observation)", calls.plan === 0, `plan=${calls.plan} (first sequence still in-flight)`);
  gates.forEach((g) => g.resolve());
  const [r1, r2] = await Promise.all([p1, p2]);
  check("T1 first sequence started", r1.started === true);
  check("T1 second sequence deduped", r2.started === false);
  check("T1 totals after settle", calls.replan === 1 && calls.plan === 1 && calls.getTasks === 1,
    `replan=${calls.replan} plan=${calls.plan} getTasks=${calls.getTasks}`);
}

// TEST 2 — lock released on success; a later call may proceed.
{
  const { calls, gates, api } = mocks();
  const lock = createRecoveryLock();
  const p = runRecoverySequence({ lock, taskId: 8, window: WINDOW, isBusy: staleNotBusy, ...api });
  gates.forEach((g) => g.resolve());
  await p;
  check("T2 lock released after success", lock.current === false);
  const p2 = runRecoverySequence({ lock, taskId: 8, window: WINDOW, isBusy: () => false, ...api });
  await Promise.resolve();
  // resolve pending gates created by p2
  // (gates array is shared; resolve everything again — resolve is idempotent)
  gates.forEach((g) => g.resolve());
  const r2 = await p2;
  check("T2 follow-up call proceeds", r2.started === true);
}

// TEST 3 — /replan rejects: error propagates, lock releases, recovery retryable.
{
  const { api } = mocks({ failReplan: true });
  const lock = createRecoveryLock();
  let error = null;
  try {
    await runRecoverySequence({ lock, taskId: 8, window: WINDOW, isBusy: staleNotBusy, ...api });
  } catch (e) { error = e; }
  check("T3 replan error propagates", error && error.message === "replan failed");
  check("T3 lock released after replan failure", lock.current === false);
}

// TEST 4 — /plan rejects: error propagates, lock releases.
{
  const { calls, gates, api } = mocks({ failPlan: true });
  const lock = createRecoveryLock();
  const p = runRecoverySequence({ lock, taskId: 8, window: WINDOW, isBusy: staleNotBusy, ...api });
  gates.forEach((g) => g.resolve());
  let error = null;
  try { await p; } catch (e) { error = e; }
  check("T4 plan error propagates", error && error.message === "plan failed");
  check("T4 lock released after plan failure", lock.current === false);
  check("T4 no getTasks after plan failure", calls.getTasks === 0);
}

console.log(failures === 0 ? "ALL TESTS PASSED" : `${failures} TEST(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
