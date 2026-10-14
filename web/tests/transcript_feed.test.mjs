import { test } from 'node:test';
import assert from 'node:assert/strict';
import { TranscriptFeed } from '../src/transcript-feed.mjs';

const body = (runId, label) => ({ schema_version: 'stage2.v1', run_id: runId, calls: [label] });
const response = (value) => ({ ok: true, json: async () => value });
const deferred = () => { let resolve; const promise = new Promise((r) => { resolve = r; }); return { promise, resolve }; };

test('a live transcript is refreshed again at terminal and final fetching is not duplicated', async () => {
  const updates = []; let requests = 0;
  const feed = new TranscriptFeed({ base: '/s2', getRunId: () => 'one', onUpdate: (v) => updates.push(v), fetchFn: async () => response(body('one', ++requests)) });
  await feed.refresh({ run_id: 'one' }, false, 0);
  await feed.refresh({ run_id: 'one' }, true, 1);
  await feed.refresh({ run_id: 'one' }, true, 2);
  assert.equal(requests, 2);
  assert.deepEqual(updates.map((v) => v.calls[0]), [1, 2]);
});

test('a late live response cannot overwrite the completed terminal transcript', async () => {
  const live = deferred(); const updates = []; let requests = 0;
  const feed = new TranscriptFeed({ base: '/s2', getRunId: () => 'one', onUpdate: (v) => updates.push(v), fetchFn: async () => ++requests === 1 ? live.promise : response(body('one', 'final verdict')) });
  const pending = feed.refresh({ run_id: 'one' }, false, 0);
  await feed.refresh({ run_id: 'one' }, true, 1);
  live.resolve(response(body('one', 'partial')));
  await pending;
  assert.deepEqual(updates.map((v) => v.calls[0]), ['final verdict']);
});

test('a previous run response cannot replace the currently selected run', async () => {
  const old = deferred(); const updates = []; let runId = 'one';
  const feed = new TranscriptFeed({ base: '/s2', getRunId: () => runId, onUpdate: (v) => updates.push(v), fetchFn: async (url) => url.includes('/one/') ? old.promise : response(body('two', 'current')) });
  const pending = feed.refresh({ run_id: 'one' }, false, 0);
  runId = 'two';
  await feed.refresh({ run_id: 'two' }, true, 1);
  old.resolve(response(body('one', 'old')));
  await pending;
  assert.deepEqual(updates.map((v) => v.run_id), ['two']);
});

test('a failed terminal fetch remains retryable on the next state update', async () => {
  let requests = 0; const updates = [];
  const feed = new TranscriptFeed({ base: '/s2', getRunId: () => 'one', onUpdate: (v) => updates.push(v), fetchFn: async () => ++requests === 1 ? { ok: false } : response(body('one', 'complete')) });
  assert.equal(await feed.refresh({ run_id: 'one' }, true, 0), false);
  assert.equal(await feed.refresh({ run_id: 'one' }, true, 1), true);
  assert.equal(updates.length, 1);
});
