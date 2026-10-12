import { ApiClient, checkHealth, describeError, resolveApiBase } from './api.mjs';
import { downloadFor } from './model.mjs';
import { Store } from './state.mjs';
import { el, mountInput, renderDownload, renderReports, renderRun } from './views.mjs';

const $ = (id) => document.getElementById(id);

async function main() {
  const base = resolveApiBase(location.search, location);
  const client = new ApiClient(base);
  const store = new Store();
  $('api-url').textContent = base;
  window.addEventListener('pagehide', () => store.dispose());

  let input = null;
  const banner = $('fixture-banner');
  const pill = $('backend-pill');
  const errorBox = $('error-box');
  let downloadToken = 0;

  store.subscribe((state) => {
    banner.hidden = state.runtimeMode !== 'fixture' && state.health?.runtime_mode !== 'fixture';
    errorBox.textContent = state.error ? describeError(state.error) : '';
    errorBox.hidden = !state.error;
    $('cancel').hidden = !(state.snapshot && ['queued', 'running'].includes(state.snapshot.status));
    input?.setBusy(state.submitting || (state.snapshot && ['queued', 'running'].includes(state.snapshot.status)));
    const handlers = {
      mountDownload(root, snap) {
        const slot = el('div', { class: 'download' });
        root.append(slot);
        const mine = ++downloadToken;
        downloadFor(snap).then((dl) => { if (mine === downloadToken && !state.withdrawn) renderDownload(slot, dl); });
      },
    };
    renderRun($('run-root'), state, handlers);
  });

  $('cancel').addEventListener('click', () => store.cancel(client));

  try {
    const health = await client.getHealth();
    const check = checkHealth(health);
    store.set({ health, healthOk: check.ok, healthReasons: check.reasons, runtimeMode: health.runtime_mode });
    pill.textContent = check.ok ? `${health.service} · ${health.runtime_mode}` : `Contract mismatch: ${check.reasons.join('; ')}`;
    pill.className = `pill ${check.ok ? 'ok' : 'bad'}`;
    $('roles').textContent = `Trained roles: ${health.trained_roles.join(', ') || 'none'} · full Stage 2 ready: ${health.full_stage2_ready ? 'yes' : 'no'}`;
  } catch (err) {
    pill.textContent = err.status === 503 ? 'Backend unavailable (503)' : 'Backend unreachable';
    pill.className = 'pill bad';
    store.set({ error: err });
  }

  let examples = [];
  try { examples = (await client.getExamples()).examples; } catch (err) { store.set({ error: err }); }
  input = mountInput($('input-root'), {
    examples,
    canSubmit: () => store.state.healthOk,
    onSubmit: async (payload) => {
      if (!store.state.healthOk) return;
      try { await store.submit(client, payload); } catch { /* surfaced through store.error */ }
    },
  });

  const loadReports = async () => {
    const out = {};
    try { out.training = await client.getTrainingReport(); } catch (err) { store.set({ error: err }); }
    try { out.benchmark = await client.getBenchmarkReport(); } catch (err) { store.set({ error: err }); }
    renderReports($('report-root'), out);
  };
  loadReports();
  for (const tab of document.querySelectorAll('[data-tab]')) {
    tab.addEventListener('click', () => {
      for (const t of document.querySelectorAll('[data-tab]')) t.setAttribute('aria-selected', String(t === tab));
      for (const p of document.querySelectorAll('[data-panel]')) p.hidden = p.dataset.panel !== tab.dataset.tab;
    });
  }
}
main();
