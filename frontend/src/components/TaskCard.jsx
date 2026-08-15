function isOverdue(task) {
  return !task.completed && new Date(task.deadline) < new Date()
}

function getUrgency(task) {
  const deadline = new Date(task.deadline)
  const now = new Date()
  const urgentCutoff = new Date(now.getTime() + 24 * 60 * 60 * 1000)
  const mediumCutoff = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000)

  if (deadline <= urgentCutoff) return 'urgent'
  if (deadline <= mediumCutoff) return 'medium'
  return 'low'
}

function formatDeadline(deadline) {
  return new Date(deadline).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function TaskCard({ task, onEdit, onComplete, onDelete }) {
  const overdue = isOverdue(task)
  const urgency = getUrgency(task)
  const state = task.completed
    ? 'Completed'
    : overdue
      ? 'Past due'
      : task.status === 'missed'
        ? 'Needs a reset'
        : 'Pending'
  const className = [
    'task-card',
    task.completed && 'task-card--completed',
    overdue && 'task-card--overdue',
    `task-card--${urgency}`,
  ].filter(Boolean).join(' ')

  return (
    <article className={className}>
      <div className="task-card__main">
        <div className="task-card__heading">
          <span className="task-status" aria-label={`Task status: ${state}`} />
          <div>
            <h3>{task.title}</h3>
            {task.description && <p className="task-card__description">{task.description}</p>}
          </div>
        </div>
        <div className="task-card__meta">
          <span className={`task-card__meta-item priority priority--${task.priority}`}>
            {task.priority} priority
          </span>
          <span className="task-card__meta-item">{task.duration_minutes} min</span>
          <span className="task-card__meta-item">{task.energy_level} energy</span>
        </div>
      </div>
      <div className="task-card__side">
        <div className="task-card__deadline">
          <span className="task-card__state">{state}</span>
          <time dateTime={task.deadline}>
            <span className="task-card__deadline-label">Deadline</span>
            {formatDeadline(task.deadline)}
          </time>
        </div>
        <div className="task-card__actions">
          {task.completed ? (
            <span className="task-card__completed-label">✓ Completed</span>
          ) : (
            <>
              <button className="button button--quiet" type="button" onClick={onEdit}>Edit</button>
              <button className="button button--complete" type="button" onClick={onComplete}>Complete</button>
            </>
          )}
          <button className="button button--quiet button--danger" type="button" onClick={onDelete}>
            Delete
          </button>
        </div>
      </div>
    </article>
  )
}

export default TaskCard
