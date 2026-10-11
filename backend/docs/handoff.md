# Ajay backend handoff

Git identity: Ajay M <ajaym556677@gmail.com>. No co-author attribution. User explicitly authorized commits and pushes to `main` after each audited task.

Shared seed base: `c0ef9625f8a7781433d4692222a18cc86a43ae02`. Initial upstream commit: `8db26b3`. The approved seed initialization precedes the backend-only work. Frozen schema hash: `5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df`.

| Task | Status | Evidence |
| --- | --- | --- |
| A.01 | Complete; native checks completed in A.03/A.06 | Six CPU tests, eight contract fixtures, environment and lint checks; versions/source audit in dependency-audit.md |
| A.02 | Complete | 36 intake/oracle/storage tests; frozen checker passes |
| A.03 | Complete | Five real self-checks and eight runner tests; image/mount evidence below |
| A.04 | Complete | 15 fixture lifecycle tests; genuine asynchronous native HTTP acceptance/report/cancel verified in A.07 |
| A.05 | Complete minimum prototype | 40/10/10 bases, 80 train records, 406 real validation jobs, 13 CPU tests |
| A.06 | Complete | Real seeded 10/300 steps, validation selection, correct sum smoke and A/raw/A hashes |
| A.07 | Complete | Bounded policy, real supported sum and unresolved unique episodes, live HTTP acceptance/report |
| A.08 | Complete | Actual same-10-base comparison, each method 1/10 solved, public completed TrainingReport |
| A.09 | Complete | 4 live episode exports, train-only 40-base/80-trial mining, 104 CPU tests, final native checks |

## A.01 actual verification

Commands run from backend using `.venv/bin/python`:

```text
python tools/check_environment.py
python=3.11.16 system=Darwin machine=arm64 foundation_ready=true
docker_cli=true colima_cli=false
model_inference=pending A.06 native smoke and training pilot
sandbox_execution=pending A.03 isolated execution checks
memory_bytes=null within sandbox; native sysctl independently returned 17179869184

python -m pytest tests/test_environment.py -q
6 passed in 0.56s

python -m codejury.contracts.check ../contracts
PASS error.json: Error
PASS event-page.json: EventPage
PASS examples.json: Examples
PASS health.json: Health
PASS run-accepted.json: RunAccepted
PASS run-create.json: RunCreate
PASS run-queued.json: RunSnapshot
PASS training-report.json: TrainingReport
PASS schema SHA-256 5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df; 8 fixtures
```

Audit found and corrected import ordering and made subprocess failure handling explicit. The checker refuses missing/changed schemas, unknown definitions, extra/missing wire fields, fixture symlinks, path traversal and unlisted JSON fixtures. Initial tests use synthetic fixtures only. Native MLX CLI help succeeds; actual inference/training remains pending. Docker daemon is unavailable and Colima is absent.

The A.01 commit can be found with `git log --grep='A.01' --format='%H %s'`; storing its own hash in the same commit would require rewriting that hash.

## A.02 actual verification

```text
python -m pytest tests/test_intake.py tests/test_oracles.py tests/test_storage.py -q
36 passed in 1.23s
python -m codejury.contracts.check ../contracts
PASS schema SHA-256 5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df; 8 fixtures
ruff check src tests tools
All checks passed!
```

Audit: submitted source is parsed only; default/annotation/decorator execution, imports, nested helpers, generators and global state are rejected. JSON bounds are depth 8, 4096 nodes, 8000-character strings and JS-exact integers. Domains reject bool/float values. Property templates use trusted deterministic implementations and type-sensitive recursive equality. Runtime paths must be disjoint from offline data. SQLite triggers enforce append-only events and immutable candidate rows; parallel append/reopen tests prove stable ordered IDs. No model or sandbox evidence is claimed.

## A.03 actual verification

```text
python -m codejury.runner.cli self-test --profile stage1-demo
architecture=arm64 host_mounts=[]
success actual_output=3 exception_type=null
input_mutation actual_output=10 input_mutated=true
timeout exception_type=TimeoutError duration_ms=2004
oversized_output exception_type=ValueError actual_output=null
PASS independent assertion mismatch detection; 5 real checks
CODEJURY_SANDBOX_TESTS=1 python -m pytest tests/test_runner_policy.py tests/test_runner_sandbox.py -q
8 passed in 5.19s
```

