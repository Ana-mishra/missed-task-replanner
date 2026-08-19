import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { formatDuration } from '../utils/duration.mjs'

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
  actual_hours: '',
  actual_minutes: '',
}

const durationChoices = [15, 30, 45, 60, 120]

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

function valuesForTask(task) {
  if (!task) return initialValues
  const deadline = task.deadline || ''
  const isPreset = durationChoices.includes(task.duration_minutes)
  return {
    ...initialValues,
    title: task.title,
    description: task.description || '',
    duration_minutes: String(task.duration_minutes),
    custom_hours: isPreset ? '' : String(Math.floor(task.duration_minutes / 60)),
    custom_minutes: isPreset ? '' : String(task.duration_minutes % 60),
    date: deadline.slice(0, 10),
    time: deadline.slice(11, 16),
    priority: task.priority,
    energy_level: task.energy_level,
  }
}

function TaskForm({ mode = 'create', task, onSubmit, onClose, submitting, error }) {
  const [values, setValues] = useState(() => valuesForTask(task))
  const [validationError, setValidationError] = useState(null)
  const [deadlineConflict, setDeadlineConflict] = useState(null)
  const [openPicker, setOpenPicker] = useState(null)
  const [calendarMonth, setCalendarMonth] = useState(() => new Date())
  const [isCustomDuration, setIsCustomDuration] = useState(
    () => Boolean(task) && !durationChoices.includes(task.duration_minutes),
  )
  const pickerArea = useRef(null)
  const timeOptions = getTimeOptions()
  const isCompletion = mode === 'complete'
  const deadlineProtected = Boolean(
    mode === 'edit'
    && task
    && !task.completed
    && (
      task.status === 'missed'
      || task.was_replanned
      || new Date(task.deadline) < new Date()
    )
  )

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
  const { name, value } = event.target

  if (name === 'actual_hours') {
    const numericValue = value === '' ? '' : Math.min(Number(value), 23)

    setValues((currentValues) => ({
      ...currentValues,
      [name]: numericValue === '' ? '' : String(numericValue),
    }))
    return
  }

  if (name === 'actual_minutes') {
    const numericValue = value === '' ? '' : Math.min(Number(value), 59)

    setValues((currentValues) => ({
      ...currentValues,
      [name]: numericValue === '' ? '' : String(numericValue),
    }))
    return
  }

  setValues((currentValues) => ({
    ...currentValues,
    [name]: value,
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
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    if (date < today) return
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

    if (isCompletion) {
  const actualHours = Number(values.actual_hours || 0)
  const actualMinutes = Number(values.actual_minutes || 0)

  const hasActualDuration =
    values.actual_hours !== '' || values.actual_minutes !== ''

  if (
    !Number.isInteger(actualHours)
    || actualHours < 0
    || !Number.isInteger(actualMinutes)
    || actualMinutes < 0
    || actualMinutes > 59
  ) {
    setValidationError('Use whole hours and minutes from 0 to 59.')
    return
  }

  const actualDuration = (actualHours * 60) + actualMinutes

  if (hasActualDuration && actualDuration <= 0) {
    setValidationError('Actual duration must be greater than zero.')
    return
  }

  onSubmit({
    actual_duration_minutes: hasActualDuration ? actualDuration : null,
  })

  return
}

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

    if (!deadlineProtected && (!values.date || !values.time)) {
      setValidationError('Please choose both a date and time for the deadline.')
      return
    }

    if (!deadlineProtected && new Date(`${values.date}T00:00:00`) < new Date(new Date().setHours(0, 0, 0, 0))) {
      setValidationError('Deadline cannot be before today.')
      return
    }

    const taskData = {
      title: values.title.trim(),
      description: values.description.trim() || null,
      duration_minutes: durationMinutes,
      deadline: deadlineProtected ? task.deadline : `${values.date}T${values.time}:00`,
      priority: values.priority,
      energy_level: values.energy_level,
    }
    const minutesUntilDeadline = Math.floor((new Date(taskData.deadline) - new Date()) / 60000)
    if (!deadlineProtected && !deadlineConflict && durationMinutes > minutesUntilDeadline) {
      setDeadlineConflict({ durationMinutes, minutesUntilDeadline, taskData })
      return
    }
    onSubmit({ ...taskData, deadline_conflicted: deadlineProtected ? task.deadline_conflicted : Boolean(deadlineConflict) })
  }

  const calendarYear = calendarMonth.getFullYear()
  const calendarMonthIndex = calendarMonth.getMonth()
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const firstDay = new Date(calendarYear, calendarMonthIndex, 1).getDay()
  const daysInMonth = new Date(calendarYear, calendarMonthIndex + 1, 0).getDate()
  const calendarDays = Array.from({ length: firstDay + daysInMonth }, (_, index) => index < firstDay ? null : index - firstDay + 1)

  return createPortal(
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
          .task-form--redesigned .deadline-locked { min-height: 2.65rem; display: grid; align-content: center; gap: .15rem; padding: .58rem .75rem; border: 1px solid #d9dfd5; border-radius: var(--radius-sm); background: #f5f6f1; color: var(--muted); font-size: .82rem; }
          .task-form--redesigned .deadline-locked strong { color: var(--text); font-weight: 700; }
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
          .task-form--redesigned .calendar-day--today { color: var(--surface); background: var(--primary); box-shadow: 0 0 0 2px #dce9d6; }
          .task-form--redesigned .calendar-day--disabled { color: #a9b0ab; cursor: not-allowed; }
          .task-form--redesigned .calendar-day--disabled:hover { background: transparent; }
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
            <h2 id="task-form-heading">{isCompletion ? 'Complete task' : mode === 'edit' ? 'Edit task' : 'Add a task'}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} disabled={submitting} aria-label="Close form">×</button>
        </div>

        <form onSubmit={handleSubmit}>
         {isCompletion ? (
  <div className="form-section">
    <p className="form-section-title">
      Estimated duration: {formatDuration(task.duration_minutes)}
    </p>

    <p className="form-help">
      If you know it, add the actual time this task took.
    </p>

    <div className="custom-duration-fields">
      <label>
        <span className="picker-label">Hours</span>
        <input
          name="actual_hours"
          type="number"
          min="0"
          max="23"
          step="1"
          inputMode="numeric"
          placeholder="0"
          value={values.actual_hours}
          onChange={handleChange}
        />
      </label>

      <label>
        <span className="picker-label">Minutes</span>
        <input
          name="actual_minutes"
          type="number"
          min="0"
          max="59"
          step="1"
          inputMode="numeric"
          placeholder="0"
          value={values.actual_minutes}
          onChange={handleChange}
        />
      </label>
    </div>
  </div>
) : <>
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
              {durationChoices.map((minutes) => <button className={`button ${!isCustomDuration && Number(values.duration_minutes) === minutes ? 'button--primary' : 'button--quiet'}`} type="button" key={minutes} onClick={() => selectDuration(minutes)}>{formatDuration(minutes)}</button>)}
              <button className={`button ${isCustomDuration ? 'button--primary' : 'button--quiet'}`} type="button" onClick={() => selectDuration(null)}>Custom</button>
            </div>
            {isCustomDuration && <div className="custom-duration-fields"><label><span className="picker-label">Hours</span><input name="custom_hours" type="number" min="0" step="1" inputMode="numeric" placeholder="0" value={values.custom_hours} onChange={handleChange} /></label><label><span className="picker-label">Minutes</span><input name="custom_minutes" type="number" min="0" max="59" step="1" inputMode="numeric" placeholder="0" value={values.custom_minutes} onChange={handleChange} /></label></div>}
          </div>

          <div className="form-section" ref={pickerArea}>
            <p className="form-section-title">Deadline</p>
            {deadlineProtected ? <>
              <p className="form-help">This deadline is preserved because the task is overdue, missed, or has been replanned.</p>
              <div className="deadline-locked"><strong>{formatDate(values.date)} · {formatTime(values.time)}</strong><span>Deadline locked to preserve the task’s history.</span></div>
            </> : <div className="deadline-fields">
              <div className="picker-field">
                <span className="picker-label">Date</span>
                <button className="picker-trigger" type="button" onClick={() => setOpenPicker(openPicker === 'date' ? null : 'date')} aria-expanded={openPicker === 'date'}><span>{formatDate(values.date)}</span><span className="picker-icon" aria-hidden="true">◷</span></button>
                {openPicker === 'date' && <div className="picker-popover"><div className="calendar-header"><button className="calendar-navigation" type="button" onClick={() => setCalendarMonth(new Date(calendarYear, calendarMonthIndex - 1, 1))} aria-label="Previous month">‹</button><span>{calendarMonth.toLocaleDateString([], { month: 'long', year: 'numeric' })}</span><button className="calendar-navigation" type="button" onClick={() => setCalendarMonth(new Date(calendarYear, calendarMonthIndex + 1, 1))} aria-label="Next month">›</button></div><div className="calendar-grid">{weekdayNames.map((day) => <span className="calendar-weekday" key={day}>{day}</span>)}{calendarDays.map((day, index) => { const calendarDate = day && new Date(calendarYear, calendarMonthIndex, day); const isPast = calendarDate && calendarDate < today; const isToday = calendarDate && toDateValue(calendarDate) === toDateValue(today); return day ? <button className={`calendar-day ${values.date === toDateValue(calendarDate) ? 'calendar-day--selected' : ''} ${isToday ? 'calendar-day--today' : ''} ${isPast ? 'calendar-day--disabled' : ''}`} type="button" key={day} disabled={isPast} onClick={() => selectDate(calendarDate)}>{day}</button> : <span key={`empty-${index}`} /> })}</div></div>}
              </div>
              <div className="picker-field">
                <span className="picker-label">Time</span>
                <button className="picker-trigger" type="button" onClick={() => setOpenPicker(openPicker === 'time' ? null : 'time')} aria-expanded={openPicker === 'time'}><span>{formatTime(values.time)}</span><span className="picker-icon" aria-hidden="true">◷</span></button>
                {openPicker === 'time' && <div className="picker-popover"><div className="time-list">{timeOptions.map((time) => <button className={`time-option ${values.time === time ? 'time-option--selected' : ''}`} type="button" key={time} onClick={() => selectTime(time)}>{formatTime(time)}</button>)}</div></div>}
              </div>
            </div>}
          </div>

          <div className="form-grid">
            <label>Priority<select name="priority" value={values.priority} onChange={handleChange}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
            <label>Energy needed<select name="energy_level" value={values.energy_level} onChange={handleChange}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
          </div>
          </>}

          {(validationError || error) && <p className="form-error" role="alert">{validationError || error}</p>}
          {deadlineConflict && <div className="deadline-conflict"><strong>Deadline may not be realistic</strong><p>This task needs {formatDuration(deadlineConflict.durationMinutes)}, but only {formatDuration(Math.max(0, deadlineConflict.minutesUntilDeadline))} remain until its deadline.</p><div><button className="button button--quiet" type="button" onClick={() => setDeadlineConflict(null)}>Adjust task</button><button className="button button--primary" type="button" onClick={() => onSubmit({ ...deadlineConflict.taskData, deadline_conflicted: true })}>Save anyway</button></div></div>}
          <div className="task-form__actions"><button className="button button--quiet" type="button" onClick={onClose} disabled={submitting}>Cancel</button><button className="button button--primary" type="submit" disabled={submitting}>{submitting ? 'Saving…' : isCompletion ? 'Complete task' : mode === 'edit' ? 'Save changes' : 'Add task'}</button></div>
        </form>
      </section>
    </div>
  , document.body)
}

export default TaskForm
