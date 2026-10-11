# Stage 1 measurement

Native evaluation completed on the 10 sealed internal assessment bases. All three methods solved 1/10, unresolved 9/10, incorrect accepted 0/10. The frozen step-100 adapter was selected before assessment; it improved output formatting and token cost, but did not improve solved count.

The predeclared assessment uses the first sealed buggy variant from each of 10 distinct bases, across the order-statistics and digits families. All three methods receive identical visible requests. Raw and trained single-shot each allow one generation of at most 1024 tokens with no format retry; the loop allows a raw Critic, one format retry, one revision, 4096 output tokens and 400 sandbox invocations. This is a preliminary comparison with unequal budgets, not a fair superiority experiment.

Every accepted answer is saved with exclusive creation before private assessment execution. The evaluator then executes the two private tests against that frozen source and never returns their results to a model/controller. Incorrect accepted means a visible-supported answer failed private assessment; unresolved means no visible-supported answer was committed. Hidden assessment cost is retained separately from runtime usage. No private assessment test or reference source is sent to runtime storage. Visible assessment requests occupy an offline runtime directory only.

The corpus is a project-authored synthetic prototype: 40 train bases/80 examples, 10 validation bases/20 variants, 10 assessment bases/20 variants. This assessment scores 10 bases, not 20 independent problems. The separate 10-base final Stage 2 pool remains unused. Offline authoring code is visible to developers, so this is an internal sealed assessment, not a secret external benchmark. Stage 1 assessment now becomes development evidence and must not be treated as fresh Stage 2 final evaluation.

Public sum live demonstrations overlap the training algorithm family and are unscored. The sealed manifest's original public_demo_overlap=false refers to the original unique-order seed demo; the later sum-family overlap is disclosed here and in the training card.

Weights/adapters and complete raw generations/results remain ignored locally. The API reads only schema-validated aggregate TrainingReport JSON; it cannot serve private sources or test inputs from that report. Before measurement completion, the genuine 300-step adapter is labelled pilot_only for the UI's completion criterion, with nulls for unmeasured losses/counts. A completed report requires all measured methods.

## Actual measured results

| Method | Solved / total | Unresolved | Incorrect accepted | Malformed | Total generated tokens | Mean runtime ms | Total runtime executions | Total elapsed ms including private assessment |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| raw_single | 1/10 | 9 | 0 | 9 | 2027 | 7626 | 22 | 77021 |
| trained_a_single | 1/10 | 9 | 0 | 0 | 348 | 2756 | 40 | 28119 |
| stage1_loop | 1/10 | 9 | 0 | 0 | 2393 | 56391 | 2742 | 565394 |

Raw single-shot malformed 9/10 responses; trained single-shot malformed 0/10. Loop's malformed flag describes a returned final answer, not individual rejected Critic proposals; full raw outputs/retries and fallback actions are in its retained episodes. All methods solved the same digit_sum base. The loop spent more time/tool work and did not improve success here. No further tuning was done after assessment.

Evidence: `artifacts/evaluation/stage1-results.json`, per-method/base `stage1-results-evidence/*/*/final-answer.json` frozen before private checks, subsequent `assessment.json`, and `training-report.json` (public schema aggregate). Runtime single-shot costs exclude the later private checks; total elapsed above includes them. Full rows record exact input/output token totals, function counts, memory, elapsed times, raw generations, and hash of each frozen answer.

Reproducibility: conversion d848c30f6d5419b9892433cf6b1062626d15340e; selected adapter 274fd6b1a4a9abd04a8a2d3e56cfbde765c81e71fdb230682f4bf66509605fb4; dataset manifest 95fabdb275e7f76e0b8aaa610e1708956aaf9a6666215c035fe0a6623ca7741a; profile stage1-demo; MLX/NumPy seeds 17. Exact weight/tokenizer/config/lock/profile hashes, installed library versions, previous committed controller revision and budget policy are in the results reproducibility manifest. A.08 measurement code is committed with this document; find its commit using `git log --grep='A.08'`.

TrainingReport shows completed with 300 actual trial steps, selected checkpoint 100, 40/10/10 bases and 80 train records. Missing train/validation loss values remain null; iteration 99 validation loss 0.185604 worsened to 0.321105 at 299. This honest internal prototype result does not establish broader repair accuracy.

Real supported live episode: `artifacts/demo/live-sum-run.json` (public training-family overlap disclosed). Real unresolved episode: `artifacts/demo/live-run.json`, including independently replayed unique input [[0,0]], observed [0,0], approved expected [0]. Also retained: successful live HTTP sum report and cancellation/error paths. Sarvesh UI integration and milestone M5 are pending; no complete integrated release is claimed.

Commands (from backend with local model/adapter environment variables):

```sh
python -m codejury.evaluation.cli stage1 --manifest data/manifests/stage1.json --config config/model.yaml --out artifacts/evaluation/stage1-results.json
python -m pytest tests/test_evaluation.py -q
python -m codejury.evaluation.cli export-report --results artifacts/evaluation/stage1-results.json --out artifacts/evaluation/training-report.json
```

Measured output/evidence directories refuse overwrite. Use a new output path for reproduction; it is a replay of development evidence, not fresh sealed assessment. The API reads the aggregate file only and returns typed 503 for corrupted reports. With no measurement yet, `export-pilot` publishes genuine adapter/loss metadata as pilot_only; fixture mode cannot be served as live.
