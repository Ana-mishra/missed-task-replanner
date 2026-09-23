import AvailableTimeCard from "./AvailableTimeCard.jsx";
import TaskCard from "./TaskCard.jsx";
import { formatDuration } from "../utils/duration.mjs";

// Plan My Day: "How do I want today's work to be scheduled?"
// Rendering only — all planning state and handlers live in App.jsx (single
// source of truth). No fetches, no duplicated state, no planning logic here.
// Visual language follows the Git-era product: task cards with inline
// actions, roadmap numbering, overload verdict banner.
export default function PlanPage({
  tasks,
  availableMinutes,
  badDayMode,
  onBadDayModeChange,
  onSaveAvailableMinutes,
  planning,
  hasPlanned,
  planIsOverloaded,
  unscheduledMinutes,
  badDayProtectedCount,
  badDayCapacityMinutes,
  scheduleRefreshReason,
  onPlanDay,
  onHidePlan,
  onGoToToday,
  onEditTask,
  onCompleteTask,
  onDeleteTask,
}) {
  const incomplete = tasks.filter(
    (task) => !task.completed && task.status !== "completed",
  );
  const scheduled = incomplete
    .filter((task) => task.scheduled_start && task.scheduled_end)
    .sort((a, b) => new Date(a.scheduled_start) - new Date(b.scheduled_start));
  const unscheduledCount = incomplete.filter(
    (task) => !task.scheduled_start || !task.scheduled_end,
  ).length;
  const plannedMinutes = scheduled.reduce(
    (total, task) => total + task.duration_minutes,
    0,
  );
  const hasNothingToPlan = incomplete.length === 0;

  return (
    <div className="plan-page">
      <header className="plan-head">
        <h1>
          Plan My Day <span aria-hidden="true">◷</span>
        </h1>
        <p>Build a realistic plan around the time you have.</p>
      </header>

      <AvailableTimeCard
        availableMinutes={availableMinutes}
        onSave={onSaveAvailableMinutes}
      />
      {!hasNothingToPlan && (
        <div className="task-list-actions">
          <button
            className={`button button--quiet plan-bad-day-toggle${badDayMode ? " plan-bad-day-toggle--active" : ""}`}
            type="button"
            aria-pressed={badDayMode}
            onClick={() => onBadDayModeChange(!badDayMode)}
          >
            {badDayMode ? "Bad Day Mode on" : "Having a low-energy day?"}
          </button>
          <button
            className="button button--primary"
            type="button"
            onClick={onPlanDay}
            disabled={planning}
          >
            {planning ? "Planning…" : hasPlanned ? "Re-plan my day" : "Plan my day"}
          </button>
          {hasPlanned && (
            <button
              className="button button--quiet"
              type="button"
              onClick={onHidePlan}
            >
              Hide plan
            </button>
          )}
        </div>
      )}

      {badDayMode && !hasNothingToPlan && (
        <p className="plan-bad-day-note">
          Your plan protects {badDayProtectedCount} deadline-critical task{badDayProtectedCount !== 1 ? 's' : ''}
          {badDayCapacityMinutes > 0
            ? ` and favors lower-energy work within ${formatDuration(badDayCapacityMinutes)} of preferred capacity.`
            : ", favoring lower-energy work where possible."}
        </p>
      )}

      {!badDayMode && !hasNothingToPlan && scheduleRefreshReason && (
        <p className="plan-bad-day-note">
          {scheduleRefreshReason === "Schedule changed after adding a task"
            ? "Plan updated after adding a new task."
            : scheduleRefreshReason === "Schedule changed after editing a task"
              ? "Plan updated after editing a task."
              : "Plan was reshaped."}
        </p>
      )}

      {hasPlanned && (
        <p className="plan-capacity">
          {scheduled.length} scheduled · {formatDuration(plannedMinutes)} planned
          of {formatDuration(availableMinutes)} available
          {planIsOverloaded && unscheduledMinutes > 0
            ? badDayMode
              ? ` · ${formatDuration(unscheduledMinutes)} set aside for later`
              : ` · ${formatDuration(unscheduledMinutes)} won't fit`
            : unscheduledCount > 0
              ? ` · ${unscheduledCount} unscheduled`
              : ""}
          {badDayMode && badDayProtectedCount > 0 && badDayCapacityMinutes > 0 && badDayProtectedCount * 60 > badDayCapacityMinutes
            ? ` · ${formatDuration(badDayProtectedCount * 60)} of deadline-critical work was protected beyond your preferred Bad Day capacity`
            : ""}
        </p>
      )}

      {hasPlanned && planIsOverloaded && (
        <section className="overload-notice" aria-labelledby="overload-heading">
          {badDayMode ? (
            <>
              <div className="overload-notice__copy">
                <p className="overload-notice__eyebrow">Your plan is intentionally lighter</p>
                <h3 id="overload-heading">
                  Protecting your energy today
                </h3>
                <p className="overload-notice__support">
                  Bad Day Mode is prioritizing deadline-critical work and
                  leaving lower-priority tasks for later.
                </p>
              </div>
              <div
                className="overload-notice__limits"
                aria-label="Daily workload limits"
              >
                <span className="overload-limit">
                  {formatDuration(availableMinutes)} available
                </span>
                <span className="overload-limit">
                  {formatDuration(plannedMinutes)} of tasks
                </span>
                {badDayCapacityMinutes > 0 && (
                  <span className="overload-limit">
                    {formatDuration(badDayCapacityMinutes)} preferred capacity
                  </span>
                )}
                {badDayProtectedCount > 0 && (
                  <span className="overload-limit">
                    {badDayProtectedCount} deadline-critical task{badDayProtectedCount !== 1 ? "s" : ""} protected
                  </span>
                )}
              </div>
            </>
          ) : (
            <>
              <div className="overload-notice__copy">
                <p className="overload-notice__eyebrow">Your day looks full</p>
                <h3 id="overload-heading">
                  More needs attention than fits today.
                </h3>
                <p className="overload-notice__support">
                  Plan My Day will prioritize what matters most and leave the rest
                  for later.
                </p>
              </div>
              <div
                className="overload-notice__limits"
                aria-label="Daily workload limits"
              >
                <span className="overload-limit">
                  {formatDuration(availableMinutes)} available
                </span>
                <span className="overload-limit">
                  {formatDuration(plannedMinutes)} of tasks
                </span>
                <span className="overload-limit overload-limit--exceeded">
                  {formatDuration(unscheduledMinutes)} over capacity
                </span>
              </div>
            </>
          )}
        </section>
      )}

      <section aria-label="Today's plan">
        <div className="section-heading">
          <h2>Today's plan</h2>
        </div>
        {scheduled.length === 0 ? (
          incomplete.length === 0 ? (
            <div className="plan-empty plan-empty--split">
              <div className="plan-empty__art">
                <svg width="260" height="168" viewBox="0 0 260 168" aria-hidden="true">
                  <path
                    d="M130 12c26-10 62-4 78 14s30 8 34 30-8 44-30 52-30 30-62 26-44 20-70 10-52 2-58-22-22-26-14-48 4-34 14-44 22-12 44-18z"
                    fill="#eaf2e7"
                  />
                  <ellipse cx="130" cy="152" rx="72" ry="9" fill="#e3ecdf" />
                  <g transform="rotate(-7 108 88)">
                    <rect x="66" y="38" width="84" height="100" rx="7" fill="#fffefb" stroke="#4f7d63" strokeWidth="2.5" />
                    <circle cx="84" cy="64" r="7" fill="none" stroke="#4f7d63" strokeWidth="2" />
                    <line x1="98" y1="64" x2="130" y2="64" stroke="#4f7d63" strokeWidth="2.5" strokeLinecap="round" />
                    <circle cx="84" cy="90" r="7" fill="none" stroke="#4f7d63" strokeWidth="2" />
                    <line x1="98" y1="90" x2="134" y2="90" stroke="#4f7d63" strokeWidth="2.5" strokeLinecap="round" />
                    <circle cx="84" cy="116" r="7" fill="none" stroke="#4f7d63" strokeWidth="2" />
                    <line x1="98" y1="116" x2="126" y2="116" stroke="#4f7d63" strokeWidth="2.5" strokeLinecap="round" />
                  </g>
                  <g stroke="#285c4d" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="128" y1="10" x2="128" y2="24" />
                    <line x1="110" y1="16" x2="115" y2="28" />
                    <line x1="146" y1="16" x2="141" y2="28" />
                  </g>
                  <g>
                    <path d="M172 148C172 118 178 96 196 78c4 22-2 48-20 66" fill="#9dbd76" />
                    <path d="M172 148c-2-24 2-44 14-58 6 20 0 42-10 56" fill="#6ca578" />
                    <path d="M172 148c8-18 22-32 40-36 0 18-14 32-36 38" fill="#8fb584" />
                    <path d="M172 148l-1-40" stroke="#3f6b52" strokeWidth="2" strokeLinecap="round" />
                  </g>
                </svg>
                <p className="plan-empty__caption">A more intentional day<br />starts with your tasks.</p>
              </div>
              <div className="plan-empty__copy">
                <p className="plan-empty__eyebrow">Nothing to plan yet</p>
                <p className="plan-empty__title">Add a few tasks from Today first.</p>
                <p className="plan-empty__body">
                  Planora will use those tasks and the time you have
                  to build a realistic plan for your day.
                </p>
                <button
                  className="button button--primary"
                  type="button"
                  onClick={onGoToToday}
                >
                  Go to Today →
                </button>
              </div>
            </div>
          ) : (
            <div className="plan-empty plan-empty--split">
              <div className="plan-empty__art">
                <svg width="260" height="168" viewBox="0 0 260 168" aria-hidden="true">
                  <path
                    d="M130 12c26-10 62-4 78 14s30 8 34 30-8 44-30 52-30 30-62 26-44 20-70 10-52 2-58-22-22-26-14-48 4-34 14-44 22-12 44-18z"
                    fill="#eaf2e7"
                  />
                  <ellipse cx="130" cy="152" rx="72" ry="9" fill="#e3ecdf" />
                  <g transform="rotate(-7 108 88)">
                    <rect x="66" y="38" width="84" height="100" rx="7" fill="#fffefb" stroke="#4f7d63" strokeWidth="2.5" />
                    <circle cx="84" cy="64" r="7" fill="none" stroke="#4f7d63" strokeWidth="2" />
                    <line x1="98" y1="64" x2="130" y2="64" stroke="#4f7d63" strokeWidth="2.5" strokeLinecap="round" />
                    <circle cx="84" cy="90" r="7" fill="none" stroke="#4f7d63" strokeWidth="2" />
                    <line x1="98" y1="90" x2="134" y2="90" stroke="#4f7d63" strokeWidth="2.5" strokeLinecap="round" />
                    <circle cx="84" cy="116" r="7" fill="none" stroke="#4f7d63" strokeWidth="2" />
                    <line x1="98" y1="116" x2="126" y2="116" stroke="#4f7d63" strokeWidth="2.5" strokeLinecap="round" />
                  </g>
                  <g stroke="#285c4d" strokeWidth="2.5" strokeLinecap="round">
                    <line x1="128" y1="10" x2="128" y2="24" />
                    <line x1="110" y1="16" x2="115" y2="28" />
                    <line x1="146" y1="16" x2="141" y2="28" />
                  </g>
                  <g>
                    <path d="M172 148C172 118 178 96 196 78c4 22-2 48-20 66" fill="#9dbd76" />
                    <path d="M172 148c-2-24 2-44 14-58 6 20 0 42-10 56" fill="#6ca578" />
                    <path d="M172 148c8-18 22-32 40-36 0 18-14 32-36 38" fill="#8fb584" />
                    <path d="M172 148l-1-40" stroke="#3f6b52" strokeWidth="2" strokeLinecap="round" />
                  </g>
                </svg>
                <p className="plan-empty__caption">A plan for today, a calmer tomorrow.</p>
              </div>
              <div className="plan-empty__copy">
                <p className="plan-empty__eyebrow">READY TO PLAN?</p>
                <p className="plan-empty__title">You have tasks for today!</p>
                <p className="plan-empty__body">Create your plan to see how they fit into your day.</p>
                <div className="plan-benefits">
                  <div className="plan-benefit">
                    <p className="plan-benefit__title">Smart scheduling</p>
                    <p className="plan-benefit__body">We'll organize your tasks based on time, priority and your energy.</p>
                  </div>
                  <div className="plan-benefit">
                    <p className="plan-benefit__title">Realistic plan</p>
                    <p className="plan-benefit__body">Get a plan that fits your available time.</p>
                  </div>
                  <div className="plan-benefit">
                    <p className="plan-benefit__title">Less stress</p>
                    <p className="plan-benefit__body">Know exactly what to do next, without feeling overwhelmed.</p>
                  </div>
                </div>
                <button
                  className="button button--primary"
                  type="button"
                  onClick={onPlanDay}
                  disabled={planning}
                >
                  {planning ? "Planning…" : "Plan my day →"}
                </button>
                <p className="plan-tip">Planning takes just a few seconds and helps you stay on track all day.</p>
              </div>
            </div>
          )
        ) : (
          <ol className="plan-roadmap">
            {scheduled.map((task) => (
              <li className="plan-roadmap__item" key={task.id}>
                <TaskCard
                  task={task}
                  showSlot
                  reason={task.reason || undefined}
                  onEdit={() => onEditTask(task)}
                  onComplete={() => onCompleteTask(task)}
                  onDelete={() => onDeleteTask(task)}
                />
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
