/* Planora service worker — browser push notifications only.
 * No offline caching, no PWA extras: receives push events, shows a
 * notification, and opens/focuses the app on click. */

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    try {
      data = { title: event.data ? event.data.text() : undefined }
    } catch {
      data = {}
    }
  }
  const title = typeof data.title === 'string' && data.title ? data.title : 'Planora reminder'
  const options = {
    body: typeof data.body === 'string' ? data.body : 'You have a Planora reminder.',
    tag: typeof data.tag === 'string' ? data.tag : 'planora-reminder',
    data: { url: typeof data.url === 'string' ? data.url : '/' },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const targetUrl = (event.notification.data && event.notification.data.url) || '/'
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const client of windows) {
        if ('focus' in client) {
          try {
            await client.focus()
            if ('navigate' in client && targetUrl && targetUrl !== '/') {
              await client.navigate(targetUrl)
            }
          } catch {
            // Focusing the existing window is best-effort.
          }
          return
        }
      }
      if (self.clients.openWindow) {
        await self.clients.openWindow(targetUrl)
      }
    })(),
  )
})
