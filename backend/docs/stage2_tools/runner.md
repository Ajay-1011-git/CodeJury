# Stage 2 runner (S2.03)

**Status:** logic verified on CPU with a labelled test double; native isolation checks are
**pending** (no Docker/Colima daemon was available when this was written).

## Layers
| Layer | File | What it does |
|---|---|---|
| In-image worker | `runner/entry.py` | Compiles and runs candidate source with a restricted builtins table and an import proxy that only exposes allowlisted symbols. Fresh globals per call, deep-copied inputs, before/after hashes, SIGALRM per-call limit (2 s), output codec check, bounded line trace. |
| Host sandbox | `runner/docker.py` | Fixed-argv `docker create` (no network, read-only root, uid 65532, cap-drop ALL, no-new-privileges, 512 MB, 64 pids, no mounts), post-create inspection, bounded stdout, external watchdog, `rm -f` of the whole container. |
| Evaluator | `runner/executor.py` | Turns (candidate, test) pairs into `Execution` records. Verdicts come from the trusted oracle gate, never from the candidate. Relations cost two calls. |

## Rules enforced
- Candidates are compiled/imported/executed only inside the sandbox. The host parses (`ast`) only.
- A hung call that the worker cannot interrupt is killed by the watchdog; the evaluator re-runs
  the chunk call-by-call and records the hung call as `timeout` (semantic), whereas VM/image loss
  is `InfrastructureError` (never a candidate verdict).
- Budget exhaustion or cancellation returns only completed rows and usage.
- Traces are only captured for requested lines, ≤32 events, ≤4 KB, locals sanitised through
  json.v1 (non-JSON locals appear as `<TypeName>`), content-hashed in `trace_ref`.
- No host paths appear in results; messages are clipped to 200 characters.

## Build and verify natively
```
colima start codejury-stage2 --arch aarch64 --cpu 2 --memory 2   # no mounts, no agent forwarding
backend/tools/stage2_tools/runner/build.sh                          # prints the image id
export CODEJURY_STAGE2_RUNNER_IMAGE=sha256:...
cd backend && python -m codejury.stage2_tools.runner_cli self-test \
  --config config/stage2_tools/runner.yaml --out artifacts/stage2_tools/runner
```
Exit code 0 = passed, 3 = pending native, 1 = failed.

## Honest limits
- `tests/stage2_tools/hostsandbox.py` (`FIXTURE_HOST_EXEC`) runs the worker as a local subprocess
  on controlled fixtures. It tests logic above the seam and the worker's own restrictions, not VM
  isolation. The live factory never imports it.
- The in-worker SIGALRM limit cannot interrupt a single long C call (for example a huge
  `math.isqrt`); the external watchdog is the backstop.
