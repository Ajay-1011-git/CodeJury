/**
 * Main Application Bootstrap
 * Strictly loads JavaScript modules without global eval or script injection.
 */

import { ApiClient, resolveApiBase } from './api.mjs';
import { globalStore } from './state.mjs';
import { mountInputView } from './input.mjs';
import { mountEvidenceView } from './evidence.mjs';
import { mountResultView } from './result.mjs';
import { mountTrainingView } from './training.mjs';

function initApp() {
  const apiBase = resolveApiBase();
  const client = new ApiClient(apiBase);

  // Update header connection info
  const apiUrlEl = document.getElementById('active-api-url');
  if (apiUrlEl) apiUrlEl.textContent = apiBase;

  const statusPill = document.getElementById('backend-status-pill');
  const fixtureBanner = document.getElementById('fixture-banner');
  const roleFixerA = document.getElementById('role-fixer-a');

  // Mount views
  mountInputView(document.getElementById('input-container'), globalStore, client);
  mountEvidenceView(
    document.getElementById('candidates-container'),
    document.getElementById('execution-container'),
    globalStore,
    client
  );
  mountResultView(document.getElementById('result-container'), globalStore, client);
  mountTrainingView(document.getElementById('training-container'), globalStore, client);

  // Health check
  client.getHealth()
    .then((health) => {
      globalStore.set({ health, runtimeMode: health.runtime_mode });
      if (statusPill) {
        statusPill.textContent = 'Connected (200 OK)';
        statusPill.className = 'badge badge-success';
      }
      if (fixtureBanner) {
        if (health.runtime_mode === 'fixture') {
          fixtureBanner.style.display = 'block';
          fixtureBanner.textContent = '⚠️ Fixture demonstration — no live inference';
        } else {
          fixtureBanner.style.display = 'none';
        }
      }
      if (roleFixerA) {
        roleFixerA.textContent = health.fixer_a_trained ? 'A: trained (adapter)' : 'A: raw (unloaded)';
      }
    })
    .catch((err) => {
      if (statusPill) {
        statusPill.textContent = 'Offline / Unreachable';
        statusPill.className = 'badge badge-danger';
      }
      console.warn('Backend connection notice:', err.message);
    });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
