<script>
  import { api, albumUrl } from '../lib/api.js'
  import { app } from '../lib/state.svelte.js'
  import { openPhoto } from '../lib/router.svelte.js'
  import { countLabel, monthLabel } from '../lib/format.js'
  import PhotoGrid from '../components/PhotoGrid.svelte'
  import Icon from '../components/Icon.svelte'

  let folders = $state([])
  $effect(() => {
    app.version
    api('/api/folders?search=1').then((f) => (folders = f)).catch(() => {})
  })

  const q = $derived(app.search.trim().toLowerCase())
  const albums = $derived(q ? folders.filter((f) => f.split('/').pop().toLowerCase().includes(q)).slice(0, 24) : [])
  // file name, album, or month/year ("june", "2024", "june 2024")
  const items = $derived(
    q
      ? (app.library || []).filter(
          (i) => i.name.toLowerCase().includes(q) || i.folder.toLowerCase().includes(q) || monthLabel(i.date).toLowerCase().includes(q),
        )
      : [],
  )
  $effect(() => {
    app.context = items
    app.uploadTarget = ''
  })
</script>

<svelte:head><title>Search · Gallery</title></svelte:head>

{#if !q}
  <div class="empty-state">
    <Icon name="search" size={48} />
    <h2>Search your gallery</h2>
    <p>Find photos by file name, album, month or year.</p>
  </div>
{:else if !albums.length && !items.length}
  <div class="empty-state">
    <Icon name="search" size={48} />
    <h2>No results for “{app.search.trim()}”</h2>
    <p>Try a file name, an album name, a month or a year.</p>
  </div>
{:else}
  <div class="page-head">
    <div>
      <h1>Results for “{app.search.trim()}”</h1>
      <p class="sub">{items.length ? countLabel(items) : 'No photos'}{albums.length ? ` · ${albums.length} album${albums.length === 1 ? '' : 's'}` : ''}</p>
    </div>
  </div>
  {#if albums.length}
    <ul class="chips">
      {#each albums as f (f)}
        <li>
          <a href={albumUrl(f)}><Icon name="albums" size={18} /><span>{f.split('/').pop()}</span>{#if f.includes('/')}<small>{f.split('/').slice(0, -1).join(' / ')}</small>{/if}</a>
        </li>
      {/each}
    </ul>
  {/if}
  {#if items.length}
    <PhotoGrid {items} grouped onopen={(i) => openPhoto(items[i].path)} />
  {/if}
{/if}

<style>
  .chips {
    list-style: none;
    margin: 0 0 1.25rem;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .chips a {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    max-width: 100%;
    padding: 0.45rem 0.9rem 0.45rem 0.7rem;
    border: 1px solid var(--line);
    border-radius: 999px;
    text-decoration: none;
    color: var(--text);
  }
  .chips a:hover {
    background: var(--hover);
  }
  .chips :global(svg) {
    color: var(--muted);
    flex: none;
  }
  .chips span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  small {
    color: var(--faint);
  }
</style>
