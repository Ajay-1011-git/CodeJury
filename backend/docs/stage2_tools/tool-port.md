# ToolPort, investigation and handoff (S2.06)

`codejury.stage2_tools.factory.make_tool_port(config_path) -> ToolPort` builds the real Docker
sandbox from `config/stage2_tools/runtime.yaml` and **fails closed** (`InfrastructureError`) when
`CODEJURY_STAGE2_RUNNER_IMAGE` or the VM is missing. The factory imports no test double.
`ToolPortImpl(sandbox)` accepts any `SandboxPort`; CPU tests inject `FixtureHostSandbox`
(`tests/stage2_tools/hostsandbox.py`, label `FIXTURE_HOST_EXEC`).

## Operation matrix (enforced by `port/verify.py` before any result leaves the port)
| operation | returns | must stay empty |
|---|---|---|
| validate | `ValidationReceipt` | everything else; 0 executions charged |
| evaluate | executions for performed (candidate, test) pairs | candidates, tests, mutants, gaps, edit_sources |
| search | candidates + executions (+ edit_sources) | tests, mutants, gaps |
| audit | probe mutants + gaps | candidates, tests, executions, edit_sources |
| investigate | admitted/quarantined tests + executions | candidates, mutants, gaps, edit_sources |

Other rules: `request_id` echoed; delegated IDs are `<id_prefix>-c|t|e|m|g NNN`; execution rows
refer to known candidates/tests; search chains rebuild hash-by-hash from the committed parent;
audit probes/gaps carry exactly the requested `suite_hash` and the exact candidate source hash;
tools never consume model/Judge budget; usage never exceeds `remaining_budget`; request tests
claiming `authoritative` status are re-derived through the oracle gate and refused if the gate
would not grant it.

`suite_hash` is opaque to the tool: the core owns the frozen hard-suite hash and the tool echoes
it (the shared fixtures use a synthetic placeholder, so the tool cannot and should not recompute it).

## Statuses
`ok`, `invalid_input` (structure/identity/oracle authority; nothing executed),
`budget_exhausted` and `cancelled` (completed prefix only, usage reflects completed work),
`infrastructure_error` (VM/image loss or an internal contract violation; never a semantic result).

## Investigation
Exactly one of `generator_spec` / `concrete_inputs`. Registered families: general, empty,
singleton, duplicates, ascending, descending, boundary, negative, unicode, missing_key,
audit_site; a family that cannot be expressed for the argument domain is rejected, not guessed.
`missing_key` produces domain-invalid inputs that are quarantined (`rejected`) and never run.
Hypothesis public APIs used (6.169.0): `given`, `settings`, `seed`, `strategies`, `find`,
`Phase`. Candidate predicates run through the sandbox seam; every probe, shrink attempt and
replay is charged. Authoritative requires an authorised oracle (approved requirement + registered
template or relation); model literals and observations are `proposed` / `observation_only`.
Shrunk failures are re-run against all targets; a failure that does not reproduce is
quarantined, not certified. ≤128 inputs per action, ≤512 registered tests per run.

## Verification
`python -m pytest tests/stage2_tools/test_tool_port.py tests/stage2_tools/test_investigation.py -q`
`python -m codejury.stage2_tools.cli self-test --config config/stage2_tools/runtime.yaml --out artifacts/stage2_tools/tool-port`
(exit 3 = native part pending). `python -m codejury.stage2_tools.contract_cli check --contracts ../contracts`.

## E1/E2 handoff for the integrator
- Entry points: `codejury.stage2_tools.factory.make_tool_port`, `codejury.stage2_tools.port.ToolPortImpl`.
- Dependencies used: `jsonschema`, `PyYAML`, `hypothesis` (already in the backend manifest). No manifest change proposed.
- Required environment: `CODEJURY_STAGE2_RUNNER_IMAGE` (built by `backend/tools/stage2_tools/runner/build.sh`).
- Not yet verified natively: every sandbox isolation check (see runner.md).
