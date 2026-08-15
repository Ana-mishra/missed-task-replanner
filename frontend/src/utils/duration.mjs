export function formatDuration(minutes) {
  const total = Math.max(0, Number(minutes) || 0)
  const hours = Math.floor(total / 60)
  const remaining = total % 60
  const parts = []
  if (hours) parts.push(`${hours} ${hours === 1 ? 'hour' : 'hours'}`)
  if (remaining || !hours) parts.push(`${remaining} ${remaining === 1 ? 'minute' : 'minutes'}`)
  return parts.join(' ')
}
