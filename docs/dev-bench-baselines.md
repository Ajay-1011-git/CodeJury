# Development benchmark baselines — Phase 0 completed

14 October 2026. This development baseline contains 100 independently authored bases,
three methods and seeds 17, 29 and 43: **900 completed and scored runs**. Every
method selection was committed before private scoring began. These are current
system measurements, not a repair-improvement or sealed-final claim.

The current jury solves **30–35/100 per seed**, compared with **1–3/100** for
B-single. B-base is zero under this output protocol because every response fails
the required format; this is not a test of unrestricted code-only outputs. The
jury wrongly accepts **6–10/100 per seed** against private tests. It has not met
the roadmap's zero-wrong-acceptance goal. T2 solve rates are 30.3%, 45.5% and 36.4%
for seeds 17, 29 and 43; a consistently achieved 40% T2 rate is not established.

## Benchmark and boundaries

- Inherited dashboard checkpoint: `1c4ba52`, branch `codex/next-phase`.
- 22 T1, 33 T2 and 45 T3 bases; one corruption per base.
- 503 literal tests: 200 supplied and 303 private scoring tests.
- All references pass and all corruptions fail at least one test: 1,006 Docker calls.
- 17 authored draft bases excluded for identity/family/semantic or near-AST overlap.
- Train/validation audit covers 100 records across 50 bases; AST threshold 0.90.
- Sealed assessment unopened; overlap against its uninspected contents is unknown.
- Frozen schema, adapters, controller prompts, greedy sampler and native topology retained.
- Candidate and reference execution stayed in Docker; no cloud calls or downloads.

Proofs: [benchmark README](../backend/data/dev_bench/README.md),
[validation](../backend/data/dev_bench/validation.json), and
[aggregate results](../backend/data/dev_bench/baseline-summary.json).

## Solve rates

Wilson 95% intervals use one base problem per seed as the denominator. Repeated
seeds are shown separately and never counted as 300 independent problems. Invalid,
unresolved, infrastructure and cancelled runs count as unsolved.

| Method | Seed | Tier | Solved / bases | Rate | Wilson 95% | Wrong accepted |
| --- | --- | --- | --- | --- | --- | --- |
| B-base | 17 | all | 0/100 | 0.0% | 0.0–3.7% | 0 |
| B-base | 17 | T1 | 0/22 | 0.0% | 0.0–14.9% | 0 |
| B-base | 17 | T2 | 0/33 | 0.0% | 0.0–10.4% | 0 |
| B-base | 17 | T3 | 0/45 | 0.0% | 0.0–7.9% | 0 |
| B-base | 29 | all | 0/100 | 0.0% | 0.0–3.7% | 0 |
| B-base | 29 | T1 | 0/22 | 0.0% | 0.0–14.9% | 0 |
| B-base | 29 | T2 | 0/33 | 0.0% | 0.0–10.4% | 0 |
| B-base | 29 | T3 | 0/45 | 0.0% | 0.0–7.9% | 0 |
| B-base | 43 | all | 0/100 | 0.0% | 0.0–3.7% | 0 |
| B-base | 43 | T1 | 0/22 | 0.0% | 0.0–14.9% | 0 |
| B-base | 43 | T2 | 0/33 | 0.0% | 0.0–10.4% | 0 |
| B-base | 43 | T3 | 0/45 | 0.0% | 0.0–7.9% | 0 |
| B-single | 17 | all | 1/100 | 1.0% | 0.2–5.4% | 4 |
| B-single | 17 | T1 | 0/22 | 0.0% | 0.0–14.9% | 1 |
| B-single | 17 | T2 | 1/33 | 3.0% | 0.5–15.3% | 1 |
| B-single | 17 | T3 | 0/45 | 0.0% | 0.0–7.9% | 2 |
| B-single | 29 | all | 3/100 | 3.0% | 1.0–8.5% | 3 |
| B-single | 29 | T1 | 0/22 | 0.0% | 0.0–14.9% | 1 |
| B-single | 29 | T2 | 3/33 | 9.1% | 3.1–23.6% | 1 |
| B-single | 29 | T3 | 0/45 | 0.0% | 0.0–7.9% | 1 |
| B-single | 43 | all | 3/100 | 3.0% | 1.0–8.5% | 3 |
| B-single | 43 | T1 | 0/22 | 0.0% | 0.0–14.9% | 1 |
| B-single | 43 | T2 | 3/33 | 9.1% | 3.1–23.6% | 1 |
| B-single | 43 | T3 | 0/45 | 0.0% | 0.0–7.9% | 1 |
| J-current | 17 | all | 30/100 | 30.0% | 21.9–39.6% | 6 |
| J-current | 17 | T1 | 10/22 | 45.5% | 26.9–65.3% | 1 |
| J-current | 17 | T2 | 10/33 | 30.3% | 17.4–47.3% | 1 |
| J-current | 17 | T3 | 10/45 | 22.2% | 12.5–36.3% | 4 |
| J-current | 29 | all | 35/100 | 35.0% | 26.4–44.7% | 8 |
| J-current | 29 | T1 | 9/22 | 40.9% | 23.3–61.3% | 1 |
| J-current | 29 | T2 | 15/33 | 45.5% | 29.8–62.0% | 1 |
| J-current | 29 | T3 | 11/45 | 24.4% | 14.2–38.7% | 6 |
| J-current | 43 | all | 30/100 | 30.0% | 21.9–39.6% | 10 |
| J-current | 43 | T1 | 9/22 | 40.9% | 23.3–61.3% | 1 |
| J-current | 43 | T2 | 12/33 | 36.4% | 22.2–53.4% | 4 |
| J-current | 43 | T3 | 9/45 | 20.0% | 10.9–33.8% | 5 |

