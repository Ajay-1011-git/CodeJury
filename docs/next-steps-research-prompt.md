# Research prompt: next steps for CodeJury

Paste everything below the line into a research-capable AI assistant, for example one with web search or deep research.

---

You are a senior ML research engineer advising a two-person student team. Research the current best methods (2024 to 2026 literature, open-source projects and model releases) and produce a concrete, evidence-backed development plan for the project described below. Search widely, compare alternatives and cite every non-obvious claim with a link. Separate measured evidence from your own judgement.

## The project: CodeJury

CodeJury is a local, multi-agent system that repairs a buggy Python function. Every decision is made by executed tests, never by a model's opinion.

**Current pipeline ("Stage 2 jury")**

- **Fixer A** sees the buggy code, requirements, tests and failure traces, and proposes a patch.
- **Fixer B** independently reconstructs the function from the signature, contract and tests. It never sees the buggy body or Fixer A's code.
- **Critic** proposes test inputs or generators to break surviving patches, in modes `discriminate`, `challenge_agreement`, `audit_gap` and `validate_revision`.
- **Judge** picks the next action from a fixed menu: revise, generate, criticize, AST search, mutation audit, select or abstain. It sees a state summary and a candidate scoreboard.
- **Tools** run in an isolated Docker sandbox (Colima VM). They also provide deterministic AST search edits and a mutation auditor.
- **Acceptance:** a patch is accepted only if it passes every authoritative check. Checks are user-supplied literal tests plus approved executable property templates (sort, dedupe, sum, string reverse, count). Everything else is an observation that cannot reject a patch.
- **Budgets:** 10,000 output tokens, 100,000 input tokens, 8 learned candidates, 8 Judge decisions and 3,000 function executions per run.

**Models and hardware**

- **Base model:** `mlx-community/Phi-4-mini-instruct-mlx-4Bit` (about 3.8B parameters, 4-bit), run with MLX on one Apple Silicon Mac with 16 GB of unified memory. Peak memory per run is about 3.3 to 5.2 GB. Everything must run locally at inference time.
- **Adapters:** one LoRA adapter per role, rank 8, applied to only 4 layers (`qkv_proj`, `o_proj`).
- **Fixer A's training data:** 80 synthetic records drawn from 40 base problems. Every bug in it is "body replaced by `return 0` or `return None`", so the model learned to write a function from its contract, not to repair real logic.
- **Offline teacher:** an existing pipeline calls Groq (`openai/gpt-oss-120b`) to generate training data.

**Measured results so far**

- **Stage 1 (single fixer):** it fixes one-operator bugs and stub bodies, such as `min` to `max`, `+` to `*`, `<` to `<=`, or a missing body. It fails all multi-line logic bugs we tried: a loop off-by-one, a missed final run, rotation wrap-around, and sums that skip negatives.
- **Stage 2:**
  - Fixer A is almost always rejected.
  - Fixer B, which rewrites from the contract, wins most simple cases, such as `return sorted(values)`.
  - The Critic ran correctly in every case but never found a counterexample.
  - The Judge reaches 92.9% valid decisions, 11 of 20 solved, with no wrong acceptances.
  - A "General" single-agent comparator stays below the 90% validity gate and solves 0 of 20 tasks. Its invalid outputs are malformed JSON.
  - An untrained raw Critic produced invalid JSON in 9 of 9 Stage 1 runs.

## Goal 1: make the system solve harder bugs

It currently solves only very basic problems. Research and rank the most effective ways to raise repair ability under these constraints: a 16 GB Mac, local inference, small models, and a budget of a few hundred to a few thousand training examples and a few GPU-hours, or cloud credits if clearly worth it. Cover at least:

1. **Base model choice.** Which open code models of 3B to 14B parameters, quantized with MLX or GGUF, give the best repair ability per GB on Apple Silicon today? Examples to evaluate include the Qwen2.5-Coder and Qwen3 coder families, DeepSeek-Coder variants, Phi-4 variants and Gemma code models. Give benchmark evidence (HumanEval-Fix, DebugBench, SWE-bench Lite or Verified where applicable, LiveCodeBench, HumanEvalPack), licenses, memory footprint and MLX availability. Is switching base models a bigger win than any amount of fine-tuning Phi-4-mini?
2. **Training data.**
   - How do we build realistic bug-repair data? Options include mutation operators (wrong operator, off-by-one, wrong variable, missing case, reordered statements), mined real bug fixes, synthetic bugs from a teacher, and execution-verified filtering.
   - Which public datasets fit, with their licenses? Examples include BugsInPy, QuixBugs, DebugBench, HumanEvalPack/HumanEvalFix, CodeNet, CommitPack and RunBugRun.
   - How do we avoid contaminating our own held-out evaluation set?
