# Codex handoff: making CodeJury smarter and needing less input

Paste everything below the line into Codex, with the CodeJury repository open as the working directory.

---

You are taking over development of **CodeJury**, a local multi-agent system that repairs buggy Python functions. Read this whole brief before changing anything. Facts marked **[verified]** were checked on this machine or against a primary source on 14 October 2026. Facts marked **[unverified]** must be checked by you before you rely on them. Never invent results, file paths, model names, benchmark numbers or library features. If something is unknown, measure it or say it is unknown.

## 0. How to work

1. **Start from the current state.** The working tree has uncommitted work from the previous session (listed in §2.6). Before your first change:
   - Run both test suites (§2.7).
   - Create a branch `codex/next-phase`.
   - Commit the existing work as one commit titled "Integrate Stage 2 jury into the main dashboard".
   - Do not commit `CodeJury-Stage1-Quality-Upgrade.zip`, `codejury-training-private-*.sha256`, `.claude/`, any `.env` file, model weights or `artifacts/`.
2. **Work in phases (§5), in order.** Each phase ends with its acceptance check, passing tests and one focused commit. Do not start a phase until the previous one meets its acceptance check, unless this brief says the phase is independent.
3. **Measure, don't assume.** Every claim of improvement needs a before/after number on the development benchmark from Phase 0, with the command that produced it.
4. **Ask the user before:**
   - downloading any model or dataset (state the repo, size and license),
   - spending Groq budget above the configured cap,
   - opening the sealed final assessment,
   - deleting anything,
   - pushing to a remote.
5. **Report after every phase:** what changed, the measured results, what failed and what is still unknown. Report failures as failures.

## 1. What the user wants

1. **Smarter repair.** Today the system only solves very basic bugs: one-operator changes, stub bodies and wrong builtins. It should solve realistic multi-line logic bugs.
2. **Minimal input.** The user wants to give only three things: the buggy code, the function name and a plain-language description of what the function should do. The system must infer argument domains, requirements and tests by itself.
   - Groq (a cloud LLM API) may be used only to *interpret the description*.
   - Groq must never see or produce the fix. The local models must still solve the bug.
   - The user must be able to watch the agents argue turn by turn ("batting each other"): proposal, challenge, counterexample, rebuttal, revision, verdict.

## 2. Ground truth about the project

### 2.1 Hardware and stack [verified]

- **Machine:** Apple M5, 16 GB unified memory, about 626 GB free disk. `iogpu.wired_limit_mb` is 0, the macOS default limit.
- **Sandbox:** Colima VM `codejury-stage1`, Running, 2 CPUs, 2 GiB RAM, Docker runtime. Candidate code runs only inside Docker.
- **Python:** 3.11 venv at `backend/.venv`.
- **Installed:** `mlx` 0.32.3, `mlx-lm` 0.32.0, `transformers` 5.19.0, `groq` 1.7.0.
- **Not installed:** `outlines`, `lm-format-enforcer`, `mlx-lm-lora`, `mlx-vlm`, `openai`.
- **Model loaders:** the installed `mlx_lm/models/` includes `qwen3_5.py`, `qwen3_5_moe.py`, `qwen3.py`, `qwen2.py`, `gemma4.py`, `gemma4_text.py`, `phi3.py`, and others.
  - `qwen3_5.py` sanitizes away `vision_tower` and `model.visual` weights, so Qwen3.5 checkpoints load as text-only.
  - `mlx_lm.generate.generate_step` accepts `logits_processors`, which is a native hook for constrained decoding.

### 2.2 Architecture

**The main dashboard** is served by `backend/src/codejury/api/app.py`.
- It mounts the Stage 2 jury API under `/s2` via `backend/src/codejury/api/stage2_bridge.py`.
- The bridge also allows only one model run at a time across both stages, and adds `GET /s2/runs/{id}/transcript`. That route returns every model call (role, purpose, reply text) plus the Judge's option menu and candidate scoreboard, read from the Stage 2 ledger.
- The Stage 1 API (`/runs`) still exists but the UI no longer uses it.
- Stage 2 code imports Stage 1 modules in about 40 places, including `models.worker.file_hash`, `runner.DockerRunner`, `properties.equal`, `training.data` and `contracts.intake`. **Do not delete Stage 1 code.**

