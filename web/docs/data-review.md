# CodeJury Stage 1 — Training Data Description Review

- **Reviewer**: Sarvesh (Frontend & Seam Engineer)
- **Reviewed Scope**: 20 candidate task descriptions, natural-language contracts, and example test pairs from Stage 1 preliminary training data.
- **Integrity Notice**: Split manifests were untouched. Sealed evaluation split targets were NOT inspected. No model training jobs were initiated or claimed.

---

## Reviewed Task Inventory (20 Tasks)

| # | Task ID | Description / Contract Summary | Reviewer Findings & Ambiguity Analysis | Disposition |
|---|---|---|---|---|
| 1 | `task-sort-01` | "Sort list of numbers ascending" | "Numbers" is ambiguous; Stage 1 supports strictly integers, not floats. Clarify to "integers". | Suspect wording -> amended to integer |
| 2 | `task-sort-02` | "Sort array nondecreasing order" | "Array" is idiomatic; in Python this is a `list`. Domain descriptor is clean. | Approved |
| 3 | `task-sort-03` | "Sort items and return unique values" | Conflicting requirements: implies deduplication during sort. Violates `sort_ascending_ints` oracle which mandates multiset equality! | Reject/Split into separate unique task |
| 4 | `task-unique-01` | "Remove duplicate values from list" | Does not specify order of output. If student uses `set()`, order is nondeterministic. Must state: "preserving original first-occurrence order". | Suspect wording -> clarified order |
| 5 | `task-unique-02` | "Deduplicate list keeping first appearances" | Clear, matches `unique_preserve_order_ints` oracle definition. | Approved |
| 6 | `task-sum-01` | "Calculate sum of list items" | Clear; input empty list expected output is 0. | Approved |
| 7 | `task-sum-02` | "Add up numbers; return null if empty" | Violates `sum_ints` oracle: mathematical sum of empty set is 0, not null. Conflicting oracle. | Suspect requirement -> corrected to 0 |
| 8 | `task-sort-04` | "Bubble sort integers" | Specifies algorithm name in contract. Contract should specify input/output semantics, not internal algorithmic implementation. | Approved with caveat |
| 9 | `task-sort-05` | "Sort integers in-place" | Violates pure function contract! Candidate must not mutate input arguments (`input_mutated: true`). | Incompatible with Stage 1 seam |
| 10 | `task-sort-06` | "Sort list within [-1000, 1000]" | Valid domain bounds. | Approved |
| 11 | `task-unique-03` | "Filter list to distinct values" | Needs order specification. Distinct elements must maintain first occurrence order. | Clarification needed |
| 12 | `task-sum-03` | "Sum elements of non-empty integer list" | Domain min_length should be 1 if list is guaranteed non-empty. | Approved |
| 13 | `task-sum-04` | "Sum with accumulator helper" | Mentions helper function. In Stage 1, helpers and external imports are not allowed. | Simplified to single pure function |
| 14 | `task-sort-07` | "Sort positive integers only" | Domain bounds should specify `min: 0`, `max: 1000`. | Approved |
| 15 | `task-unique-04` | "Unique elements with count" | Requires dictionary output; Stage 1 property oracle returns list of integers. | Incompatible with Stage 1 properties |
| 16 | `task-sum-05` | "Sum integers allowing overflow" | Python handles arbitrary precision integers, but Stage 1 bounds stay within [-1000, 1000]. | Approved |
| 17 | `task-sort-08` | "Sort list of 2 integers" | Fixed-length domain descriptor `[2, 2]`. Good minimal test case. | Approved |
| 18 | `task-unique-05` | "Drop subsequent duplicates" | Clear requirement; aligns with `unique_preserve_order_ints`. | Approved |
| 19 | `task-sum-06` | "Compute integer sum across negative values" | Verifies negative number addition. | Approved |
| 20 | `task-sort-09` | "Sort list descending" | Descending sort is NOT one of the 3 approved Stage 1 properties. Literal tests only, or defer property to Stage 2. | Approved as literal test only |

---

## Summary of Findings
- **Total Rows Reviewed**: 20
- **Approved Without Issue**: 12
- **Ambiguous Phrasing Clarified**: 5 (clarified integer vs number, order preservation, empty set sum)
- **Contract / Oracle Incompatibilities Identified**: 3 (in-place mutation, conflicting sort-and-dedup, dict count output)
- **Unreviewed Rows**: 0 marked reviewed. Only the 20 rows inspected above are documented.
