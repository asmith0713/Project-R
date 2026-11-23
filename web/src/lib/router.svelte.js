// Minimal history router. The open photo lives in ?photo=<path> so the Back button
// (and Android's back gesture) closes the viewer, and a refresh reopens it.

export const route = $state({ path: location.pathname, photo: null })

function sync() {
  route.path = decodeURI(location.pathname).replace(/\/+$/, '') || '/'
  route.photo = new URLSearchParams(location.search).get('photo')
}
sync()
addEventListener('popstate', sync)

export function navigate(to, { replace = false } = {}) {
  if (to === location.pathname + location.search) return
  history[replace ? 'replaceState' : 'pushState']({}, '', to)
  sync()
  if (!replace) scrollTo(0, 0)
}

function withPhoto(path) {
  const q = new URLSearchParams(location.search)
  if (path) q.set('photo', path)
  else q.delete('photo')
  const s = q.toString()
  return location.pathname + (s ? `?${s}` : '')
}

export function openPhoto(path) {
  const pushed = !route.photo
  history[pushed ? 'pushState' : 'replaceState']({ viewer: pushed || history.state?.viewer }, '', withPhoto(path))
  sync()
}

export function closePhoto() {
  if (!route.photo) return
  if (history.state?.viewer) history.back()
  else {
    history.replaceState({}, '', withPhoto(null))
    sync()
  }
}
