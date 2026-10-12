# Stage 1 integration and completion evidence

Integration checked on 12 October 2026 on the existing Apple Silicon demonstration Mac. The previous chat, “Pull CodeJury and process tasks”, and `00-Stages-and-Merge-Guide.md` supplied the backend context, milestone rubric and acceptance procedure.

## Merge provenance and resolution

- Canonical seed: `c0ef9625f8a7781433d4692222a18cc86a43ae02`.
- Verified Ajay backend: `ac366e1` (A.01–A.09), originally on main.
- Sarvesh frontend: `02c33b0` on `origin/sarvesh-changes`; seven frontend task commits follow `5570286`.
- Sarvesh's seed has an unrelated Git history. His seven implementation commits only add `web/`, but his initial seed differs from the canonical fixture/reference files. A normal shared-base merge was impossible.
- Created `codex/stage1-integration` from the canonical seed, merged main, then merged Sarvesh's full history with `--allow-unrelated-histories`. Retained both histories. Resolved seed conflicts by restoring **all contracts/reference files from main**, rather than accepting changed frozen files. Their tree contents remain identical to pre-integration main.
- Relocated Sarvesh's 16 synthetic development fixtures to `web/fixtures/` and adjusted his tests/tools. His mock API stays a separate, explicitly selected development tool. Finder metadata is excluded from Git.

The schema remains SHA-256 `5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df`.

## Integrated behavior

FastAPI mounts the repository-relative static web directory after all API routes. Backend-only tests remain usable without web files. `start.sh` starts the dedicated runner VM when needed, verifies trained/live readiness, serves UI and API together, and opens the browser. Model repair processes are created on request. Ctrl+C shuts down the server and repair worker; the dedicated VM remains available.

Corrections made during integration: same-origin API at every port; mock selection requires an explicit localhost query parameter; property consent starts unchecked and resets on changes; counterexample cells remain selectable after an inspection and clear across runs; evaluation headings reflect the report's actual assessment count; Stage 2 descriptions match the AST/mutation architecture. The professor demo guide now uses actual results, replacing synthetic 50-problem figures. Synthetic fixture provenance explicitly disclaims measured training results.

## Checks actually executed

| Check | Observed result |
| --- | --- |
| Backend CPU suite | 106 passed, 9 hardware tests deselected |
| New static mount/API separation and absent-web checks | 2 passed, included in CPU count |
| Frontend Node suite | 32 passed |
| Python mock API integration suite | 11 passed |
| Real runner/policy/model/view tests | 21 passed in 25.16 seconds; includes CPU views/policy and actual sandbox/native adapter checks |
| Canonical contract fixture check | 8 validated; checksum unchanged |
| Synthetic web fixtures | 16 validated against canonical Draft 2020-12 schema and Sarvesh's business-rule checker |
| Fixture development smoke harness | Static modules, mock routes/polling/report pass; expressly fixture-only |
| Source lint and launcher syntax | Passed |
| Launcher portability | Successfully started from `/private/tmp` |
| Duplicate launcher | Occupied port rejected without stopping the first server |
| Shutdown/restart | Verification server stopped cleanly and final version restarted |

## Live browser/API acceptance

The browser connected to http://127.0.0.1:8000 with `runtime_mode=live`, `model_ready=true`, `sandbox_ready=true`, `fixer_a_trained=true`, and `stage2_enabled=false`. No fixture banner was present. Native model revision and adapter hashes came from the real backend. No submitted Python source ran on the host.

- **Successful sum:** browser run `238285a4a36b44dcb75bbf509909e0cd`; original `return 0` failed supplied input `[2,-4,7]` with expected `5`. Generated `return sum(values)` passed 67 authoritative checks (one supplied plus 66 property checks), 135 executions, 467 input/202 output tokens, 30,447 ms. Downloaded `.py` and JSON through UI controls. Downloaded UTF-8 source SHA-256 `3251dbf18617cd67c47707cb9bd1611dbac212ff0ee9814a75b8ce1f34b85aad` exactly matched the selected candidate. This unscored public sum task overlaps the training family.
- **Final sum rehearsal:** `41ba09a937024d689b1a277343d5041f`, supported patch, 26,632 ms, same 135 executions and token counts; final screenshot shows actual selected source and downloads.
- **Unresolved unique:** browser run `cb97a46febaa4cddb5ca1a356ce01928`; real original failure, concrete property failures, one revision, final unresolved; 191 executions, 809 input/105 output tokens, 43,650 ms. Failed property checks include `[262,262]` and independently executed `[0,0]`. UI inspection of property-26 displayed repeated `-1000` elements in the output and an authoritative FAIL. Raw Critic format rejection and deterministic fallback were explicit in the timeline. No learned-Critic discovery claim is made.
- **Cancellation:** browser run `57be2a4392104ddbb3830296e66885ac` was visibly RUNNING before cancellation and ended CANCELLED with no selected candidate. Busy submission while it ran returned schema-valid HTTP 409.
- **Invalid input:** malformed supplied-test JSON was visibly rejected in the form; invalid HTTP run body returned schema-valid HTTP 422. All checked API responses retained no-store headers.
- **Evaluation UI:** shows actual 300-step trial, 80 train records, 40/10/10 bases and 1/10 solved for each method, with recorded evaluation provenance and unequal-budget caveat. Selected step-100 adapter hash matches the training evidence.

Public live reports, events, downloaded source, and screenshots are retained locally in `backend/artifacts/integration/` (ignored). The screenshots are `selected-patch.png`, `counterexample.png`, and `evaluation.png`. These are live evidence, separate from the development fixtures. The original native training, adapter reload and sealed assessment evidence remains under `backend/artifacts/training/` and `backend/artifacts/evaluation/`.

## What Stage 1 completion means

M1 safe execution/durable runs, M2 real repair service, M3 initial trained/reloaded Fixer A, M4 executable property challenge/revision, and M5 integrated application/measured demonstration now have recorded evidence on this Mac. This fulfills the five-of-ten planned milestone rubric in the merge guide. It does not establish 50% repair accuracy, equal research effort between stages, broad generalization or full-council superiority. No Stage 1 release tag is created by this integration task.

The current synthetic assessment is **1/10 solved for all three methods**. Stage 2 remains complementary B, learned Critic/Judge, AST repair search, mutation auditing and full research evaluation with matched budgets. Other machines need local weights, the real selected adapter/proof and public aggregate report; cloning alone does not reproduce those assets.
