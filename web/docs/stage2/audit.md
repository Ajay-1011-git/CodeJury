# Stage 2 UI audit (S2.01)

Inventory of the original Stage 1 UI at the time of the audit (unchanged by this task):

| Area | Files | Notes |
|---|---|---|
| Static page | `web/index.html`, `web/styles.css` | No framework, no build step |
| Seam client | `web/src/api.mjs` | Hard-coded `stage1.v1` guards; localhost-only `?api=` override; same-origin default |
| State/polling | `web/src/state.mjs`, `web/src/workspace.mjs` | 1 s polling, cursor dedup, terminal stop |
| Input | `web/src/input.mjs` | Stage 1 domains: `integer`/`list_integer`, one approved property |
| Evidence/results | `web/src/evidence.mjs`, `web/src/result.mjs` | Candidate/diff/verdict views |
| Training | `web/src/training.mjs`, `web/src/tabs.mjs` | `/stage1/training-report` display |
| Mock | `web/tools/mock_api.py` | Python standard library, fixture banner |
| Tests | `web/tests/*.test.mjs`, `web/tests/test_mock_api.py` | Node built-in runner |

Gaps against `stage2.v1` (addressed in S2.11): version guards, typed recursive domains, helpers,
requirements list, dependency consent, profile/policy fields, A/B view labels, lineage, test
matrix, audit gaps, Judge actions, reports and `/stage2/*` routes.
