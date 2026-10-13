# Copy this prompt into Codex on Sarvesh's Apple Silicon Mac

Take over CodeJury from Ajay's exact training checkpoint and complete the remaining
training, integration, audit, final benchmark and project release. Work autonomously
through implementation, fixes, testing, commits and pushing main. Do not stop at a
plan or ask routine confirmation. Preserve existing work and report genuine blockers.

Repository: https://github.com/Ajay-1011-git/CodeJury (main).
Private saved weights: https://github.com/Ajay-1011-git/CodeJury-training-handoff,
release `training-snapshot-2026-10-13`; Ajay must grant access if needed.

Read the repository instructions and
`backend/docs/stage2_core/teacher/continuation-handoff.md` fully before proceeding.
That handoff contains the exact restore, environment, isolation, training, freeze,
benchmark and packaging commands. Treat it as the operational continuation plan.

First preserve any local Sarvesh changes on a backup branch/commit. Clone or safely
pull main without force-resetting or discarding local changes. Ajay's and Sarvesh's
earlier work is already merged; do not reintroduce superseded branch implementations.

Exact resumption requires Ajay's directly transferred
`codejury-training-private-2026-10-13.tar.gz` (2.1 GB) and its `.sha256` sidecar. The
GitHub adapter download alone lacks the private corpora, ledgers, base model and
budget/cache state. Receive the full bundle through direct local transfer, verify
its SHA-256, then from the CodeJury root run:

```sh
python3.11 backend/tools/stage2_core/training_snapshot.py restore \
  --archive /absolute/path/to/codejury-training-private-2026-10-13.tar.gz
export CODEJURY_STAGE2_ORIGINAL_ROOT=/Users/ajay_macm5/Desktop/CodeJury
```

Keep that export set for training and services. The restorer verifies all 13,475
files and the checked-in source, refuses conflicting bytes, and preserves frozen
manifests. Never search-and-replace archived paths or bypass hash checks. Snapshot
source is commit `48cde63`; later handoff-only documentation commits retain matching
source hashes. If the full bundle is missing, complete independent setup/checks and
request that specific bundle rather than regenerating or inventing training evidence.

Recreate Python 3.11.16 and the pinned dependencies from
`handoff-metadata/runtime-requirements.txt`, including MLX 0.32.3, MLX-LM 0.32.0 and
Transformers 5.19.0; install backend editable without changing those versions. Use
real Apple Silicon MLX, not CPU fixtures. Load the two transferred Docker images into
the dedicated no-host-mount/no-agent-forwarding Colima profile, verify their identities
and run all fresh isolation checks described in the handoff. Preserve original proofs.
Serialize native work with `ComputeLease`; never delete or steal a compute lock.

Do not rerun completed teacher collection, A training or Judge continuation collection.
Teacher A step 50 is selected (6/20 solves versus 5/20, zero wrong accepts); step 100
was rejected. B's original trained weights and new-A mining/pair evidence are preserved.
Current Critic passed compatibility validation. Judge collection completed 536 actual
continuations across 96 states and stopped at a clean phase boundary; no optimizer
job is interrupted. Earlier Judge and 550-update General jobs are retained baselines.

From backend, resume the dependent pipeline:

```sh
.venv/bin/python -m codejury.stage2_core.teacher.cli complete-training \
  --config config/stage2_core/teacher.yaml
```

This must produce new real Judge labels/pilot/full/executable selection, then the
teacher-aware General corpus/pilot/full/executable selection and measured completion
token parity within 10%. Reuse completed phases; diagnose failures and preserve
immutable old jobs. Never call an independent fresh job a resumed optimizer run.
No Groq API key is needed for these next offline phases. If later teacher collection
is justified, keep keys local, preserve the shared 41-attempt/$0.0063987 ledger and
the original 60-attempt/$1 cap across all keys; halt on unknown usage. Never send
private validation/final/reference material to the teacher or add Groq to live repair.

Then finish the entire project: validate the compatible five-adapter registry and
opportunity proof, switch runtime only after quality gates pass, update evaluation
opportunity placeholders, run backend/frontend/frozen-contract and native method
checks, and exercise the real API/UI repair/revision/queue/cancel/restart/unresolved/
download flows. Fix and audit real failures while preserving frozen interfaces.

Create a clean E4 freeze only after these gates. Keep final data sealed during
development. Run the single real final benchmark using the declared 16 method/regime
plans, ten independent bases and three seeds (480 actual runs), committing outcomes
before scoring. Respect consumption markers after failures/interruption; do not tune
on final outcomes or reset the seal. Report improved, inconclusive or worse honestly.

Package the genuine portable five-adapter release with matching completed benchmark,
freeze and role identities. Finish model/data cards, reproducible instructions and
aggregate reports. Merge remaining fixes safely and push main. Keep weight releases
private unless Ajay explicitly approves public distribution. Automatic approval review
blocked public weights and remote upload of the complete case-containing bundle;
use the permitted private adapter transfer and direct local full-state transfer.

Completion means real selected training, working merged app, passed acceptance,
finished final benchmark, verified release and pushed documentation/code—not merely
an implemented trainer or saved weights. Return exact commit/release links, actual
test/native evidence, measured results and any remaining genuine limitations.
