# CodeJury — Stage 2 Learning Jobs, Experiments and Release Gates

This specification supplements both owner guides and the identical shared contract. Start from original Stage1; the optional quality upgrade is not required. It prescribes real jobs to implement and run, not existing datasets, trained adapters or guaranteed results.

## 1. Learning order and responsibilities

| Order/job | Owner | Inputs | Real output | Dependency |
|---|---|---|---|---|
| T0 Corpus/holdout audit |Both; Ajay train pools, Sarvesh final holdout|Actual Stage1 manifests, reviewed new functions|Family-disjoint train/validation/final manifests and provenance|E0|
| T1 A validation/refresh |Ajay|Original A, raw base, validation tasks|Validated frozen A Card, optional improved adapter|A2.05|
| T2 B failure mining |Ajay|Frozen A, training problems,3fixed samples/problem|Actual A failure fractions and B sampling weights|T1 + real runner|
| T3 B SFT |Ajay|Independent-view targets, weighted failures plus general mix|Separate B adapter and paired A/B validation|T2|
| T4 Fixed episode collection |Ajay uses Sarvesh tools|A/B, approved tests, search/audit, raw Critic bootstrap|Actual TRAINING EpisodeBundles|E2|
| T5 Critic filtering/SFT |Sarvesh|T4 disagreements/shared failures/gaps/correct cases|Execution-filtered Critic data, trained Card and validity/false-rejection evaluation|T4|
| T6 Alternative-action collection |Ajay|Frozen A/B/Critic/tools, identical training states|Executed option continuations and offline outcome labels|E3|
| T7 Judge SFT |Ajay|Runtime state/menu, T6 action labels|Trained Judge and fixed-versus-learned validation|T6|
| T8 General comparator SFT |Sarvesh|Authorized A/B/Critic/Judge records|One general adapter with comparable aggregate opportunity|All role records frozen|
| T9 Sealed final evaluation |Sarvesh runs harness, Ajay audits runtime parity|Frozen five adapter manifests, tools/configs/heldout|All baseline/ablation/seed results, clustered analysis|E4 + T8|

The product has four learned roles. General is the research comparator, not a fifth jury member. Training these jobs on one Mac is sequential; code/CPU tests can progress in parallel. A trained Critic/Judge is mandatory for final architecture completion. RL is an optional extension, never a substitute for SFT or a completion gate.

## 2. Data inventory and truthful collection targets

Preserve original problem/family/near-duplicate lineage. Split before generating corruptions, views, teacher answers or episodes. Correct source and hidden TRAINING assessment validate training targets but are never runtime inputs. Final references/tests remain Sarvesh-owned private data. Any Stage1 assessment previously inspected during development is no longer final evidence.

| Data | Collection target | What a smaller genuine dataset means |
|---|---|---|
| Repair corpus |Several hundred reviewed training base functions, target300; validation target60|Report actual training diversity; do not promise broad mastery from a tiny adapter|
| Final assessment |At least200 distinct heldout base problems if corpus supports it|Small preliminary research result with wide uncertainty; no padded counts|
| B sampling |3A generations per training base problem|Actual sample count/provenance and uncertainty recorded|
| Critic records |Target800 validated records, at least25% correct-candidate/no-objection and10% invalid/conflicting proposals|Actual smaller counts/mix stated; role training can be genuine but limited|
| Judge states |Target200 states across at least60 independent training problems,2–3continuation seeds|Limited empirical action supervision if fewer; repeated states are not extra base problems|

These are goals, not existing files or deadlines. Base problems are distinct behavioural tasks; a dozen mutations of one sum function remain one base problem. Include algorithmic bugs that AST operators cannot fix and natural mistakes if available; otherwise label the collection synthetic. Keep a heldout mutation-family subset so the engine is not evaluated only on its own inverse edits.

