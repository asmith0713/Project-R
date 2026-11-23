<script>
  import { app, favs } from '../lib/state.svelte.js'
  import { openPhoto, route } from '../lib/router.svelte.js'
  import { countLabel } from '../lib/format.js'
  import PhotoGrid from '../components/PhotoGrid.svelte'
  import Icon from '../components/Icon.svelte'

  // keep the open photo in the list even if it's un-hearted in the viewer
  const items = $derived((app.library || []).filter((i) => favs.has(i.path) || i.path === route.photo))
  $effect(() => {
    app.context = items
    app.uploadTarget = ''
  })
</script>

<svelte:head><title>Favorites · Gallery</title></svelte:head>

{#if !app.library}
  <div class="empty-state"><div class="spinner"></div></div>
{:else if !items.length}
  <div class="empty-state">
    <Icon name="heart" size={48} />
    <h2>No favorites yet</h2>
    <p>Tap the heart on any photo or video to find it here quickly.</p>
  </div>
{:else}
  <div class="page-head">
    <div>
      <h1>Favorites</h1>
      <p class="sub">{countLabel(items)}</p>
    </div>
  </div>
  <PhotoGrid {items} grouped onopen={(i) => openPhoto(items[i].path)} />
{/if}
