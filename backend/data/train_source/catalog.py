"""Original synthetic specifications. Reference source runs only inside the sandbox.

Families are assigned before corruption. Expected examples are independently authored.
This offline catalog is never imported by the runtime or exposed through the API.
"""

LIST = {"kind": "list_integer", "min": -10, "max": 10, "min_length": 0, "max_length": 10}
INT = {"kind": "integer", "min": -1000, "max": 1000, "min_length": None, "max_length": None}
SMALL = {**INT, "min": 0, "max": 30}
POSITIVE = {**INT, "min": 1, "max": 30}


def catalog():
    rows = []

    def add(family, split, name, contract, params, domains, body, cases):
        rows.append(
            {
                "base_problem_id": name,
                "family_id": family,
                "split": split,
                "contract": contract,
                "parameters": params,
                "domain": domains,
                "correct_source": "def solve("
                + ", ".join(params)
                + "):\n"
                + "".join("    " + line + "\n" for line in body.splitlines()),
                "cases": cases,
            }
        )

    def sequence(family, name, contract, body, cases, split="train"):
        add(family, split, name, contract, ["values"], [LIST], body, cases)

    def scalar(family, name, contract, body, cases, params=None, domains=None, split="train"):
        params = params or ["x"]
        add(family, split, name, contract, params, domains or [INT] * len(params), body, cases)

    sequence(
        "reductions",
        "total",
        "Return the mathematical sum of the integers.",
        "return sum(values)",
        [([[]], 0), ([[2, -1, 4]], 5), ([[0]], 0), ([[-3, -2]], -5)],
    )
    sequence(
        "reductions",
        "square_total",
        "Return the sum of squares of all integers.",
        "return sum(x*x for x in values)",
        [([[]], 0), ([[2, -3]], 13), ([[0]], 0), ([[1, 1]], 2)],
    )
    sequence(
        "reductions",
        "alternating_total",
        "Add values at even indices and subtract values at odd indices, starting index zero.",
        "return sum(x if i%2 == 0 else -x for i,x in enumerate(values))",
        [([[]], 0), ([[3, 1, 2]], 4), ([[4]], 4), ([[1, 2, 3, 4]], -2)],
    )
    sequence(
        "reductions",
        "nonzero_count",
        "Count integers unequal to zero.",
        "return sum(1 for x in values if x != 0)",
        [([[]], 0), ([[0, 2, 0, -1]], 2), ([[0]], 0), ([[1, 2]], 2)],
    )
    sequence(
        "reductions",
        "range_width",
        "Return maximum minus minimum, or zero for an empty list.",
        "return max(values)-min(values) if values else 0",
        [([[]], 0), ([[2, -3, 4]], 7), ([[5]], 0), ([[-2, -1]], 1)],
    )
    scalar(
        "boundaries",
        "clamp",
        "Return min(max(x, lo), hi), including when lo exceeds hi.",
        "return min(max(x,lo),hi)",
        [([5, 0, 3], 3), ([-2, 0, 3], 0), ([1, 0, 3], 1), ([1, 5, 2], 2)],
        ["x", "lo", "hi"],
    )
    scalar(
        "boundaries",
        "sign",
        "Return minus one for negative, zero for zero, and one for positive input.",
        "return -1 if x < 0 else (1 if x > 0 else 0)",
        [([-3], -1), ([4], 1), ([0], 0), ([1000], 1)],
    )
    scalar(
        "boundaries",
        "absolute_distance",
        "Return the absolute difference of x and y.",
        "return abs(x-y)",
        [([2, 5], 3), ([5, 2], 3), ([1, 1], 0), ([-3, 2], 5)],
        ["x", "y"],
    )
    scalar(
        "boundaries",
        "closer_to_zero",
        "Return the argument with smaller absolute value; choose x on ties.",
        "return x if abs(x) <= abs(y) else y",
        [([-2, 3], -2), ([5, -1], -1), ([-2, 2], -2), ([0, 1], 0)],
        ["x", "y"],
    )
    scalar(
        "boundaries",
        "strict_threshold",
        ("Return integer one exactly when x is strictly greater than threshold, otherwise zero."),
        "return 1 if x > threshold else 0",
        [([3, 2], 1), ([2, 2], 0), ([1, 2], 0), ([-1, -2], 1)],
        ["x", "threshold"],
    )
    sequence(
        "filters",
        "positive_values",
        "Keep strictly positive integers in original order, retaining duplicates.",
        "return [x for x in values if x > 0]",
        [([[0, 2, -1, 2]], [2, 2]), ([[]], []), ([[-2]], []), ([[1]], [1])],
    )
    sequence(
        "filters",
        "even_values",
        "Keep integers divisible by two in original order, retaining duplicates.",
        "return [x for x in values if x%2 == 0]",
        [([[2, 1, -2, 2]], [2, -2, 2]), ([[]], []), ([[3]], []), ([[0]], [0])],
    )
    add(
        "filters",
        "train",
        "above_threshold",
        "Keep integers strictly greater than threshold in input order.",
        ["values", "threshold"],
        [LIST, INT],
        "return [x for x in values if x > threshold]",
        [([[2, 1, 3], 1], [2, 3]), ([[], 0], []), ([[1], 1], []), ([[-1, 0], -2], [-1, 0])],
    )
    sequence(
        "filters",
        "without_zero",
        "Remove all zero integers, preserving order and duplicates.",
        "return [x for x in values if x != 0]",
        [([[0, 1, 0, -2]], [1, -2]), ([[]], []), ([[0]], []), ([[2, 2]], [2, 2])],
    )
    sequence(
        "filters",
        "negative_positions",
        "Return zero-based indices of strictly negative integers.",
        "return [i for i,x in enumerate(values) if x < 0]",
        [([[1, -1, 0, -2]], [1, 3]), ([[]], []), ([[-1]], [0]), ([[0]], [])],
    )
    sequence(
        "prefix",
        "prefix_sums",
        "Return one cumulative sum per input item, in order.",
        (
            "result=[]\ncurrent=0\nfor x in values:\n    current += x\n    result."
            "append(current)\nreturn result"
        ),
        [([[2, -1, 3]], [2, 1, 4]), ([[]], []), ([[0]], [0]), ([[-1, -2]], [-1, -3])],
    )
    sequence(
        "prefix",
        "running_max",
        "Return the maximum of each nonempty input prefix.",
        (
            "result=[]\nfor x in values:\n    result.append(max(x,result[-1]) if"
            " result else x)\nreturn result"
        ),
        [([[2, 1, 3]], [2, 2, 3]), ([[]], []), ([[-2, -3]], [-2, -2]), ([[1]], [1])],
    )
    sequence(
        "prefix",
        "prefix_positive_counts",
        "Return cumulative counts of strictly positive items.",
        (
            "result=[]\ncount=0\nfor x in values:\n    count += 1 if x > 0 else 0"
            "\n    result.append(count)\nreturn result"
        ),
        [([[1, 0, 2]], [1, 1, 2]), ([[]], []), ([[-1]], [0]), ([[1, 1]], [1, 2])],
    )
    sequence(
        "prefix",
        "adjacent_differences",
        "Return each item minus its immediately preceding item, omitting the first item.",
        "return [values[i]-values[i-1] for i in range(1,len(values))]",
        [([[2, 5, 1]], [3, -4]), ([[]], []), ([[1]], []), ([[2, 2]], [0])],
    )
    sequence(
        "prefix",
        "prefix_alternating",
        ("Return alternating cumulative sums, adding even indices and subtracting odd indices."),
        (
            "result=[]\ncurrent=0\nfor i,x in enumerate(values):\n    current += "
            "x if i%2 == 0 else -x\n    result.append(current)\nreturn result"
        ),
        [([[3, 1, 2]], [3, 2, 4]), ([[]], []), ([[2]], [2]), ([[1, 2]], [1, -1])],
    )
    scalar(
        "arithmetic",
        "floor_quotient",
        "Return floor division x by y for nonnegative x and positive y.",
        "return x//y",
        [([7, 3], 2), ([0, 2], 0), ([6, 3], 2), ([1, 2], 0)],
        ["x", "y"],
        [SMALL, POSITIVE],
    )
    scalar(
        "arithmetic",
        "remainder",
        "Return the nonnegative remainder x modulo positive y.",
        "return x%y",
        [([7, 3], 1), ([0, 2], 0), ([6, 3], 0), ([1, 2], 1)],
        ["x", "y"],
        [SMALL, POSITIVE],
    )
    scalar(
        "arithmetic",
        "manhattan_distance",
        "Return abs(x) plus abs(y).",
        "return abs(x)+abs(y)",
        [([-2, 3], 5), ([0, 0], 0), ([1, -1], 2), ([-3, -4], 7)],
        ["x", "y"],
    )
    scalar(
        "arithmetic",
        "ceil_quotient",
        "Return the ceiling of x divided by positive y for nonnegative x.",
        "return (x+y-1)//y",
        [([7, 3], 3), ([0, 2], 0), ([6, 3], 2), ([1, 2], 1)],
        ["x", "y"],
        [SMALL, POSITIVE],
    )
    scalar(
        "arithmetic",
        "interval_distance",
        "Return max(lo-x, x-hi, 0). This expression defines behavior even if lo exceeds hi.",
        "return max(lo-x,x-hi,0)",
        [([5, 0, 3], 2), ([-2, 0, 3], 2), ([1, 0, 3], 0), ([1, 5, 2], 4)],
        ["x", "lo", "hi"],
    )
    add(
        "search",
        "train",
        "first_index",
        "Return the first matching index, or minus one if absent.",
        ["values", "target"],
        [LIST, INT],
        "for i,x in enumerate(values):\n    if x == target:\n        return i\nreturn -1",
        [([[2, 1, 2], 2], 0), ([[], 1], -1), ([[1, 2], 2], 1), ([[1], 3], -1)],
    )
    add(
        "search",
        "train",
        "last_index",
        "Return the last matching index, or minus one if absent.",
        ["values", "target"],
        [LIST, INT],
        (
            "result=-1\nfor i,x in enumerate(values):\n    if x == target:\n     "
            "   result=i\nreturn result"
        ),
        [([[2, 1, 2], 2], 2), ([[], 1], -1), ([[1, 2], 1], 0), ([[1], 3], -1)],
    )
    add(
        "search",
        "train",
        "contains",
        "Return a boolean indicating whether target occurs in values.",
        ["values", "target"],
        [LIST, INT],
        "return target in values",
        [([[1, 2], 2], True), ([[], 1], False), ([[1], 3], False), ([[2, 2], 2], True)],
    )
    add(
        "search",
        "train",
        "occurrence_count",
        "Return the number of occurrences of target.",
        ["values", "target"],
        [LIST, INT],
        "return sum(1 for x in values if x == target)",
        [([[2, 1, 2], 2], 2), ([[], 1], 0), ([[1], 3], 0), ([[2], 2], 1)],
    )
    sequence(
        "search",
        "first_positive_index",
        "Return the index of the first strictly positive item, or minus one.",
        "for i,x in enumerate(values):\n    if x > 0:\n        return i\nreturn -1",
        [([[-1, 0, 2]], 2), ([[]], -1), ([[1]], 0), ([[-1]], -1)],
    )
    sequence(
        "comparison",
        "strictly_increasing",
        (
            "Return true iff every adjacent pair is strictly increasing; empty"
            " and singleton are true."
        ),
        "return all(values[i-1] < values[i] for i in range(1,len(values)))",
        [([[1, 2, 2]], False), ([[1, 2, 3]], True), ([[]], True), ([[1]], True)],
    )
    sequence(
        "comparison",
        "nondecreasing",
        "Return true iff every adjacent pair is nondecreasing; empty and singleton are true.",
        "return all(values[i-1] <= values[i] for i in range(1,len(values)))",
        [([[1, 2, 2]], True), ([[2, 1]], False), ([[]], True), ([[1]], True)],
    )
    sequence(
        "comparison",
        "palindrome_sequence",
        "Return true iff the list equals its reverse.",
        "return values == values[::-1]",
        [([[1, 2, 1]], True), ([[1, 2]], False), ([[]], True), ([[1]], True)],
    )
    sequence(
        "comparison",
        "all_equal",
        "Return true iff all items are equal; empty and singleton are true.",
        "return not values or all(x == values[0] for x in values)",
        [([[2, 2]], True), ([[1, 2]], False), ([[]], True), ([[1]], True)],
    )
    sequence(
        "comparison",
        "one_positive",
        "Return true iff exactly one integer is strictly positive.",
        "return sum(1 for x in values if x > 0) == 1",
        [([[0, 2, -1]], True), ([[1, 2]], False), ([[]], False), ([[1]], True)],
    )
    sequence(
        "transform",
        "reverse_sequence",
        "Return a new list with input order reversed, retaining duplicates.",
        "return values[::-1]",
        [([[1, 2, 1]], [1, 2, 1]), ([[1, 2, 3]], [3, 2, 1]), ([[]], []), ([[1]], [1])],
    )
    sequence(
        "transform",
        "increment_each",
        "Add one to each integer in input order.",
        "return [x+1 for x in values]",
        [([[0, -1, 2]], [1, 0, 3]), ([[]], []), ([[1]], [2]), ([[-2]], [-1])],
    )
    sequence(
        "transform",
        "negate_each",
        "Negate each integer in input order.",
        "return [-x for x in values]",
        [([[1, -2, 0]], [-1, 2, 0]), ([[]], []), ([[1]], [-1]), ([[-2]], [2])],
    )
    sequence(
        "transform",
        "absolute_each",
        "Replace each integer by its absolute value, preserving order.",
        "return [abs(x) for x in values]",
        [([[1, -2, 0]], [1, 2, 0]), ([[]], []), ([[-1]], [1]), ([[2]], [2])],
    )
    sequence(
        "transform",
        "remove_endpoints",
        "Remove the first and last list items; return empty for length less than two.",
        "return values[1:-1]",
        [([[1, 2, 3, 4]], [2, 3]), ([[]], []), ([[1]], []), ([[1, 2]], [])],
    )
    scalar(
        "number_theory",
        "gcd",
        "Return greatest common divisor of positive x and y.",
        "while y:\n    x,y=y,x%y\nreturn x",
        [([12, 18], 6), ([7, 3], 1), ([1, 1], 1), ([30, 15], 15)],
        ["x", "y"],
        [POSITIVE, POSITIVE],
        "validation",
    )
    scalar(
        "number_theory",
        "lcm",
        "Return least common multiple of positive x and y.",
        "a,b=x,y\nwhile b:\n    a,b=b,a%b\nreturn x*y//a",
        [([4, 6], 12), ([3, 7], 21), ([1, 1], 1), ([5, 10], 10)],
        ["x", "y"],
        [POSITIVE, POSITIVE],
        "validation",
    )
    scalar(
        "number_theory",
        "prime",
        "Return true iff x is prime; zero and one are not prime.",
        (
            "if x < 2:\n    return False\nfor d in range(2,x):\n    if x%d == 0:\n"
            "        return False\nreturn True"
        ),
        [([7], True), ([9], False), ([0], False), ([2], True)],
        ["x"],
        [SMALL],
        "validation",
    )
    scalar(
        "number_theory",
        "divisor_count",
        "Count positive divisors of positive x.",
        "return sum(1 for d in range(1,x+1) if x%d == 0)",
        [([6], 4), ([7], 2), ([1], 1), ([12], 6)],
        ["x"],
        [POSITIVE],
        "validation",
    )
    scalar(
        "number_theory",
        "largest_proper_divisor",
        "Return largest positive divisor strictly less than x, or zero for x=1.",
        "result=0\nfor d in range(1,x):\n    if x%d == 0:\n        result=d\nreturn result",
        [([6], 3), ([7], 1), ([1], 0), ([12], 6)],
        ["x"],
        [POSITIVE],
        "validation",
    )
    sequence(
        "runs",
        "run_lengths",
        "Return lengths of maximal consecutive equal-value runs.",
        (
            "result=[]\nfor i,x in enumerate(values):\n    if i == 0 or x != val"
            "ues[i-1]:\n        result.append(1)\n    else:\n        result[-1] +"
            "= 1\nreturn result"
        ),
        [([[1, 1, 2, 1]], [2, 1, 1]), ([[]], []), ([[1]], [1]), ([[2, 2, 2]], [3])],
        "validation",
    )
    sequence(
        "runs",
        "equal_adjacent_count",
        "Count adjacent pairs with equal integers.",
        "return sum(1 for i in range(1,len(values)) if values[i] == values[i-1])",
        [([[1, 1, 2, 2, 2]], 3), ([[]], 0), ([[1]], 0), ([[1, 2]], 0)],
        "validation",
    )
    sequence(
        "runs",
        "longest_equal_run",
        "Return the longest consecutive equal-value run length, or zero for empty input.",
        (
            "best=0\ncurrent=0\nfor i,x in enumerate(values):\n    current=curren"
            "t+1 if i > 0 and x == values[i-1] else 1\n    best=max(best,curren"
            "t)\nreturn best"
        ),
        [([[1, 1, 2, 2, 2]], 3), ([[]], 0), ([[1]], 1), ([[1, 2]], 1)],
        "validation",
    )
    sequence(
        "runs",
        "compress_runs",
        "Keep exactly one integer per consecutive equal-value run, preserving run order.",
        "return [x for i,x in enumerate(values) if i == 0 or x != values[i-1]]",
        [([[1, 1, 2, 1]], [1, 2, 1]), ([[]], []), ([[1]], [1]), ([[2, 2]], [2])],
        "validation",
    )
    sequence(
        "runs",
        "run_count",
        "Count maximal consecutive equal-value runs; empty input has zero runs.",
        "return sum(1 for i,x in enumerate(values) if i == 0 or x != values[i-1])",
        [([[1, 1, 2, 1]], 3), ([[]], 0), ([[1]], 1), ([[2, 2]], 1)],
        "validation",
    )
    add(
        "order_statistics",
        "assessment",
        "kth_sorted",
        "Return item k of ascending sorted values, or null when k is outside the list.",
        ["values", "k"],
        [LIST, SMALL],
        "return sorted(values)[k] if k < len(values) else None",
        [([[3, 1, 2], 1], 2), ([[], 0], None), ([[2, 2, 1], 1], 2), ([[1], 2], None)],
    )
    sequence(
        "order_statistics",
        "lower_median",
        "Return lower median of sorted input, or null for empty input.",
        "return sorted(values)[(len(values)-1)//2] if values else None",
        [([[3, 1, 2, 4]], 2), ([[]], None), ([[1]], 1), ([[3, 1, 2]], 2)],
        "assessment",
    )
    sequence(
        "order_statistics",
        "second_distinct_smallest",
        ("Return second distinct smallest integer, or null with fewer than two distinct values."),
        "ordered=sorted(set(values))\nreturn ordered[1] if len(ordered)>1 else None",
        [([[3, 1, 1, 2]], 2), ([[]], None), ([[1, 1]], None), ([[-1, 2]], 2)],
        "assessment",
    )
    sequence(
        "order_statistics",
        "inversion_count",
        "Count index pairs i<j with values[i] strictly greater than values[j].",
        (
            "return sum(1 for i in range(len(values)) for j in range(i+1,len(v"
            "alues)) if values[i]>values[j])"
        ),
        [([[3, 1, 2]], 2), ([[]], 0), ([[2, 2]], 0), ([[3, 2, 1]], 3)],
        "assessment",
    )
    sequence(
        "order_statistics",
        "top_two",
        (
            "Return the largest two values in descending order, retaining dupl"
            "icates; shorter inputs return all values."
        ),
        "return sorted(values,reverse=True)[:2]",
        [([[1, 3, 3, 2]], [3, 3]), ([[]], []), ([[1]], [1]), ([[-1, -2, -3]], [-1, -2])],
        "assessment",
    )
    scalar(
        "digits",
        "digit_sum",
        "Return sum of decimal digits of absolute x.",
        "return sum(int(c) for c in str(abs(x)))",
        [([-123], 6), ([0], 0), ([1000], 1), ([99], 18)],
        split="assessment",
    )
    scalar(
        "digits",
        "reverse_digits",
        ("Reverse decimal digits of absolute x, discard leading zeros, and restore original sign."),
        "value=int(str(abs(x))[::-1])\nreturn -value if x<0 else value",
        [([-120], -21), ([0], 0), ([123], 321), ([1000], 1)],
        split="assessment",
    )
    scalar(
        "digits",
        "digit_count",
        "Count decimal digits of absolute x; zero has one digit.",
        "return len(str(abs(x)))",
        [([-123], 3), ([0], 1), ([1000], 4), ([9], 1)],
        split="assessment",
    )
    scalar(
        "digits",
        "palindrome_digits",
        "Return whether decimal digits of absolute x form a palindrome, ignoring sign.",
        "digits=str(abs(x))\nreturn digits == digits[::-1]",
        [([-121], True), ([120], False), ([0], True), ([11], True)],
        split="assessment",
    )
    scalar(
        "digits",
        "count_digit",
        (
            "Count occurrences of digit d in decimal representation of absolut"
            "e x; zero is represented by one zero."
        ),
        "return sum(1 for c in str(abs(x)) if int(c) == d)",
        [([-100, 0], 2), ([0, 0], 1), ([121, 1], 2), ([99, 1], 0)],
        ["x", "d"],
        [INT, {**INT, "min": 0, "max": 9}],
        "assessment",
    )
    scalar(
        "bitwise",
        "bit_count",
        "Count set bits of nonnegative x.",
        "count=0\nwhile x:\n    count += x&1\n    x >>= 1\nreturn count",
        [([7], 3), ([0], 0), ([8], 1), ([15], 4)],
        ["x"],
        [SMALL],
        "stage2_final",
    )
    scalar(
        "bitwise",
        "bit_parity",
        "Return zero for an even number of set bits and one for odd.",
        "parity=0\nwhile x:\n    parity ^= x&1\n    x >>= 1\nreturn parity",
        [([7], 1), ([0], 0), ([8], 1), ([15], 0)],
        ["x"],
        [SMALL],
        "stage2_final",
    )
    scalar(
        "bitwise",
        "highest_bit",
        "Return the largest power of two no greater than x, or zero for zero.",
        (
            "result=0\nwhile x:\n    result=1 if result == 0 else result*2\n    x"
            " >>= 1\nreturn result"
        ),
        [([7], 4), ([0], 0), ([8], 8), ([15], 8)],
        ["x"],
        [SMALL],
        "stage2_final",
    )
    scalar(
        "bitwise",
        "power_of_two",
        "Return true exactly when positive x is a power of two.",
        "return x > 0 and x&(x-1) == 0",
        [([8], True), ([0], False), ([7], False), ([1], True)],
        ["x"],
        [SMALL],
        "stage2_final",
    )
    scalar(
        "bitwise",
        "xor_through",
        "Return bitwise XOR of integers zero through x inclusive.",
        "result=0\nfor value in range(x+1):\n    result ^= value\nreturn result",
        [([3], 0), ([0], 0), ([4], 4), ([5], 1)],
        ["x"],
        [SMALL],
        "stage2_final",
    )
    small = {**SMALL, "max": 10}
    scalar(
        "combinatorics",
        "factorial",
        "Return factorial of nonnegative x with zero factorial one.",
        "result=1\nfor value in range(1,x+1):\n    result *= value\nreturn result",
        [([4], 24), ([0], 1), ([1], 1), ([5], 120)],
        ["x"],
        [small],
        "stage2_final",
    )
    scalar(
        "combinatorics",
        "binomial",
        "Return number of ways to choose k items from x; return zero when k>x.",
        (
            "if k>x:\n    return 0\nresult=1\nfor i in range(1,k+1):\n    result=r"
            "esult*(x-i+1)//i\nreturn result"
        ),
        [([5, 2], 10), ([0, 0], 1), ([2, 3], 0), ([4, 1], 4)],
        ["x", "k"],
        [small, small],
        "stage2_final",
    )
    scalar(
        "combinatorics",
        "fibonacci",
        "Return Fibonacci number F(x), with F(0)=0 and F(1)=1.",
        "a,b=0,1\nfor i in range(x):\n    a,b=b,a+b\nreturn a",
        [([6], 8), ([0], 0), ([1], 1), ([8], 21)],
        ["x"],
        [small],
        "stage2_final",
    )
    scalar(
        "combinatorics",
        "triangular",
        "Return number of unordered distinct pairs from x items.",
        "return x*(x-1)//2",
        [([4], 6), ([0], 0), ([1], 0), ([5], 10)],
        ["x"],
        [small],
        "stage2_final",
    )
    scalar(
        "combinatorics",
        "catalan",
        "Return Catalan number C(x), with C(0)=1.",
        "result=1\nfor i in range(x):\n    result=result*2*(2*i+1)//(i+2)\nreturn result",
        [([3], 5), ([0], 1), ([1], 1), ([4], 14)],
        ["x"],
        [small],
        "stage2_final",
    )
    return rows
