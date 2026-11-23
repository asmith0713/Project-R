<script>
  import { onMount } from 'svelte'
  import { justify } from '../lib/layout.js'
  import { thumbUrl } from '../lib/api.js'
  import { app, favs, selection } from '../lib/state.svelte.js'
  import { duration, shortMonth } from '../lib/format.js'
  import Icon from './Icon.svelte'

  /** items: newest first. grouped: day headers. scrubber: timeline on the right edge. */
  let { items, grouped = true, scrubber = false, onopen } = $props()

  let el
  let width = $state(0)
  let scrollY = $state(0)
  let vh = $state(typeof innerHeight === 'number' ? innerHeight : 800)
  let top = $state(0)

  const gap = $derived(width < 600 ? 2 : 4)
  const layout = $derived(
    width ? justify(items, width, { grouped, gap, header: width < 600 ? 44 : 52 }) : { blocks: [], sections: [], height: 0 },
  )
  const visible = $derived.by(() => {
    const lo = scrollY - top - vh
    const hi = scrollY - top + vh * 2
    return layout.blocks.filter((b) => b.y + b.h > lo && b.y < hi)
  })
  const selecting = $derived(selection.size > 0)

  let frame = 0
  function measure() {
    cancelAnimationFrame(frame)
    frame = requestAnimationFrame(() => {
      if (!el) return
      scrollY = window.scrollY
      vh = window.innerHeight
      top = el.getBoundingClientRect().top + window.scrollY
      scrubShow()
    })
  }

  onMount(() => {
    const ro = new ResizeObserver(() => {
      width = el.clientWidth
      measure()
    })
    ro.observe(el)
    addEventListener('scroll', measure, { passive: true })
    addEventListener('resize', measure)
    return () => {
      ro.disconnect()
      removeEventListener('scroll', measure)
      removeEventListener('resize', measure)
      cancelAnimationFrame(frame)
    }
  })

  /** Scroll so item i is on screen (used when the viewer closes). */
  export function reveal(i) {
    const b = layout.blocks.find((b) => b.type === 'tile' && b.i === i)
    if (!b) return
    const y = top + b.y
    if (y < scrollY + 80 || y + b.h > scrollY + vh - 80) scrollTo({ top: y - vh / 3 })
  }

  $effect(() => {
    const p = app.lastViewed
    if (!p) return
    const i = items.findIndex((it) => it.path === p)
    if (i >= 0) reveal(i)
    app.lastViewed = null
  })

  // ---------- selection ----------

  let anchor = null
  function toggle(i, shift = false) {
    const p = items[i].path
    if (shift && anchor !== null) {
      const [a, b] = anchor < i ? [anchor, i] : [i, anchor]
      for (let k = a; k <= b; k++) selection.add(items[k].path)
    } else if (selection.has(p)) selection.delete(p)
    else selection.add(p)
    anchor = i
  }

  function toggleDay(idx) {
    const all = idx.every((i) => selection.has(items[i].path))
    for (const i of idx) all ? selection.delete(items[i].path) : selection.add(items[i].path)
  }

  let press = null
  let suppressClick = false
  let lastType = 'mouse'
  function down(e, i) {
    lastType = e.pointerType
    if (e.pointerType !== 'touch') return
    const x = e.clientX
    const y = e.clientY
    press = {
      x,
      y,
      t: setTimeout(() => {
        toggle(i)
        suppressClick = true
        navigator.vibrate?.(15)
      }, 420),
    }
  }
  function move(e) {
    if (press && Math.hypot(e.clientX - press.x, e.clientY - press.y) > 10) cancelPress()
  }
  function cancelPress() {
    if (press) clearTimeout(press.t)
    press = null
  }
  function click(e, i) {
    cancelPress()
    if (suppressClick) {
      suppressClick = false
      return
    }
    if (selecting || e.ctrlKey || e.metaKey) toggle(i, e.shiftKey)
    else onopen?.(i)
  }

  // ---------- timeline scrubber ----------

  const showScrubber = $derived(scrubber && layout.sections.length > 1 && layout.height > vh * 3)
  let track = $state()
  let scrubbing = $state(false)
  let scrubVisible = $state(false)
  let hideTimer
  function scrubShow() {
    if (!showScrubber) return
    scrubVisible = true
    clearTimeout(hideTimer)
    hideTimer = setTimeout(() => (scrubVisible = false), 1400)
  }
  const scrollable = $derived(Math.max(1, layout.height + top - vh))
  const progress = $derived(Math.min(1, Math.max(0, scrollY / scrollable)))
  const years = $derived.by(() => {
    const out = []
    let last = null
    for (const s of layout.sections) {
      const yr = s.date.slice(0, 4)
      if (yr !== last) out.push({ yr, f: Math.min(0.97, (s.y + top) / scrollable) })
      last = yr
    }
    // drop labels that would overlap
    return out.filter((m, k) => k === 0 || m.f - out[k - 1].f > 0.05)
  })
  const currentMonth = $derived.by(() => {
    const y = scrollY - top + vh * 0.25
    let label = layout.sections[0]?.date
    for (const s of layout.sections) {
      if (s.y > y) break
      label = s.date
    }
    return label ? shortMonth(label) : ''
  })
  function scrubTo(e) {
    const r = track.getBoundingClientRect()
    const f = Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))
    scrollTo({ top: f * scrollable })
  }
