/** Run lifecycle store: 1 s polling, cursor dedup, stale-response guards, terminal/navigation stop. */

import { TERMINAL, withdrawsSuccess } from './model.mjs';
import { ApiError } from './api.mjs';

export class Store {
  constructor({ setTimer = (f, ms) => setTimeout(f, ms), clearTimer = (t) => clearTimeout(t), intervalMs = 1000 } = {}) {
    this.listeners = new Set();
    this.setTimer = setTimer; this.clearTimer = clearTimer; this.intervalMs = intervalMs;
    this.timer = null; this.seen = new Set();
    this.state = {
      health: null, healthOk: false, healthReasons: [], runtimeMode: 'unknown', runId: null, token: 0,
      snapshot: null, events: [], after: 0, submitting: false, error: null, withdrawn: false,
      training: null, benchmark: null,
    };
  }

  subscribe(fn) { this.listeners.add(fn); fn(this.state); return () => this.listeners.delete(fn); }
  set(patch) { this.state = { ...this.state, ...patch }; for (const l of this.listeners) l(this.state); }
  stopPolling() { if (this.timer) { this.clearTimer(this.timer); this.timer = null; } }
  /** Navigation/unload: nothing may update after this. */
  dispose() { this.stopPolling(); this.set({ token: this.state.token + 1 }); }

  async submit(client, payload) {
    if (this.state.submitting) throw new Error('A submission is already in progress.');
    if (!this.state.healthOk) throw new Error('Backend contract check has not passed.');
    this.stopPolling(); this.seen.clear();
    const token = this.state.token + 1;
    this.set({ submitting: true, error: null, runId: null, token, snapshot: null, events: [], after: 0, withdrawn: false });
    try {
      const accepted = await client.createRun(payload);
      if (this.state.token !== token) return null;
      this.set({ runId: accepted.run_id, submitting: false, runtimeMode: accepted.runtime_mode });
      await this.poll(client, accepted.run_id, token);
      return accepted;
    } catch (err) {
      if (this.state.token === token) this.set({ submitting: false, error: err });
      throw err;
    }
  }

  async poll(client, runId, token) {
    if (this.state.token !== token) return;
    try {
      const [snap, page] = await Promise.all([client.getRun(runId), client.getEvents(runId, this.state.after)]);
      if (this.state.token !== token) return; // a newer run or navigation made this response stale
      const fresh = page.events.filter((e) => !this.seen.has(e.event_id));
      fresh.forEach((e) => this.seen.add(e.event_id));
      const events = [...this.state.events, ...fresh].sort((a, b) => a.event_id - b.event_id);
      const withdrawn = withdrawsSuccess(this.state.snapshot, snap) || this.state.withdrawn;
      this.set({ snapshot: snap, events, after: Math.max(this.state.after, page.next_after), runtimeMode: snap.runtime_mode, withdrawn });
      if (TERMINAL.includes(snap.status)) {
        this.stopPolling();
        try {
          const report = await client.getReport(runId);
          if (this.state.token === token) this.set({ snapshot: report, withdrawn: withdrawsSuccess(this.state.snapshot, report) || this.state.withdrawn });
        } catch (err) { if (this.state.token === token) this.set({ error: err }); }
        return;
      }
    } catch (err) {
      if (this.state.token !== token) return;
      if (err instanceof ApiError && err.status === 404) { this.set({ error: err }); return; }
      this.set({ error: err });
    }
    this.stopPolling();
    this.timer = this.setTimer(() => this.poll(client, runId, token), this.intervalMs);
  }

  async cancel(client) {
    const { runId, token } = this.state;
    if (!runId) return;
    this.stopPolling();
    try {
      const snap = await client.cancelRun(runId);
      if (this.state.token === token) this.set({ snapshot: snap, withdrawn: withdrawsSuccess(this.state.snapshot, snap) || this.state.withdrawn });
    } catch (err) { if (this.state.token === token) this.set({ error: err }); }
  }
}
