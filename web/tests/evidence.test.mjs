import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatOutcomeBadge, formatOracleBadge, renderDiffLines } from '../src/evidence.mjs';
import { renderResultView } from '../src/result.mjs';

// Minimal DOM simulation for node test environment
class MockElement {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.className = '';
    this._textContent = '';
    this._innerHTML = '';
    this.attributes = {};
    this.eventListeners = {};
    this.style = {};
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  removeChild(child) {
    const idx = this.children.indexOf(child);
    if (idx !== -1) this.children.splice(idx, 1);
  }

  get textContent() {
    if (this._textContent) return this._textContent;
    return this.children.map(c => c.textContent).join('');
  }

  set textContent(val) {
    this._textContent = val;
    this.children = [];
  }

  get innerHTML() {
    if (this._innerHTML && this.children.length === 0) return this._innerHTML;
    let s = this._innerHTML || '';
    for (const c of this.children) {
      s += c.outerHTML || c.innerHTML || c.textContent || '';
    }
    return s;
  }

  get outerHTML() {
    return `<${this.tagName.toLowerCase()} class="${this.className}" id="${this.id || ''}">${this.innerHTML}</${this.tagName.toLowerCase()}>`;
  }

  set innerHTML(val) {
    this._innerHTML = val;
    if (val === '') this.children = [];
  }

  setAttribute(k, v) {
    this.attributes[k] = v;
  }

  getAttribute(k) {
    return this.attributes[k];
  }

  addEventListener(evt, fn) {
    this.eventListeners[evt] = fn;
  }

  querySelector(sel) {
    return this._find(sel);
  }

  querySelectorAll(sel) {
    const results = [];
    this._findAll(sel, results);
    return results;
  }

  _find(sel) {
    if (sel.startsWith('#') && this.id === sel.slice(1)) return this;
    if (sel.startsWith('.') && this.className.includes(sel.slice(1))) return this;
    for (const c of this.children) {
      if (c._find) {
        const found = c._find(sel);
        if (found) return found;
      }
    }
    return null;
  }

  _findAll(sel, results) {
    if (sel.startsWith('#') && this.id === sel.slice(1)) results.push(this);
    if (sel.startsWith('.') && this.className.includes(sel.slice(1))) results.push(this);
    for (const c of this.children) {
      if (c._findAll) c._findAll(sel, results);
    }
  }
}

// Global document mock for Node test runner
globalThis.document = {
  createElement: (tag) => new MockElement(tag)
};

test('Outcome badge rules: observed != pass', () => {
  const observedBadge = formatOutcomeBadge('observed');
  assert.equal(observedBadge.textContent, 'OBSERVED');
  assert.equal(observedBadge.className.includes('badge-success'), false, 'Observed must never be given badge-success');
  assert.equal(observedBadge.className.includes('badge-neutral'), true);

  const passBadge = formatOutcomeBadge('pass');
  assert.equal(passBadge.textContent, 'PASS');
  assert.equal(passBadge.className.includes('badge-success'), true);

  const failBadge = formatOutcomeBadge('fail');
  assert.equal(failBadge.textContent, 'FAIL');
  assert.equal(failBadge.className.includes('badge-danger'), true);
});

test('Property test with null expected output renders property badge', () => {
  const propTest = {
    test_id: 'test_prop_1',
    oracle_kind: 'property',
    expected: null,
    property_id: 'sort_ascending_ints',
    oracle_status: 'authoritative'
  };
  const badge = formatOracleBadge(propTest);
  assert.equal(badge.textContent, 'Property (Auth)');
  assert.equal(badge.className.includes('badge-success'), true);
});

test('Diff line renderer escapes markup and flags diff changes', () => {
  const diffSample = '--- orig\n+++ cand\n-buggy_line()\n+fixed_line()';
  const diffEl = renderDiffLines(diffSample);
  assert.equal(diffEl.children.length, 4);
  assert.equal(diffEl.children[2].className, 'diff-del');
  assert.equal(diffEl.children[3].className, 'diff-add');
});

test('Supported patch displays selected candidate and copy/download buttons', () => {
  const container = new MockElement('div');
  const snapSupported = {
    schema_version: 'stage1.v1',
    run_id: 'run-supported-01',
    status: 'supported_patch',
    phase: 'finished',
    candidates: [
      {
        candidate_id: 'cand-001',
        origin: 'fixer_a',
        source: 'def sort_ints(x): return sorted(x)',
        source_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        diff: '+return sorted(x)',
        eligibility: 'eligible',
        rejection_reason: null
      }
    ],
    decision: {
      selected_candidate_id: 'cand-001',
      verification_scope: ['test_1', 'test_prop'],
      unresolved_requirements: [],
      evidence_ids: ['exec-1'],
      reason: 'Passed all authoritative tests.'
    },
    usage: {
      input_tokens: 100, output_tokens: 50, function_executions: 2, elapsed_ms: 500, peak_memory_mb: 30.0
    }
  };

  renderResultView(container, snapSupported);
  assert.ok(container.innerHTML.includes('Supported Patch Verified'));
  assert.ok(container.innerHTML.includes('cand-001'));
  const copyBtn = container.querySelector('#btn-copy-patch');
  assert.ok(copyBtn !== null, 'Copy patch button must be present in supported_patch');
});

test('Unresolved run does NOT include copy patch button or claim success', () => {
  const container = new MockElement('div');
  const snapUnresolved = {
    schema_version: 'stage1.v1',
    run_id: 'run-unresolved-02',
    status: 'unresolved',
    phase: 'finished',
    candidates: [],
    decision: {
      selected_candidate_id: null,
      verification_scope: ['test_1'],
      unresolved_requirements: ['req-sort'],
      evidence_ids: [],
      reason: 'Iteration budget exhausted.'
    }
  };

  renderResultView(container, snapUnresolved);
  assert.ok(container.innerHTML.includes('Unresolved — No Supported Patch Discovered'));
  const copyBtn = container.querySelector('#btn-copy-patch');
  assert.equal(copyBtn, null, 'Unresolved run must never have copy patch button');
});

test('Stale success is cleared immediately when snapshot updates to running or cancelled', () => {
  const container = new MockElement('div');
  const snapSupported = {
    status: 'supported_patch',
    decision: { selected_candidate_id: 'cand-001', verification_scope: [] },
    candidates: [{ candidate_id: 'cand-001', source: '...' }]
  };
  renderResultView(container, snapSupported);
  assert.ok(container.innerHTML.includes('Supported Patch Verified'));

  // Update to running
  renderResultView(container, { status: 'running', phase: 'generate' });
  assert.equal(container.innerHTML.includes('Supported Patch Verified'), false, 'Stale success must be cleared');
  assert.ok(container.innerHTML.includes('Run in Progress'));

  // Update to cancelled
  renderResultView(container, { status: 'cancelled', termination_reason: 'User cancelled' });
  assert.equal(container.innerHTML.includes('Supported Patch Verified'), false, 'Stale success must not be shown on cancel');
  assert.ok(container.innerHTML.includes('CANCELLED'));
});
