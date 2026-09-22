import {
  deletePushSubscription,
  getVapidPublicKey,
  savePushSubscription,
} from '../services/api.js'
import { subscribeWithTimeout } from './pushSubscribe.mjs'

const SERVICE_WORKER_URL = '/push-sw.js'

export function isPushSupported() {
  return (
    typeof window !== 'undefined' &&
    'Notification' in window &&
    'serviceWorker' in navigator &&
    'PushManager' in window
  )
}

export function getBrowserPermission() {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'unsupported'
  return Notification.permission
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  const output = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) {
    output[i] = raw.charCodeAt(i)
  }
  return output
}

// TEMPORARY production diagnostic (safe fields only): each stage throws a
// message naming the stage plus HTTP status / DOMException name / message.
// NEVER include keys, tokens, endpoints, or subscription material here.
// The VAPID key itself is never displayed — only YES/NO receipt.
function stageError(stage, detail) {
  return new Error(`Push setup failed at ${stage}. ${detail}`)
}

export async function ensurePushSubscription() {
  if (!isPushSupported()) {
    throw new Error('Browser notifications are not supported in this browser.')
  }
  if (Notification.permission !== 'granted') {
    throw new Error('Browser notification permission has not been granted.')
  }
  let publicKey
  try {
    ;({ public_key: publicKey } = await getVapidPublicKey())
  } catch (error) {
    throw stageError(
      'vapid-fetch',
      `VAPID public key received: NO. HTTP status: ${error?.status ?? 'network-error'}.`,
    )
  }
  if (!publicKey) {
    throw stageError('vapid-fetch', 'VAPID public key received: NO.')
  }
  let registration
  try {
    await navigator.serviceWorker.register(SERVICE_WORKER_URL)
  } catch (error) {
    throw stageError(
      'service-worker-register',
      `VAPID public key received: YES. ${error?.name ?? 'Error'}: ${error?.message ?? 'registration failed'}.`,
    )
  }
  try {
    registration = await navigator.serviceWorker.ready
  } catch (error) {
    throw stageError(
      'service-worker-ready',
      `VAPID public key received: YES. ${error?.name ?? 'Error'}: ${error?.message ?? 'ready failed'}.`,
    )
  }
  try {
    const existing = await registration.pushManager.getSubscription()
    const subscription =
      existing ??
      (await subscribeWithTimeout(registration, {
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      }))
    const json = subscription.toJSON()
    try {
      await savePushSubscription({
        endpoint: subscription.endpoint,
        keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
      })
    } catch (error) {
      throw stageError(
        'push-subscribe-save',
        `VAPID public key received: YES. HTTP status: ${error?.status ?? 'network-error'}.`,
      )
    }
    return subscription
  } catch (error) {
    if (error?.message?.startsWith('Push setup failed at')) throw error
    // Development diagnostic only: DOMException names/messages and our own
    // error strings contain no credentials. The UI keeps its calm message.
    console.warn('Planora push setup failed:', error?.name, error?.message)
    throw stageError(
      'push-subscribe',
      `VAPID public key received: YES. ${error?.name ?? 'Error'}: ${error?.message ?? 'subscribe failed'}.`,
    )
  }
}

export async function hasPushSubscription() {
  if (!isPushSupported()) return false
  const registration = await navigator.serviceWorker.getRegistration()
  const subscription = await registration?.pushManager?.getSubscription()
  return Boolean(subscription)
}

export async function removePushSubscription() {
  try {
    if ('serviceWorker' in navigator) {
      const registration = await navigator.serviceWorker.getRegistration()
      const subscription = await registration?.pushManager?.getSubscription()
      await subscription?.unsubscribe()
    }
  } catch {
    // Local unsubscription is best-effort; the server row is removed below.
  }
  await deletePushSubscription()
}
