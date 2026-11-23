<script>
  import { onMount } from 'svelte'
  import { uploads, add, retry, clear } from '../lib/uploads.svelte.js'
  import { app } from '../lib/state.svelte.js'
  import { bytes } from '../lib/format.js'
  import Icon from './Icon.svelte'

  let input
  let target = null // album chosen when the picker opened; null = the page's album
  let dragging = $state(false)
  let depth = 0
  let expanded = $state(false)

  onMount(() => {
    uploads.picker = (t) => {
      target = t
      input.click()
    }
  })

  const busy = $derived(uploads.files.filter((u) => u.state === 'uploading' || u.state === 'queued'))
  const errors = $derived(uploads.files.filter((u) => u.state === 'error'))
  const done = $derived(uploads.files.filter((u) => u.state === 'done'))
  const total = $derived(uploads.files.reduce((s, u) => s + u.total, 0))
  const loaded = $derived(uploads.files.reduce((s, u) => s + (u.state === 'error' ? u.total : u.loaded), 0))
  const pct = $derived(total ? Math.round((loaded / total) * 100) : 0)

  const hasFiles = (e) => [...(e.dataTransfer?.types || [])].includes('Files')
</script>

<svelte:window
  ondragenter={(e) => {
    if (!hasFiles(e) || !app.authed) return
    depth++
    dragging = true
  }}
  ondragleave={() => {
    depth = Math.max(0, depth - 1)
    if (!depth) dragging = false
  }}
  ondragover={(e) => hasFiles(e) && e.preventDefault()}
  ondrop={(e) => {
    if (!hasFiles(e)) return
    e.preventDefault()
    depth = 0
    dragging = false
    if (app.authed) add(e.dataTransfer.files, app.uploadTarget)
  }}
/>

<input
  bind:this={input}
  type="file"
  multiple
  accept="image/*,video/*,.heic,.heif,.dng"
  hidden
  onchange={(e) => {
    add(e.currentTarget.files, target ?? app.uploadTarget)
    e.currentTarget.value = ''
    target = null
  }}
/>

{#if dragging}
  <div class="drop">
    <div><Icon name="upload" size={40} /><p>Drop to upload to <strong>{app.uploadTarget || 'Library'}</strong></p></div>
  </div>
{/if}

{#if uploads.open && uploads.files.length}
  <section class="panel" aria-label="Uploads">
    <header>
      <div class="summary">
        {#if busy.length}
          <strong>Uploading {done.length + errors.length + 1} of {uploads.files.length}</strong>
          <span>{pct}% · {bytes(loaded)} of {bytes(total)}</span>
        {:else}
          <strong>{done.length} uploaded{errors.length ? `, ${errors.length} failed` : ''}</strong>
        {/if}
      </div>
      <button class="icon-btn" onclick={() => (expanded = !expanded)} aria-label={expanded ? 'Hide files' : 'Show files'} aria-expanded={expanded}>
        <span class="chev" class:up={expanded}><Icon name="right" /></span>
      </button>
      {#if !busy.length}
        <button class="icon-btn" onclick={clear} aria-label="Close"><Icon name="close" /></button>
      {/if}
    </header>
    <div class="bar"><div style:width="{pct}%" class:err={!busy.length && errors.length}></div></div>
    {#if expanded || errors.length}
      <ul>
        {#each expanded ? uploads.files : errors as u (u.id)}
          <li class={u.state}>
            <span class="name">{u.name}</span>
            <span class="st">
              {#if u.state === 'error'}{u.error}
              {:else if u.state === 'done'}<Icon name="check" size={18} />
              {:else if u.state === 'uploading'}{Math.round((u.loaded / (u.total || 1)) * 100)}%
              {:else}Waiting{/if}
            </span>
          </li>
        {/each}
      </ul>
    {/if}
    {#if !busy.length && errors.some((u) => u.file)}
      <div class="foot"><button class="btn" onclick={retry}>Retry failed</button></div>
    {/if}
  </section>
{/if}

<style>
  .drop {
    position: fixed;
    inset: 0;
    z-index: 80;
    display: grid;
    place-items: center;
    background: color-mix(in srgb, var(--accent) 18%, transparent);
    border: 3px dashed var(--accent);
    pointer-events: none;
  }
  .drop div {
    display: grid;
    justify-items: center;
    gap: 0.5rem;
    padding: 1.5rem 2rem;
    border-radius: 16px;
    background: var(--raised);
    box-shadow: var(--shadow);
    color: var(--accent);
  }
  .drop p {
    margin: 0;
    color: var(--text);
  }
  .panel {
    position: fixed;
    z-index: 40;
    right: calc(var(--safe-r) + 16px);
    bottom: calc(var(--safe-b) + 16px + var(--nav-offset, 0px));
    width: min(360px, calc(100vw - 32px));
    border-radius: 14px;
    background: var(--raised);
    border: 1px solid var(--line);
    box-shadow: var(--shadow);
    overflow: hidden;
  }
  header {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.6rem 0.5rem 0.5rem 1rem;
  }
  .summary {
    flex: 1;
    display: grid;
    line-height: 1.3;
  }
  .summary span {
    color: var(--muted);
    font-size: 0.85rem;
  }
  .chev {
    display: grid;
    transform: rotate(-90deg);
    transition: transform 0.15s;
  }
  .chev.up {
    transform: rotate(90deg);
  }
  .bar {
    height: 3px;
    background: var(--line);
  }
  .bar div {
    height: 100%;
    background: var(--accent);
    transition: width 0.2s;
  }
  .bar .err {
    background: var(--danger);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0.25rem 0;
    max-height: 40dvh;
    overflow-y: auto;
  }
  li {
    display: flex;
    gap: 0.75rem;
    justify-content: space-between;
    padding: 0.4rem 1rem;
    font-size: 0.88rem;
  }
  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .st {
    flex: none;
    color: var(--muted);
    display: inline-flex;
  }
  .done .st {
    color: var(--accent);
  }
  .error .st {
    color: var(--danger);
    max-width: 55%;
    text-align: right;
  }
  .foot {
    padding: 0.5rem 1rem 0.8rem;
  }
</style>
