import { useEffect, useMemo, useRef, useState } from "react";
import { getWeeklyReflection } from "../services/api.js";

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

function CompletionTrend({ dailyCompletedTasks, period }) {
  const entries = chartEntries(dailyCompletedTasks, period);
  const hasCompletedTasks = entries.some(([, count]) => count > 0);
  const maximum = Math.max(1, ...entries.map(([, count]) => count));
  const midpoint = maximum > 1 ? Math.ceil(maximum / 2) : null;

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
            <PlantIllustration inline />
            <strong>No scheduled tasks completed yet this week.</strong>
            <p>Your progress will appear here as you complete tasks.</p>
          </div>
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
function PlanStabilityChart({ stability }) {
  const stayed = stability?.stayed_as_planned ?? 0;
  const adjusted = stability?.adjusted ?? 0;
  const missed = stability?.missed ?? 0;

  const total = stayed + adjusted + missed;
  const insight = getStabilityInsight(stayed, adjusted, missed);

  if (!total) {
    return (
      <div className="stats-target-stability-empty">
        <PlantIllustration inline />
        <strong>Not enough data yet.</strong>
        <p>Your planning pattern will appear as your history grows.</p>
      </div>
    );
  }

  const stayedPercent = (stayed / total) * 100;
  const adjustedPercent = (adjusted / total) * 100;

  return (
    <div className="stats-target-stability-chart">
      <div className="stats-target-stability-group">
        <div
          className="stats-target-stability-donut"
          style={{
            background: `conic-gradient(
              var(--planora-green, #285c4d) 0% ${stayedPercent}%,
              var(--planora-lilac, #b8a6cf) ${stayedPercent}% ${
                stayedPercent + adjustedPercent
              }%,
              var(--planora-orange, #d99a5b) ${stayedPercent + adjustedPercent}% 100%
            )`,
          }}
          aria-label={`${stayed} stayed as planned, ${adjusted} adjusted, ${missed} missed`}
        >
          <div className="stats-target-stability-donut__inner">
            <strong>{Math.round(stayedPercent)}%</strong>
            <span>stable</span>
          </div>
        </div>

        <div className="stats-target-stability-legend">
          <div>
            <span className="stats-target-stability-dot stats-target-stability-dot--stable" />
            <span>Stayed as planned</span>
            <strong>{stayed}</strong>
          </div>

          <div>
            <span className="stats-target-stability-dot stats-target-stability-dot--adjusted" />
            <span>Adjusted</span>
            <strong>{adjusted}</strong>
          </div>

          <div>
            <span className="stats-target-stability-dot stats-target-stability-dot--missed" />
            <span>Missed</span>
            <strong>{missed}</strong>
          </div>
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
        console.log("STATS REFLECTION DATA:", data);
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
        if (!cancelled) setError(requestError.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      clearTimeout(toastTimerRef.current);
    };
  }, [period]);

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

      {loading && <p className="state-message">Gathering your progress...</p>}
      {error && <p className="state-message state-message--error">{error}</p>}
      {!loading && !error && (
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
                            ✦
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

                  <PlanStabilityChart stability={reflection?.plan_stability} />
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
                      <strong>{recoveryOverviewMissed > 0 ? percent(recoveryOverviewRate) : "—"}</strong>
                      <span>Recovery rate</span>
                    </div>

                    <p className="stats-target-callout">
                      <span className="stats-target-callout-icon" aria-hidden="true">✦</span>
                      {recoveryOverviewMissed > 0
                        ? `${recoveryOverviewRecovered} of ${recoveryOverviewMissed} missed tasks found a new place in your plan.`
                        : "Your recovery pattern will appear as you miss and recover tasks."}
                    </p>
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
