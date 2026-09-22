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

export async function ensurePushSubscription() {
  if (!isPushSupported()) {
    throw new Error('Browser notifications are not supported in this browser.')
  }
  if (Notification.permission !== 'granted') {
    throw new Error('Browser notification permission has not been granted.')
  }
  const { public_key: publicKey } = await getVapidPublicKey()
  if (!publicKey) {
    throw new Error('Push notifications are not configured yet. Please try again later.')
  }
  try {
    await navigator.serviceWorker.register(SERVICE_WORKER_URL)
    // register() resolves while the worker may still be installing, but
    // pushManager.subscribe() requires an active worker. `ready` waits for
    // activation; without it, first-time setup fails with AbortError
    // ("Subscription failed - no active Service Worker").
    const registration = await navigator.serviceWorker.ready
    const existing = await registration.pushManager.getSubscription()
    const subscription =
      existing ??
      (await subscribeWithTimeout(registration, {
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      }))
    const json = subscription.toJSON()
    await savePushSubscription({
      endpoint: subscription.endpoint,
      keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    })
    return subscription
  } catch (error) {
    // Development diagnostic only: DOMException names/messages and our own
    // error strings contain no credentials. The UI keeps its calm message.
    console.warn('Planora push setup failed:', error?.name, error?.message)
    throw error
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
