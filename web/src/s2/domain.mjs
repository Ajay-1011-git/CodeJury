/** Client-side mirror of the json.v1 codec and ValueDomain DSL. The backend stays the authority. */

export const MAX_SAFE = Number.MAX_SAFE_INTEGER;
export const ALLOWLIST = Object.freeze([
  'math.gcd', 'math.isqrt', 'bisect.bisect_left', 'bisect.bisect_right', 'collections.Counter', 'collections.deque',
]);
export const TEMPLATES = Object.freeze({
  sort_ascending_ints: { wording: 'Output is the input integers in ascending order, keeping every duplicate.', args: ['int_list'] },
  unique_preserve_order_ints: { wording: 'Output keeps each integer once, in order of first occurrence.', args: ['int_list'] },
  sum_ints: { wording: 'Output is the exact integer sum, negatives included.', args: ['int_list'] },
  reverse_string: { wording: 'Output is the string reversed by Unicode codepoint.', args: ['string'] },
  count_occurrences_ints: { wording: 'Output is the exact number of times the integer occurs in the list.', args: ['int_list', 'int'] },
});

export class JsonError extends Error {}

/** Strict json.v1 parser: no floats, NaN, duplicate keys, unsafe integers or trailing text. */
export function parseJsonV1(text) {
  let i = 0;
  const fail = (m) => { throw new JsonError(`${m} at position ${i}`); };
  const ws = () => { while (' \t\n\r'.includes(text[i]) && i < text.length) i += 1; };
  function value(depth) {
    if (depth > 8) fail('nesting deeper than 8');
    ws();
    const c = text[i];
    if (c === '{') return object(depth);
    if (c === '[') return array(depth);
    if (c === '"') return string();
    if (text.startsWith('true', i)) { i += 4; return true; }
    if (text.startsWith('false', i)) { i += 5; return false; }
    if (text.startsWith('null', i)) { i += 4; return null; }
    return number();
  }
  function number() {
    const m = /^-?(0|[1-9][0-9]*)/.exec(text.slice(i));
    if (!m) fail('unexpected token');
    const next = text[i + m[0].length];
    if (next !== undefined && '.eE'.includes(next)) fail('floats are not json.v1');
    const n = Number(m[0]);
    if (!Number.isSafeInteger(n)) fail('integer outside +/-(2^53-1)');
    i += m[0].length;
    return n;
  }
  function string() {
    const start = i;
    i += 1;
    while (i < text.length && text[i] !== '"') i += text[i] === '\\' ? 2 : 1;
    if (text[i] !== '"') fail('unterminated string');
    i += 1;
    try { return JSON.parse(text.slice(start, i)); } catch { return fail('bad string'); }
  }
  function array(depth) {
    i += 1; const out = []; ws();
    if (text[i] === ']') { i += 1; return out; }
    for (;;) {
      out.push(value(depth + 1)); ws();
      if (text[i] === ',') { i += 1; continue; }
      if (text[i] === ']') { i += 1; return out; }
      fail('expected , or ]');
    }
  }
  function object(depth) {
    i += 1; const out = Object.create(null); ws();
    if (text[i] === '}') { i += 1; return { ...out }; }
    for (;;) {
      ws();
      if (text[i] !== '"') fail('expected key');
      const key = string();
      if (key in out) fail(`duplicate key ${JSON.stringify(key)}`);
      ws();
      if (text[i] !== ':') fail('expected :');
      i += 1;
      out[key] = value(depth + 1); ws();
      if (text[i] === ',') { i += 1; continue; }
      if (text[i] === '}') { i += 1; return { ...out }; }
      fail('expected , or }');
    }
  }
  const result = value(0);
  ws();
  if (i !== text.length) fail('trailing characters');
  return result;
}

const isInt = (v) => typeof v === 'number' && Number.isInteger(v);
const cpLen = (s) => [...s].length;

export function typedEqual(a, b) {
  if (typeof a !== typeof b || (a === null) !== (b === null)) return false;
  if (Array.isArray(a)) return Array.isArray(b) && a.length === b.length && a.every((x, k) => typedEqual(x, b[k]));
  if (a && typeof a === 'object') {
    const ka = Object.keys(a); const kb = Object.keys(b);
    return ka.length === kb.length && ka.every((k) => k in b && typedEqual(a[k], b[k]));
  }
  return a === b;
}

