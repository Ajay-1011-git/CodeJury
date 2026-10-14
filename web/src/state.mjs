/**
 * CodeJury Reactive State Store & Run Lifecycle Controller
 */

export const TERMINAL_STATUSES = Object.freeze([
  'supported_patch',
  'unresolved',
  'invalid_input',
  'infrastructure_error',
  'cancelled'
]);

export class AppState {
  constructor() {
    this.listeners = new Set();
    this.seenEventIds = new Set();
    this.pollTimer = null;
    this.state = {
      health: null,
      runtimeMode: 'unknown',
      activeApiUrl: '',
      currentRunId: null,
      generationToken: 0,
      runSnapshot: null,
      events: [],
      nextAfter: 0,
      trainingReport: null,
      isSubmitting: false,
      errorNotice: null,
      stage: 1
    };
  }

  subscribe(listener) {
    this.listeners.add(listener);
    // Initial emit
    listener(this.state);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }

  set(updates) {
    this.state = { ...this.state, ...updates };
    this.notify();
  }

  get() {
    return this.state;
  }

  stopPolling() {
    if (this.pollTimer) {
      clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
  }

  async startRun(apiClient, runCreatePayload) {
    if (this.state.isSubmitting) {
      throw new Error('Run submission already in progress. Duplicate submit prevented.');
    }

    this.stopPolling();
    const token = this.state.generationToken + 1;
    this.seenEventIds.clear();

    this.set({
      isSubmitting: true,
      errorNotice: null,
      currentRunId: null,
      generationToken: token,
      runSnapshot: null,
      events: [],
      nextAfter: 0
    });

    try {
      const accepted = await apiClient.createRun(runCreatePayload);
      if (this.state.generationToken !== token) {
        // Obsolete run response
        return;
      }

      this.set({
        currentRunId: accepted.run_id,
        isSubmitting: false,
        runtimeMode: accepted.runtime_mode
      });

      // Begin polling immediately
      await this.pollLifecycle(apiClient, accepted.run_id, token);
    } catch (err) {
      if (this.state.generationToken === token) {
        this.set({
          isSubmitting: false,
          errorNotice: {
            status: err.status || 0,
            code: err.code || 'ERROR',
            message: err.message,
            fieldErrors: err.fieldErrors || []
          }
        });
      }
      throw err;
    }
  }

  async pollLifecycle(apiClient, runId, token) {
    if (this.state.generationToken !== token) return;

    try {
      // Parallel snapshot and events poll
      const [snap, page] = await Promise.all([
        apiClient.getRun(runId),
        apiClient.getEvents(runId, this.state.nextAfter)
      ]);

      if (this.state.generationToken !== token) return;

      // Deduplicate and order events
      const newEvents = [];
      for (const ev of (page.events || [])) {
        if (!this.seenEventIds.has(ev.event_id)) {
          this.seenEventIds.add(ev.event_id);
          newEvents.push(ev);
        }
      }

      const mergedEvents = [...this.state.events, ...newEvents].sort((a, b) => a.event_id - b.event_id);
      const nextAfter = page.next_after !== undefined ? page.next_after : this.state.nextAfter;

      this.set({
        runSnapshot: snap,
        events: mergedEvents,
        nextAfter: nextAfter,
        runtimeMode: snap.runtime_mode
      });

      // Terminal check
      if (TERMINAL_STATUSES.includes(snap.status)) {
        this.stopPolling();
        // Fetch report if terminal
        try {
          const report = await apiClient.getReport(runId);
          if (this.state.generationToken === token) {
            this.set({ runSnapshot: report });
          }
        } catch (repErr) {
          console.warn('Terminal report fetch notice:', repErr.message);
        }
        return;
      }

      // Schedule next poll at 1,000ms
      this.stopPolling();
      this.pollTimer = setTimeout(() => {
        this.pollLifecycle(apiClient, runId, token);
      }, 1000);
    } catch (pollErr) {
      if (this.state.generationToken !== token) return;
      console.warn('Polling error:', pollErr.message);
      // Re-schedule poll to withstand intermittent blips unless cancelled
      this.stopPolling();
      this.pollTimer = setTimeout(() => {
        this.pollLifecycle(apiClient, runId, token);
      }, 1000);
    }
  }

  async cancelRun(apiClient) {
    const runId = this.state.currentRunId;
    if (!runId) return;

    this.stopPolling();
    try {
      const snap = await apiClient.cancelRun(runId);
      this.set({
        runSnapshot: snap,
        runtimeMode: snap.runtime_mode
      });
    } catch (err) {
      this.set({
        errorNotice: {
          status: err.status || 0,
          code: err.code || 'CANCEL_ERROR',
          message: err.message
        }
      });
    }
  }
}

export const globalStore = new AppState();
