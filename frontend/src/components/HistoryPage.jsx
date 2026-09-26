import { useEffect, useMemo, useRef, useState } from "react";
import { getHistory } from "../services/api.js";
import { formatHistoryTime } from "../utils/historyFormat.mjs";

const PAGE_SIZE = 10;
const FILTERS = [
  ["all", "All"],
  ["scheduled", "Created"],
  ["completed", "Completed"],
  ["missed", "Missed"],
  ["overdue", "Overdue"],
  ["rescheduled", "Rescheduled"],
  ["recovered", "Recovered"],
];
const RANGE_LABELS = {
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

function formatDateHeading(timestamp) {
  const date = new Date(timestamp);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const formatted = date.toLocaleDateString([], {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  if (date.toDateString() === today.toDateString())
    return `Today · ${formatted}`;
  if (date.toDateString() === yesterday.toDateString())
    return `Yesterday · ${formatted}`;
  return formatted;
}

function formatTime(timestamp) {
  return formatHistoryTime(timestamp);
}

function formatSchedule(timestamp) {
  if (!timestamp) return null;
  return new Date(timestamp).toLocaleString([], {
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

function formatScheduleRange(start, end) {
  if (!start) return null;
  if (!end) return formatSchedule(start);

  const startDate = new Date(start);
  const endDate = new Date(end);
  if (startDate.toDateString() !== endDate.toDateString()) {
    return `${formatSchedule(start)}–${formatSchedule(end)}`;
  }

  return `${formatSchedule(start)}–${formatTime(end)}`;
}



function groupByDate(events) {
  return events.reduce((groups, event) => {
    const heading = formatDateHeading(event.timestamp);
    groups[heading] ??= [];
    groups[heading].push(event);
    return groups;
  }, {});
}

function EventDetail({ event }) {
  if (event.event_type === "missed") {
    const missedStart = event.old_start;
    const missedEnd = event.old_end;

    return (
      <>
        {missedStart && (
          <p> Scheduled for: {formatScheduleRange(missedStart, missedEnd)}</p>
        )}
      </>
    );
  }
  if (event.event_type === "overdue") {
  return (
    <>
      {event.deadline && (
        <p>Deadline: {formatSchedule(event.deadline)}</p>
      )}
      <p>Task remained incomplete after its deadline.</p>
    </>
  );
}

  if (event.event_type === "scheduled") {
    return (
      <>
        {event.new_start && (
          <p className="history-row__recovered">
            Scheduled for {formatSchedule(event.new_start)}
          </p>
        )}
        <p>Added to your plan</p>
      </>
    );
  }

  if (event.event_type === "recovered") {
    return (
      <>
        {event.new_start && (
          <p className="history-row__recovered">
            New scheduled time: {formatSchedule(event.new_start)}
          </p>
        )}
        <p>
          Reason:
          {event.reason || "Missed task recovered into a future plan"}
        </p>
      </>
    );
  }

  if (event.event_type === "rescheduled") {
    if (event.task_count) {
      return <p>{event.reason}</p>;
    }

    return (
      <>
        {event.old_start && (
          <p>
            Was scheduled for: {formatScheduleRange(event.old_start, event.old_end)}
          </p>
        )}
        {event.new_start && (
          <p className="history-row__recovered">
            Now scheduled for: {formatScheduleRange(event.new_start, event.new_end)}
          </p>
        )}
        {event.reason && <p>Reason: {event.reason}</p>}
      </>
    );
  }

  return (
    <>
      {event.deadline && (
        <p>Deadline: {formatSchedule(event.deadline)}</p>
      )}
    </>
  );
}

// No module-level cache: every mount fetches fresh. The page shell
// (header, controls, summary) renders immediately from local state so
// navigation paints instantly; the feed below fills in when data arrives.
function HistoryPage() {
  const [history, setHistory] = useState([]);
  const [filter, setFilter] = useState("all");
  const [isRangeOpen, setIsRangeOpen] = useState(false);
  const rangeDropdownRef = useRef(null);
  const [query, setQuery] = useState("");
  const [range, setRange] = useState("week");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  useEffect(() => {
  function handleOutsideClick(event) {
    if (
      rangeDropdownRef.current &&
      !rangeDropdownRef.current.contains(event.target)
    ) {
      setIsRangeOpen(false);
    }
  }

  document.addEventListener("mousedown", handleOutsideClick);

  return () => {
    document.removeEventListener("mousedown", handleOutsideClick);
  };
}, []);

  useEffect(() => {
  setLoading(true);
  setError(null);

  getHistory({ range })
    .then((data) => {
      setHistory(data);
    })
    .catch((requestError) => {
      setError(requestError.message);
    })
    .finally(() => setLoading(false));
}, [range]);

  const meaningfulHistory = history;

  const filterCounts = useMemo(
  () => ({
    all: meaningfulHistory.length,
    scheduled: meaningfulHistory.filter(event => event.event_type === "scheduled").length,
    completed: meaningfulHistory.filter(
      (event) => event.event_type === "completed",
    ).length,
    missed: meaningfulHistory.filter(
      (event) => event.event_type === "missed",
    ).length,
    overdue: meaningfulHistory.filter(
      (event) => event.event_type === "overdue",
    ).length,
    rescheduled: meaningfulHistory.filter(
      (event) => event.event_type === "rescheduled",
    ).length,
    recovered: meaningfulHistory.filter(
      (event) => event.event_type === "recovered",
    ).length,
  }),
  [meaningfulHistory],
);
  
  const visibleHistory = useMemo(() => {
    const search = query.trim().toLocaleLowerCase();
    return meaningfulHistory.filter(
      (event) =>
        (filter === "all" || event.event_type === filter) &&
        (!search ||
          (event.task_title ?? "Deleted task")
            .toLocaleLowerCase()
            .includes(search)),
    );
  }, [meaningfulHistory, filter, query]);
  useEffect(() => setPage(1), [filter, query, range]);

  const totalPages = Math.max(1, Math.ceil(visibleHistory.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageEvents = visibleHistory.slice(
    (safePage - 1) * PAGE_SIZE,
    safePage * PAGE_SIZE,
  );
  const start =
    visibleHistory.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1;
  const end = Math.min(safePage * PAGE_SIZE, visibleHistory.length);

  return (
    <section className="history-page" aria-labelledby="history-heading">
      <header className="history-page__header">
        <div>
          <h1 id="history-heading">
            History <span aria-hidden="true">↻</span>
          </h1>
          <p>See how your plans changed and how tasks were recovered.</p>
        </div>
        <div className="history-page__controls">
          <label className="history-search">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search history…"
              aria-label="Search history"
            />
          </label>
          <button
            className={`history-control ${filtersOpen ? "history-control--active" : ""}`}
            type="button"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-expanded={filtersOpen}
          >
            Filter
          </button>
          <div className="history-dropdown" ref={rangeDropdownRef}>
            <button type="button" className="history-dropdown-trigger" onClick={() => setIsRangeOpen((open) => !open)} aria-expanded={isRangeOpen} aria-haspopup="menu">
              {RANGE_LABELS[range]} <span className="history-dropdown-arrow" aria-hidden="true">⌄</span>
            </button>
            {isRangeOpen && <div className="history-dropdown-menu" role="menu">
              {Object.entries(RANGE_LABELS).map(([value, label]) => (
  <button
    key={value}
    type="button"
    role="menuitem"
    className={
      range === value ? "history-dropdown-option--active" : ""
    }
    onClick={() => {
      setRange(value);
      setIsRangeOpen(false);
    }}
  >
    <span>{label}</span>
    <small>{getRangeDescription(value)}</small>
  </button>
))}
            </div>}
          </div>
        </div>
      </header>

      <section className="history-summary" aria-label="History summary">
        <article className="history-summary__card history-summary__card--completed">
  <span>✓</span>
  <div>
    <p>Completed events</p>
    <strong>{filterCounts.completed}</strong>
    <small>Tasks you finished</small>
  </div>
</article>

<article className="history-summary__card history-summary__card--missed">
  <span>!</span>
  <div>
    <p>Missed events</p>
    <strong>{filterCounts.missed}</strong>
    <small>Tasks that weren&rsquo;t completed</small>
  </div>
</article>

<article className="history-summary__card history-summary__card--recovered">
  <span>↻</span>
  <div>
    <p>Recovery events</p>
    <strong>{filterCounts.recovered}</strong>
    <small>Tasks you brought back</small>
  </div>
</article>

<article className="history-summary__card history-summary__card--rescheduled">
  <span>↗</span>
  <div>
    <p>Reschedule events</p>
    <strong>{filterCounts.rescheduled}</strong>
    <small>Tasks you moved</small>
  </div>
</article>
      </section>

      {filtersOpen && (
        <div
          className="history-tabs"
          role="tablist"
          aria-label="History filters"
        >
          {FILTERS.map(([value, label]) => (
  <button
    key={value}
    className={
  filter === value
    ? "history-tab history-tab--active"
    : "history-tab"
}
    onClick={() => setFilter(value)}
  >
    <span>{label}</span>
    <span className="history-filter__count">{filterCounts[value]}</span>
  </button>
))}
        </div>
      )}
      {loading && (
        <p className="state-message" aria-live="polite">
          Loading your history…
        </p>
      )}
      {error && <p className="state-message state-message--error">{error}</p>}
      {!error && !loading && pageEvents.length === 0 && (
        <section className="history-empty history-empty--split">
          <div className="history-empty__art" aria-hidden="true">
            <svg width="300" height="220" viewBox="0 0 300 220" aria-hidden="true">
              <path
                d="M150 14c30-12 72-5 90 16s34 10 39 35-9 51-35 60-34 35-71 30-51 23-81 12-60 2-67-26-25-30-16-55 5-39 16-51 25-13 51-21z"
                fill="#eaf2e7"
              />
              <ellipse cx="150" cy="200" rx="82" ry="10" fill="#e7ede4" />
              <g transform="rotate(-5 108 112)">
                <rect x="62" y="52" width="92" height="118" rx="8" fill="#fffdf9" stroke="#7d9b8a" strokeWidth="2.5" />
                <rect x="92" y="42" width="32" height="16" rx="5" fill="#7d9b8a" />
                <circle cx="74" cy="36" r="5" fill="none" stroke="#7d9b8a" strokeWidth="2.5" />
                <circle cx="82" cy="86" r="8" fill="none" stroke="#7d9b8a" strokeWidth="2" />
                <line x1="98" y1="86" x2="134" y2="86" stroke="#7d9b8a" strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="82" cy="114" r="8" fill="none" stroke="#7d9b8a" strokeWidth="2" />
                <line x1="98" y1="114" x2="140" y2="114" stroke="#7d9b8a" strokeWidth="2.5" strokeLinecap="round" />
                <circle cx="82" cy="142" r="8" fill="none" stroke="#7d9b8a" strokeWidth="2" />
                <line x1="98" y1="142" x2="130" y2="142" stroke="#7d9b8a" strokeWidth="2.5" strokeLinecap="round" />
              </g>
              <path d="M158 128c22-8 34-22 38-44" fill="none" stroke="#7d9b8a" strokeWidth="2" strokeDasharray="5 5" strokeLinecap="round" />
              <circle cx="202" cy="72" r="20" fill="#fffdf9" stroke="#7d9b8a" strokeWidth="2.5" />
              <path d="M202 60v12l9 6" fill="none" stroke="#0b493b" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              <g>
                <path d="M52 196c0-32 6-56 26-76 5 24-1 54-22 72" fill="#9dbd76" />
                <path d="M52 196c-2-26 3-48 16-63 7 22 1 46-12 61" fill="#6ca578" />
                <path d="M52 196c9-20 25-35 45-40 0 20-16 36-41 42" fill="#8fb584" />
                <path d="M52 196l-1-44" stroke="#3f6b52" strokeWidth="2" strokeLinecap="round" />
              </g>
            </svg>
          </div>
          <div className="history-empty__copy">
            <h2>
              {range === "all"
                ? "No history yet."
                : "No history for this period yet."}
            </h2>
            <p>
              As you complete, miss, reschedule, or recover tasks, they&rsquo;ll appear
              here so you can see how your plans evolve over time.
            </p>
            <ul className="history-empty__hints">
              <li>
                <span className="history-empty__hint-icon history-empty__hint-icon--green" aria-hidden="true">✓</span>
                <span>
                  <strong>Track progress</strong>
                  <small>See what you&rsquo;ve completed</small>
                </span>
              </li>
              <li>
                <span className="history-empty__hint-icon history-empty__hint-icon--purple" aria-hidden="true">↻</span>
                <span>
                  <strong>See adjustments</strong>
                  <small>View missed, recovered, and rescheduled tasks</small>
                </span>
              </li>
              <li>
                <span className="history-empty__hint-icon history-empty__hint-icon--amber" aria-hidden="true">
                  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                    <line x1="2" y1="11" x2="12" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                    <line x1="4" y1="11" x2="4" y2="7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                    <line x1="7" y1="11" x2="7" y2="5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                    <line x1="10" y1="11" x2="10" y2="3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                  </svg>
                </span>
                <span>
                  <strong>Spot patterns</strong>
                  <small>Understand your productivity over time</small>
                </span>
              </li>
            </ul>
            <p className="history-empty__foot">Keep going — your journey will build up here.</p>
          </div>
        </section>
      )}
      {!error && pageEvents.length > 0 && (
        <section className="history-feed" aria-label="Task history timeline">
          {Object.entries(groupByDate(pageEvents)).map(([date, events]) => (
            <section className="history-day" key={date}>
              <h2>{date}</h2>
              <div className="history-timeline">
                {events.map((event) => {
                 const labels = {
  completed: "Completed",
  missed: "Missed",
  overdue: "Overdue",
  rescheduled: "Rescheduled",
  recovered: "Recovered",
  scheduled: "Created",
};

const icons = {
  completed: "✓",
  missed: "!",
  overdue: "◷",
  rescheduled: "↗",
  recovered: "↻",
  scheduled: "+",
};

const label = labels[event.event_type] ?? "History";
const icon = icons[event.event_type] ?? "•";
                  const leftTimestamp =
                    event.event_type === "completed" && event.completed_at
                      ? event.completed_at
                      : event.timestamp;
                  return (
                    <article
                      className={`history-row history-row--${event.event_type}`}
                      key={event.id}
                    >
                      <time dateTime={leftTimestamp}>
                        {formatTime(leftTimestamp)}
                      </time>
                      <span className="history-row__line" aria-hidden="true" />
                      <span className="history-row__icon" aria-hidden="true">
                        {icon}
                      </span>
                      <div className="history-row__content">
                        <div>
                          <h3>{event.task_title ?? "Deleted task"}</h3>
                          <span className="history-row__badge">{label}</span>
                        </div>
                        <EventDetail event={event} />
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          ))}
          {visibleHistory.length > PAGE_SIZE && (
            <footer className="history-pagination">
              <span>
                Showing {start} to {end} of {visibleHistory.length} events
              </span>
              <div>
                <button
                  type="button"
                  disabled={safePage === 1}
                  onClick={() => setPage((current) => current - 1)}
                  aria-label="Previous page"
                >
                  ‹
                </button>
                <span>{safePage}</span>
                <button
                  type="button"
                  disabled={safePage === totalPages}
                  onClick={() => setPage((current) => current + 1)}
                  aria-label="Next page"
                >
                  ›
                </button>
              </div>
            </footer>
          )}
        </section>
      )}
    </section>
  );
}

export default HistoryPage;
