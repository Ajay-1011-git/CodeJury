/**
 * CodeJury Typed API Seam Client (stage1.v1)
 * Strictly conforms to contracts/stage1-api.schema.json
 */

export class ApiError extends Error {
  constructor(message, status, code, fieldErrors = []) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.fieldErrors = fieldErrors;
  }
}

export function resolveApiBase(searchStr = null, loc = null) {
  const search = searchStr !== null ? searchStr : (typeof window !== 'undefined' ? window.location.search : '');
  const locationObj = loc !== null ? loc : (typeof window !== 'undefined' ? window.location : { port: '8080', origin: 'http://127.0.0.1:8080' });

  const urlParams = new URLSearchParams(search);
  const override = urlParams.get('api');
  if (override) {
    try {
      const parsed = new URL(override);
      // Strict localhost-only requirement
      const allowedHosts = ['localhost', '127.0.0.1'];
      if (allowedHosts.includes(parsed.hostname)) {
        return parsed.origin;
      }
      console.warn(`Rejected non-localhost api override: ${parsed.hostname}`);
    } catch {
      console.warn(`Malformed api override URL: ${override}`);
    }
  }

  // Same-origin default, unless running on dedicated UI dev port 8080
  if (locationObj.port === '8080') {
    return 'http://127.0.0.1:8001';
  }
  return locationObj.origin || 'http://127.0.0.1:8001';
}

export class ApiClient {
  constructor(baseUrl = null, fetchFn = null) {
    this.baseUrl = baseUrl || (typeof window !== 'undefined' ? resolveApiBase() : 'http://127.0.0.1:8001');
    this.fetch = fetchFn || (typeof window !== 'undefined' ? window.fetch.bind(window) : globalThis.fetch);
  }

  async getHealth() {
    const data = await this._request('/health');
    this._guardSchemaVersion(data, 'Health');
    return data;
  }

  async getExamples() {
    const data = await this._request('/examples');
    this._guardSchemaVersion(data, 'Examples');
    return data;
  }

  async createRun(payload) {
    if (!payload || payload.schema_version !== 'stage1.v1') {
      throw new ApiError("RunCreate payload must have schema_version 'stage1.v1'", 400, 'CLIENT_VALIDATION_ERROR');
    }
    const data = await this._request('/runs', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    this._guardSchemaVersion(data, 'RunAccepted');
    return data;
  }

  async getRun(runId) {
    const data = await this._request(`/runs/${encodeURIComponent(runId)}`);
    this._guardSchemaVersion(data, 'RunSnapshot');
    return data;
  }

  async getEvents(runId, after = 0) {
    const data = await this._request(`/runs/${encodeURIComponent(runId)}/events?after=${encodeURIComponent(after)}`);
    this._guardSchemaVersion(data, 'EventPage');
    return data;
  }

  async getCandidate(runId, candidateId) {
    const data = await this._request(`/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}`);
    return data;
  }

  async cancelRun(runId) {
    const data = await this._request(`/runs/${encodeURIComponent(runId)}/cancel`, {
      method: 'POST',
      body: '{}'
    });
    this._guardSchemaVersion(data, 'RunSnapshot');
    return data;
  }

  async getReport(runId) {
    const data = await this._request(`/runs/${encodeURIComponent(runId)}/report`);
    this._guardSchemaVersion(data, 'RunSnapshot');
    return data;
  }

  async getTrainingReport() {
    const data = await this._request('/stage1/training-report');
    this._guardSchemaVersion(data, 'TrainingReport');
    return data;
  }

  _guardSchemaVersion(data, endpointName) {
    if (data && typeof data === 'object' && 'schema_version' in data) {
      if (data.schema_version !== 'stage1.v1') {
        throw new ApiError(
          `Schema version mismatch in ${endpointName}: expected 'stage1.v1', got '${data.schema_version}'`,
          500,
          'SCHEMA_VERSION_MISMATCH'
        );
      }
    }
  }

  async _request(path, options = {}) {
    const url = `${this.baseUrl}${path}`;
    const headers = {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };

    let res;
    try {
      res = await this.fetch(url, {
        ...options,
        headers
      });
    } catch (netErr) {
      throw new ApiError(`Network connection failed to ${this.baseUrl}: ${netErr.message}`, 0, 'NETWORK_ERROR');
    }

    let parsedBody = null;
    const text = await res.text().catch(() => '');
    if (text) {
      try {
        parsedBody = JSON.parse(text);
      } catch {
        parsedBody = null;
      }
    }

    if (!res.ok) {
      const errInfo = parsedBody?.error || {};
      const code = errInfo.code || `HTTP_${res.status}`;
      const msg = errInfo.message || `Request failed with status ${res.status}`;
      const fieldErrors = errInfo.field_errors || [];
      throw new ApiError(msg, res.status, code, fieldErrors);
    }

    return parsedBody;
  }
}
