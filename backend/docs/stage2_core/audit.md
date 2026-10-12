# Stage 2 core audit and handoff

## A2.01 — audited common seed

Starting commit: `635e43e2e072455ade1e49ee0a480c60dd665f82` (published Stage 2 pack).
Common seed commit: locate with `git log --grep='A2.01' --format='%H %s'`;
the explicit SHA is recorded by the following task once that commit exists.

The actual Stage 1 implementation covers M1–M5, including integrated browser/API
acceptance in `docs/stage1-integration.md`. Original backend modules, web, schema,
fixtures, lock, weights, adapter and private datasets are preserved. The optional
quality-upgrade ZIP is untracked and unused. No stage1.v1.1 implementation found.

Observed on 12 October 2026: Python 3.11.16, Darwin ARM64, 17,179,869,184 bytes
memory; SQLite 3.53.1; FastAPI 0.143.0, Pydantic 2.14.0, jsonschema 4.26.0,
Hypothesis 6.169.0, MLX 0.32.3, MLX-LM 0.32.0, Uvicorn 0.54.0,
PyYAML 6.0.3, pytest 9.1.1, httpx 0.28.1, ruff 0.17.0. The common constraints
snapshot records 56 installed distributions. Existing `backend/uv.lock` remains
the install authority; no dependency or package-manifest change was necessary.
Hatch's existing `src/codejury` discovery includes both new namespaces; the
CPU-only bootstrap imports all four frozen ports without loading models.

Model revision `d848c30f6d5419b9892433cf6b1062626d15340e`; all six local model,
tokenizer/config/template hashes match the existing native smoke. Base weight hash:
`335fc22ddc8e9070a2359fa278c90e0cabdea0e31f16a4340524598abe0476d4`.
Selected adapter hash:
`274fd6b1a4a9abd04a8a2d3e56cfbde765c81e71fdb230682f4bf66509605fb4`;
selected step 100 from the actual 300-step trial. Recorded A/raw/A switching
passed in Stage 1; fresh native inference remains A2.03 work.

The existing dedicated runner is available. Docker inspected image
`sha256:2e357513b8bd95894224280a265c6d4153d160aca1bb1f57a6370d6ceaf9e9f5`
as ARM64. Actual VM `/proc/mounts` contained no `/Users`, virtiofs or sshfs
host shares. This audit did not execute any candidate or modify the VM.

The published Stage 1 assessment remains 1/10 solved, 9 unresolved, 0 incorrect
accepted for raw, trained A and loop. Raw malformed 9/10; trained A 0/10. Live
unique-preservation remains unresolved. Small-expression diagnoses still require
training-only investigation; no new failure classification is invented. Effects,
timeout/cancellation and adapter behavior have historical Stage 1 tests, with
Stage 2 expansion/reverification pending. The comparison's budgets differ.

Dataset manifest counts remain 40 train, 10 validation, 10 original assessment
bases, plus a previously authored 10-base Stage 2 final asset. The audit reads
manifest metadata and published aggregate results only, never private final
records. Original Stage 1 assessment is development evidence. Sarvesh must
review/seal a fresh Stage 2 final pool at S2.01 before model selection/jobs.

Verification actually run from `backend/`:

```text
python tools/stage2_core/audit.py --out artifacts/stage2_core/audit.json
Darwin arm64, 16 GiB; model_hashes_match=true; runner image/mount probes return 0
python -m codejury.stage2_core.contract_check --contracts ../contracts
83 definitions, 49 synthetic fixtures; frozen ports identical
Stage 2 schema: ee62388479918f0e33d4085d530dc210356ed104afe6170b1ff03687e53b6ee6
Ports: 524d0c0a5970fa6c46ee3137d1fa2c5b5bd13a0fa6e40d2f9abef66c6d157cd4
python -m codejury.contracts.check ../contracts
8 original Stage 1 fixtures; original schema hash unchanged
python -m pytest -m 'not sandbox and not mac' -q
106 passed, 9 hardware tests deselected in 5.10s
ruff check src/codejury/stage2_core tools/stage2_core ../integration/stage2/bootstrap.py
All checks passed
```

The default seed helper was previewed before applying. Stage 2 fixtures use
`contracts/stage2-fixtures`, with a separate checksum; no original fixture moved.
Full metadata/hashes remain in ignored `artifacts/stage2_core/audit.json`.

Implementation proceeds on Ajay's own branch from this shared seed; Sarvesh
must use a separate clone/worktree at the same seed. Ajay owns `stage2_core`
paths; no partner implementation or live placeholder role is added. Pending:
fresh native smoke, B/Critic/Judge training, Sarvesh tool/holdout audit, E1–E4
integration and final evaluation. A2.01 establishes metadata/CPU readiness only.

Validation and transaction APIs were checked against installed signatures and
the official [jsonschema documentation](https://python-jsonschema.readthedocs.io/en/stable/validate/),
[SQLite documentation](https://docs.python.org/3.11/library/sqlite3.html), and
[file-lock documentation](https://docs.python.org/3.11/library/fcntl.html).