QuixBugs remains a small external repair benchmark, not a source of independent thousands of examples. HumanEval+/MBPP+ through EvalPlus are optional repair adaptations, with buggy-input construction and licensing documented. Public benchmark contamination in base-model pretraining is a stated limitation; add independently authored tasks. Unsupported input types, imports, helper semantics and performance-only problems are excluded by a frozen preflight rule before methods run, with exclusion counts. Method crashes/abstentions during eligible tasks remain unsolved in the denominator.

## 3. Training record and validation rules

Each offline example stores base_problem_id, family_id, split, provenance/license, exact source/target hashes, runtime-view JSON/prompt hash, approved contract/tests, private training assessment reference, actual failure evidence and target response. Add role, adapter/data/config hashes and collection seed. Shared manifests use ArtifactManifest; owner-local private sample schemas are documented and validated separately and never exposed as new HTTP fields.

Runtime prompt construction is shared with inference formatting. Completion targets use actual RepairDraft, CriticDraft or JudgeDraft shape and canonical IDs. Target/reference/assessment fields are removed before prompt serialization. Verify masked token positions, chat template/EOS and that required target context is not truncated. Do not train on malformed targets merely because JSON parses. Verify code signature/domain/purity and executable correctness in the sandbox. Critic target expectations must have an authorized oracle rationale, not simply agree with a reference.

A records cover local repair and counterexample revision; B records cover independent reconstruction and later evidence revisions with view boundaries intact. B's buggy source is NOT included in initial prompt even when that source caused the record to be selected. Critic includes correct candidates for which no authorized objection exists; an observation-only general proposal is the legal no-objection format. Judge targets choose an existing available action option; they never contain hidden action scores in the input.

Records rejected by validation remain counted with reasons. Never silently relabel failed reference execution as correct. Model-generated teacher answers require the same validation. Paid teachers are optional; free route is reviewed source functions, controlled corruptions, execution-filtered local drafts and manually checked contracts. A local7B teacher must run in a separate phase and be unloaded before student jobs; memory/quality are measured, not assumed equivalent to a paid teacher.

## 4. Mac training and compatibility

One exact frozen base revision, tokenizer, quantization and adapted-module topology across A/B/Critic/Judge/general. Initial profile:4-bit base, rank8, microbatch1, short sequences, verified attention modules and gradient accumulation/checkpointing only if installed MLX supports them. Check real Phi model training/load/save/reload support before launching any full job. Qwen2.5-Coder3B is the recorded whole-experiment contingency; incompatible backbones/adapters never combined in one comparison.

Inspect installed MLX-LM JSONL schema, chat templates, sampler, completion masking, trainer and checkpoint interfaces through current documentation/signatures/--help. The project CLIs translate to those real interfaces. No guessed upstream flag table is supplied. A10–20-step pilot checks actual gradient updates, save/reload and model output; it is not the full quality result. Full training duration/checkpoint intervals are chosen on validation; no arbitrary300steps guarantees convergence. Stop VM/model services when unused during training and profile actual peak memory.

Common compute lock: choose one absolute CODEJURY_COMPUTE_LOCK path under the ignored local artifact root before branching and record it in the common config. Native workers and standalone trainers both use the same macOS standard-library fcntl.flock exclusive nonblocking lock after inspecting its API. The OS lock, not a stale PID JSON file, is authoritative; owner/PID/job metadata is diagnostic. Never force-steal a held lease. Shut down/unload the resident model worker before a trainer/teacher can acquire it. Release on exit/failure; tests use temporary locks. CPU-only modules import fcntl lazily so unsupported developer OS is not mistaken for a training-capable Mac. This protocol avoids depending on Ajay's implementation to run Sarvesh's standalone trainer.

Every adapter Card records actual steps/loss, data/base/tokenizer/quantization/topology/config hashes and role evaluation. completed requires genuine training, save/reload and measured validation. A retained Stage1 adapter is valid if those checks genuinely pass; record no new training rather than inventing a curve. The full release needs all four core roles completed and loaded compatibly. General completion is required for the planned fair research comparison.