**The Stage 2 jury** lives in `backend/src/codejury/stage2_core/` and `backend/src/codejury/stage2_tools/`.
- **Fixer A** sees the buggy code, requirements, tests and trace.
- **Fixer B** reconstructs the function independently from the signature, contract, domains and tests. It never sees the buggy body or A's code.
- **The Critic** proposes inputs or generators in modes `discriminate`, `challenge_agreement`, `audit_gap` and `validate_revision`.
- **The Judge** picks one action per step from a menu: revise, generate, criticize, search, audit, select or abstain.
- **The tools** provide sandboxed evaluation, AST search and the mutation auditor.
- **Acceptance:** a patch is accepted only when it passes all *authoritative* checks: user literal tests plus approved property templates (`sort_ascending_ints`, `unique_preserve_order_ints`, `sum_ints`, `reverse_string`, `count_occurrences_ints`).
- **Budgets per run:** 10,000 output tokens, 100,000 input tokens, 8 learned candidates, 8 Judge decisions, 3,000 function executions.
- **The frozen wire contract** is `contracts/stage2.schema.json`. The UI checks its hash (`web/src/s2/api.mjs`, `CONTRACT_HASH`). Do not edit the frozen schema; add new endpoints beside it.

**The UI** is in `web/`. `index.html` and `src/app.mjs` boot the Stage 2-only dashboard. The rest:

| File | Role |
|---|---|
| `web/src/stage2-desk.mjs` | Form, verdict, proposals and matrix |
| `web/src/stage2-debate.mjs` | The debate history as clickable rounds; `buildDebate()` is pure and unit-tested |
| `web/src/stage2-demos.mjs` | Built-in demo cases |
| `web/src/s2/*.mjs` | The original Stage 2 client, store, views and view-models |

### 2.3 Models and adapters [verified from `backend/artifacts/stage2_core/judge-learning/selected-v2/registry.json`]

- **Base:** `mlx-community/Phi-4-mini-instruct-mlx-4Bit`, at `backend/models/Phi4-mini` (phi3 architecture, 4-bit, group size 64, 32 layers).
- **One shared topology for all roles:** LoRA rank 8, scale 16, dropout 0, `num_layers` 4, keys `self_attn.qkv_proj` and `self_attn.o_proj` only.

| Role | Steps | Records | Base problems | Recorded validation |
|---|---|---|---|---|
| fixer_a | 100 | 80 | 40 | 5/20 solved, 0 incorrect accepted, 1 malformed |
| fixer_b | 200 | 160 | 37 | B 5/20, union with A 10/20, 0 incorrect accepted |
| critic | 50 | 320 | 40 | 76/80 format/domain valid, 0 authorized failures |
| judge | 100 | 80 | 38 | 28/28 valid held-out menus, 21 empirical-label matches |

- **Fixer A's training data:** every bug is "body replaced by `return 0` or `return None`" (`backend/data/train_source/train.jsonl`, mutations `replace_returns_with_0` and `replace_returns_with_None`). It learned to write a function from a contract, not to repair logic.
- **Hard-coded limits** in `backend/src/codejury/stage2_core/registry/__init__.py`:
  - It rejects any base that is not `model_type == "phi3"` with 32 layers and 4-bit/g64 quantization.
  - It rejects any LoRA keys other than `["self_attn.qkv_proj", "self_attn.o_proj"]`.
  - `role_config()` fixes decoding to `"sampler": "greedy"` and `"context_tokens": 4096`, and folds both into each role's config hash.
  - So changing the base model, the LoRA targets or the sampling settings needs a **new, versioned registry** (for example `stage2.registry.v2`) plus retrained adapters. Do not loosen v1 in place: existing hashes and adapters must stay reproducible.
