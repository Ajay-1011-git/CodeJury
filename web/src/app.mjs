/**
 * Main Application Bootstrap
 * The dashboard runs the Stage 2 jury (served under /s2). Strictly loads JavaScript modules
 * without global eval or script injection.
 */

import { globalStore } from './state.mjs';
import { mountWorkspace } from './workspace.mjs';
import { mountStage2 } from './stage2-desk.mjs';

function initApp() {
  const apiUrlEl = document.getElementById('active-api-url');
  if (apiUrlEl) apiUrlEl.textContent = `${location.origin}/s2`;

  // The workspace tabs are shared; Stage 2 owns the toolbar, so the Stage 1 store stays idle.
  globalStore.set({ stage: 2 });
  const workspace = mountWorkspace(globalStore, null);
  mountStage2(globalStore, workspace.tabs);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
