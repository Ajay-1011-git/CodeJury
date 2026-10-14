import { test } from 'node:test';
import assert from 'node:assert/strict';
import { IntakeClient, approvalDecisions, draftItems, itemSummary } from '../src/quick-case.mjs';

test('intake sends only three quick-case fields to its separate endpoint', async () => {
  const calls = [];
  const client = new IntakeClient('http://localhost/s2x', async (url, options) => {
    calls.push({ url, options });
    return { ok: true, json: async () => ({ spec_version: 1, id: 'intake-one' }) };
  });
  const payload = { source: 'def f(x):\n return 0', function_name: 'f', description: 'Double the integer.' };
  await client.infer(payload);
  assert.equal(calls[0].url, 'http://localhost/s2x/intake');
  assert.deepEqual(JSON.parse(calls[0].options.body), payload);
  await client.approve('intake/one', { approve_all: true });
  assert.equal(calls[1].url, 'http://localhost/s2x/intake/intake%2Fone/approve');
});

test('draft mapping preserves proposed source values and stable per-item IDs', () => {
  const draft = { arg_domains: [{ param: 'x', domain: { kind: 'integer' }, source: 'local_ast' }], requirements: [{ id: 'r1', text: 'Double the integer.', property_template_id: null, source: 'groq' }], examples: [{ id: 'e1', args: [2], expected: 4, source: 'groq' }] };
  assert.deepEqual(draftItems(draft).map((item) => item.id), ['domain:x', 'requirement:r1', 'example:e1']);
  assert.equal(draftItems(draft)[2].value.expected, 4);
});

test('approval is explicit and interpreter trust defaults off', () => {
  const items = [{ id: 'domain:x', decision: 'approve' }, { id: 'example:e1', decision: 'reject' }, { id: 'requirement:r1', decision: 'edit', text: '{"text":"Triple the integer."}' }];
  const decisions = approvalDecisions(items);
  assert.equal(decisions.trust_interpreter, false);
  assert.equal(decisions.items[1].decision, 'reject');
  assert.deepEqual(decisions.items[2].value, { text: 'Triple the integer.' });
  assert.equal(approvalDecisions(items, true).trust_interpreter, true);
  assert.throws(() => approvalDecisions([{ id: 'x', decision: 'edit', text: '{' }]));
});

test('review preserves corroboration and makes domains/examples readable', () => {
  const items = draftItems({ arg_domains: [{ param: 'values', domain: { kind: 'list', min_length: 0, max_length: 8, item_domain: { kind: 'integer', min: -10, max: 10 } }, source: 'groq' }], examples: [{ id: 'e1', args: [[2, -1]], expected: 1, source: 'groq', tier: 'corroborated', corroboration: ['sum_ints'] }] });
  assert.equal(items[1].tier, 'corroborated');
  assert.match(itemSummary(items[0]), /List of 0–8 items.*Integer from -10 to 10/);
  assert.equal(itemSummary(items[1]), 'Input: [[2,-1]]\nExpected output: 1');
});

test('intake refuses service/version failures and keeps their messages', async () => {
  const client = new IntakeClient('', async () => ({ ok: false, status: 503, json: async () => ({ error: { message: 'Budget cap reached' } }) }));
  await assert.rejects(client.infer({}), /Budget cap reached/);
  const other = new IntakeClient('', async () => ({ ok: true, json: async () => ({ spec_version: 2 }) }));
  await assert.rejects(other.infer({}), /version/);
});