- **Offline teacher:** `backend/config/stage2_core/teacher.yaml` sets model `openai/gpt-oss-120b`, `max_cost_usd: 1.0` and `max_in_flight: 1`. Code is in `backend/src/codejury/stage2_core/teacher/`; `client.py` uses base URL `https://api.groq.com`.
- **Groq keys:** loaded from the repository-root `.env` (mode 600, gitignored, untracked). `teacher/cli.py` calls `credentials()`, which is defined in `teacher/redaction.py` along with the allowed key names. Never print, log or commit keys.

### 2.4 Measured behaviour [verified in live runs, 14 October 2026]

- **Single-fixer (Stage 1) path:** solved one-operator and stub cases. It failed every multi-line logic bug tried: loop off-by-one, missing last run, rotation wrap-around, sum skipping negatives.
- **Stage 2 jury, typical run:** Fixer A is rejected, Fixer B wins with a from-contract rewrite (for example `return sorted(values)`), the Judge orders an audit and a Critic challenge, then selects B.
  - The "Bubble sort stops one pass early" demo gave the same result 3 times out of 3.
  - The trained Critic produced valid proposals in most runs but never found a counterexample. The patches it challenged were already correct.
  - In the built-in "Unicode string property" run, the Critic's challenge was refused ("Critic challenge refused; selection prerequisites unmet"). The run ended unresolved even though Fixer B's patch was correct.
  - "Integer square root that halves instead" ends unresolved: the Judge abstains after revisions and searches.
  - The built-in "Reviewed helper and math import" example took different action sequences across two runs. The AST search candidate won both times.
- **The untrained raw Critic** in the Stage 1 path returned invalid JSON in 9 of 9 runs, so a deterministic fallback was used.
- **The "General" single-agent comparator** is not promoted: it stays below the 90% validity gate and solves 0 of 20. Its invalid outputs are malformed JSON.

### 2.5 Project rules that must not be broken [verified in repo docs]

From `integration/stage2/COMPLETION.md` and `CodeJury-Stage2-Build-Pack/CodeJury-Stage2-Training-and-Evaluation.md`:

- **Execution:** candidate code runs only in Docker. Native model jobs share one compute lock and run sequentially, never in parallel on this Mac.
- **Sealed final assessment:**
  - The final assessment stays sealed until every method and adapter is frozen.
  - Any set inspected during development becomes development data.
  - A new final claim needs a new untouched set.
- **Splits and counting:**
  - Split by base problem and family *before* generating corruptions, views, teacher answers or episodes.
  - Variants of one base problem are one problem, not many.
- **One base, one topology:** a single frozen base revision, tokenizer, quantization and adapter topology across A, B, Critic, Judge and General. Never combine incompatible backbones in one comparison. Qwen2.5-Coder-3B is the recorded whole-experiment contingency.
- **Local teachers:** a local teacher must run in a separate phase and be unloaded before student training.
- **Training-data validation:**
  - Teacher outputs go through the same validation as everything else: sandbox-executed correctness, plus signature, domain and purity checks.
  - Do not train on malformed targets just because the JSON parses.
  - Rejected records stay counted, with reasons.
- **RL** is an optional extension, never a substitute for SFT.
- **Final evaluation:** at least 3 declared seeds. Unresolved, invalid, infrastructure and cancelled outcomes count as unsolved. Confidence intervals are clustered by base problem.

### 2.6 Uncommitted work you inherit

| Status | Files |
|---|---|
| Modified | `backend/src/codejury/api/app.py`, `backend/src/codejury/api/repository.py`, `backend/tests/test_api_lifecycle.py`, `start.sh`, `web/index.html`, `web/src/api.mjs`, `web/src/app.mjs`, `web/src/evidence.mjs`, `web/src/s2/views.mjs`, `web/src/state.mjs`, `web/src/workspace.mjs`, `web/styles.css` |
| New | `backend/src/codejury/api/stage2_bridge.py`, `backend/tests/test_stage2_bridge.py`, `web/src/history.mjs`, `web/src/stage2-debate.mjs`, `web/src/stage2-demos.mjs`, `web/src/stage2-desk.mjs`, `web/tests/stage2_debate.test.mjs`, `samples/`, `docs/next-steps-research-prompt.md`, this file |

