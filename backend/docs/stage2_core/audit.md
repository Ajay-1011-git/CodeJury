# Stage 2 core audit and handoff

## A2.01 — audited common seed

Starting commit: `635e43e2e072455ade1e49ee0a480c60dd665f82` (published Stage 2 pack).
Common seed commit: `4ef438566fa8c28243e686ab4057a1c1104ddfce`.

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

## A2.02 — verified durable state, budgets and compute lease

Implementation branch: `codex/stage2-ajay-core`, created from the common seed
above. The diff after that seed is restricted to Ajay's `stage2_core` source,
tests, configuration and documentation. Shared schemas, ports, constraints,
legacy modules and Sarvesh's code remain unchanged.

The new strict JSON boundary wrappers cover ModelPort, ToolPort, RolloutPort and
BaselinePort. Inputs/outputs are copied and validated against the canonical
schema; unknown keys, bool/float counters, nonfinite values and mismatched
response identities are rejected. Exact UTF-8 source hashing is separate from
sorted canonical JSON hashing. Cache identity includes the source, complete
test, reviewed oracle, sandbox runtime and resource profile hashes.

The SQLite ledger uses explicit immediate transactions, full synchronization
and append-only triggers for events, candidate/test/execution/probe evidence and
cache rows. Sources and trace blobs are content addressed, fsynced and published
atomically; reading an object verifies its bytes. Event IDs are allocated inside
transactions. Candidate admission checks source/signature/provenance/requirements,
parent identity and exact two-edit reconstruction, retaining intermediate source
artifacts. Only the controller can later qualify candidates; every newly admitted
CandidateDraft is pending, including schema-valid fixture candidates that were
previously labelled eligible. Qualification/selection belongs to later tasks.

Tool results must match the dispatched operation, ID prefix, candidate/test
scope, registered parents and reviewed oracle requirements. Related inputs need
two actual effect records for completed relation results. Extra reported shrink,
replay and probe costs are charged, never reduced to the number of returned
executions. Refused tool evidence rolls back candidate/evidence changes but its
reported resources are charged once, persisted and the account stops further
dispatch. Untrusted cost reports cannot establish exact actual resource usage;
they fail closed and require an infrastructure outcome from the later controller.

The budget authority reserves final qualification executions before further
investigation, checks per-dispatch ceilings, charges model/Judge attempts before
generation and prevents double accounting when a model response also reports
that attempt. Episode wall time uses a monotonic clock, not a sum of operation
timers. Budget checkpoints persist counters and the last measured elapsed time.
After a crash, elapsed time is a recorded lower bound and in-flight cost can be
unknown; recovered runs terminate as infrastructure_error with no selected patch
and never resume generation. Crash recovery does not claim completed execution.

The compute lease uses a stable kernel-locked inode. Default location is
`/private/tmp/codejury-compute-<uid>.lock`, shared across this user's clones and
worktrees. Runtime, training, teacher and benchmark jobs use the same lease.
PID/owner/job metadata describes the holder; the kernel lock determines actual
ownership, so stale/PID-reused metadata cannot block recovery. Cancellation tokens
are checked before acquisition and forwarded through the boundary wrappers.
The native worker integration and stopping an active model remain A2.03 work.

Verification actually run from `backend/`:

```text
python -m pytest tests/stage2_core/test_state.py -q
40 passed (last focused run: 1.66s)
python -m pytest -m 'not sandbox and not mac' -q
146 passed, 9 hardware tests deselected in 6.81s
python -m codejury.stage2_core.ledger_cli self-test --out artifacts/stage2_core/ledger-test.json
passed: 11 independent CPU bookkeeping checks
python -m codejury.stage2_core.contract_check --contracts ../contracts
83 definitions; 49 synthetic fixtures; schema/ports checksums unchanged
python -m codejury.contracts.check ../contracts
8 original fixtures passed; Stage 1 schema unchanged
ruff check src/codejury/stage2_core tests/stage2_core tools/stage2_core
All checks passed
```

The focused suite kills a real child holding the compute lease, races separate
SQLite connections, crashes a process inside an uncommitted transaction, and
tests duplicate settlements, source tampering, bad tool hashes/references,
two-edit provenance, cancellation, relation/shrink costs and cache reuse. All
model/tool responses are explicitly synthetic fixtures: these checks establish
state/accounting behavior, not inference, repair accuracy or trained role quality.

Audit corrections: refused tool outputs now retain their attempted resource
costs; model attempt counts are charged once despite appearing in response usage;
concurrent content-addressed writes publish complete files atomically; persisted
usage survives restart; all ledger/budget locks use a consistent acquisition order.

Next: A2.03, one-base native multi-adapter worker and real raw/A/raw/A switching.
B, Critic, Judge and general adapters are still absent and must not be replaced by
raw inference or fixtures in a live registry. No learning job or private final
assessment was run in A2.01–A2.02. Task commits are local; no automatic push.
