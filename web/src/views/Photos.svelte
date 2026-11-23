<script>
  import { app } from '../lib/state.svelte.js'
  import { openPhoto } from '../lib/router.svelte.js'
  import { countLabel } from '../lib/format.js'
  import { pick } from '../lib/uploads.svelte.js'
  import PhotoGrid from '../components/PhotoGrid.svelte'
  import Icon from '../components/Icon.svelte'

  const items = $derived(app.library || [])
  $effect(() => {
    app.context = items
    app.uploadTarget = ''
  })
</script>

<svelte:head><title>Photos · Gallery</title></svelte:head>

{#if !app.library}
  <div class="empty-state"><div class="spinner"></div></div>
{:else if !items.length}
  <div class="empty-state">
    {#if app.scanning}
      <div class="spinner"></div>
      <h2>Finding your photos…</h2>
      <p>The first look through the drive takes a minute. This page fills in by itself.</p>
    {:else}
      <Icon name="photos" size={48} />
      <h2>No photos yet</h2>
      <p>Upload from this device, or copy photos onto the drive.</p>
      <button class="btn primary" onclick={() => pick('')}><Icon name="upload" size={20} />Upload</button>
    {/if}
  </div>
{:else}
  <div class="page-head">
    <div>
      <h1>Photos</h1>
      <p class="sub">{countLabel(items)}</p>
    </div>
  </div>
  <PhotoGrid {items} grouped scrubber onopen={(i) => openPhoto(items[i].path)} />
{/if}
