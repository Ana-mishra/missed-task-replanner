const TASKS_API_URL = 'http://localhost:8000/tasks'

export async function getTasks() {
  const response = await fetch(TASKS_API_URL)

  if (!response.ok) {
    throw new Error('Could not load tasks from the backend.')
  }

  return response.json()
}

export async function createTask(taskData) {
  const response = await fetch(TASKS_API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(taskData),
  })

  const data = await response.json()

  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not create the task.')
  }

  return data
}
