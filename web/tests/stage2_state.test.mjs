import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Store } from '../src/s2/state.mjs';
import { ApiError } from '../src/s2/api.mjs';

const fx = (n) => JSON.parse(readFileSync(new URL(`../../contracts/stage2-fixtures/${n}.json`, import.meta.url)));

function fakeClient(script) {
  const calls = { events: [], getRun: 0, report: 0 };
  return {
    calls,
    createRun: async () => ({ run_id: 'r1', runtime_mode: 'fixture' }),
    getRun: async () => { const s = script.snapshots[Math.min(calls.getRun, script.snapshots.length - 1)]; calls.getRun += 1; return s; },
    getEvents: async (_id, after) => { calls.events.push(after); const page = script.pages[Math.min(calls.events.length - 1, script.pages.length - 1)]; return page; },
    getReport: async () => { calls.report += 1; return script.report ?? script.snapshots.at(-1); },
    cancelRun: async () => fx('snapshot-cancelled'),
  };
}
const ev = (ids) => ({ events: ids.map((i) => ({ event_id: i, type: 'run_started', payload: { message: 'm', evidence_ids: [] } })), next_after: Math.max(...ids) });
const manual = () => { const q = []; return { q, setTimer: (f) => { q.push(f); return q.length; }, clearTimer: () => {} }; };
const ready = (s) => s.set({ healthOk: true });

test('polls with a cursor, deduplicates events, stops at terminal and fetches the report', async () => {
  const t = manual();
  const store = new Store(t); ready(store);
  const client = fakeClient({ snapshots: [fx('snapshot-running'), fx('snapshot-supported')], pages: [ev([1, 2]), ev([2, 3]), ev([3])] });
  await store.submit(client, {});
  assert.equal(store.state.events.length, 2);
  assert.equal(store.state.after, 2);
  assert.equal(t.q.length, 1, 'one 1s poll scheduled');
  await t.q.shift()();
  assert.deepEqual(store.state.events.map((e) => e.event_id), [1, 2, 3]);
  assert.deepEqual(client.calls.events.slice(0, 2), [0, 2]);
  assert.equal(client.calls.report, 1);
  assert.equal(t.q.length, 0, 'polling stopped at the terminal state');
  assert.equal(store.state.snapshot.status, 'supported_patch');
});

test('interval is 1000 ms', () => {
  assert.equal(new Store().intervalMs, 1000);
});

test('duplicate submits and unverified backends are refused', async () => {
  const store = new Store(manual());
  await assert.rejects(store.submit(fakeClient({ snapshots: [fx('snapshot-running')], pages: [ev([1])] }), {}), /contract check/);
  ready(store);
  store.set({ submitting: true });
  await assert.rejects(store.submit(fakeClient({ snapshots: [fx('snapshot-running')], pages: [ev([1])] }), {}), /already in progress/);
});

test('a stale response from an older run cannot overwrite a newer one', async () => {
  const t = manual();
  const store = new Store(t); ready(store);
  let release;
  const slow = { ...fakeClient({ snapshots: [fx('snapshot-running')], pages: [ev([1])] }), getRun: () => new Promise((res) => { release = () => res({ ...fx('snapshot-running'), run_id: 'old' }); }) };
  const first = store.submit(slow, {});
  await new Promise((r) => setTimeout(r, 0));
  store.set({ token: store.state.token + 1, snapshot: { sentinel: true } });
  release();
  await first;
  assert.deepEqual(store.state.snapshot, { sentinel: true });
});

test('dispose on navigation stops timers and ignores late responses', async () => {
  const t = manual();
  const store = new Store(t); ready(store);
  const client = fakeClient({ snapshots: [fx('snapshot-running')], pages: [ev([1])] });
  await store.submit(client, {});
  store.dispose();
  const before = store.state.snapshot;
  for (const f of t.q.splice(0)) await f();
  assert.equal(store.state.snapshot, before);
});

test('withdrawn success: report of a different outcome clears the earlier success', async () => {
  const t = manual();
  const store = new Store(t); ready(store);
  const client = fakeClient({ snapshots: [fx('snapshot-supported')], pages: [ev([1])], report: fx('snapshot-infrastructure_error') });
  await store.submit(client, {});
  assert.equal(store.state.snapshot.status, 'infrastructure_error');
  assert.equal(store.state.withdrawn, true);
});

test('cancel stops polling and shows the cancelled snapshot, clearing a prior success', async () => {
  const t = manual();
  const store = new Store(t); ready(store);
  const client = fakeClient({ snapshots: [fx('snapshot-running')], pages: [ev([1])] });
  await store.submit(client, {});
  store.set({ snapshot: fx('snapshot-supported') });
  await store.cancel(client);
  assert.equal(store.state.snapshot.status, 'cancelled');
  assert.equal(store.state.withdrawn, true);
});

test('404 surfaces the error; other errors keep retrying every second', async () => {
  const t = manual();
  const store = new Store(t); ready(store);
  let n = 0;
  const client = { ...fakeClient({ snapshots: [fx('snapshot-running')], pages: [ev([1])] }), getRun: async () => { n += 1; throw new ApiError('boom', n === 1 ? 500 : 404, 'x'); } };
  await store.submit(client, {});
  assert.equal(t.q.length, 1);
  await t.q.shift()();
  assert.equal(store.state.error.status, 404);
  assert.equal(t.q.length, 0);
});
