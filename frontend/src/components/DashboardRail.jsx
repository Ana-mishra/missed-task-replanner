import { useState } from 'react'
import { formatDuration } from '../utils/duration.mjs'

function DashboardRail({
  recommendation,
  onRecommend,
  plannedMinutes,
  availableMinutes,
  plannedCount,
  progress,
  reflection,
}) {
  const [isRecommendationDismissed, setIsRecommendationDismissed] = useState(false)
  const usage = availableMinutes > 0
    ? Math.min(100, Math.round((plannedMinutes / availableMinutes) * 100))
    : 0

  return (
    <aside className="dashboard-rail" aria-label="Today at a glance">
        <section className="recommendation-card" aria-labelledby="recommendation-heading">
        
          <p className="rail-eyebrow">A gentle next step</p>
          <h3 id="recommendation-heading">What should I do now?</h3>
          {!recommendation || isRecommendationDismissed ? (
  <>
    <p>Let Planora choose the clearest next task for you.</p>

    <button
      className="button button--primary"
      type="button"
      onClick={() => {
        setIsRecommendationDismissed(false)
        onRecommend()
      }}
    >
      Help me choose
    </button>
  </>
) : recommendation.recommended_task ? (
  <div className="recommendation-card__task">
    <span className="recommendation-card__icon" aria-hidden="true">✦</span>

    <div>
      <h4>{recommendation.recommended_task.title}</h4>
      <p>
        {formatDuration(recommendation.recommended_task.duration_minutes)} ·{" "}
        {recommendation.recommended_task.priority} priority
      </p>
      <p className="recommendation-card__reason">
        {recommendation.reason}
      </p>

      <button
        className="button button--secondary"
        type="button"
        onClick={() => setIsRecommendationDismissed(true)}
      >
        Close
      </button>
    </div>
  </div>
          ) : <p>{recommendation.reason}</p>}
        </section>
      

      <section className="rail-card capacity-status" aria-labelledby="capacity-status-heading">
        <div className="rail-card__header">
          <h3 id="capacity-status-heading">Today’s capacity</h3>
          <span>{formatDuration(plannedMinutes)} / {formatDuration(availableMinutes)}</span>
        </div>
        <div className="capacity-status__track" aria-label={`${usage}% of available time planned`}>
          <span style={{ width: `${usage}%` }} />
        </div>
        <p>{plannedCount} {plannedCount === 1 ? 'task' : 'tasks'} in today’s plan</p>
      </section>

      <div className="rail-pair">
        <section className="rail-card plant-card" aria-labelledby="plant-heading">
          <p className="rail-eyebrow">Your plant</p>
          <div className="plant-card__content">
            <span className="plant-card__illustration" aria-hidden="true">🌱</span>
            <div>
              <h3 id="plant-heading">Level {progress?.progress_level ?? 1}</h3>
              <p>{progress ? `${progress.completed_tasks} completed tasks` : 'Your progress will grow here.'}</p>
            </div>
          </div>
          <div className="plant-card__progress"><span style={{ width: `${progress?.progress_percent ?? 0}%` }} /></div>
        </section>

        <section className="rail-card reflection-card" aria-labelledby="reflection-heading">
          <p className="rail-eyebrow">Reflection</p>
          <h3 id="reflection-heading">This week</h3>
          {reflection ? <p>{reflection.tasks_completed} completed · {reflection.tasks_recovered} recovered</p> : <p>Your weekly reflection will appear here.</p>}
          <span className="reflection-card__note">A gentle record of your progress.</span>
        </section>
      </div>
    </aside>
  )
}

export default DashboardRail
