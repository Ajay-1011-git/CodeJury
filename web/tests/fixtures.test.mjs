import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../..');
const manifestPath = path.join(rootDir, 'web/fixtures/fixture-manifest.json');

test('Fixture manifest and all 16 fixtures exist and parse cleanly', () => {
  assert.ok(fs.existsSync(manifestPath), 'Manifest must exist');
  const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  const entries = Object.entries(manifest);
  assert.equal(entries.length, 16, 'Expected 16 fixtures in manifest');

  for (const [relPath, defName] of entries) {
    const fullPath = path.join(rootDir, relPath);
    assert.ok(fs.existsSync(fullPath), `Fixture file must exist: ${relPath}`);
    const content = fs.readFileSync(fullPath, 'utf8');
    const data = JSON.parse(content);
    assert.ok(data !== null && typeof data === 'object', `Fixture ${relPath} must be a JSON object`);
    const typesWithSchemaVersion = ['RunCreate', 'RunAccepted', 'RunSnapshot', 'Event', 'EventPage', 'Error', 'Health', 'Examples', 'TrainingReport'];
    if (typesWithSchemaVersion.includes(defName)) {
      assert.equal(data.schema_version, 'stage1.v1', `Fixture ${relPath} must have schema_version 'stage1.v1'`);
    }
  }
});

test('Candidate fixture has accurate SHA-256 of UTF-8 source bytes', () => {
  const candPath = path.join(rootDir, 'web/fixtures/candidate.json');
  const cand = JSON.parse(fs.readFileSync(candPath, 'utf8'));
  const actualSha = crypto.createHash('sha256').update(cand.source, 'utf8').digest('hex');
  assert.equal(cand.source_sha256, actualSha, 'Candidate source_sha256 must match byte hash');
});

test('Run snapshot fixtures validate terminal rules', () => {
  const supported = JSON.parse(fs.readFileSync(path.join(rootDir, 'web/fixtures/run-snapshot-supported.json'), 'utf8'));
  assert.equal(supported.status, 'supported_patch');
  assert.ok(supported.decision !== null, 'Supported patch requires decision');
  assert.equal(supported.decision.selected_candidate_id, 'cand-001');

  const unresolved = JSON.parse(fs.readFileSync(path.join(rootDir, 'web/fixtures/run-snapshot-unresolved.json'), 'utf8'));
  assert.equal(unresolved.status, 'unresolved');
  assert.equal(unresolved.decision.selected_candidate_id, null, 'Unresolved must have null selected_candidate_id');
});

test('Training report fixtures reflect factual status', () => {
  const notStarted = JSON.parse(fs.readFileSync(path.join(rootDir, 'web/fixtures/training-report-not-started.json'), 'utf8'));
  assert.equal(notStarted.status, 'not_started');
  assert.equal(notStarted.steps, 0);

  const completed = JSON.parse(fs.readFileSync(path.join(rootDir, 'web/fixtures/training-report-completed.json'), 'utf8'));
  assert.equal(completed.status, 'completed');
  assert.ok(completed.steps > 0);
  assert.ok(completed.loss_points.length > 0);
});