B-base is a raw, unverified one-shot prediction. A wrong prediction is unsolved,
not a publicly accepted repair. B-single uses trained A for up to eight blind
attempts with no schema retry, revision, search, Critic or Judge, and selects only
against supplied authoritative checks. J-current uses the inherited full jury.
All methods have the same caps; actual consumption differs.

## Output validity

Rates below use actual model calls, including retry calls. The retained field
`transport_failures` counts all non-ok worker responses, including refusals;
these are separate from malformed JSON/schema responses. Format validity alone
does not establish source validity or correctness.

| Method | Role | Calls | Malformed | Malformed rate | Non-ok responses |
| --- | --- | --- | --- | --- | --- |
| B-base | raw | 300 | 300 | 100.00% | 0 |
| B-single | fixer_a | 2400 | 216 | 9.00% | 0 |
| J-current | critic | 300 | 1 | 0.33% | 25 |
| J-current | fixer_a | 496 | 84 | 16.94% | 0 |
| J-current | fixer_b | 684 | 208 | 30.41% | 0 |
| J-current | judge | 1555 | 1 | 0.06% | 0 |

## Actual resource consumption

| Method | Input / output tokens | Repair / scoring calls | Method time total / median | MLX peak |
| --- | --- | --- | --- | --- |
| B-base | 146,982 / 44,730 | 0 / 0 | 0.28 h / 3.24 s | 2982 MB |
| B-single | 1,175,912 / 422,272 | 4,666 / 54 | 2.91 h / 20.85 s | 3026 MB |
| J-current | 5,207,167 / 272,568 | 11,156 / 362 | 3.03 h / 32.85 s | 3945 MB |

Method time excludes startup, interrupted partial attempts and subsequent hidden scoring.
The interruption resumed from 679 preserved selections under the same protocol.
Abandoned partial ledgers are retained; their complete overhead is not measured.
Peak memory covers
the MLX allocator only; total Mac and VM peak remain unknown. Scoring calls are
recorded separately and never available to a live selector.

| Method | Candidate proposals | Sum of unique sources within each run | Runs with repeats |
| --- | --- | --- | --- |
| B-base | 0 | 0 | 0/300 |
| B-single | 2040 | 255 | 255/300 |
| J-current | 911 | 625 | 152/300 |

B-single retains greedy v1 decoding. Its repetitions are disclosed, not described
as independent temperature samples. Resampling and equal-budget ablations remain
deferred in the [bounded local route](bounded-local-route.md).

## Reproduce

```sh
export CODEJURY_STAGE2_RUNNER_IMAGE=sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f
backend/.venv/bin/python backend/tools/dev_bench_run.py validate --out backend/data/dev_bench/validation.json
backend/.venv/bin/python backend/tools/dev_bench_run.py run --out backend/artifacts/dev_bench/baselines-v1
```

The output directory must be new; use a different name to reproduce. Raw selected
sources and ledgers stay in ignored local artifacts. Aggregate hashes bind the
complete retained result files.

## Validation and remaining scope

Baseline-related tests pass. The latest full check before this baseline completed
was 634 backend tests passed / 9 skipped and 80 frontend tests passed; the eight
paired-diagnostic tests are included. No tests call Groq or download weights.

Quick case and the actual conversation display are prepared. Their live repair
acceptance awaits native compute. The local A refresh trial starts only after this
baseline is documented and committed. Minimal-input accuracy, a full after-change
100-base comparison, model bake-offs and the other deferred phases remain unmeasured.
