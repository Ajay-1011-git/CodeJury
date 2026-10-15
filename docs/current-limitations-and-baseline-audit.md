# Current limitations and Phi-4-mini comparison

15 October 2026. Checked against current source, the completed 900-run development
baseline and a new Docker audit of the saved raw-model replies. No model was
trained or sampled for this audit, and no cloud call or download was made.

## What CodeJury currently accepts

| Area | Current boundary |
| --- | --- |
| Problem size | Small Python functions, rather than whole applications or multi-file repositories. Source is limited to 48,000 bytes and 5,000 AST nodes; model context is 4,096 tokens. |
| Interface | 1–6 plain positional parameters. Zero-argument functions, default arguments, annotations, keyword-only/variadic and positional-only interfaces fail the static source checker. |
| Python constructs | No classes, nested functions/closures, lambdas, decorators, async, generators, global/nonlocal declarations, context managers or `match`. Ordinary loops, conditionals, comprehensions and bounded recursion can be used within the remaining rules. |
| Helpers/imports | Quick case accepts a single function without imports. Advanced case can declare up to three top-level helper interfaces and reviewed dependencies: `math.gcd`, `math.isqrt`, the two bisect functions, `collections.Counter`, and `collections.deque`. Arbitrary packages and imports are unavailable. |
| Values | JSON-compatible null, booleans, integers, strings, lists and string-keyed dictionaries. Floats, returned tuples/sets, function objects, generators, custom objects and NumPy/Pandas values are unsupported. Tuples/sets can be internal intermediates if the final output is supported. |
| Input bounds | Integers within plus/minus 1,000,000; strings at most 128 characters over an explicit alphabet; lists at most 64 items; dictionaries at most 20 entries; container nesting at most four. Advanced domains can express bounded unions; Quick case infers only eight predefined kinds. |
| Side effects | Inputs must remain unchanged. In-place sorting or other input mutation disqualifies a candidate even if its return value is correct. Files, network access, process execution and interactive input are outside the sandbox interface. |
| Execution | Existing dedicated Docker runner, 512 MB per container and two seconds per function call. Per repair caps include 15 minutes, eight learned candidates, eight Judge decisions, 3,000 function executions and 10,000 output tokens. |
| Quick case | Description, signature and bounded AST facts go to Groq; the buggy body remains local. Draft domains/examples need review and approval. The code/secret guard can reject descriptions or generated text. The current generic intake error conceals which validation failed. |
| Correctness | Finite approved tests and five registered property templates provide evidence, not a general proof. Requirements such as "must use quicksort" are not established merely by matching sorted outputs. The inference system can accept a wrong patch or decline a correct one. |

The five direct property templates cover integer sorting, order-preserving integer
deduplication, integer summation, string reversal and integer occurrence counts.
Other contracts can use approved literal examples, which give narrower coverage.
Mid-run questions resolving agent disagreements and differential Critic testing
remain deferred. Minimal-input accuracy versus full-input accuracy is unmeasured.

## Does the jury outperform the raw model?

**Yes on this development comparison, with important scope limits.** The model is
the locally installed four-bit `mlx-community/Phi-4-mini-instruct-mlx-4Bit`.
"Untrained" here means no CodeJury adapter; it is already a pretrained,
instruction-tuned model. This does not benchmark Microsoft's full-precision model
or every possible prompting, sampling and tool configuration.

The benchmark has 100 bases (22 T1, 33 T2, 45 T3), two supplied tests per problem,
and three or four private development scoring tests. All method selections were
frozen before the original private scoring. There are three repeated seeds, not
300 independent problems. The sealed final assessment remains unopened.

| Method | Seed 17 solved / 100 | Seed 29 | Seed 43 |
| --- | --- | --- | --- |
| Raw Phi-4-mini, original strict output protocol | 0 | 0 | 0 |
| Raw Phi-4-mini, saved code recovered for this audit | **9** | **8** | **9** |
| Trained Fixer A alone, up to eight blind attempts | 1 | 3 | 3 |
| Current CodeJury, full jury and tools | **30** | **35** | **30** |

The raw strict-protocol score was dominated by formatting: all 300 raw replies
failed the required RepairDraft parser. The audit removed only one optional outer
Markdown JSON fence, parsed a single JSON object and took its `source` string
verbatim, ignoring metadata schema failures. It did not edit code, select among
alternatives, add retries or use private outcomes to choose a source. All 300
extractions were committed to a local file before opening the development scorer.
278 replies supplied a parseable source; 22 did not. This is a **post-hoc code-only
audit**, kept separate from the original strict benchmark.

Every extracted proposal was checked against the original static/interface rules
and all original supplied plus private development tests in the original pinned
Docker runtime. Repeated identical source bytes for the same deterministic base
reused outcomes: 122 distinct base/source pairs, 178 reused records and 534 actual
Docker function calls. No candidate ran on the host. The audit does not relax
CodeJury's existing Python support or input-purity requirement.

The jury gains 21, 27 and 21 percentage points over recovered raw code. Paired
counts are jury-only/raw-only successes of 25/4, 31/4 and 27/6 respectively.
Raw per-seed Wilson 95% intervals are 4.8–16.2%, 4.1–15.0% and 4.8–16.2%.
Jury intervals are 21.9–39.6%, 26.4–44.7% and 21.9–39.6%. All tier-level intervals
and provenance hashes are in the [audit record](experiments/raw-code-audit.json).

## What the comparison does not establish

- The raw baseline gets one generation. The jury has multiple role adapters,
  additional evidence, retries, AST search, mutation auditing and selection.
  Original median method times were 3.24 seconds raw and 32.85 seconds jury.
  Identical resource caps do not mean identical compute consumption. A strong raw
  best-of-N/tool-assisted comparison at matched actual compute remains unmeasured.
- The trained single-fixer baseline scores below recovered raw code. These results
  do not demonstrate that Fixer A fine-tuning alone improved repair ability. The
  eight blind attempts use greedy decoding and often repeat the same source.
  The jury's gain cannot be attributed exclusively to training or agent debate.
- Jury wrong acceptances are 6, 8 and 10 per 100 bases. Among its accepted patches,
  6/36, 8/43 and 10/40 fail private checks: about 17–25%. Correctness beyond those
  finite tests is also unknown. An accepted patch still needs independent tests.
- The jury solves roughly 20–24% of the hardest T3 tier. Complex real application
  bugs, unsupported Python features and tasks outside the benchmark are not
  covered by the overall 30–35% result.
- The later 100-step A refresh and concrete-failure revision experiment failed
  their acceptance gates. They were not adopted and add no measured improvement
  to this comparison. See [training results](local-logic-trial.md).

## Reproduce this saved-reply audit

From the repository root, with the original local baseline ledgers present:

```sh
export CODEJURY_STAGE2_RUNNER_IMAGE=sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f
backend/.venv/bin/python backend/tools/dev_bench_raw_audit.py --baseline backend/artifacts/dev_bench/baselines-v1 --out backend/artifacts/dev_bench/raw-code-audit-new
```

Use a fresh output directory. The original baseline files stay unchanged. The tool
verifies their hashes and the pinned runner, freezes all extracted sources, and
then scores them. Raw replies, extracted sources and per-base results remain in
ignored local artifacts. Eight focused tests cover exact source preservation and
refusal to salvage prose, multiple proposals, duplicate source keys or Python
fences. The full original [baseline report](dev-bench-baselines.md) remains the
source for jury and trained-single-fixer measurements.
