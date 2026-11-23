// Upload queue: two files at a time, with per-file progress and errors.
import { app, changed, toast } from './state.svelte.js'
import { plural } from './format.js'
import { getCsrf } from './api.js'

const OK = /\.(jpe?g|png|gif|webp|heic|heif|tiff?|dng|mp4|mov|m4v|webm)$/i

export const uploads = $state({ files: [], open: false, picker: null })

export function pick(target = app.uploadTarget) {
  uploads.picker?.(target)
}

export function add(fileList, folder = app.uploadTarget) {
  const files = [...fileList]
  const bad = files.filter((f) => !OK.test(f.name))
  for (const f of files.filter((f) => OK.test(f.name)))
    uploads.files.push({ id: crypto.randomUUID?.() ?? Math.random().toString(36), file: f, name: f.name, folder, loaded: 0, total: f.size, state: 'queued', error: '' })
  if (bad.length) toast(`Skipped ${plural(bad.length, 'file')} that aren't photos or videos`, { error: true })
  uploads.open = true
  pump()
}

let active = 0
function pump() {
  while (active < 2) {
    const next = uploads.files.find((u) => u.state === 'queued')
    if (!next) break
    active++
    next.state = 'uploading'
    send(next).finally(() => {
      active--
      pump()
      if (!active && !uploads.files.some((u) => u.state === 'queued')) finished()
    })
  }
}

function send(u) {
  return new Promise((resolve) => {
    const x = new XMLHttpRequest()
    const fd = new FormData()
    fd.append('folder', u.folder)
    fd.append('file', u.file)
    x.open('POST', '/api/upload')
    x.setRequestHeader('X-CSRF', getCsrf() || '')
    x.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        u.loaded = e.loaded
        u.total = e.total
      }
    }
    x.onload = () => {
      let msg = ''
      try {
        msg = JSON.parse(x.responseText).error || ''
      } catch {}
      if (x.status === 200) {
        u.state = 'done'
        u.loaded = u.total
        u.file = null
      } else {
        u.state = 'error'
        u.error = msg || `Failed (${x.status})`
      }
      resolve()
    }
    x.onerror = () => {
      u.state = 'error'
      u.error = 'Connection lost'
      resolve()
    }
    x.send(fd)
  })
}

function finished() {
  const done = uploads.files.filter((u) => u.state === 'done').length
  const failed = uploads.files.filter((u) => u.state === 'error').length
  if (done) changed()
  toast(failed ? `${done} uploaded, ${failed} failed` : `${plural(done, 'item')} uploaded`, { error: !!failed && !done })
}

export function retry() {
  for (const u of uploads.files) if (u.state === 'error' && u.file) ((u.state = 'queued'), (u.error = ''), (u.loaded = 0))
  pump()
}

export function clear() {
  uploads.files = uploads.files.filter((u) => u.state === 'uploading' || u.state === 'queued')
  if (!uploads.files.length) uploads.open = false
}
