/**
 * CodeJury Input and Contract Specification Component (stage1.v1)
 * Safely renders code via textContent; validates exact schema types before POST.
 */

export const APPROVED_PROPERTIES = Object.freeze({
  sort_ascending_ints: {
    name: 'sort_ascending_ints',
    description: 'Output is a list of integers, nondecreasing, with identical input/output multiplicities.'
  },
  unique_preserve_order_ints: {
    name: 'unique_preserve_order_ints',
    description: 'Output contains exactly first occurrences, in input order.'
  },
  sum_ints: {
    name: 'sum_ints',
    description: 'Output is an integer equal to the specified mathematical sum.'
  }
});

/**
 * Validates a candidate RunCreate object against exact Stage 1 rules before serialization.
 */
export function validateRunCreatePayload(payload, propertyApproved = false) {
  const errors = [];

  if (!payload || typeof payload !== 'object') {
    return { valid: false, errors: ['Payload must be an object'] };
  }

  if (payload.schema_version !== 'stage1.v1') {
    errors.push("schema_version must be 'stage1.v1'");
  }

  if (!payload.source || typeof payload.source !== 'string' || payload.source.trim().length === 0) {
    errors.push('Source code must be a non-empty string');
  } else if (payload.source.length > 24000) {
    errors.push('Source code exceeds 24,000 character maximum');
  }

  if (!payload.function_name || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(payload.function_name)) {
    errors.push('Function name must be a valid Python identifier (letters, digits, underscore, starting with letter/underscore)');
  }

  if (!payload.contract_text || typeof payload.contract_text !== 'string' || payload.contract_text.trim().length === 0) {
    errors.push('Contract text must be a non-empty string');
  } else if (payload.contract_text.length > 8000) {
    errors.push('Contract text exceeds 8,000 character maximum');
  }

  // Input domains
  if (!Array.isArray(payload.input_domain) || payload.input_domain.length < 1 || payload.input_domain.length > 3) {
    errors.push('input_domain must contain between 1 and 3 domain descriptors');
  } else {
    payload.input_domain.forEach((d, idx) => {
      if (!['integer', 'list_integer'].includes(d.kind)) {
        errors.push(`input_domain[${idx}].kind must be 'integer' or 'list_integer'`);
      }
      if (typeof d.min !== 'number' || typeof d.min === 'boolean' || !Number.isInteger(d.min)) {
        errors.push(`input_domain[${idx}].min must be an integer`);
      }
      if (typeof d.max !== 'number' || typeof d.max === 'boolean' || !Number.isInteger(d.max)) {
        errors.push(`input_domain[${idx}].max must be an integer`);
      }
      if (Number.isInteger(d.min) && Number.isInteger(d.max)) {
        if (d.min > d.max) {
          errors.push(`input_domain[${idx}] min (${d.min}) cannot be greater than max (${d.max})`);
        }
        if (d.min < -1000 || d.max > 1000) {
          errors.push(`input_domain[${idx}] bounds must lie within [-1000, 1000]`);
        }
      }

      if (d.kind === 'integer') {
        if (d.min_length !== null || d.max_length !== null) {
          errors.push(`input_domain[${idx}] integer domain requires min_length and max_length to be null`);
        }
      } else if (d.kind === 'list_integer') {
        if (typeof d.min_length !== 'number' || typeof d.min_length === 'boolean' || !Number.isInteger(d.min_length) || d.min_length < 0) {
          errors.push(`input_domain[${idx}].min_length must be an integer >= 0`);
        }
        if (typeof d.max_length !== 'number' || typeof d.max_length === 'boolean' || !Number.isInteger(d.max_length) || d.max_length < 0) {
          errors.push(`input_domain[${idx}].max_length must be an integer >= 0`);
        }
        if (Number.isInteger(d.min_length) && Number.isInteger(d.max_length)) {
          if (d.min_length > d.max_length) {
            errors.push(`input_domain[${idx}] min_length (${d.min_length}) cannot exceed max_length (${d.max_length})`);
          }
          if (d.max_length > 30) {
            errors.push(`input_domain[${idx}] max_length cannot exceed 30`);
          }
        }
      }
    });
  }

  // Supplied tests
  if (!Array.isArray(payload.supplied_tests) || payload.supplied_tests.length < 1 || payload.supplied_tests.length > 30) {
    errors.push('supplied_tests must contain between 1 and 30 tests');
  } else {
    const seenTestIds = new Set();
    payload.supplied_tests.forEach((t, idx) => {
      if (!t.test_id || typeof t.test_id !== 'string') {
        errors.push(`supplied_tests[${idx}] must have a non-empty test_id`);
      } else {
        if (seenTestIds.has(t.test_id)) {
          errors.push(`Duplicate test_id detected: '${t.test_id}'`);
        }
        seenTestIds.add(t.test_id);
      }
      if (!Array.isArray(t.args)) {
        errors.push(`supplied_tests[${idx}].args must be an array of arguments`);
      }
    });
  }

  // Approved property
  if (payload.approved_property !== null) {
    if (!Object.keys(APPROVED_PROPERTIES).includes(payload.approved_property)) {
      errors.push(`Unknown approved_property: '${payload.approved_property}'`);
    } else if (!propertyApproved) {
      errors.push(`Property '${payload.approved_property}' chosen but explicit consent checkbox was not approved`);
    }
  }

  if (payload.resource_profile !== 'stage1-demo') {
    errors.push("resource_profile must be 'stage1-demo'");
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

export function mountInputView(container, store, client) {
  if (!container) return;

  container.innerHTML = `
    <div class="input-form-wrapper">
      <div class="callout callout-info">
        <strong>Stage 1 Contract Subset:</strong> Pure functions with 1–3 integer or list-of-integer arguments.
        Bounds are restricted to [-1,000, 1,000], list lengths &le; 30. Imports, helpers, float values, decorators, and global state are forbidden.
      </div>

      <div class="form-row">
        <div class="form-group flex-1">
          <label class="form-label" for="example-select">Load Preset Example</label>
          <select id="example-select" class="form-control">
            <option value="">-- Choose an example task --</option>
          </select>
        </div>
        <div class="form-group flex-1">
          <label class="form-label" for="function-name-input">Python Function Name</label>
          <input type="text" id="function-name-input" class="form-control" placeholder="e.g. sort_ints" value="sort_ints">
        </div>
      </div>

      <div class="form-group">
        <label class="form-label" for="source-code-input">Buggy Source Code (Unmodified Input)</label>
        <textarea id="source-code-input" class="form-control code-editor" rows="7" placeholder="def sort_ints(items):\n    ..."></textarea>
      </div>

      <div class="form-group">
        <label class="form-label" for="contract-text-input">Contract Specification (Natural Language)</label>
        <textarea id="contract-text-input" class="form-control" rows="2" placeholder="Sort an integer list in non-decreasing order..."></textarea>
      </div>

      <div class="form-row">
        <div class="form-group flex-1">
          <label class="form-label" for="domain-json-input">Input Domain Descriptors (JSON)</label>
          <textarea id="domain-json-input" class="form-control" rows="4"></textarea>
        </div>
        <div class="form-group flex-1">
          <label class="form-label" for="tests-json-input">Supplied Literal Tests (JSON)</label>
          <textarea id="tests-json-input" class="form-control" rows="4"></textarea>
        </div>
      </div>

      <div class="property-selection-card">
        <label class="form-label" for="property-select">Approved Property Oracle (Optional)</label>
        <select id="property-select" class="form-control">
          <option value="">None (Supplied literal tests only)</option>
          <option value="sort_ascending_ints">sort_ascending_ints — Nondecreasing multiset equality</option>
          <option value="unique_preserve_order_ints">unique_preserve_order_ints — Unique elements in first-appearance order</option>
          <option value="sum_ints">sum_ints — Mathematical list sum</option>
        </select>
        <p id="property-desc" class="property-desc">No property oracle selected.</p>
        <div class="checkbox-group" id="consent-wrapper" style="display: none; margin-top: 0.5rem;">
          <input type="checkbox" id="property-consent-checkbox">
          <label for="property-consent-checkbox">
            <strong>Explicit Approval:</strong> I approve the selected property as an authoritative verification oracle for this task.
          </label>
        </div>
      </div>

      <div id="validation-error-box" class="callout callout-danger" style="display: none; margin-top: 1rem;"></div>

      <div class="form-actions" style="margin-top: 1.25rem; display: flex; gap: 0.75rem;">
        <button id="btn-submit-run" class="btn btn-primary">Start Verification Run</button>
        <button id="btn-cancel-run" class="btn btn-danger" disabled>Cancel Run</button>
      </div>
    </div>
  `;

  // References
  const exampleSelect = container.querySelector('#example-select');
  const funcNameInput = container.querySelector('#function-name-input');
  const sourceInput = container.querySelector('#source-code-input');
  const contractInput = container.querySelector('#contract-text-input');
  const domainInput = container.querySelector('#domain-json-input');
  const testsInput = container.querySelector('#tests-json-input');
  const propSelect = container.querySelector('#property-select');
  const propDesc = container.querySelector('#property-desc');
  const consentWrapper = container.querySelector('#consent-wrapper');
  const consentCheckbox = container.querySelector('#property-consent-checkbox');
  const errorBox = container.querySelector('#validation-error-box');
  const submitBtn = container.querySelector('#btn-submit-run');
  const cancelBtn = container.querySelector('#btn-cancel-run');

  // Load examples from API
  client.getExamples()
    .then((data) => {
      const examples = data.examples || [];
      examples.forEach((ex, idx) => {
        const opt = document.createElement('option');
        opt.value = ex.example_id;
        opt.textContent = `${ex.title} — ${ex.description.slice(0, 50)}...`;
        exampleSelect.appendChild(opt);
      });

      // Default to first example
      if (examples.length > 0) {
        populateFormFromExample(examples[0].request);
      }
    })
    .catch((err) => {
      console.warn('Could not load examples:', err.message);
    });

  function populateFormFromExample(req) {
    if (!req) return;
    funcNameInput.value = req.function_name || '';
    sourceInput.value = req.source || '';
    contractInput.value = req.contract_text || '';
    domainInput.value = JSON.stringify(req.input_domain || [], null, 2);
    testsInput.value = JSON.stringify(req.supplied_tests || [], null, 2);
    propSelect.value = req.approved_property || '';
    updatePropertyUI();
    if (req.approved_property) {
      consentCheckbox.checked = true;
    }
  }

  exampleSelect.addEventListener('change', () => {
    const selectedId = exampleSelect.value;
    if (!selectedId) return;
    client.getExamples().then((data) => {
      const ex = (data.examples || []).find(e => e.example_id === selectedId);
      if (ex && ex.request) {
        populateFormFromExample(ex.request);
      }
    });
  });

  function updatePropertyUI() {
    const propKey = propSelect.value;
    if (propKey && APPROVED_PROPERTIES[propKey]) {
      propDesc.textContent = APPROVED_PROPERTIES[propKey].description;
      consentWrapper.style.display = 'flex';
    } else {
      propDesc.textContent = 'No property oracle selected.';
      consentWrapper.style.display = 'none';
      consentCheckbox.checked = false;
    }
  }

  propSelect.addEventListener('change', updatePropertyUI);

  // Submit Handler
  submitBtn.addEventListener('click', async () => {
    errorBox.style.display = 'none';
    errorBox.textContent = '';

    let parsedDomain, parsedTests;
    try {
      parsedDomain = JSON.parse(domainInput.value);
    } catch {
      showError('Input Domain must be valid JSON');
      return;
    }

    try {
      parsedTests = JSON.parse(testsInput.value);
    } catch {
      showError('Supplied Tests must be valid JSON');
      return;
    }

    const payload = {
      schema_version: 'stage1.v1',
      source: sourceInput.value,
      function_name: funcNameInput.value.trim(),
      contract_text: contractInput.value.trim(),
      input_domain: parsedDomain,
      supplied_tests: parsedTests,
      approved_property: propSelect.value ? propSelect.value : null,
      resource_profile: 'stage1-demo'
    };

    const validation = validateRunCreatePayload(payload, consentCheckbox.checked);
    if (!validation.valid) {
      showError(validation.errors.join('; '));
      return;
    }

    try {
      await store.startRun(client, payload);
    } catch (err) {
      showError(`Submission failed: ${err.message}`);
    }
  });

  cancelBtn.addEventListener('click', () => {
    store.cancelRun(client);
  });

  function showError(msg) {
    errorBox.style.display = 'block';
    errorBox.textContent = msg;
  }

  // Subscribe to store updates for button states
  store.subscribe((state) => {
    const isRunning = state.runSnapshot && ['queued', 'running'].includes(state.runSnapshot.status);
    submitBtn.disabled = state.isSubmitting || isRunning;
    cancelBtn.disabled = !isRunning;
  });
}
