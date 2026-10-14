/**
 * Action history as clickable rounds: who proposed what, how it was challenged, and what the
 * executed checks decided. Built from the event log, the run snapshot and (once a run finishes)
 * the stored model outputs. Everything is rendered with textContent.
 */

const ACTORS = {
  controller: 'Controller',
  fixer: 'Fixer A',
  critic: 'Critic',
  engine: 'Test engine',
  verdict: 'Verdict'
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function pre(text) {
  const block = el('pre', 'history-pre');
  block.textContent = text;
  return block;
}

function field(label, value) {
  const row = el('div', 'history-field');
  row.appendChild(el('span', 'history-label', label));
  if (value instanceof Node) row.appendChild(value);
  else row.appendChild(el('span', 'history-value', value));
  return row;
}

function json(value) {
  return JSON.stringify(value);
}

function diffBlock(diffText) {
  if (!diffText) return el('p', 'history-note history-warn', 'No change: this patch is identical to the original code.');
  const box = el('div', 'diff-view');
  for (const line of (diffText || '').split('\n').slice(3)) {
    const span = el('span', line.startsWith('+') ? 'diff-add' : line.startsWith('-') ? 'diff-del' : '');
    span.textContent = line + '\n';
    box.appendChild(span);
  }
  return box;
}

// Checks are replayed; count each test once using its latest execution for this candidate.
function latestByTest(snap, candidateId) {
  const latest = new Map();
  for (const ex of snap?.executions || []) {
    if (ex.candidate_id === candidateId) latest.set(ex.test_id, ex);
  }
  return [...latest.values()];
}

function outcomeCounts(snap, candidateId) {
  const counts = { pass: 0, fail: 0, observed: 0, other: 0 };
  for (const ex of latestByTest(snap, candidateId)) {
    // A crash or timeout on an authoritative check rejects a patch just like a wrong answer.
    const outcome = ex.outcome === 'error' || ex.outcome === 'timeout' ? 'fail' : ex.outcome;
    if (outcome in counts) counts[outcome] += 1;
    else counts.other += 1;
  }
  return counts;
}

function failingRows(snap, candidateId, limit = 4) {
  const tests = new Map((snap?.tests || []).map((t) => [t.test_id, t]));
  const rows = [];
  for (const ex of latestByTest(snap, candidateId)) {
    if (!['fail', 'error', 'timeout'].includes(ex.outcome)) continue;
    rows.push({ ex, test: tests.get(ex.test_id) });
  }
  return { rows: rows.slice(0, limit), total: rows.length };
}

function failureTable(snap, candidateId) {
  const { rows, total } = failingRows(snap, candidateId);
  const wrap = el('div', 'history-cases');
  for (const { ex, test } of rows) {
    const item = el('div', 'history-case');
    item.appendChild(field('Input', json(test?.args)));
    const expected = test?.oracle_kind === 'property'
      ? `follows ${test.property_id}`
      : json(test?.expected);
    item.appendChild(field('Expected', expected));
    item.appendChild(field('Got', ex.exception_type ? `${ex.exception_type} raised` : json(ex.actual_output)));
    wrap.appendChild(item);
  }
  if (total > rows.length) wrap.appendChild(el('p', 'history-note', `+ ${total - rows.length} more failing checks in the execution matrix.`));
  return wrap;
}

function parsedFixer(text) {
  try {
    const body = JSON.parse(text);
    return body && typeof body === 'object' ? body : null;
  } catch {
    return null;
  }
}

/** Turn the run's facts into an ordered list of rounds. */
export function buildRounds(events, snap, transcript) {
  const rounds = [];
  const candidates = new Map((snap?.candidates || []).map((c) => [c.candidate_id, c]));
  const generations = transcript?.available ? transcript.generations || [] : null;
  const actions = transcript?.available ? transcript.actions || [] : null;
  const fixerOutputs = generations ? generations.filter((g) => g.role === 'fixer_a') : [];
  const criticOutputs = generations ? generations.filter((g) => g.role === 'critic') : [];
  const proposal = actions?.find((a) => a.action === 'challenge_proposal') || null;
  const explorations = actions ? actions.filter((a) => a.action === 'property_exploration') : [];
  const patchOrder = [];
  let opened = false;
  let fixerCursor = 0;
  const challenged = new Set();

  const addChallenge = (candidateId) => {
    if (!candidateId || challenged.has(candidateId)) return;
    challenged.add(candidateId);
    const index = patchOrder.indexOf(candidateId);
    const report = explorations[index] || null;
    const first = index === 0;
    rounds.push({ key: `challenge-${candidateId}`, actor: first ? 'critic' : 'engine', candidateId, kind: 'challenge', first, report });
  };

  for (const ev of events || []) {
    const p = ev.payload || {};
    if (ev.type === 'run_started' && !opened) {
      opened = true;
      rounds.push({ key: 'open', actor: 'controller', kind: 'open', ev });
    } else if (ev.type === 'original_checked') {
      rounds.push({ key: 'baseline', actor: 'controller', kind: 'baseline', ev });
    } else if (ev.type === 'candidate_created' && p.candidate_id && p.candidate_id !== 'original') {
      const cand = candidates.get(p.candidate_id);
      patchOrder.push(p.candidate_id);
      // Format retries produce a second Fixer output for the same candidate; take the last valid one.
      let output = null;
      while (fixerCursor < fixerOutputs.length) {
        const g = fixerOutputs[fixerCursor++];
        if (parsedFixer(g.text)?.source) { output = g; break; }
      }
      rounds.push({ key: `patch-${p.candidate_id}`, actor: 'fixer', kind: 'patch', candidateId: p.candidate_id, cand, output, revision: cand?.origin === 'fixer_a_revision' });
    } else if ((ev.type === 'test_rejected' || ev.type === 'test_admitted') && patchOrder.length) {
      addChallenge(patchOrder[patchOrder.length - 1]);
    } else if (ev.type === 'revision_requested') {
      const prev = p.candidate_id;
      addChallenge(prev);
      rounds.push({ key: `result-${prev}`, actor: 'engine', kind: 'result', candidateId: prev });
      rounds.push({ key: `revise-${prev}`, actor: 'controller', kind: 'revise', candidateId: prev, report: explorations[patchOrder.indexOf(prev)] || null });
    } else if (ev.type === 'run_finished') {
      const last = patchOrder[patchOrder.length - 1];
      if (last && !rounds.some((r) => r.key === `result-${last}`)) {
        addChallenge(last);
        rounds.push({ key: `result-${last}`, actor: 'engine', kind: 'result', candidateId: last });
      }
      rounds.push({ key: 'verdict', actor: 'verdict', kind: 'verdict', ev });
    }
  }
  return { rounds, criticOutputs, proposal, hasTranscript: Boolean(generations) };
}

function summarize(round, snap, ctx) {
  const cand = round.candidateId ? (snap?.candidates || []).find((c) => c.candidate_id === round.candidateId) : null;
  switch (round.kind) {
    case 'open': return ['Case opened', `${snap?.tests?.filter((t) => t.provenance === 'supplied').length ?? 0} supplied tests are the starting evidence`];
    case 'baseline': return ['Bug reproduced', round.ev.payload?.message || ''];
    case 'patch': return [round.revision ? `Revised patch · ${round.candidateId}` : `Patch proposed · ${round.candidateId}`, cand?.diagnosis || 'Patch submitted for checking'];
    case 'challenge': {
      const r = round.report;
      const found = r ? (r.counterexample ? `found a counterexample after ${r.inputs} inputs` : `tried ${r.inputs} inputs, no counterexample`) : 'generated extra inputs';
      if (round.first) {
        const fallback = ctx.proposal?.source === 'deterministic_fallback';
        return [fallback ? 'Critic challenge · fallback used' : 'Critic challenge', `${fallback ? 'Critic reply was invalid; the test engine ' : 'Test engine '}${found}`];
      }
      return ['Challenge repeated', `Test engine ${found}`];
    }
    case 'result': {
      const c = outcomeCounts(snap, round.candidateId);
      const verdict = cand?.eligibility === 'eligible' ? 'survived' : cand?.eligibility === 'rejected' ? 'rejected' : 'checking';
      return [`${round.candidateId} ${verdict}`, `${c.pass} passed · ${c.fail} failed${c.observed ? ` · ${c.observed} observed` : ''}`];
    }
    case 'revise': return ['Counterexample sent back', `Fixer A gets one revision for ${round.candidateId}`];
    case 'verdict': {
      const selected = snap?.decision?.selected_candidate_id;
      return [selected ? `Supported patch · ${selected}` : 'Unresolved', round.ev.payload?.message || ''];
    }
    default: return [round.kind, ''];
  }
}

function details(round, snap, ctx) {
  const body = el('div', 'history-detail');
  const cand = round.candidateId ? (snap?.candidates || []).find((c) => c.candidate_id === round.candidateId) : null;
  const supplied = (snap?.tests || []).filter((t) => t.provenance === 'supplied');

  if (round.kind === 'open') {
    body.appendChild(el('p', 'history-note', 'Your supplied tests are authoritative. Only executed checks decide the outcome.'));
    for (const t of supplied) body.appendChild(field(t.test_id, `${json(t.args)} → ${json(t.expected)}`));
  } else if (round.kind === 'baseline') {
    body.appendChild(el('p', 'history-note', 'The original code was run on your tests to confirm the bug is real.'));
    body.appendChild(failureTable(snap, 'original'));
  } else if (round.kind === 'patch') {
    if (cand?.diagnosis) body.appendChild(field('Diagnosis', cand.diagnosis));
    if (cand) body.appendChild(diffBlock(cand.diff));
    if (round.revision) body.appendChild(el('p', 'history-note', 'Written after seeing the counterexample that broke the previous patch.'));
    if (round.output) {
      const raw = el('details', 'history-raw');
      raw.appendChild(el('summary', null, 'Fixer A raw output'));
      raw.appendChild(pre(round.output.text));
      body.appendChild(raw);
    }
  } else if (round.kind === 'challenge') {
    if (round.first) {
      const prop = ctx.proposal;
      if (prop) {
        body.appendChild(field('Challenge plan', `${prop.family} inputs${prop.property_id ? ` checked against ${prop.property_id}` : ' (observations only)'}`));
        body.appendChild(field('Source', prop.source === 'raw_critic' ? 'Critic proposal accepted' : 'Critic reply was invalid, so the fixed fallback plan was used'));
        if (prop.source === 'raw_critic' && prop.reason) body.appendChild(field('Critic reason', prop.reason));
      }
      for (const g of ctx.criticOutputs) {
        const raw = el('details', 'history-raw');
        raw.appendChild(el('summary', null, 'Critic raw output'));
        raw.appendChild(pre(g.text));
        body.appendChild(raw);
      }
      if (!ctx.hasTranscript) body.appendChild(el('p', 'history-note', 'Model outputs appear here when the run finishes.'));
    } else {
      body.appendChild(el('p', 'history-note', 'The same challenge plan is replayed against the revised patch, plus every earlier counterexample.'));
    }
    const r = round.report;
    if (r) {
      body.appendChild(field('Inputs tried', String(r.inputs)));
      if (r.counterexample) {
        const box = el('div', 'history-case history-case-hit');
        box.appendChild(field('Counterexample', json(r.counterexample.args)));
        box.appendChild(field('Expected', json(r.counterexample.expected)));
        box.appendChild(field('Got', json(r.counterexample.actual_output)));
        body.appendChild(box);
      } else {
        body.appendChild(el('p', 'history-note', 'No input broke this patch.'));
      }
    }
  } else if (round.kind === 'result') {
    const c = outcomeCounts(snap, round.candidateId);
    body.appendChild(field('Authoritative', `${c.pass} passed, ${c.fail} failed`));
    if (c.observed) body.appendChild(field('Observed only', `${c.observed} (no expected value, cannot fail a patch)`));
    if (cand?.rejection_reason) body.appendChild(field('Reason', cand.rejection_reason));
    if (c.fail) body.appendChild(failureTable(snap, round.candidateId));
  } else if (round.kind === 'revise') {
    const r = round.report;
    if (r?.counterexample) {
      body.appendChild(el('p', 'history-note', 'Fixer A receives the failing supplied tests and this counterexample:'));
      body.appendChild(field('Input', json(r.counterexample.args)));
      body.appendChild(field('Expected', json(r.counterexample.expected)));
      body.appendChild(field('Got', json(r.counterexample.actual_output)));
    } else {
      body.appendChild(el('p', 'history-note', 'Fixer A receives the failing supplied tests for one more attempt.'));
    }
  } else if (round.kind === 'verdict') {
    const d = snap?.decision;
    body.appendChild(field('Reason', d?.reason || round.ev.payload?.message || ''));
    if (d?.selected_candidate_id) {
      body.appendChild(field('Checks covering the patch', String(d.verification_scope?.length ?? 0)));
      const chosen = (snap.candidates || []).find((c) => c.candidate_id === d.selected_candidate_id);
      if (chosen) body.appendChild(pre(chosen.source));
    }
    for (const c of (snap?.candidates || []).filter((x) => x.candidate_id !== 'original')) {
      body.appendChild(field(c.candidate_id, c.eligibility === 'eligible' ? 'eligible' : `rejected: ${c.rejection_reason || ''}`));
    }
  }
  return body;
}

const openRounds = new Set();

export function renderHistory(container, events, snap, transcript, rawRenderer) {
  if (!container) return;
  container.innerHTML = '';
  container.appendChild(el('div', 'timeline-notice', 'Factual record of proposals, challenges and executed checks. Click a step to see the evidence.'));

  if (!events || events.length === 0) {
    container.appendChild(el('p', 'placeholder-label', snap ? `Current phase: ${snap.phase} (${snap.status})` : 'Timeline idle.'));
    return;
  }

  const ctx = buildRounds(events, snap, transcript);
  const runId = snap?.run_id || '';
  const list = el('ol', 'history');
  for (const round of ctx.rounds) {
    const id = `${runId}:${round.key}`;
    const item = el('li', `history-step actor-${round.actor} kind-${round.kind}`);
    if (round.kind === 'result' || round.kind === 'verdict') {
      const cand = (snap?.candidates || []).find((c) => c.candidate_id === round.candidateId);
      const good = round.kind === 'verdict' ? Boolean(snap?.decision?.selected_candidate_id) : cand?.eligibility === 'eligible';
      item.classList.add(good ? 'is-good' : cand?.eligibility === 'pending' ? 'is-pending' : 'is-bad');
    }
    const [title, summary] = summarize(round, snap, ctx);
    const head = el('button', 'history-head');
    head.type = 'button';
    head.setAttribute('aria-expanded', String(openRounds.has(id)));
    head.appendChild(el('span', 'history-actor', ACTORS[round.actor]));
    const text = el('span', 'history-text');
    text.appendChild(el('strong', 'history-title', title));
    text.appendChild(el('span', 'history-summary', summary));
    head.appendChild(text);
    head.appendChild(el('span', 'history-chevron', '›'));
    item.appendChild(head);
    const panel = details(round, snap, ctx);
    panel.hidden = !openRounds.has(id);
    item.appendChild(panel);
    head.addEventListener('click', () => {
      const open = panel.hidden;
      panel.hidden = !open;
      head.setAttribute('aria-expanded', String(open));
      if (open) openRounds.add(id); else openRounds.delete(id);
    });
    list.appendChild(item);
  }
  container.appendChild(list);

  if (rawRenderer) {
    const raw = el('details', 'history-rawlog');
    raw.appendChild(el('summary', null, `Raw event log (${events.length} events)`));
    const box = el('div');
    raw.appendChild(box);
    raw.addEventListener('toggle', () => { if (raw.open && !box.childElementCount) rawRenderer(box); });
    container.appendChild(raw);
  }
}
