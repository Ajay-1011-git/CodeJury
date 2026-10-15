/** One recorded case beside an independent local raw-model attempt. */
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}
const json = (value) => JSON.stringify(value, null, 2);
const RUN_ID = /^run-[0-9a-f]{32}$/;

export function comparisonUrl(runId) {
  if (!RUN_ID.test(runId)) return null;
  return `/comparison.html?run=${encodeURIComponent(runId)}`;
}

export class ComparisonClient {
  constructor(runId, fetchFn = globalThis.fetch.bind(globalThis)) {
    if (!RUN_ID.test(runId || '')) throw new Error('Open this page from a finished CodeJury result.');
    this.runId = runId; this.fetch = fetchFn;
  }
  async request(method = 'GET') {
    const response = await this.fetch(`/s2x/runs/${encodeURIComponent(this.runId)}/baseline`, { method, cache: 'no-store' });
    let body;
    try { body = await response.json(); } catch { throw new Error('The comparison service returned an unreadable response.'); }
    if (!response.ok) throw new Error(body?.error?.message || 'The comparison is unavailable.');
    if (body.comparison_version !== 1 || body.run_id !== this.runId) throw new Error('This comparison does not match the requested case.');
    return body;
  }
}

export function checkSummary(checks) {
  if (!checks) return 'No shared-example result';
  if (checks.status === 'unsupported_source') return 'Output uses unsupported Python';
  if (checks.status === 'incomplete') return `Check incomplete · ${checks.passed}/${checks.total} examples passed`;
  return `${checks.passed}/${checks.total} shared examples passed`;
}

export function comparisonState(body) {
  return {
    canStart: body.status === 'not_started',
    running: body.status === 'running',
    juryTitle: body.jury.status === 'supported_patch' ? 'Jury accepted a patch' : 'Jury left the case unresolved',
    rawTitle: !body.baseline ? 'Ready for one attempt' : body.status === 'running' ? 'Phi-4-mini is working…'
      : body.baseline.checks?.status === 'passed_examples' ? 'Passed the shared examples'
      : body.baseline.checks?.status === 'failed_examples' ? 'Failed the shared examples'
      : body.baseline.source ? 'Inspect the proposed patch' : 'No usable patch returned',
  };
}

export function executionText(execution) {
  if (!execution) return '—';
  const effects = execution.input_effects || [];
  const changed = effects.some((e) => e.mutated || e.before_hash !== e.after_hash);
  return `${execution.outcome}${changed ? ' · input changed' : ''} · ${execution.exception ? execution.exception.type : JSON.stringify(execution.actual_output)}`;
}

function sourceBlock(title, source) {
  const section = el('div');
  section.appendChild(el('h3', null, title));
  section.appendChild(el('pre', 'comparison-source', source || 'No accepted patch.'));
  return section;
}

function usageLine(usage) {
  if (!usage) return 'Usage is recorded when the attempt finishes.';
  return `${usage.output_tokens} output tokens · ${usage.input_tokens} input tokens · ${(usage.elapsed_ms / 1000).toFixed(1)} s`;
}