Runner image: `sha256:29ae090c8377a4e3d482dd6efa6fdee6a0d46a5d8eaabf916556ee341ae118b9`. Base Python 3.11.16 image: `python@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e`. Colima 0.10.3/Lima 2.2.1; VM Docker 29.5.2. Dedicated `codejury-stage1` VZ VM: aarch64, 2 CPUs, 2 GiB RAM, 10 GiB data disk; `--mount none`, no SSH agent/config forwarding, no global Docker-context activation. Initial DNS failure was resolved with explicit DNS 1.1.1.1 and 8.8.8.8. Effective `/proc/mounts` contains root/data/cidata and kernel filesystems, no `/Users`, home share, virtiofs or sshfs.

Each job is created then inspected before start: network none, no mounts/binds, UID 65532, read-only root, dropped ALL capabilities, no-new-privileges, 128 MiB memory/swap, PID limit 16, CPU 1 and 16 MiB tmpfs. Source/input are stdin data. Output/trace are bounded. A 2-second function timer and 4-second host watchdog are separate; cancellation removes the entire container. Real trusted probes verified blocked external TCP access and cleanup of both processes after `os.fork`. Candidate builtins and introspection are restricted inside the VM; this is additional defense, not a host-execution fallback.

## A.04 actual verification

```text
python -m pytest tests/test_api_lifecycle.py -q
15 passed in 2.82s
python -m uvicorn codejury.api.app:app --host 127.0.0.1 --port 8000
python tools/api_smoke.py --base-url http://127.0.0.1:8000 --contract ../contracts/stage1-api.schema.json
PASS GET /health: 200 Health
PASS GET /examples: 200 Examples
PASS GET /stage1/training-report: 200 TrainingReport
PASS GET /runs/unknown: 404 Error
{"runtime_mode":"live","model_ready":false,"sandbox_ready":false,"run_submission_status":503}
```

All frozen endpoints implemented. Synthetic worker exists only in tests and labels every snapshot/health as fixture; no fixture mode switch exists in the live application. Live native worker/loop loading remains A.06/A.07, with honest pre-acceptance 503. One SQLite transaction owns the queued/running slot; two concurrent requests produce one 202 and one 409. Cancellation is idempotent and retains the slot until a native worker stops. Restart terminates abandoned records as infrastructure_error, never replays generation. Dedicated spawned processes and exit watchers are wired; real model work is not yet exercised. API response bodies validate against the frozen schema, with JSON/no-store headers. Request bodies are bounded at 256 KiB. Development CORS accepts explicit localhost origins only. HTTP server was stopped after smoke.

## A.05 actual verification

```text
python -m codejury.training.cli collect-data --manifest data/manifests/stage1.json
Collected 70/70 bases: catalan
train=40 bases/80 records; validation=10/20; assessment=10/20; reserved Stage2=10/19
rejected_variants=1 (ineffective Stage2 corruption)
python -m codejury.training.cli validate-data --manifest data/manifests/stage1.json
manifest_sha256=95fabdb275e7f76e0b8aaa610e1708956aaf9a6666215c035fe0a6623ca7741a
rejected=[] sandbox_executions=406 execution_mode=live
python -m codejury.training.cli export-sft --manifest data/manifests/stage1.json --out artifacts/training/fixer_a_sft
{"exported":{"train":80,"validation":20},"assessment_exported":0}
python -m pytest tests/test_training_data.py -q
13 passed in 0.17s
python -m codejury.contracts.check ../contracts
PASS schema SHA-256 5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df; 8 fixtures
```

All references and retained Stage1 bugs independently executed in the pinned sandbox; cache avoids repeated identical reference jobs without inventing execution counts. Tests reject base/family/alpha-normalized solution overlap, hidden/reference prompt leakage, wrong targets, non-failing bugs, reference failures and changed observations. Test-only runner data cannot write a live validation proof. Export requires the live proof and current manifest hash. Data is synthetic return corruption; no natural errors, external benchmarks, or broad generalization claim. Private validation/assessment/Stage2 bytes are ignored, their hashes are sealed. Offline authoring code is public, so this assessment is hidden from runtime, not secret from source-reading developers. See data-card.md for limitations.

## A.06 actual verification

```text
python -m codejury.training.cli pilot --config config/training/fixer_a.yaml
completed_steps=10 reload_verified=true (final NumPy/MLX seed17 pilot)
python -m codejury.training.cli train --config config/training/fixer_a.yaml
completed_steps=300 reload_verified=true mask_verified=true max_train_tokens=444
elapsed_seconds=136.2167462919606 peak_memory_mb=3144.467552
python -m codejury.training.cli select --config config/training/fixer_a.yaml
selected_step=100; validation 2/10 solved, 0 malformed at each of 100/200/300
adapter_sha256=274fd6b1a4a9abd04a8a2d3e56cfbde765c81e71fdb230682f4bf66509605fb4
python -m pytest tests/test_model_views.py tests/test_training_data.py -q
24 passed in 0.48s
```

