# A2.04 candidate and view audit

CPU implementation is complete. Native A/B acceptance awaits a real B adapter and Sarvesh ToolPort. This checkpoint does not claim learned diversity, executable repair quality, or E2 acceptance.

Intake parses ASTs without executing code. Controller IDs preserve supplied values and approved requirement references. Target/helper interfaces are checked, and semantic validation uses the injected checked ToolPort. Unsupported intake cannot start the initial pair.

Both initial prompts are frozen before generation. B receives contract, signature, domains, helper behavior interfaces, dependencies and visible tests; source bodies, A output, diagnosis and trace are absent. Full requests, responses, role identities, seeds, prompt hashes, retries and duplicate associations remain in the private content-addressed store. Format retries reuse the allowed view and charge fresh attempts/tokens. Prose, Markdown, duplicate JSON keys, missing/extra fields and oversized drafts fail. Invalid source is refused without replacement, and initial B is still attempted.

All proposals retain provenance. Alternatives deduplicate exact/normalized AST sources separately. Revisions require the registered parent, exact hash, correct fixer family, and controller-built observed input/oracle/output/effect/exception/trace facts. Model hints never authorize tests. Judge receives frozen state and bounded visible evidence without bodies; Critic receives approved registry and candidate evidence. Strict wire records reject hidden fields.

Immutable candidate rows remain pending. Qualification derives eligibility from semantic receipts for the exact source/current hard tests, complete passing effects, all supplied hard tests, no mutation/exception/failure, matching runtime and settled successful transport. Original is never selected. New hard tests change the suite hash and invalidate prior qualification. Eligible initial A remains incumbent; otherwise edit distance and proposal order break ties. These are finite checks, not proof of universal correctness.

Integration tests exposed a budget dispatch race: request construction consumes milliseconds after reading the wall allowance. Dispatch now tightens it to the current deadline while preserving all counter ceilings and final reservations. A deterministic clock regression covers the fix.

Verification from backend:

- `python -m pytest -q`: 201 passed, 9 hardware/sandbox checks skipped.
- `python -m codejury.stage2_core.views_cli audit --fixtures ../contracts/stage2-fixtures --out artifacts/stage2_core/view-check.json`: 9 synthetic checks passed, no inference/execution.
- `python -m codejury.stage2_core.contract_check --contracts ../contracts`: 83 definitions, 49 frozen fixtures; schema/ports unchanged.
- Ruff passed. Stage 1 remains untouched.

The actual A2.03 malformed native outputs remain documented in model-audit.md. This boundary rejects them; it does not reinterpret them as repairs. Native format/executable validation belongs to A2.05. Runtime artifacts and prompt bodies stay private and ignored.
