# CodeJury Stage 2: Debate Demonstration

Stage 2 runs a jury instead of a single fixer:

- **Fixer A** repairs the buggy code it is shown.
- **Fixer B** writes an independent solution from the contract alone. It never sees the buggy body or Fixer A's code.
- **The Judge** chooses the next step from a fixed menu: revise, search, audit, call the Critic, select or abstain.
- **The Critic** tries to break the surviving patch with generated inputs.
- **The tools** run every check in an isolated sandbox. They also do small AST search edits and mutation audits.

Executed checks decide every outcome; no model can declare a patch correct.

## How to run it

1. Start the app with `./start.sh` and open the dashboard. It runs the Stage 2 jury.
2. In **Repair desk**, the example picker already shows **Bubble sort stops one pass early**. Click **Submit case**.
3. **Run evidence** opens by itself. Click each step in **Action history** to see what every role said and why.

## Main demo: "Bubble sort stops one pass early"

This case is built into the dashboard; you do not need to paste anything. It was run 3 times on 14 October 2026 (seed 7, learned policy), with the same outcome each time.

**Function name**

```text
sort_values
```

**Buggy source**

```python
def sort_values(values):
    result = list(values)
    for i in range(len(result)):
        for j in range(len(result) - i - 2):
            if result[j] > result[j + 1]:
                result[j], result[j + 1] = result[j + 1], result[j]
    return result
```

**Contract**

```text
Return a new list with the integers in ascending order, keeping every duplicate. Do not modify the input.
```

**Argument domain:** `values` is a list of 0–12 integers, each from -50 to 50.

**Requirement:** `sorted`, source `reviewed_contract`, status `approved`. Its executable template is `sort_ascending_ints`, so the Critic's generated inputs have authority to reject a patch.

**Supplied tests**

| Test | Input | Expected |
|---|---|---|
| three | `[[3, 1, 2]]` | `[1, 2, 3]` |
| dupes | `[[5, -2, 5, 0]]` | `[-2, 0, 5, 5]` |

**What happens, and what to click**

| # | Role | Step | What it shows |
|---|---|---|---|
| 1 | Controller | Bug reproduced | The original returns `[1, 3, 2]` for `[3, 1, 2]` |
| 2 | Fixer A | Proposes | It rewrites the loop and crashes with `IndexError` on both tests, so it is rejected |
| 3 | Fixer B | Proposes (independent view) | It rebuilds from the contract as `return sorted(values)` and passes both tests |
| 4 | Judge | Orders a mutation audit | The menu it chose from, and the scoreboard (A: 0 pass / 2 fail, B: 2 pass / 0 fail) |
| 5 | Tools | Mutation audit | Probe mutants of B's patch are run against the tests |
| 6 | Judge | Calls the Critic | It chose "challenge agreement" over "abstain" |
| 7 | Critic | Challenge | It explores the sort property on generated inputs and finds no counterexample |
| 8 | Judge | Selects a patch | Only after the required audit and challenge are done |
| 9 | Verdict | Supported patch · Fixer B | Accepted source, verification scope, and a download of the patch |

## Other cases in the picker

| Case | What it shows | Live result |
|---|---|---|
| Duplicate removal that keeps the last occurrence | Same debate pattern on the first-occurrence property | Supported, Fixer B |
| Sum that skips the first element | Shortest case: audit plus the Critic's property exploration | Supported, Fixer B |
| Integer square root that halves instead | **Refusal**: the Judge orders revisions and AST searches, then abstains because no candidate qualifies | Unresolved |
| Reviewed helper and math import (built in) | **Longest debate**: revisions, an AST search, an audit and two Critic challenges; the search edit wins | Supported both times, but the exact steps differed between runs |

## Honest limitations

- **Fixer A is weak.** It was trained only on placeholder `return 0` / `return None` bodies, so it rarely repairs real logic. In these demos Fixer B supplies the winning patch, or an AST search edit does.
- **The Critic rarely finds counterexamples here.** It ran correctly and with authority, but the patches it challenged were already correct. Only a counterexample is kept as a new test.
- **Runs can vary.** The models run with a fixed seed, but longer debates can still take different paths, as the gcd case did.
