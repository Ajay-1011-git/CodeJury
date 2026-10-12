# CodeJury — Complete Stage 2 Plan, Ownership and Merge Guide

**Team:** Ajay + Sarvesh. **Starting version:** original Stage1 stage1.v1; optional upgrade not implemented. **Target:** finalized architecture v2.0, four learned roles and mutation-audited investigation on Apple Silicon Mac. **Deliverable date:**12 October2026. These are build documents; no actual repository/model results were inspected here.

## 1. What Stage2 completes

M6 complementary failure-specialized FixerB; M7 execution-filtered learned Critic; M8 bounded AST repair search; M9 mutation auditor with valid gap-followup testing; M10 learned Judge, full integration and matched-tool/budget evaluation. Preserve/revalidate M1–M5 from original Stage1. Strengthen A validation, candidate sampling/revision and acceptance as needed inside Stage2; do not apply the abandoned quality upgrade first.

JSON types/helper/dependency support expand to the architecture's stated scope through the shared contract. Full repositories, floats without tolerance, nondeterministic/concurrency/performance-only repair and in-place effects remain outside architecture scope. No omitted core component is silently renamed optional. RL is the architecture's optional extension.

## 2. Balanced engineering split

| Area | Ajay | Sarvesh |
|---|---|---|
| Model runtime and adapter registry |Own native worker, scheduling,4-role switching|Consume ModelPort; standalone Critic/general training launcher|
| Repair learning |A validation/refresh, B failure mining/training|Independent Critic dataset/training, general comparator|
| Learned investigation |Action/state/controller; Judge alternatives/labels/training|Executable tool results/gaps feeding Judge|
| Program tools |Integrate ToolPort, no duplicate tools|Domain/codec/oracle, isolated runner facade, AST search, auditor, challenge/shrinking|
| API/persistence |Run lifecycle, ledger, reports,old-version exports|Mock API, evidence UI/report rendering|
| Research |Policy rollout and runtime/baseline adapters, training cost manifests|Sealed benchmark/assessment, baselines/ablations/statistics|
| Merge/release |Single integration custodian, package lock/routing|Browser/system acceptance and results/report handoff|

Each owns12 detailed tasks. Ajay's model/Judge/data/orchestration workload and Sarvesh's analysis/search/audit/Critic/evaluation workload are both substantial. Equal task count is not claimed equal time; exchange reviewed diagnostic/corpus writing if one side becomes blocked, but don't cross-edit implementation ownership.

## 3. One common seed before branching

Audit actual Stage1 repo/versions/model/data first. Preserve both owners' uncommitted work through local commits; no reset/overwrite. Custodian seeds this pack's new schema, STAGE2-SHA256SUMS and versioned stage2-fixtures/ plus readonly ports under backend/src/codejury/stage2_ports.py, legacy Stage1 schema/fixtures, reference docs and integration/stage2/README.md. Keep original Stage1 contracts/history for separate old-version release. Freeze common Python constraints from ACTUAL installed compatible dependencies; no invented pinned version table. Existing backend install must discover both new packages. Only the custodian edits package manifest/lock once before branches or at integration.

Commit common seed and save actual SHA. Branch stage2/ajay-core and stage2/sarvesh-tools from that same commit, using separate clones/worktrees. No shared edited checkout. Both receive their owner guide plus contracts/reference; canonical schema, ports and fixture bytes identical. Don't create unrelated repos. Actual remote/path supplied by team, never invented. After seed, owner-only diff is enforced by tests/handoff.

## 4. Integration and artifact checkpoints

| Checkpoint | Required handoff | Integration output |
|---|---|---|
| E0 Common seed/audit |Both original Stage1 audits; agreed hashes and model profile|One frozen contract/ports/constraints; missing foundation list|
| E1 CPU seam |Ajay A2.01–A2.04 skeleton/ports; Sarvesh S2.01–S2.06 tool facade|Schema-valid fake/model-tool calls and actual runner smoke after merge|
| E2 Fixers + tools |A2.05–A2.07 real A/B, fixed-policy episodes; S2.02–S2.07 real tools|Real training-only repair episodes for Critic and action collection|
| E3 Critic + Judge collection |S2.08 trained Critic; A2.08 frozen rollouts|Real audit/disagreement episodes and alternative-action labels; train Judge|
| E4 Learned application |A2.09–A2.12 Judge/API/integration; S2.09–S2.12 eval/general/UI|Four trained-role release, full baselines/ablations, browser/live evidence|

These checkpoints are dependencies, not dates. CPU module implementation can progress independently with fixture ports. Do not promise end-to-end learning can be honestly completed without exchanging real model/tool outputs. If one Mac is shared, schedule one exclusive native compute job at a time; code/CPU fixtures continue in parallel. Both can run standalone trainers using verified local MLX, but cannot train and infer simultaneously on the16GB profile.

