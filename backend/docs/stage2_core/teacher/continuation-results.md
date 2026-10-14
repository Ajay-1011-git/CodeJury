# Continuation results on Sarvesh's Mac — 13–14 October 2026

Measured on Sarvesh's Apple Silicon Mac after restoring Ajay's training snapshot (13,475 files
verified) with Python 3.11.16, MLX 0.32.3, MLX-LM 0.32.0 and Transformers 5.19.0. All numbers are
VALIDATION evidence: 20 runs over 10 validation base problems, seed 17. The sealed final pool has
not been opened. Twenty runs that share ten bases are a small sample; differences of one or two
solves are within run-to-run noise.

Raw outputs (ledgers, commitments, reports) are in ignored `backend/artifacts/stage2_core/teacher/`
and are not committed.

## Environment and isolation

- Colima 0.10.3 profile `codejury-stage1` (2 CPU, 2 GiB, aarch64). Colima regenerated a writable
  home mount in the Lima config on every `colima start`, which the runner correctly refused. The
  Lima config was set to `mounts: []` and the VM is started with
  `LIMA_HOME=$HOME/.colima/_lima limactl start colima-codejury-stage1`. Inside the VM: zero host
  mounts, no agent forwarding.
- Both transferred images loaded with the expected identities (`3a0eda85…`, `2e357513…`).
- Fresh runner self-test `sarvesh-runner-v2`: `overall: passed`, all 12 checks true.

## Dependent training (`complete-training`)

| Phase | Result |
|---|---|
| Judge corpus | `current-judge-corpus-v1` built from the completed continuations |
| Judge pilot / full | 20-update pilot and 100-update full job, reload verified |
| Judge selection | step 50; 10/10 valid choices and label matches on 10 validation records (5 states) |
| General v1 (550 updates) | refused: 88.8% / 87.0% valid choices at the two parity-comparable checkpoints |

Every one of the 76 Judge corpus targets is `abstain` with the same rationale. That limits what any
action policy trained on it can learn and is a known limitation of the current label set.

## Diagnosis and fixes (all on `stage2/sarvesh-continuation`)

1. **Omitted `state_id`.** Most invalid Judge/General drafts omitted the `state_id` echo, either as
   a missing key or as an opened-but-unwritten final key (`,"}`; `state_id` sorts last). Only those
   exact shapes are now restored from the controller's own state; a wrong id, other missing/extra
   keys and other malformed JSON still refuse, and every decision records `state_id_repair`.
   Replay over 768 recorded General outputs: 87 dangling and 18 omitted now parse; the single
   degenerate output still refuses. (`71497cf`, `5c9f61f`)
2. **Menu order.** The trained General agent picks the first option in most decisions (93/114). Its
   extra generate/search options were listed first, so it never reached the audit/challenge steps
   that make selection available. Canonical options now come first, as in the council. (`0c4b6bb`)
3. **Opening candidates.** The council opens with Fixer A's repair and Fixer B's reconstruction
   before any decision; General opened with none and abstained after one failed attempt. General now
   opens with one repair-view and one reconstruction-view candidate written by its own adapter.
   (`fa4110f`)
4. **Feedback revision.** A fixer candidate that failed the supplied tests, or never ran because
   static validation failed (e.g. calling an undefined helper), could not be revised. Each failed
   first-generation A/B candidate now gets one revision showing its own failing executions or the
   static-validation error; revisions are never chained. Validation of this change is pending.
   (`005177f`)

## Measured validation results

Council with the selected learned Judge (checkpoint 50):

| Controller code | Valid Judge choices | Fallbacks | Solved | Incorrect accepted |
|---|---|---|---|---|
| Before fix 1 | 58.4% (45/77) | 11 | 10/20 | 0 |
| Fix 1 (omitted key only) | 92.9% (52/56) | 1 | 11/20 | 0 |
| Fix 1 (both shapes) | 94.6% (53/56) | 1 | 9/20 | 0 |

The learned Judge also picks the first option in most decisions (43/56), so it behaves close to the
fixed controller; the Fixed-Judge ablation in the benchmark measures this directly.

General comparator (v2b weights: Judge-format records 50→150, 650 updates):

| Run | Checkpoint | Valid choices | Solved | Incorrect accepted | Status |
|---|---|---|---|---|---|
| v1 weights, no fixes | 500 / 550 | 88.8% / 87.0% | 0/20 | 0 | refused |
| v2b, no fixes | 500 / 550 | 88.5% / 81.4% | 0/20 | 0 | refused |
| v2c, fix 1 (omitted key) | 500 | 80.5% | 0/20 | 0 | refused |
| v2d, fix 1 (both shapes) | 500 | 98.2% | 0/20 | 0 | stopped |
| **v2f, fixes 1–3** | 500 | 98.7% (76/77) | 9/20 | 1 | candidate |
| **v2f, fixes 1–3** | **550** | **100% (70/70)** | **9/20** | **0** | **selected** |

v2f selected step 550: card `completed`, measured completion-exposure parity 2.0% (tolerance 10%).
21 of its 70 choices used the `state_id` restoration.

## Pending

- Validation of fix 4 (feedback revision) on the council and General. The final selected registry
  must come from the final controller code.
- Runtime/registry switch, evaluation opportunity values, full suites, API/UI acceptance, E4 freeze,
  the single sealed final benchmark and the release.
