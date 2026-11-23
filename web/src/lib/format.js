const loc = undefined // the browser's own locale

const d = (s) => new Date(s) // ISO local time without zone -> parsed as local

export function dayLabel(iso) {
  const date = d(iso)
  const today = new Date()
  const y = new Date(today)
  y.setDate(today.getDate() - 1)
  const same = (a, b) => a.toDateString() === b.toDateString()
  if (same(date, today)) return 'Today'
  if (same(date, y)) return 'Yesterday'
  const opts = { weekday: 'short', day: 'numeric', month: 'short' }
  if (date.getFullYear() !== today.getFullYear()) opts.year = 'numeric'
  return date.toLocaleDateString(loc, opts)
}

export const monthLabel = (iso) => d(iso).toLocaleDateString(loc, { month: 'long', year: 'numeric' })
export const shortMonth = (iso) => d(iso).toLocaleDateString(loc, { month: 'short', year: 'numeric' })
export const fullDate = (iso) =>
  d(iso).toLocaleDateString(loc, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
export const time = (iso) => d(iso).toLocaleTimeString(loc, { hour: 'numeric', minute: '2-digit' })
export const viewerDate = (iso) =>
  d(iso).toLocaleDateString(loc, { day: 'numeric', month: 'short', year: 'numeric' }) + ', ' + time(iso)

export function bytes(n) {
  if (!n && n !== 0) return ''
  const u = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (n >= 1024 && i < u.length - 1) {
    n /= 1024
    i++
  }
  return `${n.toFixed(n < 10 && i ? 1 : 0)} ${u[i]}`
}

export function duration(s) {
  if (!s) return ''
  s = Math.round(s)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${sec}` : `${m}:${sec}`
}

export const plural = (n, word) => `${n.toLocaleString()} ${word}${n === 1 ? '' : 's'}`

export function countLabel(items) {
  const v = items.filter((i) => i.kind === 'video').length
  const p = items.length - v
  return [p && plural(p, 'photo'), v && plural(v, 'video')].filter(Boolean).join(' · ') || 'Empty'
}
