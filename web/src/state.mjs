/**
 * Reactive Application State Store
 */

export class AppState {
  constructor() {
    this.listeners = new Set();
    this.state = {
      health: null,
      runtimeMode: 'fixture',
      currentRunId: null,
      runSnapshot: null,
      events: [],
      nextAfter: 0,
      trainingReport: null,
      isSubmitting: false,
      errorNotice: null
    };
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  set(updates) {
    this.state = { ...this.state, ...updates };
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }

  get() {
    return this.state;
  }
}

export const globalStore = new AppState();
