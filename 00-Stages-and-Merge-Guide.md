# CodeJury — Two-Stage Plan, Merge Guide and Professor Evidence

**Team:** Ajay + Sarvesh. **Now:** implement Stage 1 only. **Later:** Stage 2.  
Grounded in finalized architecture v2.0, with no change to the final four-role research goal.

## 1. What “50% complete” means

Use ten agreed deliverable milestones, each assigned 10 completion points. Stage1 implements M1–M5; Stage2 implements M6–M10. This is a planning-based completion measure, not a claim about equal hours, lines of code, accuracy, or research novelty. Stage2 may require more experimental effort. Obtain professor agreement on the milestone rubric before claiming the percentage as their grading standard.

| Milestone | Stage | Completion evidence | Points |
|---|---|---|---:|
| M1 Safe execution and durable run lifecycle | 1 | Sandbox tests, original-failure reproduction, immutable records |10|
| M2 Real local model repair service | 1 | Native inference, schema API, generated candidate and error/cancel paths |10|
| M3 Initial learning pipeline | 1 | Leak-free dataset, trained/reloaded Fixer A, training card and actual evaluation |10|
| M4 Executable critique/revision prototype | 1 | Approved property challenge, concrete counterexample, bounded revision and evidence selection |10|
| M5 Integrated application and measured demonstration | 1 | UI on live backend, patch/report export, actual results and reproducible demo |10|
| M6 Complementary Fixer B | 2 | Failure-focused adapter, independent input view, rescue-rate experiment |10|
| M7 Learned Critic | 2 | Valid/discriminating test training and false-rejection evaluation |10|
| M8 Targeted AST repair search | 2 | Bounded search, provenance, budget accounting and search ablation |10|
| M9 Mutation-audited investigation | 2 | Surviving-probe gap state, approved counterexamples and audit ablation |10|
| M10 Learned Judge and full research evaluation | 2 | Action-outcome training, full integration, equal-tool/budget baselines and ablations |10|

Do not mark an entire milestone done for a scaffold. Missing real adapter or missing live repair means the relevant Stage1 milestone remains incomplete. A fixture-only UI does not constitute 50% of this project.

## 2. Stage boundaries

Stage1 delivers a useful vertical slice: one trained A, raw/prompted Critic, fixed controller, authoritative supplied/approved-property tests, sandbox, database, API, UI, and preliminary assessment. No B is silently simulated. Four adapters, learned scheduling, audit feedback, and AST synthesis remain final architecture goals.

The Stage1 subset supports a single pure function with bounded integer/list-integer positional inputs. Other architecture types, helpers and approved dependency imports arrive only through a later versioned scope amendment. This temporary restriction does not erase the final architecture's wider JSON domain.

Stage2 is outlined to place the whole project; this pack contains no Stage2 implementation prompts. Its full build documents must inspect the actual merged Stage1 code and issue a contract amendment before adding new wire fields.

## 3. Work allocation

| Area | Ajay | Sarvesh |
|---|---|---|
| Backend/API/schema validation | Own | Consume frozen API |
| Sandbox/model worker | Own | No model/sandbox jobs |
| Training data and split manifests | Own technical pipeline and validation | Optional contract wording/edge-case review |
| Fixer A training/checkpoints | Own real Mac jobs | Display real training report |
| Critique/property/revision loop | Own | Render actual actions/evidence |
| UI/mock API/browser behaviour | No frontend edits before merge | Own |
| Demo examples | Validate and maintain public backend examples | Propose readable demo descriptions |
| Initial evaluation | Own execution/metrics | Render exact metrics and prepare explanatory visuals |
| Integration | Own merge/static-mount wiring | Help browser acceptance, without backend edits |

Sarvesh gets the easier workload by design. There is no requirement that both people do equal compute/training work. Each can complete and prove their module independently through fixtures or CLI/API evidence.

## 4. Seed repository before parallel work

Create one Git repository with `contracts/` and `reference/` copied byte-for-byte from this pack. Put generated code in the owned backend/web directories. Save the common commit SHA in both handoff notes. Do not split into two unrelated repositories with independently recreated contracts.

Suggested branch names: `stage1/ajay-backend`, `stage1/sarvesh-ui`. Both branch from the same common commit. Each developer may use their own clone or worktree. No repo URL, remote, or account has been provided; use the team's actual remote, never an invented GitHub address. Committing locally does not authorize automated pushing or publishing by a coding agent.

No shared root lockfile during isolated work. Backend and UI manifests stay in their directories. Ajay owns root README/integration scripts only after merge. The frozen seam checksum is in contracts/SHA256SUMS.

## 5. Merge procedure

