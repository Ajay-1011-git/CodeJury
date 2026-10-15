import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ComparisonClient, comparisonUrl, comparisonState, checkSummary, executionText } from '../src/comparison.mjs';

const run = `run-${'a'.repeat(32)}`;

test('comparison links accept real run ids and preserve the original desk in another page', () => {
  assert.equal(comparisonUrl(run), `/comparison.html?run=${run}`);
  assert.equal(comparisonUrl('javascript:alert(1)'), null);
});

test('loading a comparison never starts inference; only explicit POST does', async () => {
  const calls = [];
  const client = new ComparisonClient(run, async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ comparison_version: 1, run_id: run, status: 'not_started' }) };
  });
  await client.request(); await client.request('POST');
  assert.deepEqual(calls.map((c) => c.options.method), ['GET', 'POST']);
  assert.equal(calls[0].url, `/s2x/runs/${run}/baseline`);
});

test('another case or service version cannot be displayed as this comparison', async () => {
  const client = new ComparisonClient(run, async () => ({ ok: true, json: async () => ({ comparison_version: 1, run_id: 'other' }) }));
  await assert.rejects(client.request(), /does not match/);
  assert.throws(() => new ComparisonClient('../other'), /finished CodeJury/);
});

test('busy failures keep the actionable server message', async () => {
  const client = new ComparisonClient(run, async () => ({ ok: false, json: async () => ({ error: { message: 'Another repair is running' } }) }));
  await assert.rejects(client.request('POST'), /Another repair/);
});

test('unresolved jury and unusable raw replies cannot claim a successful repair', () => {
  const body = { status: 'complete', jury: { status: 'unresolved' }, baseline: { source: null, checks: null } };
  assert.equal(comparisonState(body).juryTitle, 'Jury left the case unresolved');
  assert.equal(comparisonState(body).rawTitle, 'No usable patch returned');
  assert.equal(comparisonState(body).canStart, false);
  assert.equal(checkSummary(null), 'No shared-example result');
  assert.match(checkSummary({ status: 'incomplete', passed: 1, total: 3 }), /incomplete/);
});

test('passing finite examples is labelled narrowly', () => {
  const body = { status: 'complete', jury: { status: 'supported_patch' }, baseline: { source: 'code', checks: { status: 'passed_examples' } } };
  assert.equal(comparisonState(body).rawTitle, 'Passed the shared examples');
  assert.equal(checkSummary({ status: 'passed_examples', passed: 3, total: 3 }), '3/3 shared examples passed');
});

test('a matching output that changed its input explains the failed check', () => {
  assert.equal(executionText({ outcome: 'fail', actual_output: [1, 3], input_effects: [{ mutated: true, before_hash: 'a', after_hash: 'b' }] }), 'fail · input changed · [1,3]');
});