export function validateDomain(d, depth = 0) {
  const errs = [];
  const need = {
    null: ['kind'], boolean: ['kind'], integer: ['kind', 'min', 'max'],
    string: ['kind', 'alphabet', 'min_length', 'max_length'],
    list: ['kind', 'item_domain', 'min_length', 'max_length'],
    dict: ['kind', 'key_domain', 'value_domain', 'required_keys', 'min_size', 'max_size'],
    union: ['kind', 'options'],
  };
  if (!d || typeof d !== 'object' || !(d.kind in need)) return ['domain needs a known kind'];
  if (Object.keys(d).sort().join() !== [...need[d.kind]].sort().join()) return [`${d.kind} domain fields must be exactly ${need[d.kind].join(', ')}`];
  if (depth > 10) return ['domain nesting too deep'];
  if (d.kind === 'integer' && !(isInt(d.min) && isInt(d.max) && -1e6 <= d.min && d.min <= d.max && d.max <= 1e6)) errs.push('integer bounds must satisfy -1000000 <= min <= max <= 1000000');
  if (d.kind === 'string') {
    if (typeof d.alphabet !== 'string' || cpLen(d.alphabet) < 1 || cpLen(d.alphabet) > 256 || new Set(d.alphabet).size !== cpLen(d.alphabet)) errs.push('string alphabet needs 1-256 unique codepoints');
    if (!(isInt(d.min_length) && isInt(d.max_length) && d.min_length >= 0 && d.min_length <= d.max_length && d.max_length <= 128)) errs.push('string lengths need 0 <= min <= max <= 128');
  }
  if (d.kind === 'list') {
    if (!(isInt(d.min_length) && isInt(d.max_length) && d.min_length >= 0 && d.min_length <= d.max_length && d.max_length <= 64)) errs.push('list lengths need 0 <= min <= max <= 64');
    errs.push(...validateDomain(d.item_domain, depth + 1));
  }
  if (d.kind === 'dict') {
    errs.push(...validateDomain(d.key_domain, depth + 1), ...validateDomain(d.value_domain, depth + 1));
    if (d.key_domain?.kind !== 'string') errs.push('dictionary key domain must be a string domain');
    if (!(isInt(d.min_size) && isInt(d.max_size) && d.min_size >= 0 && d.min_size <= d.max_size && d.max_size <= 20)) errs.push('dictionary sizes need 0 <= min <= max <= 20');
    if (!Array.isArray(d.required_keys) || new Set(d.required_keys).size !== d.required_keys.length || d.required_keys.length > d.max_size) errs.push('required_keys must be unique and fit max_size');
    else if (d.key_domain?.kind === 'string') for (const k of d.required_keys) if (checkValue(d.key_domain, k)) errs.push(`required key ${JSON.stringify(k)} is outside the key domain`);
  }
  if (d.kind === 'union') {
    if (!Array.isArray(d.options) || d.options.length < 2 || d.options.length > 6) errs.push('union needs 2-6 alternatives');
    else for (const o of d.options) errs.push(...validateDomain(o, depth + 1));
  }
  if (depth === 0 && nesting(d) > 4) errs.push('container nesting exceeds 4');
  return errs;
}

function nesting(d) {
  if (!d || typeof d !== 'object') return 0;
  if (d.kind === 'list') return 1 + nesting(d.item_domain);
  if (d.kind === 'dict') return 1 + nesting(d.value_domain);
  if (d.kind === 'union') return Math.max(0, ...(d.options || []).map(nesting));
  return 0;
}

/** null when the value is in the domain, otherwise a short reason. Type-sensitive. */
export function checkValue(d, v) {
  switch (d.kind) {
    case 'null': return v === null ? null : 'expected null';
    case 'boolean': return typeof v === 'boolean' ? null : 'expected boolean';
    case 'integer':
      if (!isInt(v)) return 'expected integer (booleans are not integers)';
      return d.min <= v && v <= d.max ? null : 'integer out of bounds';
    case 'string':
      if (typeof v !== 'string') return 'expected string';
      if (cpLen(v) < d.min_length || cpLen(v) > d.max_length) return 'string length outside domain';
      return [...v].every((c) => [...d.alphabet].includes(c)) ? null : 'character outside alphabet';
    case 'list':
      if (!Array.isArray(v)) return 'expected list';
      if (v.length < d.min_length || v.length > d.max_length) return 'list length outside domain';
      for (const x of v) { const r = checkValue(d.item_domain, x); if (r) return r; }
      return null;
    case 'dict': {
      if (v === null || typeof v !== 'object' || Array.isArray(v)) return 'expected dictionary';
      const keys = Object.keys(v);
      if (keys.length < d.min_size || keys.length > d.max_size) return 'dictionary size outside domain';
      for (const k of d.required_keys) if (!(k in v)) return `missing required key ${JSON.stringify(k)}`;
      for (const k of keys) { const r = checkValue(d.key_domain, k) || checkValue(d.value_domain, v[k]); if (r) return r; }
      return null;
    }
    case 'union': return d.options.some((o) => checkValue(o, v) === null) ? null : 'value matches no union alternative';
    default: return 'unknown domain';
  }
}

const reference = {
  sort_ascending_ints: (a) => [...a[0]].sort((x, y) => x - y),
  unique_preserve_order_ints: (a) => a[0].filter((x, k) => a[0].indexOf(x) === k),
  sum_ints: (a) => a[0].reduce((s, x) => s + x, 0),
  reverse_string: (a) => [...a[0]].reverse().join(''),
  count_occurrences_ints: (a) => a[0].filter((x) => x === a[1]).length,
};

