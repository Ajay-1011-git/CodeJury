# CodeJury — Stage 1

Local Python repair prototype on an Apple Silicon Mac: trained Fixer A, raw/prompted Critic, fixed controller, isolated ARM64 sandbox, SQLite evidence store, and browser interface. The UI and API share one server. No mock server or frontend build is needed for live use.

Stage 2 work is integrated on `main`: selected native A/B/Critic/Judge adapters, isolated search/audit/investigation tools, canonical evidence/API/UI, 538 real alternative continuations and research method implementations. The selected Judge passes 28/28 held-out exact-menu checks. General training, native browser acceptance and the final benchmark remain unfinished. See [the current completion record](integration/stage2/COMPLETION.md).

## Stage 2 build docs

The complete [Stage 2 build pack](CodeJury-Stage2-Build-Pack/README.md) includes both owners' instructions, shared contracts, synthetic fixtures, and training/evaluation requirements. Read the [plan and merge guide](CodeJury-Stage2-Build-Pack/CodeJury-Stage2-Plan-and-Merge.md) first, then [Sarvesh's build guide](CodeJury-Stage2-Build-Pack/CodeJury-Stage2-Sarvesh.md) or [Ajay's build guide](CodeJury-Stage2-Build-Pack/CodeJury-Stage2-Ajay.md). Follow the common seed process before creating the owner branches.

## Start everything

From this folder:

```sh
./start.sh
```

The launcher checks the trained model and adapter, starts the dedicated `codejury-stage1` Colima VM if necessary, starts the API and UI, verifies live health, and opens **http://127.0.0.1:8000**. The native model worker starts when a repair is submitted. Keep the terminal open. **Ctrl+C** stops the server and its repair worker. The sandbox VM stays available; stop it separately with `colima stop codejury-stage1` when finished.

Use `./start.sh --no-open` to skip opening a browser. Set `CODEJURY_PORT=8002 ./start.sh` to use another port. An occupied port fails with a clear message; the launcher never stops someone else's server. The script resolves paths relative to itself, so it also works when invoked from another folder.

## First-time setup

Install Python environment manager `uv`, Docker CLI, and Colima. Stage 1 requires macOS on ARM64 and Python 3.11. On this existing Mac the dependencies, weights, selected adapter, smoke proof and evaluation report are already available.

For a fresh checkout, install the locked backend dependencies:

```sh
cd backend
uv sync --frozen --python 3.11 --extra model
colima start codejury-stage1 --arch aarch64 --vm-type vz --cpus 2 --memory 2 --disk 10 --mount none --activate=false --ssh-agent=false --ssh-config=false --dns 1.1.1.1 --dns 8.8.8.8
.venv/bin/python tools/runner/build.py
```

Download the exact model revision documented in `backend/docs/handoff.md` to `backend/models/Phi4-mini`. Transfer the genuine selected adapter (including `freeze.json`) to `backend/artifacts/training/fixer_a_selected`. These large/local files are intentionally absent from Git. Transfer the public aggregate `training-report.json` into `backend/artifacts/evaluation/` to display the original recorded evaluation; private assessment data is never needed by the UI. The training card explains how to run a new experiment if the trained adapter is unavailable.

With the assets installed, create/verify the real native smoke proof:

```sh
export CODEJURY_MODEL_DIR="$PWD/models/Phi4-mini"
export CODEJURY_ADAPTER_DIR="$PWD/artifacts/training/fixer_a_selected"
.venv/bin/python -m codejury.models.cli smoke --config config/model.yaml
cd ..
./start.sh
```

Custom model and adapter directories can be supplied through the same environment variables. Missing weights, invalid adapter proof, or unavailable sandbox fails readiness; the launcher requires trained A.

## Demonstrate Stage 1

1. In **Repair desk**, select **Sum signed integers**. Review **Source code**, **Contract**, and **Test cases**; explicitly approve `sum_ints` in **Contract**. Run verification. **Run evidence** opens automatically with the original failure, generated repair, authoritative PASS cells, bounded verification scope, and actual resource usage. This public mechanics example overlaps the training family and is unscored.
2. Download the selected Python source and JSON evidence report. The source hash must match the selected candidate's `source_sha256`.
3. Select **Preserve first-occurrence order**, approve its property and run it. Inspect concrete counterexamples, the revision event and the actual final outcome. The current adapter can leave this unresolved.
4. Start another run and cancel it. Show cancellation without a selected patch. Invalid input produces a typed error.
5. Open **Training log**: 300 actual training steps, selected checkpoint 100, 40/10/10 base split, and the measured comparison below. Switching workspace or editor tabs preserves your draft and ongoing run.

| Method | Solved / total | Unresolved | Incorrect accepted |
| --- | --- | --- | --- |
| Raw single-shot | 1 / 10 | 9 | 0 |
| Trained A single-shot | 1 / 10 | 9 | 0 |
| Stage 1 loop | 1 / 10 | 9 | 0 |

This synthetic internal assessment shows improved formatting and single-shot token cost after training, with no measured solved-count improvement. Loop and single-shot budgets differ. Five of ten planned milestones constitute the Stage 1 completion rubric; they do not imply 50% repair accuracy. Complementary Fixer B, learned Critic/Judge, AST repair search, mutation auditor and full matched-budget research evaluation remain Stage 2.

See `docs/stage1-integration.md` for merge/acceptance evidence and `web/docs/professor-demo.md` for a short presentation script.

The frontend follows the root `DESIGN.md` with local fonts, original pixel sprites, accessible tabs, and responsive paper-window layouts. See `docs/frontend-design.md` for implementation and verification notes.

## Development benchmark (next phase)

The new development benchmark contains 100 independently authored problems and
separate runtime/scoring files. It uses the existing local models and Docker runner;
no cloud call or download is needed. The sealed final assessment stays unopened.

```sh
export CODEJURY_STAGE2_RUNNER_IMAGE=sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f
backend/.venv/bin/python backend/tools/dev_bench_run.py run --out backend/artifacts/dev_bench/baselines-v1
```

Use a new output directory for a new experiment, or add `--resume` for an interrupted
job with the same protocol. The full default experiment is 100 bases, three methods
and seeds 17, 29, 43; it runs sequentially and can take several hours. See the
[benchmark protocol](backend/data/dev_bench/README.md) and
[baseline results](docs/dev-bench-baselines.md). All 900 baseline runs are complete
and scored: the current jury solves 30–35/100 per seed, with 6–10 wrong acceptances;
the trained single-model comparator solves 1–3/100. Raw responses all fail the
required format. These are development results, with intervals reported per seed.

## Checks and development

```sh
(cd backend && .venv/bin/python -m pytest -m 'not sandbox and not mac' -q)
(cd web && npm test)
backend/.venv/bin/python -m unittest discover -s web/tests -p 'test_mock_api.py' -q
backend/.venv/bin/python -m codejury.contracts.check contracts
backend/.venv/bin/python web/tools/validate_contract.py --contracts contracts
```

Real hardware checks require the model/adapter environment variables above and the running dedicated VM:

```sh
cd backend
CODEJURY_SANDBOX_TESTS=1 CODEJURY_MODEL_TESTS=1 .venv/bin/python -m pytest tests/test_runner_policy.py tests/test_runner_sandbox.py tests/test_model_views.py tests/test_model_adapter.py -q
```

The original `backend/tools/handoff_check.py` audits Ajay's **isolated backend branch** against its saved base. Its backend-only ownership assertion intentionally does not apply to the merged application. Run the integrated checks above after merging.

For explicit fixture-only UI development, run `backend/.venv/bin/python web/tools/mock_api.py` and a separate static server on port 8080. Open `http://127.0.0.1:8080/?api=http://127.0.0.1:8001`. Synthetic examples live in `web/fixtures`; the frozen `contracts/` and `reference/` files remain byte-for-byte canonical. Fixture results must never be presented as live project evidence.
