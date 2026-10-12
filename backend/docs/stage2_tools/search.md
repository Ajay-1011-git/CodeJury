# AST repair search (S2.04)

Code: `src/codejury/stage2_tools/search/` (`operators.py` edit families, `engine.py` search).

## Inspected APIs (Python 3.12 here; the project targets 3.11)
`ast.NodeTransformer`, `ast.copy_location`, `ast.fix_missing_locations` and `ast.unparse` exist
in both. Parse success does not establish compilability, so compile/execute happens only in the
sandbox. Edits are applied to a `copy.deepcopy` of the parent per proposal.

## Edit families
| Family | Edit | Excluded |
|---|---|---|
| comparison | `< <= > >= == !=` replaced by neighbours | `is`, `in` |
| boundary_constant | integer literal ±1 | `bool`, unsafe integers |
| boolean_negation | negate `if`/`while`/ternary/comprehension condition, or remove an existing `not` | |
| arithmetic | `+ - * // %` swapped (BinOp and AugAssign) | `/` and `**` (float-producing) |
| variable_reference | another name bound in the same function | unknown/global names |

Operators never add branches or introduce literals other than ±1 of an existing literal, so
test-specific constants cannot be injected. Each result must keep the target signature, helper
signatures and imports (`check_edit_result`).

## Algorithm
1. Up to 3 parents (original plus promising failed A/B drafts) are evaluated once on the
   authoritative tests to find the known failing checks (these runs are real, charged and
   reported).
2. Proposals are ranked: model-hinted sites first, then lines named by candidate exceptions, then
   family/position order. Hints order work only; a wrong hint cannot hide a fix.
3. Parents are interleaved. Each executed candidate runs the known failing checks first; only if
   all pass does it run the rest of the common suite (stop on first hard failure).
4. Depth 2: a beam of the 4 best partially successful single edits seeds second edits.
5. Returned candidates passed every authoritative test. Partial success is never returned.

Caps: 48 executed unique candidates and 192 preflight proposals per episode; the engine also
keeps `len(tests)` executions in reserve for final qualification.

## Lineage
`edits[0].parent_source_hash` is the root parent's exact hash; `edits[i].result_source_hash ==
edits[i+1].parent_source_hash`; the last result hash equals the candidate's `source_hash`.
`ToolResult.edit_sources` carries the exact intermediate source. The descendant's `parent_id` is
the committed root, so a two-edit result is a descendant, not an independent opinion.

## Verification
`python -m pytest tests/stage2_tools/test_search.py -q` (CPU, `FIXTURE_HOST_EXEC` double).
`python -m codejury.stage2_tools.search_cli self-test ...` needs the native sandbox and reports
`pending_native` without it. Controlled cases validate the engine; held-out results measure
usefulness later.
