/**
 * Stage 2 debate history: proposals from Fixer A and Fixer B, each Judge decision with the
 * menu it chose from, the Critic's challenges and what they found, audits and the verdict.
 * Built from the event log, the run snapshot and the stored model replies. textContent only.
 */

export const ROLE_LABEL = {
  original: 'Original',
  fixer_a: 'Fixer A',
  fixer_b: 'Fixer B',
  fixer_a_revision: 'Fixer A',
  fixer_b_revision: 'Fixer B',
  ast_search: 'AST search',
};

const ACTOR_LABEL = {
  controller: 'Controller',
  fixer_a: 'Fixer A',
  fixer_b: 'Fixer B',
  tools: 'Tools',
  judge: 'Judge',
  critic: 'Critic',
  verdict: 'Verdict',
};

const JUDGE_VERB = {
  revise: 'orders a revision',
  generate: 'asks for a fresh proposal',
  criticize: 'calls the Critic',
  search: 'orders an AST search',
  audit: 'orders a mutation audit',
  select: 'selects a patch',
  abstain: 'abstains',
};

const FAILING = new Set(['fail', 'error', 'timeout']);

function parse(text) {
  try {
    const value = JSON.parse(text);
    return value && typeof value === 'object' ? value : null;
  } catch {
    return null;
  }
}

/** Short, stable label for a candidate: "Fixer B revision (c-3cab…)". */
export function candidateLabel(cand) {
  if (!cand) return 'unknown candidate';
  const role = ROLE_LABEL[cand.origin] || cand.origin;
  const kind = cand.origin.endsWith('_revision') ? ' revision' : '';
  return `${role}${kind}`;
}

function latestByTest(snap, candidateId) {
  const latest = new Map();
  for (const ex of snap?.executions || []) if (ex.candidate_id === candidateId) latest.set(ex.test_id, ex);
  return latest;
}

export function hardRecord(snap, candidateId) {
  const tests = new Map((snap?.tests || []).map((t) => [t.test_id, t]));
  let pass = 0; let fail = 0; let observed = 0;
  const failures = [];
  for (const ex of latestByTest(snap, candidateId).values()) {
    const test = tests.get(ex.test_id);
    if (test?.oracle_status !== 'authoritative') { observed += 1; continue; }
    if (ex.outcome === 'pass') pass += 1;
    else if (FAILING.has(ex.outcome)) { fail += 1; failures.push({ ex, test }); }
  }
  return { pass, fail, observed, failures };
}

/** Line diff (LCS) so a proposal can be read against the original. */
export function lineDiff(before, after) {
  const a = (before || '').replace(/\n$/, '').split('\n');
  const b = (after || '').replace(/\n$/, '').split('\n');
  const n = a.length; const m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i -= 1) for (let j = m - 1; j >= 0; j -= 1) {
    dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  }
  const out = [];
  let i = 0; let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { out.push({ op: ' ', line: a[i] }); i += 1; j += 1; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { out.push({ op: '-', line: a[i] }); i += 1; }
    else { out.push({ op: '+', line: b[j] }); j += 1; }
  }
  while (i < n) out.push({ op: '-', line: a[i++] });
  while (j < m) out.push({ op: '+', line: b[j++] });
  return out;
}

function queue(calls, roles) {
  return { items: calls.filter((c) => roles.includes(c.role)), next: 0 };
}

/** Take the first unconsumed call that satisfies match; earlier skipped calls are returned too. */
function take(q, match) {
  for (let k = q.next; k < q.items.length; k += 1) {
    if (match(q.items[k])) {
      const skipped = q.items.slice(q.next, k);
      q.next = k + 1;
      return { call: q.items[k], skipped };
    }
  }
  return { call: null, skipped: [] };
}