Native checks use CODEJURY_MODEL_DIR and CODEJURY_ADAPTER_DIR shown in training-card.md. The sum smoke is a disclosed training-family-overlap mechanics demonstration; unique and raw-format failures remain retained. See training-card.md for actual loss worsening, fixed shuffle-seed defect, model/license/hashes and evidence locations. No sealed assessment was opened for selection.

```text
CODEJURY_MODEL_TESTS=1 python -m pytest tests/test_model_views.py tests/test_model_adapter.py -q
12 passed in 11.88s
python -m codejury.models.cli smoke --config config/model.yaml
candidate_valid=true switch_verified=true actual_output=5
A first/reloaded=62ad79b24257fe107b1079068fce3b8224dabcadeab4c43345edcbf33b686546
raw=970ebb09dd0c16f90cd3c842a32aec1a194df41ee90def7b5a5a9af986c4888b
```

## A.07 actual verification

```text
python -m pytest tests/test_loop.py tests/test_property_engine.py -q
10 passed in 3.06s
python -m pytest -m 'not sandbox and not mac' -q
92 passed, 9 deselected in 3.46s
CODEJURY_SANDBOX_TESTS=1 python -m pytest tests/test_runner_policy.py tests/test_runner_sandbox.py -q
9 passed in 6.44s
python -m codejury.controller.cli run --request ../contracts/fixtures/run-create.json --config config/model.yaml --out artifacts/demo/live-run.json
run_id=670668cd1e0a4a26a11b042ba6dfefb7 status=unresolved
809 input tokens; 105 generated tokens; 191 function executions; 29562 ms
python -m codejury.controller.cli run --request artifacts/training/public-sum-request.json --config config/model.yaml --out artifacts/demo/live-sum-run.json
run_id=d096a4f4cc444ce8abb21fb8a2bda22f status=supported_patch
467 input tokens; 202 generated tokens; 135 function executions; 20075 ms
python tools/api_smoke.py --base-url http://127.0.0.1:8000 --contract ../contracts/stage1-api.schema.json
PASS all HTTP envelopes; live model_ready=true sandbox_ready=true POST=202
Real asynchronous HTTP sum repair: run_id=a0ebc38aea3143c0a4bbba03b1f9162c
supported_patch, busy=409, 208 events; 467 input/202 output tokens; 135 executions; 20734 ms
```

The fixed policy reproduces the supplied failure, generates A, checks supplied tests, calls raw Critic, explores approved properties (or observations), permits one revision and selects only an independently checked generated patch. The real unique example still fails after revision. Raw Critic used Markdown fences, so strict parsing rejected it and events identify the deterministic general fallback; no agent-discovery claim. The real sum example passed all admitted authoritative checks. Its training-family overlap remains disclosed.

Hypothesis 6.169.0 `given`, `settings`, strategies and `find` APIs were inspected directly and against https://hypothesis.readthedocs.io/en/latest/reference/api.html and https://hypothesis.readthedocs.io/en/latest/reference/strategies.html. Host code generates values and checks trusted oracles only. Sandbox batches contain at most eight invocations, each in a fresh child interpreter. A verified shrunken failure is independently replayed; a bounded shrink may stop before global minimality and reports shrink_limited. At most 100 exploration inputs including replay, 400 attempted executions, 4096 total generated tokens, one format retry, one revision, 600 seconds. Original cannot be selected; no learned Judge or confidence values.

Necessary integration edits extend the existing runner/image for batches and deadline propagation, and cache only schema self-validation (checksum is checked on every load; fresh schema objects remain independent). Runner image is now `sha256:2e357513b8bd95894224280a265c6d4153d160aca1bb1f57a6370d6ceaf9e9f5`; base digest unchanged. Unsupported sandbox AST policy returns semantic UnsupportedSource rather than infrastructure failure. Native worker shutdown cleans only its own PID-labelled containers if forced termination is necessary. The live HTTP server was stopped after verification. Runtime episodes/generations are ignored, separate from offline assessment.

## A.08 actual verification

