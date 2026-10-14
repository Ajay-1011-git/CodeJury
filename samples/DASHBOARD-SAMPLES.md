# CodeJury: Demonstration Cases

Eight cases for the Repair desk. Each one was run on the live system on 14 October 2026 and produced an accepted patch (`SUPPORTED PATCH`).

## How to enter a case

1. Open the dashboard at http://127.0.0.1:8000 and go to **Repair desk**.
2. Paste **Function name** into the FUNCTION NAME box.
3. **Source code** tab: paste the buggy code.
4. **Contract** tab: paste the contract into *What should this function do?* and the input domain into *Input domain (JSON)*. Set *Optional property check* as listed. If it isn't *None*, tick the approval checkbox.
5. **Test cases** tab: paste the test cases JSON.
6. Click **Start Verification Run**, then open **Run evidence** to see the verdict, the patch proposals and the execution matrix.

Run time is about 20–45 seconds per case. Only one run can be active at a time.

---

## Case 1: Sorting function that forgets to sort

**Function name**

```text
sort_values
```

**Source code** (buggy)

```python
def sort_values(values):
    return values
```

**Contract**

```text
Return a new list with the integers in ascending order, keeping duplicates.
```

**Input domain (JSON)**

```json
[
  {"kind": "list_integer", "min": -1000, "max": 1000, "min_length": 0, "max_length": 30}
]
```

**Optional property check:** Sort integers, preserving duplicates  
**Approval checkbox:** tick it

**Test cases (JSON)**

```json
[
  {"test_id": "unsorted", "args": [[3, -1, 2]], "expected": [-1, 2, 3]},
  {"test_id": "dupes", "args": [[5, 0, 5, -4]], "expected": [-4, 0, 5, 5]}
]
```

**Expected outcome:** Best demo of the argument. Fixer A's first patch is rejected when the test engine finds the counterexample `[0, -1]`; its revised patch `return sorted(values)` is then accepted after 82 checks. Open **Run evidence → Action history** and click each step to follow the exchange.

**Reference fix** (for your own checking; do not paste it)

```python
def sort_values(values):
    return sorted(values)
```

---

## Case 2: Duplicate removal that loses the order

**Function name**

```text
dedupe
```

**Source code** (buggy)

```python
def dedupe(values):
    return list(set(values))
```

**Contract**

```text
Return the first occurrence of each integer, in the order the integers first appear.
```

**Input domain (JSON)**

```json
[
  {"kind": "list_integer", "min": -1000, "max": 1000, "min_length": 0, "max_length": 30}
]
```

**Optional property check:** Unique integers in first-occurrence order  
**Approval checkbox:** tick it

**Test cases (JSON)**

```json
[
  {"test_id": "order", "args": [[9, 1, 9, -3, 1]], "expected": [9, 1, -3]}
]
```

**Expected outcome:** Second argument demo. The first patch (`return values`) is rejected; the revision is accepted after 82 checks.

**Reference fix** (for your own checking; do not paste it)

```python
def dedupe(values):
    return list(dict.fromkeys(values))
```

---

## Case 3: Even counter that counts odd numbers

**Function name**

```text
count_even
```

**Source code** (buggy)

```python
def count_even(values):
    return len([v for v in values if v % 2 == 1])
```

**Contract**

```text
Count the integers divisible by two, including zero and negatives.
```

**Input domain (JSON)**

```json
[
  {"kind": "list_integer", "min": -1000, "max": 1000, "min_length": 0, "max_length": 30}
]
```

**Optional property check:** None — use my supplied tests

**Test cases (JSON)**

```json
[
  {"test_id": "mixed", "args": [[1, 2, 3, 4]], "expected": 2},
  {"test_id": "neg-and-zero", "args": [[-4, 0, -3]], "expected": 2},
  {"test_id": "empty", "args": [[]], "expected": 0}
]
```

**Expected outcome:** Fixed on the first attempt: `== 1` becomes `== 0`. The zero and negative tests confirm the parity check.

**Reference fix** (for your own checking; do not paste it)

```python
def count_even(values):
    return len([v for v in values if v % 2 == 0])
```

---

## Case 4: Maximum finder that returns the minimum

**Function name**

```text
largest
```

**Source code** (buggy)

```python
def largest(values):
    return min(values)
```

**Contract**

```text
Return the largest integer in the non-empty list.
```

**Input domain (JSON)**

```json
[
  {"kind": "list_integer", "min": -1000, "max": 1000, "min_length": 1, "max_length": 30}
]
```

**Optional property check:** None — use my supplied tests

**Test cases (JSON)**

```json
[
  {"test_id": "mixed", "args": [[4, -2, 9, 1]], "expected": 9},
  {"test_id": "negatives", "args": [[-7, -3, -5]], "expected": -3},
  {"test_id": "single", "args": [[6]], "expected": 6}
]
```