1. Each runs their own task/acceptance checks, records real output and a commit ID, and reports only backend/** or web/** changed. Reject accidental contract changes before merge.
2. Create integration branch from the shared base and merge Ajay's branch, then Sarvesh's. Example Git commands below use actual local branch names; inspect existing branches first. If both edited root/frozen files, resolve ownership by restoring canonical seed rather than selecting whichever version looks newer.
3. Ajay mounts the now-present web directory from the backend using FastAPI's verified StaticFiles API, after registering API routes. Locate web relative to repository structure, not hardcoded /Users/Ajay paths. Keep routes available when web is absent during backend tests.
4. UI default same-origin connects to live backend at localhost8000. Do not launch Sarvesh's mock for the live acceptance. Mock remains a dev tool.
5. Validate fixtures and backend response schemas again; run backend CPU tests, actual sandbox/model smoke tests and frontend tests. Inspect health for live mode, model/sandbox ready and trained A. Read the real training report.
6. Submit a public task, observe original failure, model candidate, authoritative test outcomes and result. Verify downloaded patch hash against selected candidate, no Stage2 completion labels, correct fixture-free live screen, and real training metrics.
7. Cancel a running job and exercise an invalid-input/unresolved path. Retain actual screenshots/report JSONs and reproduction commands. Tag a completed Stage1 release only when all M1–M5 evidence exists.

```bash
git switch -c stage1/integration <actual-shared-base-sha>
git merge --no-ff stage1/ajay-backend
git merge --no-ff stage1/sarvesh-ui
```

These are local integration commands, not claims that branches already exist. Do not cherry-pick only the visible UI and omit training artefacts/handoff. Large weights remain local; collaborators exchange checkpoint manifests and download/transfer bytes through an agreed method.

## 6. Professor-facing Stage1 output

Required real outputs after implementation:

- A working local browser application on the Mac connected to the real backend.
- A saved, identifiable Fixer A LoRA adapter with a genuine training log and reload verification.
- A before/after repair example with a reproduced supplied failure and actual passing checks for the selected patch.
- An executed property counterexample or challenge evidence, with provenance and revision shown if it actually occurred.
- A downloaded selected Python source and visible JSON evidence report.
- A preliminary comparison table for raw single-shot, trained A single-shot, and Stage1 loop, containing actual solved/total and costs.
- A clear slide/checklist of five completed milestones and the five Stage2 milestones pending.

Suggested statement: “We have completed the first five of ten agreed deliverable milestones: local repair execution, a trained initial Fixer, verified challenge/revision, and the integrated evidence UI. The complementary agent training, repair search, mutation auditor and learned investigation policy are Stage2.”

Do not say “our full council beats a single model” based on Stage1. Do not claim recorded/synthetic repairs are live. Raw-vs-loop budgets differ; explain that Stage1 evaluation is preliminary. Full matched-tool and budget research comparisons come in Stage2.

## 7. Stage2 overview and training responsibilities

Ajay owns B failure mining and training, Critic execution-filtered training, Judge alternative-action labels/training, AST search and auditor core, and full evaluation. Sarvesh owns richer multi-candidate/audit/policy views, benchmark report presentation and reviewed demo/data support. Rebalance only if their experience changes; the harder learning infrastructure stays with Ajay by default.

Training order: freeze A → mine training-only A failures → train B with general-data mixture → collect A/B disagreements/shared failures → train Critic on valid executable challenges → implement search/audit and collect alternative-action continuations → train Judge → freeze all checkpoints → sealed final evaluation. Stage1 internal assessment results are development evidence; keep a separate final Stage2 holdout.

No automatic online training in live runs. Paid teachers can accelerate collection but the required path stays execution-validated local/reference data. No quality equivalence is assumed between free and paid data sources.

## 8. Pack contents and usage

Give Ajay `01-Stage1-Ajay-Build.md`; give Sarvesh `02-Stage1-Sarvesh-Build.md`. Each also receives the unchanged contracts and reference folders. Shared contract and fixtures are part of each standalone guide's assumed seed repository. Read this overview for milestone accounting, assignment and integration. The fifth document is a fixture/contract check report generated while preparing this pack, not a result of building CodeJury.

## 9. Source verification and anti-hallucination boundary

Official MLX-LM LoRA docs, FastAPI tutorial, Colima repository, Docker run reference and Hypothesis quickstart were checked while preparing this pack. Installed versions/flags still must be inspected by the builder. Project-owned codejury.* CLI commands are task specifications to implement. Do not mistake them for existing tools. No Mac training, real candidate execution, or model evaluation has been performed as part of creating these documents.

Sources: [MLX-LM LoRA](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md), [FastAPI](https://fastapi.tiangolo.com/tutorial/), [Colima](https://github.com/abiosoft/colima), [Docker run](https://docs.docker.com/reference/cli/docker/container/run/), [Hypothesis quickstart](https://hypothesis.readthedocs.io/en/latest/quickstart.html). Final architecture contains further model/dataset sources.
