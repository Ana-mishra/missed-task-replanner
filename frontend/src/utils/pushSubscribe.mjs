// Bounded pushManager.subscribe(): the Push API has no built-in timeout,
// so a stalled push-service connection can hang forever. Racing against a
// timer lets the caller fall back to its calm error path instead.
// Zero imports: safe to unit-test under plain Node.
export const SUBSCRIBE_TIMEOUT_MS = 30000

export function subscribeWithTimeout(registration, options, timeoutMs = SUBSCRIBE_TIMEOUT_MS) {
  let timer
  return Promise.race([
    registration.pushManager.subscribe(options).finally(() => clearTimeout(timer)),
    new Promise((_, reject) => {
      timer = setTimeout(
        () => reject(new Error('Push subscription timed out. Please try again.')),
        timeoutMs,
      )
    }),
  ])
}
