<script>
  import { SvelteSet } from 'svelte/reactivity'
  import { api, post } from '../lib/api.js'
  import { app, ask, restore, fail, toast } from '../lib/state.svelte.js'
  import { plural } from '../lib/format.js'
  import Icon from '../components/Icon.svelte'

  let list = $state(null)
  const picked = new SvelteSet()

  $effect(() => {
    app.version
    api('/api/trash').then((l) => (list = l)).catch(fail)
  })
  $effect(() => {
    app.context = []
  })

  const daysLeft = (t) => Math.max(0, Math.ceil((t.expires * 1000 - Date.now()) / 86400000))

  async function restoreSel() {
    await restore([...picked])
    picked.clear()
  }

  async function purge(all) {
    const n = all ? list.length : picked.size
    const ok = await ask({
      kind: 'confirm',
      title: all ? 'Empty trash?' : `Delete ${plural(n, 'item')} forever?`,
      body: "This can't be undone.",
      confirm: 'Delete forever',
      danger: true,
    })
    if (!ok) return
    try {
      await post('/api/trash/delete', all ? { all: true } : { ids: [...picked] })
      picked.clear()
      app.version++
      toast(`${plural(n, 'item')} deleted forever`)
    } catch (e) {
      fail(e)
    }
  }

  function toggle(id) {
    picked.has(id) ? picked.delete(id) : picked.add(id)
  }
</script>

<svelte:head><title>Trash · Gallery</title></svelte:head>

<svelte:window onkeydown={(e) => e.key === 'Escape' && !app.dialog && picked.clear()} />

{#if !list}
  <div class="empty-state"><div class="spinner"></div></div>
{:else}
  <div class="page-head">
    <div>
      <h1>Trash</h1>
      <p class="sub">Items are deleted forever after 30 days</p>
    </div>
    {#if list.length}
      <div class="page-actions">
        {#if picked.size}
          <button class="btn" onclick={() => picked.clear()}><Icon name="close" size={18} />{picked.size} selected</button>
          <button class="btn primary" onclick={restoreSel}><Icon name="restore" size={20} />Restore</button>
          <button class="btn danger" onclick={() => purge(false)}>Delete forever</button>
        {:else}
          <button class="btn" onclick={() => list.forEach((t) => picked.add(t.id))}><Icon name="select" size={20} />Select all</button>
          <button class="btn danger" onclick={() => purge(true)}><Icon name="trash" size={20} />Empty trash</button>
        {/if}
      </div>
    {/if}
  </div>

  {#if !list.length}
    <div class="empty-state">
      <Icon name="trash" size={48} />
      <h2>Trash is empty</h2>
      <p>Things you delete stay here for 30 days, so you can change your mind.</p>
    </div>
  {:else}
    <ul class="grid">
      {#each list as t (t.id)}
        <li>
          <button class="tile" class:sel={picked.has(t.id)} onclick={() => toggle(t.id)} aria-pressed={picked.has(t.id)} aria-label="{t.name}, from {t.from.split('/').slice(0, -1).join('/') || 'Library'}">
            <img src="/tt/{t.id}" alt="" loading="lazy" onload={(e) => e.currentTarget.classList.add('in')} />
            {#if t.kind === 'video'}<span class="vid"><Icon name="play" size={14} /></span>{/if}
            <span class="check"><Icon name={picked.has(t.id) ? 'check-circle' : 'circle'} size={22} /></span>
            <span class="days">{daysLeft(t)} {daysLeft(t) === 1 ? 'day' : 'days'}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
{/if}

<style>
  .grid {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(140px, 30vw), 1fr));
    gap: 4px;
  }
  .tile {
    position: relative;
    display: block;
    width: 100%;
    aspect-ratio: 1;
    padding: 0;
    border: 0;
    background: var(--tile);
    cursor: pointer;
    overflow: hidden;
  }
  img {
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
  .sel {
    background: var(--accent-soft);
  }
  .sel img {
    transform: scale(0.86);
    border-radius: 6px;
  }
  .check {
    position: absolute;
    left: 6px;
    top: 6px;
    display: grid;
    color: #fff;
    filter: drop-shadow(0 1px 2px rgb(0 0 0 / 0.6));
  }
  .sel .check {
    color: var(--accent);
    filter: none;
  }
  .days,
  .vid {
    position: absolute;
    right: 6px;
    padding: 0 6px;
    border-radius: 999px;
    background: rgb(0 0 0 / 0.5);
    color: #fff;
    font-size: 0.72rem;
    line-height: 1.6;
  }
  .days {
    bottom: 6px;
  }
  .vid {
    top: 6px;
    display: grid;
    place-items: center;
    padding: 2px;
  }
</style>
