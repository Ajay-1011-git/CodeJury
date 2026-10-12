/**
 * CodeJury Training & Benchmark Evaluation Visualizer (stage1.v1)
 * Renders real backend loss curves via lightweight SVG and evaluation comparison table.
 * Strictly avoids hardcoded metrics or fabricated curves.
 */

export function validateEvaluationData(evalRows) {
  if (!Array.isArray(evalRows)) return { valid: false, error: 'Evaluation data must be an array' };
  for (const row of evalRows) {
    if (row.total < 0 || row.solved < 0 || row.unresolved < 0 || row.incorrect_accepted < 0) {
      return { valid: false, error: 'Evaluation counters cannot be negative' };
    }
    if (row.solved > row.total) {
      return { valid: false, error: `Malformed evaluation row: solved (${row.solved}) exceeds total (${row.total})` };
    }
    if (row.solved + row.unresolved + row.incorrect_accepted !== row.total) {
      return { valid: false, error: `Malformed evaluation row: partition sum does not equal total (${row.total})` };
    }
  }
  return { valid: true };
}

export function generateLossSvg(lossPoints, width = 600, height = 240) {
  if (!lossPoints || lossPoints.length === 0) {
    return '<p class="placeholder-label">No loss data points available.</p>';
  }

  // Filter valid points
  const validSteps = lossPoints.map(p => p.step);
  const minStep = Math.min(...validSteps);
  const maxStep = Math.max(...validSteps);
  const stepSpan = maxStep - minStep || 1;

  const validTrain = lossPoints.filter(p => typeof p.train_loss === 'number').map(p => p.train_loss);
  const validVal = lossPoints.filter(p => typeof p.validation_loss === 'number').map(p => p.validation_loss);
  const allLosses = [...validTrain, ...validVal];

  if (allLosses.length === 0) {
    return '<p class="placeholder-label">No numeric loss values recorded.</p>';
  }

  const minLoss = 0;
  const maxLoss = Math.max(...allLosses) * 1.1 || 1;
  const lossSpan = maxLoss - minLoss;

  const padding = { top: 20, right: 30, bottom: 35, left: 50 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  function toX(step) {
    return padding.left + ((step - minStep) / stepSpan) * plotW;
  }

  function toY(loss) {
    return padding.top + plotH - ((loss - minLoss) / lossSpan) * plotH;
  }

  // Paths
  let trainPath = '';
  let valPath = '';

  lossPoints.forEach((p, idx) => {
    const x = toX(p.step);
    if (typeof p.train_loss === 'number') {
      const y = toY(p.train_loss);
      trainPath += (trainPath ? ` L ${x.toFixed(1)} ${y.toFixed(1)}` : `M ${x.toFixed(1)} ${y.toFixed(1)}`);
    }
    if (typeof p.validation_loss === 'number') {
      const y = toY(p.validation_loss);
      valPath += (valPath ? ` L ${x.toFixed(1)} ${y.toFixed(1)}` : `M ${x.toFixed(1)} ${y.toFixed(1)}`);
    }
  });

  return `
    <svg viewBox="0 0 ${width} ${height}" class="loss-chart-svg" style="width: 100%; height: auto; max-height: 280px;">
      <!-- Grid & Axes -->
      <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}" stroke="#2b3952" stroke-width="1" />
      <line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" stroke="#2b3952" stroke-width="1" />

      <!-- Axis Labels -->
      <text x="${padding.left - 10}" y="${padding.top + 5}" fill="#64748b" font-size="10" text-anchor="end">${maxLoss.toFixed(2)}</text>
      <text x="${padding.left - 10}" y="${height - padding.bottom}" fill="#64748b" font-size="10" text-anchor="end">0.00</text>
      <text x="${padding.left}" y="${height - padding.bottom + 18}" fill="#64748b" font-size="10">Step ${minStep}</text>
      <text x="${width - padding.right}" y="${height - padding.bottom + 18}" fill="#64748b" font-size="10" text-anchor="end">Step ${maxStep}</text>

      <!-- Curves -->
      ${trainPath ? `<path d="${trainPath}" fill="none" stroke="#38bdf8" stroke-width="2" />` : ''}
      ${valPath ? `<path d="${valPath}" fill="none" stroke="#a855f7" stroke-width="2" stroke-dasharray="4" />` : ''}

      <!-- Legend -->
      <g transform="translate(${width - 220}, 15)">
        <line x1="0" y1="0" x2="20" y2="0" stroke="#38bdf8" stroke-width="2" />
        <text x="26" y="4" fill="#94a3b8" font-size="11">Training Loss</text>
        <line x1="110" y1="0" x2="130" y2="0" stroke="#a855f7" stroke-width="2" stroke-dasharray="4" />
        <text x="136" y="4" fill="#94a3b8" font-size="11">Validation Loss</text>
      </g>
    </svg>
  `;
}

export function mountTrainingView(container, store, client) {
  if (!container) return;

  function loadReport() {
    client.getTrainingReport()
      .then((report) => {
        store.set({ trainingReport: report });
        renderTrainingReport(container, report);
      })
      .catch((err) => {
        container.innerHTML = `
          <div class="callout callout-danger">
            Failed to retrieve training report: ${escapeHtml(err.message)}
          </div>
        `;
      });
  }

  store.subscribe((state) => {
    if (state.trainingReport) {
      renderTrainingReport(container, state.trainingReport);
    }
  });

  loadReport();
}

export function renderTrainingReport(container, report) {
  container.innerHTML = '';
  if (!report) {
    container.innerHTML = '<p class="placeholder-label">Awaiting training report...</p>';
    return;
  }

  const wrapper = document.createElement('div');
  wrapper.className = 'training-report-wrapper';

  // Header status banner
  const statusBanner = document.createElement('div');
  const isFixture = report.runtime_mode === 'fixture';
  statusBanner.className = `callout ${report.status === 'completed' ? 'callout-success' : 'callout-info'}`;
  statusBanner.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
      <div>
        <strong>Training Status:</strong> <span class="badge ${report.status === 'completed' ? 'badge-success' : 'badge-neutral'}">${report.status.toUpperCase()}</span>
      </div>
      ${isFixture ? '<span class="badge badge-warn">Synthetic Fixture Metrics</span>' : '<span class="badge badge-neutral">Recorded local evaluation</span>'}
    </div>
    <p style="margin-top: 0.4rem; font-size: 0.85rem;">${escapeHtml(report.provenance_note || 'Report from backend.')}</p>
  `;
  wrapper.appendChild(statusBanner);

  // Model & Dataset Metadata Grid
  const metaGrid = document.createElement('div');
  metaGrid.className = 'training-meta-grid';
  metaGrid.innerHTML = `
    <div class="meta-card">
      <span class="meta-label">Model ID</span>
      <strong class="meta-value">${report.model_id ? escapeHtml(report.model_id) : '—'}</strong>
    </div>
    <div class="meta-card">
      <span class="meta-label">Model Revision</span>
      <strong class="meta-value">${report.model_revision ? escapeHtml(report.model_revision) : '—'}</strong>
    </div>
    <div class="meta-card">
      <span class="meta-label">Adapter SHA-256</span>
      <strong class="meta-value cand-sha">${report.adapter_sha256 ? `${report.adapter_sha256.slice(0, 16)}…` : 'None (Raw baseline)'}</strong>
    </div>
    <div class="meta-card">
      <span class="meta-label">Train Records / Steps</span>
      <strong class="meta-value">${report.train_records} records / ${report.steps} steps</strong>
    </div>
    <div class="meta-card">
      <span class="meta-label">Dataset Split (Train / Val / Eval)</span>
      <strong class="meta-value">${report.train_base_problems} / ${report.validation_base_problems} / ${report.evaluation_base_problems} problems</strong>
    </div>
  `;
  wrapper.appendChild(metaGrid);

  // If training not started
  if (report.status === 'not_started' || (!report.loss_points?.length && !report.evaluation?.length)) {
    const unmeasuredBox = document.createElement('div');
    unmeasuredBox.className = 'callout callout-info';
    unmeasuredBox.innerHTML = `
      <h4>Not Yet Measured</h4>
      <p>Training and benchmark evaluation metrics await Ajay's backend training run. Empty metrics are honestly displayed without simulated curves or fabricated results.</p>
    `;
    wrapper.appendChild(unmeasuredBox);
    container.appendChild(wrapper);
    return;
  }

  // Loss Curve Section
  if (report.loss_points && report.loss_points.length > 0) {
    const lossSection = document.createElement('div');
    lossSection.className = 'loss-section';
    lossSection.innerHTML = `
      <h3 style="margin-bottom: 0.5rem; font-size: 1rem;">Optimization Trajectory (Cross-Entropy Loss)</h3>
      <div class="loss-chart-box">
        ${generateLossSvg(report.loss_points)}
      </div>
    `;
    wrapper.appendChild(lossSection);
  }

  // Evaluation Table Section
  if (report.evaluation && report.evaluation.length > 0) {
    const valResult = validateEvaluationData(report.evaluation);
    if (!valResult.valid) {
      const errBox = document.createElement('div');
      errBox.className = 'callout callout-danger';
      errBox.textContent = `Evaluation data integrity error: ${valResult.error}`;
      wrapper.appendChild(errBox);
    } else {
      const evalSection = document.createElement('div');
      evalSection.className = 'eval-section';
      evalSection.innerHTML = `
        <h3 style="margin-top: 1rem; margin-bottom: 0.5rem; font-size: 1rem;">Measured Evaluation (${report.evaluation_base_problems} assessment problems)</h3>
        <div class="table-responsive">
          <table class="eval-table">
            <thead>
              <tr>
                <th>Method</th>
                <th>Total</th>
                <th>Solved</th>
                <th>Unresolved</th>
                <th>Incorrect Accepted</th>
                <th>Pass Rate (%)</th>
                <th>Mean Latency</th>
                <th>Mean Tokens</th>
              </tr>
            </thead>
            <tbody>
              ${report.evaluation.map((r) => {
                const passRate = r.total > 0 ? ((r.solved / r.total) * 100).toFixed(1) : '0.0';
                const latency = r.mean_elapsed_ms !== null ? `${r.mean_elapsed_ms} ms` : '—';
                const tokens = r.mean_output_tokens !== null ? `${r.mean_output_tokens}` : '—';
                const methodLabel = r.method === 'raw_single' ? 'Raw Model (Single-Shot)'
                  : r.method === 'trained_a_single' ? 'Trained Fixer A (Single-Shot)'
                  : 'Stage 1 Loop (Fixer A + Oracles)';
                return `
                  <tr>
                    <td><strong>${escapeHtml(methodLabel)}</strong></td>
                    <td>${r.total}</td>
                    <td><strong class="text-success">${r.solved}</strong></td>
                    <td>${r.unresolved}</td>
                    <td>${r.incorrect_accepted}</td>
                    <td><span class="badge ${r.solved > 0 ? 'badge-success' : 'badge-neutral'}">${passRate}%</span></td>
                    <td>${latency}</td>
                    <td>${tokens}</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      `;
      wrapper.appendChild(evalSection);
    }
  }

  container.appendChild(wrapper);
}

function escapeHtml(str) {
  if (typeof str !== 'string') return String(str);
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
