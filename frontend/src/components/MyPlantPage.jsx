import { useEffect, useRef, useState } from 'react'

import { getTaskHistory } from '../services/api.js'
import { IconLeaf } from './icons.jsx'
import {
  companionMood,
  eyeTrackingOffset,
  growthTimeline,
  journeyLine,
  littleMoment,
  recentDaysStrip,
  recoveredToday,
} from '../utils/plantCompanion.mjs'

// Moods with open pupils that may track the cursor. Closed-eye moods
// (HAPPY arcs, NEEDS_CARE lines) have no track groups by construction.
const TRACKED_MOODS = new Set(['GROWING', 'RETURNING'])

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
    let raf = 0
    let target = { dx: 0, dy: 0 }
    let current = { dx: 0, dy: 0 }
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
    }
    // Cursor left the viewport: glide back to neutral.
    const onLeave = () => { target = { dx: 0, dy: 0 } }
    const tick = () => {
      const goal = TRACKED_MOODS.has(moodIdRef.current) ? target : { dx: 0, dy: 0 }
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
// YourJourney — the recent 7 IST days as one connected sequence, plus a
// single contextual line. Lit leaves mark genuine growth days; missed days
// stay quiet and muted. No scores, no streaks.
// ---------------------------------------------------------------------------
function YourJourney({ strip }) {
  return (
    <section className="plant-journey" aria-label="Your journey">
      <h2 className="plant-journey__heading">Your journey</h2>
      <ol className="plant-journey__track">
        {strip.map((day) => (
          <li
            key={day.key}
            className={[
              'plant-journey__day',
              day.showedUp ? 'plant-journey__day--lit' : 'plant-journey__day--muted',
              day.isToday ? 'plant-journey__day--today' : '',
            ].filter(Boolean).join(' ')}
            aria-label={`${day.label}${day.showedUp ? ', showed up' : ''}${day.isToday ? ', today' : ''}`}
            aria-current={day.isToday ? 'date' : undefined}
          >
            <IconLeaf width={20} height={20} />
            <span className="plant-journey__day-label">{day.label}</span>
          </li>
        ))}
      </ol>
      <p className="plant-journey__line">{journeyLine(strip)}</p>
    </section>
  )
}

// ---------------------------------------------------------------------------
// LittleMoment — one deterministic note from the companion, derived from
// already-available data. A note, never a notification or a report.
// ---------------------------------------------------------------------------
function LittleMoment({ note }) {
  return (
    <section className="plant-moment" aria-label="A little moment">
      <h2 className="plant-moment__heading">A little moment</h2>
      <p className="plant-moment__note">{note}</p>
    </section>
  )
}

// ---------------------------------------------------------------------------
// GrowthJourney — seed → sprout → growing → today as pure visual story.
// Position comes from the backend stage; nothing numeric is shown.
// ---------------------------------------------------------------------------
function GrowthJourney({ stage, completedToday }) {
  const nodes = growthTimeline(stage, completedToday)
  return (
    <section className="plant-growth" aria-label="Your plant's journey">
      <h2 className="plant-growth__heading">Your plant&apos;s journey</h2>
      <ol className="plant-growth__track">
        {nodes.map((node) => (
          <li
            key={node.id}
            className={`plant-growth__node plant-growth__node--${node.state}`}
            aria-label={`${node.label}${node.state === 'done' ? ', reached' : node.state === 'current' ? ', current' : ''}`}
            aria-current={node.id === 'today' ? 'date' : undefined}
          >
            <span className="plant-growth__dot" aria-hidden="true">
              {(node.state === 'done' || node.state === 'current') && (
                <IconLeaf width={13} height={13} />
              )}
            </span>
            <span className="plant-growth__label">{node.label}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}

// ---------------------------------------------------------------------------
// PlantFace — dedicated expression component living on the pot body.
// All four mood variants stay mounted; CSS crossfades the active one via
// data-mood so expression changes transition gently with no JS state
// machine. Shapes are simple SVG strokes in the existing green family.
// ---------------------------------------------------------------------------
function PlantFace({ mood, faceRef }) {
  return (
    <g className="plant-face" data-mood={mood} ref={faceRef}>
      {/* HAPPY — gentle curved eyes, small smile, soft blush */}
      <g className="plant-face__variant" data-face="HAPPY">
        <path className="plant-face__feature" d="M83 192 Q88 187.5 93 192" />
        <path className="plant-face__feature" d="M107 192 Q112 187.5 117 192" />
        <path className="plant-face__feature" d="M93 200 Q100 204.5 107 200" />
        <ellipse className="plant-face__blush" cx="79" cy="198" rx="3.5" ry="2.2" />
        <ellipse className="plant-face__blush" cx="121" cy="198" rx="3.5" ry="2.2" />
      </g>
      {/* GROWING — bright open eyes, curious smile */}
      <g className="plant-face__variant" data-face="GROWING">
        <g className="plant-face__track">
          <g className="plant-face__blink">
            <circle className="plant-face__eye-dot" cx="88" cy="191" r="2.7" />
            <circle className="plant-face__eye-dot" cx="112" cy="191" r="2.7" />
          </g>
        </g>
        <path className="plant-face__feature" d="M92 199 Q100 205.5 108 199" />
      </g>
      {/* NEEDS_CARE — sleepy eyes, small neutral mouth. Tired, never broken. */}
      <g className="plant-face__variant" data-face="NEEDS_CARE">
        <path className="plant-face__feature" d="M83 192 L93 192" />
        <path className="plant-face__feature" d="M107 192 L117 192" />
        <path className="plant-face__feature" d="M95 200.5 Q100 202 105 200.5" />
      </g>
      {/* RETURNING — raised happy brows, bright eyes, open smile: welcome back */}
      <g className="plant-face__variant" data-face="RETURNING">
        <path className="plant-face__brow" d="M82 184 Q88 180.5 94 184" />
        <path className="plant-face__brow" d="M106 184 Q112 180.5 118 184" />
        <g className="plant-face__track">
          <g className="plant-face__blink">
            <circle className="plant-face__eye-dot" cx="88" cy="191" r="2.9" />
            <circle className="plant-face__eye-dot" cx="112" cy="191" r="2.9" />
          </g>
        </g>
        <path className="plant-face__feature" d="M91 198 Q100 206.5 109 198" />
        <ellipse className="plant-face__blush" cx="79" cy="198" rx="3.5" ry="2.2" />
        <ellipse className="plant-face__blush" cx="121" cy="198" rx="3.5" ry="2.2" />
      </g>
    </g>
  )
}

// ---------------------------------------------------------------------------
// PlantSvg — inline SVG plant in a ceramic pot.
// Vitality drives leaf droop via CSS class. Care animation fires via
// the 'plant-visual--caring' class added on first-completion-of-day.
// ---------------------------------------------------------------------------
function PlantSvg({ stage, vitality, animating, mood, faceRef }) {
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
      <PlantFace mood={mood} faceRef={faceRef} />
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
    growth_days,
    stage,
    completed_today,
    vitality,
  } = plantData

  const strip = recentDaysStrip(historyEvents ?? [])
  const showedUpYesterday = historyEvents === null
    ? undefined
    : (strip.length >= 2 ? strip[strip.length - 2].showedUp : undefined)

  const mood = companionMood({ completed_today, vitality, showedUpYesterday })
  moodIdRef.current = mood.id
  const moment = littleMoment({
    completed_today,
    showedUpYesterday,
    didRecoverToday: recoveredToday(historyEvents ?? []),
  })

  return (
    <div className="plant-page">
      <header className="plant-page__header">
        <p className="plant-page__eyebrow">MY PLANT</p>
        <h1 className="plant-page__title">My Plant</h1>
        <p className="plant-page__standfirst">
          A little companion that grows with you.
        </p>
      </header>

      {/* ---- Living companion composition: environment + journal ---- */}
      <div className="plant-companion-layout">
        {/* ---- Central hero ---- */}
        <section className="plant-stage" aria-label="Plant visual">
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
          </svg>
          <span className="plant-world__mote plant-world__mote--1" />
          <span className="plant-world__mote plant-world__mote--2" />
          <span className="plant-world__mote plant-world__mote--3" />
        </div>
        <div className={`plant-visual plant-visual--${stage} plant-visual--vitality-${vitality}`}>
          <PlantSvg stage={stage} vitality={vitality} animating={animating} mood={mood.id} faceRef={faceRef} />
        </div>

        <p className={`plant-companion-copy plant-companion-copy--${mood.id.toLowerCase()}`}>
          {mood.message}
        </p>
        <p className="plant-consistency">
          {growth_days > 0
            ? `Your plant has grown with you for ${growth_days} day${growth_days === 1 ? '' : 's'}.`
            : 'Your first day of showing up will plant the seed.'}
        </p>
        </section>

        <aside className="plant-journal" aria-label="Companion journal">
          <YourJourney strip={strip} />
          <LittleMoment note={moment} />
          <GrowthJourney stage={stage} completedToday={completed_today} />
        </aside>
      </div>
    </div>
  )
}
