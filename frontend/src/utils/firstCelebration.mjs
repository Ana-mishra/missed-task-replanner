// First-task-of-the-day celebration: a tiny moment of recognition, not
// gamification. No XP, points, badges, streaks, levels, counters, or
// progress bars anywhere here — just a soft chime and a floating note.
//
// The single source of truth for "already completed today" is the app's
// existing todayCompletedTaskIds (derived from real /task-history
// completed events). The module-level celebrated set below only dedupes
// the same completion event firing twice in one session; a page refresh
// re-derives everything from history, so a celebration can never replay.

export const FIRST_TASK_EVENT = "planora:first-task-completion";

// True only for a genuine incomplete → completed transition that is the
// day's first completion. `todayCompletedTaskIds` must be the snapshot
// taken BEFORE the completing update resolves.
export function isFirstCompletionToday(task, todayCompletedTaskIds) {
  if (!task) return false
  if (task.completed || task.status === "completed") return false
  return (todayCompletedTaskIds ?? []).length === 0
}

function localDayKey(now = new Date()) {
  return now.toDateString()
}

// Same-event guard: completingId in App already serializes requests, but
// two paths (button + form) could theoretically report the same task, so
// a (day, task) pair only ever celebrates once per session.
const celebratedPairs = new Set()

export function shouldCelebrateTask(taskId, now = new Date()) {
  const key = `${localDayKey(now)}:${String(taskId)}`
  if (celebratedPairs.has(key)) return false
  celebratedPairs.add(key)
  return true
}

// Must be called synchronously inside the user's click/keypress handler so
// the AudioContext is created/resumed within the user gesture. Safe to
// call on every completion attempt; only warms up one shared context.
let audioContext = null

export function prepareCelebrationAudio() {
  try {
    if (typeof window === "undefined") return null
    const Ctor = window.AudioContext || window.webkitAudioContext
    if (!Ctor) return null
    if (!audioContext) audioContext = new Ctor()
    if (audioContext.state === "suspended") void audioContext.resume()
    return audioContext
  } catch {
    return null
  }
}

// A very short, soft two-note chime (~0.9 s), generated with Web Audio so
// no audio asset or dependency is needed. Plays only on an already-running
// context, so it can never autoplay outside the user's gesture.
export function playFirstTaskChime({ subtle = false } = {}) {
  try {
    const context = audioContext
    if (!context || context.state !== "running") return false
    const reducedMotion =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    const gainValue = reducedMotion || subtle ? 0.06 : 0.12
    const notes = reducedMotion ? [{ at: 0, freq: 659.25 }] : [
      { at: 0, freq: 659.25 },
      { at: 0.18, freq: 987.77 },
    ]
    const startedAt = context.currentTime
    for (const note of notes) {
      const oscillator = context.createOscillator()
      const gain = context.createGain()
      oscillator.type = "sine"
      oscillator.frequency.value = note.freq
      gain.gain.setValueAtTime(0.0001, startedAt + note.at)
      gain.gain.exponentialRampToValueAtTime(gainValue, startedAt + note.at + 0.03)
      gain.gain.exponentialRampToValueAtTime(0.0001, startedAt + note.at + 0.85)
      oscillator.connect(gain)
      gain.connect(context.destination)
      oscillator.start(startedAt + note.at)
      oscillator.stop(startedAt + note.at + 0.9)
    }
    return true
  } catch {
    return false
  }
}

// Fire the full celebration exactly once per (day, task): chime + event
// for the floating note. Returns true when the celebration fired.
export function celebrateFirstTask(taskId, now = new Date()) {
  if (!shouldCelebrateTask(taskId, now)) return false
  playFirstTaskChime()
  try {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(FIRST_TASK_EVENT))
    }
  } catch {
    // The chime already played; a failed dispatch must not throw.
  }
  return true
}
