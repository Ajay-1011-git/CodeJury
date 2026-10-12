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
import { mountWorkspace } from './workspace.mjs';

function initApp() {
  const apiBase = resolveApiBase();
  const client = new ApiClient(apiBase);

  // Connection and header indicators
  const apiUrlEl = document.getElementById('active-api-url');
  if (apiUrlEl) apiUrlEl.textContent = apiBase;

  const statusPill = document.getElementById('backend-status-pill');
  const fixtureBanner = document.getElementById('fixture-banner');
  const roleFixerA = document.getElementById('role-fixer-a');
  const runStatusBadge = document.getElementById('run-status-badge');

  // Cancel poll timer on window navigation or unload
  window.addEventListener('beforeunload', () => {
    globalStore.stopPolling();
  });

  // Reactive state subscription
  globalStore.subscribe((state) => {
    // Fixture banner guard: persistent when fixture mode
    if (fixtureBanner) {
      if (state.runtimeMode === 'fixture') {
        fixtureBanner.hidden = false;
        fixtureBanner.textContent = '⚠️ Fixture demonstration — no live inference';
      } else {
        fixtureBanner.hidden = true;
      }
    }

    // Role Fixer A status
    if (roleFixerA && state.health) {
      roleFixerA.textContent = state.health.fixer_a_trained ? 'Trained adapter' : 'Adapter unavailable';
    }

    // Run status badge
    if (runStatusBadge) {
      if (state.runSnapshot) {
        const s = state.runSnapshot.status;
        runStatusBadge.textContent = s.toUpperCase();
        if (s === 'supported_patch') {
          runStatusBadge.className = 'badge badge-success';
        } else if (s === 'unresolved' || s === 'cancelled') {
          runStatusBadge.className = 'badge badge-warn';
        } else if (s === 'invalid_input' || s === 'infrastructure_error') {
          runStatusBadge.className = 'badge badge-danger';
        } else {
          runStatusBadge.className = 'badge badge-neutral';
        }
      } else {
        runStatusBadge.textContent = state.isSubmitting ? 'SUBMITTING...' : 'IDLE';
        runStatusBadge.className = 'badge badge-neutral';
      }
    }
  });

  mountWorkspace(globalStore, client);

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

  // Initial Health check
  client.getHealth()
    .then((health) => {
      globalStore.set({ health, runtimeMode: health.runtime_mode });
      if (statusPill) {
        const ready = health.model_ready && health.sandbox_ready;
        statusPill.textContent = health.runtime_mode === 'fixture' ? 'Fixture backend' : ready ? 'Local backend ready' : 'Setup required';
        statusPill.className = `connection-status ${ready ? 'ready' : 'unavailable'}`;
      }
    })
    .catch((err) => {
      if (statusPill) {
        statusPill.textContent = err.status === 503 ? 'Service Unavailable (503)' : 'Offline / Unreachable';
        statusPill.className = 'connection-status unavailable';
      }
      globalStore.set({
        errorNotice: {
          status: err.status || 0,
          code: err.code || 'CONNECT_ERROR',
          message: err.message
        }
      });
    });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
