import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AppState, TERMINAL_STATUSES } from '../src/state.mjs';

test('AppState prevents duplicate submissions', async () => {
  const store = new AppState();
  const slowClient = {
    createRun: () => new Promise(resolve => setTimeout(() => resolve({ schema_version: 'stage1.v1', run_id: 'r1', status: 'queued', runtime_mode: 'fixture' }), 50)),
    getRun: async () => ({ status: 'queued', runtime_mode: 'fixture' }),
    getEvents: async () => ({ events: [], next_after: 0 })
  };

  const p1 = store.startRun(slowClient, { schema_version: 'stage1.v1' });
  assert.equal(store.get().isSubmitting, true);

  await assert.rejects(
    async () => store.startRun(slowClient, { schema_version: 'stage1.v1' }),
    /duplicate submit/i
  );

  await p1;
  store.stopPolling();
  assert.equal(store.get().isSubmitting, false);
});

test('AppState generation token discards stale async polls', async () => {
  const store = new AppState();
  let pollCount = 0;
  const mockClient = {
    createRun: async (p) => ({ schema_version: 'stage1.v1', run_id: p.run_id, status: 'queued', runtime_mode: 'fixture' }),
    getRun: async (runId) => {
      pollCount++;
      return { schema_version: 'stage1.v1', run_id: runId, status: 'running', runtime_mode: 'fixture' };
    },
    getEvents: async () => ({ events: [], next_after: 0 })
  };

  // Start run 1
  await store.startRun(mockClient, { schema_version: 'stage1.v1', run_id: 'run-1' });
  const token1 = store.get().generationToken;
  assert.equal(store.get().currentRunId, 'run-1');

  // Start run 2 immediately (token increments)
  await store.startRun(mockClient, { schema_version: 'stage1.v1', run_id: 'run-2' });
  const token2 = store.get().generationToken;
  assert.ok(token2 > token1);
  assert.equal(store.get().currentRunId, 'run-2');

  // Attempt stale poll with token1
  await store.pollLifecycle(mockClient, 'run-1', token1);
  // Store should NOT have regressed to run-1
  assert.equal(store.get().currentRunId, 'run-2');

  store.stopPolling();
});

test('AppState deduplicates and preserves ordering of events', async () => {
  const store = new AppState();
  const eventsBatch1 = [
    { event_id: 2, type: 'original_checked' },
    { event_id: 1, type: 'run_started' }
  ];
  const eventsBatch2 = [
    { event_id: 2, type: 'original_checked' }, // duplicate
    { event_id: 3, type: 'candidate_created' }
  ];

  let pollStep = 0;
  const mockClient = {
    createRun: async () => ({ schema_version: 'stage1.v1', run_id: 'run-ev', status: 'queued', runtime_mode: 'fixture' }),
    getRun: async () => ({ schema_version: 'stage1.v1', status: 'running', runtime_mode: 'fixture' }),
    getEvents: async () => {
      pollStep++;
      return pollStep === 1
        ? { events: eventsBatch1, next_after: 2 }
        : { events: eventsBatch2, next_after: 3 };
    }
  };

  await store.startRun(mockClient, { schema_version: 'stage1.v1' });
  // Second poll
  await store.pollLifecycle(mockClient, 'run-ev', store.get().generationToken);
  store.stopPolling();

  const finalEvents = store.get().events;
  assert.equal(finalEvents.length, 3);
  assert.equal(finalEvents[0].event_id, 1);
  assert.equal(finalEvents[1].event_id, 2);
  assert.equal(finalEvents[2].event_id, 3);
});

test('AppState terminates polling and retrieves report upon terminal status', async () => {
  const store = new AppState();
  let reportFetched = false;
  const mockClient = {
    createRun: async () => ({ schema_version: 'stage1.v1', run_id: 'r-term', status: 'queued', runtime_mode: 'fixture' }),
    getRun: async () => ({ schema_version: 'stage1.v1', status: 'supported_patch', runtime_mode: 'fixture' }),
    getEvents: async () => ({ events: [], next_after: 0 }),
    getReport: async () => {
      reportFetched = true;
      return { schema_version: 'stage1.v1', status: 'supported_patch', termination_reason: 'Completed' };
    }
  };

  await store.startRun(mockClient, { schema_version: 'stage1.v1' });
  assert.equal(store.pollTimer, null, 'Polling timer must be stopped');
  assert.equal(reportFetched, true, 'Report must be fetched upon terminal state');
  assert.equal(store.get().runSnapshot.status, 'supported_patch');
});

test('AppState cancelRun terminates polling cleanly', async () => {
  const store = new AppState();
  const mockClient = {
    createRun: async () => ({ schema_version: 'stage1.v1', run_id: 'r-cancel', status: 'queued', runtime_mode: 'fixture' }),
    getRun: async () => ({ schema_version: 'stage1.v1', status: 'running', runtime_mode: 'fixture' }),
    getEvents: async () => ({ events: [], next_after: 0 }),
    cancelRun: async () => ({ schema_version: 'stage1.v1', status: 'cancelled', runtime_mode: 'fixture' })
  };

  await store.startRun(mockClient, { schema_version: 'stage1.v1' });
  await store.cancelRun(mockClient);
  assert.equal(store.pollTimer, null);
  assert.equal(store.get().runSnapshot.status, 'cancelled');
});
