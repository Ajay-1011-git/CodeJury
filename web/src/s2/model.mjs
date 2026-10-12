/** Pure view-models over stage2.v1 records. No DOM, no network: everything here is unit-tested. */

export const TERMINAL = Object.freeze(['supported_patch', 'unresolved', 'invalid_input', 'infrastructure_error', 'cancelled']);
export const CAPS = Object.freeze({
  output_tokens: 10000, input_tokens: 100000, function_executions: 3000, elapsed_ms: 900000,
  learned_candidates: 8, search_candidates: 48, audit_mutants: 48, judge_decisions: 8,
});
export const NOT_MEASURED = 'not measured';

/** null is "not measured"; zero stays zero. */
export function fmt(value, digits = 0) {
  if (value === null || value === undefined) return NOT_MEASURED;
  if (typeof value === 'number' && !Number.isInteger(value)) return value.toFixed(digits || 3);
  return String(value);
}
export const pct = (v) => (v === null || v === undefined ? NOT_MEASURED : `${(v * 100).toFixed(1)}%`);

export const ROLE_CARDS = Object.freeze({
  original: { label: 'Original (never selectable)', view: 'The submitted buggy bundle.' },
  fixer_a: { label: 'Fixer A', view: 'Initial view A: buggy bundle, requirements, tests and trace.' },
  fixer_b: { label: 'Fixer B', view: 'Initial view B (independent): signature, contract, domains, dependency and helper interfaces, tests — never A’s code or the buggy body.' },
  fixer_a_revision: { label: 'Fixer A revision', view: 'Revision of a committed parent using real counterexamples.' },
  fixer_b_revision: { label: 'Fixer B revision', view: 'Revision of a committed parent using real counterexamples.' },
  ast_search: { label: 'AST search edit', view: 'Deterministic descendant of a committed parent; not an independent opinion.' },
});

const byId = (list, key) => new Map(list.map((x) => [x[key], x]));

/** Parent chain, ordered edits and a hash-chain check that reconstructs each edit in order. */
export function lineage(snapshot, candidate) {
  const cands = byId(snapshot.candidates, 'candidate_id');
  const artifacts = byId(snapshot.edit_sources || [], 'source_hash');
  const parents = [];
  let cursor = candidate;
  const guard = new Set();
  while (cursor.parent_id && !guard.has(cursor.candidate_id)) {
    guard.add(cursor.candidate_id);
    const parent = cands.get(cursor.parent_id);
    if (!parent) { parents.push({ candidate_id: cursor.parent_id, missing: true }); break; }
    parents.push({ candidate_id: parent.candidate_id, origin: parent.origin, source_hash: parent.source_hash });
    cursor = parent;
  }
  const root = parents.length ? cands.get(candidate.parent_id) : null;
  let expected = root ? root.source_hash : null;
  let chainOk = candidate.edits.length === 0 || root !== null;
  const steps = candidate.edits.map((edit, index) => {
    const ok = expected === edit.parent_source_hash;
    const last = index === candidate.edits.length - 1;
    const resultKnown = last ? edit.result_source_hash === candidate.source_hash : artifacts.has(edit.result_source_hash);
    if (!ok || !resultKnown) chainOk = false;
    expected = edit.result_source_hash;
    return { ...edit, ok: ok && resultKnown, intermediate: last ? null : artifacts.get(edit.result_source_hash)?.source ?? null };
  });
  return { parents, steps, chainOk };
}

export function isStale(snapshot, candidate) {
  return candidate.eligibility === 'eligible' && snapshot.suite_hash !== null
    && candidate.verification_suite_hash !== snapshot.suite_hash;
}

export function candidateCards(snapshot) {
  const selected = snapshot.decision?.selected_candidate_id ?? null;
  return snapshot.candidates.map((c) => ({
    candidate: c,
    role: ROLE_CARDS[c.origin] || { label: c.origin, view: '' },
    lineage: lineage(snapshot, c),
    stale: isStale(snapshot, c),
    selectable: c.origin !== 'original' && c.eligibility === 'eligible' && !isStale(snapshot, c),
    selected: c.candidate_id === selected,
  }));
}

const STATUS_LABEL = {
  authoritative: 'authoritative (can reject)',
  proposed: 'proposed (observation only)',
  observation_only: 'observation only',
  rejected: 'rejected (not executed)',
};
export const testStatusLabel = (t) => STATUS_LABEL[t.oracle_status] || t.oracle_status;

export function testMatrix(snapshot) {
  const cell = new Map();
  for (const e of snapshot.executions) cell.set(`${e.test_id}|${e.candidate_id}`, e);
  return {
    candidates: snapshot.candidates.map((c) => c.candidate_id),
    rows: snapshot.tests.map((t) => ({
      test: t,
      label: testStatusLabel(t),
      authoritative: t.oracle_status === 'authoritative',
      cells: snapshot.candidates.map((c) => {
        const e = cell.get(`${t.test_id}|${c.candidate_id}`);
        return e ? { outcome: e.outcome, mutated: e.input_effects.some((x) => x.mutated), execution: e } : null;
      }),
    })),
  };
}

