// Justified rows (like Google Photos): every full row fills the width exactly and keeps
// each photo's shape. With `grouped`, photos sit under day headers, and days small
// enough to fit in one row are packed side by side instead of each taking a whole row.
// Returns absolutely-positioned blocks so the grid can render only what's on screen.

import { dayLabel } from './format.js'

export function rowHeight(width) {
  if (width < 420) return 112
  if (width < 700) return 140
  if (width < 1100) return 180
  return 220
}

const aspect = (it) => Math.min(Math.max(it.w / it.h || 1, 0.5), 2.6)

/** Lay out `idx` (indices into items) as justified rows starting at y. */
function rows(items, idx, width, target, gap, y, blocks) {
  let row = []
  let sum = 0
  const flush = (last) => {
    if (!row.length) return
    const free = width - gap * (row.length - 1)
    let h = free / sum
    const short = last && h > target * 1.25 // don't blow up a lonely last row
    if (short) h = target
    let x = 0
    for (const r of row) {
      const w = r.a * h
      blocks.push({ type: 'tile', key: items[r.i].path, x, y, w, h, i: r.i })
      x += w + gap
    }
    if (!short) {
      const lastBlock = blocks[blocks.length - 1] // absorb rounding so rows line up
      lastBlock.w = width - lastBlock.x
    }
    y += h + gap
    row = []
    sum = 0
  }
  for (const i of idx) {
    const a = aspect(items[i])
    row.push({ i, a })
    sum += a
    if (sum * target + gap * (row.length - 1) >= width) flush(false)
  }
  flush(true)
  return y
}

export function justify(items, width, { grouped = true, gap = 4, header = 52 } = {}) {
  const target = rowHeight(width)
  const blocks = []
  const sections = []

  if (!grouped) {
    const y = rows(items, items.map((_, i) => i), width, target, gap, 0, blocks)
    return { blocks, sections, height: Math.max(0, y - gap) }
  }

  const groups = []
  let cur = null
  items.forEach((it, i) => {
    const key = it.date.slice(0, 10)
    if (!cur || cur.key !== key) groups.push((cur = { key, date: it.date, idx: [] }))
    cur.idx.push(i)
  })

  const between = width < 600 ? 10 : 16 // space between days sharing a row
  const minHead = width < 600 ? 104 : 128 // room for the day label
  let y = 0
  let band = null // { y, x } while packing small days side by side

  for (const g of groups) {
    const natural = g.idx.reduce((s, i) => s + aspect(items[i]) * target, 0) + gap * (g.idx.length - 1)
    const small = natural < width * 0.98
    const label = dayLabel(g.date)

    if (small) {
      const w = Math.max(natural, minHead)
      if (!band || band.x + w > width) {
        if (band) y = band.y + header + target + gap + 8
        band = { y, x: 0 }
      }
      sections.push({ y: band.y, date: g.date })
      blocks.push({ type: 'header', key: `h${g.key}`, x: band.x, y: band.y, w, h: header, label, idx: g.idx })
      let x = band.x
      for (const i of g.idx) {
        const tw = aspect(items[i]) * target
        blocks.push({ type: 'tile', key: items[i].path, x, y: band.y + header, w: tw, h: target, i })
        x += tw + gap
      }
      band.x += w + between
      continue
    }

    if (band) {
      y = band.y + header + target + gap + 8
      band = null
    }
    sections.push({ y, date: g.date })
    blocks.push({ type: 'header', key: `h${g.key}`, x: 0, y, w: width, h: header, label, idx: g.idx })
    y = rows(items, g.idx, width, target, gap, y + header, blocks) + 8
  }
  if (band) y = band.y + header + target + gap + 8
  return { blocks, sections, height: Math.max(0, y) }
}
