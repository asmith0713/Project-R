<script>
  import { api, albumUrl } from '../lib/api.js'
  import { app, favs, newAlbum, lockHidden } from '../lib/state.svelte.js'
  import { albumMenu } from '../lib/albumMenu.js'
  import { openPhoto, navigate } from '../lib/router.svelte.js'
  import { countLabel, plural } from '../lib/format.js'
  import { pick } from '../lib/uploads.svelte.js'
  import PhotoGrid from '../components/PhotoGrid.svelte'
  import Icon from '../components/Icon.svelte'
  import Menu from '../components/Menu.svelte'
  import AlbumCard from '../components/AlbumCard.svelte'

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
          // items in hidden albums aren't in the library, so take their hearts from here
          for (const it of d.items) if (it.fav) favs.add(it.path)
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
    const all = data.hidden ? items : (app.library || []).filter((i) => !path || i.path.startsWith(prefix))
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
  const parent = $derived(path.split('/').slice(0, -1).join('/'))
  const menu = $derived(
    data && !isRoot
      ? albumMenu(
          { path, count: total },
          {
            hiddenRoot: data.hiddenRoot,
            insideHidden: data.hidden && !data.hiddenRoot,
            extra: [{ icon: 'folder-plus', label: 'New album inside', run: create }],
            on: {
              renamed: (p) => navigate(albumUrl(p), { replace: true }),
              moved: (p) => navigate(albumUrl(p), { replace: true }),
              deleted: () => navigate(albumUrl(parent), { replace: true }),
              hidden: () => navigate('/hidden'),
            },
          },
        )
      : [],
  )

  async function hideAgain() {
    await lockHidden()
    navigate('/', { replace: true })
  }
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
      <h1>
        {#if data.hidden}<span class="hidden-badge" title="Hidden album"><Icon name="lock" size={18} /></span>{/if}
        {data.name}
      </h1>
      <p class="sub">
        {#if isRoot}{plural(data.albums.length, 'album')}{:else}{data.albums.length ? `${plural(data.albums.length, 'album')} · ` : ''}{plural(total, 'item')}{/if}
      </p>
    </div>
    <div class="page-actions">
      {#if total}
        <button class="btn" onclick={slideshow}><Icon name="shuffle" size={20} />Slideshow</button>
      {/if}
      {#if data.hidden}
        <button class="btn" onclick={hideAgain}><Icon name="eye-off" size={20} />Hide again</button>
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
        <li><AlbumCard album={a} insideHidden={data.hidden} /></li>
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
  .hidden-badge {
    display: inline-grid;
    place-items: center;
    width: 30px;
    height: 30px;
    margin-right: 0.35rem;
    vertical-align: 0.15em;
    border-radius: 50%;
    background: var(--accent-soft);
    color: var(--accent);
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
