/** Minimal-input specification intake. All draft items are observations until approval. */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export class IntakeClient {
  constructor(base = `${location.origin}/s2x`, fetchFn = globalThis.fetch.bind(globalThis)) {
    this.base = base; this.fetch = fetchFn;
  }
  async request(path, payload) {
    const response = await this.fetch(`${this.base}${path}`, {
      method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    let body;
    try { body = await response.json(); } catch { throw new Error('The intake service returned an unreadable response.'); }
    if (!response.ok) throw new Error(body?.error?.message || `Intake failed (${response.status}).`);
    if (body.spec_version !== 1) throw new Error('The intake service version does not match this dashboard.');
    return body;
  }
  infer(payload) { return this.request('/intake', payload); }
  approve(id, decisions) { return this.request(`/intake/${encodeURIComponent(id)}/approve`, decisions); }
}

export function draftItems(draft) {
  return [
    ...(draft.arg_domains || []).map((d) => ({ id: `domain:${d.param}`, label: `Argument: ${d.param}`, value: { domain: d.domain }, source: d.source, tier: d.tier || 'proposed' })),
    ...(draft.requirements || []).map((r) => ({ id: `requirement:${r.id}`, label: 'Requirement', value: { text: r.text, property_template_id: r.property_template_id }, source: r.source, tier: r.tier || 'proposed' })),
    ...(draft.examples || []).map((e) => ({ id: `example:${e.id}`, label: 'Example', value: { args: e.args, expected: e.expected }, source: e.source, tier: e.tier || 'proposed', corroboration: e.corroboration || [] })),
  ];
}

export function domainSummary(domain) {
  if (!domain) return 'No domain supplied';
  const size = `${domain.min_length}–${domain.max_length}`;
  switch (domain.kind) {
    case 'integer': return `Integer from ${domain.min} to ${domain.max}`;
    case 'boolean': return 'True or false';
    case 'null': return 'Null';
    case 'string': return `Text, ${size} characters; allowed characters: ${JSON.stringify(domain.alphabet)}`;
    case 'list': return `List of ${size} items. Each item: ${domainSummary(domain.item_domain)}`;
    case 'dict': return `Dictionary with ${domain.min_size}–${domain.max_size} entries. Keys: ${domainSummary(domain.key_domain)}. Values: ${domainSummary(domain.value_domain)}`;
    default: return JSON.stringify(domain);
  }
}

export function itemSummary(item) {
  if (item.id.startsWith('domain:')) return domainSummary(item.value.domain);
  if (item.id.startsWith('requirement:')) {
    const template = item.value.property_template_id;
    return item.value.text + (template ? `\nProperty proposed for approval: ${template}` : '');
  }
  return `Input: ${JSON.stringify(item.value.args)}\nExpected output: ${JSON.stringify(item.value.expected)}`;
}

export function approvalDecisions(items, trustInterpreter = false) {
  return { trust_interpreter: trustInterpreter, items: items.map((item) => {
    const value = item.decision === 'edit' ? JSON.parse(item.text) : undefined;
    return { item_id: item.id, decision: item.decision, ...(value === undefined ? {} : { value }) };
  }) };
}

export function mountQuickCase(root, { client = new IntakeClient(), onAccepted, canSubmit = () => true } = {}) {
  let busy = false; let disposed = false; let generation = 0; let draft = null; let externalBusy = false;
  const form = el('form', 'quick-case-form');
  const intro = el('p', 'text-dim', 'Give the code, function name and desired behavior. The cloud interpreter sees your description, signature and AST facts to draft checks for approval. The buggy body stays local; local agents repair it.');
  form.appendChild(intro);
  const inputs = {};
  for (const [key, title, tag] of [['source', 'Buggy code', 'textarea'], ['function_name', 'Function name', 'input'], ['description', 'What should the function do?', 'textarea']]) {
    const label = el('label', 'quick-field'); label.appendChild(el('span', null, title));
    const input = el(tag, key === 'source' ? 'code-input' : '');
    input.name = key; input.required = true;
    if (tag === 'textarea') input.rows = key === 'source' ? 8 : 3;
    if (key === 'source') input.placeholder = 'def total(values):\n    return 0';
    if (key === 'function_name') input.placeholder = 'total';
    if (key === 'description') input.placeholder = 'Return the sum of every integer, including negatives. Empty input gives zero.';
    inputs[key] = input; label.appendChild(input); form.appendChild(label);
  }
  const interpret = el('button', 'btn btn-primary', 'Draft the specification'); interpret.type = 'submit';
  form.appendChild(interpret);
  const status = el('p', 'quick-status'); status.setAttribute('role', 'status');
  const panel = el('div', 'quick-approval');
  root.append(form, status, panel);

  function updateBusy() {
    interpret.disabled = busy || externalBusy;
    for (const input of Object.values(inputs)) input.disabled = busy;
    for (const node of panel.querySelectorAll('button')) node.disabled = busy || externalBusy;
  }
  function renderDraft() {
    panel.replaceChildren();
    if (!draft) return;
    panel.appendChild(el('h3', null, 'Review the inferred specification'));
    panel.appendChild(el('p', 'callout callout-info', 'These are proposed requirements and examples. Approving them makes them the checks the jury must pass. Confirm that they describe the intended behavior.'));
    for (const ambiguity of draft.disagreements || []) panel.appendChild(el('p', 'callout callout-warn', `Clarify before approval: ${ambiguity}`));
    const items = draftItems(draft);
    const controls = [];
    for (const item of items) {
      const card = el('div', 'quick-item');
      const heading = el('div', 'quick-item-heading');
      heading.appendChild(el('strong', null, item.label));
      heading.appendChild(el('span', 'badge badge-neutral', `${item.source} · ${item.tier}`));
      const choice = el('select'); choice.setAttribute('aria-label', `Decision for ${item.id}`);
      for (const [value, text] of [['approve', 'Approve'], ['edit', 'Edit'], ['reject', 'Reject']]) {
        const option = el('option', null, text); option.value = value; choice.appendChild(option);
      }
      heading.appendChild(choice); card.appendChild(heading);
      const summary = el('pre', 'quick-item-summary', itemSummary(item));
      card.appendChild(summary);
      if (item.corroboration?.length) card.appendChild(el('p', 'text-dim', 'Matches an independent registered property check. Approval is still required.'));
      const text = el('textarea', 'quick-item-value'); text.rows = item.id.startsWith('domain:') ? 5 : 3;
      text.value = JSON.stringify(item.value, null, 2); text.hidden = true;
      text.setAttribute('aria-label', `Inferred ${item.label.toLowerCase()}`);
      choice.addEventListener('change', () => { text.hidden = choice.value !== 'edit'; summary.hidden = choice.value === 'edit'; card.classList.toggle('quick-item-rejected', choice.value === 'reject'); });
      card.appendChild(text); panel.appendChild(card); controls.push({ item, choice, text });
    }
    const trustLabel = el('label', 'quick-trust');
    const trust = el('input'); trust.type = 'checkbox'; trust.checked = false;
    trustLabel.append(trust, document.createTextNode(' Trust the interpreter for this case (verdict will be labelled as an interpreted specification)'));
    panel.appendChild(trustLabel);
    const actions = el('div', 'quick-actions');
    const approveAll = el('button', 'btn btn-primary', 'Approve all & start the jury'); approveAll.type = 'button';
    const approveSelected = el('button', 'btn', 'Apply decisions & start the jury'); approveSelected.type = 'button';
    actions.append(approveAll, approveSelected); panel.appendChild(actions);
    const submit = async (all) => {
      if (busy || externalBusy || !canSubmit()) return;
      busy = true; updateBusy(); status.textContent = 'Submitting the approved specification…';
      const mine = generation;
      try {
        // “Approve all” resets rejected choices, but preserves deliberate edits.
        const selected = controls.map(({ item, choice, text }) => ({ id: item.id, decision: all && choice.value !== 'edit' ? 'approve' : choice.value, text: text.value }));
        const decisions = approvalDecisions(selected, trust.checked);
        const result = await client.approve(draft.id, decisions);
        if (disposed || mine !== generation) return;
        status.textContent = result.authority_label;
        await onAccepted?.(result);
      } catch (err) { if (!disposed && mine === generation) status.textContent = err.message; }
      finally { busy = false; updateBusy(); }
    };
    approveAll.addEventListener('click', () => submit(true));
    approveSelected.addEventListener('click', () => submit(false));
    updateBusy();
  }
  for (const input of Object.values(inputs)) input.addEventListener('input', () => {
    if (draft) { draft = null; generation += 1; panel.replaceChildren(); status.textContent = 'Inputs changed. Draft the specification again.'; }
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (busy || externalBusy || !canSubmit()) return;
    busy = true; updateBusy(); draft = null; panel.replaceChildren();
    const mine = ++generation;
    status.textContent = 'Interpreter (cloud, spec only) is drafting requirements…';
    try {
      const payload = Object.fromEntries(Object.entries(inputs).map(([key, input]) => [key, input.value]));
      const result = await client.infer(payload);
      if (disposed || mine !== generation) return;
      draft = result; status.textContent = 'Draft ready. Review it, then approve the checks.'; renderDraft();
    } catch (err) { if (!disposed && mine === generation) status.textContent = err.message; }
    finally { busy = false; updateBusy(); }
  });
  return { setBusy(value) { externalBusy = Boolean(value); updateBusy(); }, dispose() { disposed = true; generation += 1; } };
}
