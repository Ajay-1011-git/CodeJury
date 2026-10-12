import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

const dir = new URL('../src/s2/', import.meta.url);

test('no HTML injection or dynamic code paths exist in the stage 2 UI', () => {
  const banned = [/\.innerHTML/, /outerHTML/, /insertAdjacentHTML/, /document\.write/, /\beval\s*\(/, /new Function/, /setTimeout\(\s*['"`]/];
  for (const file of readdirSync(dir)) {
    const text = readFileSync(new URL(file, dir), 'utf8');
    for (const re of banned) assert.doesNotMatch(text, re, `${file} matches ${re}`);
  }
});

test('the page ships no inline script and loads only its module', () => {
  const html = readFileSync(new URL('../stage2.html', import.meta.url), 'utf8');
  assert.doesNotMatch(html, /<script(?![^>]*src=)[^>]*>/);
  assert.match(html, /type="module" src="src\/s2\/app\.mjs"/);
  assert.match(html, /id="fixture-banner"/);
});

test('stage 1 UI files are untouched copies of the original contract (still stage1.v1)', () => {
  assert.match(readFileSync(new URL('../src/api.mjs', import.meta.url), 'utf8'), /stage1\.v1/);
});
