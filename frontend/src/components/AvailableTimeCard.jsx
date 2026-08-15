import { useState } from 'react'
import { formatDuration } from '../utils/duration.mjs'

const PRESETS = [120, 240, 360, 480, 600]

function numberValue(value, maximum) {
  const digits = value.replace(/\D/g, '').slice(0, 2)
  return digits === '' ? '' : String(Math.min(maximum, Number(digits)))
}

export default function AvailableTimeCard({ availableMinutes, onSave }) {
  const [isOpen, setIsOpen] = useState(false)
  const [choice, setChoice] = useState(PRESETS.includes(availableMinutes) ? String(availableMinutes) : 'custom')
  const [hours, setHours] = useState(String(Math.floor(availableMinutes / 60)))
  const [minutes, setMinutes] = useState(String(availableMinutes % 60))
  const [error, setError] = useState('')
  const hasSavedTime = localStorage.getItem('todayAvailableMinutes') !== null

  function openEditor() {
    setChoice(PRESETS.includes(availableMinutes) ? String(availableMinutes) : 'custom')
    setHours(String(Math.floor(availableMinutes / 60)))
    setMinutes(String(availableMinutes % 60))
    setError('')
    setIsOpen(true)
  }

  function save() {
    const total = choice === 'custom'
      ? (Number(hours) || 0) * 60 + (Number(minutes) || 0)
      : Number(choice)
    if (total <= 0) {
      setError('Choose at least one minute.')
      return
    }
    onSave(total)
    localStorage.setItem('todayAvailableMinutes', String(total))
    setIsOpen(false)
  }

  return <>
    <section className="available-time-card" aria-labelledby="available-time-heading">
      <div className="available-time-card__header">
        <p className="available-time-card__eyebrow">Your time today</p>
        <button className="button button--quiet" type="button" onClick={openEditor}>{hasSavedTime ? 'Change time' : 'Set time'}</button>
      </div>
      <div className="available-time-card__content">
        <h3 id="available-time-heading" className="available-time-card__duration">{hasSavedTime ? formatDuration(availableMinutes) : 'Set your available time'}</h3>
        <p className="available-time-card__caption">available for tasks</p>
        <p className="available-time-card__help">Plan My Day uses this time to choose which tasks realistically fit into your day.</p>
      </div>
    </section>

    {isOpen && <div className="modal-backdrop"><section className="available-time-dialog" role="dialog" aria-modal="true" aria-labelledby="time-dialog-title">
      <p className="available-time-card__eyebrow">Time available today</p>
      <h2 id="time-dialog-title">How much time do you have available for tasks today?</h2>
      <p className="available-time-dialog__help">Plan My Day will use this time to choose which tasks realistically fit into your day.</p>
      <p className="available-time-dialog__label">Quick choices</p>
      <div className="available-time-dialog__choices">
        {PRESETS.map((preset) => <button key={preset} type="button" className={`time-choice ${choice === String(preset) ? 'time-choice--selected' : ''}`} onClick={() => { setChoice(String(preset)); setError('') }}>{formatDuration(preset)}</button>)}
        <button type="button" className={`time-choice ${choice === 'custom' ? 'time-choice--selected' : ''}`} onClick={() => setChoice('custom')}>Custom</button>
      </div>
      {choice === 'custom' && <div className="available-time-dialog__custom">
        <p>Custom time</p>
        <label>Hours<input inputMode="numeric" value={hours} onChange={(event) => setHours(numberValue(event.target.value, 23))} /></label>
        <label>Minutes<input inputMode="numeric" value={minutes} onChange={(event) => setMinutes(numberValue(event.target.value, 59))} /></label>
      </div>}
      {error && <p className="available-time-dialog__error">{error}</p>}
      <div className="available-time-dialog__actions"><button className="button button--quiet" type="button" onClick={() => setIsOpen(false)}>Cancel</button><button className="button button--primary" type="button" onClick={save}>Save time</button></div>
    </section></div>}
  </>
}
