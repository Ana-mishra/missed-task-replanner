import { useEffect, useRef, useState } from 'react'

// ---------------------------------------------------------------------------
// Stage display configuration — mirrors backend thresholds but is only used
// for display labels and progress copy, never for re-computing growth_days.
// ---------------------------------------------------------------------------
const STAGE_LABELS = {
  seed:        'Seed',
  sprout:      'Sprout',
  young_plant: 'Young Plant',
  growing:     'Growing Plant',
  flourishing: 'Flourishing Plant',
  mature:      'Mature Plant',
}

const STAGE_NEXT_LABELS = {
  seed:        'Sprout',
  sprout:      'Young Plant',
  young_plant: 'Growing Plant',
  growing:     'Flourishing Plant',
  flourishing: 'Mature Plant',
  mature:      null,
}

// ---------------------------------------------------------------------------
// Vitality copy — neutral, warm, never guilt-based.
// ---------------------------------------------------------------------------
function vitalityCopy(vitality, completedToday) {
  if (completedToday) return 'Your plant is thriving today.'
  switch (vitality) {
    case 'healthy':    return 'Your plant is doing well.'
    case 'waiting':    return 'A little care today would delight your plant.'
    case 'droopy':     return 'Your plant is waiting for you.'
    case 'very_droopy': return 'Your plant misses you — it\'s still here.'
    default:           return 'Your plant is here whenever you are.'
  }
}

// ---------------------------------------------------------------------------
// PlantSvg — inline SVG plant in a ceramic pot.
// Vitality drives leaf droop via CSS class. Care animation fires via
// the 'plant-visual--caring' class added on first-completion-of-day.
// ---------------------------------------------------------------------------
function PlantSvg({ stage, vitality, animating }) {
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
      {/* Pot highlight stripe */}
      <path
        className="plant-pot__highlight"
        d="M75 184 L125 184 L123 190 L77 190 Z"
        opacity="0.18"
      />
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
// Progress bar toward next stage
// ---------------------------------------------------------------------------
function StageProgress({ stage, stageProgress }) {
  const nextLabel = STAGE_NEXT_LABELS[stage]
  if (stage === 'mature') {
    return (
      <p className="plant-progress__terminal">
        Your plant has reached its fullest form.
      </p>
    )
  }
  return (
    <div className="plant-progress">
      <div className="plant-progress__bar-wrap" aria-label={`${Math.round(stageProgress)}% toward ${nextLabel}`}>
        <div
          className="plant-progress__bar-fill"
          style={{ width: `${Math.min(100, stageProgress)}%` }}
        />
      </div>
      <p className="plant-progress__label">
        {Math.round(stageProgress)}% toward <span>{nextLabel}</span>
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// MyPlantPage — main export
// ---------------------------------------------------------------------------
export default function MyPlantPage({ plantData, plantLoading, plantError }) {
  // Track the previous grew_today so we can detect the first-of-day event.
  const prevGrewTodayRef = useRef(plantData?.grew_today ?? false)
  const [animating, setAnimating] = useState(false)

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
    stage_progress,
    current_streak_days,
    days_since_last_growth,
    completed_today,
    grew_today,
    vitality,
  } = plantData

  const stageLabel = STAGE_LABELS[stage] ?? stage
  const copy = vitalityCopy(vitality, completed_today)

  return (
    <div className="plant-page">
      <header className="plant-page__header">
        <p className="plant-page__eyebrow">MY PLANT</p>
        <h1 className="plant-page__title">My Plant</h1>
        <p className="plant-page__standfirst">
          Your plant grows with the days you show up.
        </p>
      </header>

      {/* ---- Central visual (hero) ---- */}
      <section className="plant-stage" aria-label="Plant visual">
        <div className={`plant-visual plant-visual--${stage} plant-visual--vitality-${vitality}`}>
          <PlantSvg stage={stage} vitality={vitality} animating={animating} />
        </div>

        {/* Stage badge */}
        <p className="plant-stage__label">{stageLabel}</p>

        {/* Vitality copy */}
        <p className={`plant-vitality-copy plant-vitality-copy--${vitality}`}>
          {copy}
        </p>
      </section>

      {/* ---- Growth Days (primary metric) + Progress ---- */}
      <section className="plant-metrics" aria-label="Growth metrics">
        <div className="plant-metric plant-metric--primary">
          <span className="plant-metric__value">{growth_days}</span>
          <span className="plant-metric__label">GROWTH DAYS</span>
        </div>

        {/* Stage progress directly beneath Growth Days */}
        <div className="plant-stage-progress" aria-label="Stage progress">
          <StageProgress stage={stage} stageProgress={stage_progress} />
        </div>

        {/* Days in a row — quiet secondary treatment */}
        {current_streak_days > 0 && (
          <p className="plant-streak-quiet">
            {current_streak_days} day{current_streak_days === 1 ? '' : 's'} in a row
          </p>
        )}
      </section>
    </div>
  )
}
