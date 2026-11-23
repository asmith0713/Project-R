// App-wide state and every action that changes files. Views read from here and call
// these functions; after a change `app.version` is bumped so open views re-fetch.

import { SvelteSet } from 'svelte/reactivity'
import { api, post, setCsrf, downloadUrl } from './api.js'
import { plural } from './format.js'

export const app = $state({
  authed: null, // null = still checking
  configured: true,
  library: null, // all items, newest first
  scanning: false,
  version: 0, // bump to make views reload
  toasts: [],
  dialog: null,
  uploadTarget: '', // album the Upload button sends to
  context: [], // items of the page on screen; the viewer pages through these
  slideshow: null, // { items } while a shuffled slideshow runs
  lastViewed: null, // path the viewer closed on, so the grid can scroll to it
})

export const favs = new SvelteSet()
export const selection = new SvelteSet()

// ---------- session ----------

export async function checkSession() {
  try {
    const s = await api('/api/session')
    app.configured = s.configured
    if (s.authed) setCsrf(s.csrf)
    app.authed = s.authed
  } catch {
    app.authed = false
  }
}

export async function login(key) {
  const r = await post('/api/login', { key })
  setCsrf(r.csrf)
  app.authed = true
}

export async function logout() {
  try {
    await post('/api/logout')
  } catch {}
  signedOut()
}

export function signedOut() {
  app.authed = false
  app.library = null
  favs.clear()
  selection.clear()
}

// ---------- data ----------

let scanTimer
export async function loadLibrary() {
  const r = await api('/api/library')
  app.library = r.items
  app.scanning = r.scanning
  favs.clear()
  for (const it of r.items) if (it.fav) favs.add(it.path)
  clearTimeout(scanTimer)
  if (r.scanning) scanTimer = setTimeout(loadLibrary, 4000) // first-run indexing
  return r.items
}

export function changed() {
  app.version++
  loadLibrary().catch(() => {})
}

// ---------- feedback ----------

let toastId = 0
export function toast(message, { error = false, action, onAction, ms = 4500 } = {}) {
  const id = ++toastId
  app.toasts.push({ id, message, error, action, onAction })
  setTimeout(() => dismiss(id), ms)
}
export const dismiss = (id) => (app.toasts = app.toasts.filter((t) => t.id !== id))
export const fail = (e) => toast(e?.message || 'Something went wrong', { error: true })

// Dialogs return a promise: confirm -> true/false, prompt -> string|null, album -> path|null
export function ask(dialog) {
  return new Promise((resolve) => {
    app.dialog = { ...dialog, resolve: (v) => ((app.dialog = null), resolve(v)) }
  })
}

// ---------- actions ----------

export async function setFavorite(paths, on) {
  paths = [...paths]
  for (const p of paths) on ? favs.add(p) : favs.delete(p)
  try {
    await post('/api/favorite', { paths, on })
  } catch (e) {
    for (const p of paths) on ? favs.delete(p) : favs.add(p)
    fail(e)
  }
}

export async function deletePaths(paths) {
  paths = [...paths]
  if (!paths.length) return false
  const ok = await ask({
    kind: 'confirm',
    title: paths.length === 1 ? 'Move to trash?' : `Move ${paths.length} items to trash?`,
    body: 'You can restore them from Trash for 30 days.',
    confirm: 'Move to trash',
    danger: true,
  })
  if (!ok) return false
  try {
    const r = await post('/api/delete', { paths })
    for (const p of r.deleted) favs.delete(p)
    selection.clear()
    changed()
    toast(r.deleted.length === 1 ? 'Moved to trash' : `${r.deleted.length} items moved to trash`, {
      action: 'Undo',
      onAction: () => restore(r.ids),
    })
    return true
  } catch (e) {
    fail(e)
    return false
  }
}

export async function restore(ids) {
  try {
    const r = await post('/api/trash/restore', { ids })
    changed()
    toast(r.restored.length === 1 ? 'Restored' : `${r.restored.length} items restored`)
  } catch (e) {
    fail(e)
  }
}

export async function moveTo(paths) {
  paths = [...paths]
  const dest = await ask({ kind: 'album', title: paths.length === 1 ? 'Move to album' : `Move ${paths.length} items to album` })
  if (dest === null || dest === undefined) return null
  try {
    const r = await post('/api/move', { paths, dest })
    selection.clear()
    changed()
    toast(r.moved.length ? `Moved ${plural(r.moved.length, 'item')} to ${dest || 'Library'}` : 'Already in that album')
    return r.moved
  } catch (e) {
    fail(e)
    return null
  }
}

export async function renameItem(item) {
  const dot = item.name.lastIndexOf('.')
  const stem = dot > 0 ? item.name.slice(0, dot) : item.name
  const name = await ask({ kind: 'prompt', title: 'Rename', value: stem, suffix: item.name.slice(dot), confirm: 'Rename' })
  if (!name || name === stem) return null
  try {
    const r = await post('/api/rename', { path: item.path, name })
    changed()
    return r.path
  } catch (e) {
    fail(e)
    return null
  }
}

export async function newAlbum(parent = '') {
  const name = await ask({ kind: 'prompt', title: 'New album', placeholder: 'Album name', confirm: 'Create' })
  if (!name) return null
  try {
    const r = await post('/api/mkdir', { folder: parent, name })
    changed()
    toast(`Created “${name}”`)
    return r.path
  } catch (e) {
    fail(e)
    return null
  }
}

export async function renameAlbum(path) {
  const old = path.split('/').pop()
  const name = await ask({ kind: 'prompt', title: 'Rename album', value: old, confirm: 'Rename' })
  if (!name || name === old) return null
  try {
    const r = await post('/api/rename', { path, name })
    changed()
    return r.path
  } catch (e) {
    fail(e)
    return null
  }
}

export async function deleteAlbum(path) {
  const ok = await ask({
    kind: 'confirm',
    title: `Delete “${path.split('/').pop()}”?`,
    body: 'The album is empty, so nothing else is deleted.',
    confirm: 'Delete album',
    danger: true,
  })
  if (!ok) return false
  try {
    await post('/api/rmdir', { path })
    changed()
    return true
  } catch (e) {
    fail(e)
    return false
  }
}

export function download(items) {
  // Separate clicks so the browser saves each original file; small delay keeps
  // mobile browsers from dropping all but the first.
  items.forEach((it, n) =>
    setTimeout(() => {
      const a = document.createElement('a')
      a.href = downloadUrl(it)
      a.download = it.name
      document.body.append(a)
      a.click()
      a.remove()
    }, n * 400),
  )
}
