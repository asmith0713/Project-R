<script>
  import { thumbUrl, albumUrl } from '../lib/api.js'
  import { albumMenu } from '../lib/albumMenu.js'
  import { plural } from '../lib/format.js'
  import Icon from './Icon.svelte'
  import Menu from './Menu.svelte'

  /** album: { path, name, count, cover }. sub: optional caption replacing the count. */
  let { album, hiddenRoot = false, insideHidden = false, sub = '' } = $props()
  let open = $state(false)
  const items = $derived(albumMenu(album, { hiddenRoot, insideHidden }))
</script>

<div class="card" class:menu-open={open}>
  <a href={albumUrl(album.path)} class="link">
    <div class="cover">
      {#if album.cover}
        <img src={thumbUrl(album.cover)} alt="" loading="lazy" onload={(e) => e.currentTarget.classList.add('in')} />
      {:else}
        <Icon name="folder" size={40} />
      {/if}
      {#if hiddenRoot}<span class="lock"><Icon name="lock" size={16} /></span>{/if}
    </div>
    <strong>{album.name}</strong>
    <span>{sub || (album.count ? plural(album.count, 'item') : 'Empty')}</span>
  </a>
  <div class="more">
    <Menu {items} bind:open label="Options for {album.name}" />
  </div>
</div>

<style>
  .card {
    position: relative;
  }
  .link {
    display: grid;
    gap: 0.15rem;
    text-decoration: none;
  }
  .cover {
    position: relative;
    aspect-ratio: 1;
    display: grid;
    place-items: center;
    border-radius: var(--radius);
    overflow: hidden;
    background: var(--tile);
    color: var(--faint);
    margin-bottom: 0.45rem;
    transition: transform 0.15s;
  }
  .link:hover .cover {
    transform: scale(1.02);
  }
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition: opacity 0.25s;
  }
  img:global(.in) {
    opacity: 1;
  }
  .lock {
    position: absolute;
    left: 8px;
    bottom: 8px;
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: rgb(0 0 0 / 0.55);
    color: #fff;
  }
  strong {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    padding-right: 4px;
  }
  span {
    color: var(--muted);
    font-size: 0.85rem;
  }
  /* ⋮ sits on the cover's top-right corner: always on touch screens, on hover with a mouse */
  .more {
    position: absolute;
    top: 6px;
    right: 6px;
    z-index: 2;
  }
  .more :global(.icon-btn) {
    width: 34px;
    height: 34px;
    background: rgb(0 0 0 / 0.45);
    color: #fff;
  }
  .more :global(.icon-btn:hover) {
    background: rgb(0 0 0 / 0.65);
  }
  @media (hover: hover) {
    .more :global(.icon-btn) {
      opacity: 0;
      transition: opacity 0.12s;
    }
    .card:hover .more :global(.icon-btn),
    .card:focus-within .more :global(.icon-btn),
    .menu-open .more :global(.icon-btn) {
      opacity: 1;
    }
  }
  .menu-open {
    z-index: 3;
  }
</style>