/** Pure: turn a Stage 2 run into ordered debate rounds. */
export function buildDebate(snap, events, transcript) {
  const rounds = [];
  if (!snap) return rounds;
  const cands = new Map((snap.candidates || []).map((c) => [c.candidate_id, c]));
  const actions = new Map((snap.actions || []).map((a) => [a.action_id, a]));
  const calls = transcript?.calls || [];
  const fixerA = queue(calls, ['fixer_a']);
  const fixerB = queue(calls, ['fixer_b']);
  const judge = queue(calls, ['judge']);
  const critic = queue(calls, ['critic']);
  const learned = snap.policy_mode === 'learned';
  let baselineShown = false;
  let open = null;

  const closeOpen = () => { open = null; };
  for (const ev of events || []) {
    const p = ev.payload || {};
    if (ev.type === 'run_started') {
      rounds.push({ key: 'open', actor: 'controller', kind: 'open' });
    } else if (ev.type === 'candidate_created' && p.candidate_id) {
      const cand = cands.get(p.candidate_id);
      if (!cand) continue;
      closeOpen();
      if (cand.origin === 'original') continue;
      const role = cand.origin.startsWith('fixer_a') ? 'fixer_a' : cand.origin.startsWith('fixer_b') ? 'fixer_b' : 'tools';
      let reply = null; let invalid = [];
      if (role !== 'tools') {
        const q = role === 'fixer_a' ? fixerA : fixerB;
        const found = take(q, (c) => (parse(c.text)?.source || '').trim() === cand.source.trim());
        reply = found.call; invalid = found.skipped;
      }
      rounds.push({ key: `cand-${cand.candidate_id}`, actor: role, kind: 'proposal', candidateId: cand.candidate_id, reply, invalid });
    } else if (ev.type === 'execution_completed' && !baselineShown) {
      const cand = cands.get(p.candidate_id);
      if (cand?.origin === 'original') {
        baselineShown = true;
        rounds.push({ key: 'baseline', actor: 'controller', kind: 'baseline', candidateId: cand.candidate_id });
      }
    } else if (ev.type === 'action_selected' || ev.type === 'action_refused') {
      closeOpen();
      const action = actions.get(p.action_id) || null;
      let found = { call: null, skipped: [] };
      if (learned && ev.type === 'action_selected') {
        found = take(judge, (c) => {
          const draft = parse(c.text);
          const option = (c.options || []).find((o) => o.option_id === draft?.action_option_id);
          return option ? option.summary === p.message : draft?.rationale === p.message;
        });
      } else if (learned) {
        found = take(judge, () => true);
      }
      const round = {
        key: `act-${p.action_id || ev.event_id}`,
        actor: learned && !/fixed fallback/i.test(p.message) ? 'judge' : 'controller',
        kind: ev.type === 'action_refused' ? 'refused' : 'decision',
        message: p.message, action, call: found.call, refusedCalls: found.skipped,
      };
      rounds.push(round);
      if (action?.kind === 'criticize') {
        open = { key: `critic-${action.action_id}`, actor: 'critic', kind: 'challenge', action, call: take(critic, () => true).call, tests: [] };
        rounds.push(open);
      } else if (action?.kind === 'audit') {
        open = { key: `audit-${action.action_id}`, actor: 'tools', kind: 'audit', action, gaps: [], tests: [] };
        rounds.push(open);
      }
    } else if (ev.type === 'test_admitted' && open && p.test_id) {
      open.tests.push(p.test_id);
    } else if (ev.type === 'audit_gap_found' && open?.kind === 'audit') {
      open.gaps.push(p.gap_id);
    } else if (ev.type === 'candidate_invalidated' || ev.type === 'budget_exhausted' || ev.type === 'test_rejected') {
      rounds.push({ key: `ev-${ev.event_id}`, actor: 'controller', kind: 'notice', type: ev.type, message: p.message, candidateId: p.candidate_id });
    } else if (ev.type === 'run_finished') {
      closeOpen();
      rounds.push({ key: 'verdict', actor: 'verdict', kind: 'verdict', message: p.message });
    }
  }
  return rounds;
}

// ------------------------------------------------------------------ rendering

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}
function field(label, value) {
  const row = el('div', 'history-field');
  row.appendChild(el('span', 'history-label', label));
  if (value instanceof Node) row.appendChild(value); else row.appendChild(el('span', 'history-value', value));
  return row;
}
function pre(text) { return el('pre', 'history-pre', text); }
function raw(summary, text) {
  const box = el('details', 'history-raw');
  box.appendChild(el('summary', null, summary));
  box.appendChild(pre(text));
  return box;
}
const json = (v) => JSON.stringify(v);

