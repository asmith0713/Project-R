<script>
  import Icon from './Icon.svelte'

  /** items: [{ icon, label, run, danger?, hidden? }] */
  let { items, open = $bindable(false), label = 'More', icon = 'more', dark = false } = $props()
  let root
  let list = $state()

  function toggle() {
    open = !open
    if (open) queueMicrotask(() => list?.querySelector('button')?.focus())
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
      const bs = [...list.querySelectorAll('button')]
      const i = bs.indexOf(document.activeElement)
      bs[(i + (e.key === 'ArrowDown' ? 1 : -1) + bs.length) % bs.length]?.focus()
    }
  }
</script>

<svelte:window onpointerdown={outside} onkeydowncapture={key} />

<div class="wrap" bind:this={root}>
  <button class="icon-btn" class:dark onclick={toggle} aria-label={label} aria-haspopup="menu" aria-expanded={open}>
    <Icon name={icon} />
  </button>
  {#if open}
    <div class="menu" role="menu" bind:this={list}>
      {#each items.filter((i) => !i.hidden) as it (it.label)}
        <button role="menuitem" class:danger={it.danger} onclick={() => pick(it)}>
          <Icon name={it.icon} size={20} />
          <span>{it.label}</span>
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
  @keyframes pop {
    from {
      opacity: 0;
      transform: scale(0.95);
    }
  }
</style>
