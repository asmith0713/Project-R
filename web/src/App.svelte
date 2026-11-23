<script>
  import { onMount } from 'svelte'
  import { route, navigate } from './lib/router.svelte.js'
  import { setUnauthorizedHandler } from './lib/api.js'
  import { app, favs, selection, checkSession, loadLibrary, logout, signedOut, setFavorite, deletePaths, moveTo, download, fail } from './lib/state.svelte.js'
  import { pick } from './lib/uploads.svelte.js'
  import Icon from './components/Icon.svelte'
  import Viewer from './components/Viewer.svelte'
  import Dialog from './components/Dialog.svelte'
  import Toasts from './components/Toasts.svelte'
  import Uploader from './components/Uploader.svelte'
  import Login from './views/Login.svelte'
  import Photos from './views/Photos.svelte'
  import Albums from './views/Albums.svelte'
  import Favorites from './views/Favorites.svelte'
  import Trash from './views/Trash.svelte'
  import Search from './views/Search.svelte'
  import Hidden from './views/Hidden.svelte'
  import SearchBox from './components/SearchBox.svelte'

  const nav = [
    { href: '/', label: 'Photos', icon: 'photos' },
    { href: '/albums', label: 'Albums', icon: 'albums' },
    { href: '/favorites', label: 'Favorites', icon: 'heart' },
    { href: '/trash', label: 'Trash', icon: 'trash' },
  ]

  const page = $derived(
    route.path === '/' ? 'photos'
    : route.path === '/albums' || route.path.startsWith('/albums/') ? 'albums'
    : route.path === '/favorites' ? 'favorites'
    : route.path === '/trash' ? 'trash'
    : route.path === '/search' ? 'search'
    : route.path === '/hidden' ? 'hidden'
    : 'other',
  )
  const albumPath = $derived(page === 'albums' ? route.path.slice('/albums/'.length) : '')
  const active = (href) => (href === '/' ? page === 'photos' : route.path.startsWith(href))

  // viewer pages through the slideshow list, or whatever the current page shows
  const viewerItems = $derived(app.slideshow?.items ?? app.context)
  const showViewer = $derived(!!route.photo && viewerItems.some((i) => i.path === route.photo))

  // selection bar acts on these
  // hidden-album items aren't in the library, so also look in what's on screen
  const byPath = $derived(new Map([...(app.library || []), ...app.context].map((i) => [i.path, i])))
  const selected = $derived([...selection].map((p) => byPath.get(p)).filter(Boolean))
  const allFav = $derived(selected.length > 0 && selected.every((i) => favs.has(i.path)))

  $effect(() => {
    if (app.authed === true && !app.library) loadLibrary().catch(fail)
    if (app.authed === true && route.path === '/login') navigate('/', { replace: true })
  })
  $effect(() => {
    page // leaving a page drops its selection
    selection.clear()
  })
  $effect(() => {
    if (page !== 'search') app.search = ''
  })
  $effect(() => {
    if (page === 'other' && app.authed) navigate('/', { replace: true })
  })

  // in-app links without full page loads
  function linkClick(e) {
    const a = e.target.closest?.('a[href]')
    if (!a || e.defaultPrevented || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    if (a.target || a.hasAttribute('download') || a.origin !== location.origin) return
    if (/^\/(t|m|d|tt|api)\//.test(a.pathname)) return
    e.preventDefault()
    navigate(a.pathname + a.search)
  }

  function key(e) {
    if (e.key === 'Escape' && selection.size && !route.photo && !app.dialog) selection.clear()
  }

  onMount(() => {
    setUnauthorizedHandler(() => {
      if (app.authed) signedOut()
    })
    checkSession()
  })
</script>

<svelte:window onclick={linkClick} onkeydown={key} />

{#if app.authed === null}
  <div class="boot"><div class="spinner"></div></div>
{:else if !app.authed}
  <Login />
{:else}
  <div class="shell">
    <aside class="sidebar">
      <a class="brand" href="/"><img src="/icon.svg" alt="" width="30" height="30" /> <span>Gallery</span></a>
      <nav aria-label="Main">
        {#each nav as n (n.href)}
          <a href={n.href} class:active={active(n.href)} aria-current={active(n.href) ? 'page' : undefined}>
            <Icon name={n.icon} filled={active(n.href)} />
            <span>{n.label}</span>
          </a>
        {/each}
      </nav>
      <div class="side-foot">
        {#if app.library}<span>{app.library.length.toLocaleString()} items</span>{/if}
        {#if app.scanning}<span class="scan"><span class="dot"></span>Indexing new photos…</span>{/if}
      </div>
    </aside>

    <header class="topbar" class:selecting={selection.size > 0 && page !== 'trash'}>
      {#if selection.size > 0 && page !== 'trash'}
        <button class="icon-btn" onclick={() => selection.clear()} aria-label="Clear selection"><Icon name="close" /></button>
        <strong class="count">{selection.size} selected</strong>
        <div class="tools">
          <button class="icon-btn" onclick={() => setFavorite(selection, !allFav)} aria-label={allFav ? 'Remove from favorites' : 'Add to favorites'} title={allFav ? 'Remove from favorites' : 'Add to favorites'}>
            <Icon name="heart" filled={allFav} />
          </button>
          <button class="icon-btn" onclick={() => moveTo(selection)} aria-label="Move to album" title="Move to album"><Icon name="move" /></button>
          <button class="icon-btn" onclick={() => download(selected)} aria-label="Download" title="Download"><Icon name="download" /></button>
          <button class="icon-btn" onclick={() => deletePaths(selection)} aria-label="Move to trash" title="Move to trash"><Icon name="trash" /></button>
        </div>
      {:else}
        <a class="brand mobile" href="/"><img src="/icon.svg" alt="" width="28" height="28" /> <span>Gallery</span></a>
        <SearchBox />
        <div class="spacer"></div>
        {#if page !== 'trash'}
          <button class="btn upload" onclick={() => pick()}>
            <Icon name="upload" size={20} /><span class="label">Upload</span>
          </button>
        {/if}
        <button class="icon-btn" onclick={logout} aria-label="Lock" title="Lock"><Icon name="lock" /></button>
      {/if}
    </header>

    <main class="content">
      {#if page === 'photos'}
        <Photos />
      {:else if page === 'albums'}
        {#key albumPath}<Albums path={albumPath} />{/key}
      {:else if page === 'favorites'}
        <Favorites />
      {:else if page === 'trash'}
        <Trash />
      {:else if page === 'search'}
        <Search />
      {:else if page === 'hidden'}
        <Hidden />
      {/if}
    </main>

    <nav class="bottomnav" aria-label="Main">
      {#each nav as n (n.href)}
        <a href={n.href} class:active={active(n.href)} aria-current={active(n.href) ? 'page' : undefined}>
          <span class="pill"><Icon name={n.icon} filled={active(n.href)} /></span>
          <span>{n.label}</span>
        </a>
      {/each}
    </nav>
  </div>

  {#if showViewer}
    <Viewer items={viewerItems} path={route.photo} autoplay={!!app.slideshow} />
  {/if}
  <Uploader />
{/if}

{#if app.dialog}
  {#key app.dialog}<Dialog dialog={app.dialog} />{/key}
{/if}
<Toasts />

<style>
  .boot {
    min-height: 100dvh;
    display: grid;
    place-items: center;
  }
  .shell {
    min-height: 100dvh;
    display: grid;
    grid-template-columns: var(--sidebar) 1fr;
    grid-template-rows: auto 1fr;
    grid-template-areas: 'side top' 'side main';
  }
  .sidebar {
    grid-area: side;
    position: sticky;
    top: 0;
    height: 100dvh;
    display: flex;
    flex-direction: column;
    padding: calc(var(--safe-t) + 12px) 12px calc(var(--safe-b) + 16px) calc(var(--safe-l) + 12px);
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    height: 44px;
    padding: 0 0.7rem;
    margin-bottom: 0.75rem;
    text-decoration: none;
    font-size: 1.2rem;
    font-weight: 600;
    letter-spacing: -0.01em;
  }
  .brand img {
    border-radius: 8px;
  }
  .sidebar nav {
    display: grid;
    gap: 2px;
  }
  .sidebar nav a {
    display: flex;
    align-items: center;
    gap: 1.1rem;
    height: 48px;
    padding: 0 1.2rem;
    border-radius: 999px;
    text-decoration: none;
    color: var(--muted);
    font-weight: 500;
  }
  .sidebar nav a:hover {
    background: var(--hover);
  }
  .sidebar nav a.active {
    background: var(--accent-soft);
    color: var(--accent);
  }
  .side-foot {
    margin-top: auto;
    display: grid;
    gap: 0.4rem;
    padding: 0 1.2rem;
    color: var(--faint);
    font-size: 0.82rem;
  }
  .scan {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse {
    50% {
      opacity: 0.3;
    }
  }

  .topbar {
    grid-area: top;
    position: sticky;
    top: 0;
    z-index: 20;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    min-height: calc(var(--topbar) + var(--safe-t));
    padding: var(--safe-t) calc(var(--safe-r) + 16px) 0 16px;
    background: color-mix(in srgb, var(--bg) 88%, transparent);
    backdrop-filter: saturate(1.4) blur(14px);
    -webkit-backdrop-filter: saturate(1.4) blur(14px);
  }
  .topbar.selecting {
    background: var(--accent-soft);
    backdrop-filter: none;
  }
  .count {
    flex: 1;
    font-weight: 500;
    font-size: 1.05rem;
  }
  .tools {
    display: flex;
    gap: 2px;
  }
  .spacer {
    flex: 1;
  }
  .brand.mobile {
    display: none;
    margin: 0;
    padding: 0;
  }
  .content {
    grid-area: main;
    min-width: 0;
    padding: 0 calc(var(--safe-r) + 24px) calc(var(--safe-b) + 48px + var(--nav-offset)) 8px;
  }
  .bottomnav {
    display: none;
  }

  /* tablets & phones: bottom tabs instead of the sidebar */
  @media (max-width: 899px) {
    .shell {
      grid-template-columns: 1fr;
      grid-template-areas: 'top' 'main';
    }
    .sidebar {
      display: none;
    }
    .brand.mobile {
      display: flex;
    }
    .content {
      padding-left: calc(var(--safe-l) + 12px);
      padding-right: calc(var(--safe-r) + 12px);
    }
    .bottomnav {
      position: fixed;
      z-index: 20;
      left: 0;
      right: 0;
      bottom: 0;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      height: calc(var(--bottomnav) + var(--safe-b));
      padding: 0 var(--safe-r) var(--safe-b) var(--safe-l);
      background: color-mix(in srgb, var(--bg) 92%, transparent);
      backdrop-filter: saturate(1.4) blur(14px);
      -webkit-backdrop-filter: saturate(1.4) blur(14px);
      border-top: 1px solid var(--line);
    }
    .bottomnav a {
      display: grid;
      justify-items: center;
      align-content: center;
      gap: 2px;
      text-decoration: none;
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 500;
    }
    .pill {
      display: grid;
      place-items: center;
      width: 56px;
      height: 30px;
      border-radius: 999px;
      transition: background 0.15s;
    }
    .bottomnav a.active {
      color: var(--text);
    }
    .bottomnav a.active .pill {
      background: var(--accent-soft);
      color: var(--accent);
    }
  }
  @media (max-width: 520px) {
    .upload {
      width: 40px;
      padding: 0;
      justify-content: center;
      border: 0;
      background: none;
    }
    .upload .label {
      display: none;
    }
  }
  /* landscape phones: keep the photo area as tall as possible */
  @media (max-height: 500px) and (orientation: landscape) {
    .shell {
      --topbar: 52px;
    }
  }
</style>
