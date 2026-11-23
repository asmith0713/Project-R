<script>
  import { app, tryUnlock, toast } from '../lib/state.svelte.js'
  import { route, navigate } from '../lib/router.svelte.js'
  import Icon from './Icon.svelte'

  let open = $state(false) // phones: field expanded over the top bar
  let input = $state()
  let busy = false

  function typed() {
    if (app.search.trim()) {
      if (route.path !== '/search') navigate('/search')
    } else if (route.path === '/search') history.back()
  }

  async function submit(e) {
    e.preventDefault()
    const q = app.search.trim()
    if (!q || busy) return
    busy = true
    const ok = await tryUnlock(q)
    busy = false
    input?.blur()
    if (ok) {
      app.search = ''
      open = false
      navigate('/hidden', { replace: route.path === '/search' })
      toast('Hidden albums unlocked')
    }
  }

  function clear() {
    app.search = ''
    typed()
    input?.focus()
  }

  function close() {
    open = false
    if (app.search) clear()
  }

  $effect(() => {
    if (open) queueMicrotask(() => input?.focus())
  })
</script>

<button class="icon-btn opener" onclick={() => (open = true)} aria-label="Search"><Icon name="search" /></button>

<form class="search" class:open role="search" onsubmit={submit}>
  <button type="button" class="icon-btn back" onclick={close} aria-label="Close search"><Icon name="back" /></button>
  <Icon name="search" size={20} />
  <input
    bind:this={input}
    bind:value={app.search}
    oninput={typed}
    onkeydown={(e) => e.key === 'Escape' && (e.stopPropagation(), close(), input.blur())}
    type="text"
    inputmode="search"
    enterkeyhint="search"
    placeholder="Search photos and albums"
    aria-label="Search photos and albums"
    autocomplete="off"
    autocorrect="off"
    autocapitalize="off"
    spellcheck="false"
  />
  {#if app.search}
    <button type="button" class="icon-btn clear" onclick={clear} aria-label="Clear search"><Icon name="close" size={20} /></button>
  {/if}
</form>

<style>
  .search {
    flex: 1;
    max-width: 620px;
    display: flex;
    align-items: center;
    gap: 0.6rem;
    height: 46px;
    padding: 0 0.4rem 0 1rem;
    border-radius: 999px;
    background: var(--bg-2);
    color: var(--muted);
    transition: background 0.15s, box-shadow 0.15s;
  }
  .search:focus-within {
    background: var(--raised);
    box-shadow: var(--shadow);
  }
  input {
    flex: 1;
    min-width: 0;
    height: 100%;
    border: 0;
    outline: none;
    background: none;
    color: var(--text);
    font: inherit;
    font-size: 16px; /* stops iOS zooming in */
  }
  .opener,
  .back {
    display: none;
  }
  .clear {
    width: 34px;
    height: 34px;
  }
  @media (max-width: 680px) {
    .opener {
      display: inline-grid;
    }
    .search {
      display: none;
    }
    .search.open {
      display: flex;
      position: absolute;
      inset: var(--safe-t) calc(var(--safe-r) + 8px) 0 calc(var(--safe-l) + 8px);
      height: auto;
      margin: 9px 0;
      padding-left: 0.2rem;
      z-index: 2;
      background: var(--raised);
      box-shadow: var(--shadow);
    }
    .search.open .back {
      display: inline-grid;
    }
    .search.open > :global(svg) {
      display: none;
    }
  }
</style>
