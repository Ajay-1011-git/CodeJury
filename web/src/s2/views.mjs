/** DOM rendering. Every dynamic string goes through textContent; there is no HTML injection path. */

import { ALLOWLIST, TEMPLATES, parseJsonV1, validateRunCreate, JsonError } from './domain.mjs';
import {
  actionTimeline, candidateCards, fmt, gapViews, reportView, resourceView, testMatrix, trainingView, NOT_MEASURED,
} from './model.mjs';

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') node.className = v;
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else if (k === 'text') node.textContent = v;
    else node.setAttribute(k, v === true ? '' : String(v));
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}
const code = (text, cls = 'code-block') => el('pre', { class: cls }, el('code', { text }));
const badge = (text, kind = 'neutral') => el('span', { class: `badge badge-${kind}`, text });
const hash = (h) => el('code', { class: 'hash', title: h, text: h ? h.slice(0, 12) : NOT_MEASURED });
const clear = (node) => { while (node.firstChild) node.firstChild.remove(); };
const OUTCOME_KIND = { pass: 'success', fail: 'danger', error: 'danger', timeout: 'warn', observed: 'neutral' };

// ---------------------------------------------------------------- input form
const REQ_SOURCES = ['user', 'reviewed_contract'];

export function mountInput(root, { examples, onSubmit, canSubmit }) {
  const f = {};
  const field = (label, control, hint) => el('label', { class: 'field' }, el('span', { class: 'field-label', text: label }), control, hint && el('small', { text: hint }));
  f.source = el('textarea', { rows: 10, spellcheck: 'false', class: 'code-input', 'aria-label': 'Buggy source' });
  f.fn = el('input', { type: 'text', value: '', autocomplete: 'off' });
  f.contract = el('textarea', { rows: 3 });
  f.seed = el('input', { type: 'number', min: 0, value: 0 });
  f.policy = el('select', {}, el('option', { value: 'learned', text: 'learned (Judge chooses actions)' }), el('option', { value: 'fixed', text: 'fixed policy (deterministic menu)' }));
  const args = el('div', { class: 'rows' });
  const helpers = el('div', { class: 'rows' });
  const reqs = el('div', { class: 'rows' });
  const tests = el('div', { class: 'rows' });
  const deps = el('div', { class: 'deps' }, ALLOWLIST.map((d) => el('label', { class: 'check' }, el('input', { type: 'checkbox', value: d }), ` ${d}`)));
  const problems = el('ul', { class: 'problems', role: 'alert' });
  const submit = el('button', { type: 'submit', class: 'btn btn-primary', text: 'Submit case' });

  const rowShell = (container, ...nodes) => {
    const row = el('div', { class: 'row' }, ...nodes, el('button', { type: 'button', class: 'btn-link', text: 'remove', onclick: () => row.remove() }));
    container.append(row);
    return row;
  };
  const addArg = (name = '', domain = '') => rowShell(args,
    el('input', { 'data-k': 'name', placeholder: 'argument name', value: name }),
    el('textarea', { 'data-k': 'domain', rows: 3, class: 'code-input', placeholder: '{"kind":"list","item_domain":{"kind":"integer","min":-10,"max":10},"min_length":0,"max_length":8}', text: domain }));
  const addHelper = (h = {}) => rowShell(helpers,
    el('input', { 'data-k': 'name', placeholder: 'helper name', value: h.name || '' }),
    el('input', { 'data-k': 'signature', placeholder: 'name(a, b)', value: h.signature || '' }),
    el('textarea', { 'data-k': 'contract_text', rows: 2, placeholder: 'reviewed behaviour of the helper', text: h.contract_text || '' }));
  const addReq = (r = {}) => {
    const template = el('select', { 'data-k': 'property_template_id' }, el('option', { value: '', text: '(no executable template)' }),
      Object.keys(TEMPLATES).map((t) => el('option', { value: t, text: t, selected: r.property_template_id === t })));
    const wording = el('small', { class: 'wording' });
    const show = () => { wording.textContent = template.value ? `Wording that will be enforced: ${TEMPLATES[template.value].wording}` : 'Prose only: nothing executable is approved.'; };
    template.addEventListener('change', show);
    show();
    return rowShell(reqs,
      el('input', { 'data-k': 'requirement_id', placeholder: 'requirement id', value: r.requirement_id || '' }),
      el('textarea', { 'data-k': 'description', rows: 2, placeholder: 'requirement wording', text: r.description || '' }),
      el('select', { 'data-k': 'source' }, REQ_SOURCES.map((s) => el('option', { value: s, text: s, selected: r.source === s }))),
      el('select', { 'data-k': 'approval_status' }, ['approved', 'proposed'].map((s) => el('option', { value: s, text: s, selected: r.approval_status === s }))),
      template, wording);
  };
  const addTest = (t = {}) => rowShell(tests,
    el('input', { 'data-k': 'test_id', placeholder: 'test id', value: t.test_id || '' }),
    el('textarea', { 'data-k': 'inputs', rows: 2, class: 'code-input', placeholder: '[[1, 2]]  (one JSON value per argument)', text: t.inputs ? JSON.stringify(t.inputs) : '' }),
    el('textarea', { 'data-k': 'expected', rows: 1, class: 'code-input', placeholder: 'expected JSON value', text: t.expected === undefined ? '' : JSON.stringify(t.expected) }),
    el('input', { 'data-k': 'requirement_ids', placeholder: 'requirement ids, comma separated', value: (t.requirement_ids || []).join(', ') }));

  const read = (row, k) => row.querySelector(`[data-k="${k}"]`).value;
  const parse = (text, label, bad) => {
    try { return parseJsonV1(text); } catch (e) { bad.push(`${label}: ${e instanceof JsonError ? e.message : 'invalid JSON'}`); return null; }
  };
  function collect() {
    const bad = [];
    const domain_schema = [...args.children].map((row) => ({ name: read(row, 'name').trim(), domain: parse(read(row, 'domain'), `domain of ${read(row, 'name') || '?'}`, bad) }));
    const payload = {
      schema_version: 'stage2.v1', source: f.source.value, function_name: f.fn.value.trim(), contract_text: f.contract.value,
      domain_schema,
      helper_interfaces: [...helpers.children].map((r) => ({ name: read(r, 'name').trim(), signature: read(r, 'signature').trim(), contract_text: read(r, 'contract_text') })),
      requirements: [...reqs.children].map((r) => ({
        schema_version: 'stage2.v1', requirement_id: read(r, 'requirement_id').trim(), description: read(r, 'description'),
        source: read(r, 'source'), approval_status: read(r, 'approval_status'),
        property_template_id: read(r, 'property_template_id') || null, parameters: {},
      })),
      supplied_tests: [...tests.children].map((r) => ({
        schema_version: 'stage2.v1', test_id: read(r, 'test_id').trim(), inputs: parse(read(r, 'inputs'), `inputs of ${read(r, 'test_id') || '?'}`, bad),
        expected: parse(read(r, 'expected'), `expected of ${read(r, 'test_id') || '?'}`, bad),
        requirement_ids: read(r, 'requirement_ids').split(',').map((s) => s.trim()).filter(Boolean),
      })),
      allowed_dependencies: [...deps.querySelectorAll('input:checked')].map((i) => i.value),
      resource_profile: 'mac-standard-v1', policy_mode: f.policy.value, seed: Number(f.seed.value),
    };
    return { payload, bad };
  }
  function fill(ex) {
    const r = ex.request;
    f.source.value = r.source; f.fn.value = r.function_name; f.contract.value = r.contract_text;
    f.policy.value = r.policy_mode; f.seed.value = r.seed;
    for (const box of [args, helpers, reqs, tests]) clear(box);
    r.domain_schema.forEach((a) => addArg(a.name, JSON.stringify(a.domain, null, 1)));
    r.helper_interfaces.forEach(addHelper);
    r.requirements.forEach(addReq);
    r.supplied_tests.forEach(addTest);
    for (const box of deps.querySelectorAll('input')) box.checked = r.allowed_dependencies.includes(box.value);
    problems.replaceChildren();
  }

  const picker = el('select', { 'aria-label': 'Examples' }, el('option', { value: '', text: 'Load an example…' }), examples.map((e, k) => el('option', { value: k, text: e.title })));
  picker.addEventListener('change', () => { if (picker.value !== '') fill(examples[Number(picker.value)]); });
  const form = el('form', { class: 'case-form', novalidate: true },
    el('div', { class: 'field-row' }, picker),
    field('Source (text only; never run in the browser)', f.source),
    el('div', { class: 'two' }, field('Function name', f.fn), field('Seed', f.seed)),
    field('Contract', f.contract),
    el('fieldset', {}, el('legend', { text: 'Typed argument domains (ValueDomain JSON, max 6)' }), args, el('button', { type: 'button', class: 'btn', text: 'Add argument', onclick: () => addArg() })),
    el('fieldset', {}, el('legend', { text: 'Reviewed helper interfaces (max 3)' }), helpers, el('button', { type: 'button', class: 'btn', text: 'Add helper', onclick: () => addHelper() })),
    el('fieldset', {}, el('legend', { text: 'Requirements — approve before the run; the model can never approve' }), reqs, el('button', { type: 'button', class: 'btn', text: 'Add requirement', onclick: () => addReq({ source: 'user', approval_status: 'approved' }) })),
    el('fieldset', {}, el('legend', { text: 'Supplied tests (authoritative, user-owned)' }), tests, el('button', { type: 'button', class: 'btn', text: 'Add test', onclick: () => addTest() })),
    el('fieldset', {}, el('legend', { text: 'Dependency consent (reviewed allowlist only)' }), deps),
    el('div', { class: 'two' }, field('Resource profile', el('input', { value: 'mac-standard-v1', disabled: true })), field('Policy', f.policy)),
    problems, submit);
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const { payload, bad } = collect();
    const issues = [...bad, ...(bad.length ? [] : validateRunCreate(payload))];
    problems.replaceChildren(...issues.map((m) => el('li', { text: m })));
    if (issues.length) return;
    if (!canSubmit()) { problems.replaceChildren(el('li', { text: 'The backend contract check has not passed; submission is blocked.' })); return; }
    await onSubmit(payload);
  });
  root.replaceChildren(form);
  if (examples[0]) { picker.value = '0'; fill(examples[0]); }
  return { setBusy(busy) { submit.disabled = busy; }, fill, collect };
}