/** Gaps bound to an exact source and suite; probes are evidence, never votes. */
export function gapViews(snapshot) {
  const cands = byId(snapshot.candidates, 'candidate_id');
  const mutants = byId(snapshot.probe_mutants, 'mutant_id');
  return snapshot.audit_gaps.map((gap) => {
    const cand = cands.get(gap.candidate_id);
    const stale = !cand || cand.source_hash !== gap.candidate_source_hash || gap.suite_hash !== snapshot.suite_hash;
    return {
      gap, stale,
      probes: gap.mutant_ids.map((id) => mutants.get(id)).filter(Boolean).map((m) => ({
        mutant: m,
        equivalence: m.equivalence_status === 'unknown' ? 'equivalence unknown' : m.equivalence_status.replace('_', ' '),
      })),
      note: stale ? 'Stale: bound to a different source or suite and cannot accuse the current candidate.'
        : 'Unresolved test gap. A survivor may be equivalent; it is not evidence the candidate is wrong.',
    };
  });
}

export function actionTimeline(snapshot, events) {
  const rows = snapshot.actions.map((a) => ({
    kind: 'action', id: a.action_id, title: `${a.kind}${a.parameters.mode ? ` · ${a.parameters.mode}` : ''}`,
    detail: a.rationale, evidence: a.evidence_ids, budget: a.requested_budget,
  }));
  const log = events.filter((e) => ['action_selected', 'action_refused', 'candidate_invalidated', 'budget_exhausted', 'test_admitted', 'test_rejected', 'audit_gap_found'].includes(e.type)).map((e) => ({
    kind: e.type, id: String(e.event_id), title: e.type.replace(/_/g, ' '), detail: e.payload.message,
    fallback: /fixed fallback/i.test(e.payload.message), evidence: e.payload.evidence_ids,
  }));
  return { actions: rows, log, policy: snapshot.policy_mode };
}

export function resourceView(usage) {
  return Object.entries(CAPS).map(([key, cap]) => ({ key, used: usage[key], cap }))
    .concat([{ key: 'peak_memory_mb', used: usage.peak_memory_mb, cap: null }])
    .map((row) => ({ ...row, label: row.key.replace(/_/g, ' '), shown: row.used === null ? NOT_MEASURED : String(row.used) }));
}

export async function sha256Hex(text) {
  const digest = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

/** Download comes only from the backend decision and the immutable candidate bytes. */
export async function downloadFor(snapshot) {
  const d = snapshot?.decision;
  if (!snapshot || snapshot.status !== 'supported_patch' || !d?.selected_candidate_id) return null;
  const cand = snapshot.candidates.find((c) => c.candidate_id === d.selected_candidate_id);
  if (!cand || cand.origin === 'original' || cand.eligibility !== 'eligible' || isStale(snapshot, cand)) return null;
  if ((await sha256Hex(cand.source)) !== cand.source_hash) return null;
  return {
    filename: `${snapshot.problem.function_name}.${cand.source_hash.slice(0, 12)}.py`,
    text: cand.source, hash: cand.source_hash, candidate_id: cand.candidate_id, scope: d.verification_scope,
    suite_hash: d.suite_hash,
  };
}

/** A previously shown success must disappear when a newer snapshot withdraws it. */
export function withdrawsSuccess(prev, next) {
  return !!prev && prev.status === 'supported_patch' && (!next || next.status !== 'supported_patch'
    || next.decision?.selected_candidate_id !== prev.decision?.selected_candidate_id);
}

/** Fixture and live reports never share one chart. */
export function chartGroups(reports) {
  const groups = { live: [], fixture: [] };
  for (const r of reports) groups[r.runtime_mode === 'live' ? 'live' : 'fixture'].push(r);
  return groups;
}

export function reportView(report) {
  const fixture = report.runtime_mode === 'fixture';
  return {
    fixture,
    status: report.status,
    outcome: report.research_outcome,
    rows: report.rows.map((r) => {
      const six = ['solved', 'incorrect_accepted', 'unresolved', 'invalid_input', 'infrastructure_error', 'cancelled'];
      return {
        row: r,
        exact: `${r.solved} / ${r.total_base_problems} solved`,
        partition: six.reduce((s, k) => s + r[k], 0) === r.total_base_problems,
        precision: pct(r.acceptance_precision),
        width: r.total_base_problems ? (100 * r.solved) / r.total_base_problems : 0,
      };
    }),
    note: report.paired_analysis_note,
    limitations: report.limitations,
  };
}

export function trainingView(report) {
  return report.cards.map((c) => ({
    card: c,
    label: ({ fixer_a: 'Fixer A', fixer_b: 'Fixer B', critic: 'Critic', judge: 'Judge', general: 'General comparator (not a jury role)' })[c.role],
    status: c.status,
    losses: c.loss_points.map((p) => ({ step: p.step, train: p.train_loss, validation: p.validation_loss })),
    comparator: c.role === 'general',
  }));
}