## 5. B complementarity experiment

Freeze A. On TRAINING problems collect3fixed generation seeds and assess final proposals privately. Estimate f_A as the fraction of semantic/format failures, handling infrastructure failures separately. Starting weighting w=1+2*f_A; tune alpha in0/1/2/4 on validation. Preserve25–50% general mixture to avoid only difficult failure examples.

Choose B checkpoint considering standalone success and union A/B success. Report rescue rate among A-failed tasks, joint failure and overlap. Disagreement, different wording or adapter-vector orthogonality are not useful complementarity metrics. Required controls: alpha0 with same independent view, and B trained/inferred with A's view while failure weighting preserved. Those controls are additional real B checkpoints/configurations, not merely a flag changed after training. Report their offline training cost; no false claim of identical opportunities if runs differ.

## 6. Critic soundness experiment

Execution-filter proposals on train/validation candidates: valid domain, approved oracle compatibility, discriminating actual output and reproducible shrunk input. Correct-candidate objections are assessed privately to measure false hard rejection. Include unsound literals/relations, out-of-domain probes and honest no-useful-objection targets. Observe disagreement without declaring a winner when semantics are unapproved.

Measure authorized counterexample yield, proposal validity, false rejection and new valid failures from audit-gap guidance. Compare learned Critic with generic valid edge generation at equal execution budget. The auditor supplies locations/requirements, not ground-truth bugs. Mutation kill count alone cannot serve as reward or quality evidence.

## 7. Judge labels from alternative actions

Take a frozen TRAINING EpisodeBundle/StateSnapshot before an action. Enumerate valid menu options and execute up to4useful alternatives, each with the same remaining resource ceilings, fixed-v1 continuation policy and2–3fixed seeds. Keep parent state/events/sources immutable; each fork has independent run IDs/KV/sandbox state. The scorer sees private TRAINING assessment only after the fork commits its final answer. No hidden-feedback revision.

Initial utility: correct selection1, incorrect selection-1, abstain0, minus0.05 normalized cost. Normalize cost using declared token/time/execution caps consistently; freeze formula/coefficients after validation. Label the best empirical mean option. Record replicated disagreement/uncertain ties and use a declared deterministic tie rule or exclude uncertain labels; do not fabricate precise values from one guessed continuation. Penalize harmful false rejection separately in analysis. Final outcome correctness is finite-assessment support, not proof.

Judge prompt contains visible state/options/candidates/evidence/gaps/budgets only. Output selects state_id and existing option ID; deterministic controller validates stale IDs, prerequisites, evidence and budget. One schema retry then explicit fixed fallback within8Judge decisions. Evaluation compares learned vs fixed SAME tools/caps, including all Judge token/retry cost. Good explanations alone do not establish better decisions.

## 8. Required final methods and resource comparisons

| ID | Method | Tools and purpose |
|---|---|---|
| B0 |Raw base, one repair|Reference for difficulty; unmatched one-shot|
| B1 |Trained A with execution feedback|Training benefit; same visible evidence|
| B2 |A sampling/revision|Separates council from extra attempts; up to8learned attempts within matched caps|
| B3 |One trained general agent|Same test/search/audit/action tools and comparable aggregate role-training opportunity|
| B4 |Four prompted roles, fixed controller|Raw base role prompts, same available tools; learned specialization control|
| CJ |Full CodeJury|Four learned adapters, learned Judge, tools and oracle gate|

Token-matched comparison: common10,000 output/100,000 input,3,000 function calls,8learned/48search/48audit/8decision caps, same hardware/domain/call timeout,15min safety limit. Baselines with fewer trained decisions can spend their budget differently, including more A sampling under the8attempt cap. Count every role call, retry, prefill, shrink, probe and search. Actual costs need not match; report them. B0 remains explicitly unmatched. B1 cap/allocation is frozen and reported, not secretly privileged.

