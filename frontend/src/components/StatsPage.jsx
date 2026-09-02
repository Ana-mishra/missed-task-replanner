import { useEffect, useMemo, useRef, useState } from "react";
import {
  getEstimation,
  getPersonalization,
  getProgress,
  getWeeklyReflection,
} from "../services/api.js";
import { formatDuration } from "../utils/duration.mjs";

function percent(value) {
  return `${Math.round(value || 0)}%`;
}

function periodComparisonLabel(period) {
  if (period === "week") return "last week";
  if (period === "month") return "last month";
  return null;
}

function changeText(current, previous, label, suffix = "") {
  if (previous === null || previous === undefined) return "All-time progress";
  const change = current - previous;
  if (change === 0) return `No change from ${label}`;
  const direction = change > 0 ? "↑" : "↓";
  return `${direction} ${Math.round(Math.abs(change))}${suffix} from ${label}`;
}

function changeTone(current, previous) {
  if (previous === null || previous === undefined || current === previous)
    return "neutral";
  return current > previous ? "positive" : "negative";
}

function weekday(value) {
  if (!value) return "No clear pattern yet";
  return new Date(`${value}T00:00:00`).toLocaleDateString([], {
    weekday: "long",
  });
}

const PERIOD_LABELS = {
  week: "This Week",
  month: "This Month",
  all: "All Time",
};

function chartEntries(values, period) {
  const entries = Object.entries(values || {});
  if (period !== "month") return entries;
  const grouped = new Map();
  entries.forEach(([date, value]) => {
    const current = new Date(`${date}T00:00:00`);
    const mondayOffset = (current.getDay() + 6) % 7;
    current.setDate(current.getDate() - mondayOffset);
    const key = current.toISOString().slice(0, 10);
    grouped.set(key, (grouped.get(key) || 0) + value);
  });
  return [...grouped.entries()];
}

function chartLabel(date, period) {
  return new Date(`${date}T00:00:00`).toLocaleDateString(
    [],
    period === "week"
      ? { weekday: "short" }
      : { month: "short", day: "numeric" },
  );
}

function compactChartDuration(minutes) {
  const total = Math.max(0, Number(minutes) || 0);
  const hours = Math.floor(total / 60);
  const remaining = total % 60;
  if (!hours) return `${remaining}m`;
  if (!remaining) return `${hours}h`;
  return `${hours}h ${remaining}m`;
}

function chartScaleMaximum(maximum) {
  const scales = [120, 240, 480, 720, 960];
  return (
    scales.find((scale) => maximum <= scale) || Math.ceil(maximum / 240) * 240
  );
}

function SummaryCard({ icon, label, value, detail, tone, detailTone }) {
  return (
    <article
      className={`stats-target-summary-card stats-target-summary-card--${tone}`}
    >
      <span className="stats-target-summary-card__icon" aria-hidden="true">
        {icon}
      </span>
      <p>{label}</p>
      <strong>{value}</strong>
      <span
        className={
          detailTone
            ? `stats-target-summary-card__detail stats-target-summary-card__detail--${detailTone}`
            : "stats-target-summary-card__detail"
        }
      >
        {detail}
      </span>
    </article>
  );
}