function diffView(before, after) {
  const box = el('div', 'diff-view');
  const rows = lineDiff(before, after);
  if (!rows.some((r) => r.op !== ' ')) return el('p', 'history-note history-warn', 'No change: identical to the original code.');
  for (const r of rows) box.appendChild(el('span', r.op === '+' ? 'diff-add' : r.op === '-' ? 'diff-del' : '', `${r.op} ${r.line}\n`));
  return box;
}

function expectedOf(test) {
  const spec = test?.oracle_spec || {};
  if (spec.kind === 'literal') return json(spec.expected);
  if (spec.kind === 'property') return `follows ${spec.property_id || 'the approved property'}`;
  if (spec.kind === 'metamorphic') return 'metamorphic relation';
  return spec.hypothesis || spec.kind || 'not specified';
}

function failureList(snap, candidateId, limit = 4) {
  const { failures } = hardRecord(snap, candidateId);
  const wrap = el('div', 'history-cases');
  for (const { ex, test } of failures.slice(0, limit)) {
    const item = el('div', 'history-case');
    item.appendChild(field('Input', json(test?.inputs)));
    item.appendChild(field('Expected', expectedOf(test)));
    item.appendChild(field('Got', ex.exception ? `${ex.exception.type}: ${ex.exception.message}` : json(ex.actual_output)));
    wrap.appendChild(item);
  }
  if (failures.length > limit) wrap.appendChild(el('p', 'history-note', `+ ${failures.length - limit} more failing checks in the execution matrix.`));
  return wrap;
}

function verdictText(cand, rec) {
  if (cand.eligibility === 'eligible') return `survives · ${rec.pass} passed`;
  if (cand.eligibility === 'rejected') return rec.fail ? `rejected · ${rec.fail} failed` : 'rejected';
  return 'not yet checked';
}

function summarize(round, snap) {
  const cand = round.candidateId ? (snap.candidates || []).find((c) => c.candidate_id === round.candidateId) : null;
  switch (round.kind) {
    case 'open': return ['Case opened', `${snap.problem?.supplied_test_ids?.length ?? 0} supplied tests · ${snap.problem?.requirements?.length ?? 0} requirements`];
    case 'baseline': {
      const rec = hardRecord(snap, round.candidateId);
      return ['Bug reproduced', rec.fail ? `Original fails ${rec.fail} supplied test${rec.fail === 1 ? '' : 's'}` : 'Original checked'];
    }
    case 'proposal': {
      const rec = hardRecord(snap, cand.candidate_id);
      const verb = cand.origin === 'ast_search' ? 'AST search proposes an edit'
        : cand.origin.endsWith('_revision') ? `${ROLE_LABEL[cand.origin]} revises`
        : cand.origin === 'fixer_b' ? 'Fixer B proposes (independent view)' : 'Fixer A proposes';
      return [verb, `${verdictText(cand, rec)}${cand.diagnosis ? ` · ${cand.diagnosis}` : ''}`];
    }
    case 'decision': {
      const kind = round.action?.kind;
      const who = round.actor === 'judge' ? 'Judge' : 'Controller';
      return [`${who} ${JUDGE_VERB[kind] || 'acts'}`, round.message || ''];
    }
    case 'refused': return ['Judge draft refused', round.message || ''];
    case 'challenge': {
      const draft = parse(round.call?.text || '');
      const mode = draft?.mode || round.action?.parameters?.mode || 'challenge';
      const tests = (snap.tests || []).filter((t) => round.tests.includes(t.test_id));
      const auth = tests.filter((t) => t.oracle_status === 'authoritative').length;
      const broke = brokenBy(snap, round.tests);
      const found = broke.length ? `broke ${broke.map(candidateLabel).join(', ')}` : 'no candidate broken';
      const explored = draft?.oracle_spec?.kind === 'property' && !tests.length
        ? `explored ${draft.oracle_spec.property_id} on generated inputs · no counterexample`
        : `${tests.length} tests (${auth} authoritative) · ${found}`;
      return [`Critic challenge · ${mode.replace(/_/g, ' ')}`, explored];
    }
    case 'audit': {
      const mutants = (snap.probe_mutants || []).length;
      return ['Mutation audit', `${mutants} probe mutant${mutants === 1 ? '' : 's'} · ${round.gaps.length} test gap${round.gaps.length === 1 ? '' : 's'}`];
    }
    case 'notice': return [round.type.replace(/_/g, ' '), round.message || ''];
    case 'verdict': {
      const id = snap.decision?.selected_candidate_id;
      const winner = id ? (snap.candidates || []).find((c) => c.candidate_id === id) : null;
      return [winner ? `Supported patch · ${candidateLabel(winner)}` : 'Unresolved', round.message || snap.termination_reason || ''];
    }
    default: return [round.kind, ''];
  }
}

