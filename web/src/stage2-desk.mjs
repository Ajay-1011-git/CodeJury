/**
 * Stage 2 inside the main dashboard: the same Repair desk / Run evidence / Training log
 * tabs, backed by the Stage 2 jury API that the main server serves under /s2.
 */

import { ApiClient, checkHealth, describeError } from './s2/api.mjs';
import { Store } from './s2/state.mjs';
import { mountInput, renderReports, renderDownload } from './s2/views.mjs';
import { downloadFor, resourceView, TERMINAL, ROLE_CARDS, lineage } from './s2/model.mjs';
import { formatOutcomeBadge } from './evidence.mjs';
import { renderConversation, candidateLabel, hardRecord, lineDiff } from './stage2-debate.mjs';
import { DEMO_CASES } from './stage2-demos.mjs';
import { mountQuickCase } from './quick-case.mjs';
import { TranscriptFeed } from './transcript-feed.mjs';
import { comparisonUrl } from './comparison.mjs';

const ACTIVE = ['queued', 'running'];

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}
const json = (v) => JSON.stringify(v, null, 1);


/** Short column label for a test: its supplied id, or where it came from. */
function testLabels(snap) {
  const counts = {};
  const labels = new Map();
  for (const t of snap.tests || []) {
    if (t.provenance === 'supplied') { labels.set(t.test_id, t.test_id.length > 14 ? `supplied ${t.test_id.slice(-4)}` : t.test_id); continue; }
    const key = { property_engine: 'generated', critic: 'critic', search: 'search', audit: 'audit' }[t.provenance] || t.provenance;
    counts[key] = (counts[key] || 0) + 1;
    labels.set(t.test_id, `${key} #${counts[key]}`);
  }
  return labels;
}

function expectedText(test) {
  const spec = test?.oracle_spec || {};
  if (spec.kind === 'literal') return JSON.stringify(spec.expected);
  if (spec.kind === 'property') return `Approved property: ${spec.property_id}`;
  if (spec.kind === 'observation') return `Observation only: ${spec.hypothesis || 'no expected value'}`;
  return spec.kind || 'not specified';
}

// ------------------------------------------------------------------ verdict