```text
python -m codejury.evaluation.cli stage1 --manifest data/manifests/stage1.json --config config/model.yaml --out artifacts/evaluation/stage1-results.json
raw_single: solved=1 total=10 unresolved=9 incorrect_accepted=0 mean_elapsed_ms=7626 mean_output_tokens=203
trained_a_single: solved=1 total=10 unresolved=9 incorrect_accepted=0 mean_elapsed_ms=2756 mean_output_tokens=35
stage1_loop: solved=1 total=10 unresolved=9 incorrect_accepted=0 mean_elapsed_ms=56391 mean_output_tokens=239
python -m pytest tests/test_evaluation.py -q
5 passed in 0.15s
python -m pytest -m 'not sandbox and not mac' -q
97 passed, 9 deselected in 6.86s
python -m codejury.evaluation.cli export-report --results artifacts/evaluation/stage1-results.json --out artifacts/evaluation/training-report.json
TrainingReport schema valid, status=completed, steps=300, train/validation/evaluation bases=40/10/10
Actual GET /stage1/training-report: HTTP200 pilot_only before completed comparison; HTTP200 completed after export
```

All final answers were exclusively saved before private execution, with no hidden-feedback revision. Same visible-input hashes across all methods; first sealed variant per base was predeclared. Exact costs and retained failures are in stage1-results.md; no success improvement or matched-budget superiority claim. Runtime/API reads only public aggregate JSON, not private tests/source. Report export is atomic and missing losses use null. Real supported sum and unresolved unique episodes remain independently reproducible; UI integration is still pending.

## Run and reproduce the backend

Python 3.11.16, uv 0.12.10, FastAPI 0.143.0, Pydantic 2.14.0, jsonschema 4.26.0, Hypothesis 6.169.0, MLX 0.32.3, MLX-LM 0.32.0, Uvicorn 0.54.0, pytest 9.1.1 were verified on this 16 GiB ARM64 Mac. CPU policy/API tests use clearly labelled fixtures; native inference/sandbox evidence is separate.

From `backend/`, install with `uv sync --python 3.11 --extra model` and use `.venv/bin/python` for commands below. Existing local weights and selected adapter are available in this workspace. Machine-specific paths are environment settings, not committed absolute config values:

```sh
export CODEJURY_MODEL_DIR="$PWD/models/Phi4-mini"
export CODEJURY_ADAPTER_DIR="$PWD/artifacts/training/fixer_a_selected"
.venv/bin/python -m codejury.models.cli smoke --config config/model.yaml
.venv/bin/python -m uvicorn codejury.api.app:app --host 127.0.0.1 --port 8000
```

A fresh Mac needs the dedicated VM and built image. Preserve the default Docker context and disable all personal-directory/agent shares:

```sh
colima start codejury-stage1 --arch aarch64 --vm-type vz --cpu 2 --memory 2 --disk 10 --mount none --activate=false --ssh-agent=false --ssh-config=false --dns 1.1.1.1 --dns 8.8.8.8
.venv/bin/python tools/runner/build.py
```

The build records that machine's actual image ID in backend/config/runner.yaml. The current image is `sha256:2e357513b8bd95894224280a265c6d4153d160aca1bb1f57a6370d6ceaf9e9f5`; base `python@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e`. No host fallback is used.

Exact local model conversion: `mlx-community/Phi-4-mini-instruct-mlx-4Bit`, revision `d848c30f6d5419b9892433cf6b1062626d15340e`. The inspected Hugging Face CLI accepts:

```sh
HF_HUB_DISABLE_XET=1 hf download mlx-community/Phi-4-mini-instruct-mlx-4Bit --revision d848c30f6d5419b9892433cf6b1062626d15340e --local-dir models/Phi4-mini --include '*.json' '*.safetensors' '*.jinja' 'README.md'
```

Weights, adapters, private offline assets and all raw experiment outputs are ignored. To reproduce the identical experiment on another machine, transfer the selected adapter/config/freeze and private dataset bytes locally and verify their published hashes; they are not included by cloning Git. `data/manifests/stage1.json` fixes those asset hashes. Regenerating synthetic data creates new observed timings/bytes and a new experiment seal; it cannot be represented as the original frozen dataset. Existing collection/training/evaluation/freeze commands refuse overwriting evidence. The public source catalog is available for creating a new experiment, with the data card's limitations.

CPU handoff verification requires no weights or private data:

```sh
.venv/bin/python tools/handoff_check.py --contracts ../contracts
```

Explicit hardware verification, after setup:

```sh
CODEJURY_SANDBOX_TESTS=1 .venv/bin/python -m pytest tests/test_runner_policy.py tests/test_runner_sandbox.py -q
CODEJURY_MODEL_TESTS=1 .venv/bin/python -m pytest tests/test_model_views.py tests/test_model_adapter.py -q
.venv/bin/python tools/handoff_check.py --contracts ../contracts --native
```

