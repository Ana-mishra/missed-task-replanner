import { useEffect, useState } from 'react'
import AppShell from './components/AppShell.jsx'
import TaskCard from './components/TaskCard.jsx'
import TaskForm from './components/TaskForm.jsx'
import { createTask, getTasks, updateTask } from './services/api.js'

function App() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [formMode, setFormMode] = useState(null)
  const [selectedTask, setSelectedTask] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState(null)

  useEffect(() => {
    async function loadTasks() {
      try { setTasks(await getTasks()) } catch (requestError) { setError(requestError.message) } finally { setLoading(false) }
    }
    loadTasks()
  }, [])

  const incompleteTasks = tasks.filter((task) => !task.completed)
  const totalMinutes = incompleteTasks.reduce((total, task) => total + task.duration_minutes, 0)

  function openTaskForm(mode, task = null) { setFormError(null); setSelectedTask(task); setFormMode(mode) }
  function closeTaskForm() { if (!submitting) { setFormMode(null); setSelectedTask(null); setFormError(null) } }
  function replaceTask(updatedTask) { setTasks((currentTasks) => currentTasks.map((task) => task.id === updatedTask.id ? updatedTask : task)) }

  async function handleTaskSubmit(taskData) {
    setSubmitting(true); setFormError(null)
    try {
      if (formMode === 'create') {
        const createdTask = await createTask(taskData)
        setTasks((currentTasks) => [...currentTasks, createdTask])
      } else if (formMode === 'edit') {
        replaceTask(await updateTask(selectedTask.id, { ...selectedTask, ...taskData }))
      } else {
        replaceTask(await updateTask(selectedTask.id, { ...selectedTask, completed: true, status: 'completed', actual_duration_minutes: taskData.actual_duration_minutes }))
      }
      setFormMode(null); setSelectedTask(null)
    } catch (requestError) { setFormError(requestError.message) } finally { setSubmitting(false) }
  }

  return <AppShell><section className="welcome" aria-labelledby="today-heading"><p className="eyebrow">Your gentle reset</p><h1 id="today-heading">Today, one clear step at a time.</h1><p className="welcome__copy">Your plan can adapt when the day does. Start with what is in front of you.</p></section><section className="summary" aria-label="Today’s task summary"><div className="summary__item"><span className="summary__value">{incompleteTasks.length}</span><span className="summary__label">tasks to focus on</span></div><div className="summary__rule" aria-hidden="true" /><div className="summary__item"><span className="summary__value">{totalMinutes}</span><span className="summary__label">estimated minutes</span></div></section><section className="tasks-section" aria-labelledby="task-list-heading"><div className="section-heading"><div><p className="eyebrow">Your list</p><h2 id="task-list-heading">Today’s tasks</h2></div><div className="section-heading__actions">{!loading && !error && <span className="task-count">{tasks.length} total</span>}<button className="button button--primary" type="button" onClick={() => openTaskForm('create')}>Add task</button></div></div>{loading && <p className="state-message">Loading your tasks…</p>}{error && <div className="state-message state-message--error" role="alert"><strong>We could not reach your planner.</strong><p>{error} Make sure the FastAPI backend is running at http://localhost:8000.</p></div>}{!loading && !error && tasks.length === 0 && <div className="empty-state"><span className="empty-state__sprout" aria-hidden="true">⌁</span><h3>Your list is clear</h3><p>No tasks yet. When you add one in the backend, it will appear here.</p><button className="button button--primary" type="button" onClick={() => openTaskForm('create')}>Add your first task</button></div>}{!loading && !error && tasks.length > 0 && <div className="task-list">{tasks.map((task) => <TaskCard key={task.id} task={task} onEdit={() => openTaskForm('edit', task)} onComplete={() => openTaskForm('complete', task)} />)}</div>}</section>{formMode && <TaskForm key={`${formMode}-${selectedTask?.id ?? 'new'}`} mode={formMode} task={selectedTask} onSubmit={handleTaskSubmit} onClose={closeTaskForm} submitting={submitting} error={formError} />}</AppShell>
}

export default App