// ---------------------------------------------------------------- run views
export function renderRun(root, state, handlers) {
  clear(root);
  const snap = state.snapshot;
  if (!snap) { root.append(el('p', { class: 'placeholder-label', text: state.runId ? 'Waiting for the first snapshot…' : 'No case yet.' })); return; }
  const kind = { supported_patch: 'success', unresolved: 'warn', cancelled: 'warn', invalid_input: 'danger', infrastructure_error: 'danger' }[snap.status] || 'neutral';
  root.append(el('div', { class: 'run-head' }, badge(snap.status.toUpperCase(), kind), badge(`phase: ${snap.phase}`), badge(`policy: ${snap.policy_mode}`), snap.runtime_mode === 'fixture' && badge('FIXTURE', 'warn')));
  if (state.withdrawn) root.append(el('p', { class: 'notice', role: 'alert', text: 'An earlier success was withdrawn by a newer result: nothing is downloadable from it.' }));
  if (snap.termination_reason) root.append(el('p', { class: 'notice', text: snap.termination_reason }));

  root.append(el('h3', { text: 'Resources (actual, not progress)' }), el('table', { class: 'table' }, el('tbody', {}, resourceView(snap.resource_usage).map((r) => el('tr', {}, el('th', { text: r.label }), el('td', { text: r.shown }), el('td', { class: 'dim', text: r.cap === null ? '' : `cap ${r.cap}` }))))));

  root.append(el('h3', { text: 'Candidates and provenance' }));
  for (const c of candidateCards(snap)) {
    const cand = c.candidate;
    const card = el('article', { class: `cand${c.selected ? ' selected' : ''}` },
      el('header', {}, el('strong', { text: `${cand.candidate_id} · ${c.role.label}` }), badge(cand.eligibility, cand.eligibility === 'eligible' ? 'success' : 'neutral'),
        c.stale && badge('qualification STALE', 'warn'), c.selected && badge('selected by backend', 'success'), !c.selectable && badge('not selectable', 'neutral')),
      el('p', { class: 'dim', text: c.role.view }),
      el('p', {}, 'source ', hash(cand.source_hash), cand.model_config_hash && [' · model config ', hash(cand.model_config_hash)], cand.parent_id && [' · parent ', el('code', { text: cand.parent_id })]),
      cand.diagnosis && el('p', { text: `Diagnosis: ${cand.diagnosis}` }),
      cand.assumptions.length > 0 && el('ul', {}, cand.assumptions.map((a) => el('li', { text: a }))),
      cand.rejection_reason && el('p', { class: 'notice', text: `Rejected: ${cand.rejection_reason}` }));
    if (c.lineage.steps.length) {
      card.append(el('ol', { class: 'edits' }, c.lineage.steps.map((s) => el('li', {}, badge(s.ok ? 'hash ok' : 'hash BROKEN', s.ok ? 'success' : 'danger'), ` ${s.operator_family} @ line ${s.location.lineno}: `, el('code', { text: s.before }), ' → ', el('code', { text: s.after }), ' ', hash(s.parent_source_hash), ' ⇒ ', hash(s.result_source_hash)))));
      if (!c.lineage.chainOk) card.append(el('p', { class: 'notice', text: 'The edit chain does not reconstruct this source.' }));
    }
    card.append(el('details', {}, el('summary', { text: 'Exact source' }), code(cand.source)));
    root.append(card);
  }

  const m = testMatrix(snap);
  root.append(el('h3', { text: 'Test matrix' }));
  root.append(el('div', { class: 'scroll' }, el('table', { class: 'table matrix' },
    el('thead', {}, el('tr', {}, el('th', { text: 'test' }), el('th', { text: 'oracle' }), m.candidates.map((c) => el('th', { text: c })))),
    el('tbody', {}, m.rows.map((r) => el('tr', { class: r.authoritative ? '' : 'soft' }, el('th', { text: r.test.test_id }), el('td', { text: r.label }),
      r.cells.map((cell) => el('td', {}, cell ? badge(cell.outcome + (cell.mutated ? ' · mutated input' : ''), OUTCOME_KIND[cell.outcome]) : el('span', { class: 'dim', text: 'not run' }))))))))); 

  root.append(el('h3', { text: 'Audit gaps and probes' }));
  const gaps = gapViews(snap);
  if (!gaps.length) root.append(el('p', { class: 'dim', text: 'No audit gap recorded.' }));
  for (const g of gaps) {
    root.append(el('article', { class: 'cand' }, el('header', {}, el('strong', { text: g.gap.gap_id }), badge(g.gap.interpretation), g.stale && badge('STALE', 'warn')),
      el('p', {}, `candidate ${g.gap.candidate_id} · source `, hash(g.gap.candidate_source_hash), ' · suite ', hash(g.gap.suite_hash), ` · line ${g.gap.location.lineno} · ${g.gap.operator_family}`),
      el('p', { class: 'dim', text: g.note }), g.gap.requirement_ids.length === 0 && el('p', { class: 'dim', text: 'No reviewed requirement mapping attached.' }),
      el('ul', {}, g.probes.map((p) => el('li', {}, badge('probe, not a vote'), ' ', el('code', { text: p.mutant.mutant_id }), ` ${p.mutant.outcome} · ${p.equivalence} `, el('details', {}, el('summary', { text: 'probe source' }), code(p.mutant.source)))))));
  }

  const tl = actionTimeline(snap, state.events);
  root.append(el('h3', { text: 'Judge actions' }), el('p', { class: 'dim', text: tl.policy === 'fixed' ? 'Fixed policy run.' : 'Learned policy; refusals and fixed fallbacks are marked.' }));
  root.append(el('ul', { class: 'timeline' }, [...tl.actions.map((a) => el('li', {}, badge(a.title), ` ${a.detail}`, a.evidence.length > 0 && el('small', { text: ` evidence: ${a.evidence.join(', ')}` }))),
    ...tl.log.map((e) => el('li', {}, badge(e.title, e.kind === 'action_refused' ? 'warn' : 'neutral'), e.fallback && badge('FIXED FALLBACK', 'warn'), ` ${e.detail}`))]));

  if (snap.decision) {
    const d = snap.decision;
    root.append(el('h3', { text: 'Decision' }), el('p', { text: d.reason }), el('p', {}, 'Verification scope: ', d.verification_scope.join(' · ') || NOT_MEASURED));
    if (d.unresolved_requirements.length > 0) root.append(el('p', { text: `Unresolved requirements: ${d.unresolved_requirements.join(', ')}` }));
    handlers.mountDownload(root, snap);
  }
}