function CompletionTrend({ dailyCompletedTasks, period }) {
  const entries = chartEntries(dailyCompletedTasks, period);
  const maximum = Math.max(1, ...entries.map(([, count]) => count));
  const midpoint = maximum > 1 ? Math.ceil(maximum / 2) : null;

  return (
    <div
      className="stats-target-trend-chart"
      aria-label="Tasks completed each day"
    >
      <div className="stats-target-trend-axis" aria-hidden="true">
        <span>{maximum}</span>
        {midpoint !== null && <span>{midpoint}</span>}
        <span>0</span>
      </div>
      <div className="stats-target-trend-plot">
        <div className="stats-target-trend-grid" aria-hidden="true">
          <span />
          <span />
          {midpoint !== null && <span />}
        </div>
        {entries.length === 0 ? (
          <p className="stats-target-empty">
            Complete tasks to see your weekly trend.
          </p>
        ) : (
          entries.map(([day, count]) => (
            <div className="stats-target-bar" key={day}>
              <strong>{count}</strong>
              <div className="stats-target-bar__track">
                <span style={{ height: `${(count / maximum) * 100}%` }} />
              </div>
              <small>{chartLabel(day, period)}</small>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function WorkComparison({ reflection, period }) {
  const [activeIndex, setActiveIndex] = useState(null);

  const plannedEntries = chartEntries(
    reflection?.daily_planned_minutes,
    period,
  );

  const actualEntries = chartEntries(reflection?.daily_actual_minutes, period);

  const dates = [
    ...new Set([
      ...plannedEntries.map(([date]) => date),
      ...actualEntries.map(([date]) => date),
    ]),
  ].sort();

  const plannedValues = Object.fromEntries(plannedEntries);
  const actualValues = Object.fromEntries(actualEntries);

  const planned = dates.map((date) => plannedValues[date] || 0);
  const actual = dates.map((date) => actualValues[date] || 0);

  const maximum = chartScaleMaximum(Math.max(1, ...planned, ...actual));

  const pointX = (index) =>
    dates.length > 1 ? 42 + (index * 236) / (dates.length - 1) : 160;

  const pointY = (value) => 130 - (value / maximum) * 95;

  const plannedPoints = planned
    .map((value, index) => `${pointX(index)},${pointY(value)}`)
    .join(" ");

  const actualPoints = actual
    .map((value, index) => `${pointX(index)},${pointY(value)}`)
    .join(" ");

  return (
    <div className="stats-target-work">
     <div className="stats-target-work__legend">
  <span>
    <i className="stats-target-dot stats-target-dot--planned" />
    Planned <small>(intended)</small>
  </span>

  <span>
    <i className="stats-target-dot stats-target-dot--actual" />
    Completed <small>(actual)</small>
  </span>
</div>

      

      <div
        className="stats-target-work-chart"
        aria-label="Planned time compared with completed time"
        onMouseLeave={() => setActiveIndex(null)}
      >
        <svg
          viewBox="0 0 320 170"
          role="img"
          aria-label="Planned time and completed time by day"
        >
          <g className="stats-target-work-chart__grid" aria-hidden="true">
            <line x1="36" y1="35" x2="300" y2="35" />
            <line x1="36" y1="82" x2="300" y2="82" />
            <line x1="36" y1="106" x2="300" y2="106" />
            <line x1="36" y1="130" x2="300" y2="130" />
          </g>

          {[maximum, maximum / 2, maximum / 4, 0].map((value, index) => (
            <text x="4" y={[39, 86, 110, 134][index]} key={value}>
              {compactChartDuration(value)}
            </text>
          ))}

          <polyline
            className="stats-target-work-chart__line stats-target-work-chart__line--planned"
            points={plannedPoints}
          />

          <polyline
            className="stats-target-work-chart__line stats-target-work-chart__line--actual"
            points={actualPoints}
          />

          {planned.map((value, index) => (
            <circle
              className="stats-target-work-chart__point"
              cx={pointX(index)}
              cy={pointY(value)}
              r="4"
              key={`planned-${dates[index]}`}
            />
          ))}

          {actual.map((value, index) => (
            <circle
              className="stats-target-work-chart__point stats-target-work-chart__point--actual"
              cx={pointX(index)}
              cy={pointY(value)}
              r="4"
              key={`actual-${dates[index]}`}
            />
          ))}

          {dates.map((date, index) => (
            <rect
              className="stats-target-work-chart__target"
              x={pointX(index) - (dates.length > 1 ? 16 : 35)}
              y="20"
              width={dates.length > 1 ? 32 : 70}
              height="120"
              key={`target-${date}`}
              tabIndex="0"
              role="button"
              aria-label={`${chartLabel(date, period)}: ${compactChartDuration(
                planned[index],
              )} planned and ${compactChartDuration(actual[index])} completed`}
              onMouseEnter={() => setActiveIndex(index)}
              onFocus={() => setActiveIndex(index)}
              onBlur={() => setActiveIndex(null)}
            />
          ))}

          {dates.map((date, index) => (
            <text x={pointX(index) - 9} y="157" key={date}>
              {chartLabel(date, period)}
            </text>
          ))}
        </svg>

        {activeIndex !== null &&
          dates[activeIndex] &&
          (() => {
            const plannedTime = planned[activeIndex];
            const completedTime = actual[activeIndex];
            const difference = plannedTime - completedTime;

            let status;

            if (difference === 0) {
              status = "You completed everything you scheduled.";
            } else if (difference > 0) {
              status = `${compactChartDuration(
                difference,
              )} of scheduled work was not completed.`;
            } else {
              status = `${compactChartDuration(
                Math.abs(difference),
              )} more than scheduled was completed.`;
            }

            const position =
              dates.length > 1
                ? 13 + (activeIndex * 74) / (dates.length - 1)
                : 50;

            return (
              <div
                className="stats-target-work-tooltip"
                role="tooltip"
                style={{
                  left: `${Math.min(85, Math.max(15, position))}%`,
                }}
              >
                <strong>
                  {new Date(
                    `${dates[activeIndex]}T00:00:00`,
                  ).toLocaleDateString([], {
                    weekday: "long",
                  })}
                </strong>

                <span>
                  Planned
                  <b>{compactChartDuration(plannedTime)}</b>
                </span>

                <span>
                  Completed
                  <b>{compactChartDuration(completedTime)}</b>
                </span>

                <span className="stats-target-work-tooltip__status">
                  {status}
                </span>
              </div>
            );
          })()}
      </div>

      <p className="stats-target-callout">
        {reflection?.tasks_completed
          ? `You completed ${reflection.tasks_completed} task${
              reflection.tasks_completed === 1 ? "" : "s"
            } in this period.`
          : "Completed work will appear here as your period grows."}
      </p>
    </div>
  );
}

function PlantIllustration() {
  return (
    <div className="stats-target-plant" aria-hidden="true">
      <span className="stats-target-plant__leaf stats-target-plant__leaf--left" />
      <span className="stats-target-plant__leaf stats-target-plant__leaf--right" />
      <span className="stats-target-plant__stem" />
      <span className="stats-target-plant__pot" />
    </div>
  );
}

function StatsPage() {
  const [progress, setProgress] = useState(null);
  const [reflection, setReflection] = useState(null);
  const [estimation, setEstimation] = useState(null);
  const [personalization, setPersonalization] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [rangeOpen, setRangeOpen] = useState(false);
  const rangeRef = useRef(null);
  useEffect(() => {
  const handleClickOutside = (event) => {
    if (
      rangeRef.current &&
      !rangeRef.current.contains(event.target)
    ) {
      setRangeOpen(false);
    }
  };

  document.addEventListener("mousedown", handleClickOutside);

  return () => {
    document.removeEventListener("mousedown", handleClickOutside);
  };
}, []);
  const [period, setPeriod] = useState("week");

  useEffect(() => {
    Promise.all([getProgress(), getEstimation(), getPersonalization()])
      .then(([progressData, estimationData, personalizationData]) => {
        setProgress(progressData);
        setEstimation(estimationData);
        setPersonalization(personalizationData.insights || []);
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    getWeeklyReflection(period)
      .then(setReflection)
      .catch((requestError) => setError(requestError.message));
  }, [period]);

  const insightItems = useMemo(() => {
    const items = [];
    if (reflection?.most_productive_day)
      items.push({
        icon: "☼",
        title: "Most productive day",
        text: `You completed the most tasks on ${weekday(reflection.most_productive_day)}.`,
      });
    if (reflection?.tasks_recovered)
      items.push({
        icon: "↗",
        title: "Strong recovery",
        text: `${reflection.tasks_recovered} task${reflection.tasks_recovered === 1 ? "" : "s"} recovered in this period.`,
      });
    if (progress?.completion_rate !== undefined)
      items.push({
        icon: "◎",
        title: "On the right track",
        text: `Your completion rate is ${percent(progress.completion_rate)}.`,
      });
    personalization
      .slice(0, 1)
      .forEach((insight) =>
        items.push({
          icon: "✦",
          title: "Personal pattern",
          text: insight.message,
        }),
      );
    return items.slice(0, 3);
  }, [personalization, progress, reflection]);

  const recoveryRate = reflection?.tasks_missed
    ? (reflection.tasks_recovered / reflection.tasks_missed) * 100
    : 0;
  const difference = Math.abs(estimation?.total_difference_minutes || 0);
  const comparisonLabel = periodComparisonLabel(period);
  const completionRate = (reflection?.completion_rate || 0) * 100;
  const previousCompletionRate =
    reflection?.previous_completion_rate === null ||
    reflection?.previous_completion_rate === undefined
      ? reflection?.previous_completion_rate
      : reflection.previous_completion_rate * 100;
  const taskDetail = comparisonLabel
    ? changeText(
        reflection?.tasks_completed || 0,
        reflection?.previous_tasks_completed,
        comparisonLabel,
      )
    : "All-time progress";
  const taskTone = comparisonLabel
    ? changeTone(
        reflection?.tasks_completed || 0,
        reflection?.previous_tasks_completed,
      )
    : "neutral";
  const completionDetail = comparisonLabel
    ? changeText(
        completionRate,
        previousCompletionRate,
        comparisonLabel,
        " pts",
      )
    : "All-time progress";
  const completionTone = comparisonLabel
    ? changeTone(completionRate, previousCompletionRate)
    : "neutral";
  const recoveryDetail = reflection?.tasks_missed
    ? `${reflection.tasks_recovered} of ${reflection.tasks_missed} missed tasks recovered`
    : "No missed tasks in this period";
  const previousRecoveryRate = reflection?.previous_tasks_missed
    ? (reflection.previous_tasks_recovered / reflection.previous_tasks_missed) *
      100
    : null;
  const recoveryComparison =
    comparisonLabel && previousRecoveryRate !== null
      ? changeText(recoveryRate, previousRecoveryRate, comparisonLabel, " pts")
      : recoveryDetail;
  const recoveryTone =
    comparisonLabel && previousRecoveryRate !== null
      ? changeTone(recoveryRate, previousRecoveryRate)
      : "neutral";

  return (
    <section className="stats-target-page" aria-labelledby="stats-heading">
      <header className="stats-target-header">
        <div>
          <h1 id="stats-heading">
            Your Stats <span aria-hidden="true">▥</span>
          </h1>
          <p>Understand your progress and keep building better days.</p>
        </div>
        <div className="stats-target-header__controls">
          <div className="stats-target-range" ref={rangeRef}>
            <button
              type="button"
              onClick={() => setRangeOpen((open) => !open)}
              aria-expanded={rangeOpen}
            >
              {PERIOD_LABELS[period]} <span aria-hidden="true">⌄</span>
            </button>
            {rangeOpen && (
              <div className="stats-target-range__menu" role="menu">
                {Object.entries(PERIOD_LABELS).map(([value, label]) => (
                  <button
                    type="button"
                    role="menuitem"
                    key={value}
                    onClick={() => {
                      setPeriod(value);
                      setRangeOpen(false);
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button
            className="stats-target-export"
            type="button"
            onClick={() => window.print()}
          >
            ⇩ <span>Export</span>
          </button>
        </div>
      </header>

      {loading && <p className="state-message">Gathering your progress...</p>}
      {error && <p className="state-message state-message--error">{error}</p>}
      {!loading && !error && (
        <>
          <section className="stats-target-summary" aria-label="Stats summary">
            <SummaryCard
              icon="✓"
              label="Tasks Completed"
              value={reflection?.tasks_completed ?? 0}
              detail={taskDetail}
              detailTone={taskTone}
              tone="green"
            />
            <SummaryCard
              icon="◷"
              label="Completion Rate"
              value={percent(completionRate)}
              detail={completionDetail}
              detailTone={completionTone}
              tone="lilac"
            />
            <SummaryCard
              icon="↗"
              label="Recovery Rate"
              value={percent(recoveryRate)}
              detail={recoveryComparison}
              detailTone={recoveryTone}
              tone="orange"
            />
            <SummaryCard
              icon="♨"
              label="Current Streak"
              value={`${progress?.current_streak_days ?? 0} days`}
              detail={
                progress?.current_streak_days
                  ? "Keep it up!"
                  : "A new streak can start today"
              }
              tone="sage"
            />
          </section>

          <section className="stats-target-row stats-target-row--charts">
            <article className="stats-target-panel stats-target-panel--trend">
              <div className="stats-target-panel__heading">
                <div>
                  <h2>Completion Trend</h2>
                  <p>Completed tasks over the selected period</p>
                </div>
              </div>
              <CompletionTrend
                dailyCompletedTasks={reflection?.daily_completed_tasks}
                period={period}
              />
              <p className="stats-target-callout">
                {reflection?.most_productive_day
                  ? `You were most productive on ${weekday(reflection.most_productive_day)}.`
                  : "Your most productive day will appear as your history grows."}
              </p>
            </article>
            <article className="stats-target-panel stats-target-panel--work">
              <div className="stats-target-panel__heading">
                <div>
                  <h2>Planned time vs. completed time</h2>
                  <p>See what you planned and what you actually finished.</p>
                </div>
              </div>
              <WorkComparison reflection={reflection} period={period} />
            </article>
          </section>

          <section className="stats-target-row stats-target-row--details">
            <article className="stats-target-panel stats-target-panel--insights">
              <div className="stats-target-panel__heading">
                <h2>Insights</h2>
                <span aria-hidden="true">✦</span>
              </div>
              <div className="stats-target-insights">
                {insightItems.length ? (
                  insightItems.map((item) => (
                    <div className="stats-target-insight" key={item.title}>
                      <span>{item.icon}</span>
                      <div>
                        <strong>{item.title}</strong>
                        <p>{item.text}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="stats-target-empty">
                    More insights will appear as your history grows.
                  </p>
                )}
              </div>
              <PlantIllustration />
            </article>
            <article className="stats-target-panel stats-target-panel--accuracy">
              <div className="stats-target-panel__heading">
                <h2>Time Estimation Accuracy</h2>
              </div>
              <div className="stats-target-accuracy">
                <div
                  className="stats-target-ring"
                  style={{
                    "--accuracy": `${estimation?.average_accuracy_percent || 0}%`,
                  }}
                >
                  <strong>
                    {percent(estimation?.average_accuracy_percent)}
                  </strong>
                  <span>Avg Accuracy</span>
                </div>
                <dl>
                  <div>
                    <dt>Estimated Time</dt>
                    <dd>
                      {formatDuration(estimation?.estimated_minutes || 0)}
                    </dd>
                  </div>
                  <div>
                    <dt>Actual Time</dt>
                    <dd>{formatDuration(estimation?.actual_minutes || 0)}</dd>
                  </div>
                  <div>
                    <dt>Difference</dt>
                    <dd>{formatDuration(difference)}</dd>
                  </div>
                </dl>
              </div>
            </article>
            <article className="stats-target-panel stats-target-panel--consistency">
              <div className="stats-target-panel__heading">
                <h2>Progress & Consistency</h2>
                <span aria-hidden="true">⚘</span>
              </div>
              <p className="stats-target-label">Progress Level</p>
              <div className="stats-target-progress-title">
                <strong>Level {progress?.progress_level ?? 1}</strong>
                <span>{percent(progress?.progress_percent)} XP</span>
              </div>
              <div className="stats-target-progress">
                <span
                  style={{ width: `${progress?.progress_percent || 0}%` }}
                />
              </div>
              <div className="stats-target-consistency">
                <div>
                  <small>Consistency</small>
                  <strong>
                    {progress?.current_streak_days ? "Good" : "Starting"}
                  </strong>
                </div>
                <div>
                  <small>Missed Tasks</small>
                  <strong>{reflection?.tasks_missed ?? 0}</strong>
                </div>
              </div>
              <p className="stats-target-balance">
                {reflection?.tasks_missed
                  ? "Keep balancing your week."
                  : "You are finding your rhythm."}
              </p>
            </article>
          </section>

          <section className="stats-target-footer">
            <span aria-hidden="true">♡</span>
            <div>
              <strong>Consistency is your superpower!</strong>
              <p>
                You’re showing up and putting in the work. Small steps every day
                lead to big progress.
              </p>
            </div>
            <PlantIllustration />
          </section>
        </>
      )}
    </section>
  );
}

export default StatsPage;
