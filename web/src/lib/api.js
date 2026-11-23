// Small fetch wrapper: JSON in/out, CSRF header on writes, friendly errors.

let csrf = null
let onUnauthorized = () => {}

export const setCsrf = (t) => (csrf = t)
export const getCsrf = () => csrf
export const setUnauthorizedHandler = (fn) => (onUnauthorized = fn)

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export async function api(path, { method = 'GET', json, form, signal } = {}) {
  const headers = {}
  let body
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  } else if (form) body = form
  if (method !== 'GET' && csrf) headers['X-CSRF'] = csrf
  let r
  try {
    r = await fetch(path, { method, headers, body, signal, credentials: 'same-origin' })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError("Can't reach the gallery. Check you're on the home wifi.", 0)
  }
  let data = null
  try {
    data = await r.json()
  } catch {}
  if (r.status === 401 && path !== '/api/login') onUnauthorized()
  if (!r.ok) throw new ApiError(data?.error || `Something went wrong (${r.status})`, r.status)
  return data
}

export const post = (path, json) => api(path, { method: 'POST', json })

// Each path segment is encoded separately so names with #, ?, %, emoji work.
export const enc = (p) => p.split('/').map(encodeURIComponent).join('/')
export const thumbUrl = (it) => `/t/${enc(it.path)}${it.v ? `?v=${it.v}` : ''}`
export const viewUrl = (it) => `/m/${enc(it.path)}${it.v ? `?v=${it.v}` : ''}`
export const downloadUrl = (it) => `/d/${enc(it.path)}`
export const albumUrl = (path) => (path ? `/albums/${enc(path)}` : '/albums')
