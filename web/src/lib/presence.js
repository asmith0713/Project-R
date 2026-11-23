// Lock the gallery when its tab or the browser closes.
//
// - pagehide: tell the server goodbye (sendBeacon survives the page closing). The server
//   ends the sign-in a few seconds later unless the page checks back in, which a reload
//   does straight away and a closed tab can't.
// - Other open tabs of the gallery hear about the goodbye (BroadcastChannel) and check in,
//   so closing one tab doesn't lock the others.
// - Heartbeat every minute while open; phones that kill the browser without any event are
//   covered by the server's idle limit (no contact for 10 minutes ends the sign-in).
import { app, checkSession } from './state.svelte.js'
import { api, getCsrf } from './api.js'

const ping = () => api('/api/ping').catch(() => {}) // a 401 shows the sign-in screen

export function startPresence() {
  const bc = 'BroadcastChannel' in window ? new BroadcastChannel('gallery-presence') : null
  if (bc)
    bc.onmessage = (e) => {
      if (e.data !== 'closing' || !app.authed) return
      // after the other tab's goodbye has reached the server
      setTimeout(ping, 1000)
      setTimeout(ping, 4000)
    }

  addEventListener('pagehide', () => {
    if (!app.authed) return
    bc?.postMessage('closing')
    const fd = new FormData()
    fd.append('csrf', getCsrf() || '')
    navigator.sendBeacon('/api/bye', fd)
  })

  // coming back via Back/Forward cache: the goodbye was sent, so ask whether we're still in
  addEventListener('pageshow', (e) => {
    if (e.persisted) checkSession()
  })

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && app.authed) ping()
  })

  setInterval(() => app.authed && ping(), 60_000)
}
