<script>
  import { api } from '../lib/api.js'
  import { app, lockHidden, changeCode, fail } from '../lib/state.svelte.js'
  import { navigate } from '../lib/router.svelte.js'
  import { plural } from '../lib/format.js'
  import Icon from '../components/Icon.svelte'
  import Menu from '../components/Menu.svelte'
  import AlbumCard from '../components/AlbumCard.svelte'

  let data = $state(null)

  $effect(() => {
    app.version
    api('/api/hidden')
      .then((d) => {
        // locked (or timed out): behave as if this page doesn't exist
        if (!d.unlocked) navigate('/', { replace: true })
        else data = d
      })
      .catch(fail)
  })
  $effect(() => {
    app.context = []
    app.uploadTarget = ''
  })

  async function hideAgain() {
    await lockHidden()
    navigate('/', { replace: true })
  }
</script>

<svelte:head><title>Gallery</title></svelte:head>

{#if !data}
  <div class="empty-state"><div class="spinner"></div></div>
{:else}
  <div class="page-head">
    <div>
      <h1><Icon name="lock-open" size={26} /> Hidden albums</h1>
      <p class="sub">Not shown anywhere else. They hide again when you lock the gallery or after 15 minutes unused.</p>
    </div>
    <div class="page-actions">
      <button class="btn primary" onclick={hideAgain}><Icon name="eye-off" size={20} />Hide again</button>
      <Menu items={[{ icon: 'edit', label: 'Change secret code', run: changeCode }]} label="Hidden album options" />
    </div>
  </div>

  {#if !data.albums.length}
    <div class="empty-state">
      <Icon name="eye-off" size={48} />
      <h2>Nothing hidden yet</h2>
      <p>Open an album, tap ⋮ and choose <strong>Hide album</strong>.</p>
    </div>
  {:else}
    <ul class="albums">
      {#each data.albums as a (a.path)}
        <li>
          <AlbumCard album={a} hiddenRoot sub="{a.path.includes('/') ? `in ${a.path.split('/').slice(0, -1).join(' / ')} · ` : ''}{a.count ? plural(a.count, 'item') : 'Empty'}" />
        </li>
      {/each}
    </ul>
  {/if}
{/if}

<style>
  h1 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .albums {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(160px, 42vw), 1fr));
    gap: 1.25rem 1rem;
  }
</style>
