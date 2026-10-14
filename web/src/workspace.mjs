import { mountTabs } from './tabs.mjs';

export function mountWorkspace(store, client) {
  const root = document.querySelector('[data-tabs="workspace"]');
  const tabs = mountTabs(root, key => {
    for (const link of document.querySelectorAll('[data-workspace-link]')) {
      link.classList.toggle('active', link.dataset.workspaceLink === key);
      if (link.dataset.workspaceLink === key) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
  });
  const navigate = key => {
    tabs.activate(key);
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document.getElementById('workbench').scrollIntoView({ behavior: reduce ? 'instant' : 'smooth', block: 'start' });
  };
  for (const link of document.querySelectorAll('[data-workspace-link]')) {
    link.addEventListener('click', event => {
      event.preventDefault();
      history.replaceState(null, '', '#' + link.dataset.workspaceLink);
      navigate(link.dataset.workspaceLink);
    });
  }
  window.addEventListener('hashchange', () => {
    const key = location.hash.slice(1);
    if (['repair', 'evidence', 'training'].includes(key)) navigate(key);
  });
  if (['repair', 'evidence', 'training'].includes(location.hash.slice(1))) tabs.activate(location.hash.slice(1));
  let seenRunId = null;
  const activity = document.getElementById('workspace-activity');
  const cancel = document.getElementById('btn-cancel-live');
  cancel.addEventListener('click', () => { if (store.get().stage !== 2) store.cancelRun(client); });
  store.subscribe(state => {
    if (state.stage === 2) return;
    if (state.currentRunId && state.currentRunId !== seenRunId) {
      seenRunId = state.currentRunId;
      tabs.activate('evidence', true);
    }
    const status = state.runSnapshot?.status;
    const active = ['queued', 'running'].includes(status);
    cancel.hidden = !active;
    cancel.disabled = !active;
    activity.textContent = state.isSubmitting ? 'Opening your case…'
      : ['queued', 'running'].includes(status) ? 'Checking the evidence…'
      : status === 'supported_patch' ? 'A patch supported by the checks'
      : status === 'unresolved' ? 'No supported patch — inspect the evidence'
      : status === 'cancelled' ? 'Case cancelled'
      : status === 'infrastructure_error' ? 'Execution interrupted — inspect the report'
      : 'Ready for a new case';
  });
  const tablist = document.querySelector('.workspace-tabs');
  const mobile = window.matchMedia('(max-width: 760px)');
  const orientation = () => tablist.setAttribute('aria-orientation', mobile.matches ? 'horizontal' : 'vertical');
  orientation();
  mobile.addEventListener('change', orientation);
  return { tabs, navigate };
}
