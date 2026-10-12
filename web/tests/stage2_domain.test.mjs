import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { JsonError, checkValue, parseJsonV1, typedEqual, validateDomain, validateRunCreate } from '../src/s2/domain.mjs';

const fx = (n) => JSON.parse(readFileSync(new URL(`../../contracts/stage2-fixtures/${n}.json`, import.meta.url)));

test('strict json.v1 parsing keeps nested bool/int/null and rejects non-json.v1', () => {
  assert.deepEqual(parseJsonV1('{"a":[1,true,null,"é😀",{"b":[]}]}'), { a: [1, true, null, 'é😀', { b: [] }] });
  for (const bad of ['1.0', '1e3', '[1,]', '{"a":1,"a":2}', 'NaN', '9007199254740993', '[1] x', '', '{"a"}', '"unterminated']) {
    assert.throws(() => parseJsonV1(bad), JsonError, bad);
  }
  assert.equal(parseJsonV1('9007199254740991'), 9007199254740991);
  assert.throws(() => parseJsonV1('[[[[[[[[[[1]]]]]]]]]]'), JsonError);
});

test('type-sensitive equality separates bool, int and null', () => {
  assert.equal(typedEqual(true, 1), false);
  assert.equal(typedEqual([1, [true]], [1, [1]]), false);
  assert.equal(typedEqual({ a: null }, { a: 0 }), false);
  assert.equal(typedEqual({ a: [1, 'x'] }, { a: [1, 'x'] }), true);
});

const INT = { kind: 'integer', min: -5, max: 5 };
test('domain validation mirrors the backend limits', () => {
  assert.deepEqual(validateDomain(INT), []);
  assert.notDeepEqual(validateDomain({ kind: 'integer', min: 3, max: 1 }), []);
  assert.notDeepEqual(validateDomain({ kind: 'integer', min: 0, max: 1e7 }), []);
  assert.notDeepEqual(validateDomain({ kind: 'string', alphabet: 'aa', min_length: 0, max_length: 1 }), []);
  assert.notDeepEqual(validateDomain({ kind: 'union', options: [INT] }), []);
  assert.notDeepEqual(validateDomain({ kind: 'mystery' }), []);
  let deep = INT;
  for (let i = 0; i < 5; i += 1) deep = { kind: 'list', item_domain: deep, min_length: 0, max_length: 1 };
  assert.ok(validateDomain(deep).some((e) => /nesting/.test(e)));
  const key = { kind: 'string', alphabet: 'ab', min_length: 1, max_length: 1 };
  const dict = { kind: 'dict', key_domain: key, value_domain: INT, min_size: 0, max_size: 2 };
  assert.deepEqual(validateDomain({ ...dict, required_keys: ['a'] }), []);
  assert.notDeepEqual(validateDomain({ ...dict, required_keys: ['z'] }), []);
  assert.notDeepEqual(validateDomain({ ...dict, required_keys: ['a', 'a'] }), []);
});

test('membership: unicode codepoints, bools, dict keys, unions', () => {
  const s = { kind: 'string', alphabet: 'a😀', min_length: 0, max_length: 2 };
  assert.equal(checkValue(s, '😀😀'), null);
  assert.notEqual(checkValue(s, '😀😀a'), null);
  assert.notEqual(checkValue(INT, true), null);
  const key = { kind: 'string', alphabet: 'ab', min_length: 1, max_length: 1 };
  const dict = { kind: 'dict', key_domain: key, value_domain: INT, required_keys: ['a'], min_size: 0, max_size: 2 };
  assert.equal(checkValue(dict, { a: 1, b: 2 }), null);
  assert.match(checkValue(dict, { b: 2 }), /missing required key/);
  const union = { kind: 'union', options: [INT, { kind: 'null' }] };
  assert.equal(checkValue(union, null), null);
  assert.notEqual(checkValue(union, 'x'), null);
});

test('published run-create fixtures pass the client-side intake', () => {
  for (const n of ['run-create', 'run-create-helper', 'run-create-nested', 'run-create-null', 'run-create-string']) {
    assert.deepEqual(validateRunCreate(fx(n)), [], n);
  }
});

test('intake rejects contradictions, unauthorised approval, bad dependencies', () => {
  const base = fx('run-create');
  const mut = (f) => { const c = structuredClone(base); f(c); return validateRunCreate(c); };
  assert.ok(mut((c) => { c.supplied_tests[0].expected = 999; }).some((e) => /contradicts approved/.test(e)));
  assert.ok(mut((c) => { c.requirements[0].source = 'model'; c.requirements[0].approval_status = 'approved'; }).some((e) => /only user\/reviewed_contract/.test(e)));
  assert.ok(mut((c) => { c.allowed_dependencies = ['os.path']; }).some((e) => /allowlist/.test(e)));
  assert.ok(mut((c) => { c.supplied_tests[0].inputs = [[999]]; }).length > 0);
  assert.ok(mut((c) => { c.schema_version = 'stage1.v1'; }).length > 0);
  assert.ok(mut((c) => { c.source = 'x'.repeat(48001); }).some((e) => /48,000/.test(e)));
  assert.ok(mut((c) => { c.requirements.push({ ...c.requirements[0] }); }).some((e) => /duplicate requirement/.test(e)));
  assert.ok(mut((c) => { c.requirements[0].property_template_id = 'reverse_string'; }).some((e) => /does not fit/.test(e)));
  assert.ok(mut((c) => { c.helper_interfaces = [{ name: 'h', signature: 'h(x)', contract_text: '' }]; }).some((e) => /behaviour/.test(e)));
});
