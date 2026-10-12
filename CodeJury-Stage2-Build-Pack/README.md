# CodeJury — Complete Stage 2 Build Pack

Start from the ORIGINAL Stage1. You do not need to implement the optional Stage1 quality upgrade first. This pack completes the agreed architecture: complementary Fixers A/B, trained Critic/Judge, AST search, mutation-gap investigation, full local application and research evaluation.

## Read and distribute

1. Read **CodeJury-Stage2-Plan-and-Merge.md** together. Audit actual Stage1 code and preserve working modules.
2. Ajay receives **CodeJury-Stage2-Ajay.md** plus unchanged contracts/, reference/ and the common training/evaluation specification.
3. Sarvesh receives **CodeJury-Stage2-Sarvesh.md** plus the identical supporting folders/specification.
4. Both read **CodeJury-Stage2-Training-and-Evaluation.md** before collecting data or launching jobs.
5. Seed one common contract/ports/constraints commit before branching. Each guide has12 detailed tasks with explicit ownership, dependencies and VERIFY requirements.

Ajay owns model runtime, A/B/Judge training, orchestration/API/ledger and integration. Sarvesh owns oracle/domain/sandbox tools, AST search/auditor, Critic/general training, research harness and UI. Both own hard backend/learning work. Comparable workload does not mean exactly equal hours.

## Existing repository seed

From this downloaded pack directory, using your actual repository path:

```bash
python3 tools/seed_stage2.py --repo /actual/path/to/codejury
python3 tools/seed_stage2.py --repo /actual/path/to/codejury --apply
```

First command is a no-write preview. Inspect paths before applying. The helper requires the original known Stage1 schema and refuses conflicts/symlinks. It preserves original Stage1 schema/checksum/fixtures/application code, adds contracts/stage2.schema.json, contracts/STAGE2-SHA256SUMS and contracts/stage2-fixtures/, copies the frozen Python ports and creates reference/stage2/ copies. It does not modify runtime data or implement the project.

The downloaded pack keeps its samples under contracts/fixtures/ for packaging. Inside the real repository use the explicitly versioned contracts/stage2-fixtures/ directory and STAGE2-SHA256SUMS; keep the old Stage1 checker/fixtures separate. Stage2 project checkers must select these paths, not accidentally validate Stage1 samples against the new schema.

Before branching the custodian also inspects actual dependency versions, seeds shared compatible constraints/package discovery and records the common commit SHA. Then use separate clones/worktrees for stage2/ajay-core and stage2/sarvesh-tools. Edit only your module; merge at E1–E4 checkpoints. No automatic push/deployment/publication is authorized by these documents.

## Independent versus coupled work

Both halves implement and CPU-check independently with schema-valid fixtures at the ModelPort/ToolPort/RolloutPort/BaselinePort seam. Fixtures never count as real student failures, training or performance results. Actual coupled episodes and Judge labels need E2/E3 real artifact exchange; final evaluation needs all trained roles/general baseline frozen at E4. One Mac runs only one resident inference/training/teacher job at a time through the common compute lock.

Project-owned codejury.* commands in the guides are interfaces to implement/wrap, not tools already installed. Inspect actual upstream APIs/--help before using them. If hardware checks cannot run, mark them pending.

## Optional instruction-pack validation

Use an existing environment with jsonschema or a temporary isolated venv:

```bash
python3 -m venv /tmp/codejury-stage2-pack-check
/tmp/codejury-stage2-pack-check/bin/python -m pip install jsonschema
/tmp/codejury-stage2-pack-check/bin/python tools/validate_pack.py
```

This validates documents/contracts/synthetic examples only. Candidate sources are parsed and hashed, never executed on the host. It does not train models or measure CodeJury.

**Release truth:** all four learned roles and functional tools are required. Strong single-agent comparison, ablations and three-seed paired analysis are separate research gates. A negative/inconclusive result remains visible; no architecture can guarantee a score or superiority. All supplied API patches, training losses and benchmark counts are invented fixtures; public RunCreate examples are input seeds, not promised live repairs.
