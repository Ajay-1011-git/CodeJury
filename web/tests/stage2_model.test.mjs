import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  actionTimeline, candidateCards, chartGroups, downloadFor, fmt, gapViews, lineage, reportView, resourceView,
  testMatrix, trainingView, withdrawsSuccess, sha256Hex,
} from '../src/s2/model.mjs';

const fx = (n) => JSON.parse(readFileSync(new URL(`../../contracts/stage2-fixtures/${n}.json`, import.meta.url)));
const snap = () => fx('snapshot-supported');

test('null is not measured while zero stays zero', () => {
  assert.equal(fmt(null), 'not measured');
  assert.equal(fmt(0), '0');
  assert.equal(fmt(0.5, 2), '0.50');
  const usage = { ...snap().resource_usage, peak_memory_mb: null, learned_candidates: 0 };
  const rows = Object.fromEntries(resourceView(usage).map((r) => [r.key, r.shown]));
  assert.equal(rows.peak_memory_mb, 'not measured');
  assert.equal(rows.learned_candidates, '0');
});

test('role cards separate the independent B view and mark the original unselectable', () => {
  const cards = candidateCards(snap());
  const by = Object.fromEntries(cards.map((c) => [c.candidate.origin, c]));
  assert.match(by.fixer_b.role.view, /never A’s code or the buggy body/);
  assert.match(by.fixer_a.role.view, /buggy bundle/);
  assert.equal(by.original.selectable, false);
  assert.equal(by.ast_search.selected, true);
});

test('search lineage reconstructs parent and edit hashes; a broken chain is detected', () => {
  const s = snap();
  const c = s.candidates.find((x) => x.origin === 'ast_search');
  const l = lineage(s, c);
  assert.equal(l.parents[0].candidate_id, c.parent_id);
  assert.equal(l.steps.length, c.edits.length);
  const broken = structuredClone(s);
  broken.candidates.find((x) => x.origin === 'ast_search').edits[0].parent_source_hash = '0'.repeat(64);
  assert.equal(lineage(broken, broken.candidates.find((x) => x.origin === 'ast_search')).chainOk, false);
});

test('two-edit lineage needs the intermediate artifact', () => {
  const s = snap();
  const root = s.candidates.find((x) => x.origin === 'original');
  const base = s.candidates.find((x) => x.origin === 'ast_search');
  const two = { ...base, candidate_id: 'c-two', parent_id: root.candidate_id, edits: [
    { ...base.edits[0], parent_source_hash: root.source_hash, result_source_hash: 'a'.repeat(64) },
    { ...base.edits[0], parent_source_hash: 'a'.repeat(64), result_source_hash: base.source_hash }] };
  const withArtifact = { ...s, candidates: [...s.candidates, two], edit_sources: [{ schema_version: 'stage2.v1', source_hash: 'a'.repeat(64), source: 'x' }] };
  assert.equal(lineage(withArtifact, two).chainOk, true);
  assert.equal(lineage({ ...withArtifact, edit_sources: [] }, two).chainOk, false);
});

test('stale qualification is flagged when the suite changed', () => {
  const s = snap();
  s.suite_hash = 'f'.repeat(64);
  assert.ok(candidateCards(s).find((c) => c.candidate.eligibility === 'eligible').stale);
  assert.equal(candidateCards(s).find((c) => c.candidate.eligibility === 'eligible').selectable, false);
});

test('test matrix distinguishes authority and marks mutated input', () => {
  const m = testMatrix(snap());
  assert.equal(m.rows.length, snap().tests.length);
  assert.ok(m.rows.every((r) => r.cells.length === m.candidates.length));
  const mutated = structuredClone(snap());
  mutated.executions[0].input_effects[0].mutated = true;
  assert.ok(testMatrix(mutated).rows.flatMap((r) => r.cells).some((c) => c && c.mutated));
});

test('gaps bind to the exact source and suite and keep equivalence unknown', () => {
  const s = snap();
  // the shared fixtures carry unrelated placeholder hashes; bind them like a real backend would
  s.audit_gaps[0].suite_hash = s.suite_hash;
  s.candidates.find((c) => c.candidate_id === s.audit_gaps[0].candidate_id).source_hash = s.audit_gaps[0].candidate_source_hash;
  const g = gapViews(s)[0];
  assert.equal(g.stale, false);
  assert.equal(g.probes[0].equivalence, 'equivalence unknown');
  assert.match(g.note, /not evidence the candidate is wrong/);
  const revised = structuredClone(s);
  revised.candidates.find((c) => c.candidate_id === g.gap.candidate_id).source_hash = '1'.repeat(64);
  assert.equal(gapViews(revised)[0].stale, true);
  const newSuite = { ...s, suite_hash: '2'.repeat(64) };
  assert.equal(gapViews(newSuite)[0].stale, true);
});