**Expected outcome:** Fixed on the first attempt: `min` becomes `max`.

**Reference fix** (for your own checking; do not paste it)

```python
def largest(values):
    return max(values)
```

---

## Case 5: Rectangle area that adds instead of multiplies

**Function name**

```text
area
```

**Source code** (buggy)

```python
def area(width, height):
    return width + height
```

**Contract**

```text
Return the area of a rectangle: width multiplied by height.
```

**Input domain (JSON)**

```json
[
  {"kind": "integer", "min": 0, "max": 100, "min_length": null, "max_length": null},
  {"kind": "integer", "min": 0, "max": 100, "min_length": null, "max_length": null}
]
```

**Optional property check:** None — use my supplied tests

**Test cases (JSON)**

```json
[
  {"test_id": "basic", "args": [3, 4], "expected": 12},
  {"test_id": "zero", "args": [0, 7], "expected": 0},
  {"test_id": "square", "args": [5, 5], "expected": 25}
]
```

**Expected outcome:** Fixed on the first attempt: `+` becomes `*`.

**Reference fix** (for your own checking; do not paste it)

```python
def area(width, height):
    return width * height
```

---

## Case 6: Range check with a missing body

**Function name**

```text
in_range
```

**Source code** (buggy)

```python
def in_range(x, lo, hi):
    return None
```

**Contract**

```text
Return True if lo <= x <= hi (both ends inclusive), otherwise False.
```

**Input domain (JSON)**

```json
[
  {"kind": "integer", "min": -100, "max": 100, "min_length": null, "max_length": null},
  {"kind": "integer", "min": -100, "max": 100, "min_length": null, "max_length": null},
  {"kind": "integer", "min": -100, "max": 100, "min_length": null, "max_length": null}
]
```

**Optional property check:** None — use my supplied tests

**Test cases (JSON)**

```json
[
  {"test_id": "inside", "args": [5, 1, 9], "expected": true},
  {"test_id": "low-edge", "args": [1, 1, 9], "expected": true},
  {"test_id": "high-edge", "args": [9, 1, 9], "expected": true},
  {"test_id": "outside", "args": [10, 1, 9], "expected": false}
]
```

**Expected outcome:** The body is empty (`return None`); the Fixer writes it from the contract. The edge tests check both ends are inclusive.

**Reference fix** (for your own checking; do not paste it)

```python
def in_range(x, lo, hi):
    return lo <= x <= hi
```

---

## Case 7: List doubler with a missing body

**Function name**

```text
double_each
```

**Source code** (buggy)

```python
def double_each(values):
    return 0
```

**Contract**

```text
Return a new list with every integer multiplied by two, in the same order.
```

**Input domain (JSON)**

```json
[
  {"kind": "list_integer", "min": -500, "max": 500, "min_length": 0, "max_length": 30}
]
```

**Optional property check:** None — use my supplied tests

**Test cases (JSON)**

```json
[
  {"test_id": "basic", "args": [[1, -2, 3]], "expected": [2, -4, 6]},
  {"test_id": "empty", "args": [[]], "expected": []}
]
```

**Expected outcome:** The body is empty (`return 0`); the Fixer writes a list comprehension from the contract.

**Reference fix** (for your own checking; do not paste it)

```python
def double_each(values):
    return [v * 2 for v in values]
```

---

## Case 8: Range counter that excludes its endpoints

**Function name**

```text
count_in_range
```

**Source code** (buggy)

```python
def count_in_range(values, lo, hi):
    count = 0
    for value in values:
        if lo < value < hi:
            count += 1
    return count
```

**Contract**

```text
Count the integers v with lo <= v <= hi (both ends inclusive). If lo is greater than hi, return zero.
```

**Input domain (JSON)**

```json
[
  {"kind": "list_integer", "min": -100, "max": 100, "min_length": 0, "max_length": 30},
  {"kind": "integer", "min": -100, "max": 100, "min_length": null, "max_length": null},
  {"kind": "integer", "min": -100, "max": 100, "min_length": null, "max_length": null}
]
```

**Optional property check:** None — use my supplied tests

**Test cases (JSON)**

```json
[
  {"test_id": "inclusive", "args": [[1, 2, 3, 4, 5], 2, 4], "expected": 3},
  {"test_id": "low-edge", "args": [[2, 2, 9], 2, 5], "expected": 2},
  {"test_id": "high-edge", "args": [[5, 6], 0, 5], "expected": 1},
  {"test_id": "inverted", "args": [[1, 2, 3], 3, 1], "expected": 0}
]
```

**Expected outcome:** A boundary bug with three arguments: `lo < v < hi` becomes `lo <= v <= hi`.

**Reference fix** (for your own checking; do not paste it)

```python
def count_in_range(values, lo, hi):
    count = 0
    for value in values:
        if lo <= value <= hi:
            count += 1
    return count
```

---
