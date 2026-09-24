import { useEffect, useMemo, useState } from "react";
import TaskInspector from "./TaskInspector.jsx";
import {
  IconBell,
  IconCalendar,
  IconCheck,
  IconChevron,
  IconClock,
  IconLeaf,
  IconList,
  IconMissed,
  IconOverdue,
  IconPlus,
} from "./icons.jsx";
import { getTaskHistory } from "../services/api.js";

function startOfDay(value) {
  const d = new Date(value);
  d.setHours(0, 0, 0, 0);
  return d;
}

function isToday(value) {
  if (!value) return false;
  return startOfDay(value).getTime() === startOfDay(new Date()).getTime();
}

function fmtTime(value) {
  return new Date(value).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function fmtSlot(start, end) {
  if (!start) return null;
  if (!end) return fmtTime(start);
  const sameDay =
    new Date(start).toDateString() === new Date(end).toDateString();
  return sameDay ? `${fmtTime(start)} – ${fmtTime(end)}` : `${fmtTime(start)} → ${fmtTime(end)}`;
}

function fmtDayHeading() {
  return new Date().toLocaleDateString([], {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

// Daypart greeting from the browser's local time. Boundaries:
// 5:00–11:59 morning, 12:00–16:59 afternoon, 17:00–20:59 evening,
// otherwise night.
function greetingForDate(value) {
  const hour = new Date(value).getHours();
  if (hour >= 5 && hour < 12) return { text: "Good morning", icon: "☀" };
  if (hour >= 12 && hour < 17) return { text: "Good afternoon", icon: "☀" };
  if (hour >= 17 && hour < 21) return { text: "Good evening", icon: "🌤️" };
  return { text: "Good night", icon: "🌙" };
}

// Backend-derived state only: pending / completed / missed, plus the
// deadline-passed (overdue) distinction. No invented fourth status.
function sheetState(task) {
  if (task.completed || task.status === "completed") return "completed";
  if (task.status === "missed") return "missed";
  if (new Date(task.deadline) < new Date()) return "overdue";
  return "pending";
}

const STATE_META = {
  completed: { label: "Completed", Icon: IconCheck },
  missed: { label: "Missed", Icon: IconMissed },
  overdue: { label: "Overdue", Icon: IconOverdue },
  pending: { label: "Pending", Icon: IconClock },
};

function SheetRow({ task, state, selected, onSelect, onRecover, recoveringId, timeline = false, now = false, tone = null }) {
  const { label, Icon } = STATE_META[state];
  const MarkerIcon = tone === "unscheduled" ? IconCalendar : Icon;
  const slot = fmtSlot(task.scheduled_start, task.scheduled_end);
  const showState = state === "overdue" || state === "missed";
  return (
    <article
      className={`sheet-row sheet-row--${state}${selected ? " sheet-row--selected" : ""}${now ? " sheet-row--now" : ""}${tone ? ` sheet-row--${tone}` : ""}`}
    >
      <button
        className="sheet-row__body"
        type="button"
        onClick={onSelect}
        aria-label={`${task.title}${slot ? `, scheduled ${slot}` : ""}${showState ? `, ${label}` : ""}. Open details.`}
        aria-expanded={selected}
      >
        {timeline && task.scheduled_start && (
          <span className="sheet-row__time">{fmtTime(task.scheduled_start)}</span>
        )}
        <span className="sheet-row__marker" aria-hidden="true">
          <MarkerIcon />
        </span>
        <span className="sheet-row__text">
          <strong className="sheet-row__title">{task.title}</strong>
          <span className="sheet-row__sub">
            {slot ? (
              <span className="sheet-row__slot">{slot}</span>
            ) : (
              <span className="sheet-row__slot sheet-row__slot--none">Unscheduled</span>
            )}
            {showState && (
              <>
                <span aria-hidden="true"> · </span>
                <span className="sheet-row__state">{label}</span>
              </>
            )}
          </span>
        </span>
        <span className="sheet-row__open" aria-hidden="true">
          <IconChevron />
        </span>
      </button>
    </article>
  );
}

function Section({ eyebrow, title, hint, children }) {
  if (!children) return null;
  return (
    <section className="sheet-section" aria-label={title}>
      <header className="sheet-section__head">
        <p className="sheet-eyebrow">{eyebrow}</p>
        <h2 className="sheet-section__title">{title}</h2>
        {hint && <p className="sheet-section__hint">{hint}</p>}
      </header>
      {children}
    </section>
  );
}

export default function DaySheet({
  tasks,
  incompleteTasks,
  completedTodayTasks,
  currentUser,
  loading,
  error,
  onCreate,
  onEdit,
  onComplete,
  onDelete,
  onRecover,
  recoveringId,
}) {
  const [now, setNow] = useState(() => new Date());
  const [selectedId, setSelectedId] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 60000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    getTaskHistory().then(setHistory).catch(() => setHistory([]));
  }, [tasks]);

  const groups = useMemo(() => {
    const nowDate = now;
    const nowMs = nowDate.getTime();
    const nowRows = [];
    const upcoming = [];
    const earlier = [];
    const missed = [];
    const overdue = [];
    const unscheduled = [];
    for (const task of incompleteTasks) {
      const state = sheetState(task);
      if (state === "missed") {
        missed.push(task);
        continue;
      }
      if (state === "overdue" && !task.scheduled_start) {
        overdue.push(task);
        continue;
      }
      if (!task.scheduled_start || !task.scheduled_end) {
        unscheduled.push(task);
        continue;
      }
      const start = new Date(task.scheduled_start).getTime();
      const end = new Date(task.scheduled_end).getTime();
      if (state === "overdue") {
        overdue.push(task);
      } else if (start <= nowMs && end > nowMs) {
        nowRows.push(task);
      } else if (start > nowMs) {
        upcoming.push(task);
      } else {
        earlier.push(task);
      }
    }
    const byStart = (a, b) =>
      new Date(a.scheduled_start) - new Date(b.scheduled_start);
    nowRows.sort(byStart);
    upcoming.sort(byStart);
    earlier.sort(byStart);
    return { nowRows, upcoming, earlier, missed, overdue, unscheduled };
  }, [incompleteTasks, now]);

  const selectedTask =
    tasks.find((task) => String(task.id) === String(selectedId)) ?? null;
  const selectedIsNow =
    selectedTask !== null &&
    groups.nowRows.some((task) => String(task.id) === String(selectedTask.id));

  // Partition of incomplete tasks (mutually exclusive, exhaustive):
  // A (planned)     = pending + complete slot          -> now/upcoming/earlier
  // B (decision)    = missed OR overdue (slot ignored) -> missed/overdue trays
  // C (unscheduled) = pending + no complete slot       -> unscheduled tray
  const plannedCount = groups.nowRows.length + groups.upcoming.length + groups.earlier.length;
  const decisionCount = groups.missed.length + groups.overdue.length;
  const unscheduledCount = groups.unscheduled.length;

  const firstName = currentUser?.name?.trim().split(/\s+/)[0] ?? "";
  const greeting = greetingForDate(now);

  return (
    <div className="day-sheet">
      <header className="sheet-head">
        <div>
          <p className="sheet-eyebrow">{fmtDayHeading()}</p>
          <h1 className="sheet-title">
            {firstName ? `${greeting.text}, ${firstName}!` : greeting.text} <span aria-hidden="true">{greeting.icon}</span>
          </h1>
          <p className="sheet-standfirst">
            Here is what your day looks like.
          </p>
        </div>
        <button className="button button--primary sheet-head__add" type="button" onClick={onCreate}>
          <IconPlus />
          Add task
        </button>
      </header>

      {!loading && (incompleteTasks.length > 0 || completedTodayTasks.length > 0) && (
        <section className="history-summary" aria-label="Today at a glance">
          <article className="history-summary__card history-summary__card--completed">
            <span aria-hidden="true">◷</span>
            <div>
              <p>Scheduled</p>
              <strong>{plannedCount}</strong>
            </div>
          </article>
          <article className="history-summary__card history-summary__card--missed">
            <span aria-hidden="true"><IconBell width={20} height={20} /></span>
            <div>
              <p>Needs decision</p>
              <strong>{decisionCount}</strong>
            </div>
          </article>
          <article className="history-summary__card history-summary__card--unscheduled">
            <span aria-hidden="true"><IconCalendar width={20} height={20} /></span>
            <div>
              <p>Unscheduled</p>
              <strong>{unscheduledCount}</strong>
            </div>
          </article>
        </section>
      )}

      {loading && <p className="sheet-state">Loading your tasks…</p>}
      {error && <p className="sheet-state sheet-state--error">{error}</p>}

      {!loading && incompleteTasks.length === 0 && completedTodayTasks.length === 0 && (
        <section className="sheet-empty sheet-empty--polished" aria-label="Empty day">
          <svg className="sheet-empty__art" width="260" height="168" viewBox="0 0 260 168" aria-hidden="true">
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
          <p className="sheet-eyebrow sheet-empty__eyebrow">Your day is open</p>
          <h2 className="sheet-empty__title">What would make today feel productive?</h2>
          <p className="sheet-empty__body">Add what matters, and Planora will find a realistic place for it.</p>
          <button className="button button--primary sheet-empty__cta" type="button" onClick={onCreate}>
            <IconPlus />
            Add your first task
          </button>
          <ul className="sheet-empty__hints" aria-label="How Planora helps">
            <li>
              <span className="sheet-empty__hint-icon" aria-hidden="true"><IconList /></span>
              <span>
                <strong>Capture what&rsquo;s on your mind</strong>
                <small>Add tasks, big or small</small>
              </span>
            </li>
            <li>
              <span className="sheet-empty__hint-icon" aria-hidden="true"><IconClock /></span>
              <span>
                <strong>Plan with intention</strong>
                <small>Let Planora help you find time for it</small>
              </span>
            </li>
            <li>
              <span className="sheet-empty__hint-icon" aria-hidden="true"><IconLeaf /></span>
              <span>
                <strong>Feel more in control</strong>
                <small>A clearer day leads to a calmer mind</small>
              </span>
            </li>
          </ul>
        </section>
      )}

      <div className="day-layout">
      <div className="day-main">
      {(groups.missed.length > 0 || groups.overdue.length > 0 || groups.unscheduled.length > 0) && (
        <Section
          eyebrow="Needs a decision"
          title="Open loops"
          hint="Missed slots, passed deadlines, and unscheduled work."
        >
          <div className="day-card">
            {groups.overdue.map((task) => (
              <SheetRow
                key={task.id}
                task={task}
                state="overdue"
                selected={String(selectedId) === String(task.id)}
                onSelect={() => setSelectedId(task.id)}
                onRecover={onRecover}
                recoveringId={recoveringId}
              />
            ))}
            {(groups.missed.length > 0 || groups.unscheduled.length > 0) && (
              <>
                <div className="sheet-subhead">
                  <p className="sheet-eyebrow">Unscheduled <span className="sheet-count">{groups.missed.length + groups.unscheduled.length}</span></p>
                </div>
                <p className="sheet-section__hint">Tasks not yet planned for today.</p>
                {groups.missed.map((task) => (
                  <SheetRow
                    key={task.id}
                    task={task}
                    state="missed"
                    selected={String(selectedId) === String(task.id)}
                    onSelect={() => setSelectedId(task.id)}
                    onRecover={onRecover}
                    recoveringId={recoveringId}
                  />
                ))}
                {groups.unscheduled.map((task) => (
                  <SheetRow
                    key={task.id}
                    task={task}
                    state="pending"
                    tone="unscheduled"
                    selected={String(selectedId) === String(task.id)}
                    onSelect={() => setSelectedId(task.id)}
                    onRecover={onRecover}
                    recoveringId={recoveringId}
                  />
                ))}
              </>
            )}
          </div>
        </Section>
      )}

      {(groups.nowRows.length > 0 || groups.upcoming.length > 0 || groups.earlier.length > 0) && (
        <Section eyebrow="Schedule" title="The day's plan" hint="Persisted slots from Plan My Day.">
          <div className="sheet-rows sheet-rows--ruled day-card">
            <div className="sheet-nowline" aria-label={`Current time ${fmtTime(now)}`}>
              <span className="sheet-nowline__rule" aria-hidden="true" />
              <span className="sheet-nowline__pill">Now · {fmtTime(now)}</span>
              <span className="sheet-nowline__rule" aria-hidden="true" />
            </div>
            {groups.earlier.length > 0 && (
              <div className="sheet-daypart">
                <p className="sheet-daypart__label">Earlier</p>
                {groups.earlier.map((task) => (
                  <SheetRow
                    key={task.id}
                    task={task}
                    state={sheetState(task)}
                    timeline
                    selected={String(selectedId) === String(task.id)}
                    onSelect={() => setSelectedId(task.id)}
                    onRecover={onRecover}
                    recoveringId={recoveringId}
                  />
                ))}
              </div>
            )}
            {groups.nowRows.length > 0 && (
              <div className="sheet-daypart">
                <p className="sheet-daypart__label">Happening now</p>
                {groups.nowRows.map((task) => (
                  <SheetRow
                    key={task.id}
                    task={task}
                    state={sheetState(task)}
                    timeline
                    now
                    selected={String(selectedId) === String(task.id)}
                    onSelect={() => setSelectedId(task.id)}
                    onRecover={onRecover}
                    recoveringId={recoveringId}
                  />
                ))}
              </div>
            )}
            {groups.upcoming.length > 0 && (
              <div className="sheet-daypart">
                <p className="sheet-daypart__label">Upcoming</p>
                {groups.upcoming.map((task) => (
                  <SheetRow
                    key={task.id}
                    task={task}
                    state={sheetState(task)}
                    timeline
                    selected={String(selectedId) === String(task.id)}
                    onSelect={() => setSelectedId(task.id)}
                    onRecover={onRecover}
                    recoveringId={recoveringId}
                  />
                ))}
              </div>
            )}
          </div>
        </Section>
      )}

      {completedTodayTasks.length > 0 && (
        <section className="sheet-section" aria-label="Completed">
          <p className="sheet-eyebrow">Completed <span className="sheet-count">{completedTodayTasks.length}</span></p>
          <div className="sheet-rows">
            {completedTodayTasks.map((task) => (
              <SheetRow
                key={task.id}
                task={task}
                state="completed"
                selected={String(selectedId) === String(task.id)}
                onSelect={() => setSelectedId(task.id)}
                onRecover={onRecover}
                recoveringId={recoveringId}
              />
            ))}
          </div>
        </section>
      )}
      </div>

      {selectedTask && (
        <aside className="day-detail" aria-label="Task detail panel">
          <TaskInspector
            inline
            task={selectedTask}
            happeningNow={selectedIsNow}
            history={history.filter(
              (event) => String(event.task_id) === String(selectedId),
            )}
            onClose={() => setSelectedId(null)}
            onEdit={() => selectedTask && onEdit(selectedTask)}
            onComplete={() => selectedTask && onComplete(selectedTask)}
            onDelete={() => selectedTask && onDelete(selectedTask)}
            onRecover={() => selectedTask && onRecover(selectedTask)}
            recovering={selectedTask && recoveringId === selectedTask.id}
          />
        </aside>
      )}
      </div>

    </div>
  );
}

// Re-exported for tests/consumers that only need the grouping rule.
export { sheetState, isToday };
