<script>
  import { app, dismiss } from '../lib/state.svelte.js'
</script>

<div class="toasts" aria-live="polite">
  {#each app.toasts as t (t.id)}
    <div class="toast" class:error={t.error} role={t.error ? 'alert' : 'status'}>
      <span>{t.message}</span>
      {#if t.action}
        <button onclick={() => (dismiss(t.id), t.onAction())}>{t.action}</button>
      {/if}
    </div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed;
    z-index: 95;
    left: 50%;
    transform: translateX(-50%);
    bottom: calc(var(--safe-b) + 20px + var(--nav-offset, 0px));
    display: grid;
    gap: 0.5rem;
    width: max-content;
    max-width: calc(100vw - 32px);
    pointer-events: none;
  }
  .toast {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem 1rem 0.75rem 1.1rem;
    border-radius: 10px;
    background: #2b2d33;
    color: #f3f3f5;
    box-shadow: var(--shadow);
    pointer-events: auto;
    animation: in 0.2s ease-out;
  }
  .toast.error {
    background: #5c1d1b;
  }
  button {
    border: 0;
    background: none;
    color: #a9c1ff;
    font-weight: 600;
    cursor: pointer;
    padding: 0.2rem 0.3rem;
  }
  @keyframes in {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
  }
</style>
