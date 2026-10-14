import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildDebate, lineDiff, hardRecord } from '../src/stage2-debate.mjs';

const original = { candidate_id: 'c-o', origin: 'original', source: 'def f(x):\n    return 0\n', eligibility: 'rejected' };
const a = { candidate_id: 'c-a', origin: 'fixer_a', source: 'def f(x):\n    return 1\n', eligibility: 'rejected' };
const b = { candidate_id: 'c-b', origin: 'fixer_b', source: 'def f(x):\n    return x\n', eligibility: 'eligible' };
const snap = {
  run_id: 'run-x', policy_mode: 'learned', status: 'supported_patch',
  candidates: [original, a, b],
  tests: [{ test_id: 't1', inputs: [2], oracle_status: 'authoritative', oracle_spec: { kind: 'literal', expected: 2 }, provenance: 'supplied' }],
  executions: [
    { candidate_id: 'c-o', test_id: 't1', outcome: 'fail', actual_output: 0 },
    { candidate_id: 'c-a', test_id: 't1', outcome: 'fail', actual_output: 1 },
    { candidate_id: 'c-b', test_id: 't1', outcome: 'pass', actual_output: 2 },
  ],
  actions: [
    { action_id: 'act-1', kind: 'criticize', parameters: { mode: 'challenge_agreement' }, target_ids: ['c-b'] },
    { action_id: 'act-2', kind: 'select', parameters: { candidate_id: 'c-b' }, target_ids: ['c-b'] },
  ],
  decision: { selected_candidate_id: 'c-b', reason: 'done', verification_scope: ['t1'], unresolved_requirements: [] },
};
const ev = (id, type, payload) => ({ event_id: id, type, payload: { candidate_id: null, test_id: null, action_id: null, message: '', ...payload } });
const events = [
  ev(1, 'run_started', {}), ev(2, 'candidate_created', { candidate_id: 'c-o' }), ev(3, 'execution_completed', { candidate_id: 'c-o' }),
  ev(4, 'candidate_created', { candidate_id: 'c-a' }), ev(5, 'candidate_created', { candidate_id: 'c-b' }),
  ev(6, 'action_selected', { action_id: 'act-1', message: 'Challenge shared agreement' }),
  ev(7, 'test_admitted', { test_id: 't1' }),
  ev(8, 'action_selected', { action_id: 'act-2', message: 'Select it' }),
  ev(9, 'run_finished', { message: 'done' }),
];
const transcript = { calls: [
  { role: 'fixer_a', text: 'not json' },
  { role: 'fixer_a', text: JSON.stringify({ source: a.source }) },
  { role: 'fixer_b', text: JSON.stringify({ source: b.source }) },
  { role: 'judge', text: JSON.stringify({ action_option_id: 'option-01' }), options: [{ option_id: 'option-01', summary: 'Challenge shared agreement' }] },
  { role: 'critic', text: JSON.stringify({ mode: 'challenge_agreement' }) },
  { role: 'judge', text: JSON.stringify({ action_option_id: 'option-02' }), options: [{ option_id: 'option-02', summary: 'Select it' }] },
] };

test('debate rounds pair events with the model replies that produced them', () => {
  const rounds = buildDebate(snap, events, transcript);
  assert.deepEqual(rounds.map((r) => r.kind), ['open', 'baseline', 'proposal', 'proposal', 'decision', 'challenge', 'decision', 'verdict']);
  const [, , ra, rb, judge1, critic, judge2] = rounds;
  assert.equal(ra.actor, 'fixer_a');
  assert.equal(ra.invalid.length, 1, 'unparseable Fixer A reply is kept as an unusable attempt');
  assert.equal(rb.reply.role, 'fixer_b');
  assert.equal(judge1.actor, 'judge');
  assert.equal(judge1.call.options[0].option_id, 'option-01');
  assert.deepEqual(critic.tests, ['t1']);
  assert.equal(critic.call.role, 'critic');
  assert.equal(judge2.call.options[0].summary, 'Select it');
});

test('fixed policy decisions are attributed to the Controller', () => {
  const rounds = buildDebate({ ...snap, policy_mode: 'fixed' }, events, { calls: [] });
  assert.ok(rounds.filter((r) => r.kind === 'decision').every((r) => r.actor === 'controller'));
});

test('a Critic refusal belongs to the Controller and does not consume the next Judge reply', () => {
  const withRefusal = [...events.slice(0, 7),
    ev(71, 'action_refused', { message: 'Malformed or out-of-scope Critic draft' }),
    ...events.slice(7)];
  const rounds = buildDebate(snap, withRefusal, transcript);
  const refused = rounds.find((r) => r.kind === 'refused');
  assert.equal(refused.actor, 'controller');
  assert.equal(refused.call, null);
  assert.equal(rounds.filter((r) => r.kind === 'decision')[1].call.options[0].summary, 'Select it');
});

test('hard record counts only authoritative checks', () => {
  assert.deepEqual([hardRecord(snap, 'c-b').pass, hardRecord(snap, 'c-a').fail], [1, 1]);
});

test('line diff marks changed lines', () => {
  assert.deepEqual(lineDiff('a\nb\n', 'a\nc\n').map((r) => r.op), [' ', '-', '+']);
});

test('conversation keeps recorded claims, tokens, evidence and revision diffs unchanged', async () => {
  const { buildTurns } = await import('../src/stage2-debate.mjs');
  const turns = [
    { turn: 1, role: 'fixer_a', kind: 'proposal', claim: 'The accumulator skipped negatives.', tokens: 42 },
    { turn: 2, role: 'tools', kind: 'counterexample', claim: 'Sandbox evidence committed', evidence: { exec_id: 'e1', input: [-2], expected: -2, actual: 0, tier: 'authoritative' }, tokens: 0 },
    { turn: 3, role: 'fixer_a', kind: 'revision', claim: 'Include negative values.', patch_diff: '- old\n+ new', tokens: 20 },
  ];
  assert.deepEqual(buildTurns(snap, events, { turns }), turns);
  assert.equal(buildTurns(snap, events, { turns })[0].claim, turns[0].claim);
  assert.deepEqual(buildTurns(snap, events, { calls: transcript.calls }), [], 'never invent a conversation when turn records are absent');
});

test('conversation ignores unknown role/kind records and keeps cloud interpretation labelled', async () => {
  const { buildTurns } = await import('../src/stage2-debate.mjs');
  const turns = [
    { turn: 1, role: 'interpreter', kind: 'proposal', claim: '{"requirements":[]}', label: 'Interpreter (cloud, spec only)' },
    { turn: 2, role: 'invented', kind: 'proposal', claim: 'not recorded' },
  ];
  assert.equal(buildTurns(snap, [], { turns }).length, 1);
  assert.equal(buildTurns(snap, [], { turns })[0].label, 'Interpreter (cloud, spec only)');
  assert.deepEqual(buildTurns(null, [], { turns }), []);
});
