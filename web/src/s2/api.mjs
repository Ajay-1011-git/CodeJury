/** Typed stage2.v1 seam client. Network, schema-version and error handling only; no rendering. */

export const SCHEMA = 'stage2.v1';
export const CONTRACT_HASH = 'ee62388479918f0e33d4085d530dc210356ed104afe6170b1ff03687e53b6ee6';
const LOCAL_HOSTS = ['localhost', '127.0.0.1'];

export class ApiError extends Error {
  constructor(message, status, code, fieldErrors = []) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
  }
}

/** Same-origin by default; an explicit localhost-only ?api= override is allowed. */
export function resolveApiBase(search = '', loc = { origin: 'http://127.0.0.1:8000' }) {
  const override = new URLSearchParams(search).get('api');
  if (override) {
    try {
      const url = new URL(override);
      if (['http:', 'https:'].includes(url.protocol) && LOCAL_HOSTS.includes(url.hostname)
          && !url.username && !url.password) return url.origin;
    } catch { /* fall through to same origin */ }
  }
  return loc.origin;
}

/** Stage 2 UI must not submit unless the backend speaks exactly this contract. */
export function checkHealth(health) {
  const reasons = [];
  if (!health || health.schema_version !== SCHEMA) reasons.push(`backend does not speak ${SCHEMA}`);
  else {
    if (health.service !== 'codejury-stage2') reasons.push('not a CodeJury Stage 2 service');
    if (health.contract_hash !== CONTRACT_HASH) reasons.push('contract hash differs from this UI');
  }
  return { ok: reasons.length === 0, reasons };
}

export function describeError(err) {
  if (!(err instanceof ApiError)) return String(err && err.message ? err.message : err);
  const fields = err.fieldErrors?.length ? ` (${err.fieldErrors.join('; ')})` : '';
  const prefix = {
    409: 'Busy or conflicting state',
    404: 'Unknown run or candidate',
    422: 'Request rejected by the contract',
    503: 'Backend dependency unavailable',
    0: 'Backend unreachable',
  }[err.status] || `Backend error ${err.status}`;
  return `${prefix}: ${err.message}${fields}`;
}

export class ApiClient {
  constructor(baseUrl, fetchFn = globalThis.fetch?.bind(globalThis)) {
    this.baseUrl = baseUrl;
    this.fetch = fetchFn;
  }

  getHealth() { return this.#get('/health', 'Health'); }
  getExamples() { return this.#get('/examples', 'Examples'); }
  createRun(payload) {
    if (!payload || payload.schema_version !== SCHEMA) {
      throw new ApiError(`RunCreate must carry schema_version ${SCHEMA}`, 422, 'schema_version_mismatch', ['schema_version']);
    }
    return this.#request('/runs', { method: 'POST', body: JSON.stringify(payload) }, 'RunAccepted');
  }
  getRun(id) { return this.#get(`/runs/${encodeURIComponent(id)}`, 'RunSnapshot'); }
  getEvents(id, after = 0) {
    if (!Number.isInteger(after) || after < 0) throw new ApiError('cursor must be an integer >= 0', 422, 'bad_cursor', ['after']);
    return this.#get(`/runs/${encodeURIComponent(id)}/events?after=${after}`, 'EventPage');
  }
  getCandidate(runId, candidateId) {
    return this.#get(`/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}`, 'Candidate');
  }
  cancelRun(id) { return this.#request(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST', body: '{}' }, 'RunSnapshot'); }
  getReport(id) { return this.#get(`/runs/${encodeURIComponent(id)}/report`, 'RunSnapshot'); }
  getTrainingReport() { return this.#get('/stage2/training-report', 'TrainingReport'); }
  getBenchmarkReport() { return this.#get('/stage2/benchmark-report', 'BenchmarkReport'); }

  #get(path, name) { return this.#request(path, {}, name); }

  async #request(path, options, name) {
    let res;
    try {
      res = await this.fetch(`${this.baseUrl}${path}`, {
        ...options,
        cache: 'no-store',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
      });
    } catch (netErr) {
      throw new ApiError(`cannot reach ${this.baseUrl}: ${netErr.message}`, 0, 'network_error');
    }
    const text = await res.text().catch(() => '');
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = null; }
    if (!res.ok) {
      const info = body?.error || {};
      throw new ApiError(info.message || `HTTP ${res.status}`, res.status, info.code || `http_${res.status}`, info.field_errors || []);
    }
    if (!body || body.schema_version !== SCHEMA) {
      throw new ApiError(`${name} is not ${SCHEMA}`, 502, 'schema_version_mismatch', ['schema_version']);
    }
    return body;
  }
}
