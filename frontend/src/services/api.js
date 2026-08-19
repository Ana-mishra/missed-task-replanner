const TASKS_API_URL = 'http://localhost:8000/tasks'

export async function getTasks() {
  const response = await fetch(TASKS_API_URL)

  if (!response.ok) {
    throw new Error('Could not load tasks from the backend.')
  }

  return response.json()
}

export async function getTaskHistory() {
  const response = await fetch('http://localhost:8000/task-history')

  if (!response.ok) {
    throw new Error('Could not load task history from the backend.')
  }

  return response.json()
}

export async function getHistory(params = {}) {
  const query = new URLSearchParams()

  if (params.range) {
    query.set('range', params.range)
  }

  if (params.eventType) {
    query.set('event_type', params.eventType)
  }

  if (params.startDate) {
    query.set('start_date', params.startDate)
  }

  if (params.endDate) {
    query.set('end_date', params.endDate)
  }

  const queryString = query.toString()
  const url = `http://localhost:8000/history${queryString ? `?${queryString}` : ''}`

  const response = await fetch(url)

  if (!response.ok) {
    throw new Error('Could not load history from the backend.')
  }

  return response.json()
}

export async function getHistorySummary(params = {}) {
  const query = new URLSearchParams()

  if (params.range) {
    query.set('range', params.range)
  }

  if (params.startDate) {
    query.set('start_date', params.startDate)
  }

  if (params.endDate) {
    query.set('end_date', params.endDate)
  }

  const queryString = query.toString()
  const url = `http://localhost:8000/history/summary${queryString ? `?${queryString}` : ''}`

  const response = await fetch(url)

  if (!response.ok) {
    throw new Error('Could not load history summary from the backend.')
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

export async function updateTask(taskId, taskData) {
  const response = await fetch(`${TASKS_API_URL}/${taskId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(taskData),
  })

  const data = await response.json()

  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not update the task.')
  }

  return data
}

export async function deleteTask(taskId) {
  const response = await fetch(`${TASKS_API_URL}/${taskId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    let message = 'Could not delete the task.'
    try {
      const data = await response.json()
      if (typeof data.detail === 'string') message = data.detail
    } catch {
      // The backend may return an empty error response.
    }
    throw new Error(message)
  }
}

export async function planDay(planData) {
  const response = await fetch('http://127.0.0.1:8000/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(planData),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not create a plan.')
  }
  return data
}
export async function replanTask(taskId, planData) {
  const response = await fetch(`http://127.0.0.1:8000/replan/${taskId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(planData),
  })

  const data = await response.json()

  if (!response.ok) {
    throw new Error(
      typeof data.detail === 'string'
        ? data.detail
        : 'Could not replan the task.',
    )
  }

  return data
}
export async function recommendTask() {
  const response = await fetch('http://127.0.0.1:8000/recommend')

  const data = await response.json()

  if (!response.ok) {
    throw new Error(
      typeof data.detail === 'string'
        ? data.detail
        : 'Could not get a recommendation.',
    )
  }

  return data
}

async function getAnalytics(path, message) {
  const response = await fetch(`http://127.0.0.1:8000/analytics/${path}`)
  const data = await response.json()
  if (!response.ok) throw new Error(message)
  return data
}

export function getProgress() {
  return getAnalytics('progress', 'Could not load progress.')
}

export function getWeeklyReflection() {
  return getAnalytics('reflection/weekly', 'Could not load weekly reflection.')
}
