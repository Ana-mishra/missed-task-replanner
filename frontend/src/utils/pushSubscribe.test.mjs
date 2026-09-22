// Focused test for the push-subscription hang guard. Plain Node:
//   node src/utils/pushSubscribe.test.mjs
import { subscribeWithTimeout } from './pushSubscribe.mjs'

let failures = 0
function check(name, cond, detail = '') {
  console.log(`${cond ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`)
  if (!cond) failures += 1
}

const okOptions = { userVisibleOnly: true, applicationServerKey: new Uint8Array(65) }

// 1. A hanging subscribe() must reject after the timeout instead of pending forever.
{
  const hanging = { pushManager: { subscribe: () => new Promise(() => {}) } }
  const start = Date.now()
  try {
    await subscribeWithTimeout(hanging, okOptions, 120)
    check('hanging subscribe rejects', false)
  } catch (error) {
    const elapsed = Date.now() - start
    check('hanging subscribe rejects after timeout', elapsed >= 100 && elapsed < 5000, `${elapsed}ms`)
    check('timeout error is safe to display', /timed out/.test(error.message))
  }
}

// 2. A fast subscribe() resolves normally and clears its timer.
{
  const fakeSub = { endpoint: 'https://push.example/sub' }
  const quick = { pushManager: { subscribe: async () => fakeSub } }
  const result = await subscribeWithTimeout(quick, okOptions, 1000)
  check('fast subscribe resolves with subscription', result === fakeSub)
}

// 3. A rejecting subscribe() still propagates the original error.
{
  const failing = { pushManager: { subscribe: async () => { throw new DOMException('denied', 'NotAllowedError') } } }
  try {
    await subscribeWithTimeout(failing, okOptions, 1000)
    check('rejecting subscribe propagates', false)
  } catch (error) {
    check('rejecting subscribe propagates original error', error.name === 'NotAllowedError')
  }
}

if (failures > 0) {
  console.error(`${failures} FAILURE(S)`)
  process.exit(1)
} else {
  console.log('ALL TESTS PASSED')
}
