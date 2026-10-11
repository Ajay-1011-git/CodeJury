/**
 * CodeJury API Seam Client (stage1.v1)
 * Adheres strictly to contracts/stage1-api.schema.json
 */

export function resolveApiBase() {
  const urlParams = new URLSearchParams(window.location.search);
  const override = urlParams.get('api');
  if (override) {
    try {
      const parsed = new URL(override);
      // Strictly enforce localhost URLs
      if (['localhost', '127.0.0.1'].includes(parsed.hostname)) {
        return parsed.origin;
      }
    } catch {
      console.warn('Invalid api override URL, falling back to default');
    }
  }
  // Default to mock server on port 8001 during standalone dev, or same-origin if not on port 8080
  if (window.location.port === '8080') {
    return 'http://127.0.0.1:8001';
  }
  return window.location.origin;
}

export class ApiClient {
  constructor(baseUrl = resolveApiBase()) {
    this.baseUrl = baseUrl;
  }

  async getHealth() {
    return this._fetch('/health');
  }

  async getExamples() {
    return this._fetch('/examples');
  }

  async createRun(payload) {
    return this._fetch('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  }

  async getRun(runId) {
    return this._fetch(`/runs/${encodeURIComponent(runId)}`);
  }

  async getEvents(runId, after = 0) {
    return this._fetch(`/runs/${encodeURIComponent(runId)}/events?after=${after}`);
  }

  async getCandidate(runId, candidateId) {
    return this._fetch(`/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(candidateId)}`);
  }

  async cancelRun(runId) {
    return this._fetch(`/runs/${encodeURIComponent(runId)}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    });
  }

  async getReport(runId) {
    return this._fetch(`/runs/${encodeURIComponent(runId)}/report`);
  }

  async getTrainingReport() {
    return this._fetch('/stage1/training-report');
  }

  async _fetch(path, options = {}) {
    const url = `${this.baseUrl}${path}`;
    const res = await fetch(url, {
      ...options,
      headers: {
        'Accept': 'application/json',
        ...(options.headers || {})
      }
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const err = new Error(data?.error?.message || `HTTP ${res.status}`);
      err.status = res.status;
      err.body = data;
      throw err;
    }
    return data;
  }
}
