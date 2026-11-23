// The ⋮ menu for an album, shared by album cards, the album page and the Hidden page.
import { renameAlbum, moveAlbum, deleteAlbum, hideAlbum, unhideAlbum } from './state.svelte.js'

/**
 * album: { path, count }
 * hiddenRoot: this album is itself hidden (show "Unhide")
 * insideHidden: it sits inside a hidden album (hidden with its parent; can't toggle alone)
 * on: optional callbacks after success: renamed(newPath), moved(newPath), deleted(), hidden()
 */
export function albumMenu(album, { hiddenRoot = false, insideHidden = false, on = {}, extra = [] } = {}) {
  return [
    ...extra,
    { icon: 'edit', label: 'Rename', run: async () => { const p = await renameAlbum(album.path); if (p) on.renamed?.(p) } },
    { icon: 'move', label: 'Move into album…', run: async () => { const p = await moveAlbum(album.path); if (p) on.moved?.(p) } },
    hiddenRoot
      ? { icon: 'lock-open', label: 'Unhide album', run: async () => (await unhideAlbum(album.path)) && on.unhidden?.() }
      : { icon: 'eye-off', label: 'Hide album', hidden: insideHidden, run: async () => (await hideAlbum(album.path)) && on.hidden?.() },
    { icon: 'share', label: 'Share', disabled: true, hint: 'Coming soon', run: () => {} },
    { icon: 'trash', label: 'Delete album', danger: true, run: async () => (await deleteAlbum(album.path, album.count)) && on.deleted?.() },
  ]
}