/** Candidates that failed an authoritative check among the given tests. */
function brokenBy(snap, testIds) {
  const ids = new Set(testIds);
  const tests = new Map((snap.tests || []).map((t) => [t.test_id, t]));
  const out = new Map();
  for (const ex of snap.executions || []) {
    if (ids.has(ex.test_id) && FAILING.has(ex.outcome) && tests.get(ex.test_id)?.oracle_status === 'authoritative') {
      const cand = (snap.candidates || []).find((c) => c.candidate_id === ex.candidate_id);
      if (cand && cand.origin !== 'original') out.set(cand.candidate_id, cand);
    }
  }
  return [...out.values()];
}

function details(round, snap) {
  const body = el('div', 'history-detail');
  const cands = new Map((snap.candidates || []).map((c) => [c.candidate_id, c]));
  const original = (snap.candidates || []).find((c) => c.origin === 'original');
  const cand = round.candidateId ? cands.get(round.candidateId) : null;
  const label = (id) => (cands.get(id) ? candidateLabel(cands.get(id)) : id);

  if (round.kind === 'open') {
    body.appendChild(field('Contract', snap.problem?.contract_text || ''));
    for (const r of snap.problem?.requirements || []) {
      body.appendChild(field(r.requirement_id, `${r.description}${r.property_template_id ? ` (executable: ${r.property_template_id})` : ' (prose only)'}`));
    }
    const supplied = (snap.tests || []).filter((t) => t.provenance === 'supplied');
    for (const t of supplied) body.appendChild(field('Test', `${json(t.inputs)} → ${expectedOf(t)}`));
  } else if (round.kind === 'baseline') {
    body.appendChild(el('p', 'history-note', 'The submitted code is run first, so every later claim is measured against a real failure.'));
    body.appendChild(failureList(snap, round.candidateId));
  } else if (round.kind === 'proposal') {
    const view = {
      fixer_a: 'Fixer A sees the buggy code, requirements, tests and the failure trace.',
      fixer_b: 'Fixer B works independently: it sees the signature, contract and tests, never the buggy body or Fixer A’s code.',
      fixer_a_revision: 'Revision written from real counterexamples against its earlier patch.',
      fixer_b_revision: 'Revision written from real counterexamples against its earlier patch.',
      ast_search: 'A deterministic small edit to an earlier candidate, not an independent opinion.',
    }[cand.origin];
    if (view) body.appendChild(el('p', 'history-note', view));
    if (cand.diagnosis) body.appendChild(field('Diagnosis', cand.diagnosis));
    body.appendChild(diffView(original?.source, cand.source));
    const rec = hardRecord(snap, cand.candidate_id);
    body.appendChild(field('Checks', `${rec.pass} passed, ${rec.fail} failed${rec.observed ? `, ${rec.observed} observed` : ''}`));
    if (cand.rejection_reason) body.appendChild(field('Rejected', cand.rejection_reason));
    if (rec.fail) body.appendChild(failureList(snap, cand.candidate_id));
    for (const bad of round.invalid || []) body.appendChild(raw(`${ACTOR_LABEL[round.actor]} unusable reply`, bad.text || '(empty)'));
    if (round.reply) body.appendChild(raw(`${ACTOR_LABEL[round.actor]} raw reply`, round.reply.text || ''));
  } else if (round.kind === 'decision' || round.kind === 'refused') {
    if (round.actor === 'controller') body.appendChild(el('p', 'history-note', snap.policy_mode === 'fixed' ? 'Fixed policy: the Controller takes the first permitted action.' : 'The Judge draft was unusable, so the fixed fallback action was taken.'));
    const draft = parse(round.call?.text || '');
    if (round.action) {
      body.appendChild(field('Action', round.action.kind));
      if (round.action.target_ids?.length) body.appendChild(field('Targets', round.action.target_ids.map(label).join(', ')));
    }
    if (draft?.rationale) body.appendChild(field('Judge reason', draft.rationale));
    if (round.call?.options?.length) {
      const menu = el('div', 'debate-menu');
      menu.appendChild(el('span', 'history-label', 'Options the Judge saw'));
      for (const o of round.call.options) {
        const chosen = o.option_id === draft?.action_option_id;
        const row = el('div', `debate-option${chosen ? ' is-chosen' : ''}`);
        row.appendChild(el('span', 'debate-option-mark', chosen ? '✓' : ''));
        row.appendChild(el('span', 'debate-option-kind', o.kind));
        row.appendChild(el('span', 'debate-option-text', `${o.summary || ''}${o.target_ids?.length ? ` → ${o.target_ids.map(label).join(', ')}` : ''}`));
        menu.appendChild(row);
      }
      body.appendChild(menu);
    }
    if (round.call?.scoreboard?.length) {
      const table = el('div', 'debate-score');
      table.appendChild(el('span', 'history-label', 'Scoreboard at this moment'));
      for (const s of round.call.scoreboard) {
        if (s.origin === 'original') continue;
        table.appendChild(field(candidateLabel(s), `${s.eligibility} · ${s.hard_passes} pass / ${s.hard_failures} fail`));
      }
      body.appendChild(table);
    }
    for (const bad of round.refusedCalls || []) body.appendChild(raw('Refused Judge draft', bad.text || '(empty)'));
    if (round.call) body.appendChild(raw('Judge raw reply', round.call.text || ''));
  } else if (round.kind === 'challenge') {
    const draft = parse(round.call?.text || '');
    if (draft) {
      body.appendChild(field('Mode', draft.mode.replace(/_/g, ' ')));
      if (draft.rationale) body.appendChild(field('Critic reason', draft.rationale));
      if (draft.target_candidate_ids?.length) body.appendChild(field('Targets', draft.target_candidate_ids.map(label).join(', ')));
      if (draft.concrete_inputs) body.appendChild(field('Proposed inputs', json(draft.concrete_inputs)));
      if (draft.generator_spec) body.appendChild(field('Generator', `${draft.generator_spec.family} inputs for argument ${draft.generator_spec.argument_index}`));
      body.appendChild(field('Oracle', draft.oracle_spec?.kind === 'observation' ? 'observation only (cannot reject a patch)' : draft.oracle_spec?.kind === 'property' ? `approved property ${draft.oracle_spec.property_id} (can reject a patch)` : draft.oracle_spec?.kind || 'unknown'));
    } else if (round.call) {
      body.appendChild(el('p', 'history-note history-warn', 'The Critic reply could not be parsed.'));
    } else {
      body.appendChild(el('p', 'history-note', 'Critic reply appears here when the run finishes.'));
    }
    const tests = (snap.tests || []).filter((t) => round.tests.includes(t.test_id));
    if (tests.length) {
      body.appendChild(field('Tests added', `${tests.length} (${tests.filter((t) => t.oracle_status === 'authoritative').length} authoritative)`));
      const sample = el('div', 'history-cases');
      for (const t of tests.slice(0, 4)) {
        const item = el('div', 'history-case');
        item.appendChild(field('Input', json(t.inputs)));
        item.appendChild(field('Oracle', t.oracle_status === 'authoritative' ? expectedOf(t) : 'observed only'));
        sample.appendChild(item);
      }
      body.appendChild(sample);
    }
    if (draft?.oracle_spec?.kind === 'property' && !tests.length) {
      body.appendChild(el('p', 'history-note', `The test engine generated inputs from this plan and checked every surviving patch against ${draft.oracle_spec.property_id}. Only a counterexample is kept as a new test, and none was found.`));
    }
    const broke = brokenBy(snap, round.tests);
    body.appendChild(broke.length
      ? field('Result', `Counterexample found: ${broke.map(candidateLabel).join(', ')} failed`)
      : el('p', 'history-note', 'No candidate failed these tests.'));
    if (round.call) body.appendChild(raw('Critic raw reply', round.call.text || ''));
  } else if (round.kind === 'audit') {
    body.appendChild(el('p', 'history-note', 'Small mutations of each surviving patch are run against the current tests. A surviving mutant marks a gap in the tests, never a vote against the patch.'));
    for (const m of (snap.probe_mutants || []).slice(0, 6)) {
      body.appendChild(field(m.outcome || 'probe', `${m.edit?.operator_family || ''}: ${m.edit?.before ?? ''} → ${m.edit?.after ?? ''}`));
    }
    if (round.gaps.length) body.appendChild(field('Gaps', round.gaps.join(', ')));
  } else if (round.kind === 'notice') {
    body.appendChild(el('p', 'history-note', round.message || ''));
  } else if (round.kind === 'verdict') {
    const d = snap.decision;
    body.appendChild(field('Reason', d?.reason || snap.termination_reason || ''));
    const winner = d?.selected_candidate_id ? cands.get(d.selected_candidate_id) : null;
    if (winner) {
      body.appendChild(field('Winner', candidateLabel(winner)));
      body.appendChild(pre(winner.source));
    }
    for (const c of snap.candidates || []) {
      if (c.origin === 'original') continue;
      body.appendChild(field(candidateLabel(c), c.eligibility === 'eligible' ? 'eligible' : `${c.eligibility}${c.rejection_reason ? `: ${c.rejection_reason}` : ''}`));
    }
  }
  return body;
}

