/**
 * CodeJury Evidence Matrix, Candidate Inspector, and Event Timeline (stage1.v1)
 * Strictly renders code via textContent; handles property oracles and execution outcomes.
 */
import { renderHistory } from './history.mjs';
import { TERMINAL_STATUSES } from './state.mjs';

export function renderDiffLines(diffText) {
  const container = document.createElement('div');
  container.className = 'diff-view';
  if (!diffText) {
    container.textContent = '(No diff — baseline source)';
    return container;
  }

  const lines = diffText.split('\n');
  for (const line of lines) {
    const lineEl = document.createElement('span');
    if (line.startsWith('+') && !line.startsWith('+++')) {
      lineEl.className = 'diff-add';
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      lineEl.className = 'diff-del';
    }
    lineEl.textContent = line + '\n';
    container.appendChild(lineEl);
  }
  return container;
}

export function formatOracleBadge(test) {
  const badge = document.createElement('span');
  if (test.oracle_status === 'authoritative') {
    badge.className = 'badge badge-success';
    badge.textContent = test.oracle_kind === 'property' ? 'Property (Auth)' : 'Literal (Auth)';
  } else if (test.oracle_status === 'proposed') {
    badge.className = 'badge badge-warn';
    badge.textContent = 'Proposed';
  } else {
    badge.className = 'badge badge-neutral';
    badge.textContent = 'Observation Only';
  }
  return badge;
}

export function formatOutcomeBadge(outcome) {
  const badge = document.createElement('span');
  // CRITICAL RULE: observed is never given a green pass badge
  if (outcome === 'pass') {
    badge.className = 'badge badge-success';
    badge.textContent = 'PASS';
  } else if (outcome === 'observed') {
    badge.className = 'badge badge-neutral';
    badge.textContent = 'OBSERVED';
  } else if (outcome === 'fail') {
    badge.className = 'badge badge-danger';
    badge.textContent = 'FAIL';
  } else if (outcome === 'timeout') {
    badge.className = 'badge badge-warn';
    badge.textContent = 'TIMEOUT';
  } else if (outcome === 'error') {
    badge.className = 'badge badge-danger';
    badge.textContent = 'ERROR';
  } else {
    badge.className = 'badge badge-neutral';
    badge.textContent = 'PENDING';
  }
  return badge;
}

export function mountEvidenceView(candidatesContainer, executionContainer, store, client) {
  if (!candidatesContainer || !executionContainer) return;

  let selectedExecution = null;
  let inspectedRunId = null;
  let transcript = null;
  let transcriptRunId = null;
  let lastState = null;

  const drawHistory = (state) => {
    renderHistory(document.getElementById('progress-container'), state.events, state.runSnapshot, transcript,
      (box) => renderTimeline(box, state.events, state.runSnapshot));
  };

  store.subscribe((state) => {
    lastState = state;
    const snap = state.runSnapshot;
    if ((snap?.run_id || null) !== inspectedRunId) {
      selectedExecution = null;
      inspectedRunId = snap?.run_id || null;
      transcript = null;
    }
    // Model outputs are stored when the run finishes; fetch them once per run.
    if (snap && TERMINAL_STATUSES.includes(snap.status) && transcriptRunId !== snap.run_id && client?.getTranscript) {
      transcriptRunId = snap.run_id;
      const runId = snap.run_id;
      client.getTranscript(runId).then((data) => {
        if (inspectedRunId !== runId) return;
        transcript = data;
        if (lastState) drawHistory(lastState);
      }).catch((err) => console.warn('Transcript unavailable:', err.message));
    }
    renderCandidates(candidatesContainer, snap);
    const onSelect = (exec, test, cand) => {
      selectedExecution = { exec, test, cand };
      renderExecutionMatrix(executionContainer, snap, selectedExecution, onSelect);
    };
    renderExecutionMatrix(executionContainer, snap, selectedExecution, onSelect);
    drawHistory(state);
  });
}