### 2.7 Commands [verified]

```bash
# Backend tests (last run: 548 passed, 9 skipped)
cd backend && .venv/bin/python -m pytest tests -q
# Frontend tests (last run: 73 passed)
cd web && npm test
# Run the app (stops whatever holds port 8000, checks the jury is ready)
./start.sh
```

The Stage 2 sandbox needs `CODEJURY_STAGE2_RUNNER_IMAGE=sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f`; `start.sh` sets it. Only one server may own the Stage 2 ledger (`backend/artifacts/stage2_core/runtime/api-instance.lock`). If the user's app is running, test on another port and expect `/s2` to answer 503 there. That is the guard working, not a bug.

## 3. Research findings you can rely on [verified sources]

An external research pass produced recommendations. These sources were confirmed to exist with matching titles:

| Source | What it shows |
|---|---|
| arXiv 2504.21798, SWE-smith | Scaling software-engineering data by generating bugs and validating them by execution |
| arXiv 2407.01489, Agentless | Localize, repair, validate pipeline |
| arXiv 2404.10100, TiCoder | User-approved generated tests for interactive code generation |
| arXiv 2501.02901, DeCon | Detecting incorrect LLM-generated assertions with postconditions |
| arXiv 2502.12143, Small Models Struggle to Learn from Strong Reasoners | Long teacher reasoning traces do not reliably help students of 3B or smaller |
| arXiv 2502.08788, Stop Overvaluing Multi-Agent Debate | Debate often fails to beat simpler baselines at equal compute |
| arXiv 2607.26117, Try Again, Don't Look Back | Blind resampling beats self-repair in small code models (single author, preprint) |

**Libraries confirmed on PyPI:**

| Package | Version | License |
|---|---|---|
| `mlx-lm-lora` | 5.8.6 | Apache-2.0 (SFT/DPO/ORPO/GRPO with LoRA on MLX) |
| `mlx-guided-grpo` | 2.1.1 | MIT |
| `textpolicy` | 0.1.11 | not stated |
| `llm-structured-output` | 0.0.20 | not stated (MLX JSON-schema acceptor) |
| `pcd-rlcd` | 0.1.4 | not stated |
| `outlines` | 1.3.3 | Apache-2.0 |
| `lm-format-enforcer` | 0.11.3 | MIT |

Check licenses before adding any dependency to `pyproject.toml` / `uv.lock`.

**Candidate base models (Hugging Face API metadata; nothing downloaded):**

| Repo | Architecture | License | Weights |
|---|---|---|---|
| `mlx-community/Phi-4-mini-instruct-mlx-4Bit` (current) | phi3 | MIT | 2.16 GB |
| `mlx-community/Qwen3.5-4B-MLX-4bit` | qwen3_5 | apache-2.0 | 3.03 GB |
| `mlx-community/Qwen3.5-9B-MLX-4bit` | qwen3_5 (text model `qwen3_5_text`, 32 layers, hidden 4096, 4-bit g64; repo tagged image-text-to-text) | apache-2.0 | 5.95 GB |
| `mlx-community/Qwen2.5-Coder-7B-Instruct-4bit` | qwen2 | apache-2.0 | 4.28 GB |
| `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit` | qwen2 | apache-2.0 | 8.31 GB (likely too large beside the VM; measure before trying) |

**[unverified], check before relying on it:**

- How to disable Qwen3.5 "thinking" through the chat template. Inspect the downloaded `tokenizer_config.json` / chat template for an `enable_thinking` variable or equivalent.
- Whether the MLX Qwen3.5 repos ship `chat_template.jinja`, which the registry's `BASE_FILES` expects. Their file list shows `tokenizer_config.json` but no separate jinja file.
- Real repair ability of these models on our tasks. No public HumanEval-Fix or DebugBench numbers were found for Qwen3.5.
- Peak memory with the VM plus a 9B model plus long context.
- Licenses of BugsInPy, QuixBugs, RunBugRun and DebugBench, and Groq's terms for training on outputs.

## 4. Strategy

The bottleneck is mainly the training data and the base model, not the number of agents:

