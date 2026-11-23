<script>
  import Icon from './Icon.svelte'

  /** items: [{ icon, label, run, danger?, hidden?, disabled?, hint? }] */
  let { items, open = $bindable(false), label = 'More', icon = 'more', dark = false, onopen } = $props()
  let root
  let list = $state()
  let flipX = $state(false)
  let flipY = $state(false)

  function toggle(e) {
    e?.preventDefault()
    e?.stopPropagation()
    open = !open
    if (open) onopen?.()
    if (open)
      queueMicrotask(() => {
        if (!list) return
        // keep the menu on screen: flip right/left and up/down as needed
        const r = list.getBoundingClientRect()
        flipX = r.left < 8
        flipY = r.bottom > innerHeight - 8 && r.top - r.height > 60
        list.querySelector('button:not(:disabled)')?.focus()
      })
  }
  function pick(it) {
    open = false
    it.run()
  }
  function outside(e) {
    if (open && !root.contains(e.target)) open = false
  }
  function key(e) {
    if (!open) return
    if (e.key === 'Escape') {
      e.stopPropagation()
      open = false
      root.querySelector('.icon-btn').focus()
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const bs = [...list.querySelectorAll('button:not(:disabled)')]
      const i = bs.indexOf(document.activeElement)
      bs[(i + (e.key === 'ArrowDown' ? 1 : -1) + bs.length) % bs.length]?.focus()
    }
  }
</script>

<svelte:window onpointerdown={outside} onkeydowncapture={key} />

<div class="wrap" bind:this={root} class:open>
  <button class="icon-btn" class:dark onclick={toggle} aria-label={label} aria-haspopup="menu" aria-expanded={open}>
    <Icon name={icon} />
  </button>
  {#if open}
    <div class="menu" class:flipX class:flipY role="menu" bind:this={list}>
      {#each items.filter((i) => !i.hidden) as it (it.label)}
        <button role="menuitem" class:danger={it.danger} disabled={it.disabled} onclick={() => pick(it)}>
          <Icon name={it.icon} size={20} />
          <span>{it.label}</span>
          {#if it.hint}<small>{it.hint}</small>{/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .wrap {
    position: relative;
  }
  .dark:hover {
    background: rgb(255 255 255 / 0.12);
  }
  .menu {
    position: absolute;
    right: 0;
    top: calc(100% + 4px);
    z-index: 30;
    min-width: 220px;
    max-width: min(320px, 90vw);
    padding: 6px 0;
    border-radius: 10px;
    background: var(--raised);
    color: var(--text);
    box-shadow: var(--shadow);
    border: 1px solid var(--line);
    animation: pop 0.12s ease-out;
    transform-origin: top right;
  }
  .menu button {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    width: 100%;
    padding: 0.6rem 1rem;
    border: 0;
    background: none;
    text-align: left;
    cursor: pointer;
    color: var(--text);
  }
  .menu button:disabled {
    cursor: default;
    opacity: 0.5;
  }
  .menu button:disabled:hover {
    background: none;
  }
  .menu small {
    margin-left: auto;
    padding-left: 0.75rem;
    color: var(--faint);
    font-size: 0.75rem;
    white-space: nowrap;
  }
  .menu button span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .menu button :global(svg) {
    color: var(--muted);
    flex: none;
  }
  .menu button:hover,
  .menu button:focus-visible {
    background: var(--hover);
    outline: none;
  }
  .menu .danger,
  .menu .danger :global(svg) {
    color: var(--danger);
  }
  .menu.flipX {
    right: auto;
    left: 0;
    transform-origin: top left;
  }
  .menu.flipY {
    top: auto;
    bottom: calc(100% + 4px);
  }
  @keyframes pop {
    from {
      opacity: 0;
      transform: scale(0.95);
    }
  }
</style>