const openRounds = new Set();

export function renderDebate(container, snap, events, transcript) {
  container.replaceChildren();
  container.appendChild(el('div', 'timeline-notice', 'Who proposed what, how the Judge steered, what the Critic tried, and what the executed checks decided. Click a step for the evidence.'));
  if (!snap) {
    container.appendChild(el('p', 'placeholder-label', 'No debate yet. Submit a Stage 2 case.'));
    return;
  }
  const list = el('ol', 'history');
  for (const round of buildDebate(snap, events, transcript)) {
    const id = `${snap.run_id}:${round.key}`;
    const item = el('li', `history-step actor-${round.actor} kind-${round.kind}`);
    const cand = round.candidateId ? (snap.candidates || []).find((c) => c.candidate_id === round.candidateId) : null;
    if (round.kind === 'proposal' && cand) item.classList.add(cand.eligibility === 'eligible' ? 'is-good' : cand.eligibility === 'rejected' ? 'is-bad' : 'is-pending');
    if (round.kind === 'verdict') item.classList.add(snap.decision?.selected_candidate_id ? 'is-good' : 'is-bad');
    if (round.kind === 'refused') item.classList.add('is-bad');
    const [title, summary] = summarize(round, snap);
    const head = el('button', 'history-head');
    head.type = 'button';
    head.setAttribute('aria-expanded', String(openRounds.has(id)));
    head.appendChild(el('span', 'history-actor', ACTOR_LABEL[round.actor]));
    const text = el('span', 'history-text');
    text.appendChild(el('strong', 'history-title', title));
    text.appendChild(el('span', 'history-summary', summary));
    head.appendChild(text);
    head.appendChild(el('span', 'history-chevron', '›'));
    const panel = details(round, snap);
    panel.hidden = !openRounds.has(id);
    head.addEventListener('click', () => {
      const show = panel.hidden;
      panel.hidden = !show;
      head.setAttribute('aria-expanded', String(show));
      if (show) openRounds.add(id); else openRounds.delete(id);
    });
    item.append(head, panel);
    list.appendChild(item);
  }
  container.appendChild(list);
}
