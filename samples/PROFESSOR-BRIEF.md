# CodeJury: Project Briefing

**Authors:** Ajay and Sarvesh
**Stage demonstrated:** Stage 1 prototype (local, live inference)
**Date:** 14 October 2026

## 1. Purpose

CodeJury repairs small bugs in Python functions. The system has three properties:

- **It does not trust its own model.** A language model proposes a patch, and only executed tests decide whether the patch is accepted.
- **The user's specification is the source of truth.** The user supplies a natural-language contract, an input domain and test cases. These define correct behaviour.
- **It may refuse to answer.** If no patch passes every authoritative check, the system reports *Unresolved* and does not present a guess as a fix.

## 2. How a run works

| Role | Implementation | Responsibility |
|---|---|---|
| **Fixer A** | Phi-4-mini with a LoRA adapter fine-tuned by us | Reads the buggy code, contract and failing tests, then proposes a patched function. If the patch fails, it receives the failure evidence and proposes one revision. |
| **Critic** | The same base model, prompted without the adapter | Proposes a plan for challenging each patch. If its reply is invalid, a fixed fallback plan is used; in all our runs the reply was invalid. |
| **Controller** | Fixed, deterministic policy | Runs every candidate in an isolated sandbox VM, records each execution, and rejects any candidate that fails an authoritative check. |

**Which tests count.** The user's supplied tests are authoritative. When the user also approves a *property*, that property becomes an authoritative oracle too: sorting, order-preserving de-duplication or summation, which the system computes independently of the candidate code. The test engine then generates extra inputs from the challenge plan and checks them against the property, and this is where a weak patch is caught. Without a property, those extra inputs are recorded only as observations.

**Possible verdicts.**

- **Supported patch:** every admitted authoritative check passed.
- **Unresolved:** no candidate passed.

The dashboard shows the full evidence for each run: every proposal with its diff, every execution, and the reason for every rejection.

## 3. Demonstration results

We ran eight cases on the live system, each twice. Case 8 was run once.

| # | Bug | Verdict | What it shows |
|---|---|---|---|
| 1 | Sort returns its input unsorted | Supported, 2/2 | First patch rejected by a generated counterexample; revision accepted after 82 checks |
| 2 | `set()` loses first-occurrence order | Supported, 2/2 | First patch rejected; revision accepted after 82 checks |
| 3 | Counts odd numbers instead of even | Supported, 2/2 | One-operator fix |
| 4 | Uses `min` instead of `max` | Supported, 2/2 | Wrong-builtin fix |
| 5 | Adds instead of multiplies | Supported, 2/2 | Arithmetic fix |
| 6 | Missing body, inclusive range check | Supported, 2/2 | Function written from the contract |
| 7 | Missing body, list transform | Supported, 2/2 | Function written from the contract |
| 8 | Exclusive instead of inclusive range | Supported, 1/1 | Boundary fix, three arguments |

Cases 1 and 2 show the main idea. The model's first answer was wrong, the test evidence exposed it, and the system accepted only the corrected patch.

## 4. Limitations

- **The Critic does not yet work.** In every run we inspected, the untrained Critic's reply was invalid, so the fixed fallback plan generated the challenge inputs. The challenge still caught every bad patch, but the Critic contributed nothing.
- **Narrow training data.** Fixer A was trained on 80 synthetic records. In every record the function body had been replaced by `return 0` or `return None`. The model therefore learned to *write a function from its contract* rather than to *repair existing logic*.
- **Multi-line logic bugs stay unresolved.** We also tested six harder cases: a loop off-by-one, a missed final run, a rotation wrap-around, sums that skip negatives, and others. All six ended *Unresolved*. The system behaved correctly by rejecting every incorrect patch, but the model did not produce a correct one.
- **Stage 2 comparator not promoted.** In Stage 2 we trained a learned Judge and a single "General" comparator agent. The Judge reached 92.9% valid decisions, 11 of 20 tasks solved and no wrong acceptances. The General agent stayed below our 90% validity gate and solved 0 of 20 tasks. We report it as not promoted rather than tuning it until it passes.

## 5. Next steps

1. Retrain Fixer A on realistic mutations (wrong operators, off-by-one errors, reordered statements) in place of placeholder bodies.
2. Re-run the harder cases above as a held-out benchmark.
3. Complete the Stage 2 comparison with a fair General baseline, or document its absence in the final report.
