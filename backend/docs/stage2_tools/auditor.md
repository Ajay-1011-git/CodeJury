# Mutation auditor (S2.05)

Code: `src/codejury/stage2_tools/auditor/engine.py`; operators are shared with search
(`search/operators.py`) but used for a different purpose: probes, not candidates.

## Semantics
| Outcome | Meaning |
|---|---|
| `killed` | An **authoritative** test rejected the mutant (wrong output, mutation, crash). Observations and proposed oracles can never kill. |
| `survived` | Passed every authoritative test. May be equivalent or a genuine test gap; says nothing bad about the parent by itself. |
| `timeout` | First rejection was a timeout (kept separate from killed). |
| `invalid` | Failed static re-check or did not compile in the sandbox. |
| `duplicate` | Same source as the parent or an earlier probe. |

`equivalence_status` defaults to `unknown`. After a mutant survives, it is compared with the
parent on up to 32 non-authoritative tests: any difference gives `observed_different`; agreement
on at least one gives `observed_equivalent` (sampled behaviour, **not** a proof).

`AuditGap`s group survivors by exact candidate source, suite hash, location and family and are
always `unresolved_test_gap`. `requirement_ids` are attached only when the caller can justify a
mapping; otherwise they stay empty with a warning. A revised candidate or a changed suite makes a
gap stale (`gap_is_stale`). Probes are never returned as CandidateDrafts; promoting a useful probe
edit needs explicit search registration and full acceptance.

## Budget
≤24 probes per version, ≤48 per episode (`episode_remaining`), 96 preflight proposals. Probe
slots are charged per returned mutant; sandbox calls are charged per actual invocation. Outcomes
are cached by (mutant source hash, suite hash); a cache hit costs no executions and a new suite
never reuses old rows. Budget exhaustion/cancel returns only completed probes.

There is deliberately no 100% kill target and no automatic equivalent-mutant solver.
Effectiveness is measured later by new valid failures and selected-patch correctness.

## Verification
`python -m pytest tests/stage2_tools/test_auditor.py -q` (CPU, `FIXTURE_HOST_EXEC` double).
`audit_cli self-test` needs the native sandbox; it reports `pending_native` otherwise.
