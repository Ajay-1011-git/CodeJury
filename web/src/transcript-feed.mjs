/** Refresh actual stored replies, including one complete terminal transcript. */
export class TranscriptFeed {
  constructor({ base, getRunId, onUpdate, fetchFn = globalThis.fetch.bind(globalThis), intervalMs = 2500 }) {
    Object.assign(this, { base, getRunId, onUpdate, fetchFn, intervalMs });
    this.runId = null;
    this.sequence = 0;
    this.lastAt = 0;
    this.pending = false;
    this.terminalRequested = false;
  }

  async refresh(snapshot, terminal, now = Date.now()) {
    const runId = snapshot.run_id;
    const changed = this.runId !== runId;
    if (changed) {
      this.runId = runId;
      this.sequence += 1;
      this.lastAt = 0;
      this.pending = false;
      this.terminalRequested = false;
    }
    if (terminal ? this.terminalRequested : this.pending || (!changed && now - this.lastAt < this.intervalMs)) return false;
    if (terminal) this.terminalRequested = true;
    const sequence = ++this.sequence;
    this.lastAt = now;
    this.pending = true;
    try {
      const response = await this.fetchFn(`${this.base}/runs/${encodeURIComponent(runId)}/transcript`, { cache: 'no-store' });
      if (!response.ok) throw new Error('Transcript unavailable');
      const body = await response.json();
      if (body.schema_version !== 'stage2.v1' || body.run_id !== runId) throw new Error('Transcript mismatch');
      if (sequence !== this.sequence || this.getRunId() !== runId) return false;
      this.onUpdate(body);
      return true;
    } catch {
      if (sequence === this.sequence && terminal) this.terminalRequested = false;
      return false;
    } finally {
      if (sequence === this.sequence) this.pending = false;
    }
  }
}
