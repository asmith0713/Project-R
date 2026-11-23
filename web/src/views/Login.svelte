<script>
  import { app, login } from '../lib/state.svelte.js'
  import Icon from '../components/Icon.svelte'

  let key = $state('')
  let show = $state(false)
  let busy = $state(false)
  let error = $state('')

  async function submit(e) {
    e.preventDefault()
    if (!key || busy) return
    busy = true
    error = ''
    try {
      await login(key)
    } catch (err) {
      error = err.message
      key = ''
    } finally {
      busy = false
    }
  }
</script>

<main class="login">
  <form onsubmit={submit} class="card">
    <img src="/icon.svg" alt="" width="56" height="56" />
    <h1>Private Gallery</h1>
    {#if !app.configured}
      <p class="note">No secret key is set yet. On the Pi, run <code>python3 app.py setpass</code> and restart the gallery.</p>
    {:else}
      <p class="sub">Enter your secret key to continue</p>
      <div class="field" class:bad={error}>
        <label for="key" class="sr-only">Secret key</label>
        <input id="key" type={show ? 'text' : 'password'} bind:value={key} autocomplete="current-password" autocapitalize="off" spellcheck="false" placeholder="Secret key" required />
        <button type="button" class="eye" onclick={() => (show = !show)} aria-label={show ? 'Hide key' : 'Show key'} aria-pressed={show}>
          {show ? 'Hide' : 'Show'}
        </button>
      </div>
      {#if error}<p class="err" role="alert">{error}</p>{/if}
      <button class="btn primary go" disabled={busy || !key}>
        {#if busy}<span class="spinner small"></span>{:else}<Icon name="lock" size={18} />{/if}
        Unlock
      </button>
    {/if}
  </form>
  <p class="foot">Private · Locks when you close the tab</p>
</main>

<style>
  .login {
    min-height: 100dvh;
    display: grid;
    place-content: center;
    gap: 1.25rem;
    padding: calc(var(--safe-t) + 24px) 16px calc(var(--safe-b) + 24px);
    background:
      radial-gradient(1200px 600px at 50% -10%, var(--accent-soft), transparent 70%),
      var(--bg);
  }
  .card {
    width: min(380px, calc(100vw - 32px));
    display: grid;
    justify-items: center;
    gap: 0.9rem;
    padding: 2.2rem 1.6rem 1.8rem;
    border-radius: 24px;
    background: var(--raised);
    border: 1px solid var(--line);
    box-shadow: var(--shadow);
    text-align: center;
  }
  h1 {
    margin: 0.25rem 0 0;
    font-size: 1.5rem;
    font-weight: 600;
    letter-spacing: -0.01em;
  }
  .sub,
  .note {
    margin: -0.3rem 0 0.4rem;
    color: var(--muted);
  }
  .field {
    display: flex;
    width: 100%;
    border: 1px solid var(--line);
    border-radius: 12px;
    background: var(--bg);
  }
  .field:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  .field.bad {
    border-color: var(--danger);
  }
  input {
    flex: 1;
    min-width: 0;
    font: inherit;
    font-size: 16px; /* stops iOS zooming in */
    color: inherit;
    border: 0;
    background: none;
    outline: none;
    padding: 0.8rem 0.9rem;
  }
  .eye {
    border: 0;
    background: none;
    color: var(--accent);
    font-weight: 500;
    padding: 0 0.9rem;
    cursor: pointer;
  }
  .err {
    margin: -0.2rem 0 0;
    color: var(--danger);
    font-size: 0.9rem;
  }
  .go {
    width: 100%;
    justify-content: center;
    height: 46px;
    margin-top: 0.3rem;
    font-size: 1rem;
  }
  .small {
    width: 18px;
    height: 18px;
    border-width: 2px;
  }
  .foot {
    margin: 0;
    text-align: center;
    color: var(--faint);
    font-size: 0.82rem;
  }
  code {
    font-size: 0.9em;
    background: var(--bg-2);
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
  }
</style>