test('timeline marks refusals and fixed fallbacks', () => {
  const events = [
    { event_id: 1, type: 'action_refused', payload: { message: 'refused stale option', evidence_ids: [] } },
    { event_id: 2, type: 'action_selected', payload: { message: 'Fixed fallback selected', evidence_ids: [] } },
    { event_id: 3, type: 'candidate_created', payload: { message: 'ignored', evidence_ids: [] } }];
  const t = actionTimeline(snap(), events);
  assert.equal(t.log.length, 2);
  assert.equal(t.log[1].fallback, true);
  assert.equal(t.log[0].fallback, false);
  assert.equal(t.policy, 'learned');
});

test('download comes from the backend decision and exact bytes only', async () => {
  const s = snap();
  // fixture hashes are synthetic placeholders unless the source really hashes to them
  const chosen = s.candidates.find((c) => c.candidate_id === s.decision.selected_candidate_id);
  const real = structuredClone(s);
  real.candidates.find((c) => c.candidate_id === chosen.candidate_id).source_hash = await sha256Hex(chosen.source);
  real.candidates.find((c) => c.candidate_id === chosen.candidate_id).verification_suite_hash = real.suite_hash;
  const dl = await downloadFor(real);
  assert.equal(dl.text, chosen.source);
  assert.match(dl.filename, /^sum_values\.[0-9a-f]{12}\.py$/);
  assert.equal(dl.hash, await sha256Hex(dl.text));
  const tampered = structuredClone(real);
  tampered.candidates.find((c) => c.candidate_id === chosen.candidate_id).source += '# edit\n';
  assert.equal(await downloadFor(tampered), null);
  for (const status of ['unresolved', 'cancelled', 'infrastructure_error', 'invalid_input']) {
    assert.equal(await downloadFor({ ...real, status }), null, status);
  }
  const noDecision = { ...real, decision: { ...real.decision, selected_candidate_id: null } };
  assert.equal(await downloadFor(noDecision), null);
  const original = structuredClone(real);
  original.decision.selected_candidate_id = original.candidates.find((c) => c.origin === 'original').candidate_id;
  assert.equal(await downloadFor(original), null);
  const stale = { ...real, suite_hash: '9'.repeat(64) };
  assert.equal(await downloadFor(stale), null);
});

test('a withdrawn success is detected', () => {
  const ok = snap();
  assert.equal(withdrawsSuccess(ok, fx('snapshot-cancelled')), true);
  assert.equal(withdrawsSuccess(ok, fx('snapshot-infrastructure_error')), true);
  assert.equal(withdrawsSuccess(ok, ok), false);
  assert.equal(withdrawsSuccess(null, ok), false);
});

test('reports: exact counts, null precision, not-run, fixture separation', () => {
  const full = reportView(fx('benchmark-report'));
  assert.ok(full.rows.every((r) => r.partition));
  assert.match(full.rows[0].exact, /^\d+ \/ \d+ solved$/);
  const none = structuredClone(fx('benchmark-report'));
  none.rows[0].acceptance_precision = null; none.rows[0].solved = 0; none.rows[0].unresolved = none.rows[0].total_base_problems;
  none.rows[0].incorrect_accepted = 0;
  const v = reportView(none).rows[0];
  assert.equal(v.precision, 'not measured');
  assert.equal(v.exact.startsWith('0 /'), true);
  assert.equal(reportView(fx('benchmark-not-run')).rows.length, 0);
  assert.equal(reportView(fx('benchmark-not-run')).outcome, 'not_measured');
  const g = chartGroups([fx('benchmark-report'), { ...fx('benchmark-report'), runtime_mode: 'live' }]);
  assert.equal(g.fixture.length, 1);
  assert.equal(g.live.length, 1);
  const bad = structuredClone(fx('benchmark-report'));
  bad.rows[0].solved += 1;
  assert.equal(reportView(bad).rows[0].partition, false);
});

test('training cards label the general comparator and keep null losses', () => {
  const v = trainingView(fx('training-report'));
  assert.ok(v.every((c) => c.label));
  const none = trainingView(fx('training-not-started'));
  assert.ok(none.every((c) => c.status === 'not_started'));
});