function shape(domain) {
  if (domain.kind === 'integer') return 'int';
  if (domain.kind === 'string') return 'string';
  if (domain.kind === 'list' && domain.item_domain.kind === 'integer') return 'int_list';
  return 'other';
}

export function templateCompatible(templateId, domainSchema) {
  const t = TEMPLATES[templateId];
  return !!t && domainSchema.length === t.args.length && domainSchema.every((a, k) => shape(a.domain) === t.args[k]);
}

export function byteLength(s) { return new TextEncoder().encode(s).length; }

/** Pre-submit checks mirroring the backend intake. Returns a list of human-readable problems. */
export function validateRunCreate(p) {
  const errs = [];
  if (!p || typeof p !== 'object') return ['request must be an object'];
  if (p.schema_version !== 'stage2.v1') errs.push("schema_version must be 'stage2.v1'");
  if (typeof p.source !== 'string' || !p.source.trim()) errs.push('source must be non-empty');
  else if (byteLength(p.source) > 48000) errs.push('source exceeds 48,000 bytes');
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(p.function_name || '')) errs.push('function name must be a Python identifier');
  if (typeof p.contract_text !== 'string' || !p.contract_text.trim() || p.contract_text.length > 12000) errs.push('contract text must be 1-12,000 characters');
  const schema = p.domain_schema;
  if (!Array.isArray(schema) || schema.length < 1 || schema.length > 6) errs.push('1-6 argument domains are required');
  else {
    const names = new Set();
    for (const a of schema) {
      if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(a.name || '') || names.has(a.name)) errs.push(`argument name ${JSON.stringify(a.name)} is invalid or repeated`);
      names.add(a.name);
      for (const e of validateDomain(a.domain)) errs.push(`${a.name}: ${e}`);
    }
  }
  if (!Array.isArray(p.helper_interfaces) || p.helper_interfaces.length > 3) errs.push('at most 3 helper interfaces');
  else for (const h of p.helper_interfaces) if (!h.name || !h.signature || !h.contract_text?.trim()) errs.push(`helper ${h.name || '?'} needs name, signature and behaviour text`);
  const reqs = p.requirements || [];
  if (reqs.length < 1 || reqs.length > 30) errs.push('1-30 requirements are required');
  const ids = new Set();
  for (const r of reqs) {
    if (ids.has(r.requirement_id)) errs.push(`duplicate requirement ${r.requirement_id}`);
    ids.add(r.requirement_id);
    if (r.approval_status === 'approved' && !['user', 'reviewed_contract'].includes(r.source)) errs.push(`${r.requirement_id}: only user/reviewed_contract requirements can be approved`);
    if (r.property_template_id) {
      if (!(r.property_template_id in TEMPLATES)) { if (r.approval_status === 'approved') errs.push(`${r.requirement_id}: unregistered template`); } else if (r.approval_status === 'approved' && Array.isArray(schema) && !templateCompatible(r.property_template_id, schema)) errs.push(`${r.requirement_id}: template ${r.property_template_id} does not fit the argument domains`);
    }
  }
  const tests = p.supplied_tests || [];
  if (tests.length < 1 || tests.length > 50) errs.push('1-50 supplied tests are required');
  const seen = new Set();
  for (const t of tests) {
    if (seen.has(t.test_id)) errs.push(`duplicate test ${t.test_id}`);
    seen.add(t.test_id);
    if (!Array.isArray(t.inputs) || t.inputs.length !== (schema || []).length) { errs.push(`${t.test_id}: argument count differs from the domain`); continue; }
    t.inputs.forEach((v, k) => { const r = checkValue(schema[k].domain, v); if (r) errs.push(`${t.test_id}.${schema[k].name}: ${r}`); });
    for (const rid of t.requirement_ids || []) if (!ids.has(rid)) errs.push(`${t.test_id}: unknown requirement ${rid}`);
    const cited = (t.requirement_ids?.length ? t.requirement_ids : [...ids]);
    for (const rid of cited) {
      const r = reqs.find((x) => x.requirement_id === rid);
      if (r && r.approval_status === 'approved' && r.property_template_id in reference && templateCompatible(r.property_template_id, schema)) {
        if (!typedEqual(reference[r.property_template_id](t.inputs), t.expected)) errs.push(`${t.test_id}: expectation contradicts approved requirement ${rid}`);
      }
    }
  }
  const deps = p.allowed_dependencies || [];
  if (deps.length > 10 || deps.some((d) => !ALLOWLIST.includes(d))) errs.push('dependencies must come from the reviewed allowlist');
  if (p.resource_profile !== 'mac-standard-v1') errs.push('resource_profile must be mac-standard-v1');
  if (!['learned', 'fixed'].includes(p.policy_mode)) errs.push('policy_mode must be learned or fixed');
  if (!isInt(p.seed) || p.seed < 0) errs.push('seed must be an integer >= 0');
  return errs;
}