export function renderComparison(root, body, { start, pending = false, message = '' } = {}) {
  root.replaceChildren();
  const state = comparisonState(body);
  const intro = el('section', 'card comparison-intro');
  intro.appendChild(el('p', 'comparison-run', `Case ${body.run_id.slice(-8)} · ${body.function_name}`));
  intro.appendChild(el('p', null, body.scope));
  intro.appendChild(el('p', 'text-dim', 'The sandbox requires inputs to remain unchanged. An output can match the expected value and still fail if it changes the input.'));
  if (body.authority_label) intro.appendChild(el('p', 'callout callout-info', body.authority_label));
  const status = el('p', 'callout callout-info', message || body.message || 'Run one local base-model attempt to see its proposed repair.');
  status.setAttribute('role', 'status'); intro.appendChild(status);
  if (state.canStart) {
    const button = el('button', 'btn btn-primary', pending ? 'Starting Phi-4-mini…' : 'Run Phi-4-mini without fine-tuning');
    button.disabled = pending; button.type = 'button'; button.addEventListener('click', start);
    intro.appendChild(button);
  }
  root.appendChild(intro);
  const grid = el('div', 'comparison-grid');
  const jury = el('section', 'card comparison-output');
  jury.appendChild(el('span', 'eyebrow', 'CODEJURY'));
  jury.appendChild(el('h2', null, state.juryTitle));
  jury.appendChild(el('p', null, body.jury.reason));
  jury.appendChild(el('p', 'comparison-checks', checkSummary(body.jury.checks)));
  jury.appendChild(el('p', 'text-dim', `Full jury run: ${usageLine(body.jury.usage)}`));
  jury.appendChild(sourceBlock('Selected patch', body.jury.source));
  const raw = el('section', 'card comparison-output comparison-raw');
  raw.appendChild(el('span', 'eyebrow', 'PHI-4-MINI / NO CODEJURY ADAPTER'));
  raw.appendChild(el('h2', null, state.rawTitle));
  raw.appendChild(el('p', 'comparison-checks', checkSummary(body.baseline?.checks)));
  raw.appendChild(el('p', 'text-dim', `Single model reply: ${usageLine(body.baseline?.usage)}`));
  raw.appendChild(sourceBlock('Proposed patch', body.baseline?.source || (state.running ? 'Waiting for the actual model reply…' : 'No base-model patch yet.')));
  if (body.baseline?.format_status) raw.appendChild(el('p', 'text-dim', body.baseline.format_status));
  if (body.baseline?.reply) {
    const details = el('details'); details.appendChild(el('summary', null, 'Actual model reply'));
    details.appendChild(el('pre', 'comparison-source', body.baseline.reply)); raw.appendChild(details);
  }
  grid.append(jury, raw); root.appendChild(grid);
  const tests = el('section', 'card comparison-tests');
  tests.appendChild(el('h2', null, 'The same approved examples'));
  tests.appendChild(el('p', 'text-dim', 'These are the original supplied examples. Jury-generated challenges and proposed patches are not shown to the base model.'));
  const wrap = el('div', 'comparison-table-wrap'); const table = el('table');
  const head = el('tr'); for (const label of ['Input', 'Expected', 'CodeJury', 'Phi-4-mini']) head.appendChild(el('th', null, label));
  const thead = el('thead'); thead.appendChild(head); table.appendChild(thead);
  const tbody = el('tbody');
  for (const test of body.tests) {
    const row = el('tr'); row.appendChild(el('td', null, JSON.stringify(test.inputs)));
    row.appendChild(el('td', null, test.oracle_spec.kind === 'literal' ? JSON.stringify(test.oracle_spec.expected) : 'Approved property'));
    for (const item of [body.jury, body.baseline]) {
      const execution = item?.checks?.executions?.find((r) => r.test_id === test.test_id);
      const shown = executionText(execution);
      row.appendChild(el('td', null, shown));
    }
    tbody.appendChild(row);
  }
  table.appendChild(tbody); wrap.appendChild(table); tests.appendChild(wrap); root.appendChild(tests);
  const details = el('details', 'card comparison-input'); details.appendChild(el('summary', null, 'Original bug and specification'));
  details.appendChild(sourceBlock('Original code', body.original_source));
  details.appendChild(el('pre', 'comparison-source', json(body.specification))); root.appendChild(details);
}

export async function mountComparison(root, runId) {
  let client, body, disposed = false, timer = null, pending = false;
  const dispose = () => { disposed = true; if (timer) clearTimeout(timer); };
  const paint = (message = '') => { if (!disposed) renderComparison(root, body, { start, pending, message }); };
  const schedule = () => { if (!disposed && body.status === 'running') timer = setTimeout(load, 1000); };
  async function load() {
    try { body = await client.request(); if (disposed) return; paint(); schedule(); }
    catch (error) {
      if (disposed) return;
      if (body) { paint(error.message); schedule(); }
      else root.replaceChildren(el('p', 'callout callout-danger', error.message));
    }
  }
  async function start() {
    if (pending || body.status !== 'not_started') return;
    pending = true; paint();
    try { body = await client.request('POST'); if (!disposed) { pending = false; paint(); schedule(); } }
    catch (error) { pending = false; if (!disposed) paint(error.message); }
  }
  try { client = new ComparisonClient(runId); await load(); }
  catch (error) { root.replaceChildren(el('p', 'callout callout-danger', error.message)); }
  return { dispose };
}

if (typeof document !== 'undefined') {
  const root = document.getElementById('comparison-root');
  if (root) mountComparison(root, new URLSearchParams(location.search).get('run')).then((view) => window.addEventListener('pagehide', view.dispose));
}
