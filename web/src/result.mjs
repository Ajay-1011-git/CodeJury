/**
 * CodeJury Verdict, Report Export, and Verifiable Artifacts (stage1.v1)
 * Exports genuine report JSON and candidate source without fabricated prose.
 */

export function mountResultView(container, store, client) {
  if (!container) return;

  store.subscribe((state) => {
    const snap = state.runSnapshot;
    renderResultView(container, snap);
  });
}

export function renderResultView(container, snap) {
  container.innerHTML = '';

  if (!snap) {
    const p = document.createElement('p');
    p.className = 'placeholder-label';
    p.textContent = 'Awaiting run completion. Verdict will appear once run reaches a terminal state.';
    container.appendChild(p);
    return;
  }

  const status = snap.status;

  if (['queued', 'running'].includes(status)) {
    const progressBox = document.createElement('div');
    progressBox.className = 'callout callout-info';
    progressBox.innerHTML = `
      <strong>Run in Progress:</strong> Phase: <code>${snap.phase}</code>. Polling backend evidence...
    `;
    container.appendChild(progressBox);
    return;
  }

  // Terminal States
  const resultCard = document.createElement('div');
  resultCard.className = 'verdict-wrapper';

  if (status === 'supported_patch') {
    const decision = snap.decision;
    const selectedId = decision?.selected_candidate_id;
    const selectedCand = (snap.candidates || []).find(c => c.candidate_id === selectedId);

    const banner = document.createElement('div');
    banner.className = 'callout callout-success';
    banner.innerHTML = `
      <h3>✅ Supported Patch Verified</h3>
      <p>Candidate <code>${selectedId}</code> passed all authoritative tests within verification scope without mutating input.</p>
    `;
    resultCard.appendChild(banner);

    // Decision scope
    const scopeBox = document.createElement('div');
    scopeBox.className = 'result-detail-box';
    scopeBox.innerHTML = `
      <h4>Verification Scope & Decision</h4>
      <p><strong>Reason:</strong> ${escapeHtml(decision?.reason || '')}</p>
      <p><strong>Authoritative Tests Passed:</strong></p>
      <ul>
        ${(decision?.verification_scope || []).map(t => `<li><code>${escapeHtml(t)}</code></li>`).join('')}
      </ul>
    `;
    resultCard.appendChild(scopeBox);

    // Usage summary
    if (snap.usage) {
      const u = snap.usage;
      const usageBox = document.createElement('div');
      usageBox.className = 'result-usage-box';
      usageBox.innerHTML = `
        <h4>Actual Resource Usage</h4>
        <div class="usage-grid">
          <div><span>Elapsed Time:</span> <strong>${u.elapsed_ms} ms</strong></div>
          <div><span>Input Tokens:</span> <strong>${u.input_tokens}</strong></div>
          <div><span>Output Tokens:</span> <strong>${u.output_tokens}</strong></div>
          <div><span>Executions:</span> <strong>${u.function_executions}</strong></div>
          <div><span>Peak Memory:</span> <strong>${u.peak_memory_mb !== null ? `${u.peak_memory_mb} MB` : 'N/A'}</strong></div>
        </div>
      `;
      resultCard.appendChild(usageBox);
    }

    // Selected code preview & action buttons
    if (selectedCand) {
      const codeBox = document.createElement('div');
      codeBox.className = 'selected-code-preview';
      codeBox.innerHTML = `
        <h4>Selected Candidate Source Code: <code>${selectedCand.candidate_id}</code></h4>
        <pre><code id="selected-source-code">${escapeHtml(selectedCand.source)}</code></pre>
      `;
      resultCard.appendChild(codeBox);

      // Actions
      const btnBar = document.createElement('div');
      btnBar.className = 'action-button-bar';

      const copyBtn = document.createElement('button');
      copyBtn.id = 'btn-copy-patch';
      copyBtn.className = 'btn btn-secondary';
      copyBtn.textContent = 'Copy Patch Source';
      copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(selectedCand.source).then(() => {
          copyBtn.textContent = '✓ Copied!';
          setTimeout(() => { copyBtn.textContent = 'Copy Patch Source'; }, 2000);
        });
      });
      btnBar.appendChild(copyBtn);

      const downloadPyBtn = document.createElement('button');
      downloadPyBtn.id = 'btn-download-source';
      downloadPyBtn.className = 'btn btn-secondary';
      downloadPyBtn.textContent = 'Download Source (.py)';
      downloadPyBtn.addEventListener('click', () => {
        downloadBlob(selectedCand.source, `repaired_${selectedId}.py`, 'text/x-python');
      });
      btnBar.appendChild(downloadPyBtn);

      const downloadJsonBtn = document.createElement('button');
      downloadJsonBtn.id = 'btn-download-report';
      downloadJsonBtn.className = 'btn btn-primary';
      downloadJsonBtn.textContent = 'Download Report JSON';
      downloadJsonBtn.addEventListener('click', () => {
        downloadBlob(JSON.stringify(snap, null, 2), `codejury-report-${snap.run_id}.json`, 'application/json');
      });
      btnBar.appendChild(downloadJsonBtn);

      resultCard.appendChild(btnBar);
    }
  } else if (status === 'unresolved') {
    const decision = snap.decision;
    const banner = document.createElement('div');
    banner.className = 'callout callout-danger';
    banner.innerHTML = `
      <h3>❌ Unresolved — No Supported Patch Discovered</h3>
      <p>Iteration budget exhausted without satisfying all contract requirements.</p>
    `;
    resultCard.appendChild(banner);

    const infoBox = document.createElement('div');
    infoBox.className = 'result-detail-box';
    infoBox.innerHTML = `
      <p><strong>Reason:</strong> ${escapeHtml(decision?.reason || snap.termination_reason || 'No candidate satisfied oracles.')}</p>
      ${decision?.unresolved_requirements?.length ? `<p><strong>Unresolved Requirements:</strong></p><ul>${decision.unresolved_requirements.map(r => `<li><code>${escapeHtml(r)}</code></li>`).join('')}</ul>` : ''}
    `;
    resultCard.appendChild(infoBox);

    // Download report JSON is permitted, but NO copy patch button
    const btnBar = document.createElement('div');
    btnBar.className = 'action-button-bar';
    const downloadJsonBtn = document.createElement('button');
    downloadJsonBtn.id = 'btn-download-report';
    downloadJsonBtn.className = 'btn btn-secondary';
    downloadJsonBtn.textContent = 'Download Run Snapshot JSON';
    downloadJsonBtn.addEventListener('click', () => {
      downloadBlob(JSON.stringify(snap, null, 2), `codejury-report-${snap.run_id}.json`, 'application/json');
    });
    btnBar.appendChild(downloadJsonBtn);
    resultCard.appendChild(btnBar);
  } else {
    // cancelled, infrastructure_error, invalid_input
    const banner = document.createElement('div');
    banner.className = 'callout callout-danger';
    banner.innerHTML = `
      <h3>Terminal Outcome: ${escapeHtml(status.toUpperCase())}</h3>
      <p>${escapeHtml(snap.termination_reason || snap.decision?.reason || 'Run concluded without patch selection.')}</p>
    `;
    resultCard.appendChild(banner);

    const btnBar = document.createElement('div');
    btnBar.className = 'action-button-bar';
    const downloadJsonBtn = document.createElement('button');
    downloadJsonBtn.id = 'btn-download-report';
    downloadJsonBtn.className = 'btn btn-secondary';
    downloadJsonBtn.textContent = 'Download Snapshot JSON';
    downloadJsonBtn.addEventListener('click', () => {
      downloadBlob(JSON.stringify(snap, null, 2), `codejury-report-${snap.run_id}.json`, 'application/json');
    });
    btnBar.appendChild(downloadJsonBtn);
    resultCard.appendChild(btnBar);
  }

  // Stage 2 boundary notification
  const stage2Notice = document.createElement('div');
  stage2Notice.className = 'stage2-deferred-notice';
  stage2Notice.innerHTML = `
    <small>Stage 2 Modules Deferred: Fixer B multi-candidate synthesis, learned Judge oracle arbitration, adversarial auditor, and tree-search MCTS.</small>
  `;
  resultCard.appendChild(stage2Notice);

  container.appendChild(resultCard);
}

function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function escapeHtml(str) {
  if (typeof str !== 'string') return String(str);
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
