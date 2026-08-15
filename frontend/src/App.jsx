import { useEffect, useState } from 'react'
import AppShell from './components/AppShell.jsx'
import TaskCard from './components/TaskCard.jsx'
import TaskForm from './components/TaskForm.jsx'
import AvailableTimeCard from './components/AvailableTimeCard.jsx'
import { formatDuration } from './utils/duration.mjs'
import {
  createTask,
  deleteTask,
  getTasks,
  planDay,
  replanTask,
  updateTask,
} from './services/api.js'
import {
  DEFAULT_AVAILABLE_MINUTES,
  getTodayOverloadStatus,
  getPlannedWorkload,
} from './utils/workload.mjs'


function formatDeadline(deadline) {
  return new Date(deadline).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function App() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [mode, setMode] = useState(null)
  const [selected, setSelected] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState(null)
  const [taskToDelete, setTaskToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState(null)
  const [planning, setPlanning] = useState(false)
  const [hasPlanned, setHasPlanned] = useState(false)
  const [plannedTasks, setPlannedTasks] = useState([])
  const [planIsOverloaded, setPlanIsOverloaded] = useState(false)
  const [availableMinutes, setAvailableMinutes] = useState(() => Number(localStorage.getItem('todayAvailableMinutes')) || DEFAULT_AVAILABLE_MINUTES)
  const [capacityChoice, setCapacityChoice] = useState('custom')
  const [isCapacityEditorOpen, setIsCapacityEditorOpen] = useState(false)
  const [isEditingCustomCapacity, setIsEditingCustomCapacity] = useState(false)
  const [previousCapacityChoice, setPreviousCapacityChoice] = useState(null)
  const [savedCustomMinutes, setSavedCustomMinutes] = useState(DEFAULT_AVAILABLE_MINUTES)
  const [customHours, setCustomHours] = useState(6)
  const [customMinutes, setCustomMinutes] = useState(0)
  const [hasChosenCapacity, setHasChosenCapacity] = useState(false)

  useEffect(() => {
    getTasks()
      .then(setTasks)
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false))
  }, [])

  const isCompletedTask = (task) => task.completed || task.status === 'completed'
  const incompleteTasks = tasks.filter((task) => !isCompletedTask(task))
  const completedTasks = tasks.filter(isCompletedTask)
  const totalMinutes = incompleteTasks.reduce(
    (total, task) => total + task.duration_minutes,
    0,
  )
  const currentPlannedTasks = plannedTasks
    .map((plannedTask) => tasks.find((task) => String(task.id) === String(plannedTask.id)))
    .filter((task) => task && !isCompletedTask(task))
  const plannedWorkload = getPlannedWorkload(currentPlannedTasks, availableMinutes)


  function updateAvailableMinutes(minutes) {
    return Number(minutes)
  }

  function openCustomCapacityEditor() {
    setPreviousCapacityChoice(capacityChoice)
    setCapacityChoice('custom')
    setCustomHours(Math.floor(savedCustomMinutes / 60))
    setCustomMinutes(savedCustomMinutes % 60)
    setIsEditingCustomCapacity(true)
  }

  function saveCustomCapacity() {
    const totalMinutes = (Number(customHours) || 0) * 60 + (Number(customMinutes) || 0)
    if (totalMinutes > 0) {
      setSavedCustomMinutes(totalMinutes)
      localStorage.setItem('todayCustomMinutes', String(totalMinutes))
      setCapacityChoice('custom')
      updateAvailableMinutes(totalMinutes)
      setIsEditingCustomCapacity(false)
    }
  }

  function cancelCapacityEditor() {
    if (isEditingCustomCapacity && previousCapacityChoice) setCapacityChoice(previousCapacityChoice)
    setIsEditingCustomCapacity(false)
    setIsCapacityEditorOpen(false)
  }

  const formatHoursAndMinutes = formatDuration

  function openForm(nextMode, task = null) {
    setSelected(task)
    setMode(nextMode)
    setFormError(null)
  }

  async function submitForm(data) {
    setSubmitting(true)

    try {
      let saved

      if (mode === 'create') {
        saved = await createTask(data)
        setTasks((all) => [...all, saved])
      } else if (mode === 'edit') {
        saved = await updateTask(selected.id, { ...selected, ...data })
        setTasks((all) => all.map((task) => (task.id === saved.id ? saved : task)))
      } else {
        saved = await updateTask(selected.id, {
          ...selected,
          completed: true,
          status: 'completed',
          actual_duration_minutes: data.actual_duration_minutes,
        })
        setTasks((all) => all.map((task) => (task.id === saved.id ? saved : task)))
      }

      setMode(null)
      setSelected(null)
    } catch (requestError) {
      setFormError(requestError.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function confirmDelete() {
    setDeleting(true)

    try {
      await deleteTask(taskToDelete.id)
      setTasks((all) => all.filter((task) => task.id !== taskToDelete.id))
      setTaskToDelete(null)
    } catch (requestError) {
      setDeleteError(requestError.message)
    } finally {
      setDeleting(false)
    }
  }
  async function handleMiss(task) {
  setError(null)

  try {
    const now = new Date()
    const availableStart = now
    const availableEnd = new Date(
      now.getTime() + availableMinutes * 60 * 1000,
    )

    const result = await replanTask(task.id, {
      available_start: availableStart.toISOString(),
      available_end: availableEnd.toISOString(),
    })

    const updatedTasks = await getTasks()
    setTasks(updatedTasks)

    setPlannedTasks([])
    setPlanIsOverloaded(false)
    setHasPlanned(false)
  } catch (requestError) {
    setError(requestError.message)
  }
}

  async function handlePlanDay() {
  if (hasPlanned) {
    setHasPlanned(false)
    return
  }

  setPlanning(true)

  try {
    const now = new Date()
    const availableStart = now
    const availableEnd = new Date(
      now.getTime() + availableMinutes * 60 * 1000,
    )

    const result = await planDay({
      available_start: availableStart.toISOString(),
      available_end: availableEnd.toISOString(),
    })

    setPlannedTasks(
      result.schedule.map((item) => ({
        id: item.task_id,
      })),
    )
    setPlanIsOverloaded(result.is_overloaded)
    setHasPlanned(true)
  } catch (requestError) {
    setError(requestError.message)
  } finally {
    setPlanning(false)
  }
}

  function planReason(task) {
    const deadline = new Date(task.deadline)
    if (deadline < new Date()) {
      return 'Overdue'
    }
    if (task.priority === 'high') {
      return 'High priority'
    }
    return 'Closest upcoming deadline'
  }

  const plannedMinutes = currentPlannedTasks.reduce(
    (total, task) => total + task.duration_minutes,
    0,
  )
  const overloadStatus = getTodayOverloadStatus(tasks, availableMinutes)

  return (
    <AppShell>
      <section className="welcome">
        <p className="eyebrow">Your gentle reset</p>
        <h1>Today, one clear step at a time.</h1>
        <p className="welcome__copy">Your plan can adapt when the day does.</p>
      </section>

      <section className="summary">
        <div className="summary__item">
          <span className="summary__value">{incompleteTasks.length}</span>
          <span className="summary__label">tasks to focus on</span>
        </div>
        <div className="summary__rule" />
        <div className="summary__item">
          <span className="summary__value">{formatDuration(totalMinutes)}</span>
          <span className="summary__label">estimated time</span>
        </div>
      </section>

      <section className="tasks-section">
        <div className="section-heading">
          <h2>Today’s tasks</h2>
        </div>

        <AvailableTimeCard availableMinutes={availableMinutes} onSave={setAvailableMinutes} />

        <div className="task-list-actions">
          <button className={`button button--quiet ${hasPlanned ? 'button--plan-open' : ''}`} onClick={handlePlanDay} disabled={planning} aria-expanded={hasPlanned} aria-controls="today-plan">{planning ? 'Planning…' : hasPlanned ? 'Hide plan ×' : 'Plan my day'}</button>
          <button className="button button--primary" onClick={() => openForm('create')}>Add task</button>
        </div>

        <section className="capacity-summary" aria-labelledby="capacity-heading">
          <div>
            <p className="capacity-control__eyebrow">Time available today</p>
            <h3 id="capacity-heading">{hasChosenCapacity ? formatHoursAndMinutes(availableMinutes) : 'Set your available time'}</h3>
            <p>{hasChosenCapacity ? 'available for tasks · Plan My Day will use this time to build today’s plan.' : 'Tell Plan My Day how much time you want to spend on tasks today.'}</p>
          </div>
          <button className="button button--quiet" type="button" onClick={() => setIsCapacityEditorOpen(true)}>
            {hasChosenCapacity ? 'Change time' : 'Set time'}
          </button>
        </section>

        {isCapacityEditorOpen && <div className="modal-backdrop"><section className="capacity-dialog" role="dialog" aria-modal="true" aria-labelledby="capacity-dialog-heading">
          <h2 id="capacity-dialog-heading">How much time do you have available for tasks today?</h2>
          <p>Plan My Day will use this limit when choosing which tasks fit into your day.</p>
          <div className="capacity-control__choices">
            {[120, 240, 360, 480, 600].map((minutes) => <button className={`capacity-choice ${capacityChoice === String(minutes) ? 'capacity-choice--selected' : ''}`} key={minutes} type="button" onClick={() => { setCapacityChoice(String(minutes)); setIsEditingCustomCapacity(false); updateAvailableMinutes(minutes) }}>{minutes / 60}h</button>)}
            <button className={`capacity-choice ${capacityChoice === 'custom' ? 'capacity-choice--selected' : ''}`} type="button" onClick={openCustomCapacityEditor}>Custom</button>
          </div>
          {isEditingCustomCapacity && <div className="capacity-control__custom"><label><input type="number" min="0" max="23" value={customHours} onChange={(event) => setCustomHours(Math.min(23, Math.max(0, Number(event.target.value) || 0)))} /><span>hours</span></label><label><input type="number" min="0" max="59" value={customMinutes} onChange={(event) => setCustomMinutes(Math.min(59, Math.max(0, Number(event.target.value) || 0)))} /><span>minutes</span></label></div>}
          <div className="capacity-dialog__actions"><button className="button button--quiet" type="button" onClick={cancelCapacityEditor}>Cancel</button><button className="button button--primary" type="button" disabled={isEditingCustomCapacity && ((Number(customHours) || 0) * 60 + (Number(customMinutes) || 0) <= 0)} onClick={() => { if (isEditingCustomCapacity) saveCustomCapacity(); setIsCapacityEditorOpen(false) }}>Save time</button></div>
        </section></div>}

        {false && <section className="capacity-control" aria-labelledby="capacity-heading">
          <div className="capacity-control__heading">
            <p className="capacity-control__eyebrow">How much time do you have today?</p>
            {!isEditingCustomCapacity && <>
              <h3 id="capacity-heading">{formatHoursAndMinutes(availableMinutes)}</h3>
              <p>available for tasks</p>
            </>}
          </div>
          {!isEditingCustomCapacity ? <>
            <p className="capacity-control__choose">Choose your time</p>
            <div className="capacity-control__choices" aria-label="Today’s available time">
              {[120, 240, 360, 480, 600].map((minutes) => (
                <button className={`capacity-choice ${capacityChoice === String(minutes) ? 'capacity-choice--selected' : ''}`} key={minutes} type="button" onClick={() => { setCapacityChoice(String(minutes)); setIsEditingCustomCapacity(false); updateAvailableMinutes(minutes) }}>
                  {minutes / 60}h
                </button>
              ))}
              <button className={`capacity-choice ${capacityChoice === 'custom' ? 'capacity-choice--selected' : ''}`} type="button" onClick={openCustomCapacityEditor}>Custom</button>
            </div>
          </> : (
            <div className="capacity-control__custom">
              <p>Custom time</p>
              <label>
                <input
                  type="number"
                  min="0"
                  max="23"
                  step="1"
                  value={customHours}
                  onChange={(event) => setCustomHours(Math.min(23, Math.max(0, Number(event.target.value) || 0)))}
                />
                <span>hours</span>
              </label>
              <label>
                <input
                  type="number"
                  min="0"
                  max="59"
                  step="1"
                  value={customMinutes}
                  onChange={(event) => setCustomMinutes(Math.min(59, Math.max(0, Number(event.target.value) || 0)))}
                />
                <span>minutes</span>
              </label>
              <div className="capacity-control__custom-actions">
                <button className="button button--primary" type="button" onClick={saveCustomCapacity}>Save</button>
                <button className="button button--quiet" type="button" onClick={() => setIsEditingCustomCapacity(false)}>Cancel</button>
              </div>
            </div>
          )}
        </section>}

        {overloadStatus.isOverloaded && (
          <section className="overload-notice" aria-labelledby="overload-heading">
            <div className="overload-notice__copy">
              <p className="overload-notice__eyebrow">Your day looks full</p>
              <h3 id="overload-heading">More needs attention than fits today.</h3>
              <p className="overload-notice__support">
                Plan My Day will prioritize what matters most and leave the rest for later.
              </p>
            </div>
            <div className="overload-notice__limits" aria-label="Daily workload limits">
              <span className="overload-limit">{formatHoursAndMinutes(overloadStatus.availableMinutes)} available</span>
              <span className="overload-limit">{formatHoursAndMinutes(overloadStatus.totalTodayMinutes)} of tasks</span>
              <span className="overload-limit overload-limit--exceeded">{formatHoursAndMinutes(overloadStatus.overloadedByMinutes)} over capacity</span>
            </div>
          </section>
        )}

        {hasPlanned && (
          <section className="plan-panel" id="today-plan" aria-live="polite">
            <div className="plan-panel__header">
              <div>
                <p className="plan-panel__eyebrow">Daily roadmap</p>
                <h3>Your plan for today</h3>
                <p className="plan-panel__subtitle">
                  Your clearest path through today’s priorities.
                </p>
              </div>
            </div>
            {currentPlannedTasks.length === 0 ? (
              <p className="plan-panel__clear">
                {incompleteTasks.length === 0
                  ? 'You’re all clear for today.'
                  : 'No pending task fits into the remaining time today.'}
              </p>
            ) : (
              <>
                <ol className="plan-panel__list">
                  {currentPlannedTasks.map((task, index) => (
                    <li className="plan-panel__item" key={task.id}>
                      <span className="plan-panel__number">{index + 1}</span>
                      <div>
                        <strong>{task.title}</strong>
                        <span className="plan-panel__meta">
                          {formatDuration(task.duration_minutes)} · {task.priority} priority · Due {formatDeadline(task.deadline)}
                        </span>
                        <span className="plan-panel__reason">
                          <span className="plan-panel__reason-label">Why now</span>
                          {planReason(task)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ol>
                <p className="plan-panel__summary">
                  {currentPlannedTasks.length} {currentPlannedTasks.length === 1 ? 'task' : 'tasks'} · {formatDuration(plannedMinutes)} planned
                  {plannedMinutes < availableMinutes && ` · ${formatDuration(availableMinutes - plannedMinutes)} remaining`}
                </p>
              </>
            )}
          </section>
        )}

        {loading && <p className="state-message">Loading your tasks…</p>}
        {error && <p className="state-message state-message--error">{error}</p>}

        {incompleteTasks.length > 0 && (
          <div className="task-list">
            {incompleteTasks.map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onEdit={() => openForm('edit', task)}
                onComplete={() => openForm('complete', task)}
                onMiss={() => handleMiss(task)}
                onDelete={() => setTaskToDelete(task)}
              />
            ))}
          </div>
        )}

        {completedTasks.length > 0 && (
          <section className="completed-section">
            <h2>Completed</h2>
            <div className="task-list">
              {completedTasks.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onEdit={() => openForm('edit', task)}
                  onComplete={() => openForm('complete', task)}
                  onDelete={() => setTaskToDelete(task)}
                />
              ))}
            </div>
          </section>
        )}
      </section>

      {mode && (
        <TaskForm
          key={`${mode}-${selected?.id ?? 'new'}`}
          mode={mode}
          task={selected}
          onSubmit={submitForm}
          onClose={() => !submitting && setMode(null)}
          submitting={submitting}
          error={formError}
        />
      )}

      {taskToDelete && (
        <div className="modal-backdrop">
          <section className="task-form">
            <h2>Delete this task?</h2>
            <p className="completion-copy">This task will be permanently removed.</p>
            {deleteError && <p className="form-error">{deleteError}</p>}
            <div className="task-form__actions">
              <button className="button button--quiet" onClick={() => setTaskToDelete(null)}>
                Cancel
              </button>
              <button
                className="button button--quiet button--danger"
                onClick={confirmDelete}
                disabled={deleting}
              >
                {deleting ? 'Deleting…' : 'Delete task'}
              </button>
            </div>
          </section>
        </div>
      )}
    </AppShell>
  )
}

export default App
