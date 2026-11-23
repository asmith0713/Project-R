<script>
  import { api, thumbUrl, albumUrl } from '../lib/api.js'
  import { app, newAlbum, renameAlbum, deleteAlbum } from '../lib/state.svelte.js'
  import { openPhoto, navigate } from '../lib/router.svelte.js'
  import { countLabel, plural } from '../lib/format.js'
  import { pick } from '../lib/uploads.svelte.js'
  import PhotoGrid from '../components/PhotoGrid.svelte'
  import Icon from '../components/Icon.svelte'
  import Menu from '../components/Menu.svelte'

  let { path = '' } = $props()

  let data = $state(null)
  let error = $state('')

  $effect(() => {
    app.version // reload after uploads, moves, renames…
    const p = path
    api(`/api/albums?path=${encodeURIComponent(p)}`)
      .then((d) => {
        if (p === path) {
          data = d
          error = ''
        }
      })
      .catch((e) => (error = e.message))
  })

  const items = $derived(data?.items || [])
  $effect(() => {
    app.context = items
    app.uploadTarget = path
  })

  const isRoot = $derived(!path)
  const total = $derived((data?.albums || []).reduce((s, a) => s + a.count, 0) + items.length)

  function slideshow() {
    const prefix = path ? path + '/' : ''
    const all = (app.library || []).filter((i) => !path || i.path.startsWith(prefix))
    if (!all.length) return
    const list = [...all]
    for (let i = list.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[list[i], list[j]] = [list[j], list[i]]
    }
    app.slideshow = { items: list }
    openPhoto(list[0].path)
  }

  async function create() {
    const p = await newAlbum(path)
    if (p) navigate(albumUrl(p))
  }
  async function rename() {
    const p = await renameAlbum(path)
    if (p) navigate(albumUrl(p), { replace: true })
  }
  async function remove() {
    const parent = path.split('/').slice(0, -1).join('/')
    if (await deleteAlbum(path)) navigate(albumUrl(parent), { replace: true })
  }

  const menu = $derived([
    { icon: 'folder-plus', label: 'New album inside', run: create },
    { icon: 'edit', label: 'Rename album', run: rename },
    { icon: 'trash', label: 'Delete album', run: remove, danger: true, hidden: total > 0 },
  ])
</script>

<svelte:head><title>{data?.name || 'Albums'} · Gallery</title></svelte:head>

{#if error}
  <div class="empty-state">
    <Icon name="albums" size={48} />
    <h2>{error}</h2>
    <a class="btn" href="/albums">All albums</a>
  </div>
{:else if !data}
  <div class="empty-state"><div class="spinner"></div></div>
{:else}
  {#if !isRoot}
    <nav class="crumbs" aria-label="Album path">
      <a href="/albums">Albums</a>
      {#each data.crumbs.slice(0, -1) as c (c.path)}
        <Icon name="right" size={16} /><a href={albumUrl(c.path)}>{c.name}</a>
      {/each}
    </nav>
  {/if}

  <div class="page-head">
    <div>
      <h1>{data.name}</h1>
      <p class="sub">
        {#if isRoot}{plural(data.albums.length, 'album')}{:else}{data.albums.length ? `${plural(data.albums.length, 'album')} · ` : ''}{plural(total, 'item')}{/if}
      </p>
    </div>
    <div class="page-actions">
      {#if total}
        <button class="btn" onclick={slideshow}><Icon name="shuffle" size={20} />Slideshow</button>
      {/if}
      {#if isRoot}
        <button class="btn" onclick={create}><Icon name="plus" size={20} />New album</button>
      {:else}
        <Menu items={menu} label="Album options" />
      {/if}
    </div>
  </div>

  {#if data.albums.length}
    <ul class="albums">
      {#each data.albums as a (a.path)}
        <li>
          <a href={albumUrl(a.path)} class="card">
            <div class="cover">
              {#if a.cover}
                <img src={thumbUrl(a.cover)} alt="" loading="lazy" onload={(e) => e.currentTarget.classList.add('in')} />
              {:else}
                <Icon name="folder" size={40} />
              {/if}
            </div>
            <strong>{a.name}</strong>
            <span>{a.count ? plural(a.count, 'item') : 'Empty'}</span>
          </a>
        </li>
      {/each}
    </ul>
  {/if}

  {#if items.length}
    {#if isRoot || data.albums.length}
      <h2 class="section">{isRoot ? 'Not in an album' : 'In this album'} <span>{countLabel(items)}</span></h2>
    {/if}
    <PhotoGrid {items} grouped={false} onopen={(i) => openPhoto(items[i].path)} />
  {:else if !data.albums.length}
    <div class="empty-state small">
      <Icon name="image" size={44} />
      <h2>This album is empty</h2>
      <p>Upload photos here, or move some in from Photos.</p>
      <button class="btn primary" onclick={() => pick(path)}><Icon name="upload" size={20} />Upload here</button>
    </div>
  {/if}
{/if}

<style>
  .crumbs {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.2rem;
    padding-top: 0.5rem;
    color: var(--muted);
    font-size: 0.9rem;
  }
  .crumbs a {
    text-decoration: none;
    padding: 0.1rem 0.25rem;
    border-radius: 4px;
  }
  .crumbs a:hover {
    color: var(--text);
    background: var(--hover);
  }
  .albums {
    list-style: none;
    margin: 0 0 1.5rem;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(160px, 42vw), 1fr));
    gap: 1.25rem 1rem;
  }
  @media (max-width: 420px) {
    .albums {
      grid-template-columns: repeat(2, 1fr);
      gap: 1rem 0.6rem;
    }
  }
  .card {
    display: grid;
    gap: 0.15rem;
    text-decoration: none;
  }
  .cover {
    aspect-ratio: 1;
    display: grid;
    place-items: center;
    border-radius: var(--radius);
    overflow: hidden;
    background: var(--tile);
    color: var(--faint);
    margin-bottom: 0.45rem;
    transition: transform 0.15s;
  }
  .card:hover .cover {
    transform: scale(1.02);
  }
  .cover img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition: opacity 0.25s;
  }
  .cover img:global(.in) {
    opacity: 1;
  }
  .card strong {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .card span {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .section {
    margin: 0.5rem 0 0.75rem;
    font-size: 1rem;
    font-weight: 500;
  }
  .section span {
    color: var(--muted);
    font-weight: 400;
    font-size: 0.9rem;
    margin-left: 0.4rem;
  }
  .empty-state.small {
    padding-top: 10vh;
  }
</style>
