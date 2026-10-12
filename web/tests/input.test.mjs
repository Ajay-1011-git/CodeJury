import { test } from 'node:test';
import assert from 'node:assert/strict';
import { validateRunCreatePayload } from '../src/input.mjs';

const validBasePayload = {
  schema_version: 'stage1.v1',
  source: 'def sort_ints(items):\n    return items\n',
  function_name: 'sort_ints',
  contract_text: 'Sort integers in nondecreasing order.',
  input_domain: [
    {
      kind: 'list_integer',
      min: -100,
      max: 100,
      min_length: 0,
      max_length: 20
    }
  ],
  supplied_tests: [
    {
      test_id: 'test_1',
      args: [[3, 1, 2]],
      expected: [1, 2, 3]
    }
  ],
  approved_property: null,
  resource_profile: 'stage1-demo'
};

test('Valid example payload passes validation', () => {
  const res = validateRunCreatePayload(validBasePayload, false);
  assert.equal(res.valid, true);
  assert.equal(res.errors.length, 0);
});

test('Missing property consent check rejects payload', () => {
  const withProperty = {
    ...validBasePayload,
    approved_property: 'sort_ascending_ints'
  };
  // Without consent (propertyApproved = false)
  const res = validateRunCreatePayload(withProperty, false);
  assert.equal(res.valid, false);
  assert.ok(res.errors.some(e => e.includes('explicit consent checkbox')));

  // With consent (propertyApproved = true)
  const resApproved = validateRunCreatePayload(withProperty, true);
  assert.equal(resApproved.valid, true);
});

test('Unknown property name is rejected', () => {
  const badProp = {
    ...validBasePayload,
    approved_property: 'unsupported_sort_descending'
  };
  const res = validateRunCreatePayload(badProp, true);
  assert.equal(res.valid, false);
  assert.ok(res.errors.some(e => e.includes('Unknown approved_property')));
});

test('Boolean passed as integer is rejected', () => {
  const boolAsIntDomain = {
    ...validBasePayload,
    input_domain: [
      {
        kind: 'integer',
        min: true, // boolean should not be accepted as integer
        max: 10,
        min_length: null,
        max_length: null
      }
    ]
  };
  const res = validateRunCreatePayload(boolAsIntDomain, false);
  assert.equal(res.valid, false);
  assert.ok(res.errors.some(e => e.includes('must be an integer')));
});

test('Repeated test IDs are detected and rejected', () => {
  const duplicateTests = {
    ...validBasePayload,
    supplied_tests: [
      { test_id: 'test_alpha', args: [[1]], expected: [1] },
      { test_id: 'test_alpha', args: [[2]], expected: [2] } // duplicate
    ]
  };
  const res = validateRunCreatePayload(duplicateTests, false);
  assert.equal(res.valid, false);
  assert.ok(res.errors.some(e => e.includes("Duplicate test_id detected: 'test_alpha'")));
});

test('HTML/XSS injection string is preserved verbatim as plain text', () => {
  const xssSource = 'def sort_ints(items):\n    # <script>alert("xss")</script>\n    return items\n';
  const xssPayload = {
    ...validBasePayload,
    source: xssSource
  };
  const res = validateRunCreatePayload(xssPayload, false);
  assert.equal(res.valid, true);
  assert.equal(xssPayload.source, xssSource);
  assert.ok(xssPayload.source.includes('<script>'));
});

test('Source edits appear in request unchanged without expected repaired code', () => {
  const customUserCode = 'def sort_ints(items):\n    # User bespoke implementation\n    return sorted(items, reverse=True)\n';
  const customPayload = {
    ...validBasePayload,
    source: customUserCode
  };
  assert.equal(customPayload.source, customUserCode);
  // Ensure no fabricated repaired code is inserted
  assert.equal('repaired_code' in customPayload, false);
  assert.equal('patch' in customPayload, false);
});

test('Malformed domain entries produce validation errors instead of crashing the editor', () => {
  for (const value of [null, 3, []]) {
    const result = validateRunCreatePayload({ ...validBasePayload, input_domain: [value] }, false);
    assert.equal(result.valid, false);
    assert.ok(result.errors.some(error => error.includes('domain object')));
  }
});

test('Malformed test entries produce validation errors instead of crashing the editor', () => {
  for (const value of [null, 3, []]) {
    const result = validateRunCreatePayload({ ...validBasePayload, supplied_tests: [value] }, false);
    assert.equal(result.valid, false);
    assert.ok(result.errors.some(error => error.includes('test object')));
  }
});
