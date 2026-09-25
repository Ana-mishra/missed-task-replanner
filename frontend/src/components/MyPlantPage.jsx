import { useCallback, useEffect, useRef, useState } from 'react'

import { getTaskHistory } from '../services/api.js'
import { IconLeaf } from './icons.jsx'
import '../styles/my-plant.css'
import {
  companionMood,
  eyeTrackingOffset,
  isNewUser,
  littleMoment,
  NEW_USER_WELCOME,
  recentDaysStrip,
  recoveredToday,
  resolveDisplayStage,
} from '../utils/plantCompanion.mjs'
import { markPlantIntroSeen, readPlantIntroSeen } from '../utils/plantIntro.mjs'

// Moods with open pupils that may track the cursor. NEEDS_CARE keeps
// sleepy half-lidded eyes with no track groups by construction.
const TRACKED_MOODS = new Set(['HAPPY', 'GROWING', 'RETURNING'])

// Day state labels for journey interaction messages
const DAY_MESSAGES = {
  completed: "You showed up that day. 🌱",
  missed: "A slower day. That's okay.",
  today: "You're here today. That's what matters. 💚",
  recovered: "You came back and kept going. 🌿",
}

// ---------------------------------------------------------------------------
// useEyeTracking — pupils follow the cursor via ref + rAF only (zero
// re-renders). The transform is applied to .plant-face__track wrappers so it
// never fights the blink animation on the inner groups. Scoped to this page:
// listeners attach on mount and are fully removed on unmount.
// ---------------------------------------------------------------------------
function useEyeTracking(faceRef, moodIdRef) {
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    // Touch devices get the pure idle animation; no cursor to follow.
    if (!window.matchMedia('(pointer: fine)').matches) return
    let raf = 0
    let target = { dx: 0, dy: 0 }
    let current = { dx: 0, dy: 0 }
    let lastPointerAt = Date.now()
    let nextLookAt = Date.now() + 3600
    let idleLook = { dx: 0, dy: 0 }
    const onMove = (event) => {
      const face = faceRef.current
      if (!face || typeof event.clientX !== 'number') return
      const rect = face.getBoundingClientRect()
      target = eyeTrackingOffset(
        event.clientX,
        event.clientY,
        rect.left + rect.width / 2,
        rect.top + rect.height / 2,
      )
      lastPointerAt = Date.now()
    }
    // Cursor left the viewport: glide back to neutral.
    const onLeave = () => { target = { dx: 0, dy: 0 } }
    const tick = () => {
      const now = Date.now()
      if (now - lastPointerAt > 2800 && now >= nextLookAt) {
        idleLook = { dx: [-2.2, 0, 2.2][Math.floor(Math.random() * 3)], dy: -0.7 }
        nextLookAt = now + 3200 + Math.random() * 3600
      }
      const hasRecentPointer = now - lastPointerAt < 2800
      const goal = TRACKED_MOODS.has(moodIdRef.current)
        ? (hasRecentPointer ? target : idleLook)
        : { dx: 0, dy: 0 }
      current = {
        dx: current.dx + (goal.dx - current.dx) * 0.12,
        dy: current.dy + (goal.dy - current.dy) * 0.12,
      }
      const face = faceRef.current
      if (face) {
        const transform = `translate(${current.dx.toFixed(2)}px, ${current.dy.toFixed(2)}px)`
        face.querySelectorAll('.plant-face__track').forEach((node) => {
          node.style.transform = transform
        })
      }
      raf = requestAnimationFrame(tick)
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    document.documentElement.addEventListener('mouseleave', onLeave)
    raf = requestAnimationFrame(tick)
    return () => {
      window.removeEventListener('pointermove', onMove)
      document.documentElement.removeEventListener('mouseleave', onLeave)
      cancelAnimationFrame(raf)
      faceRef.current
        ?.querySelectorAll('.plant-face__track')
        .forEach((node) => { node.style.transform = '' })
    }
  }, [])
}

// ---------------------------------------------------------------------------
// usePetting — a small friendly reaction when the plant is clicked/tapped:
// brief bounce via the 'plant-visual--petted' class. Cooldown-limited so
// repeated clicking never looks chaotic; skipped while the care animation
// owns the SVG transform. No scores, no rewards — just a companion.
// ---------------------------------------------------------------------------
function usePetting(visualRef) {
  const [petted, setPetted] = useState(false)
  const coolingRef = useRef(false)
  const timersRef = useRef([])
  useEffect(() => () => {
    timersRef.current.forEach((timer) => window.clearTimeout(timer))
  }, [])
  const pet = useCallback(() => {
    if (coolingRef.current) return
    if (visualRef.current?.classList.contains('plant-visual--caring')) return
    coolingRef.current = true
    setPetted(true)
    const settleTimer = window.setTimeout(() => {
      setPetted(false)
      const cooldownTimer = window.setTimeout(() => { coolingRef.current = false }, 1400)
      timersRef.current.push(cooldownTimer)
    }, 950)
    timersRef.current.push(settleTimer)
  }, [visualRef])
  return [petted, pet]
}

