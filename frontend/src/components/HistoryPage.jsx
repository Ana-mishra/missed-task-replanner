import { useEffect, useMemo, useRef, useState } from "react";
import { getHistory, getHistorySummary } from "../services/api.js";

const PAGE_SIZE = 10;
const FILTERS = [
  ["all", "All"],
  ["scheduled", "Scheduled"],
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
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
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

function HistoryPage() {
  const [history, setHistory] = useState([]);
  const [summary, setSummary] = useState({
  completed: 0,
  missed: 0,
  recovered: 0,
  rescheduled: 0,
});
  const [filter, setFilter] = useState("all");
  const [isRangeOpen, setIsRangeOpen] = useState(false);
  const rangeDropdownRef = useRef(null);
  const [query, setQuery] = useState("");
  const [range, setRange] = useState("week");
  const [filtersOpen, setFiltersOpen] = useState(true);
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

  getHistory({ range })
    .then(setHistory)
    .catch((requestError) => setError(requestError.message))
    .finally(() => setLoading(false));
}, [range]);

useEffect(() => {
  getHistorySummary({ range })
    .then(setSummary)
    .catch((requestError) => setError(requestError.message));
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
    <strong>{summary.completed}</strong>
  </div>
</article>

<article className="history-summary__card history-summary__card--missed">
  <span>!</span>
  <div>
    <p>Missed events</p>
    <strong>{summary.missed}</strong>
  </div>
</article>

<article className="history-summary__card history-summary__card--recovered">
  <span>↻</span>
  <div>
    <p>Recovery events</p>
    <strong>{summary.recovered}</strong>
  </div>
</article>

<article className="history-summary__card history-summary__card--rescheduled">
  <span>↗</span>
  <div>
    <p>Reschedule events</p>
    <strong>{summary.rescheduled}</strong>
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
      {loading && <p className="state-message">Loading your history…</p>}
      {error && <p className="state-message state-message--error">{error}</p>}
      {!loading && !error && pageEvents.length === 0 && (
        <section className="history-empty">
          <span aria-hidden="true">🌱</span>
          <h2>
            {range === "all"
              ? "No history yet."
              : "No history for this period yet."}
          </h2>
          <p>
            Complete, miss, or replan a task and your journey will appear here.
          </p>
        </section>
      )}
      {!loading && !error && pageEvents.length > 0 && (
        <section className="history-feed" aria-label="Task history timeline">
          {Object.entries(groupByDate(pageEvents)).map(([date, events]) => (
            <section className="history-day" key={date}>
              <h2>{date}</h2>
              <div className="history-timeline">
                {events.map((event) => {
                  console.log("HISTORY EVENT:", event);
                 const labels = {
  completed: "Completed",
  missed: "Missed",
  overdue: "Overdue",
  rescheduled: "Rescheduled",
  recovered: "Recovered",
  scheduled: "Scheduled",
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