export function renderDownload(root, dl) {
  if (!dl) { root.append(el('p', { class: 'dim', text: 'No patch is downloadable: the backend did not select a currently qualified candidate.' })); return; }
  const blob = new Blob([dl.text], { type: 'text/x-python' });
  const url = URL.createObjectURL(blob);
  root.append(el('p', {}, el('a', { class: 'btn btn-primary', href: url, download: dl.filename, text: `Download ${dl.filename}` }), ' SHA-256 ', hash(dl.hash)));
}

// ---------------------------------------------------------------- reports
export function renderReports(root, { training, benchmark }) {
  clear(root);
  if (training) {
    root.append(el('h3', { text: 'Adapter cards' }));
    if (training.runtime_mode === 'fixture') root.append(el('p', { class: 'notice', text: 'SYNTHETIC fixture report: not evidence of learning.' }));
    for (const v of trainingView(training)) {
      const c = v.card;
      root.append(el('article', { class: 'cand' }, el('header', {}, el('strong', { text: v.label }), badge(v.status, v.status === 'completed' ? 'success' : 'warn')),
        el('p', {}, `steps ${fmt(c.steps)} · base problems ${fmt(c.train_base_problems)} · records ${fmt(c.train_records)} · adapter `, hash(c.adapter_hash)),
        el('p', { text: c.evaluation_summary }),
        v.losses.length > 0 && el('table', { class: 'table' }, el('thead', {}, el('tr', {}, ['step', 'train loss', 'validation loss'].map((h) => el('th', { text: h })))), el('tbody', {}, v.losses.map((l) => el('tr', {}, el('td', { text: l.step }), el('td', { text: fmt(l.train, 4) }), el('td', { text: fmt(l.validation, 4) })))))));
    }
  }
  if (benchmark) {
    const v = reportView(benchmark);
    root.append(el('h3', { text: 'Benchmark' }), el('p', {}, badge(benchmark.status), ' ', badge(`research outcome: ${v.outcome}`, v.outcome === 'worse' ? 'danger' : v.outcome === 'improved' ? 'success' : 'neutral'), v.fixture && badge('FIXTURE — never mixed with live data', 'warn')));
    if (!v.rows.length) root.append(el('p', { class: 'dim', text: 'Not run: there are no benchmark rows.' }));
    root.append(el('div', { class: 'scroll' }, el('table', { class: 'table' }, el('thead', {}, el('tr', {}, ['method', 'solved', 'incorrect accepted', 'unresolved', 'invalid', 'infra', 'cancelled', 'precision', 'mean in/out tokens', 'mean ms', 'memory MB', 'budget'].map((h) => el('th', { text: h })))),
      el('tbody', {}, v.rows.map(({ row, exact, precision, partition }) => el('tr', {}, el('th', { title: row.note, text: row.method }), el('td', { text: exact }), ['incorrect_accepted', 'unresolved', 'invalid_input', 'infrastructure_error', 'cancelled'].map((k) => el('td', { text: row[k] })), el('td', { text: precision }),
        el('td', { text: `${fmt(row.mean_input_tokens)} / ${fmt(row.mean_output_tokens)}` }), el('td', { text: fmt(row.mean_elapsed_ms) }), el('td', { text: fmt(row.mean_peak_memory_mb) }), el('td', { text: partition ? row.budget_comparison : 'COUNTS DO NOT PARTITION' })))))));
    root.append(el('p', { text: benchmark.paired_analysis_note }), el('ul', {}, benchmark.limitations.map((l) => el('li', { text: l }))));
  }
}
