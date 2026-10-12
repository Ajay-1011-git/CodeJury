import test from 'node:test';
import assert from 'node:assert/strict';
import { ApiClient, ApiError, CONTRACT_HASH, checkHealth, describeError, resolveApiBase } from '../src/s2/api.mjs';
import { readFileSync } from 'node:fs';

const fx = (n) => JSON.parse(readFileSync(new URL(`../../contracts/stage2-fixtures/${n}.json`, import.meta.url)));
const respond = (status, body) => async () => ({ ok: status < 400, status, text: async () => JSON.stringify(body) });

test('api override is localhost-only and same-origin is the default', () => {
  const loc = { origin: 'http://127.0.0.1:8080' };
  assert.equal(resolveApiBase('?api=http://localhost:8001', loc), 'http://localhost:8001');
  assert.equal(resolveApiBase('?api=https://evil.example', loc), loc.origin);
  assert.equal(resolveApiBase('?api=http://user:pw@localhost:1', loc), loc.origin);
  assert.equal(resolveApiBase('', loc), loc.origin);
});

test('health guard requires version, service and the frozen contract hash', () => {
  assert.equal(checkHealth(fx('health')).ok, true);
  assert.equal(CONTRACT_HASH, fx('health').contract_hash);
  assert.equal(checkHealth({ ...fx('health'), contract_hash: '0'.repeat(64) }).ok, false);
  assert.equal(checkHealth({ ...fx('health'), schema_version: 'stage1.v1' }).ok, false);
  assert.equal(checkHealth({ ...fx('health'), service: 'other' }).ok, false);
});

test('responses of another schema version are rejected, errors keep their envelope', async () => {
  const stage1 = new ApiClient('http://x', respond(200, { schema_version: 'stage1.v1' }));
  await assert.rejects(stage1.getHealth(), (e) => e.code === 'schema_version_mismatch');
  const c = new ApiClient('http://x', respond(409, fx('error-version')));
  await assert.rejects(c.getRun('r'), (e) => e instanceof ApiError && e.status === 409 && e.fieldErrors[0] === 'schema_version');
  assert.match(describeError(new ApiError('m', 422, 'c', ['f'])), /Request rejected by the contract: m \(f\)/);
  assert.match(describeError(new ApiError('m', 503, 'c')), /unavailable/);
  assert.match(describeError(new ApiError('m', 404, 'c')), /Unknown run/);
  assert.match(describeError(new ApiError('m', 409, 'c')), /Busy/);
});

test('network failures become status 0 and cursors are validated', async () => {
  const c = new ApiClient('http://x', async () => { throw new Error('refused'); });
  await assert.rejects(c.getHealth(), (e) => e.status === 0 && e.code === 'network_error');
  const ok = new ApiClient('http://x', respond(200, fx('events')));
  await assert.rejects(async () => ok.getEvents('r', -1), (e) => e.code === 'bad_cursor');
  await assert.rejects(async () => ok.getEvents('r', 1.5), (e) => e.code === 'bad_cursor');
  assert.equal((await ok.getEvents('r', 0)).events.length, 12);
});

test('createRun refuses payloads of the wrong version before any request', async () => {
  let called = false;
  const c = new ApiClient('http://x', async () => { called = true; });
  assert.throws(() => c.createRun({ schema_version: 'stage1.v1' }), (e) => e.status === 422);
  assert.equal(called, false);
});

test('routes are exactly the contract table', async () => {
  const seen = [];
  const c = new ApiClient('http://x', async (url, o) => { seen.push(`${o.method || 'GET'} ${url.replace('http://x', '')}`); return { ok: true, status: 200, text: async () => JSON.stringify({ schema_version: 'stage2.v1' }) }; });
  await c.getHealth(); await c.getExamples(); await c.createRun({ schema_version: 'stage2.v1' });
  await c.getRun('a b'); await c.getEvents('r', 7); await c.getCandidate('r', 'c1'); await c.cancelRun('r'); await c.getReport('r');
  await c.getTrainingReport(); await c.getBenchmarkReport();
  assert.deepEqual(seen, ['GET /health', 'GET /examples', 'POST /runs', 'GET /runs/a%20b', 'GET /runs/r/events?after=7',
    'GET /runs/r/candidates/c1', 'POST /runs/r/cancel', 'GET /runs/r/report', 'GET /stage2/training-report', 'GET /stage2/benchmark-report']);
});
