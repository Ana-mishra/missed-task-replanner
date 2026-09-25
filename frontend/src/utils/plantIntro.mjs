// One-time new-user introduction persistence for My Plant.
//
// The seed→sprout welcome plays only once for a genuinely new user.
// Afterwards (refresh, navigation, return visits) the flag below says it
// was seen and the intro never replays. Storage access is guarded so
// private-mode failures can never break the page; the only cost of an
// unreadable store is replaying the welcome, never a crash.
//
// The storage parameter exists so tests can inject a fake store.
// Production callers omit it and get window.localStorage.

export const PLANT_INTRO_SEEN_KEY = 'planora.plantIntroSeen.v1'

function resolveStore(storage) {
  if (storage !== undefined) return storage
  if (typeof window !== 'undefined' && window.localStorage) {
    return window.localStorage
  }
  return undefined
}

export function readPlantIntroSeen(storage) {
  try {
    return resolveStore(storage)?.getItem(PLANT_INTRO_SEEN_KEY) === 'true'
  } catch {
    return false
  }
}

export function markPlantIntroSeen(storage) {
  try {
    resolveStore(storage)?.setItem(PLANT_INTRO_SEEN_KEY, 'true')
  } catch {
    // Private-mode or unavailable storage: stay silent.
  }
}
