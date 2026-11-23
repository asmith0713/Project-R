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
  search: '', // kept out of the URL on purpose: the secret code is typed here
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

// ---------- hidden albums ----------
// Albums hidden behind a secret code. The code is typed into the search box; the
// server decides, so nothing about hidden albums ever reaches the page while locked.

export async function tryUnlock(code) {
  if (code.trim().length < 4) return false
  try {
    const r = await post('/api/hidden/unlock', { code })
    return r.ok
  } catch {
    return false
  }
}

export async function lockHidden() {
  try {
    await post('/api/hidden/lock')
  } catch {}
  app.version++
}

async function askNewCode(title) {
  const a = await ask({ kind: 'prompt', title, body: 'To open hidden albums later, type this code into the search box and press Enter.', placeholder: 'At least 4 characters', password: true, confirm: 'Next' })
  if (!a) return null
  if (a.length < 4) return (fail({ message: 'Use at least 4 characters' }), null)
  const b = await ask({ kind: 'prompt', title: 'Type it again', password: true, confirm: 'Save code' })
  if (b === null) return null
  if (a !== b) return (fail({ message: "The two codes didn't match" }), null)
  return a
}

export async function hideAlbum(path) {
  try {
    let s = await api('/api/hidden')
    if (!s.configured) {
      const code = await askNewCode('Create a secret code')
      if (!code) return false
      await post('/api/hidden/code', { code })
    } else if (!s.unlocked) {
      const code = await ask({ kind: 'prompt', title: 'Enter your secret code', password: true, confirm: 'Continue' })
      if (!code) return false
      if (!(await tryUnlock(code))) return (fail({ message: "That code didn't work" }), false)
    }
    await post('/api/hidden/hide', { path })
    changed()
    toast('Album hidden. To find it, type your secret code in search.')
    return true
  } catch (e) {
    fail(e)
    return false
  }
}

export async function unhideAlbum(path) {
  try {
    await post('/api/hidden/unhide', { path })
    changed()
    toast('Album is visible again')
    return true
  } catch (e) {
    fail(e)
    return false
  }
}

export async function changeCode() {
  const code = await askNewCode('New secret code')
  if (!code) return
  try {
    await post('/api/hidden/code', { code })
    toast('Secret code changed')
  } catch (e) {
    fail(e)
  }
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

export async function deleteAlbum(path, count = 0) {
  const name = path.split('/').pop()
  const ok = await ask({
    kind: 'confirm',
    title: `Delete “${name}”?`,
    body: count
      ? `Its ${plural(count, 'item')} (sub-albums included) move to Trash, where you can restore them for 30 days.`
      : 'The album is empty, so nothing else is deleted.',
    confirm: 'Delete album',
    danger: true,
  })
  if (!ok) return false
  try {
    const r = await post('/api/rmdir', { path })
    changed()
    toast(r.kept ? `Moved ${plural(r.ids.length, 'item')} to trash. The folder was kept because it has other files.` : `Deleted “${name}”`, {
      action: r.ids.length ? 'Undo' : undefined,
      onAction: () => restore(r.ids),
    })
    return true
  } catch (e) {
    fail(e)
    return false
  }
}

export async function moveAlbum(path) {
  const name = path.split('/').pop()
  const parent = path.split('/').slice(0, -1).join('/')
  const dest = await ask({ kind: 'album', title: `Move “${name}” into…`, exclude: path, current: parent, top: 'Top level (not inside an album)' })
  if (dest === null || dest === undefined || dest === parent) return null
  try {
    const r = await post('/api/move-album', { path, dest })
    changed()
    toast(`Moved “${name}” into ${dest ? `“${dest.split('/').pop()}”` : 'the top level'}`)
    return r.path
  } catch (e) {
    fail(e)
    return null
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
