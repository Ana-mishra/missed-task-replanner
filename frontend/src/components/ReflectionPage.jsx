import { useEffect, useMemo, useRef, useState } from "react";
import { getDailyReflection, saveDailyReflection } from "../services/api.js";
import { formatDuration } from "../utils/duration.mjs";

const MOODS = [
  { value: "tough", face: "sad", label: "Tough" },
  { value: "okay", face: "slightly-sad", label: "Okay" },
  { value: "neutral", face: "neutral", label: "Neutral" },
  { value: "good", face: "happy", label: "Good" },
  { value: "great", face: "very-happy", label: "Great" },
];

function localDateValue() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function initialForm(reflection) {
  return {
    mood: reflection?.mood ?? null,
    went_well: reflection?.went_well ?? "",
    could_be_better: reflection?.could_be_better ?? "",
    note_to_self: reflection?.note_to_self ?? "",
    tomorrow_step: reflection?.tomorrow_step ?? "",
  };
}

function ReflectionPage({ availableMinutes }) {
  const [selectedDate, setSelectedDate] = useState(localDateValue);
  const [reflection, setReflection] = useState(null);
  const [form, setForm] = useState(initialForm());
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const calendarRef = useRef(null);
  const isEditingRef = useRef(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const isToday = selectedDate === localDateValue();
  const isPastDate = selectedDate < localDateValue();
  const [calendarOpen, setCalendarOpen] = useState(false);
const [calendarMonth, setCalendarMonth] = useState(() => new Date());

const calendarYear = calendarMonth.getFullYear();
const calendarMonthIndex = calendarMonth.getMonth();

const today = new Date();
today.setHours(0, 0, 0, 0);
const todayValue = localDateValue();

const firstDay = new Date(
  calendarYear,
  calendarMonthIndex,
  1,
).getDay();

const daysInMonth = new Date(
  calendarYear,
  calendarMonthIndex + 1,
  0,
).getDate();

const calendarDays = Array.from(
  { length: firstDay + daysInMonth },
  (_, index) =>
    index < firstDay ? null : index - firstDay + 1,
);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    setSuccess(null);

     // Every time the selected date changes, start in view mode.
  isEditingRef.current = false;
  setIsEditing(false);

    getDailyReflection(selectedDate)
      .then((result) => {
        if (!active) return;
        setReflection(result)
setForm(initialForm(result))

const hasSavedReflection =
  result?.mood != null ||
  Boolean(result?.went_well) ||
  Boolean(result?.could_be_better) ||
  Boolean(result?.note_to_self) ||
  Boolean(result?.tomorrow_step)

if (!hasSavedReflection && !isPastDate) {
  isEditingRef.current = true;
  setIsEditing(true);
}
      })
      .catch((requestError) => active && setError(requestError.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [selectedDate]);

  useEffect(() => {
  function handleOutsideClick(event) {
    if (
      calendarRef.current &&
      !calendarRef.current.contains(event.target)
    ) {
      setCalendarOpen(false);
    }
  }

  if (calendarOpen) {
    document.addEventListener("mousedown", handleOutsideClick);
  }

  return () => {
    document.removeEventListener("mousedown", handleOutsideClick);
  };
}, [calendarOpen]);

  const glanceRows = useMemo(
    () => [
      [
        "Completed",
        reflection?.completed ?? 0,
        "reflection-glance__dot--complete",
      ],
      ["Missed", reflection?.missed ?? 0, "reflection-glance__dot--missed"],
      [
        "Recovered",
        reflection?.recovered ?? 0,
        "reflection-glance__dot--recovered",
      ],
    ],
    [reflection],
  );

  function update(field, value) {
  if (isPastDate) return;

  setSuccess(null);
  setForm((current) => ({ ...current, [field]: value }));
}

  async function handleSave(event) {
    console.log("HANDLE SAVE CALLED", event.nativeEvent?.submitter);
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const saved = await saveDailyReflection(selectedDate, form);
      setReflection(saved)
setForm(initialForm(saved))
setIsEditing(false)
setSuccess("Reflection saved.");
window.setTimeout(() => {
  setSuccess(null);
}, 2000);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  }
  function handleEdit(event) {
  event.preventDefault();

  if (isPastDate) return;

  setSuccess(null);
  setError(null);
  isEditingRef.current = true;
  setIsEditing(true);
}
  console.log("IS EDITING:", isEditing)
  const availableLabel = isToday
    ? formatDuration(availableMinutes)
    : reflection?.available_minutes == null
      ? "Not set"
      : formatDuration(reflection.available_minutes);

  return (
    <section className="reflection-page">
      <header className="reflection-page__header">
        <div>
          <h1>
            Reflection <span aria-hidden="true">🌿</span>
          </h1>
          <p>Pause. Reflect. Grow.</p>
        </div>
        <div
  className="reflection-date-picker"
  ref={calendarRef}
>
  <span className="sr-only">Reflection date</span>

  <button
    className="reflection-date-picker__trigger"
    type="button"
    onClick={() => setCalendarOpen((open) => !open)}
    aria-expanded={calendarOpen}
  >
    <span>
      {new Date(`${selectedDate}T00:00:00`).toLocaleDateString([], {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })}
    </span>

    <span className="reflection-date-picker__icon" aria-hidden="true">
  <svg
    viewBox="0 0 24 24"
    width="17"
    height="17"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="3" y="4" width="18" height="17" rx="2" />
    <line x1="16" y1="2.5" x2="16" y2="6" />
    <line x1="8" y1="2.5" x2="8" y2="6" />
    <line x1="3" y1="9" x2="21" y2="9" />
  </svg>
</span>
  </button>

  {calendarOpen && (
    <div className="reflection-calendar">
      <div className="reflection-calendar__header">
        <button
  type="button"
  disabled={
    calendarYear === today.getFullYear() &&
    calendarMonthIndex === today.getMonth()
  }
  onClick={() =>
    setCalendarMonth(
      new Date(calendarYear, calendarMonthIndex + 1, 1),
    )
  }
  aria-label="Next month"
>
  ›
</button>

        <strong>
          {calendarMonth.toLocaleDateString([], {
            month: "long",
            year: "numeric",
          })}
        </strong>

        <button
          type="button"
          onClick={() =>
            setCalendarMonth(
              new Date(calendarYear, calendarMonthIndex + 1, 1),
            )
          }
          aria-label="Next month"
        >
          ›
        </button>
      </div>

      <div className="reflection-calendar__grid">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(
          (day) => (
            <span
              className="reflection-calendar__weekday"
              key={day}
            >
              {day}
            </span>
          ),
        )}

        {calendarDays.map((day, index) => {
          const calendarDate =
            day &&
            new Date(calendarYear, calendarMonthIndex, day);

          const dateValue = calendarDate
            ? calendarDate.toISOString().slice(0, 10)
            : null;

          const isSelected = dateValue === selectedDate;
          const isTodayDate = dateValue === todayValue;
          const isFutureDate = dateValue > todayValue;

          return day ? (
            <button
  type="button"
  key={day}
  disabled={isFutureDate}
  className={`reflection-calendar__day ${
    isSelected && !isTodayDate
      ? "reflection-calendar__day--selected"
      : ""
  } ${
    isTodayDate
      ? "reflection-calendar__day--today"
      : ""
  }`}
  onClick={() => {
    if (isFutureDate) return;

    setSelectedDate(dateValue);
    setCalendarOpen(false);
  }}
>
  {day}
</button>
          ) : (
            <span key={`empty-${index}`} />
          );
        })}
      </div>
    </div>
  )}
</div>
      </header>

      <section className="reflection-intro">
        <span className="reflection-intro__quote" aria-hidden="true">
          “
        </span>
        <p>
          Reflection turns experience into insight and insight into progress.
        </p>
        <span className="reflection-intro__leaf" aria-hidden="true">
          ❧
        </span>
      </section>

      <form className="reflection-layout" onSubmit={handleSave}>
        <main className="reflection-main">
          <section
            className="reflection-surface reflection-mood"
            aria-labelledby="mood-heading"
          >
            <h2 id="mood-heading">How was your day overall?</h2>
            <div
              className="reflection-mood__choices"
              role="radiogroup"
              aria-label="Your mood"
            >
              {MOODS.map((mood) => (
                <button
  className={`reflection-mood__choice ${
    form.mood === mood.value ? "reflection-mood__choice--selected" : ""
  }`}
  type="button"
  disabled={!isEditing || saving || isPastDate}
  onClick={() => update("mood", mood.value)}
>
                  <span
  className={`mood-face mood-face--${mood.face}`}
  aria-hidden="true"
>
  <i />
</span>
                  <strong>{mood.label}</strong>
                </button>
              ))}
            </div>
          </section>

          <section className="reflection-surface reflection-writing">
            <label htmlFor="went-well">
              <span>What went well today?</span>
              <small>Celebrate the wins, no matter how small.</small>
            </label>
            <textarea
  id="went-well"
  maxLength={500}
  placeholder="Write your thoughts..."
  value={form.went_well}
  onChange={(event) => update("went_well", event.target.value)}
  readOnly={!isEditing || isPastDate}
/>
            <span className="reflection-writing__count">
              {form.went_well.length} / 500
            </span>
            <div className="reflection-writing__rule" />
            <label htmlFor="could-be-better">
              <span>What could have gone better?</span>
              <small>Be honest with yourself. It’s okay.</small>
            </label>
           <textarea 
  id="could-be-better" 
  maxLength="500" 
  placeholder="Write your thoughts..." 
  value={form.could_be_better} 
  onChange={(event) => 
    update("could_be_better", event.target.value) 
  }
  readOnly={!isEditing || isPastDate}
/>
            <span className="reflection-writing__count">
              {form.could_be_better.length} / 500
            </span>
          </section>
        </main>

        <aside className="reflection-side">
          <section
            className="reflection-surface reflection-glance"
            aria-labelledby="glance-heading"
          >
            <h2 id="glance-heading">Today at a glance</h2>
            {glanceRows.map(([label, value, tone]) => (
              <p key={label}>
                <span className={`reflection-glance__dot ${tone}`} />
                {label}
                <strong>{value}</strong>
              </p>
            ))}
            <div className="reflection-glance__rule" />
            <p>
              <span className="reflection-glance__icon" aria-hidden="true">
                ◷
              </span>
              Scheduled work
              <strong>
                {formatDuration(reflection?.planned_work_minutes ?? 0)}
              </strong>
            </p>
            <p>
              <span className="reflection-glance__icon" aria-hidden="true">
                ◴
              </span>
              Available time<strong>{availableLabel}</strong>
            </p>
          </section>

          <section className="reflection-surface reflection-note">
            <label htmlFor="note-to-self">
              <span>A note to yourself</span>
              <small>Leave a kind note for your future self.</small>
            </label>
            <textarea
              id="note-to-self"
              maxLength="500"
              placeholder="Write a kind note..."
              value={form.note_to_self}
              onChange={(event) => update("note_to_self", event.target.value)}
              readOnly={!isEditing || isPastDate}
            />
            <span className="reflection-writing__count">
              {form.note_to_self.length} / 500
            </span>
          </section>

          <section className="reflection-surface reflection-streak">
            <h2>Reflection streak</h2>
            <p>
              You’ve reflected for {reflection?.streak_days ?? 0} day
              {reflection?.streak_days === 1 ? "" : "s"} in a row!
            </p>
            <div className="reflection-streak__days">
              {(reflection?.recent_streak_days ?? []).map((day) => (
                <span
                  className={
                    day.reflected
                      ? "reflection-streak__day reflection-streak__day--done"
                      : "reflection-streak__day"
                  }
                  key={day.date}
                >
                  <i aria-hidden="true">{day.reflected ? "✓" : ""}</i>
                  <small>
                    {new Date(`${day.date}T12:00:00`).toLocaleDateString([], {
                      weekday: "short",
                    })}
                  </small>
                </span>
              ))}
            </div>
          </section>
        </aside>

        <footer className="reflection-save reflection-surface">
          <label htmlFor="tomorrow-step">
            <span>One small step for tomorrow</span>
            <small>What’s one thing you will focus on tomorrow?</small>
          </label>
          <input
            id="tomorrow-step"
            maxLength="500"
            placeholder="e.g., Wake up early, focus on studies, drink more water..."
            value={form.tomorrow_step}
            onChange={(event) => update("tomorrow_step", event.target.value)}
            readOnly={!isEditing || isPastDate}
          />
          {isPastDate ? null : isEditing ? (
  <button
    className="button button--primary"
    disabled={saving || loading}
    type="submit"
  >
    {saving ? "Saving…" : reflection ? "Save changes" : "Save reflection"}
  </button>
) : (
  <button
    className="reflection-edit-button"
    type="button"
    onClick={handleEdit}
  >
    Edit reflection
  </button>
)}
          {success && (
            <p className="reflection-save__success" role="status">
              {success}
            </p>
          )}
          {error && (
            <p className="reflection-save__error" role="alert">
              {error}
            </p>
          )}
        </footer>
      </form>
    </section>
  );
}

export default ReflectionPage;