function renderVerdict(root, state, onDownloadSlot) {
  root.replaceChildren();
  const snap = state.snapshot;
  if (state.error) root.appendChild(Object.assign(el('div', 'callout callout-danger'), { textContent: describeError(state.error) }));
  if (!snap) {
    root.appendChild(el('p', 'placeholder-label', state.runId || state.submitting ? 'Opening the case…' : 'Awaiting a Stage 2 case. The verdict appears once the jury finishes.'));
    return;
  }
  if (ACTIVE.includes(snap.status)) {
    const box = el('div', 'callout callout-info');
    box.appendChild(el('strong', null, 'Debate in progress. '));
    box.appendChild(document.createTextNode(`Phase: ${snap.phase}. ${snap.candidates.filter((c) => c.origin !== 'original').length} proposals so far.`));
    root.appendChild(box);
    return;
  }
  const d = snap.decision;
  const winner = d?.selected_candidate_id ? snap.candidates.find((c) => c.candidate_id === d.selected_candidate_id) : null;
  const banner = el('div', `callout ${winner ? 'callout-success' : 'callout-danger'}`);
  banner.appendChild(el('h3', null, winner ? `Supported patch from ${candidateLabel(winner)}` : snap.status === 'unresolved' ? 'Unresolved: no patch was accepted' : snap.status.replace(/_/g, ' ')));
  banner.appendChild(el('p', null, d?.reason || snap.termination_reason || ''));
  root.appendChild(banner);

  const facts = el('div', 'result-detail-box');
  facts.appendChild(el('h4', null, 'How the jury got here'));
  const proposals = snap.candidates.filter((c) => c.origin !== 'original');
  const byRole = (prefix) => proposals.filter((c) => c.origin.startsWith(prefix)).length;
  const lines = [
    `Fixer A proposals: ${byRole('fixer_a')} · Fixer B proposals: ${byRole('fixer_b')} · AST search edits: ${byRole('ast_search')}`,
    `Judge decisions: ${snap.actions.length} (${snap.policy_mode} policy)`,
    `Critic challenges: ${snap.actions.filter((a) => a.kind === 'criticize').length} · Tests: ${snap.tests.length} (${snap.tests.filter((t) => t.oracle_status === 'authoritative').length} authoritative)`,
  ];
  if (d?.verification_scope?.length) lines.push(`Patch verified on ${d.verification_scope.length} authoritative test${d.verification_scope.length === 1 ? '' : 's'}`);
  if (d?.unresolved_requirements?.length) lines.push(`Unresolved requirements: ${d.unresolved_requirements.join(', ')}`);
  for (const line of lines) facts.appendChild(el('p', null, line));
  root.appendChild(facts);

  if (winner) {
    const code = el('div', 'selected-code-preview');
    code.appendChild(el('h4', null, 'Accepted source'));
    code.appendChild(el('pre', 'history-pre', winner.source));
    root.appendChild(code);
    const slot = el('div');
    root.appendChild(slot);
    onDownloadSlot(slot, snap);
  }

  const usage = el('div', 'result-usage-box');
  usage.appendChild(el('h4', null, 'Resources used'));
  for (const r of resourceView(snap.resource_usage)) {
    if (['input_tokens', 'output_tokens', 'function_executions', 'elapsed_ms', 'judge_decisions', 'learned_candidates', 'peak_memory_mb'].includes(r.key)) {
      usage.appendChild(el('p', null, `${r.label}: ${r.key === 'peak_memory_mb' && r.used ? Math.round(r.used) : r.shown}${r.cap ? ` / ${r.cap}` : ''}`));
    }
  }
  root.appendChild(usage);
  const compareUrl = comparisonUrl(snap.run_id);
  if (compareUrl && ['supported_patch', 'unresolved'].includes(snap.status)) {
    const compare = el('a', 'btn comparison-link', 'Compare with base Phi-4-mini ↗');
    compare.href = compareUrl; compare.target = '_blank'; compare.rel = 'noopener';
    root.appendChild(compare);
  }
}

// ------------------------------------------------------------------ proposals

function renderCandidates(root, snap) {
  root.replaceChildren();
  const proposals = (snap?.candidates || []).filter((c) => c.origin !== 'original');
  if (!proposals.length) { root.appendChild(el('p', 'placeholder-label', 'No proposals yet.')); return; }
  const original = snap.candidates.find((c) => c.origin === 'original');
  const selected = snap.decision?.selected_candidate_id;
  const list = el('div', 'candidates-list');
  for (const cand of proposals) {
    const card = el('div', `candidate-card s2-cand origin-${cand.origin}${cand.candidate_id === selected ? ' is-selected' : ''}`);
    const header = el('div', 'candidate-header');
    const title = el('div');
    title.appendChild(el('strong', null, candidateLabel(cand)));
    title.appendChild(el('span', 'cand-sha', ` ${cand.candidate_id.slice(0, 14)}…`));
    header.appendChild(title);
    const badge = el('span', `badge ${cand.eligibility === 'eligible' ? 'badge-success' : cand.eligibility === 'rejected' ? 'badge-danger' : 'badge-neutral'}`, cand.candidate_id === selected ? 'Selected' : cand.eligibility);
    header.appendChild(badge);
    card.appendChild(header);
    card.appendChild(el('p', 'candidate-diag', ROLE_CARDS[cand.origin]?.view || ''));
    if (cand.diagnosis) card.appendChild(el('p', 'candidate-diag', `Diagnosis: ${cand.diagnosis}`));
    const rec = hardRecord(snap, cand.candidate_id);
    card.appendChild(el('p', 'candidate-diag', `Authoritative checks: ${rec.pass} passed, ${rec.fail} failed${rec.observed ? ` · ${rec.observed} observed` : ''}`));
    if (cand.rejection_reason) card.appendChild(el('p', 'candidate-rejection', `Rejection reason: ${cand.rejection_reason}`));
    const steps = lineage(snap, cand).steps;
    if (steps.length) {
      const edits = el('ol', 'edits');
      for (const s of steps) edits.appendChild(el('li', null, `${s.operator_family} at line ${s.location.lineno}: ${s.before} → ${s.after}`));
      card.appendChild(edits);
    }
    card.appendChild(el('span', 'code-label', 'Change from the original:'));
    const diff = el('div', 'diff-view');
    const rows = lineDiff(original?.source, cand.source);
    if (!rows.some((r) => r.op !== ' ')) diff.textContent = '(identical to the original code)';
    for (const r of rows) diff.appendChild(el('span', r.op === '+' ? 'diff-add' : r.op === '-' ? 'diff-del' : '', `${r.op} ${r.line}\n`));
    card.appendChild(diff);
    const src = el('details', 'candidate-source');
    src.appendChild(el('summary', null, 'Inspect full source'));
    src.appendChild(el('pre', null, cand.source));
    card.appendChild(src);
    list.appendChild(card);
  }
  root.appendChild(list);
}