function renderCandidates(container, snap) {
  container.innerHTML = '';
  if (!snap || !snap.candidates || snap.candidates.length === 0) {
    const p = document.createElement('p');
    p.className = 'placeholder-label';
    p.textContent = 'No candidates generated yet. Awaiting run start.';
    container.appendChild(p);
    return;
  }

  const list = document.createElement('div');
  list.className = 'candidates-list';

  snap.candidates.forEach((cand) => {
    const card = document.createElement('div');
    card.className = 'candidate-card';

    const header = document.createElement('div');
    header.className = 'candidate-header';

    const titleBox = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = `${cand.candidate_id} (${cand.origin})`;
    titleBox.appendChild(title);

    const sha = document.createElement('span');
    sha.className = 'cand-sha';
    sha.textContent = ` SHA: ${cand.source_sha256.slice(0, 12)}…`;
    titleBox.appendChild(sha);
    header.appendChild(titleBox);

    // Eligibility badge
    const eligBadge = document.createElement('span');
    if (cand.eligibility === 'eligible') {
      eligBadge.className = 'badge badge-success';
      eligBadge.textContent = 'Eligible';
    } else if (cand.eligibility === 'rejected') {
      eligBadge.className = 'badge badge-danger';
      eligBadge.textContent = 'Rejected';
    } else {
      eligBadge.className = 'badge badge-neutral';
      eligBadge.textContent = 'Pending';
    }
    header.appendChild(eligBadge);
    card.appendChild(header);

    if (cand.diagnosis) {
      const diag = document.createElement('p');
      diag.className = 'candidate-diag';
      diag.textContent = `Diagnosis: ${cand.diagnosis}`;
      card.appendChild(diag);
    }

    if (cand.rejection_reason) {
      const rej = document.createElement('p');
      rej.className = 'candidate-rejection';
      rej.textContent = `Rejection Reason: ${cand.rejection_reason}`;
      card.appendChild(rej);
    }

    // Diff
    const diffLabel = document.createElement('span');
    diffLabel.className = 'code-label';
    diffLabel.textContent = 'Source Diff:';
    card.appendChild(diffLabel);
    card.appendChild(renderDiffLines(cand.diff));

    const sourceDetails = document.createElement('details');
    sourceDetails.className = 'candidate-source';
    const summary = document.createElement('summary');
    summary.textContent = 'Inspect full source';
    const source = document.createElement('pre');
    source.textContent = cand.source;
    sourceDetails.appendChild(summary);
    sourceDetails.appendChild(source);
    card.appendChild(sourceDetails);
    list.appendChild(card);
  });

  container.appendChild(list);
}