Exchange immutable ArtifactManifest-validated files under ignored backend/artifacts/stage2-exchange/{owner}/. Training-pool records only cross into learning; hidden final assessment remains Sarvesh-owned private local data. Exchange weights through an agreed local/network method with checksums, not Git or pasted secret-bearing paths. Rejected/incompatible manifests stop that job; no guessed conversion. Same base/tokenizer/quantization/topology required.

## 5. Merge procedure and conflict policy

At each E checkpoint, commit completed owner work; integrator creates/checks integration branch from common seed, merges owner branches, runs schema/ports checks before native jobs. Fix owner defects on owner branch and remerge; do not patch both implementations in shared files. Incorporate common integration checkpoint before further independent work, keeping frozen contract unchanged. No broad unrelated reformat or duplicate model runner.

Ajay wires make_model_port/make_tool_port/app factory and makes the Stage2 boot command `python -m codejury.stage2_core.cli serve --config integration/stage2/runtime.yaml` available after merge. This is a project CLI to implement. Sarvesh's tools run through Python port, not a new microservice. API routes register before static mount. One package lock includes both owner dependency lists and verified common constraints. Separate modules keep imports from eagerly loading partner weights or launching services.

Run shared pack/contract checks, both CPU suites, actual sandbox tests, role-switch/native smoke and real end-to-end tests. Inspect every failure: no API response schema filtering-away invalid extra fields, no fake fallback on live startup. Preserve old Stage1 database/version records separately. New API uses stage2.v1 and typed409 for known archived old IDs, not rewritten history. Cancellation/kill/restart recovery tested on live workers.

## 6. Completion and quality are separate

Feature-complete: all M6–M10 components implemented,4 adapters genuinely trained/reloaded/evaluated, expanded domain/helper sandbox, gap-driven challenges, learned action validation, live UI, sealed research evaluation and reproducible release artifacts. Fixed controller is diagnostic baseline/fallback, not the finished learned-Judge claim.

Performance outcome: measure CodeJury against a strong general single-agent with the SAME tests/search/audit tools and comparable inference/training opportunities. Added agents alone do not establish superiority. If paired confidence intervals include no gain, report inconclusive; if worse, retain results and diagnose. A failed superiority hypothesis does not justify fake tests or missing components. No promised percentage/novelty score/full marks.

## 7. Final demonstration and evidence bundle

Show real Mac browser run with original failure, independent A/B provenance, admitted counterexample, audit gap that leads to actual investigation when available, AST repair, Judge actions/refusals, selected immutable patch and limits. Some components may not fire on one easy problem; use multiple disclosed live cases rather than forcing an action for theatre. Show unresolved/cancel/error and actual4-role adapter cards. Fixture rehearsal stays labelled.

Bundle actual commits, model/checkpoint/tokenizer/quantization/topology hashes, dataset/family splits/licenses, train/config logs, actual baseline/ablation records, per-seed clustered analysis, runtime/CPU memory/latency, limitations and reproduction commands. Hidden assessment sources stay separate from public bundle. Public benchmark provenance/pretraining contamination acknowledged. No report of correct patch from existence of an unselected candidate.

## 8. Pack navigation

CodeJury-Stage2-Ajay.md and CodeJury-Stage2-Sarvesh.md are standalone owner guides sharing identical contract. CodeJury-Stage2-Training-and-Evaluation.md specifies common training order, manifests, baselines and release gates. contracts/ holds machine schema/ports/synthetic fixture pairs. Original architecture/Stage1 guides are reference copies, not proof they were implemented. Validation report checks docs/fixtures, not models/project. Read this plan first, then owner guide.

## 9. Sources and unknowns

Current official sources checked: [MLX-LM LoRA](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md), [Python3.11 AST](https://docs.python.org/3.11/library/ast.html), [Hypothesis strategies](https://hypothesis.readthedocs.io/en/latest/reference/strategies.html), [FastAPI response models](https://fastapi.tiangolo.com/tutorial/response-model/), [Colima configuration](https://github.com/abiosoft/colima/blob/main/embedded/defaults/colima.yaml), [QuixBugs](https://github.com/jkoppel/QuixBugs), [EvalPlus](https://github.com/evalplus/evalplus), [Phi model card](https://huggingface.co/microsoft/Phi-4-mini-instruct). Installed APIs, exact model training support, dataset licenses and Mac throughput require live audit; no guessed upstream CLI flags are prescribed here.

## Additive seed helper

From the downloaded pack, run `python3 tools/seed_stage2.py --repo /actual/path/to/codejury` for a no-write preview, then the same with `--apply` after the path inventory matches the intended repo. It refuses unknown original schemas or conflicting existing Stage2 files. It keeps original Stage1 schema/checksum/fixtures and application code, adds Stage2 fixtures at contracts/stage2-fixtures/, and writes reference copies under reference/stage2/. Before coding, both read those reference copies; standalone pack guides use reference/ directly. The helper does not choose dependency versions, modify runtime data or create a Git commit; the custodian audits/seeds common constraints/package discovery and commits the shared seed.