- **Data:** realistic bugs instead of stub bodies.
- **Base model:** a stronger code model at the same memory budget.
- **Selection:** many independent candidates filtered by execution.
- **Output reliability:** malformed JSON eliminated by constrained decoding.
- **A useful Critic:** one that produces executable counterexamples by comparing candidates against each other.

Debate adds value only when the Critic produces executable evidence. The jury must therefore be measured against a single model given the same compute.

## 5. Phases

### Phase 0: development benchmark and baselines (do this first)

**Goal:** a trustworthy way to measure progress, without touching the sealed final set.

1. **Build `backend/data/dev_bench/`, a new development benchmark.**
   - Use new, independently written base problems, not derived from `train.jsonl` and never from the sealed final assessment.
   - Aim for at least 100 base problems in three tiers:
     - T1: single-token bugs.
     - T2: multi-line logic bugs, such as off-by-one, missed final iteration, wrong loop bounds, wrong accumulator initialisation, missing edge case, wrong comparison chain or reordered statements.
     - T3: edge-case and multi-step bugs.
   - Each problem stores: correct source, buggy source, contract text, Stage 2 RunCreate fields (domains, requirements, approved template where one fits) and private hidden tests used only for scoring.
   - Record provenance and family IDs. Run the existing family/near-duplicate disjointness checks (`training.data.assert_disjoint`, `normalized`) against all training sources.
2. **Write `backend/tools/dev_bench_run.py`.**
   - It runs each problem through `/s2` (or the controller directly) with a fixed seed list, then scores the **selected** patch against the hidden tests.
   - It records solved, wrong-accepted, unresolved, invalid and infrastructure outcomes, plus tokens, executions, wall-clock and peak memory, per problem and per seed, as JSONL.
   - It prints solve rate with Wilson 95% intervals, by tier.
3. **Run three baselines on the current system:**
   - B-base: the base model without adapters, single shot.
   - B-single: one model given the same token and execution budget, using best-of-n selected by the same authoritative tests.
   - J-current: the full current jury.

**Acceptance:** the benchmark is committed, without hidden tests in any prompt path; baseline numbers are written to `docs/dev-bench-baselines.md` with the commands used; tests pass.

**Stop and report** if fewer than 60 problems are ready. Do not pad the set with variants.

### Phase 1: structured-output reliability (independent of Phase 2)

**Goal:** malformed JSON drops below 2% in every role on the dev benchmark.

1. Implement constrained decoding through `mlx_lm` `logits_processors`. Inspect the installed `generate_step` signature first.
   - For the Judge, constrain `action_option_id` to the offered option IDs, using the existing short state-scoped menu IDs.
   - For the Critic, use a JSON-schema acceptor (evaluate `llm-structured-output` for license and MLX 0.32 compatibility, or write a small grammar processor).
2. For Fixers, put code in a tagged block (for example `<patch>…</patch>`) with a small JSON envelope. This is a prompt/format change, so it **requires retraining or a format-compatible prompt**; measure it before adopting.
3. Allow one retry with the parse error message on failure. Count retries against the budget.
4. Record the decoding change as a registry/role-config change (new hash), never silently.

**Acceptance:** before/after invalid-output rates per role, and an unchanged or better solve rate.

### Phase 2: base-model bake-off (needs downloads; ask first)

1. Add a `stage2.registry.v2` path that accepts a declared architecture allowlist and per-architecture LoRA target names.
   - Keep v1 validation untouched.
   - Make the sampler and context length explicit registry fields.
2. With the user's approval, download and pin exact revisions of the candidates: Qwen3.5-4B-MLX-4bit, Qwen3.5-9B-MLX-4bit and Qwen2.5-Coder-7B-Instruct-4bit. The current Phi-4-mini is the control.
3. Verify text-only loading, the chat template, and how to turn thinking off (Qwen3.5). Record peak memory and tokens per second with the Colima VM running.
4. Evaluate **base models without adapters**, all with the same prompts, on dev-bench tiers T1–T2, using the B-single protocol.