</script>

<div class="grid" class:selecting bind:this={el} style:height="{layout.height}px">
  {#each visible as b (b.key)}
    {#if b.type === 'header'}
      {@const all = b.idx.every((i) => selection.has(items[i].path))}
      <div class="head" style:transform="translate({b.x}px, {b.y}px)" style:width="{b.w}px" style:height="{b.h}px">
        <button class="day-check" class:on={all} onclick={() => toggleDay(b.idx)} aria-label="Select {b.label}">
          <Icon name={all ? 'check-circle' : 'circle'} size={20} />
        </button>
        <span class="label">{b.label}</span>
      </div>
    {:else}
      {@const it = items[b.i]}
      {@const sel = selection.has(it.path)}
      <div
        class="tile"
        class:sel
        style:transform="translate({b.x}px, {b.y}px)"
        style:width="{b.w}px"
        style:height="{b.h}px"
      >
        <button
          class="hit"
          aria-label="{sel ? 'Deselect' : 'Open'} {it.name}"
          onpointerdown={(e) => down(e, b.i)}
          onpointermove={move}
          onpointerup={cancelPress}
          onpointercancel={cancelPress}
          oncontextmenu={(e) => lastType === 'touch' && e.preventDefault()}
          onclick={(e) => click(e, b.i)}
        >
          <img src={thumbUrl(it)} alt="" loading="lazy" decoding="async" draggable="false" onload={(e) => e.currentTarget.classList.add('in')} />
        </button>
        {#if it.kind === 'video'}
          <span class="badge"><Icon name="play" size={14} />{duration(it.dur)}</span>
        {/if}
        {#if favs.has(it.path)}
          <span class="fav"><Icon name="heart" filled size={16} /></span>
        {/if}
        <button class="check" aria-label="Select {it.name}" tabindex="-1" onclick={() => toggle(b.i)}>
          <Icon name={sel ? 'check-circle' : 'circle'} size={22} />
        </button>
      </div>
    {/if}
  {/each}
</div>

{#if showScrubber}
  <div
    class="scrubber"
    class:show={scrubVisible || scrubbing}
    bind:this={track}
    aria-hidden="true"
    onpointerenter={scrubShow}
    onpointerdown={(e) => {
      scrubbing = true
      e.currentTarget.setPointerCapture(e.pointerId)
      scrubTo(e)
    }}
    onpointermove={(e) => scrubbing && scrubTo(e)}
    onpointerup={() => ((scrubbing = false), scrubShow())}
    onpointercancel={() => (scrubbing = false)}
  >
    {#each years as m (m.yr)}
      <span class="year" style:top="{m.f * 100}%">{m.yr}</span>
    {/each}
    <div class="thumb" style:top="{progress * 100}%">
      <span class="bubble">{currentMonth}</span>
    </div>
  </div>
{/if}

<style>
  .grid {
    position: relative;
    width: 100%;
    contain: layout;
  }
  .head,
  .tile {
    position: absolute;
    top: 0;
    left: 0;
  }
  .head {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-weight: 500;
    font-size: 0.95rem;
    padding-top: 0.6rem;
  }
  .label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .day-check {
    display: grid;
    place-items: center;
    width: 0;
    height: 28px;
    padding: 0;
    border: 0;
    background: none;
    color: var(--muted);
    cursor: pointer;
    overflow: hidden;
    transition: width 0.15s;
  }
  .head:hover .day-check,
  .selecting .day-check {
    width: 28px;
  }
  .day-check.on {
    color: var(--accent);
  }
  .tile {
    overflow: hidden;
    background: var(--tile);
    transition: transform 0s;
  }
  .hit {
    display: block;
    width: 100%;
    height: 100%;
    padding: 0;
    border: 0;
    background: none;
    cursor: pointer;
    -webkit-touch-callout: none;
    user-select: none;
  }
  .hit:focus-visible {
    outline-offset: -3px;
  }
  img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition:
      opacity 0.25s,
      transform 0.15s;
  }
  img:global(.in) {
    opacity: 1;
  }
  .sel img {
    transform: scale(0.86);
    border-radius: 6px;
  }
  .sel {
    background: var(--accent-soft);
  }
  .badge {
    position: absolute;
    right: 6px;
    top: 6px;
    display: inline-flex;
    align-items: center;
    gap: 2px;
    padding: 1px 7px 1px 4px;
    border-radius: 999px;
    background: rgb(0 0 0 / 0.5);
    color: #fff;
    font-size: 0.75rem;
    font-weight: 500;
    pointer-events: none;
  }
  .fav {
    position: absolute;
    left: 6px;
    bottom: 4px;
    color: #fff;
    filter: drop-shadow(0 1px 2px rgb(0 0 0 / 0.6));
    pointer-events: none;
  }
  .check {
    position: absolute;
    left: 4px;
    top: 4px;
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    padding: 0;
    border: 0;
    border-radius: 50%;
    background: none;
    color: #fff;
    filter: drop-shadow(0 1px 2px rgb(0 0 0 / 0.55));
    cursor: pointer;
    opacity: 0;
    pointer-events: none; /* invisible on touch screens, so it mustn't steal taps */
    transition: opacity 0.12s;
  }
  .sel .check {
    color: var(--accent);
    filter: none;
    background: var(--bg);
    width: 24px;
    height: 24px;
    left: 7px;
    top: 7px;
  }
  @media (hover: hover) {
    .tile:hover .check {
      opacity: 1;
      pointer-events: auto;
    }
    .tile:hover::after {
      content: '';
      position: absolute;
      inset: 0 0 auto;
      height: 56px;
      background: linear-gradient(rgb(0 0 0 / 0.35), transparent);
      pointer-events: none;
    }
    .sel:hover::after {
      display: none;
    }
  }
  .selecting .check {
    opacity: 1;
    pointer-events: auto;
  }

  .scrubber {
    position: fixed;
    z-index: 5;
    right: calc(var(--safe-r) + 2px);
    top: calc(var(--safe-t) + var(--topbar) + 16px);
    bottom: calc(var(--safe-b) + 24px + var(--nav-offset, 0px));
    width: 44px;
    cursor: ns-resize;
    touch-action: none;
    opacity: 0;
    transition: opacity 0.3s;
  }
  .scrubber.show,
  .scrubber:hover {
    opacity: 1;
  }
  .year {
    position: absolute;
    right: 8px;
    transform: translateY(-50%);
    font-size: 0.7rem;
    color: var(--muted);
    background: var(--bg);
    padding: 0 4px;
    border-radius: 4px;
    pointer-events: none;
  }
  .thumb {
    position: absolute;
    right: 4px;
    width: 28px;
    height: 4px;
    margin-top: -2px;
    border-radius: 4px;
    background: var(--accent);
    pointer-events: none;
  }
  .bubble {
    position: absolute;
    right: 36px;
    top: 50%;
    transform: translateY(-50%);
    white-space: nowrap;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    background: var(--raised);
    box-shadow: var(--shadow);
    font-size: 0.8rem;
    font-weight: 500;
  }
</style>
