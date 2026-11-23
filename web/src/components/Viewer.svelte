<script>
  import { onMount } from 'svelte'
  import { api, thumbUrl, viewUrl, albumUrl } from '../lib/api.js'
  import { openPhoto, closePhoto, navigate } from '../lib/router.svelte.js'
  import { app, favs, setFavorite, deletePaths, moveTo, renameItem, download } from '../lib/state.svelte.js'
  import { viewerDate, fullDate, time, bytes, duration } from '../lib/format.js'
  import Icon from './Icon.svelte'
  import Menu from './Menu.svelte'

  let { items, path, autoplay = false } = $props()

  const index = $derived(Math.max(0, items.findIndex((i) => i.path === path)))
  const item = $derived(items[index])
  const slides = $derived([-1, 0, 1].map((d) => ({ d, it: items[index + d] })).filter((s) => s.it))

  let stage = $state()
  let W = $state(innerWidth)
  let H = $state(innerHeight)

  // ---------- chrome (top bar) visibility ----------
  let chrome = $state(true)
  let idle
  function wake() {
    chrome = true
    clearTimeout(idle)
    if (playing || matchMedia('(hover: hover)').matches) idle = setTimeout(() => !menuOpen && !info && (chrome = false), 2800)
  }

  // ---------- paging ----------
  let dx = $state(0)
  let dy = $state(0)
  let animating = $state(false)

  function go(d) {
    const next = items[index + d]
    if (!next || animating) return
    resetZoom()
    animating = true
    dx = -d * (W + 24)
    setTimeout(() => {
      animating = false
      dx = 0
      openPhoto(next.path)
    }, 220)
  }

  function close() {
    app.lastViewed = item?.path
    app.slideshow = null
    closePhoto()
  }

  let loaded = $state(false)

  // ---------- zoom ----------
  let scale = $state(1)
  let tx = $state(0)
  let ty = $state(0)

  function fitted(it = item) {
    const a = it.w / it.h
    return a > W / H ? [W, W / a] : [H * a, H]
  }
  function clampPan() {
    const [mw, mh] = fitted()
    const mx = Math.max(0, (mw * scale - W) / 2)
    const my = Math.max(0, (mh * scale - H) / 2)
    tx = Math.min(mx, Math.max(-mx, tx))
    ty = Math.min(my, Math.max(-my, ty))
  }
  function zoomAt(s, cx, cy) {
    s = Math.min(6, Math.max(1, s))
    const px = cx - W / 2
    const py = cy - H / 2
    tx = px - ((px - tx) * s) / scale
    ty = py - ((py - ty) * s) / scale
    scale = s
    if (s === 1) tx = ty = 0
    clampPan()
  }
  function resetZoom() {
    scale = 1
    tx = ty = 0
  }

  // ---------- gestures ----------
  const pts = new Map()
  let g = null // current gesture (plain object; only `zooming` drives the template)
  let zooming = $state(false)
  let lastTap = 0

  function rel(e) {
    const r = stage.getBoundingClientRect()
    return [e.clientX - r.left, e.clientY - r.top]
  }

  function pdown(e) {
    if (e.button > 0 || animating) return
    pts.set(e.pointerId, rel(e))
    if (pts.size === 2) {
      const [a, b] = [...pts.values()]
      g = { type: 'pinch', d0: Math.hypot(a[0] - b[0], a[1] - b[1]), s0: scale, tx0: tx, ty0: ty, c0: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] }
      dx = dy = 0
      zooming = true
      stage.setPointerCapture(e.pointerId)
    } else if (pts.size === 1) {
      const [x, y] = rel(e)
      g = { type: 'pending', x0: x, y0: y, t0: performance.now(), tx0: tx, ty0: ty, id: e.pointerId }
    }
  }

  function pmove(e) {
    if (!pts.has(e.pointerId) || !g) return
    pts.set(e.pointerId, rel(e))
    const [x, y] = rel(e)
    if (g.type === 'pinch' && pts.size === 2) {
      const [a, b] = [...pts.values()]
      const d = Math.hypot(a[0] - b[0], a[1] - b[1])
      const c = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
      scale = g.s0
      tx = g.tx0 + (c[0] - g.c0[0])
      ty = g.ty0 + (c[1] - g.c0[1])
      zoomAt(Math.max(0.8, (g.s0 * d) / g.d0), c[0], c[1])
      return
    }
    const mx = x - g.x0
    const my = y - g.y0
    if (g.type === 'pending' && Math.hypot(mx, my) > 8) {
      g.type = scale > 1 ? 'pan' : Math.abs(mx) > Math.abs(my) ? 'swipe' : my > 0 ? 'dismiss' : 'none'
      zooming = g.type === 'pan'
      stage.setPointerCapture(e.pointerId)
    }
    if (g.type === 'pan') {
      tx = g.tx0 + mx
      ty = g.ty0 + my
      clampPan()
    } else if (g.type === 'swipe') {
      const edge = (mx > 0 && index === 0) || (mx < 0 && index === items.length - 1)
      dx = edge ? mx / 3 : mx
    } else if (g.type === 'dismiss') {
      dy = Math.max(0, my)
    }
  }

  function pup(e) {
    if (!pts.has(e.pointerId)) return
    pts.delete(e.pointerId)
    if (!pts.size) zooming = false
    if (!g) return
    if (g.type === 'pinch') {
      if (pts.size === 0) {
        if (scale < 1.05) resetZoom()
        g = null
      }
      return
    }
    const dt = performance.now() - g.t0
    if (g.type === 'swipe') {
      const v = dx / dt
      if (dx < -W * 0.18 || v < -0.5) go(1)
      else if (dx > W * 0.18 || v > 0.5) go(-1)
      if (!animating) dx = 0
    } else if (g.type === 'dismiss') {
      if (dy > 110) close()
      dy = 0
    } else if (g.type === 'pending' && dt < 300 && e.type === 'pointerup') {
      tap(e)
    }
    g = null
  }

  let tapTimer
  function tap(e) {
    if (e.target.closest('video') && item.kind === 'video') return // let the video controls work
    const now = performance.now()
    if (now - lastTap < 300) {
      clearTimeout(tapTimer)
      lastTap = 0
      const [x, y] = rel(e)
      if (item.kind === 'image') scale > 1 ? resetZoom() : zoomAt(2.5, x, y)
      return
    }
    lastTap = now
    if (e.pointerType === 'mouse') return // desktop: bars follow the mouse instead
    tapTimer = setTimeout(() => (chrome ? ((chrome = false), clearTimeout(idle)) : wake()), e.pointerType === 'mouse' ? 0 : 260)
  }

  function wheel(e) {
    if (item.kind !== 'image') return
    e.preventDefault()
    const [x, y] = rel(e)
    zoomAt(scale * Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0025)), x, y)
  }

  // ---------- slideshow ----------
  let playing = $state(false)
  let slideTimer
  function play(on = !playing) {
    playing = on
    clearTimeout(slideTimer)
    if (on) {
      chrome = false
      tick()
    } else wake()
  }
  function tick() {
    clearTimeout(slideTimer)
    if (!playing || item?.kind === 'video') return // videos advance when they end
    slideTimer = setTimeout(() => (index < items.length - 1 ? go(1) : play(false)), 5000)
  }
  $effect(() => {
    path
    tick()
  })
  function videoEnded() {
    if (playing) index < items.length - 1 ? go(1) : play(false)
  }

  // ---------- info + actions ----------
  let info = $state(false)
  let details = $state(null)
  let menuOpen = $state(false)
  const cache = new Map()
  $effect(() => {
    if (!info || !item || item.kind !== 'image') return (details = null)
    const p = item.path
    if (cache.has(p)) return (details = cache.get(p))
    details = null
    api(`/api/info?path=${encodeURIComponent(p)}`)
      .then((d) => {
        cache.set(p, d)
        if (item?.path === p) details = d
      })
      .catch(() => {})
  })

  function neighbour() {
    return (items[index + 1] || items[index - 1])?.path
  }
  async function remove() {
    const next = neighbour()
    if (await deletePaths([item.path])) next ? openPhoto(next) : close()
  }
  async function move() {
    const next = neighbour()
    const moved = await moveTo([item.path])
    if (moved?.length && !items.some((i) => i.path === moved[0])) next ? openPhoto(next) : close()
  }
  async function rename() {
    const np = await renameItem(item)
    if (np) openPhoto(np)
  }

  const menu = $derived([
    { icon: 'download', label: 'Download original', run: () => download([item]) },
    { icon: 'edit', label: 'Rename', run: rename },
    { icon: 'move', label: 'Move to album', run: move },
    { icon: 'albums', label: `Open album “${item?.folder || 'Library'}”`, run: () => (close(), setTimeout(() => navigate(albumUrl(item.folder)), 30)) },
    { icon: playing ? 'pause' : 'play', label: playing ? 'Stop slideshow' : 'Slideshow', run: () => play() },
  ])

  // ---------- preloading + lifecycle ----------
  $effect(() => {
    for (const d of [1, -1, 2]) {
      const n = items[index + d]
      if (n?.kind === 'image') new Image().src = viewUrl(n)
    }
  })
  $effect(() => {
    path
    resetZoom()
    loaded = false
  })
  $effect(() => {
    if (!items.length) close()
  })

  function key(e) {
    if (app.dialog || e.target.closest?.('input, textarea')) return
    if (menuOpen && e.key !== 'Escape') return
    const k = e.key
    if (k === 'ArrowRight') go(1)
    else if (k === 'ArrowLeft') go(-1)
    else if (k === 'Escape') info ? (info = false) : menuOpen ? null : close()
    else if (k === 'i') info = !info
    else if (k === 'f') setFavorite([item.path], !favs.has(item.path))
    else if (k === 'Delete') remove()
    else if (k === ' ' && item.kind !== 'video') {
      e.preventDefault()
      play()
    } else if (k === '+' || k === '=') zoomAt(scale * 1.5, W / 2, H / 2)
    else if (k === '-') zoomAt(scale / 1.5, W / 2, H / 2)
    else return
    wake()
  }

  onMount(() => {
    const html = document.documentElement
    const prev = html.style.overflow
    html.style.overflow = 'hidden'
    const ro = new ResizeObserver(() => {
      W = stage.clientWidth
      H = stage.clientHeight
      clampPan()
    })
    ro.observe(stage)
    wake()
    if (autoplay) play(true)
    return () => {
      html.style.overflow = prev
      ro.disconnect()
      clearTimeout(idle)
      clearTimeout(slideTimer)
      clearTimeout(tapTimer)
    }
  })
