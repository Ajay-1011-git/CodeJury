# Stage 2 workbench (S2.11)

`web/stage2.html` + `web/src/s2/*.mjs` + `web/stage2.css`. The original Stage 1 page, modules,
tests and mock are **unchanged** (`index.html` is still `stage1.v1`); at merge the integrator can
serve `stage2.html` as the default page. No framework, no build step, same-origin by default,
explicit localhost-only `?api=` override.

| Module | Role |
|---|---|
| `api.mjs` | typed `stage2.v1` client, all ten routes, health guard (`service`, version and frozen `contract_hash`), 404/409/422/503 messages, cursor validation |
| `domain.mjs` | strict json.v1 parser (no floats/dup keys/unsafe ints), ValueDomain validation + membership, intake mirror (templates, allowlist, contradictions) |
| `model.mjs` | pure view-models: lineage + hash-chain check, role/view cards, stale detection, test matrix, gaps, timeline, resources, download, reports |
| `state.mjs` | 1000 ms polling, cursor dedup, generation-token stale-response guard, terminal stop, dispose on `pagehide`, success withdrawal |
| `views.mjs` / `app.mjs` | DOM via `textContent` only; no `innerHTML`/`eval`/`new Function` (enforced by a test) |

## What the page shows
- Persistent **FIXTURE** banner whenever `runtime_mode` is `fixture`; submission is blocked until
  the health check matches this UI's contract hash.
- Repair desk: typed domain JSON per argument, ≤3 helper interfaces, requirements with source,
  approval and the exact enforced template wording, supplied tests, dependency consent from the
  reviewed allowlist, fixed `mac-standard-v1` profile, learned/fixed policy, seed. Approval happens
  before the run; benchmarks never get human oracle rescue.
- Case file: A/B initial-view labels and role cards, parent/edit/hash lineage (a broken chain is
  flagged), authoritative vs proposed vs observation-only test matrix, "qualification STALE"
  when a candidate's suite hash is not the current one, audit gaps bound to exact source+suite
  with "equivalence unknown", probes labelled *not a vote*, Judge actions with refusals and
  FIXED FALLBACK markers, actual resource usage (null → "not measured", 0 stays 0), decision text
  and scope.
- Download comes only from the backend decision: the selected candidate must be non-original,
  eligible and current, and its bytes must hash to `source_hash` (SubtleCrypto). Cancel,
  infrastructure error, unresolved, invalid input or a later withdrawal clear it.
- Training & benchmark tab: adapter cards (general comparator labelled as not a jury role),
  exact solved/total, six-way partition check, null precision, not_run/partial/completed,
  research outcome, limitations. Fixture reports are labelled and never share a chart with live.

## Verification actually run
| Check | Result |
|---|---|
| `python3 web/tools/check_stage2_fixtures.py --contracts contracts` | 49 fixtures, 0 failures |
| `node --test web/tests/*.test.mjs` | 69 pass (35 new Stage 2 + 34 Stage 1) |
| `python3 -m unittest web/tests/test_stage2_mock.py` | 5 pass |
| `python3 web/tools/stage2_browser_check.py --base-url http://127.0.0.1:8080` | ok: module graph, no inline script, no injection paths, Stage 1 page preserved |

### Manual browser checks (built-in browser pane, mock on :8001, static server on :8080)
Recorded as observed; **not** automated.
- `audit-gap`/`refusal` scenario: health pill "codejury-stage2 · fixture", banner visible, example
  prefilled; submit → queued → running → SUPPORTED_PATCH; 4 candidate cards (original marked
  not selectable), lineage "hash ok boundary_constant @ line 3: 1 → 0", test matrix rows, gap with
  "probe, not a vote", timeline with "action refused" and "FIXED FALLBACK", download link
  `sum_values.809a5da60b2c.py`. The shared fixtures carry placeholder hashes, so the gap shows
  STALE (correct behaviour for unbound hashes).
- `withdraw` scenario: success followed by an infrastructure-error report → INFRASTRUCTURE_ERROR,
  withdrawn notice, empty download slot.
- `--unavailable`: pill "Backend unavailable (503)", error box text, no run can start.
- Found and fixed during this pass: a syntax error (paren count) and an "Illegal invocation"
  caused by calling `setTimeout` as a method; unit tests had not covered the DOM/default-timer paths.

## Not covered
Mobile-width layout, keyboard-only walkthrough and a headless-browser regression suite were not
run. The UI has not been exercised against the real Ajay API (it does not exist on this branch).
