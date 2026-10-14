# CodeJury development benchmark v1

100 independently authored base problems: 22 T1 (one-token corruptions), 33 T2
(logic and state bugs) and 45 T3 (edge cases and multi-step algorithms). One
corruption per base. This is development data, never training or final assessment.

`runtime.jsonl` contains only provenance and Stage 2 RunCreate inputs. Each method
sees two supplied literal tests. `private/scoring.jsonl` contains references and
three or four additional tests per problem. The authoring catalogue and scoring
file must never be loaded by a runtime model, interpretation endpoint or training
export. Hidden here means withheld from model prompts, not encrypted or sealed.
The benchmark is intentionally committed for reproducible development.

All references pass all 503 tests in the existing Docker sandbox. Every corruption
fails at least one test. Validation ran 1,006 reference/corruption function calls.
Three initially undetected corruptions (leap year, upper bound and spiral traversal)
required additional scoring cases; the failed validation is retained locally in
`backend/artifacts/dev_bench/validation-attempt2.json`.

17 initially authored bases were excluded before model evaluation. Reasons appear
in `excluded.json`; the catalogue retains their provenance. Besides exact base,
family and normalized-AST checks, a conservative normalized-AST string similarity
threshold of 0.90 is enforced against the train and validation source inventories.
Semantically overlapping run-encoding tasks were also excluded even where their
original family labels differed. Every selected source has a unique normalized AST.

The existing A, B, Critic, Judge and General collectors use
`backend/data/manifests/stage1.json`. The audit opens only its train and validation
assets: 100 records from 50 base problems, hash-bound in `validation.json`. The
assessment and final-assessment assets stay unopened. Consequently disjointness
against the sealed final population is **unknown**, rather than claimed from
uninspected contents. New family names describe actual task semantics.

Contracts may declare relational preconditions beyond rectangular ValueDomains:
sorted inputs for binary searches; valid interval endpoints; rectangular matrices
where specified; valid Roman numerals, versions and postfix expressions. All
supplied and scoring inputs satisfy those preconditions. These functions therefore
do not promise behavior for every point in the enclosing domain. No registered
property template precisely represents these novel contracts, so requirements
have no template binding. Proposed observation experiments remain non-authoritative.

The tests are finite, hand-written examples, not an exhaustive correctness proof.
Tier assignments describe task/bug difficulty, not measured model performance.

## Commands (from repository root)

```sh
export CODEJURY_STAGE2_RUNNER_IMAGE=sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f
backend/.venv/bin/python backend/tools/dev_bench_run.py validate --out backend/data/dev_bench/validation.json
backend/.venv/bin/python backend/tools/dev_bench_run.py run --out backend/artifacts/dev_bench/baselines-v1
backend/.venv/bin/python backend/tools/dev_bench_run.py summarize --out backend/artifacts/dev_bench/baselines-v1
```

`run` defaults to seeds 17, 29 and 43 and all three methods. It requires current,
successful Docker validation and four completed current-role adapters. Each job
writes a new protocol file exclusively, append-only commitments, append-only scores
and a summary. It never overwrites previous jobs. Use `--resume` with exactly the
same protocol after interruption. A partially written JSONL line fails closed.
A changed benchmark, runner, model registry or sandbox refuses resume.

`--ids unordered_pairs --seeds 17` is an explicit harness smoke subset. Its protocol
has `full_population: false`; its results cannot stand in for full baselines.

B-base is the raw base without adapters, one attempt, and an unverified prediction.
Incorrect raw predictions count unsolved, never as wrong accepted patches. B-single
uses one trained Fixer A adapter, up to eight blind attempts, with supplied-suite
selection and no Critic, Judge, AST search or revisions. J-current is the unchanged
learned jury. All share the existing caps; B-base is deliberately single-shot and
uses less compute. The v1 sampler remains greedy; changing attempt seeds does not
provide temperature diversity. Candidate counts and unique source counts are both
recorded. These are matched **caps**, not guaranteed matched actual consumption.

All method commitments precede any hidden scoring, so hidden outcomes cannot steer
later methods. Only the selected source is scored. Scoring calls are recorded
separately from repair-budget executions. Invalid input/output, infrastructure and
cancelled runs all count unsolved. Wilson intervals use independent base counts
separately for each seed and tier; seeds never inflate a binomial denominator.
Peak memory is the native MLX allocator's measured per-generation maximum, excluding
VM and other process memory. Total system peak remains unknown. Raw logs and ledgers
stay in local ignored artifacts; aggregate reports belong in `docs/`.