</script>

<svelte:window onkeydown={key} />

<div
  class="viewer"
  class:info
  role="dialog"
  tabindex="-1"
  aria-modal="true"
  aria-label={item ? `${item.name}, ${index + 1} of ${items.length}` : 'Viewer'}
  style:--fade={1 - Math.min(dy / 400, 0.6)}
  onmousemove={() => !playing && wake()}
>
  <div
    class="stage"
    bind:this={stage}
    onpointerdown={pdown}
    onpointermove={pmove}
    onpointerup={pup}
    onpointercancel={pup}
    onwheel={wheel}
    role="presentation"
  >
    <div class="track" class:animating style:transform="translate3d({dx}px, {dy}px, 0) scale({1 - Math.min(dy / 1600, 0.15)})">
      {#each slides as s (s.it.path)}
        {@const it = s.it}
        <div class="slide" style:transform="translateX({s.d * (W + 24)}px)">
          {#if it.kind === 'video' && s.d === 0}
            <!-- svelte-ignore a11y_media_has_caption -->
            <video
              src={viewUrl(it)}
              poster={thumbUrl(it)}
              controls
              autoplay
              playsinline
              onended={videoEnded}
              onplay={() => playing && clearTimeout(slideTimer)}
            ></video>
          {:else}
            {@const [bw, bh] = fitted(it)}
            <div class="media" style:transform={s.d === 0 ? `translate(${tx}px, ${ty}px) scale(${scale})` : ''} class:zooming>
              <div class="box" style:width="{bw}px" style:height="{bh}px">
                <img class="ph" src={thumbUrl(it)} alt="" draggable="false" />
                {#if it.kind === 'image'}
                  <img
                    class="full"
                    class:loaded={s.d !== 0 || loaded}
                    src={viewUrl(it)}
                    alt={it.name}
                    draggable="false"
                    onload={() => s.d === 0 && (loaded = true)}
                  />
                {:else}
                  <span class="play-badge"><Icon name="play" size={40} /></span>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>
    {#if item?.kind === 'image' && !loaded}
      <div class="loading"><div class="spinner"></div></div>
    {/if}
  </div>

  <header class="bar" class:hide={!chrome}>
    <button class="icon-btn" onclick={close} aria-label="Close"><Icon name="back" /></button>
    <div class="title">
      {#if item}
        <strong>{viewerDate(item.date)}</strong>
        <span>{index + 1} of {items.length}{item.kind === 'video' && item.dur ? ` · ${duration(item.dur)}` : ''}</span>
      {/if}
    </div>
    {#if item}
      <button class="icon-btn" class:hearted={favs.has(item.path)} onclick={() => setFavorite([item.path], !favs.has(item.path))} aria-label={favs.has(item.path) ? 'Remove from favorites' : 'Add to favorites'} aria-pressed={favs.has(item.path)}>
        <Icon name="heart" filled={favs.has(item.path)} />
      </button>
      <button class="icon-btn" class:active={info} onclick={() => (info = !info)} aria-label="Info" aria-pressed={info}><Icon name="info" /></button>
      <button class="icon-btn" onclick={remove} aria-label="Move to trash"><Icon name="trash" /></button>
      <Menu items={menu} bind:open={menuOpen} label="More options" dark />
    {/if}
  </header>

  {#if items.length > 1 && chrome}
    {#if index > 0}
      <button class="nav prev" onclick={() => go(-1)} aria-label="Previous"><Icon name="left" size={30} /></button>
    {/if}
    {#if index < items.length - 1}
      <button class="nav next" onclick={() => go(1)} aria-label="Next"><Icon name="right" size={30} /></button>
    {/if}
  {/if}

  {#if playing}
    <button class="stop" onclick={() => play(false)}><Icon name="pause" size={20} />Pause slideshow</button>
  {/if}

  {#if info && item}
    <aside class="panel" aria-label="Details">
      <div class="panel-head">
        <button class="icon-btn" onclick={() => (info = false)} aria-label="Close details"><Icon name="close" /></button>
        <h2>Details</h2>
      </div>
      <dl>
        <div class="row">
          <Icon name="calendar" />
          <div><dt>{fullDate(item.date)}</dt><dd>{time(item.date)}</dd></div>
        </div>
        <div class="row">
          <Icon name={item.kind === 'video' ? 'video' : 'image'} />
          <div>
            <dt class="wrap">{item.name}</dt>
            <dd>
              {#if item.w > 1}{item.kind === 'image' ? `${((item.w * item.h) / 1e6).toFixed(1)} MP · ` : ''}{item.w} × {item.h} · {/if}{bytes(item.size)}
            </dd>
          </div>
        </div>
        <div class="row">
          <Icon name="albums" />
          <div>
            <dt><a href={albumUrl(item.folder)} onclick={close}>{item.folder || 'Library'}</a></dt>
            <dd>Album</dd>
          </div>
        </div>
        {#if details?.camera}
          <div class="row">
            <Icon name="camera" />
            <div>
              <dt>{details.camera}</dt>
              <dd>{[details.aperture, details.shutter, details.focal, details.iso].filter(Boolean).join(' · ')}</dd>
              {#if details.lens}<dd class="faint">{details.lens}</dd>{/if}
            </div>
          </div>
        {/if}
        {#if details?.gps}
          <div class="row">
            <Icon name="place" />
            <div>
              <dt>
                <a href="https://www.openstreetmap.org/?mlat={details.gps[0]}&mlon={details.gps[1]}#map=16/{details.gps[0]}/{details.gps[1]}" target="_blank" rel="noopener noreferrer">Show on map</a>
              </dt>
              <dd>{details.gps[0].toFixed(5)}, {details.gps[1].toFixed(5)}</dd>
            </div>
          </div>
        {/if}
      </dl>
    </aside>
  {/if}
</div>

<style>
  .viewer {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: flex;
    background: rgb(0 0 0 / var(--fade, 1));
    color: #f1f1f3;
    overscroll-behavior: contain;
  }
  .stage {
    position: relative;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    touch-action: none;
    user-select: none;
  }
  .track {
    position: absolute;
    inset: 0;
    will-change: transform;
  }
  .track.animating {
    transition: transform 0.22s cubic-bezier(0.2, 0.7, 0.3, 1);
  }
  .slide {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
  }
  .media {
    position: relative;
    display: grid;
    place-items: center;
    width: 100%;
    height: 100%;
    transition: transform 0.2s ease-out;
    transform-origin: center;
  }
  .media.zooming {
    transition: none;
  }
  /* thumbnail and full image share one box sized to the photo, so the swap doesn't jump */
  .box {
    position: relative;
    display: grid;
    place-items: center;
  }
  .box img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
  .full {
    opacity: 0;
    transition: opacity 0.2s;
  }
  .full.loaded {
    opacity: 1;
  }
  video {
    max-width: 100%;
    max-height: 100%;
    background: #000;
  }
  .play-badge {
    position: relative;
    display: grid;
    place-items: center;
    width: 72px;
    height: 72px;
    border-radius: 50%;
    background: rgb(0 0 0 / 0.5);
  }
  .loading {
    position: absolute;
    right: 16px;
    bottom: calc(16px + var(--safe-b));
    pointer-events: none;
  }
  .loading .spinner {
    width: 22px;
    height: 22px;
    border-color: rgb(255 255 255 / 0.25);
    border-top-color: #fff;
  }

  .bar {
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: calc(var(--safe-t) + 8px) calc(var(--safe-r) + 8px) 24px calc(var(--safe-l) + 8px);
    background: linear-gradient(rgb(0 0 0 / 0.6), transparent);
    transition: opacity 0.2s;
  }
  .viewer.info .bar {
    right: var(--panel-w, 0px);
  }
  .bar.hide {
    opacity: 0;
    pointer-events: none;
  }
  .bar .icon-btn:hover {
    background: rgb(255 255 255 / 0.12);
  }
  .bar .hearted {
    color: var(--heart);
  }
  .bar .active {
    background: rgb(255 255 255 / 0.16);
  }
  .title {
    flex: 1;
    min-width: 0;
    display: grid;
    line-height: 1.25;
    padding: 0 0.25rem;
  }
  .title strong {
    font-weight: 500;
    font-size: 0.95rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .title span {
    font-size: 0.78rem;
    opacity: 0.75;
  }
  .nav {
    position: absolute;
    top: 50%;
    z-index: 2;
    display: none;
    place-items: center;
    width: 52px;
    height: 52px;
    margin-top: -26px;
    border: 0;
    border-radius: 50%;
    background: rgb(30 30 30 / 0.55);
    color: #fff;
    cursor: pointer;
  }
  .nav:hover {
    background: rgb(60 60 60 / 0.75);
  }
  .prev {
    left: calc(var(--safe-l) + 16px);
  }
  .next {
    right: calc(var(--safe-r) + 16px);
  }
  .viewer.info .next {
    right: calc(var(--panel-w) + 16px);
  }
  @media (hover: hover) and (pointer: fine) {
    .nav {
      display: grid;
    }
  }
  .stop {
    position: absolute;
    left: 50%;
    bottom: calc(var(--safe-b) + 20px);
    transform: translateX(-50%);
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.55rem 1.1rem;
    border: 0;
    border-radius: 999px;
    background: rgb(30 30 30 / 0.7);
    color: #fff;
    cursor: pointer;
    opacity: 0.4;
    transition: opacity 0.2s;
  }
  .stop:hover,
  .stop:focus-visible {
    opacity: 1;
  }

  /* details: side panel on wide screens, bottom sheet on phones */
  .viewer {
    --panel-w: 0px;
  }
  .viewer.info {
    --panel-w: 360px;
  }
  .panel {
    width: 360px;
    flex: none;
    overflow-y: auto;
    background: var(--surface);
    color: var(--text);
    padding: calc(var(--safe-t) + 8px) calc(var(--safe-r) + 16px) calc(var(--safe-b) + 24px) 12px;
  }
  .panel-head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }
  .panel-head h2 {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 500;
  }
  dl {
    margin: 0;
    display: grid;
    gap: 1.1rem;
    padding-left: 8px;
  }
  .row {
    display: grid;
    grid-template-columns: 24px 1fr;
    gap: 1rem;
    align-items: start;
    color: var(--muted);
  }
  dt {
    color: var(--text);
    font-weight: 500;
  }
  dt a {
    color: var(--accent);
    text-decoration: none;
  }
  dt a:hover {
    text-decoration: underline;
  }
  dd {
    margin: 0;
    font-size: 0.88rem;
  }
  .wrap {
    overflow-wrap: anywhere;
  }
  .faint {
    color: var(--faint);
  }
  @media (max-width: 760px) {
    .viewer.info {
      --panel-w: 0px;
    }
    .viewer {
      flex-direction: column;
    }
    .panel {
      width: auto;
      max-height: 55dvh;
      border-radius: 18px 18px 0 0;
      padding: 8px calc(var(--safe-r) + 16px) calc(var(--safe-b) + 20px) calc(var(--safe-l) + 12px);
      box-shadow: 0 -8px 30px rgb(0 0 0 / 0.4);
    }
  }
</style>