function renderExecutionMatrix(container, snap, selectedExecution, onSelect) {
  const previousTable = container.querySelector('.table-responsive');
  const scrollLeft = previousTable?.scrollLeft || 0;
  const scrollTop = previousTable?.scrollTop || 0;
  container.innerHTML = '';
  if (!snap || !snap.tests || snap.tests.length === 0) {
    const p = document.createElement('p');
    p.className = 'placeholder-label';
    p.textContent = 'No test executions available yet.';
    container.appendChild(p);
    return;
  }

  const tests = snap.tests;
  const candidates = snap.candidates || [];
  const executions = snap.executions || [];

  // Build matrix lookup: `${cand_id}:${test_id}` -> execution
  const execMap = new Map();
  for (const ex of executions) {
    execMap.set(`${ex.candidate_id}:${ex.test_id}`, ex);
  }

  const tableWrapper = document.createElement('div');
  tableWrapper.className = 'table-responsive';
  tableWrapper.setAttribute('tabindex', '0');
  tableWrapper.setAttribute('aria-label', 'Scrollable execution matrix');

  const table = document.createElement('table');
  table.className = 'matrix-table';

  // Table header
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  const thCorner = document.createElement('th');
  thCorner.textContent = 'Candidate';
  headerRow.appendChild(thCorner);

  tests.forEach((t) => {
    const th = document.createElement('th');
    th.className = 'matrix-col-header';
    const nameEl = document.createElement('div');
    nameEl.textContent = t.test_id;
    th.appendChild(nameEl);
    th.appendChild(formatOracleBadge(t));
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  // Table body
  const tbody = document.createElement('tbody');
  candidates.forEach((cand) => {
    const row = document.createElement('tr');
    const tdCand = document.createElement('td');
    tdCand.innerHTML = `<strong>${cand.candidate_id}</strong> <br><small class="text-dim">${cand.origin}</small>`;
    row.appendChild(tdCand);

    tests.forEach((t) => {
      const td = document.createElement('td');
      td.className = 'matrix-cell';
      const exec = execMap.get(`${cand.candidate_id}:${t.test_id}`);
      const outcome = exec ? exec.outcome : 'pending';
      const badge = formatOutcomeBadge(outcome);

      const cellBtn = document.createElement('button');
      cellBtn.className = 'matrix-cell-btn';
      cellBtn.appendChild(badge);
      cellBtn.setAttribute('aria-label', `View execution for ${cand.candidate_id} on ${t.test_id}`);
      if (onSelect && exec) {
        cellBtn.addEventListener('click', () => onSelect(exec, t, cand));
      }
      td.appendChild(cellBtn);
      row.appendChild(td);
    });

    tbody.appendChild(row);
  });
  table.appendChild(tbody);
  tableWrapper.appendChild(table);
  container.appendChild(tableWrapper);
  tableWrapper.scrollLeft = scrollLeft;
  tableWrapper.scrollTop = scrollTop;

  // Counterexample drilldown inspector
  const drilldownBox = document.createElement('div');
  drilldownBox.className = 'counterexample-inspector';

  if (selectedExecution && selectedExecution.exec) {
    const { exec, test, cand } = selectedExecution;
    drilldownBox.innerHTML = `
      <div class="drilldown-header">
        <h3>Execution Inspection: <code>${exec.execution_id}</code></h3>
        <span class="badge badge-neutral">${cand.candidate_id} on ${test.test_id}</span>
      </div>
      <div class="drilldown-grid">
        <div><strong>Test Oracle:</strong> ${test.oracle_kind} (${test.oracle_status})</div>
        <div><strong>Outcome:</strong> <span class="badge ${exec.outcome === 'pass' ? 'badge-success' : exec.outcome === 'observed' ? 'badge-neutral' : 'badge-danger'}">${exec.outcome.toUpperCase()}</span></div>
        <div><strong>Duration:</strong> ${exec.duration_ms} ms</div>
        <div><strong>Input Mutated:</strong> ${exec.input_mutated ? '⚠️ Yes (Illegal)' : 'No'}</div>
      </div>
      <div class="drilldown-detail">
        <label>Input Arguments:</label>
        <pre><code>${escapeHtml(JSON.stringify(test.args, null, 2))}</code></pre>
      </div>
      <div class="drilldown-detail">
        <label>${test.oracle_kind === 'property' ? 'Approved Property Oracle:' : 'Expected Literal Output:'}</label>
        <pre><code>${test.oracle_kind === 'property' ? escapeHtml(test.property_id || 'Approved property') : escapeHtml(JSON.stringify(test.expected, null, 2))}</code></pre>
      </div>
      <div class="drilldown-detail">
        <label>Actual Candidate Output:</label>
        <pre><code>${escapeHtml(JSON.stringify(exec.actual_output, null, 2))}</code></pre>
      </div>
      ${exec.exception_type ? `<div class="drilldown-detail"><label>Exception Type:</label> <code>${escapeHtml(exec.exception_type)}</code></div>` : ''}
      ${exec.trace && exec.trace.length > 0 ? `<div class="drilldown-detail"><label>Execution Trace:</label><pre><code>${escapeHtml(exec.trace.join('\n'))}</code></pre></div>` : ''}
    `;
  } else {
    drilldownBox.innerHTML = `
      <p class="placeholder-label">Click any execution cell in the matrix above to inspect counterexample inputs, actual outputs, and execution traces.</p>
    `;
  }

  container.appendChild(drilldownBox);
}

function renderTimeline(container, events, snap) {
  if (!container) return;
  container.innerHTML = '';

  const headerNotice = document.createElement('div');
  headerNotice.className = 'timeline-notice';
  headerNotice.textContent = 'Factual execution event log — NOT hidden chain-of-thought or learned Judge reasoning';
  container.appendChild(headerNotice);

  if (!events || events.length === 0) {
    const p = document.createElement('p');
    p.className = 'placeholder-label';
    p.textContent = snap ? `Current phase: ${snap.phase} (${snap.status})` : 'Timeline idle.';
    container.appendChild(p);
    return;
  }

  const timeline = document.createElement('div');
  timeline.className = 'timeline';

  events.forEach((ev) => {
    const item = document.createElement('div');
    item.className = 'timeline-item';

    const time = document.createElement('span');
    time.className = 'timeline-time';
    time.textContent = ev.timestamp_utc ? ev.timestamp_utc.split('T')[1]?.replace('Z', '') : `#${ev.event_id}`;
    item.appendChild(time);

    const content = document.createElement('div');
    content.className = 'timeline-content';

    const typeBadge = document.createElement('span');
    typeBadge.className = 'badge badge-neutral';
    typeBadge.textContent = ({
      run_started: 'Case opened', original_checked: 'Baseline checked',
      candidate_created: 'Patch proposed', execution_completed: 'Test executed',
      test_admitted: 'Check admitted', test_rejected: 'Proposal rejected',
      revision_requested: 'Revision requested', run_finished: 'Case closed'
    })[ev.type] || ev.type;
    content.appendChild(typeBadge);

    const msg = document.createElement('span');
    msg.className = 'timeline-msg';
    msg.textContent = ` ${ev.payload?.message || ''}`;
    content.appendChild(msg);

    if (ev.payload?.evidence_ids && ev.payload.evidence_ids.length > 0) {
      const evIds = document.createElement('small');
      evIds.className = 'timeline-evidence text-dim';
      evIds.textContent = ` [Evidence: ${ev.payload.evidence_ids.join(', ')}]`;
      content.appendChild(evIds);
    }

    item.appendChild(content);
    timeline.appendChild(item);
  });

  container.appendChild(timeline);
}

function escapeHtml(str) {
  if (typeof str !== 'string') return String(str);
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
