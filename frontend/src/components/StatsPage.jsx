import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getHistory, getWeeklyReflection } from "../services/api.js";
import { stabilitySegmentAtAngle, stabilityTooltip } from "../utils/stabilityTooltip.mjs";
import {
  formatCompletionTime,
  trendDetailsByDisplayKey,
} from "../utils/completionDays.mjs";

function percent(value) {
  return `${Math.round(value || 0)}%`;
}

function periodComparisonLabel(period) {
  if (period === "week") return "last week";
  if (period === "month") return "last month";
  if (period === "year") return "last year";
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

function formatActiveDate(dateString, period) {
  if (!dateString) return null;
  const dateObj = new Date(`${dateString}T00:00:00`);
  if (isNaN(dateObj.getTime())) return null;

  if (period === "week") {
    return dateObj.toLocaleDateString([], { weekday: "long" });
  }
  if (period === "month" || period === "year") {
    return dateObj.toLocaleDateString([], { month: "long", day: "numeric" });
  }
  return dateObj.toLocaleDateString([], { month: "long", day: "numeric", year: "numeric" });
}

function findMostActivePlannedDay(dailyScheduledCompletedTasks) {
  if (!dailyScheduledCompletedTasks) return null;
  const entries = Object.entries(dailyScheduledCompletedTasks);
  let maxCount = 0;
  let bestDate = null;
  for (const [dateStr, count] of entries) {
    if (count > maxCount) {
      maxCount = count;
      bestDate = dateStr;
    }
  }
  return maxCount > 0 ? bestDate : null;
}

const PERIOD_LABELS = {
  week: "This Week",
  month: "This Month",
  year: "This Year",
  all: "All Time",
};

function getRangeDescription(range) {
  const today = new Date();

  if (range === "week") {
    const day = today.getDay();
    const monday = new Date(today);
    monday.setDate(today.getDate() - (day === 0 ? 6 : day - 1));

    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);

    return `${monday.toLocaleDateString([], {
      day: "numeric",
      month: "short",
    })} – ${sunday.toLocaleDateString([], {
      day: "numeric",
      month: "short",
      year: "numeric",
    })}`;
  }

  if (range === "month") {
    const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
    const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);

    return `${firstDay.toLocaleDateString([], {
      day: "numeric",
      month: "short",
    })} – ${lastDay.toLocaleDateString([], {
      day: "numeric",
      month: "short",
      year: "numeric",
    })}`;
  }

  if (range === "year") {
    return `1 Jan – 31 Dec ${today.getFullYear()}`;
  }

  return "All recorded history";
}

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
  const d = new Date(`${date}T00:00:00`);
  if (period === "week") return d.toLocaleDateString([], { weekday: "short" });
  if (period === "year" || period === "all") return d.toLocaleDateString([], { month: "short" });
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}
function getStabilityInsight(stayed, adjusted, missed) {
  const total = stayed + adjusted + missed;

  if (!total) {
    return {
      title: "Your planning pattern is still taking shape.",
      text: "Keep using Planora and we'll start to see how your plans hold up.",
    };
  }

  const stayedPercent = (stayed / total) * 100;
  const adjustedPercent = (adjusted / total) * 100;
  const missedPercent = (missed / total) * 100;

  if (missedPercent >= 30 && missed > adjusted) {
    return {
      title: "Missed plans are your biggest pattern.",
      text: `${missed} of ${total} planned tasks were missed, more than the ${adjusted} that were adjusted.`,
    };
  }

  if (missedPercent >= 30) {
    return {
      title: "You're missing a noticeable share of your plans.",
      text: `${missed} of ${total} planned tasks were missed this period.`,
    };
  }

  if (stayedPercent >= 70) {
    return {
      title: "Your plans are holding up well.",
      text: `${stayed} of ${total} planned tasks stayed intact this period.`,
    };
  }

  if (adjustedPercent >= 50) {
    return {
      title: "Your plans need frequent adjustment.",
      text: `${adjusted} of ${total} planned tasks changed course, while ${stayed} stayed intact.`,
    };
  }

  if (stayedPercent >= 50) {
    return {
      title: "Most of your plans are staying on track.",
      text: `${stayed} of ${total} planned tasks stayed intact this period.`,
    };
  }

  return {
    title: "Your plans are changing more than staying intact.",
    text: `${adjusted + missed} of ${total} planned tasks were adjusted or missed.`,
  };
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

function CompletionTrend({ dailyCompletedTasks, period, historyRecords, onNeedDetails }) {
  const entries = chartEntries(dailyCompletedTasks, period);
  const hasCompletedTasks = entries.some(([, count]) => count > 0);
  const maximum = Math.max(1, ...entries.map(([, count]) => count));
  const midpoint = maximum > 1 ? Math.ceil(maximum / 2) : null;
  const [activeDay, setActiveDay] = useState(null);
  useEffect(() => setActiveDay(null), [period, historyRecords]);
  const detailsByDay = useMemo(
    () => trendDetailsByDisplayKey(historyRecords ?? [], period),
    [historyRecords, period],
  );

  function tipTitle(day) {
    const date = new Date(`${day}T00:00:00`);
    if (period === "week") {
      return date.toLocaleDateString([], { weekday: "long" });
    }
    if (period === "month") {
      return `Week of ${chartLabel(day, period)}`;
    }
    return date.toLocaleDateString([], { month: "long", year: "numeric" });
  }

  function renderTip(day, count, position) {
    const items = detailsByDay.get(day) ?? [];
    const shown = items.slice(0, 6);
    return (
      <div
        className={`stats-target-tip${position ? ` stats-target-tip--${position}` : ""}`}
        role="status"
      >
        <strong>{tipTitle(day)}</strong>
        <p>
          {count === 0
            ? "No scheduled tasks completed"
            : `${count} task${count === 1 ? "" : "s"} completed`}
        </p>
        {count > 0 && (
          <ul>
            {shown.map((item) => (
              <li key={`${item.taskId}-${item.id}`}>
                <span aria-hidden="true">✓</span>
                <span>{item.title}</span>
                <time>{formatCompletionTime(item.timestampMs)}</time>
              </li>
            ))}
          </ul>
        )}
        {items.length > shown.length && (
          <p>+{items.length - shown.length} more</p>
        )}
      </div>
    );
  }

  return (
    <div
      className="stats-target-trend-chart"
      aria-label="Planned tasks completed each day"
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
        {!hasCompletedTasks ? (
          <div className="stats-target-trend-empty">
            <svg className="stats-target-empty-art" width="120" height="76" viewBox="0 0 120 76" aria-hidden="true">
              <ellipse cx="60" cy="66" rx="46" ry="7" fill="#e9f1e6" />
              <g fill="none" stroke="#7d9b8a" strokeWidth="2.5" strokeLinecap="round">
                <line x1="26" y1="62" x2="26" y2="40" />
                <line x1="44" y1="62" x2="44" y2="30" />
                <line x1="62" y1="62" x2="62" y2="22" />
                <line x1="22" y1="62" x2="66" y2="62" />
              </g>
              <g>
                <path d="M82 64C82 46 86 32 98 22c3 14-1 30-13 40" fill="#9dbd76" />
                <path d="M82 64c-1-15 1-27 9-35 4 12 0 26-7 34" fill="#6ca578" />
                <path d="M82 64l-1-24" stroke="#3f6b52" strokeWidth="1.8" strokeLinecap="round" />
              </g>
            </svg>
            <strong>Your progress will appear here</strong>
            <p>Complete a few scheduled tasks to start seeing your completion trend.</p>
          </div>
        ) : (
          entries.map(([day, count], index) => {
            const position = index === 0 ? "first" : index === entries.length - 1 ? "last" : null;
            return (
              <div
                className="stats-target-bar"
                key={day}
                role="button"
                tabIndex={0}
                aria-expanded={activeDay === day}
                aria-label={`${chartLabel(day, period)}: ${count} scheduled tasks completed. Activate for details.`}
                onMouseEnter={() => {
                  onNeedDetails?.();
                  setActiveDay(day);
                }}
                onMouseLeave={() => setActiveDay(null)}
                onFocus={() => {
                  onNeedDetails?.();
                  setActiveDay(day);
                }}
                onBlur={() => setActiveDay(null)}
                onClick={() => setActiveDay((current) => (current === day ? null : day))}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setActiveDay((current) => (current === day ? null : day));
                  } else if (event.key === "Escape") {
                    setActiveDay(null);
                  }
                }}
              >
                <strong>{count}</strong>
                <div className="stats-target-bar__track">
                  <span style={{ height: `${(count / maximum) * 100}%` }} />
                </div>
                <small>{chartLabel(day, period)}</small>
                {activeDay === day && renderTip(day, count, position)}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function PlannedCompletedTasks({ reflection }) {
  const scheduledTasks = reflection?.tasks_scheduled ?? 0;
  const completed = reflection?.tasks_scheduled_completed ?? 0;

  const completionRate = scheduledTasks > 0 ? (completed / scheduledTasks) * 100 : 0;

  return (
    <div className="stats-target-work">
      <div className="stats-target-work-bars">
        <div className="stats-target-work-row">
          <div className="stats-target-work-label">
            <span>Scheduled</span>
            <strong>{scheduledTasks}</strong>
            <small>tasks</small>
          </div>

          <div className="stats-target-work-track">
            <div
              className="stats-target-work-fill stats-target-work-fill--planned"
              style={{ width: scheduledTasks > 0 ? "100%" : "0%" }}
            />
          </div>
        </div>

        <div className="stats-target-work-row">
          <div className="stats-target-work-label">
            <span>Completed</span>
            <strong>{completed}</strong>
            <small>tasks</small>
          </div>

          <div className="stats-target-work-track">
            <div
              className="stats-target-work-fill stats-target-work-fill--completed"
              style={{
                width: `${Math.min(100, Math.max(0, completionRate))}%`,
              }}
            />
          </div>
        </div>
      </div>

      <div
        className="stats-target-work-rate"
        style={{
          "--completion": `${Math.min(100, Math.max(0, completionRate))}%`,
        }}
      >
        <div className="stats-target-work-rate__inner">
          <strong>{percent(completionRate)}</strong>
          <span>completed</span>
        </div>
      </div>

      <p className="stats-target-callout">
        <span className="stats-target-callout-icon" aria-hidden="true">✦</span>
        {scheduledTasks > 0
          ? `${completed} of ${scheduledTasks} Scheduled tasks were completed.`
          : "Scheduled tasks will appear as your history grows."}
      </p>
    </div>
  );
}
const STABILITY_CATEGORIES = [
  {
    key: "stayed_as_planned",
    label: "Stayed as planned",
    color: "var(--planora-green, #285c4d)",
  },
  {
    key: "adjusted",
    label: "Adjusted",
    color: "var(--planora-lilac, #b8a6cf)",
  },
  {
    key: "missed",
    label: "Missed",
    color: "var(--planora-orange, #d99a5b)",
  },
];

const STABILITY_DONUT_RADIUS = 44;
const STABILITY_DONUT_CIRCUMFERENCE = 2 * Math.PI * STABILITY_DONUT_RADIUS;

function PlanStabilityChart({ stability, tasksByCategory }) {
  const [hoveredCategory, setHoveredCategory] = useState(null);
  const [pinnedCategory, setPinnedCategory] = useState(null);

  const stayed = stability?.stayed_as_planned ?? 0;
  const adjusted = stability?.adjusted ?? 0;
  const missed = stability?.missed ?? 0;

  const total = stayed + adjusted + missed;
  const insight = getStabilityInsight(stayed, adjusted, missed);

  const counts = { stayed_as_planned: stayed, adjusted, missed };

  // A new period means new cohorts: drop any previous selection.
  useEffect(() => {
    setHoveredCategory(null);
    setPinnedCategory(null);
  }, [stayed, adjusted, missed]);

  if (!total) {
    return (
      <div className="stats-target-stability-empty">
        <svg className="stats-target-empty-art" width="120" height="76" viewBox="0 0 120 76" aria-hidden="true">
          <ellipse cx="60" cy="66" rx="46" ry="7" fill="#e9f1e6" />
          <g>
            <rect x="28" y="18" width="48" height="42" rx="6" fill="#fffdf9" stroke="#7d9b8a" strokeWidth="2.5" />
            <line x1="28" y1="30" x2="76" y2="30" stroke="#7d9b8a" strokeWidth="2.5" />
            <line x1="40" y1="14" x2="40" y2="22" stroke="#7d9b8a" strokeWidth="2.5" strokeLinecap="round" />
            <line x1="64" y1="14" x2="64" y2="22" stroke="#7d9b8a" strokeWidth="2.5" strokeLinecap="round" />
            <g fill="#9dbd76">
              <rect x="36" y="37" width="9" height="6" rx="1.5" />
              <rect x="49" y="37" width="9" height="6" rx="1.5" />
              <rect x="36" y="47" width="9" height="6" rx="1.5" />
              <rect x="49" y="47" width="9" height="6" rx="1.5" />
            </g>
          </g>
          <g>
            <path d="M86 64C86 48 89 36 99 28c3 12-1 26-11 34" fill="#9dbd76" />
            <path d="M86 64l-1-20" stroke="#3f6b52" strokeWidth="2" strokeLinecap="round" />
          </g>
        </svg>
        <strong>Not enough data yet.</strong>
        <p>Your planning pattern will appear as your history grows.</p>
      </div>
    );
  }

  const stayedPercent = (stayed / total) * 100;

  // Pinned selection wins over hover; cleared by re-click, Escape, or data change.
  const shownKey = pinnedCategory ?? hoveredCategory;
  const shownCount = shownKey ? (counts[shownKey] ?? 0) : 0;
  const shownTasks = shownKey ? (tasksByCategory?.[shownKey] ?? []) : [];
  const tip = stabilityTooltip(shownCount, shownTasks);
  const showTooltip = shownKey !== null && shownCount > 0;

  function togglePinned(key) {
    setPinnedCategory((current) => (current === key ? null : key));
  }

  function handleSegmentKeyDown(event, key) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      togglePinned(key);
    } else if (event.key === "Escape") {
      setPinnedCategory(null);
      setHoveredCategory(null);
    }
  }

  let consumedFraction = 0;
  const segments = STABILITY_CATEGORIES.map((category) => {
    const count = counts[category.key] ?? 0;
    const fraction = count / total;
    const startFraction = consumedFraction;
    consumedFraction += fraction;
    return { ...category, count, fraction, startFraction };
  }).filter((segment) => segment.count > 0);

  return (
    <div className="stats-target-stability-chart">
      <div className="stats-target-stability-group">
        <div
          className="stats-target-stability-donut stats-target-stability-donut--interactive"
          onMouseLeave={() => setHoveredCategory(null)}
        >
          <svg
            className="stats-target-stability-ring"
            viewBox="0 0 100 100"
            role="img"
            aria-label={`${stayed} stayed as planned, ${adjusted} adjusted, ${missed} missed`}
            onMouseMove={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              const dx = event.clientX - (rect.left + rect.width / 2);
              const dy = event.clientY - (rect.top + rect.height / 2);
              const radius = Math.min(rect.width, rect.height) / 2;
              const distance = Math.hypot(dx, dy);
              if (radius <= 0 || distance < radius * 0.6 || distance > radius * 1.1) {
                setHoveredCategory(null);
                return;
              }
              let angle = Math.atan2(dx, -dy) / (2 * Math.PI);
              if (angle < 0) angle += 1;
              setHoveredCategory(
                stabilitySegmentAtAngle(
                  counts,
                  STABILITY_CATEGORIES.map((category) => category.key),
                  angle,
                ),
              );
            }}
          >
            {segments.map((segment) => {
              const isActive = shownKey === segment.key;
              const isDimmed = shownKey !== null && !isActive;
              return (
                <circle
                  key={segment.key}
                  cx="50"
                  cy="50"
                  r={STABILITY_DONUT_RADIUS}
                  fill="none"
                  stroke={segment.color}
                  strokeWidth={isActive ? 15 : 12}
                  strokeDasharray={`${segment.fraction * STABILITY_DONUT_CIRCUMFERENCE} ${STABILITY_DONUT_CIRCUMFERENCE}`}
                  strokeDashoffset={
                    -segment.startFraction * STABILITY_DONUT_CIRCUMFERENCE
                  }
                  transform="rotate(-90 50 50)"
                  className={`stats-target-stability-segment${isActive ? " is-active" : ""}${isDimmed ? " is-dimmed" : ""}`}
                  tabIndex={0}
                  role="button"
                  aria-expanded={pinnedCategory === segment.key}
                  aria-label={`${segment.label}: ${segment.count} task${segment.count === 1 ? "" : "s"}. Activate to pin details.`}
                  onMouseEnter={() => setHoveredCategory(segment.key)}
                  onFocus={() => setHoveredCategory(segment.key)}
                  onBlur={() => setHoveredCategory(null)}
                  onClick={() => togglePinned(segment.key)}
                  onKeyDown={(event) => handleSegmentKeyDown(event, segment.key)}
                />
              );
            })}
          </svg>
          <div className="stats-target-stability-donut__inner">
            <strong>{Math.round(stayedPercent)}%</strong>
            <span>stable</span>
          </div>
          {showTooltip && (
            <div
              className="stats-target-tip stats-target-tip--below"
              role="status"
              aria-live="polite"
            >
              <strong>
                {STABILITY_CATEGORIES.find((category) => category.key === shownKey)?.label}
              </strong>
              <p>
                {shownCount} task{shownCount === 1 ? "" : "s"}
                {pinnedCategory ? " · pinned" : ""}
              </p>
              {tip.visible.length > 0 ? (
                <ul>
                  {tip.visible.map((task, index) => (
                    <li key={`${task.id ?? "deleted"}-${index}`}>
                      <span aria-hidden="true">•</span> {task.title}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>Task details are no longer available.</p>
              )}
              {tip.more > 0 && <p>+{tip.more} more</p>}
            </div>
          )}
        </div>

        <div className="stats-target-stability-legend">
          {STABILITY_CATEGORIES.map((category) => {
            const count = counts[category.key] ?? 0;
            const isActive = shownKey === category.key;
            const isDimmed = shownKey !== null && !isActive;
            return (
              <div
                key={category.key}
                className={`stats-target-stability-legend__item${isActive ? " is-active" : ""}${isDimmed ? " is-dimmed" : ""}`}
                role="button"
                tabIndex={0}
                aria-expanded={pinnedCategory === category.key}
                aria-label={`${category.label}: ${count} task${count === 1 ? "" : "s"}. Activate to pin details.`}
                onMouseEnter={() => setHoveredCategory(category.key)}
                onMouseLeave={() => setHoveredCategory(null)}
                onFocus={() => setHoveredCategory(category.key)}
                onBlur={() => setHoveredCategory(null)}
                onClick={() => togglePinned(category.key)}
                onKeyDown={(event) => handleSegmentKeyDown(event, category.key)}
              >
                <span className={`stats-target-stability-dot stats-target-stability-dot--${category.key === "stayed_as_planned" ? "stable" : category.key}`} />
                <span>{category.label}</span>
                <strong>{count}</strong>
              </div>
            );
          })}
        </div>
      </div>

      <p className="stats-target-callout stats-target-callout--bottom">
        <span className="stats-target-callout-icon" aria-hidden="true">
          ✦
        </span>
        {insight.title}
      </p>
    </div>
  );
}
function getDeadlineBehaviorInsight(behavior) {
  const completed = Math.max(0, Number(behavior?.completed_before_deadline) || 0);
  const rescheduled = Math.max(0, Number(behavior?.rescheduled) || 0);
  const missed = Math.max(0, Number(behavior?.missed_deadline) || 0);
  const total = completed + rescheduled + missed;

  // Case 1 — Zero State
  if (!total) {
    return "Complete some scheduled tasks to start seeing your deadline pattern.";
  }

  // Case 12 — Single Event States
  if (total === 1) {
    if (completed === 1) {
      return "Your first scheduled task was completed before its deadline.";
    }
    if (rescheduled === 1) {
      return "You rescheduled your scheduled task this period.";
    }
    if (missed === 1) {
      return "Your scheduled task missed its deadline this period.";
    }
  }

  // Case 13 — Two Events Tie States
  if (total === 2) {
    if (completed === 1 && missed === 1) {
      return "One scheduled task met its deadline and one missed it.";
    }
    if (completed === 1 && rescheduled === 1) {
      return "You completed and rescheduled your scheduled tasks about equally.";
    }
    if (rescheduled === 1 && missed === 1) {
      return "Your scheduled tasks were split between rescheduling and missed deadlines.";
    }
  }

  // Case 11 — Three-way Tie
  if (completed === rescheduled && rescheduled === missed) {
    return "Your deadline outcomes were evenly split this period.";
  }

  // Two-way Ties (largest equal)
  if (completed === missed && completed > rescheduled) {
    return "Your scheduled tasks were split between meeting and missing deadlines.";
  }
  if (rescheduled === missed && rescheduled > completed) {
    return "Your scheduled tasks were split between rescheduling and missed deadlines.";
  }
  if (completed === rescheduled && completed > missed) {
    return "You completed and rescheduled your scheduled tasks about equally.";
  }

  // Dominant States
  if (completed > rescheduled && completed > missed) {
    return "Most scheduled tasks were completed before their deadlines.";
  }
  if (missed > completed && missed > rescheduled) {
    return "Most scheduled tasks missed their deadlines this period.";
  }
  if (rescheduled > completed && rescheduled > missed) {
    return "You adjusted your schedule more often than you missed deadlines.";
  }

  return "Most scheduled tasks were completed before their deadlines.";
}

function DeadlineBehaviorChart({ behavior }) {
  const completed = behavior?.completed_before_deadline ?? 0;
  const rescheduled = behavior?.rescheduled ?? 0;
  const missed = behavior?.missed_deadline ?? 0;

  const insightText = getDeadlineBehaviorInsight(behavior);

  const rows = [
    {
      icon: "✓",
      label: "Completed before deadline",
      value: completed,
      tone: "green",
    },
    {
      icon: "↗",
      label: "Rescheduled",
      value: rescheduled,
      tone: "orange",
    },
    {
      icon: "!",
      label: "Missed deadline",
      value: missed,
      tone: "coral",
    },
  ];

  return (
    <div className="stats-target-deadline-chart">
      <div className="stats-target-deadline-rows">
        {rows.map((row) => (
          <div className="stats-target-deadline-row" key={row.label}>
            <span
              className={`stats-target-deadline-row__icon stats-target-deadline-row__icon--${row.tone}`}
              aria-hidden="true"
            >
              {row.icon}
            </span>
            <span className="stats-target-deadline-row__label">
              {row.label}
            </span>
            <strong className="stats-target-deadline-row__value">
              {row.value}
            </strong>
          </div>
        ))}
      </div>
      <p className="stats-target-callout stats-target-callout--bottom">
        <span className="stats-target-callout-icon" aria-hidden="true">✦</span>
        {insightText}
      </p>
    </div>
  );
}

function PlantIllustration({ inline = false }) {
  return (
    <div
      className={
        inline
          ? "stats-target-plant stats-target-plant--inline"
          : "stats-target-plant"
      }
      aria-hidden="true"
    >
      <span className="stats-target-plant__leaf stats-target-plant__leaf--left" />
      <span className="stats-target-plant__leaf stats-target-plant__leaf--right" />
      <span className="stats-target-plant__stem" />
      <span className="stats-target-plant__pot" />
    </div>
  );
}

function NewWeekNotification({ visible, onClose }) {
  if (!visible) return null;
  return (
    <div className="stats-new-week-toast" role="status" aria-live="polite">
      <span className="stats-new-week-toast__icon" aria-hidden="true">✓</span>
      <div className="stats-new-week-toast__body">
        <strong>It's a new week!</strong>
        <p>Your stats will start filling up as you plan, complete, and make progress.</p>
      </div>
      <button
        type="button"
        className="stats-new-week-toast__close"
        onClick={onClose}
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

// No module-level reflection cache: every mount fetches fresh. The page
// shell (header, summary, panels) renders immediately from null-safe
// defaults so navigation paints instantly; values fill in when data arrives.
function StatsPage() {
  const [reflection, setReflection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [rangeOpen, setRangeOpen] = useState(false);
  const [toastVisible, setToastVisible] = useState(false);
  const toastTimerRef = useRef(null);
  const rangeRef = useRef(null);
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (rangeRef.current && !rangeRef.current.contains(event.target)) {
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
    let cancelled = false;
    setLoading(true);
    setError(null);
    getWeeklyReflection(period)
      .then((data) => {
        if (cancelled) return;
        setReflection(data);
        if (period === "week") {
          const now = new Date();
          const dayOfWeek = now.getDay();
          const isEarlyInWeek = dayOfWeek >= 1 && dayOfWeek <= 3;
          const dailyScheduledCompleted = data?.daily_scheduled_completed_tasks || {};
          const hasPlannedCompletedThisWeek = Object.values(dailyScheduledCompleted).some((v) => v > 0);
          const hasPlannedActivity =
            (data?.tasks_scheduled ?? 0) > 0 ||
            (data?.tasks_scheduled_completed ?? 0) > 0 ||
            (data?.recovery_overview_missed ?? 0) > 0 ||
            (data?.recovery_overview_recovered ?? 0) > 0;
          const isNewWeek = isEarlyInWeek && !hasPlannedCompletedThisWeek && !hasPlannedActivity;
          if (isNewWeek) {
            setToastVisible(true);
            clearTimeout(toastTimerRef.current);
            toastTimerRef.current = setTimeout(() => setToastVisible(false), 5000);
          } else {
            setToastVisible(false);
          }
        } else {
          setToastVisible(false);
        }
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      clearTimeout(toastTimerRef.current);
    };
  }, [period]);

  // Event-level history for the trend tooltip. Fetched lazily on the
  // first bar interaction (not on mount) and cached per period, so Stats
  // never downloads the full event stream for tooltips nobody opens.
  const trendCacheRef = useRef(new Map());
  const trendInflightRef = useRef(new Set());
  const periodRef = useRef(period);
  periodRef.current = period;
  const [trendRecords, setTrendRecords] = useState(undefined);
  useEffect(() => {
    setTrendRecords(undefined);
  }, [period]);
  const ensureTrendRecords = useCallback(() => {
    const key = periodRef.current;
    if (trendCacheRef.current.has(key)) {
      const cached = trendCacheRef.current.get(key);
      setTrendRecords((current) => (current === undefined ? cached : current));
      return;
    }
    if (trendInflightRef.current.has(key)) return;
    trendInflightRef.current.add(key);
    getHistory({ range: key })
      .then((data) => {
        const records = Array.isArray(data) ? data : [];
        trendCacheRef.current.set(key, records);
        if (periodRef.current === key) setTrendRecords(records);
      })
      .catch(() => {
        trendCacheRef.current.set(key, null);
        if (periodRef.current === key) setTrendRecords(null);
      })
      .finally(() => {
        trendInflightRef.current.delete(key);
      });
  }, []);

  const recoveryOverviewMissed = reflection?.recovery_overview_missed ?? 0;
  const recoveryOverviewRecovered =
    reflection?.recovery_overview_recovered ?? 0;
  const recoveryOverviewRate = recoveryOverviewMissed
    ? (recoveryOverviewRecovered / recoveryOverviewMissed) * 100
    : 0;
  const stabilityTotal =
    (reflection?.plan_stability?.stayed_as_planned ?? 0) +
    (reflection?.plan_stability?.adjusted ?? 0) +
    (reflection?.plan_stability?.missed ?? 0);

  const insightItems = useMemo(() => {
    const items = [];
    // 1. Most active day
    const bestPlannedDateStr = findMostActivePlannedDay(reflection?.daily_scheduled_completed_tasks);
    if (bestPlannedDateStr) {
      const formattedDate = formatActiveDate(bestPlannedDateStr, period);
      if (formattedDate) {
        items.push({
          icon: "☼",
          title: "Most active day",
          text: `You completed the most planned tasks on ${formattedDate}.`,
        });
      }
    }

    // 2. Planning adjustments
    const adjustedCount = Number(reflection?.plan_stability?.adjusted ?? 0);
    if (adjustedCount > 0) {
      items.push({
        icon: "⚙",
        title: "Planning adjustments",
        text: `You adjusted ${adjustedCount} planned task${adjustedCount === 1 ? "" : "s"} this period.`,
      });
    }

    // 3. Deadline focus
    const completedBeforeDeadline = reflection?.deadline_behavior?.completed_before_deadline ?? 0;
    const rescheduledDeadlines = reflection?.deadline_behavior?.rescheduled ?? 0;
    const missedDeadlines = reflection?.deadline_behavior?.missed_deadline ?? 0;
    const totalDeadlineActivity = completedBeforeDeadline + rescheduledDeadlines + missedDeadlines;

    if (totalDeadlineActivity > 0) {
      if (completedBeforeDeadline > 0) {
        const percentage = Math.round((completedBeforeDeadline / totalDeadlineActivity) * 100);
        items.push({
          icon: "◎",
          title: "Deadline focus",
          text: `${percentage}% of your planned tasks were completed before their deadlines.`,
        });
      } else {
        items.push({
          icon: "◎",
          title: "Deadline focus",
          text: "None of your planned tasks were completed before their deadlines this period.",
        });
      }
    }

    return items.slice(0, 3);
  }, [reflection, stabilityTotal, period]);

  const recoveryRate = recoveryOverviewMissed
    ? (recoveryOverviewRecovered / recoveryOverviewMissed) * 100
    : 0;
  const comparisonLabel = periodComparisonLabel(period);
  const completionRate = (reflection?.completion_rate || 0) * 100;
  const previousCompletionRate =
    reflection?.previous_completion_rate === null ||
    reflection?.previous_completion_rate === undefined
      ? reflection?.previous_completion_rate
      : reflection.previous_completion_rate * 100;
  const taskDetail = comparisonLabel
    ? changeText(
        reflection?.tasks_scheduled_completed || 0,
        reflection?.previous_tasks_completed,
        comparisonLabel,
      )
    : "All-time progress";
  const taskTone = comparisonLabel
    ? changeTone(
        reflection?.tasks_scheduled_completed || 0,
        reflection?.previous_tasks_completed,
      )
    : "neutral";
  const completionDetail = comparisonLabel
    ? `${changeText(
        completionRate,
        previousCompletionRate,
        comparisonLabel,
        " pts",
      )} · planned tasks completed`
    : "Planned tasks completed";
  const completionTone = comparisonLabel
    ? changeTone(completionRate, previousCompletionRate)
    : "neutral";
  const recoveryDetail = recoveryOverviewMissed
    ? `${recoveryOverviewRecovered} of ${recoveryOverviewMissed} missed tasks recovered`
    : "No missed tasks in this period";
  const previousRecoveryRate = reflection?.previous_tasks_missed
    ? (reflection.previous_tasks_recovered / reflection.previous_tasks_missed) *
      100
    : null;
  const recoveryComparison =
    comparisonLabel && previousRecoveryRate !== null
      ? `${recoveryDetail} · ${changeText(
          recoveryRate,
          previousRecoveryRate,
          comparisonLabel,
          " pts",
        )}`
      : recoveryDetail;
  const recoveryTone =
    comparisonLabel && previousRecoveryRate !== null
      ? changeTone(recoveryRate, previousRecoveryRate)
      : "neutral";
  const hasStatsActivity =
    (reflection?.tasks_completed ?? 0) > 0 ||
    (reflection?.tasks_missed ?? 0) > 0 ||
    (reflection?.tasks_recovered ?? 0) > 0 ||
    (reflection?.postponement_cycles ?? 0) > 0;

  return (
    <section className="stats-target-page" aria-labelledby="stats-heading">
      <NewWeekNotification
        visible={toastVisible}
        onClose={() => {
          setToastVisible(false);
          clearTimeout(toastTimerRef.current);
        }}
      />
      <header className="stats-target-header">
        <div>
          <h1 id="stats-heading">
            Your Stats <span aria-hidden="true">▥</span>
          </h1>
          <p>Understand your planning patterns and how they evolve.</p>
        </div>
        <div className="stats-target-header__controls">
          <div className="history-dropdown" ref={rangeRef}>
            <button
              type="button"
              className="history-dropdown-trigger"
              onClick={() => setRangeOpen((open) => !open)}
              aria-expanded={rangeOpen}
              aria-haspopup="menu"
            >
              <span>{PERIOD_LABELS[period]}</span>
              <span className="history-dropdown-arrow" aria-hidden="true">⌄</span>
            </button>
            {rangeOpen && (
              <div className="history-dropdown-menu" role="menu">
                {Object.entries(PERIOD_LABELS).map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    role="menuitem"
                    className={
                      period === value
                        ? "history-dropdown-option--active"
                        : ""
                    }
                    onClick={() => {
                      setPeriod(value);
                      setRangeOpen(false);
                    }}
                  >
                    <span>{label}</span>
                    <small>{getRangeDescription(value)}</small>
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

      {loading && (
        <p className="state-message" aria-live="polite">
          Gathering your progress...
        </p>
      )}
      {error && !reflection && (
        <p className="state-message state-message--error">{error}</p>
      )}
      {!(!reflection && error) && (
        <>
          <section className="stats-target-summary" aria-label="Stats summary">
            <SummaryCard
              icon="✓"
              label="Scheduled Tasks Completed"
              value={reflection?.tasks_scheduled_completed ?? 0}
              detail={
                (reflection?.tasks_scheduled_completed ?? 0) > 0
                  ? taskDetail
                  : "Start by completing a scheduled task this week."
              }
              detailTone={(reflection?.tasks_scheduled_completed ?? 0) > 0 ? taskTone : "neutral"}
              tone="green"
            />

            <SummaryCard
              icon="◷"
              label="Completion Rate"
              value={
                (reflection?.tasks_scheduled ?? 0) > 0 ? percent(completionRate) : "—"
              }
              detail={
                (reflection?.tasks_scheduled ?? 0) > 0 &&
                (reflection?.tasks_scheduled_completed ?? 0) > 0
                  ? completionDetail
                  : "Not enough data yet. Keep going!"
              }
              detailTone={
                (reflection?.tasks_scheduled ?? 0) > 0 &&
                (reflection?.tasks_scheduled_completed ?? 0) > 0
                  ? completionTone
                  : "neutral"
              }
              tone="lilac"
            />

            <SummaryCard
              icon="↗"
              label="Recovery Rate"
              value={recoveryOverviewMissed > 0 ? percent(recoveryRate) : "—"}
              detail={
                recoveryOverviewMissed > 0
                  ? recoveryComparison
                  : "Will appear once you recover a missed scheduled task."
              }
              detailTone={recoveryOverviewMissed > 0 ? recoveryTone : "neutral"}
              tone="orange"
            />

            <SummaryCard
              icon="◌"
              label="Plan Stability"
              value={
                stabilityTotal > 0
                  ? percent(
                      (reflection.plan_stability.stayed_as_planned / stabilityTotal) * 100
                    )
                  : "—"
              }
              detail={
                stabilityTotal > 0
                  ? "Tasks that stayed as planned"
                  : "Your plan stability will appear as you build more data."
              }
              tone="sage"
            />
          </section>

          <section className="stats-target-row stats-target-row--charts">
                <article className="stats-target-panel stats-target-panel--trend">
                  <div className="stats-target-panel__heading">
                    <div>
                      <h2>Completion Trend</h2>
                      <p>Scheduled tasks completed over the selected period</p>
                    </div>
                  </div>
                  <CompletionTrend
                    dailyCompletedTasks={reflection?.daily_scheduled_completed_tasks}
                    period={period}
                    historyRecords={trendRecords}
                    onNeedDetails={ensureTrendRecords}
                  />
                </article>
                <article className="stats-target-panel stats-target-panel--work">
                  <div className="stats-target-panel__heading">
                    <div>
                      <h2>Scheduled vs Completed tasks</h2>
                      <p>See how scheduled task outcomes led to completion.</p>
                    </div>
                  </div>
                  <PlannedCompletedTasks reflection={reflection} />
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
                        <div className="stats-target-insights-empty">
                          <span className="stats-target-insights-empty__icon" aria-hidden="true">
                            <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                              <path
                                d="M7 1.5a3.5 3.5 0 0 0-2 6.36c.5.4.83.83 1 1.64h2c.17-.81.5-1.24 1-1.64A3.5 3.5 0 0 0 7 1.5z"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="1.2"
                                strokeLinejoin="round"
                              />
                              <line x1="5.8" y1="11" x2="8.2" y2="11" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                              <line x1="6.2" y1="12.5" x2="7.8" y2="12.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                              <line x1="7" y1="0.5" x2="7" y2="0" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
                              <line x1="3" y1="2.2" x2="3.7" y2="2.9" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
                              <line x1="11" y1="2.2" x2="10.3" y2="2.9" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
                            </svg>
                          </span>
                          <strong>Your week is just getting started.</strong>
                          <p>
                            Complete a few tasks to see personalized insights here.
                          </p>
                        </div>
                      )}
                    </div>
                </article>
                <article className="stats-target-panel stats-target-panel--accuracy">
                  <div className="stats-target-panel__heading">
                    <div>
                      <h2>Plan stability</h2>
                      <p>How often your plans stay intact.</p>
                    </div>
                  </div>

                  <PlanStabilityChart stability={reflection?.plan_stability} tasksByCategory={reflection?.plan_stability_tasks} />
                </article>
                <article className="stats-target-panel stats-target-panel--consistency">
                  <div className="stats-target-panel__heading">
                    <div>
                      <h2>Deadline behavior</h2>
                      <p>How you handle task deadlines.</p>
                    </div>
                  </div>

                  <DeadlineBehaviorChart
                    behavior={reflection?.deadline_behavior}
                  />
                </article>
                <article className="stats-target-panel stats-target-panel--recovery">
                  <div className="stats-target-panel__heading">
                    <div>
                      <h2>Recovery overview</h2>
                      <p>Turning missed tasks into future wins.</p>
                    </div>
                  </div>

                  <div className="stats-target-recovery">
                    {recoveryOverviewMissed > 0 ? (
                      <>
                        <div className="stats-target-recovery__flow">
                          <div className="stats-target-recovery__item stats-target-recovery__item--missed">
                            <strong>{recoveryOverviewMissed}</strong>
                            <span>Missed tasks</span>
                          </div>

                          <span
                            className="stats-target-recovery__arrow"
                            aria-hidden="true"
                          >
                            ↓
                          </span>

                          <div className="stats-target-recovery__item stats-target-recovery__item--recovered">
                            <strong>{recoveryOverviewRecovered}</strong>
                            <span>Recovered tasks</span>
                          </div>
                        </div>

                        <span
                          className="stats-target-recovery__arrow"
                          aria-hidden="true"
                        >
                          ↓
                        </span>

                        <div className="stats-target-recovery__rate">
                          <strong>{percent(recoveryOverviewRate)}</strong>
                          <span>Recovery rate</span>
                        </div>

                        <p className="stats-target-callout">
                          <span className="stats-target-callout-icon" aria-hidden="true">✦</span>
                          {`${recoveryOverviewRecovered} of ${recoveryOverviewMissed} missed tasks found a new place in your plan.`}
                        </p>
                      </>
                    ) : (
                      <div className="stats-target-recovery-empty">
                        <svg className="stats-target-empty-art" width="130" height="70" viewBox="0 0 130 70" aria-hidden="true">
                          <path
                            d="M64 8c14-5 34-3 44 6s14 6 15 16-4 20-16 24-18 12-36 9-28 6-42-1-21-4-22-15-1-16 7-24 8-12 20-14 10-3 30-1z"
                            fill="#eef4ea"
                          />
                          <ellipse cx="60" cy="62" rx="42" ry="5" fill="#e3ecdf" />
                          <g fill="none" stroke="#7d9b8a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M38 30a15 15 0 0 1 26-9" />
                            <path d="M64 21l1 8M64 21l-8 1" />
                            <path d="M68 44a15 15 0 0 1-26 9" />
                            <path d="M42 53l-1-8M42 53l8-1" />
                          </g>
                          <g>
                            <path d="M92 58c0-12 2-22 10-29 2 9-1 20-8 27" fill="#9dbd76" />
                            <path d="M92 58l-1-16" stroke="#3f6b52" strokeWidth="1.8" strokeLinecap="round" />
                          </g>
                        </svg>
                        <strong>Your recovery pattern will appear here.</strong>
                        <p>Recover a few missed tasks to see how you bounce back.</p>
                      </div>
                    )}
                  </div>
                </article>
              </section>

              <section className="stats-target-footer">
                <span aria-hidden="true">♡</span>
                <div>
                  <strong>You’re finding your rhythm.</strong>
                  <p>
                    {(reflection?.tasks_scheduled_completed ?? 0) > 0
                      ? `You completed ${reflection.tasks_scheduled_completed} scheduled task${reflection.tasks_scheduled_completed === 1 ? "" : "s"} in this period.`
                      : "Your planning patterns will appear as you build more history."}
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
