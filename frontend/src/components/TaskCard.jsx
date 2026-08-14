function isOverdue(task) {
  return !task.completed && new Date(task.deadline) < new Date()
}

function formatDeadline(deadline) {
  return new Date(deadline).toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function TaskCard({ task }) {
  const overdue = isOverdue(task)
  const state = task.completed ? 'Completed' : overdue ? 'Past due' : task.status === 'missed' ? 'Needs a reset' : 'Pending'
  const className = ['task-card', task.completed && 'task-card--completed', overdue && 'task-card--overdue', task.priority === 'high' && 'task-card--high-priority'].filter(Boolean).join(' ')

  return <article className={className}><div className="task-card__main"><div className="task-card__heading"><span className="task-status" aria-label={`Task status: ${state}`} /><div><h3>{task.title}</h3>{task.description && <p className="task-card__description">{task.description}</p>}</div></div><div className="task-card__meta"><span className={`priority priority--${task.priority}`}>{task.priority} priority</span><span>{task.duration_minutes} min</span><span>{task.energy_level} energy</span></div></div><div className="task-card__deadline"><span className="task-card__state">{state}</span><time dateTime={task.deadline}>{formatDeadline(task.deadline)}</time></div></article>
}

export default TaskCard
