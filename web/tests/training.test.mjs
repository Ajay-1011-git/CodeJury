import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { validateEvaluationData, generateLossSvg, renderTrainingReport } from '../src/training.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// DOM Mock Element for testing
class MockElement {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.className = '';
    this._textContent = '';
    this._innerHTML = '';
  }
  appendChild(child) {
    this.children.push(child);
    return child;
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
    return `<${this.tagName.toLowerCase()} class="${this.className}">${this.innerHTML}</${this.tagName.toLowerCase()}>`;
  }
  set innerHTML(val) {
    this._innerHTML = val;
    if (val === '') this.children = [];
  }
}

globalThis.document = {
  createElement: (tag) => new MockElement(tag)
};

test('Zero / empty report displays unmeasured state without fabricated curves', () => {
  const container = new MockElement('div');
  const emptyReport = {
    schema_version: 'stage1.v1',
    runtime_mode: 'fixture',
    status: 'not_started',
    model_id: null,
    model_revision: null,
    adapter_sha256: null,
    train_base_problems: 0,
    validation_base_problems: 0,
    evaluation_base_problems: 0,
    train_records: 0,
    steps: 0,
    loss_points: [],
    evaluation: [],
    provenance_note: 'Awaiting training runs.'
  };

  renderTrainingReport(container, emptyReport);
  assert.ok(container.innerHTML.includes('Not Yet Measured'));
  assert.equal(container.innerHTML.includes('<svg'), false, 'Empty report must not fabricate SVG loss curves');
});

test('Real-shape nonempty loss points and evaluation rows render correctly', () => {
  const container = new MockElement('div');
  const completedReport = {
    schema_version: 'stage1.v1',
    runtime_mode: 'fixture',
    status: 'completed',
    model_id: 'qwen2.5-coder-7b-instruct',
    model_revision: 'v1.0',
    adapter_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    train_base_problems: 140,
    validation_base_problems: 30,
    evaluation_base_problems: 50,
    train_records: 420,
    steps: 300,
    loss_points: [
      { step: 0, train_loss: 2.5, validation_loss: 2.6 },
      { step: 100, train_loss: 1.2, validation_loss: 1.4 },
      { step: 200, train_loss: 0.6, validation_loss: 0.9 }
    ],
    evaluation: [
      {
        method: 'raw_single',
        total: 50,
        solved: 14,
        unresolved: 36,
        incorrect_accepted: 0,
        mean_elapsed_ms: 1100,
        mean_output_tokens: 180
      },
      {
        method: 'stage1_loop',
        total: 50,
        solved: 39,
        unresolved: 11,
        incorrect_accepted: 0,
        mean_elapsed_ms: 3400,
        mean_output_tokens: 580
      }
    ],
    provenance_note: 'Genuine evaluation results.'
  };

  renderTrainingReport(container, completedReport);
  assert.ok(container.innerHTML.includes('COMPLETED'));
  assert.ok(container.innerHTML.includes('<svg'));
  assert.ok(container.innerHTML.includes('Raw Model (Single-Shot)'));
  assert.ok(container.innerHTML.includes('Stage 1 Loop (Fixer A + Oracles)'));
  assert.ok(container.innerHTML.includes('78.0%')); // 39/50
});

test('Null metrics and empty memory are preserved as dashes and not converted to 0', () => {
  const container = new MockElement('div');
  const reportWithNulls = {
    schema_version: 'stage1.v1',
    runtime_mode: 'live',
    status: 'completed',
    model_id: 'model-a',
    model_revision: null,
    adapter_sha256: null,
    train_base_problems: 10,
    validation_base_problems: 5,
    evaluation_base_problems: 10,
    train_records: 20,
    steps: 50,
    loss_points: [{ step: 0, train_loss: null, validation_loss: null }],
    evaluation: [
      {
        method: 'raw_single',
        total: 10,
        solved: 2,
        unresolved: 8,
        incorrect_accepted: 0,
        mean_elapsed_ms: null, // Null latency
        mean_output_tokens: null // Null tokens
      }
    ],
    provenance_note: 'Pilot run'
  };

  renderTrainingReport(container, reportWithNulls);
  assert.ok(container.innerHTML.includes('—')); // Nulls displayed as dash
  assert.equal(container.innerHTML.includes('0 ms'), false, 'Null elapsed ms must not become 0 ms');
});

test('Evaluation validation rejects bad counters and solved > total', () => {
  // solved > total
  const badSolved = [
    { method: 'raw_single', total: 50, solved: 55, unresolved: 0, incorrect_accepted: 0 }
  ];
  const res1 = validateEvaluationData(badSolved);
  assert.equal(res1.valid, false);
  assert.ok(res1.error.includes('exceeds total'));

  // Negative counter
  const negCounter = [
    { method: 'raw_single', total: 50, solved: -1, unresolved: 51, incorrect_accepted: 0 }
  ];
  const res2 = validateEvaluationData(negCounter);
  assert.equal(res2.valid, false);
  assert.ok(res2.error.includes('cannot be negative'));

  // Partition mismatch
  const mismatch = [
    { method: 'raw_single', total: 50, solved: 20, unresolved: 20, incorrect_accepted: 0 } // sum = 40 != 50
  ];
  const res3 = validateEvaluationData(mismatch);
  assert.equal(res3.valid, false);
  assert.ok(res3.error.includes('partition sum does not equal total'));
});

test('Verify no evaluation metrics or loss points are hardcoded in training.mjs', () => {
  const code = fs.readFileSync(path.join(__dirname, '../src/training.mjs'), 'utf8');
  // Check that the code dynamically references fields from report parameter, not hardcoded numbers
  assert.ok(code.includes('report.loss_points'));
  assert.ok(code.includes('report.evaluation'));
  assert.equal(code.includes('solved: 39'), false);
  assert.equal(code.includes('train_records: 420'), false);
});