// ------------------------------------------------------------------ matrix

function renderMatrix(root, snap, selection, onSelect) {
  const old = root.querySelector('.table-responsive');
  const scroll = [old?.scrollLeft || 0, old?.scrollTop || 0];
  root.replaceChildren();
  if (!snap || !snap.tests?.length) { root.appendChild(el('p', 'placeholder-label', 'No test executions yet.')); return; }
  const labels = testLabels(snap);
  const execs = new Map();
  for (const ex of snap.executions) execs.set(`${ex.candidate_id}|${ex.test_id}`, ex);
  const wrap = el('div', 'table-responsive');
  wrap.tabIndex = 0;
  wrap.setAttribute('aria-label', 'Scrollable execution matrix');
  const table = el('table', 'matrix-table');
  const head = el('tr');
  head.appendChild(el('th', null, 'Candidate'));
  for (const t of snap.tests) {
    const th = el('th', 'matrix-col-header');
    th.appendChild(el('div', null, labels.get(t.test_id)));
    th.appendChild(el('span', `badge ${t.oracle_status === 'authoritative' ? 'badge-success' : 'badge-neutral'}`, t.oracle_status === 'authoritative' ? 'Authoritative' : 'Observation'));
    head.appendChild(th);
  }
  const thead = el('thead'); thead.appendChild(head); table.appendChild(thead);
  const tbody = el('tbody');
  for (const cand of snap.candidates) {
    const row = el('tr');
    const first = el('td');
    first.appendChild(el('strong', null, cand.origin === 'original' ? 'Original' : candidateLabel(cand)));
    first.appendChild(el('br'));
    first.appendChild(el('small', 'text-dim', cand.candidate_id.slice(0, 12)));
    row.appendChild(first);
    for (const t of snap.tests) {
      const td = el('td', 'matrix-cell');
      const ex = execs.get(`${cand.candidate_id}|${t.test_id}`);
      const btn = el('button', 'matrix-cell-btn');
      btn.type = 'button';
      btn.appendChild(formatOutcomeBadge(ex ? ex.outcome : 'pending'));
      btn.setAttribute('aria-label', `Execution of ${candidateLabel(cand)} on ${labels.get(t.test_id)}`);
      if (ex) btn.id = `execution-${ex.execution_id}`;
      if (ex) btn.addEventListener('click', () => onSelect({ ex, test: t, cand }));
      td.appendChild(btn);
      row.appendChild(td);
    }
    tbody.appendChild(row);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
  root.appendChild(wrap);
  [wrap.scrollLeft, wrap.scrollTop] = scroll;

  const box = el('div', 'counterexample-inspector');
  if (selection) {
    const { ex, test, cand } = selection;
    const header = el('div', 'drilldown-header');
    header.appendChild(el('h3', null, `${cand.origin === 'original' ? 'Original' : candidateLabel(cand)} on ${labels.get(test.test_id)}`));
    header.appendChild(formatOutcomeBadge(ex.outcome));
    box.appendChild(header);
    const add = (label, text) => {
      const d = el('div', 'drilldown-detail');
      d.appendChild(el('label', null, label));
      d.appendChild(el('pre', null, text));
      box.appendChild(d);
    };
    add('Input arguments', json(test.inputs));
    add('Oracle', `${expectedText(test)} (${test.oracle_status.replace(/_/g, ' ')})`);
    add('Actual output', ex.exception ? `${ex.exception.type}: ${ex.exception.message}` : json(ex.actual_output));
    if (ex.input_effects?.some((e) => e.mutated)) add('Input mutation', 'The candidate modified its input, which counts as a failure.');
    add('Test source', `${test.provenance.replace(/_/g, ' ')} · ${test.test_id}`);
  } else {
    box.appendChild(el('p', 'placeholder-label', 'Click any cell to see the input, the oracle and what the candidate returned.'));
  }
  root.appendChild(box);
}

// ------------------------------------------------------------------ mount

export function mountStage2(globalStore, tabs) {
  const base = `${location.origin}/s2`;
  const client = new ApiClient(base);
  const store = new Store();
  const $ = (id) => document.getElementById(id);
  const containers = {
    input: $('s2-input-container'), result: $('s2-result-container'), debate: $('s2-progress-container'),
    candidates: $('s2-candidates-container'), matrix: $('s2-execution-container'), training: $('s2-training-container'),
  };
  for (const node of Object.values(containers)) node?.classList.add('s2-scope');
  const setPill = (text, ready) => {
    const pill = $('backend-status-pill');
    pill.textContent = text;
    pill.className = `connection-status ${ready ? 'ready' : 'unavailable'}`;
  };
  window.addEventListener('pagehide', () => store.dispose());

  let transcript = null;
  let selection = null;
  let selectionRun = null;
  let seenRun = null;
  let input = null;
  let quickInput = null;
  let authorityLabel = null;
  let downloadToken = 0;


  const transcriptFeed = new TranscriptFeed({
    base,
    getRunId: () => store.state.runId,
    onUpdate: (body) => { transcript = body; paint(store.state); },
  });

  const toolbar = (state) => {
    const snap = state.snapshot;
    const status = snap?.status;
    const badge = $('run-status-badge');
    badge.textContent = status ? status.toUpperCase() : state.submitting ? 'SUBMITTING...' : 'IDLE';
    badge.className = `badge ${status === 'supported_patch' ? 'badge-success' : ['unresolved', 'cancelled'].includes(status) ? 'badge-warn' : ['invalid_input', 'infrastructure_error'].includes(status) ? 'badge-danger' : 'badge-neutral'}`;
    const cancel = $('btn-cancel-live');
    cancel.hidden = cancel.disabled = !ACTIVE.includes(status);
    $('workspace-activity').textContent = state.submitting ? 'Opening the case for the jury…'
      : ACTIVE.includes(status) ? 'The jury is debating…'
      : status === 'supported_patch' ? 'The jury accepted a patch'
      : status === 'unresolved' ? 'No patch accepted. Inspect the debate'
      : status === 'cancelled' ? 'Case cancelled'
      : status ? status.replace(/_/g, ' ') : 'Ready for a new case';
  };

  function paint(state) {
    const snap = state.snapshot;
    if (snap && snap.run_id !== selectionRun) { selection = null; selectionRun = snap.run_id; }
    if (snap && transcript?.run_id !== snap.run_id) transcript = null;
    toolbar(state);
    renderVerdict(containers.result, state, (slot, s) => {
      const mine = ++downloadToken;
      downloadFor(s).then((dl) => { if (mine === downloadToken) renderDownload(slot, dl); });
    });
    const label = transcript?.authority_label || authorityLabel;
    if (label && snap) containers.result.appendChild(el('p', 'callout callout-info', label));
    renderConversation(containers.debate, snap, state.events, transcript, (execId) => {
      const execution = snap?.executions?.find((ex) => ex.execution_id === execId);
      if (!execution) return;
      selection = { ex: execution, test: snap.tests.find((t) => t.test_id === execution.test_id), cand: snap.candidates.find((c) => c.candidate_id === execution.candidate_id) };
      renderMatrix(containers.matrix, snap, selection, (pick) => { selection = pick; paint(store.state); });
      const cell = document.getElementById(`execution-${execId}`);
      cell?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      cell?.focus({ preventScroll: true });
    });
    renderCandidates(containers.candidates, snap);
    const onSelect = (pick) => { selection = pick; renderMatrix(containers.matrix, snap, selection, onSelect); };
    renderMatrix(containers.matrix, snap, selection, onSelect);
  }

  store.subscribe((state) => {
    const snap = state.snapshot;
    if (state.runId && state.runId !== seenRun) { seenRun = state.runId; tabs?.activate('evidence', true); }
    input?.setBusy(state.submitting || (snap && ACTIVE.includes(snap.status)));
    quickInput?.setBusy(state.submitting || (snap && ACTIVE.includes(snap.status)));
    // Replies are stored as the debate runs; refresh them while it is live and once at the end.
    if (snap) {
      transcriptFeed.refresh(snap, TERMINAL.includes(snap.status));
    }
    paint(state);
  });

  $('btn-cancel-live').addEventListener('click', () => store.cancel(client));
  paint(store.state);

  (async () => {
    let health = null;
    try {
      health = await client.getHealth();
      const check = checkHealth(health);
      store.set({ health, healthOk: check.ok, healthReasons: check.reasons, runtimeMode: health.runtime_mode });
      setPill(check.ok && health.full_stage2_ready ? 'Jury ready' : 'Setup required', check.ok && health.full_stage2_ready);
      $('fixture-banner').hidden = health.runtime_mode !== 'fixture';
      for (const node of document.querySelectorAll('[data-s2-role]')) {
        node.textContent = health.trained_roles.includes(node.dataset.s2Role) ? 'Trained adapter' : 'Not trained';
      }
    } catch (err) {
      for (const node of document.querySelectorAll('[data-s2-role]')) node.textContent = 'Unavailable';
      setPill(err.status === 503 ? 'Jury unavailable (503)' : 'Offline / unreachable', false);
      containers.input.replaceChildren();
      const box = el('div', 'callout callout-danger');
      box.appendChild(el('strong', null, 'The jury is not running in this server. '));
      box.appendChild(document.createTextNode(err.status === 503 ? describeError(err) : 'Restart the app with ./start.sh.'));
      containers.input.appendChild(box);
      return;
    }
    let examples = [];
    try { examples = (await client.getExamples()).examples; } catch (err) { store.set({ error: err }); }
    const quick = el('section', 'quick-case');
    quick.appendChild(el('h2', null, 'Quick case'));
    const advanced = el('details', 'advanced-case');
    advanced.appendChild(el('summary', null, 'Advanced case: supply domains and tests yourself'));
    const advancedBody = el('div'); advanced.appendChild(advancedBody);
    containers.input.replaceChildren(quick, advanced);
    quickInput = mountQuickCase(quick, {
      canSubmit: () => store.state.healthOk,
      onAccepted: async (result) => {
        authorityLabel = result.authority_label;
        // Join the existing Store lifecycle after /s2x has admitted exactly one run.
        const alreadyAccepted = {
          createRun: async () => result.accepted,
          getRun: (...args) => client.getRun(...args),
          getEvents: (...args) => client.getEvents(...args),
          getReport: (...args) => client.getReport(...args),
          cancelRun: (...args) => client.cancelRun(...args),
        };
        await store.submit(alreadyAccepted, { schema_version: 'stage2.v1' });
      },
    });
    window.addEventListener('pagehide', () => quickInput.dispose());
    input = mountInput(advancedBody, {
      examples: [...DEMO_CASES, ...examples],
      canSubmit: () => store.state.healthOk,
      onSubmit: async (payload) => {
        authorityLabel = null;
        try { await store.submit(client, payload); } catch { /* shown in the verdict card */ }
      },
    });
    if (!health.full_stage2_ready) {
      containers.input.prepend(Object.assign(el('div', 'callout callout-danger'), { textContent: 'Not every Stage 2 role or tool is ready; the learned policy will be refused. Use the fixed policy or finish setup.' }));
    }
    const reports = {};
    try { reports.training = await client.getTrainingReport(); } catch { /* optional */ }
    try { reports.benchmark = await client.getBenchmarkReport(); } catch { /* optional */ }
    renderReports(containers.training, reports);
  })();

  return { store };
}