**Acceptance:** a table of solve rate by tier, invalid-output rate, tokens per second, peak memory and license, plus a recommended base model. Per §2.5 the whole jury must then move to that base together; never mix backbones in one comparison.

**Stop and report** if no candidate beats Phi-4-mini by a margin outside the confidence interval.

### Phase 3: realistic training data, then retrain the roles

1. **Generate data for training problems only,** keeping problems family-disjoint from dev-bench and the sealed set.
   - Start from correct functions.
   - Apply **composed** mutations, 1–3 per function: operator swap, off-by-one, boundary constant, wrong variable, dropped statement, reordered statements, wrong initialiser, missing branch.
   - Use Groq offline to write **semantically different** buggy variants and short diagnoses. Groq here generates training data, not live fixes. Respect `max_cost_usd`; ask before raising it.
   - Keep a record only if the buggy version fails at least one hidden test **and** the reference fix passes every test in the sandbox.
2. **Repair targets:** a 1–3 sentence diagnosis plus the patch. No long reasoning traces (see arXiv 2502.12143).
3. **Retrain each role** under the v2 registry. Use LoRA on all linear modules (attention and MLP) and more layers, at rank 16 and 32, with a learning-rate sweep. Validate with the existing mask, reload and validation checks, and select by execution on the validation split.
4. Keep Fixer B's view boundary: B must never see the buggy body.

**Acceptance:** record counts with rejection reasons, adapter cards, and dev-bench before/after. The T2 target is ≥40% solved (a goal, not a promise).

### Phase 4: inference-time compute

1. **Blind resampling:** allow the Judge's `generate` action to request k independent candidates at temperature above zero. This is a registry sampler change. Charge every candidate to the budget.
2. **Concrete-failure repair:** revisions get the first concrete failing input, the expected value, the actual value and a "must change behaviour" instruction. Reject revisions that are byte-identical to their parent before execution.
3. **Ablate** blind resampling against repair at equal tokens on the dev benchmark (arXiv 2607.26117 says resampling wins for small models; test it on our tasks).

**Acceptance:** an ablation table at equal budget.

### Phase 5: an adversarial Critic

1. Add **differential testing:** when two eligible candidates exist, generate inputs from the domain and run both in the sandbox. Any disagreement becomes a `discriminate` target.
   - An approved property or template decides between them where one applies.
   - Otherwise the disagreement is shown to the user (Phase 6) and never auto-decided by a model.
2. Feed survived mutants from the auditor into Critic `audit_gap` proposals.
3. Measure "wrong candidates killed by the Critic that the supplied tests missed" on the dev benchmark, plus the wrong-acceptance rate. The latter must stay 0.

**Acceptance:** that metric, reported with and without the Critic. If the Critic adds nothing, say so.

### Phase 6: minimal-input mode (code, name and description only)

This can start in parallel with Phases 2–3, because it uses the existing jury.

1. **New endpoints** beside the frozen contract, for example in a new `backend/src/codejury/api/intake.py` mounted by `app.py`:
   - `POST /s2x/intake` takes `{source, function_name, description}`.
   - It returns an **inferred spec draft**:
     ```json
     {"spec_version":1,"function":{"name":"","signature":""},
      "arg_domains":[{"param":"","domain":{},"source":"local_ast|groq"}],
      "requirements":[{"id":"","text":"","property_template_id":null,"source":"groq"}],
      "examples":[{"id":"","args":[],"expected":null,"source":"groq","tier":"proposed"}],
      "disagreements":[]}
     ```
   - `POST /s2x/intake/{id}/approve` takes per-item `approve|edit|reject` decisions. It builds a valid Stage 2 `RunCreate` and submits it to `/s2/runs`.
2. **Local inference first:** derive the signature, argument names, use-sites (iterated, indexed, compared, called with `len`, used as a dict) and literal constants from the AST, in a local module. Map them to the closest Stage 2 `ValueDomain`.
3. **Groq interpretation:**
   - **Input:** function name, signature, description and the AST-derived facts. **Never the function body.**
   - **Output:** a schema-restricted spec covering requirements, at most 8 example input/expected pairs and template suggestions.
   - **Leak guard:** a validator rejects any string field that contains code (`def`, `return`, `lambda`, backticks, assignment or operator patterns), or that has high n-gram overlap with the buggy body.
   - **Logging:** append-only, with request hash, response and validator result, and keys redacted (reuse `teacher/redaction.py`).
   - **Model:** use the model configured in `backend/config/stage2_core/teacher.yaml` unless the user chooses another. Call it through the existing client patterns, with the budget ledger.
