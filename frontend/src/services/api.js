const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const ACCESS_TOKEN_STORAGE_KEY = 'planora.accessToken'

export function getAccessToken() {
  try {
    return localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setAccessToken(token) {
  try {
    localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, token)
  } catch {
    // Requests still fail cleanly through the backend if browser storage is unavailable.
  }
}

export function clearAccessToken() {
  try {
    localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
  } catch {
    // Clearing a missing/unavailable browser storage entry is intentionally a no-op.
  }
}

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers)
  const token = getAccessToken()

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  return fetch(`${API_BASE_URL}${path}`, { ...options, headers })
}

async function readError(response, fallbackMessage) {
  try {
    const data = await response.json()
    return typeof data.detail === 'string' ? data.detail : fallbackMessage
  } catch {
    return fallbackMessage
  }
}

export async function login(credentials) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })

  if (!response.ok) throw new Error(await readError(response, 'Could not sign in.'))

  const data = await response.json()
  setAccessToken(data.access_token)
  return data
}

export async function register(credentials) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })

  if (!response.ok) throw new Error(await readError(response, 'Could not create the account.'))

  return response.json()
}

export async function getTasks() {
  const response = await apiFetch('/tasks')
  if (!response.ok) throw new Error(await readError(response, 'Could not load tasks from the backend.'))
  return response.json()
}

export async function getTaskHistory() {
  const response = await apiFetch('/task-history')
  if (!response.ok) throw new Error(await readError(response, 'Could not load task history from the backend.'))
  return response.json()
}

function historyQuery(params) {
  const query = new URLSearchParams()
  if (params.range) query.set('range', params.range)
  if (params.eventType) query.set('event_type', params.eventType)
  if (params.startDate) query.set('start_date', params.startDate)
  if (params.endDate) query.set('end_date', params.endDate)
  const queryString = query.toString()
  return queryString ? `?${queryString}` : ''
}

export async function getHistory(params = {}) {
  const response = await apiFetch(`/history${historyQuery(params)}`)
  if (!response.ok) throw new Error(await readError(response, 'Could not load history from the backend.'))
  return response.json()
}

export async function getHistorySummary(params = {}) {
  const response = await apiFetch(`/history/summary${historyQuery(params)}`)
  if (!response.ok) throw new Error(await readError(response, 'Could not load history summary from the backend.'))
  return response.json()
}

export async function createTask(taskData) {
  const response = await apiFetch('/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(taskData),
  })
  if (!response.ok) throw new Error(await readError(response, 'Could not create the task.'))
  return response.json()
}

export async function updateTask(taskId, taskData) {
  const response = await apiFetch(`/tasks/${taskId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(taskData),
  })
  if (!response.ok) throw new Error(await readError(response, 'Could not update the task.'))
  return response.json()
}

export async function deleteTask(taskId) {
  const response = await apiFetch(`/tasks/${taskId}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await readError(response, 'Could not delete the task.'))
}

export async function planDay(planData) {
  const response = await apiFetch('/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(planData),
  })
  if (!response.ok) throw new Error(await readError(response, 'Could not create a plan.'))
  return response.json()
}

export async function replanTask(taskId, planData) {
  const response = await apiFetch(`/replan/${taskId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(planData),
  })
  if (!response.ok) throw new Error(await readError(response, 'Could not replan the task.'))
  return response.json()
}

export async function recommendTask() {
  const response = await apiFetch('/recommend')
  if (!response.ok) throw new Error(await readError(response, 'Could not get a recommendation.'))
  return response.json()
}

async function getAnalytics(path, message) {
  const response = await apiFetch(`/analytics/${path}`)
  if (!response.ok) throw new Error(await readError(response, message))
  return response.json()
}

export function getProgress() {
  return getAnalytics('progress', 'Could not load progress.')
}

export function getWeeklyReflection() {
  return getAnalytics('reflection/weekly', 'Could not load weekly reflection.')
}