3. **Distillation from a large teacher.** Use Groq-hosted large models offline to generate verified repair trajectories, including reasoning traces, critiques and revisions. Only trajectories whose patches pass the sandbox tests are kept. What does the evidence say about rejection-sampling fine-tuning, STaR or ReST-style self-improvement, and distilling from reasoning models into small models?
4. **Reinforcement learning with execution feedback.** Methods such as GRPO, PPO, DPO or KTO on pass/fail rewards, and "RL from unit tests". Is any of this feasible on a 16 GB Mac with MLX, or does it need cloud GPUs? Which frameworks support it?
5. **Fine-tuning capacity.** Is LoRA rank 8 on 4 layers too small? Recommend rank, target modules, layer count, QLoRA versus full LoRA, and learning-rate settings, with evidence.
6. **Inference-time compute.** Compare sampling many candidates and selecting by tests, iterative repair loops with execution traces and error messages, self-debugging, reflection, tree search, and localize-then-repair (as in Agentless). Which of these give the largest gains for small models within our token budgets?
7. **Multi-agent value.** Does a Fixer / Critic / Judge debate actually beat a single model with the same compute? Summarize the evidence on LLM debate and multi-agent code repair, and how to make the Critic genuinely adversarial: differential testing between candidates, property inference, and mutation-guided test generation.
8. **Structured output reliability.** How do we stop malformed JSON from small models? Options include constrained or grammar decoding in MLX (for example Outlines or lm-format-enforcer equivalents), simpler output formats, and repair-and-retry.

## Goal 2: repair with minimal user input

Today the user must supply typed argument domains, requirements, approved property templates and literal test cases. We want the user to provide only:

- the buggy code,
- the function name,
- a plain-language description of what the function should do.

Groq may be used to interpret the description, but it must not solve the bug. The local models must still produce the fix. Research and design:

1. **Specification inference.** Turn the description, function name and signature (plus types inferred from the code) into argument domains, a short list of requirements and candidate properties. How reliable is LLM-based spec and test generation? Cite work on test-oracle generation, LLM test generation such as CodeT, TiCoder, ChatUniTest and property-based test generation, and the "test oracle problem".
2. **The oracle problem without user tests.** If tests come from an LLM's reading of the description, they can be wrong. Compare these options:
   - Show the inferred tests to the user for one-click approval.
   - Mark generated tests as non-authoritative until two independent sources agree.
   - Use differential testing between Fixer A and Fixer B to find disagreements, then ask the user or Groq to adjudicate only the disagreeing input, never the code.
   - Use metamorphic relations.

   What does the literature recommend, and what are the failure modes, such as tests copied from the buggy behaviour?
3. **Keeping Groq out of the solution.**
   - How do we enforce and audit that the interpreter never sees or suggests a fix? Options include prompt design, output schema restrictions (no code allowed in outputs), stripping the function body from what Groq sees, and logging every Groq exchange.
   - Should Groq see the buggy body at all? Consider argument type inference versus leakage.
4. **Conversation-style history in the UI.** Users want to see the agents "batting" against each other: proposal, challenge, counterexample, rebuttal, revision, verdict. Find good UX patterns and open-source examples for showing multi-agent debates with executable evidence attached to each turn. Examples include agent trace viewers such as LangSmith, Phoenix or AgentOps, and SWE-agent trajectory viewers. Recommend a turn-based transcript format.

## What to deliver

1. **An executive summary:** the 3 to 5 changes most likely to raise solve rate the most, each with expected impact, effort and risk.
2. **A comparison table for each goal:** option, evidence (with citation), expected gain, compute or memory cost, effort in days, risks, and fit with our constraints.
3. **A recommended roadmap of 4 to 8 weeks:** ordered steps, with a measurable milestone for each, such as "solve at least 40% of the held-out multi-line bug set".
4. **An evaluation plan:**
   - A held-out benchmark of realistic bugs with difficulty tiers, kept free of training contamination.
   - The metrics: solve rate, wrong-acceptance rate, unresolved rate, tokens and time.
   - Fair baselines: a single model with the same compute, and the base model without adapters.
5. **A concrete design for Goal 2:** data flow, which component sees what, JSON schemas for the inferred specification, the approval step, and how inferred tests gain or lose authority.
6. **Specific resources:** model names with exact versions, datasets with licenses, papers with links, and repositories.
7. **Open questions and unknowns,** clearly marked.

## Ground rules

- Prefer sources from 2024 to 2026, and say when a claim rests on older or weak evidence.
- Do not recommend anything that sends user code to a cloud model for solving. Cloud use is allowed only for offline training-data generation and for interpreting the description.
- Respect licenses. Flag datasets or models that cannot be used for training or redistribution.
- Keep the core rule intact: only executed, authoritative checks can accept a patch.
- Be specific and quantitative where possible. Avoid generic advice.
