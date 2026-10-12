import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient, ApiError, resolveApiBase } from '../src/api.mjs';

function mockFetch(status, body, isJson = true) {
  return async (url, options) => {
    return {
      ok: status >= 200 && status < 300,
      status: status,
      text: async () => isJson ? (typeof body === 'string' ? body : JSON.stringify(body)) : body
    };
  };
}

test('resolveApiBase respects strict localhost constraints', () => {
  // Localhost override allowed
  const urlLocal = resolveApiBase('?api=http://localhost:8000', { port: '8080' });
  assert.equal(urlLocal, 'http://localhost:8000');

  const url127 = resolveApiBase('?api=http://127.0.0.1:8002', { port: '8080' });
  assert.equal(url127, 'http://127.0.0.1:8002');

  // External / cloud override rejected
  const urlEvil = resolveApiBase('?api=https://evil.cloud.com/api', { port: '8080', origin: 'http://127.0.0.1:8080' });
  assert.equal(urlEvil, 'http://127.0.0.1:8080');

  // Every port defaults to same-origin; mock mode requires an explicit override.
  const default8080 = resolveApiBase('', { port: '8080', origin: 'http://127.0.0.1:8080' });
  assert.equal(default8080, 'http://127.0.0.1:8080');
  assert.equal(resolveApiBase('?api=ftp://localhost:8001', { origin: 'http://127.0.0.1:8000' }), 'http://127.0.0.1:8000');
  assert.equal(resolveApiBase('?api=http://localhost:8001', { origin: 'http://127.0.0.1:8000' }), 'http://localhost:8001');

  // Production same-origin default
  const prodOrigin = resolveApiBase('', { port: '8000', origin: 'http://127.0.0.1:8000' });
  assert.equal(prodOrigin, 'http://127.0.0.1:8000');
});

test('ApiClient routes execute successfully with exact methods', async () => {
  const recorded = [];
  const fakeFetch = async (url, opts) => {
    recorded.push({ url, method: opts?.method || 'GET' });
    if (url.endsWith('/health')) {
      return { ok: true, status: 200, text: async () => JSON.stringify({ schema_version: 'stage1.v1', service: 'codejury-stage1', runtime_mode: 'fixture', model_ready: true, sandbox_ready: true, fixer_a_trained: false, stage2_enabled: false }) };
    }
    if (url.endsWith('/examples')) {
      return { ok: true, status: 200, text: async () => JSON.stringify({ schema_version: 'stage1.v1', examples: [] }) };
    }
    if (url.endsWith('/runs')) {
      return { ok: true, status: 202, text: async () => JSON.stringify({ schema_version: 'stage1.v1', run_id: 'run-test-1', status: 'queued', runtime_mode: 'fixture' }) };
    }
    if (url.includes('/events')) {
      return { ok: true, status: 200, text: async () => JSON.stringify({ schema_version: 'stage1.v1', run_id: 'run-test-1', events: [], next_after: 0 }) };
    }
    if (url.endsWith('/cancel')) {
      return { ok: true, status: 200, text: async () => JSON.stringify({ schema_version: 'stage1.v1', run_id: 'run-test-1', status: 'cancelled' }) };
    }
    return { ok: true, status: 200, text: async () => JSON.stringify({ schema_version: 'stage1.v1' }) };
  };

  const client = new ApiClient('http://127.0.0.1:8001', fakeFetch);
  await client.getHealth();
  await client.getExamples();
  await client.createRun({ schema_version: 'stage1.v1', dummy: true });
  await client.getEvents('run-test-1', 0);
  await client.cancelRun('run-test-1');

  assert.equal(recorded[0].method, 'GET');
  assert.equal(recorded[1].method, 'GET');
  assert.equal(recorded[2].method, 'POST');
  assert.equal(recorded[3].method, 'GET');
  assert.equal(recorded[4].method, 'POST');
});

test('ApiClient throws on wrong schema_version', async () => {
  const client = new ApiClient('http://127.0.0.1:8001', mockFetch(200, { schema_version: 'wrong.v2' }));
  await assert.rejects(
    async () => await client.getHealth(),
    (err) => {
      assert.equal(err.code, 'SCHEMA_VERSION_MISMATCH');
      return true;
    }
  );
});

test('ApiClient handles typed Error envelopes: 404, 409, 422, 503', async () => {
  const err404 = { schema_version: 'stage1.v1', error: { code: 'RUN_NOT_FOUND', message: 'Run not found', field_errors: [] } };
  const client404 = new ApiClient('http://127.0.0.1:8001', mockFetch(404, err404));
  await assert.rejects(
    async () => await client404.getRun('run-missing'),
    (err) => {
      assert.equal(err.status, 404);
      assert.equal(err.code, 'RUN_NOT_FOUND');
      return true;
    }
  );

  const err409 = { schema_version: 'stage1.v1', error: { code: 'RUN_SLOT_BUSY', message: 'Active run slot busy', field_errors: [] } };
  const client409 = new ApiClient('http://127.0.0.1:8001', mockFetch(409, err409));
  await assert.rejects(
    async () => await client409.createRun({ schema_version: 'stage1.v1' }),
    (err) => {
      assert.equal(err.status, 409);
      assert.equal(err.code, 'RUN_SLOT_BUSY');
      return true;
    }
  );

  const err503 = { schema_version: 'stage1.v1', error: { code: 'SERVICE_UNAVAILABLE', message: 'Inference backend unavailable', field_errors: [] } };
  const client503 = new ApiClient('http://127.0.0.1:8001', mockFetch(503, err503));
  await assert.rejects(
    async () => await client503.getHealth(),
    (err) => {
      assert.equal(err.status, 503);
      assert.equal(err.code, 'SERVICE_UNAVAILABLE');
      return true;
    }
  );
});

test('ApiClient handles inaccessible backend network failures', async () => {
  const netFailFetch = async () => {
    throw new TypeError('fetch failed');
  };
  const client = new ApiClient('http://127.0.0.1:8001', netFailFetch);
  await assert.rejects(
    async () => await client.getHealth(),
    (err) => {
      assert.equal(err.code, 'NETWORK_ERROR');
      return true;
    }
  );
});