4. **Authority ladder.** This keeps the core rule that only authoritative checks accept a patch:

   | Tier | Meaning | Can it reject a patch? |
   |---|---|---|
   | `proposed` | Inferred by Groq or the local models | No, observation only |
   | `corroborated` | A Groq example agrees with an independent local check or a metamorphic relation | No; a failure forces an "ask the user" step |
   | `approved` | The user clicked approve | Yes; becomes a supplied literal test |
   | Registered templates | The user approved a registered property template | Yes |

   Characterisation outputs of the buggy code are tagged `buggy_behaviour` and never become oracles without user confirmation.
   - **Open decision for the user:** the user said they don't want to provide tests. Implement one-click "approve all inferred items" as the default. Also offer an explicit **"trust the interpreter"** toggle that promotes Groq examples to authoritative *with a visible label* on the verdict ("verified against an interpreted specification, not user tests"). Ask the user which default they want; do not decide silently.
5. **Mid-run user questions:** when Fixer A and Fixer B disagree on an input (Phase 5), show only that input and both outputs to the user, never the code, and ask which output is correct. The answer becomes an approved test.
6. **UI:** add a "Quick case" form (code, name, description) to the Repair desk in `web/src/stage2-desk.mjs`, then an approval panel for the draft spec.

**Acceptance:**
- Dev-bench solve rate in minimal-input mode is within 10 points of the full-input mode.
- Zero leaks in a red-team suite: buggy functions whose fix is obvious from the body; assert that no Groq output contains the fix or code.
- The approval flow works end to end in the dashboard.

### Phase 7: the "batting" conversation view

1. Extend `/s2/runs/{id}/transcript` and `buildDebate()` (`web/src/stage2-debate.mjs`, already unit-tested) into a turn record:
   ```json
   {"turn":1,"role":"fixer_a","kind":"proposal|challenge|counterexample|rebuttal|revision|verdict","claim":"","evidence":{"exec_id":"","input":[],"expected":null,"actual":null,"tier":""},"patch_diff":"","tokens":0}
   ```
2. Render it as a chat: one bubble per turn, colour by role, expandable evidence chips. A counterexample bubble links to the execution cell, and a revision shows the diff against its parent.
   - Keep the existing clickable step view as a "timeline" alternative.
   - Show Groq interpretation turns too, labelled "Interpreter (cloud, spec only)".
3. Only display text actually produced by models or tools. Never synthesise dialogue.

**Acceptance:** live runs render correctly; unit tests cover turn building; screenshots go in the PR description.

### Phase 8 (optional): preference learning

Only after Phases 0–5 are measured: DPO, then optionally GRPO, on pass/fail pairs from sandbox outcomes, using `mlx-lm-lora` (check the license and MLX 0.32 compatibility first) or cloud TRL with the user's approval. RL never replaces SFT (§2.5).

## 6. Definition of done for each phase

- Tests pass. Add tests for every new module; no test may call Groq or download models (use fakes).
- Before/after numbers come from the dev benchmark, with seeds, commands and confidence intervals.
- No change to `contracts/stage2.schema.json`.
- No secrets in code, logs or commits.
- Docs are updated: `README.md` "how to run", plus a short results note in `docs/`.
- The commit message says what changed and what was measured, and does not overstate results.

## 7. Do not

- Do not open, read or score the sealed final assessment.
- Do not train on dev-bench or sealed problems, or on their families.
- Do not mix base models or adapter topologies in one comparison.
- Do not let any cloud model see the buggy function body during a live repair, or propose code.
- Do not make model-only judgements authoritative.
- Do not delete Stage 1 code or the existing adapters.
- Do not report a result you did not measure.