The checker stores its actual checked commit SHA and native/CPU distinction in ignored `artifacts/handoff/check.json`. Before A.09, the completed measurement commit is `61d385b092e1cedd5f803a7ac7fceef87a953665`; find the final handoff commit with `git log --grep='A.09' --format='%H %s'`. This avoids an impossible self-referential commit hash inside its own contents. Every backend task is separately committed/pushed using Ajay M, without co-author trailers. Approved seed initialization is the only change before the saved shared base; the comparison from that base is backend-only and the schema remains unchanged.

## Limits and remaining integration

The synthetic prototype meets the minimum 40/10/10 base split, not the larger 80/20/20 collection target. No natural student errors were supplied or fabricated. Training improves format conformity but the current sealed assessment remains 1/10 solved for all methods, with unequal loop/single budgets. Raw Critic formatting can fail; deterministic fallback is explicit. A verified bounded patch is supported only within admitted authoritative checks, never presented as universal correctness. Known failed generations and validation-loss worsening remain in the evidence.

Sarvesh's web module, live UI integration, screenshots and complete M5 release are pending. No partner files, full Stage1 release tag, B adapter, trained Critic/Judge, AST search, or mutation audit have been added. The Stage2 final pool has not been scored or used for mining. Backend scripts use localhost only; HTTP verification servers were stopped when their checks finished.

## A.09 actual verification and Stage2 hooks

```text
python -m pytest tests/test_episode_export.py -q
7 passed in 0.24s
python tools/export_episode.py runtime --out artifacts/stage2/runtime-visible-episodes.jsonl
{"episodes":4,"runtime_modes":["live"],"hidden_join":false}
python tools/export_episode.py mine-train --manifest data/manifests/stage1.json --config config/model.yaml --out artifacts/stage2/fixer-a-train-failures.jsonl --bases 5 --repeats 2
bases=5 trials=10 failed_trials=0 failure_base_records=0 (retained smoke, not fabricated failures)
python tools/export_episode.py mine-train --manifest data/manifests/stage1.json --config config/model.yaml --out artifacts/stage2/fixer-a-train-failures-full.jsonl --bases 40 --repeats 2
runtime_mode=live bases=40 trials=80 failed_trials=16 failure_base_records=8 split=train
python tools/handoff_check.py --contracts ../contracts
104 passed, 9 hardware tests deselected; contract fixtures/checksum and backend-only diff pass
python tools/handoff_check.py --contracts ../contracts --native
104 passed, 9 deselected in 3.18s
9 runner/policy tests passed in 5.44s (8 real sandbox + 1 CPU policy)
12 model/view tests passed in 11.76s (1 real native adapter + 11 CPU views)
```

The first native checker run found the CPU suite inheriting live model paths, making an unavailable-model boundary test incorrectly see model_ready=true. The checker now explicitly isolates its CPU environment using nonexistent local model paths, then keeps actual model settings for hardware tests. This is test-environment isolation, not substituting live inference. The final complete check above passed; skipped hardware tests in the CPU invocation are not presented as passed.

Runtime JSONL has stable visible problem, candidate, test, action and outcome IDs. Unknown offline fields are dropped; unapproved/hidden authoritative literals and malformed counterexample fields are rejected. Runtime export SHA-256: `ab99f41c705955cec2da9237b5e3f63a4eb79de2a3649c2f3ab7c8621c83cb58`. It contains public live episodes only, not assessment sessions.

Training-only joins reject assessment/Stage2 IDs and unmatched visible requests. The loader opens only the sealed train asset. Full mining used the first buggy variant from each of 40 training bases, with two actual deterministic-settings A trials each; 80 repeated trials are not 80 independent problems or both original variants. The 8 failed bases are clamp, above_threshold, negative_positions, adjacent_differences, ceil_quotient, palindrome_sequence, all_equal and one_positive. Each failed twice. Failure export SHA-256: `3ca9312dee2079feba4442fbb2f081befc978d83e215e18fc47b1a2869ceef6f`.

`artifacts/stage2/fixer-a-train-failures-full.jsonl` contains train provenance, source IDs, visible requests and repeated raw A outputs/outcomes. Independently frozen answers and offline training assessment outcomes are separate in `fixer-a-train-failures-full-evidence/offline-training-join.jsonl`; no private assessment test inputs or reference sources appear in the runtime-visible export. This supplies hooks/evidence for future B/Critic/Judge work, without training any Stage2 role. The sealed Stage1 assessment and final Stage2 pools were not opened for mining. Injection cannot claim live mining.

Final verification compares `git diff --name-only c0ef9625f8a7781433d4692222a18cc86a43ae02...HEAD`; all changed paths are under backend. No weights, private datasets, SQLite databases, generated experiments or root Finder metadata are tracked. The frozen schema hash is unchanged. Current tracked work is complete for A.01–A.09; whole-application M5 remains pending partner UI integration.
