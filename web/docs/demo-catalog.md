# CodeJury Stage 1 — Demonstration Task Catalog

This catalog documents 8 benchmark demonstration tasks prepared by Sarvesh for frontend verification and professor presentation. Ajay ports verified tasks into backend training and evaluation datasets.

All tasks operate within the frozen Stage 1 boundary: pure Python functions with 1–3 integer or list-of-integer positional parameters, integer values within `[-1000, 1000]`, and list lengths $\le 30$.

---

### Task 1: Non-Decreasing Integer Sort with Duplicate Preservation
- **Function Name**: `sort_ints`
- **Input Domain**: `1` parameter: `list_integer`, bounds `[-1000, 1000]`, length `[0, 30]`.
- **Approved Property**: `sort_ascending_ints`
- **Intended Behaviour**: Return a new list containing the exact elements of the input list sorted in non-decreasing order ($x_i \le x_{i+1}$), with identical element multiplicities.
- **Easy Visible Failing Example**:
  ```python
  def sort_ints(items):
      # Bug: Reverses the list instead of sorting
      return list(reversed(items))
  ```
  *Failure*: Input `[3, 1, 2]` produces `[2, 1, 3]`, which violates non-decreasing monotonicity.
- **Edge-Case Explanation**: Lists containing duplicate values (e.g. `[5, 1, 5, 2]`) must preserve duplicate counts (`[1, 2, 5, 5]`) rather than deduplicating or dropping occurrences.

---

### Task 2: Unique Elements Preserving Original Appearance Order
- **Function Name**: `unique_preserve_order`
- **Input Domain**: `1` parameter: `list_integer`, bounds `[-500, 500]`, length `[0, 25]`.
- **Approved Property**: `unique_preserve_order_ints`
- **Intended Behaviour**: Filter out duplicate occurrences, retaining only the first appearance of each unique integer in its original relative sequence.
- **Easy Visible Failing Example**:
  ```python
  def unique_preserve_order(items):
      # Bug: Python set() hashes and scrambles original insertion order
      return list(set(items))
  ```
  *Failure*: Input `[3, 1, 3, 2, 1]` may yield `[1, 2, 3]` instead of the required `[3, 1, 2]`.
- **Edge-Case Explanation**: All-identical elements `[7, 7, 7, 7]` must collapse to single element `[7]`. Elements already distinct must remain strictly unchanged.

---

### Task 3: Integer Sequence Summation
- **Function Name**: `sum_ints`
- **Input Domain**: `1` parameter: `list_integer`, bounds `[-1000, 1000]`, length `[0, 30]`.
- **Approved Property**: `sum_ints`
- **Intended Behaviour**: Compute the exact mathematical sum of all integer elements in the list. Returns `0` if list is empty.
- **Easy Visible Failing Example**:
  ```python
  def sum_ints(items):
      # Bug: Off-by-one loop slice skips the first element
      total = 0
      for x in items[1:]:
          total += x
      return total
  ```
  *Failure*: Input `[10, 20, 30]` yields `50` instead of `60`.
- **Edge-Case Explanation**: Empty list `[]` yields `0`. Negative numbers must subtract correctly without sign inversion or float conversions.

---

### Task 4: Empty and Singleton List Robustness
- **Function Name**: `sort_ints`
- **Input Domain**: `1` parameter: `list_integer`, bounds `[-100, 100]`, length `[0, 5]`.
- **Approved Property**: `sort_ascending_ints`
- **Intended Behaviour**: Safely return identical lists for inputs of length 0 or 1 without index errors.
- **Easy Visible Failing Example**:
  ```python
  def sort_ints(items):
      # Bug: Unconditional index access crashes on empty list
      if items[0] is not None:
          return sorted(items)
  ```
  *Failure*: Input `[]` raises `IndexError: list index out of range`.
- **Edge-Case Explanation**: Verifies runner sandboxing catches unhandled exceptions and marks candidate execution outcome as `error` rather than false pass.

---

### Task 5: Extreme Boundary Integer Comparison
- **Function Name**: `sort_ints`
- **Input Domain**: `1` parameter: `list_integer`, bounds `[-1000, 1000]`, length `[2, 10]`.
- **Approved Property**: `sort_ascending_ints`
- **Intended Behaviour**: Correctly order extreme boundary values at the opposite limits of the contract domain.
- **Easy Visible Failing Example**:
  ```python
  def sort_ints(items):
      # Bug: Modulo-based bucket sort fails on negative extremes
      return sorted(items, key=lambda x: abs(x))
  ```
  *Failure*: Input `[-1000, 50, -200, 1000]` sorts by magnitude `[50, -200, -1000, 1000]`, which fails arithmetic ordering where `-1000 < -200 < 50 < 1000`.
- **Edge-Case Explanation**: Distinguishes mathematical integer order from absolute value order across zero crossings.

---

### Task 6: Multiset Duplicate Preservation Under In-Place Mutation Trap
- **Function Name**: `sort_ints`
- **Input Domain**: `1` parameter: `list_integer`, bounds `[-200, 200]`, length `[1, 20]`.
- **Approved Property**: `sort_ascending_ints`
- **Intended Behaviour**: Sort the list without mutating the caller's input argument in-place (`input_mutated: false`).
- **Easy Visible Failing Example**:
  ```python
  def sort_ints(items):
      # Bug: Mutates caller argument in-place
      items.sort()
      return items
  ```
  *Failure*: In-place mutation of the input list triggers runner sandbox violation (`input_mutated: true`), rejecting the candidate.
- **Edge-Case Explanation**: Demonstrates the contract runner's immutable argument verification trap.

---

### Task 7: Alternating Sign Net Zero Cancellation
- **Function Name**: `sum_ints`
- **Input Domain**: `1` parameter: `list_integer`, bounds `[-1000, 1000]`, length `[2, 20]`.
- **Approved Property**: `sum_ints`
- **Intended Behaviour**: Exact accumulation of opposite sign pairs summing to net zero.
- **Easy Visible Failing Example**:
  ```python
  def sum_ints(items):
      # Bug: Accumulates positive numbers only
      return sum(x for x in items if x > 0)
  ```
  *Failure*: Input `[-50, 50, -100, 100]` yields `150` instead of `0`.
- **Edge-Case Explanation**: Verifies oracles test negative integers and zero cancellation without heuristic rounding.

---

### Task 8: Unsupported Type & Contract Violation (Negative Test)
- **Function Name**: `compute_mean`
- **Input Domain**: Unsupported float domain descriptor.
- **Approved Property**: `None`
- **Intended Behaviour**: The Stage 1 seam strictly rejects non-integer domains, floating point numbers, and helper function imports before execution.
- **Easy Visible Failing Example**:
  ```python
  import numpy as np

  def compute_mean(items):
      return float(np.mean(items))
  ```
  *Failure*: AST validation rejects `import numpy`, and schema validator rejects non-integer / float return values.
- **Edge-Case Explanation**: Demonstrates boundary safety: client validator rejects the payload with `422 VALIDATION_FAILED` rather than executing untrusted third-party packages.