// ---------------------------------------------------------------------------
// useBlink — the resting state is always open eyes; a quick squash plays
// every few seconds at randomized intervals so blinks never look
// mechanical. Returns true only during the ~150ms lid-close. Skipped
// entirely under prefers-reduced-motion.
// ---------------------------------------------------------------------------
function useBlink() {
  const [blinking, setBlinking] = useState(false)
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let alive = true
    let openTimer = 0
    let closeTimer = 0
    const schedule = () => {
      openTimer = window.setTimeout(() => {
        if (!alive) return
        setBlinking(true)
        closeTimer = window.setTimeout(() => {
          if (!alive) return
          setBlinking(false)
          schedule()
        }, 150)
      }, 2600 + Math.random() * 3800)
    }
    schedule()
    return () => {
      alive = false
      window.clearTimeout(openTimer)
      window.clearTimeout(closeTimer)
    }
  }, [])
  return blinking
}

// ---------------------------------------------------------------------------
// JourneyDay — interactive day button for the 7-day journey strip.
// When clicked, becomes selected and triggers plant/message reaction.
// ---------------------------------------------------------------------------
function JourneyDay({ day, isSelected, onSelect }) {
  const isLit = day.showedUp
  const isToday = day.isToday
  const isRecovered = day.recovered // if we track this

  let messageKey = 'missed'
  if (isToday) messageKey = 'today'
  else if (isLit) messageKey = 'completed'
  else if (isRecovered) messageKey = 'recovered'

  const state = isToday ? 'today' : isRecovered ? 'recovered' : isLit ? 'completed' : 'missed'

  return (
    <button
      key={day.key}
      className={[
        'plant-journey__day',
        isLit ? 'plant-journey__day--lit' : 'plant-journey__day--muted',
        isToday ? 'plant-journey__day--today' : '',
        isSelected ? 'plant-journey__day--selected' : '',
      ].filter(Boolean).join(' ')}
      onClick={() => onSelect(day)}
      aria-label={`${day.label}, ${state}${isSelected ? ', selected' : ''}`}
      aria-current={isToday ? 'date' : undefined}
      aria-pressed={isSelected}
      title={DAY_MESSAGES[messageKey]}
    >
      <IconLeaf width={24} height={24} />
      <span className="plant-journey__day-label">{day.label}</span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// PlantSpeech — the plant's voice, shown as a soft botanical callout near
// the plant. Changes based on mood and selected journey day.
// ---------------------------------------------------------------------------
function PlantSpeech({ mood, selectedDay, completedToday, recoveredToday, defaultMessage }) {
  // If a day is selected, show that day's message
  if (selectedDay) {
    if (selectedDay.isToday) {
      return (
        <p className="plant-speech">
          <span className="plant-speech__bubble" aria-live="polite">
            You're here today. That's what matters. 💚
          </span>
        </p>
      )
    }
    if (selectedDay.showedUp) {
      return (
        <p className="plant-speech">
          <span className="plant-speech__bubble" aria-live="polite">
            You showed up that day. 🌱
          </span>
        </p>
      )
    }
    if (selectedDay.recovered) {
      return (
        <p className="plant-speech">
          <span className="plant-speech__bubble" aria-live="polite">
            You came back and kept going. 🌿
          </span>
        </p>
      )
    }
    return (
      <p className="plant-speech">
        <span className="plant-speech__bubble" aria-live="polite">
          A slower day. That's okay.
        </span>
      </p>
    )
  }

  // Default: mood-based message (from littleMoment or companionMood)
  let message = defaultMessage || mood.message
  if (completedToday && recoveredToday) {
    message = "You came back today. Your plant is happy to see you. 🌿"
  } else if (completedToday) {
    message = "You took care of things today. 💚"
  } else if (recoveredToday) {
    message = "You made some progress today. 🌱"
  }

  return (
    <p className="plant-speech">
      <span className="plant-speech__bubble" aria-live="polite">{message}</span>
    </p>
  )
}

// ---------------------------------------------------------------------------
// PlantFace — dedicated expression component living on the pot body.
// All four mood variants stay mounted; CSS crossfades the active one via
// data-mood so expression changes transition gently with no JS state
// machine. Shapes are simple SVG strokes in the existing green family.
// ---------------------------------------------------------------------------
function PlantFace({ mood, faceRef, blinking }) {
  const faceClass = ['plant-face', blinking ? 'plant-face--blinking' : '']
    .filter(Boolean).join(' ')
  return (
    <g className={faceClass} data-mood={mood} ref={faceRef}>
      {/* HAPPY — open expressive eyes with visible sclera & pupils, gentle smile, soft blush */}
      <g className="plant-face__variant" data-face="HAPPY">
        {/* Eye whites (sclera) — stationary */}
        <g className="plant-face__eyes">
          <ellipse className="plant-face__eye-white" cx="85" cy="188" rx="7.5" ry="6" />
          <ellipse className="plant-face__eye-white" cx="115" cy="188" rx="7.5" ry="6" />
        </g>
        {/* Pupils — these track the cursor, and blink scales them */}
        <g className="plant-face__track">
          <g className="plant-face__blink">
            <circle className="plant-face__pupil" cx="85" cy="188" r="3.2" />
            <circle className="plant-face__pupil" cx="115" cy="188" r="3.2" />
          </g>
        </g>
        <path className="plant-face__feature" d="M90 197 Q100 202 110 197" />
        <ellipse className="plant-face__blush" cx="76" cy="194" rx="4" ry="2.5" />
        <ellipse className="plant-face__blush" cx="124" cy="194" rx="4" ry="2.5" />
      </g>
      {/* GROWING — bright open eyes, curious smile */}
      <g className="plant-face__variant" data-face="GROWING">
        <g className="plant-face__eyes">
          <ellipse className="plant-face__eye-white" cx="85" cy="187" rx="8" ry="6.5" />
          <ellipse className="plant-face__eye-white" cx="115" cy="187" rx="8" ry="6.5" />
        </g>
        <g className="plant-face__track">
          <g className="plant-face__blink">
            <circle className="plant-face__pupil" cx="85" cy="187" r="3.5" />
            <circle className="plant-face__pupil" cx="115" cy="187" r="3.5" />
          </g>
        </g>
        <path className="plant-face__feature" d="M89 196 Q100 203 111 196" />
      </g>
      {/* NEEDS_CARE — sleepy/droopy lids, small neutral mouth.
          Tired, never broken, never fully closed. */}
      <g className="plant-face__variant" data-face="NEEDS_CARE">
        <g className="plant-face__blink">
          {/* Heavy-lidded: eye whites partially covered by upper lid */}
          <ellipse className="plant-face__eye-white" cx="85" cy="189" rx="7.5" ry="4" />
          <ellipse className="plant-face__eye-white" cx="115" cy="189" rx="7.5" ry="4" />
          <circle className="plant-face__pupil" cx="85" cy="189" r="2.8" />
          <circle className="plant-face__pupil" cx="115" cy="189" r="2.8" />
          {/* Upper eyelids for sleepy look */}
          <path className="plant-face__lid" d="M77.5 183.5 Q85 181.5 92.5 183.5" />
          <path className="plant-face__lid" d="M107.5 183.5 Q115 181.5 122.5 183.5" />
        </g>
        <path className="plant-face__feature" d="M79 186.5 L91 186.5" />
        <path className="plant-face__feature" d="M109 186.5 L121 186.5" />
        <path className="plant-face__feature" d="M92 197.5 Q100 199.5 108 197.5" />
      </g>
      {/* RETURNING — raised happy brows, bright open eyes, open smile: welcome back */}
      <g className="plant-face__variant" data-face="RETURNING">
        <path className="plant-face__brow" d="M79 180 Q85 176.5 91 180" />
        <path className="plant-face__brow" d="M109 180 Q115 176.5 121 180" />
        <g className="plant-face__eyes">
          <ellipse className="plant-face__eye-white" cx="85" cy="187" rx="8" ry="6.5" />
          <ellipse className="plant-face__eye-white" cx="115" cy="187" rx="8" ry="6.5" />
        </g>
        <g className="plant-face__track">
          <g className="plant-face__blink">
            <circle className="plant-face__pupil" cx="85" cy="187" r="3.8" />
            <circle className="plant-face__pupil" cx="115" cy="187" r="3.8" />
          </g>
        </g>
        <path className="plant-face__feature" d="M88 195 Q100 204 112 195" />
        <ellipse className="plant-face__blush" cx="76" cy="194" rx="4" ry="2.5" />
        <ellipse className="plant-face__blush" cx="124" cy="194" rx="4" ry="2.5" />
      </g>
    </g>
  )
}

// ---------------------------------------------------------------------------
// PlantSvg — inline SVG plant in a ceramic pot.
// Vitality drives leaf droop via CSS class. Care animation fires via
// the 'plant-visual--caring' class added on first-completion-of-day.
// ---------------------------------------------------------------------------
function PlantSvg({ stage, vitality, animating, mood, faceRef, blinking, bloomStage }) {
  // How many leaf pairs to show based on stage, and how tall the stem is.
  const stageConfig = {
    seed:        { stemH: 0,   leaves: 0, showSeedBody: true  },
    sprout:      { stemH: 28,  leaves: 1, showSeedBody: false },
    young_plant: { stemH: 48,  leaves: 2, showSeedBody: false },
    growing:     { stemH: 68,  leaves: 3, showSeedBody: false },
    flourishing: { stemH: 88,  leaves: 4, showSeedBody: false },
    mature:      { stemH: 104, leaves: 5, showSeedBody: false },
  }
  const cfg = stageConfig[stage] || stageConfig.seed

  const droopClass = vitality === 'droopy' ? 'plant-visual--droopy'
    : vitality === 'very_droopy' ? 'plant-visual--very-droopy'
    : ''

  const svgClass = [
    'plant-visual__svg',
    droopClass,
    animating ? 'plant-visual--caring' : '',
  ].filter(Boolean).join(' ')

  // Soil / pot base is always at y=170 in the 200×220 viewBox.
  const soilY = 170
  const potTop = soilY + 8
  const stemBaseX = 100
  const stemTopY  = soilY - cfg.stemH

  return (
    <svg
      className={svgClass}
      viewBox="0 0 200 220"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
    >
      {/* ---- Pot body ---- */}
      {/* Pot rim (slightly wider trapezoid) */}
      <path
        className="plant-pot__rim"
        d="M62 172 Q62 168 66 168 L134 168 Q138 168 138 172 L136 176 L64 176 Z"
      />
      {/* Pot body trapezoid */}
      <path
        className="plant-pot__body"
        d="M64 176 L72 214 Q72 218 76 218 L124 218 Q128 218 128 214 L136 176 Z"
      />
      {/* Companion face sits on the pot body */}
      <PlantFace mood={mood} faceRef={faceRef} blinking={blinking} />
      {/* Soil disc */}
      <ellipse
        className="plant-pot__soil"
        cx="100" cy="170" rx="36" ry="6"
      />

      {/* ---- Seed body (only in seed stage) ---- */}
      {cfg.showSeedBody && (
        <g className="plant-seed">
          <ellipse cx="100" cy="163" rx="8" ry="6" className="plant-seed__body" />
          <line x1="100" y1="157" x2="100" y2="152" className="plant-seed__sprout" strokeLinecap="round" />
          <line x1="100" y1="154" x2="95"  y2="149" className="plant-seed__sprout" strokeLinecap="round" />
        </g>
      )}

      {/* The upper plant moves independently so the pot remains grounded. */}
      <g className="plant-organic">
      {/* ---- Stem ---- */}
      {cfg.stemH > 0 && (
        <line
          className="plant-stem"
          x1={stemBaseX} y1={soilY - 2}
          x2={stemBaseX} y2={stemTopY}
          strokeLinecap="round"
        />
      )}

      {/* ---- Leaves ---- */}
      {cfg.leaves >= 1 && (
        <g className="plant-leaves plant-leaves--pair1">
          {/* Left leaf */}
          <path
            className="plant-leaf plant-leaf--left"
            d={`M ${stemBaseX} ${stemTopY + 14}
                Q ${stemBaseX - 28} ${stemTopY - 4} ${stemBaseX - 10} ${stemTopY - 20}
                Q ${stemBaseX - 4}  ${stemTopY + 2}  ${stemBaseX} ${stemTopY + 14}`}
          />
          {/* Right leaf */}
          <path
            className="plant-leaf plant-leaf--right"
            d={`M ${stemBaseX} ${stemTopY + 14}
                Q ${stemBaseX + 28} ${stemTopY - 4} ${stemBaseX + 10} ${stemTopY - 20}
                Q ${stemBaseX + 4}  ${stemTopY + 2}  ${stemBaseX} ${stemTopY + 14}`}
          />
        </g>
      )}
      {cfg.leaves >= 2 && (
        <g className="plant-leaves plant-leaves--pair2">
          <path
            className="plant-leaf plant-leaf--left"
            d={`M ${stemBaseX} ${stemTopY + 36}
                Q ${stemBaseX - 32} ${stemTopY + 18} ${stemBaseX - 12} ${stemTopY + 2}
                Q ${stemBaseX - 4}  ${stemTopY + 22}  ${stemBaseX} ${stemTopY + 36}`}
          />
          <path
            className="plant-leaf plant-leaf--right"
            d={`M ${stemBaseX} ${stemTopY + 36}
                Q ${stemBaseX + 32} ${stemTopY + 18} ${stemBaseX + 12} ${stemTopY + 2}
                Q ${stemBaseX + 4}  ${stemTopY + 22}  ${stemBaseX} ${stemTopY + 36}`}
          />
        </g>
      )}
      {cfg.leaves >= 3 && (
        <g className="plant-leaves plant-leaves--pair3">
          <path
            className="plant-leaf plant-leaf--left"
            d={`M ${stemBaseX} ${stemTopY + 58}
                Q ${stemBaseX - 30} ${stemTopY + 40} ${stemBaseX - 10} ${stemTopY + 24}
                Q ${stemBaseX - 3}  ${stemTopY + 44}  ${stemBaseX} ${stemTopY + 58}`}
          />
          <path
            className="plant-leaf plant-leaf--right"
            d={`M ${stemBaseX} ${stemTopY + 58}
                Q ${stemBaseX + 30} ${stemTopY + 40} ${stemBaseX + 10} ${stemTopY + 24}
                Q ${stemBaseX + 3}  ${stemTopY + 44}  ${stemBaseX} ${stemTopY + 58}`}
          />
        </g>
      )}
      {cfg.leaves >= 4 && (
        <g className="plant-leaves plant-leaves--pair4">
          <path
            className="plant-leaf plant-leaf--left"
            d={`M ${stemBaseX} ${stemTopY + 80}
                Q ${stemBaseX - 34} ${stemTopY + 60} ${stemBaseX - 14} ${stemTopY + 44}
                Q ${stemBaseX - 4}  ${stemTopY + 66}  ${stemBaseX} ${stemTopY + 80}`}
          />
          <path
            className="plant-leaf plant-leaf--right"
            d={`M ${stemBaseX} ${stemTopY + 80}
                Q ${stemBaseX + 34} ${stemTopY + 60} ${stemBaseX + 14} ${stemTopY + 44}
                Q ${stemBaseX + 4}  ${stemTopY + 66}  ${stemBaseX} ${stemTopY + 80}`}
          />
        </g>
      )}
      {cfg.leaves >= 5 && (
        <g className="plant-leaves plant-leaves--pair5">
          {/* Topmost pair — slightly smaller, spread wide for mature look */}
          <path
            className="plant-leaf plant-leaf--left"
            d={`M ${stemBaseX} ${stemTopY + 20}
                Q ${stemBaseX - 24} ${stemTopY + 4} ${stemBaseX - 6} ${stemTopY - 12}
                Q ${stemBaseX}      ${stemTopY + 4}  ${stemBaseX} ${stemTopY + 20}`}
          />
          <path
            className="plant-leaf plant-leaf--right"
            d={`M ${stemBaseX} ${stemTopY + 20}
                Q ${stemBaseX + 24} ${stemTopY + 4} ${stemBaseX + 6} ${stemTopY - 12}
                Q ${stemBaseX}      ${stemTopY + 4}  ${stemBaseX} ${stemTopY + 20}`}
          />
        </g>
      )}

      {/* Flowers arrive only after a quiet moment with the companion. */}
      {cfg.stemH > 0 && (
        <g className={`plant-blooms plant-blooms--stage-${bloomStage}`} aria-hidden="true">
          <g className="plant-bloom plant-bloom--one" transform={`translate(${stemBaseX - 17} ${stemTopY + 7})`}>
            <g className="plant-bloom__motion">
            <circle className="plant-bloom__petal" cx="0" cy="-4" r="3.4" />
            <circle className="plant-bloom__petal" cx="3.8" cy="-1.2" r="3.4" />
            <circle className="plant-bloom__petal" cx="2.3" cy="3.4" r="3.4" />
            <circle className="plant-bloom__petal" cx="-2.3" cy="3.4" r="3.4" />
            <circle className="plant-bloom__petal" cx="-3.8" cy="-1.2" r="3.4" />
            <circle className="plant-bloom__center" cx="0" cy="0" r="2" />
            </g>
          </g>
          <g className="plant-bloom plant-bloom--two" transform={`translate(${stemBaseX + 21} ${stemTopY + 20})`}>
            <g className="plant-bloom__motion">
            <circle className="plant-bloom__petal" cx="0" cy="-3.2" r="2.7" />
            <circle className="plant-bloom__petal" cx="3" cy="-1" r="2.7" />
            <circle className="plant-bloom__petal" cx="1.8" cy="2.8" r="2.7" />
            <circle className="plant-bloom__petal" cx="-1.8" cy="2.8" r="2.7" />
            <circle className="plant-bloom__petal" cx="-3" cy="-1" r="2.7" />
            <circle className="plant-bloom__center" cx="0" cy="0" r="1.6" />
            </g>
          </g>
        </g>
      )}
      </g>

      {/* ---- Tiny sparkle particles (shown during care animation only) ---- */}
      <g className="plant-sparkles" aria-hidden="true">
        <circle className="plant-sparkle plant-sparkle--1" cx="82"  cy={stemTopY - 8}  r="2.5" />
        <circle className="plant-sparkle plant-sparkle--2" cx="118" cy={stemTopY - 12} r="2"   />
        <circle className="plant-sparkle plant-sparkle--3" cx="94"  cy={stemTopY - 22} r="1.5" />
        <circle className="plant-sparkle plant-sparkle--4" cx="112" cy={stemTopY}      r="1.5" />
      </g>
    </svg>
  )
}

// ---------------------------------------------------------------------------
// MyPlantPage — main export. The plant is the hero; everything else is one
// contextual message, one consistency line, and a quiet 7-day strip.
// ---------------------------------------------------------------------------
export default function MyPlantPage({ plantData, plantLoading, plantError }) {
  // Track the previous grew_today so we can detect the first-of-day event.
  const prevGrewTodayRef = useRef(plantData?.grew_today ?? false)
  const [animating, setAnimating] = useState(false)
  // Eye-tracking targets the face group imperatively; the current mood id
  // is shared via ref so the rAF loop never needs re-renders or re-subscribes.
  const faceRef = useRef(null)
  const moodIdRef = useRef(null)
  useEyeTracking(faceRef, moodIdRef)
  const visualRef = useRef(null)
  const [petted, pet] = usePetting(visualRef)
  const blinking = useBlink()

  // One-time new-user introduction: seed → pop → sprout, persisted so it
  // never replays. Hooks stay above the early returns below.
  const [introSeen, setIntroSeen] = useState(() => readPlantIntroSeen())
  const [introPhase, setIntroPhase] = useState('idle') // idle|seed|pop|sprout|done
  const introTimersRef = useRef([])
  useEffect(() => () => {
    introTimersRef.current.forEach((timer) => window.clearTimeout(timer))
  }, [])

  // Selected day in journey strip for interaction
  const [selectedDay, setSelectedDay] = useState(null)
  const [sceneReacting, setSceneReacting] = useState(false)
  const [bloomStage, setBloomStage] = useState(0)
  const sceneTimerRef = useRef(0)

  useEffect(() => () => window.clearTimeout(sceneTimerRef.current), [])
  const reactToScene = useCallback(() => {
    setSceneReacting(false)
    window.clearTimeout(sceneTimerRef.current)
    requestAnimationFrame(() => {
      setSceneReacting(true)
      sceneTimerRef.current = window.setTimeout(() => setSceneReacting(false), 1100)
    })
  }, [])
  const selectDay = useCallback((day) => {
    setSelectedDay(day)
    reactToScene()
  }, [reactToScene])

  useEffect(() => {
    const firstBloom = window.setTimeout(() => setBloomStage(1), 24000)
    const secondBloom = window.setTimeout(() => setBloomStage(2), 34000)
    return () => {
      window.clearTimeout(firstBloom)
      window.clearTimeout(secondBloom)
    }
  }, [])

  useEffect(() => {
    if (!plantData) return
    const justGrew = !prevGrewTodayRef.current && plantData.grew_today
    if (justGrew) {
      setAnimating(true)
      // Animation is ~1.4 s; clear the class slightly after so it can replay
      // if the user navigates away and back (though grew_today won't be false
      // again until tomorrow, so replaying is already guarded by the server).
      const t = setTimeout(() => setAnimating(false), 1800)
      return () => clearTimeout(t)
    }
    prevGrewTodayRef.current = plantData.grew_today
  }, [plantData?.grew_today])

  // Also fire the animation on first mount if grew_today is already true
  // (user navigates to the plant page after already completing a task).
  const mountedRef = useRef(false)
  useEffect(() => {
    if (mountedRef.current) return
    mountedRef.current = true
    if (plantData?.grew_today) {
      setAnimating(true)
      const t = setTimeout(() => setAnimating(false), 1800)
      return () => clearTimeout(t)
    }
  }, [plantData])

  // Yesterday (IST) decides HAPPY vs RETURNING only when real history is
  // available; otherwise the mood safely falls back to HAPPY. One fetch
  // feeds the mood, the journey strip, and the little moment alike.
  // NOTE: hooks must stay above the early returns below so every render
  // calls the exact same hook sequence. This fetch is plantData-independent.
  const [historyEvents, setHistoryEvents] = useState(null)

  useEffect(() => {
    let cancelled = false
    getTaskHistory()
      .then((history) => { if (!cancelled) setHistoryEvents(history ?? []) })
      .catch(() => { if (!cancelled) setHistoryEvents([]) })
    return () => { cancelled = true }
  }, [])

  // One-time intro choreography. Fires only once history confirms a
  // genuinely new user; the render body below derives the phase classes
  // and the static pre-history frame from the same inputs.
  useEffect(() => {
    if (!plantData) return
    const historyLoaded = historyEvents !== null
    const confirmed =
      historyLoaded &&
      !readPlantIntroSeen() &&
      isNewUser({
        historyEvents,
        growthDays: plantData.growth_days ?? 0,
        completedToday: plantData.completed_today,
      })
    if (!confirmed) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      // No motion: settle directly on the sprout and remember it.
      setIntroPhase('sprout')
      markPlantIntroSeen()
      setIntroSeen(true)
      const t = window.setTimeout(() => setIntroPhase('done'), 300)
      introTimersRef.current.push(t)
      return () => window.clearTimeout(t)
    }
    setIntroPhase('seed')
    const t1 = window.setTimeout(() => setIntroPhase('pop'), 1100)
    const t2 = window.setTimeout(() => setIntroPhase('sprout'), 2100)
    const t3 = window.setTimeout(() => {
      setIntroPhase('done')
      markPlantIntroSeen()
      setIntroSeen(true)
    }, 3700)
    introTimersRef.current.push(t1, t2, t3)
    return () => {
      window.clearTimeout(t1)
      window.clearTimeout(t2)
      window.clearTimeout(t3)
    }
  }, [plantData, historyEvents])

  if (plantLoading) {
    return (
      <div className="plant-page">
        <header className="plant-page__header">
          <h1 className="plant-page__title">My Plant</h1>
        </header>
        <p className="state-message" aria-live="polite">Loading your plant…</p>
      </div>
    )
  }

  if (plantError || !plantData) {
    return (
      <div className="plant-page">
        <header className="plant-page__header">
          <h1 className="plant-page__title">My Plant</h1>
        </header>
        <p className="state-message state-message--error" role="alert">
          {plantError || 'Could not load your plant data.'}
        </p>
      </div>
    )
  }

  const {
    stage,
    completed_today,
    vitality,
  } = plantData

  const strip = recentDaysStrip(historyEvents ?? [])
  const showedUpYesterday = historyEvents === null
    ? undefined
    : (strip.length >= 2 ? strip[strip.length - 2].showedUp : undefined)

  const mood = companionMood({ completed_today, vitality, showedUpYesterday })
  const moment = littleMoment({
    completed_today,
    showedUpYesterday,
    didRecoverToday: recoveredToday(historyEvents ?? []),
  })
  const didRecoverToday = recoveredToday(historyEvents ?? [])
  const selectedState = selectedDay
    ? (selectedDay.isToday ? 'today' : selectedDay.recovered ? 'recovered' : selectedDay.showedUp ? 'completed' : 'missed')
    : ''
  // Selecting a day gives the companion a small, meaningful visual response
  // without changing any persisted plant data or mood calculation.
  const displayMood = selectedState === 'missed'
    ? { ...mood, id: 'NEEDS_CARE' }
    : selectedState === 'recovered'
      ? { ...mood, id: 'RETURNING' }
      : selectedState === 'completed' || selectedState === 'today'
        ? { ...mood, id: 'HAPPY' }
        : mood

  // New-user state: no meaningful history → seed/sprout visual, HAPPY
  // face, welcome message. Never the slow-day copy, and never a flash of
  // it: while history is still loading for a possibly-new account, hold
  // the same static seed frame the intro starts from.
  const historyLoaded = historyEvents !== null
  const possiblyNew =
    !plantData.completed_today && Number(plantData.growth_days ?? 0) === 0
  const confirmedNew =
    historyLoaded &&
    !introSeen &&
    isNewUser({
      historyEvents,
      growthDays: plantData.growth_days ?? 0,
      completedToday: plantData.completed_today,
    })
  const newUserActive = (!historyLoaded && !introSeen && possiblyNew) || confirmedNew
  const introSprouted = introPhase === 'sprout' || introPhase === 'done'
  const displayStage = resolveDisplayStage({
    isNewUser: newUserActive,
    introSprouted,
    backendStage: stage,
  })
  const effectiveMood =
    newUserActive && !selectedDay ? { ...displayMood, id: 'HAPPY' } : displayMood
  moodIdRef.current = effectiveMood.id
  // A new user's plant is always fresh and healthy on screen: no droop,
  // no wilt, no desaturation, regardless of the backend vitality value.
  const displayVitality = newUserActive ? 'healthy' : vitality

  // Add recovered flag to strip days for interaction messages
  const enrichedStrip = strip.map(day => ({
    ...day,
    recovered: historyEvents?.some(
      e => e.event_type === 'recovered' && dayKeyInZone(e.timestamp) === day.key
    ) ?? false,
  }))

  // Helper for day key (mirrors plantCompanion.mjs)
  function dayKeyInZone(value, timeZone = "Asia/Kolkata") {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone, year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(new Date(value))
    const get = (type) => parts.find((part) => part.type === type).value
    return `${get("year")}-${get("month")}-${get("day")}`
  }

  return (
    <div className="plant-page plant-companion-page">
      <header className="plant-page__header">
        <h1 className="plant-page__title">My Plant</h1>
        <p className="plant-page__standfirst">
          Your little companion that grows with you.
        </p>
        <span className="plant-page__sparkle" aria-hidden="true">✦</span>
      </header>

      {/* ---- Living companion: one centered column. The plant leads and
           the journey, moment, and growth notes support it. ---- */}
      <div className="plant-companion-flow">
        {/* ---- Central hero: plant + speech ---- */}
        <section className={[
          'plant-stage',
          sceneReacting || petted ? 'plant-stage--reacting' : '',
          newUserActive && introPhase !== 'idle' && introPhase !== 'done'
            ? `plant-stage--intro-${introPhase}`
            : '',
        ].filter(Boolean).join(' ')} aria-label="Plant visual">
          <div className="plant-world" aria-hidden="true">
            <svg className="plant-world__silhouettes" viewBox="0 0 640 200" focusable="false">
              <g className="plant-world__frond plant-world__frond--left">
                <path d="M40 190 Q70 120 52 60 Q86 116 74 190 Z" />
                <path d="M74 190 Q96 140 88 96 Q110 142 104 190 Z" />
              </g>
              <g className="plant-world__frond plant-world__frond--right">
                <path d="M600 190 Q570 120 588 60 Q554 116 566 190 Z" />
                <path d="M566 190 Q544 140 552 96 Q530 142 536 190 Z" />
              </g>
              <g className="plant-world__grass">
                <path d="M228 196 Q236 165 242 196 Q248 157 254 196 Q262 170 268 196 Z" />
                <path d="M370 196 Q378 170 384 196 Q392 157 398 196 Q406 166 412 196 Z" />
              </g>
            </svg>
            <span className="plant-world__ground" />
            <span className="plant-world__leaf plant-world__leaf--1" />
            <span className="plant-world__leaf plant-world__leaf--2" />
            <span className="plant-world__leaf plant-world__leaf--3" />
            <span className="plant-world__mote plant-world__mote--1" />
            <span className="plant-world__mote plant-world__mote--2" />
            <span className="plant-world__mote plant-world__mote--3" />
            <span className="plant-world__mote plant-world__mote--4" />
            <span className="plant-world__spark plant-world__spark--1">✦</span>
            <span className="plant-world__spark plant-world__spark--2">✦</span>
          </div>
          <button
            ref={visualRef}
            type="button"
            className={[
              'plant-visual',
              `plant-visual--${displayStage}`,
              `plant-visual--vitality-${displayVitality}`,
              `plant-visual--mood-${effectiveMood.id.toLowerCase()}`,
              petted ? 'plant-visual--petted' : '',
              effectiveMood.id === 'RETURNING' ? 'plant-visual--perked' : '',
              selectedState ? `plant-visual--day-${selectedState}` : '',
              newUserActive && introPhase !== 'idle' && introPhase !== 'done'
                ? `plant-visual--intro-${introPhase}`
                : '',
            ].filter(Boolean).join(' ')}
            onClick={() => { pet(); reactToScene() }}
            aria-label="My plant companion. Press to say hello."
          >
            <PlantSvg stage={displayStage} vitality={displayVitality} animating={animating} mood={effectiveMood.id} faceRef={faceRef} blinking={blinking} bloomStage={bloomStage} />
          </button>

          {/* Plant speech bubble - replaces separate "Little Moment" section */}
          <PlantSpeech
            mood={effectiveMood}
            selectedDay={selectedDay}
            completedToday={completed_today}
            recoveredToday={didRecoverToday}
            defaultMessage={newUserActive && !selectedDay ? NEW_USER_WELCOME : moment}
          />

        </section>

        {/* ---- Interactive Journey - replaces static "Your Journey" section ---- */}
        <section className="plant-journey" aria-label="Explore this week with your plant">
          <h2 className="plant-journey__heading">A little week together</h2>
          <div className="plant-journey__track">
            {enrichedStrip.map((day) => (
              <JourneyDay
                key={day.key}
                day={day}
                isSelected={selectedDay?.key === day.key}
                onSelect={selectDay}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
