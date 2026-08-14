import { useEffect, useRef, useState } from 'react'

const initialValues = {
  title: '',
  description: '',
  duration_minutes: '30',
  custom_hours: '',
  custom_minutes: '',
  date: '',
  time: '',
  priority: 'medium',
  energy_level: 'medium',
}

const durationChoices = [
  { label: '15 min', minutes: 15 },
  { label: '30 min', minutes: 30 },
  { label: '45 min', minutes: 45 },
  { label: '1 hr', minutes: 60 },
  { label: '2 hr', minutes: 120 },
]

const weekdayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function toDateValue(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDate(value) {
  if (!value) return 'Choose a date'
  return new Date(`${value}T00:00:00`).toLocaleDateString([], {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function formatTime(value) {
  if (!value) return 'Choose a time'
  const [hours, minutes] = value.split(':').map(Number)
  return new Date(2000, 0, 1, hours, minutes).toLocaleTimeString([], {
    hour: 'numeric', minute: '2-digit',
  })
}

function getTimeOptions() {
  return Array.from({ length: 96 }, (_, index) => {
    const hours = String(Math.floor(index / 4)).padStart(2, '0')
    const minutes = String((index % 4) * 15).padStart(2, '0')
    return `${hours}:${minutes}`
  })
}

function TaskForm({ onSubmit, onClose, submitting, error }) {
  const [values, setValues] = useState(initialValues)
  const [validationError, setValidationError] = useState(null)
  const [openPicker, setOpenPicker] = useState(null)
  const [calendarMonth, setCalendarMonth] = useState(() => new Date())
  const [isCustomDuration, setIsCustomDuration] = useState(false)
  const pickerArea = useRef(null)
  const timeOptions = getTimeOptions()

  useEffect(() => {
    function closeOnOutsideClick(event) {
      if (pickerArea.current && !pickerArea.current.contains(event.target)) {
        setOpenPicker(null)
      }
    }

    document.addEventListener('mousedown', closeOnOutsideClick)
    return () => document.removeEventListener('mousedown', closeOnOutsideClick)
  }, [])

  function handleChange(event) {
    setValues((currentValues) => ({
      ...currentValues,
      [event.target.name]: event.target.value,
    }))
  }

  function selectDuration(minutes) {
    setIsCustomDuration(minutes === null)
    setValues((currentValues) => ({
      ...currentValues,
      duration_minutes: minutes === null ? currentValues.duration_minutes : String(minutes),
    }))
  }

  function selectDate(date) {
    setValues((currentValues) => ({ ...currentValues, date: toDateValue(date) }))
    setOpenPicker(null)
  }

  function selectTime(time) {
    setValues((currentValues) => ({ ...currentValues, time }))
    setOpenPicker(null)
  }

  function handleSubmit(event) {
    event.preventDefault()
    setValidationError(null)

    if (!values.title.trim()) {
      setValidationError('Please add a task title.')
      return
    }

    const customHours = Number(values.custom_hours || 0)
    const customMinutes = Number(values.custom_minutes || 0)
    const durationMinutes = isCustomDuration
      ? (customHours * 60) + customMinutes
      : Number(values.duration_minutes)

    if (
      isCustomDuration
      && (!Number.isInteger(customHours) || customHours < 0 || !Number.isInteger(customMinutes) || customMinutes < 0 || customMinutes > 59)
    ) {
      setValidationError('Use whole hours and minutes from 0 to 59.')
      return
    }

    if (durationMinutes <= 0) {
      setValidationError('Duration must be greater than zero.')
      return
    }

    if (!values.date || !values.time) {
      setValidationError('Please choose both a date and time for the deadline.')
      return
    }

    onSubmit({
      title: values.title.trim(),
      description: values.description.trim() || null,
      duration_minutes: durationMinutes,
      deadline: `${values.date}T${values.time}:00`,
      priority: values.priority,
      energy_level: values.energy_level,
    })
  }

  const calendarYear = calendarMonth.getFullYear()
  const calendarMonthIndex = calendarMonth.getMonth()
  const firstDay = new Date(calendarYear, calendarMonthIndex, 1).getDay()
  const daysInMonth = new Date(calendarYear, calendarMonthIndex + 1, 0).getDate()
  const calendarDays = Array.from({ length: firstDay + daysInMonth }, (_, index) => index < firstDay ? null : index - firstDay + 1)

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="task-form task-form--redesigned" role="dialog" aria-modal="true" aria-labelledby="task-form-heading">
        <style>{`
          .task-form--redesigned .form-section { margin-top: 1.45rem; }
          .task-form--redesigned .form-section-title { margin: 0 0 .4rem; color: var(--text); font-size: .82rem; font-weight: 700; }
          .task-form--redesigned .form-help { margin: 0; color: var(--muted); font-size: .8rem; }
          .task-form--redesigned .duration-choices { display: flex; flex-wrap: wrap; gap: .45rem; margin-top: .75rem; }
          .task-form--redesigned .duration-choices .button { min-width: 4.3rem; }
          .task-form--redesigned .custom-duration-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: .9rem; }
          .task-form--redesigned .deadline-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: .75rem; }
          .task-form--redesigned .picker-field { position: relative; }
          .task-form--redesigned .picker-label { display: block; margin-bottom: .45rem; font-size: .82rem; font-weight: 700; }
          .task-form--redesigned .picker-trigger { width: 100%; min-height: 2.65rem; display: flex; align-items: center; justify-content: space-between; padding: .7rem .75rem; border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text); background: #fffefc; text-align: left; font-size: .9rem; }
          .task-form--redesigned .picker-trigger:hover { border-color: #bdcdc2; }
          .task-form--redesigned .picker-trigger:focus-visible { outline: 2px solid #9cc3aa; border-color: var(--primary); }
          .task-form--redesigned .picker-icon { color: var(--primary); font-size: 1rem; }
          .task-form--redesigned .picker-popover { position: absolute; z-index: 2; top: calc(100% + .45rem); left: 0; width: min(19.5rem, calc(100vw - 3rem)); padding: .8rem; border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--surface-elevated); box-shadow: var(--shadow-md); }
          .task-form--redesigned .calendar-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: .65rem; font-size: .82rem; font-weight: 750; }
          .task-form--redesigned .calendar-navigation { width: 1.8rem; height: 1.8rem; border: 0; border-radius: 50%; color: var(--primary); background: #edf3ed; font-size: 1.1rem; }
          .task-form--redesigned .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: .2rem; }
          .task-form--redesigned .calendar-weekday { padding-block: .25rem; color: var(--muted); font-size: .65rem; font-weight: 700; text-align: center; }
          .task-form--redesigned .calendar-day { aspect-ratio: 1; border: 0; border-radius: 50%; color: var(--text); background: transparent; font-size: .76rem; }
          .task-form--redesigned .calendar-day:hover { background: #edf3ed; }
          .task-form--redesigned .calendar-day--selected { color: var(--surface); background: var(--primary); }
          .task-form--redesigned .calendar-day--selected:hover { background: var(--primary); }
          .task-form--redesigned .time-list { max-height: 13rem; display: grid; grid-template-columns: repeat(3, 1fr); gap: .35rem; overflow-y: auto; padding-right: .15rem; }
          .task-form--redesigned .time-option { border: 0; border-radius: var(--radius-sm); padding: .45rem .25rem; color: var(--text); background: #f5f7f2; font-size: .75rem; }
          .task-form--redesigned .time-option:hover { background: #e3eee4; }
          .task-form--redesigned .time-option--selected { color: var(--surface); background: var(--primary); }
          .task-form--redesigned .time-option--selected:hover { background: var(--primary); }
          .task-form--redesigned .form-grid { margin-top: 1.45rem; }
          @media (max-width: 540px) { .task-form--redesigned .deadline-fields, .task-form--redesigned .custom-duration-fields { grid-template-columns: 1fr; gap: .75rem; } .task-form--redesigned .picker-popover { width: 100%; } }
        `}</style>

        <div className="task-form__header">
          <div>
            <p className="eyebrow">Task details</p>
            <h2 id="task-form-heading">Add a task</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} disabled={submitting} aria-label="Close form">×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-section">
            <label>
              Task title
              <input name="title" required placeholder="What would you like to make progress on?" value={values.title} onChange={handleChange} />
            </label>
            <label>
              Description <span className="optional">optional</span>
              <textarea name="description" rows="2" placeholder="A little context can make restarting easier." value={values.description} onChange={handleChange} />
            </label>
          </div>

          <div className="form-section">
            <p className="form-section-title">How long?</p>
            <p className="form-help">How long will this take?</p>
            <div className="duration-choices" aria-label="Quick duration choices">
              {durationChoices.map((choice) => <button className={`button ${!isCustomDuration && Number(values.duration_minutes) === choice.minutes ? 'button--primary' : 'button--quiet'}`} type="button" key={choice.minutes} onClick={() => selectDuration(choice.minutes)}>{choice.label}</button>)}
              <button className={`button ${isCustomDuration ? 'button--primary' : 'button--quiet'}`} type="button" onClick={() => selectDuration(null)}>Custom</button>
            </div>
            {isCustomDuration && <div className="custom-duration-fields"><label><span className="picker-label">Hours</span><input name="custom_hours" type="number" min="0" step="1" inputMode="numeric" placeholder="0" value={values.custom_hours} onChange={handleChange} /></label><label><span className="picker-label">Minutes</span><input name="custom_minutes" type="number" min="0" max="59" step="1" inputMode="numeric" placeholder="0" value={values.custom_minutes} onChange={handleChange} /></label></div>}
          </div>

          <div className="form-section" ref={pickerArea}>
            <p className="form-section-title">Deadline</p>
            <div className="deadline-fields">
              <div className="picker-field">
                <span className="picker-label">Date</span>
                <button className="picker-trigger" type="button" onClick={() => setOpenPicker(openPicker === 'date' ? null : 'date')} aria-expanded={openPicker === 'date'}><span>{formatDate(values.date)}</span><span className="picker-icon" aria-hidden="true">◷</span></button>
                {openPicker === 'date' && <div className="picker-popover"><div className="calendar-header"><button className="calendar-navigation" type="button" onClick={() => setCalendarMonth(new Date(calendarYear, calendarMonthIndex - 1, 1))} aria-label="Previous month">‹</button><span>{calendarMonth.toLocaleDateString([], { month: 'long', year: 'numeric' })}</span><button className="calendar-navigation" type="button" onClick={() => setCalendarMonth(new Date(calendarYear, calendarMonthIndex + 1, 1))} aria-label="Next month">›</button></div><div className="calendar-grid">{weekdayNames.map((day) => <span className="calendar-weekday" key={day}>{day}</span>)}{calendarDays.map((day, index) => day ? <button className={`calendar-day ${values.date === toDateValue(new Date(calendarYear, calendarMonthIndex, day)) ? 'calendar-day--selected' : ''}`} type="button" key={day} onClick={() => selectDate(new Date(calendarYear, calendarMonthIndex, day))}>{day}</button> : <span key={`empty-${index}`} />)}</div></div>}
              </div>
              <div className="picker-field">
                <span className="picker-label">Time</span>
                <button className="picker-trigger" type="button" onClick={() => setOpenPicker(openPicker === 'time' ? null : 'time')} aria-expanded={openPicker === 'time'}><span>{formatTime(values.time)}</span><span className="picker-icon" aria-hidden="true">◷</span></button>
                {openPicker === 'time' && <div className="picker-popover"><div className="time-list">{timeOptions.map((time) => <button className={`time-option ${values.time === time ? 'time-option--selected' : ''}`} type="button" key={time} onClick={() => selectTime(time)}>{formatTime(time)}</button>)}</div></div>}
              </div>
            </div>
          </div>

          <div className="form-grid">
            <label>Priority<select name="priority" value={values.priority} onChange={handleChange}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
            <label>Energy needed<select name="energy_level" value={values.energy_level} onChange={handleChange}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
          </div>

          {(validationError || error) && <p className="form-error" role="alert">{validationError || error}</p>}
          <div className="task-form__actions"><button className="button button--quiet" type="button" onClick={onClose} disabled={submitting}>Cancel</button><button className="button button--primary" type="submit" disabled={submitting}>{submitting ? 'Adding…' : 'Add task'}</button></div>
        </form>
      </section>
    </div>
  )
}

export default TaskForm
