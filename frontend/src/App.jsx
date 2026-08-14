import { useEffect, useState } from 'react'

const TASKS_API_URL = 'http://localhost:8000/tasks'

function App() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function loadTasks() {
      try {
        const response = await fetch(TASKS_API_URL)

        if (!response.ok) {
          throw new Error('Could not load tasks from the backend.')
        }

        const taskData = await response.json()
        setTasks(taskData)
      } catch (error) {
        setError(error.message)
      } finally {
        setLoading(false)
      }
    }

    loadTasks()
  }, [])

  return (
    <main>
      <h1>Missed Task Replanner</h1>

      {loading && <p>Loading tasks…</p>}

      {error && (
        <p role="alert">
          {error} Make sure the FastAPI backend is running at http://localhost:8000.
        </p>
      )}

      {!loading && !error && tasks.length === 0 && (
        <p>No tasks yet. Create a task in the backend to see it here.</p>
      )}

      {!loading && !error && tasks.length > 0 && (
        <ul>
          {tasks.map((task) => (
            <li key={task.id}>
              <h2>{task.title}</h2>
              <p>Priority: {task.priority}</p>
              <p>Duration: {task.duration_minutes} minutes</p>
              <p>Deadline: {new Date(task.deadline).toLocaleString()}</p>
              <p>Status: {task.completed ? 'completed' : task.status}</p>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}

export default App
