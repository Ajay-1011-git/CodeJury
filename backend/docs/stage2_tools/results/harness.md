# Benchmark harness (S2.09)

Status: harness built and CPU-checked on **synthetic fixtures** only. No final assessment, no real
method run and no quality claim exists yet (that is S2.12, after S2.08/S2.10).

## Protocol implemented (`evaluation/`)
1. `preflight`: frozen exclusion rule (unsupported domain/imports/helpers, failing reference),
   reporting the original population and the eligible subset. Nothing is padded.
2. `commit_all`: every (method, regime, task, seed) run is requested through the BaselinePort
   with no hidden data. Selected source/hash and the candidate pool are written to an append-only
   `commitments.jsonl` whose digest is checked before scoring.
3. `score_all`: hidden tests are applied once to the committed selection (no repair feedback),
   inside the sandbox in live mode. Pool correctness is scored only afterwards, as a secondary
   diagnostic; headline counts are from the selected patch, never oracle-best.
4. Outcomes: solved / incorrect_accepted / unresolved / invalid_input / infrastructure_error /
   cancelled, all kept in the denominator; their sum equals `total_base_problems` per row.
5. Time-matched regime: the harness itself cancels at the declared cutoff; late answers count as
   cancelled (unsolved). Token-matched runs use the common Budget caps plus a 15-minute safety
   cancel. B0 is a labelled unmatched reference.

Methods: B0, B1, B2, B3, B4, CJ, time-matched B3/B4/CJ and the seven ablations
(`config/stage2_tools/evaluation.yaml`; validation experiments use `evaluation-validation.yaml`,
which can never target the final split). Frozen method config hash = SHA-256 of the canonical
method block + regime caps + profile + declared sampling/public seeds. The native BaselinePort now registers those exact hashes and refuses changed caps/configuration.

## Statistics
Per base problem the mean over seeds is taken; the resampling unit is the base problem
(seeds/variants are nested, never independent). Clustered paired percentile bootstrap, 10,000
resamples, 95%, fixed seed, pure Python (deterministic). `research_outcome`:
improved = solved CI > 0 and false acceptance not significantly higher and ≤ +0.02;
worse = solved CI < 0 or false acceptance significantly higher; otherwise inconclusive;
`not_measured` when the fair B3 baseline is missing. Reports include wins/losses/ties and
natural / synthetic / held-out-family subsets.

## Not yet measurable here
Critic authorised yield/false rejection, gap-to-new-failure rate and Judge-vs-fixed need runtime
event export (null in reports). Peak memory is null unless the runtime measured it.

## External benchmarks
- QuixBugs: licence checked on GitHub = MIT. Small (40 programs) secondary benchmark; many
  programs use types/imports outside json.v1 and will be excluded by preflight, with counts.
- EvalPlus (HumanEval+/MBPP+): licence = Apache-2.0. Repair adaptation (buggy-input construction,
  helper/type mapping) is **not yet implemented**; its `trusted_exec` must never run candidates on
  the host: translate tests into the sandbox harness. Contamination in base-model pretraining is
  a stated limitation.

## Commands
`python -m codejury.stage2_tools.eval_cli smoke --config config/stage2_tools/evaluation-validation.yaml --mode fixture --out artifacts/stage2_tools/harness-check`
`... run --config config/stage2_tools/evaluation.yaml --split final_assessment --out artifacts/stage2_tools/evaluation` (needs live ports; exits 3 = pending otherwise)
`... analyze --results artifacts/stage2_tools/evaluation --out artifacts/stage2_tools/benchmark-report.json`

The real factory requires all four completed roles, the trained General comparator and both native B controls before private assessment access. Final E4 additionally requires the comparable-exposure audit, clean committed source, exact model/control/config/runtime/hardware hashes, and an unconsumed final asset. A per-user Mac marker binds final consumption to the asset hash across checkouts and freeze filenames. The sealed loader rejoins the learning seal and checks base/family/reference disjointness. The declared first lexicographic variant per base keeps variants from inflating the independent sample size. Baseline B4 uses four actual raw prompts, including a raw menu choice inside fixed prerequisites; raw receipts never carry adapter identities. The deterministic Fixed-Judge ablation remains distinct.

The actual final commands now require `--freeze`: run `... run --config config/stage2_tools/evaluation.yaml --split final_assessment --freeze artifacts/stage2_core/e4.json --freeze-only --out artifacts/stage2_tools/final-unused` to write the freeze after validation; omit `--freeze-only` and choose a new `--out` directory for the single final run. No final assessment has run at this checkpoint.