Walltime comparison: common real elapsed cutoff on identical Mac, same safety/execution limits and generous equal token ceilings; record unfinished/pending tests as unsolved. Do not confuse token-matched and time-matched rows. Freeze configs separately; no sleeping baseline, no forced debate sequence for B3. Report all offline training/data/teacher costs, not just inference.

General comparator merges all four authorized role-record distributions into one explicit-task-tag SFT corpus. Match aggregate training example/token opportunities and actual optimizer exposure, accounting for repetitions/views. Same base/quantization; validation tuning opportunities recorded. It uses one general adapter for repair/test/action with the same ToolPort and action validator. This baseline is essential to claim value beyond giving one AI stronger tools/data.

## 9. Required component ablations

| Variant | Changed factor | Held fixed |
|---|---|---|
| B-unweighted |Train B with alpha0|Independent view/base/data split/total opportunity|
| B-same-view |Train/infer B with A input view|Failure weighting/base/data opportunity|
| Generic-Critic |Use vetted generic edge generators|Same approved properties and execution budget|
| No-search |Disable AST actions|Same remaining declared resource ceilings; actual costs reported|
| No-gap-feedback |Audit allowed but hide gap summaries from Critic/Judge|Equivalent audit/execution allowance|
| Audit-at-end |Audit only after main choices|Same audit/execution cap; no investigation feedback|
| Fixed-Judge |Use fixed-v1 menu choice|Same frozen A/B/Critic/tools/caps|

These change one factor, not several hidden training/settings choices. Judge/no-gap data leakage tested by sentinel IDs/hashes. Audit-at-end can report gaps but cannot claim it repaired them. Required external/natural/held-out mutation-family subsets reveal search-vocabulary overfitting. If resources restrict planned runs, report the missing experiments as incomplete rather than presenting full evaluation.

## 10. Final measurement protocol

1. Seal final dataset before learning. Validate references/resource suitability without exposing hidden checks to agents. Predeclare exclusions and eligible count.
2. Complete all real four-role and general training/validation; freeze model, tool, data, profile, continuation and baseline/ablation configs. Do not run final assessment during S2.09 harness development.
3. Run every method with at least3declared sampling seeds. Commit final selected source/hash before hidden scoring; no repair informed by hidden outcomes.
4. Score final selection, retaining unresolved/invalid/infra/cancel as unsolved. Score candidate-pool correctness only afterwards for secondary selection diagnostics.
5. Store per-problem/per-seed outcomes/costs. Public rows show the first fixed seed with a clear note; all-seed analysis clusters by base problem. Confidence intervals use paired clustered differences, not treating mutants/seeds as independent.
6. Report acceptance precision/coverage, false acceptance, B rescue/joint failure, Critic soundness, audit-followup yield, Judge gain, input/output tokens, calls, latency and measured/null memory. Count partition identity is enforced.
7. Determine improved/inconclusive/worse from paired uncertainty plus incorrect acceptance/cost tradeoff. Gains whose interval includes no improvement are inconclusive. Do not select only the best seed or relabel observed test passage as hidden correctness.
8. Any later iteration after inspecting final results turns that set into development data; seal a new untouched set for a new final claim.

## 11. Release checkboxes

**Functional:** original Stage1 gates revalidated; expanded pure JSON/helper scope; isolated code and traces; actual A/B/Critic/Judge; validated learned actions; bounded search/auditor and gap followups; immutable evidence; real API/UI/cancel/restart/download.

**Learning:** genuine saved/reloaded compatible cards; actual data/log/hash/split lineage; sound Critic checks; real alternative-action labels; no hidden feedback or final data in training.

**Research:** trained fair general comparator, all baseline/ablation/seed outcomes, paired clustered analysis and actual costs/provenance/limits. A scientifically negative result stays visible. Full marks or superiority are not guaranteed by architecture size.

**Handoff:** common commit/owner diffs, actual environment/commands/config hashes and documented pending hardware or experiments. No synthetic fixture is completion evidence.
