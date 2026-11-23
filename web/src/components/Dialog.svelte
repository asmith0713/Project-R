<script>
  import { onMount } from 'svelte'
  import { api } from '../lib/api.js'
  import { app } from '../lib/state.svelte.js'
  import Icon from './Icon.svelte'

  let { dialog } = $props()
  // svelte-ignore state_referenced_locally
  let value = $state(dialog.value ?? '') // App re-creates this component per dialog
  let folders = $state(null)
  let filter = $state('')
  let creating = $state(false)
  let newName = $state('')
  let box

  const shown = $derived(
    (folders || []).filter((f) => !filter || f.toLowerCase().includes(filter.toLowerCase())),
  )

  onMount(() => {
    if (dialog.kind === 'album') api('/api/folders').then((f) => (folders = f)).catch(() => (folders = []))
    const prev = document.activeElement
    queueMicrotask(() => {
      const input = box.querySelector('input')
      if (input) {
        input.focus()
        input.select()
      } else box.querySelector('.primary, button')?.focus()
    })
    return () => prev?.focus?.()
  })

  const done = (v) => dialog.resolve(v)
  function submit(e) {
    e.preventDefault()
    if (dialog.kind === 'prompt') done(value.trim() || null)
    else if (dialog.kind === 'confirm') done(true)
  }
  async function createAndPick() {
    const name = newName.trim()
    if (!name) return
    try {
      const r = await api('/api/mkdir', { method: 'POST', json: { folder: '', name } })
      app.version++
      done(r.path)
    } catch (e) {
      alertMsg = e.message
    }
  }
  let alertMsg = $state('')

  function key(e) {
    if (e.key === 'Escape') {
      e.stopPropagation()
      done(dialog.kind === 'confirm' ? false : null)
    }
    if (e.key === 'Tab') {
      const f = [...box.querySelectorAll('button, input, [tabindex="0"]')].filter((x) => !x.disabled)
      if (!f.length) return
      if (e.shiftKey && document.activeElement === f[0]) (e.preventDefault(), f.at(-1).focus())
      else if (!e.shiftKey && document.activeElement === f.at(-1)) (e.preventDefault(), f[0].focus())
    }
  }
</script>

<svelte:window onkeydowncapture={key} />

<div class="scrim" role="presentation" onclick={() => done(dialog.kind === 'confirm' ? false : null)}></div>
<div class="dialog" class:tall={dialog.kind === 'album'} role="dialog" aria-modal="true" aria-labelledby="dlg-title" tabindex="-1" bind:this={box}>
<form onsubmit={submit}>
  <h2 id="dlg-title">{dialog.title}</h2>
  {#if dialog.body}<p>{dialog.body}</p>{/if}

  {#if dialog.kind === 'prompt'}
    <label class="field">
      <span class="sr-only">{dialog.title}</span>
      <input bind:value placeholder={dialog.placeholder || ''} maxlength="120" autocomplete="off" enterkeyhint="done" />
      {#if dialog.suffix}<span class="suffix">{dialog.suffix}</span>{/if}
    </label>
  {:else if dialog.kind === 'album'}
    {#if folders && folders.length > 8}
      <input class="filter" bind:value={filter} placeholder="Search albums" type="search" />
    {/if}
    <div class="albums">
      {#if folders === null}
        <div class="center"><div class="spinner"></div></div>
      {:else}
        {#if !filter}
          <button type="button" class="album" onclick={() => done('')}><Icon name="photos" size={20} /> <span>Library (no album)</span></button>
        {/if}
        {#each shown as f (f)}
          <button type="button" class="album" onclick={() => done(f)} style:padding-left="{1 + (f.split('/').length - 1) * 1.1}rem">
            <Icon name="folder" size={20} /> <span>{f.split('/').pop()}</span>
          </button>
        {/each}
      {/if}
    </div>
    {#if creating}
      <div class="new">
        <input bind:value={newName} placeholder="New album name" maxlength="120" onkeydown={(e) => e.key === 'Enter' && (e.preventDefault(), createAndPick())} />
        <button type="button" class="btn primary" onclick={createAndPick} disabled={!newName.trim()}>Create</button>
      </div>
      {#if alertMsg}<p class="err" role="alert">{alertMsg}</p>{/if}
    {/if}
  {/if}

  <div class="actions">
    {#if dialog.kind === 'album' && !creating}
      <button type="button" class="btn new-btn" onclick={() => (creating = true)}><Icon name="folder-plus" size={18} />New album</button>
    {/if}
    <button type="button" class="btn" onclick={() => done(dialog.kind === 'confirm' ? false : null)}>Cancel</button>
    {#if dialog.kind !== 'album'}
      <button class="btn primary" class:danger={dialog.danger} disabled={dialog.kind === 'prompt' && !value.trim()}>{dialog.confirm || 'OK'}</button>
    {/if}
  </div>
</form>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 90;
    background: var(--scrim);
    animation: fade 0.15s;
  }
  .dialog {
    position: fixed;
    z-index: 91;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    width: min(420px, calc(100vw - 32px));
    max-height: calc(100dvh - 48px);
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
    padding: 1.4rem;
    border-radius: 20px;
    background: var(--raised);
    color: var(--text);
    box-shadow: var(--shadow);
    animation: rise 0.18s ease-out;
  }
  form {
    display: contents;
  }
  .dialog.tall {
    height: min(560px, calc(100dvh - 48px));
  }
  h2 {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 600;
  }
  p {
    margin: 0;
    color: var(--muted);
  }
  .field {
    display: flex;
    align-items: center;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--bg);
    padding-right: 0.8rem;
  }
  .field:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  input {
    font: inherit;
    color: inherit;
    background: transparent;
    border: 0;
    outline: none;
    padding: 0.7rem 0.85rem;
    flex: 1;
    min-width: 0;
  }
  .filter,
  .new input {
    border: 1px solid var(--line);
    border-radius: 10px;
    background: var(--bg);
  }
  .suffix {
    color: var(--faint);
  }
  .albums {
    flex: 1;
    overflow-y: auto;
    margin: 0 -1.4rem;
    border-block: 1px solid var(--line);
  }
  .album {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
    padding: 0.65rem 1.4rem;
    border: 0;
    background: none;
    text-align: left;
    cursor: pointer;
  }
  .album span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .album :global(svg) {
    color: var(--muted);
    flex: none;
  }
  .album:hover,
  .album:focus-visible {
    background: var(--hover);
    outline: none;
  }
  .center {
    display: grid;
    place-items: center;
    padding: 2rem;
  }
  .new {
    display: flex;
    gap: 0.5rem;
  }
  .err {
    color: var(--danger);
    font-size: 0.9rem;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 0.5rem;
  }
  .new-btn {
    margin-right: auto;
  }
  @keyframes fade {
    from {
      opacity: 0;
    }
  }
  @keyframes rise {
    from {
      opacity: 0;
      transform: translate(-50%, -46%);
    }
  }
</style>
