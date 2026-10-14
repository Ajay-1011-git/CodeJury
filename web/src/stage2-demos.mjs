/** Stage 2 demonstration cases shown first in the example picker. Each was run live through the jury. */
export const DEMO_CASES = [
  {
    "example_id": "bubble-sort",
    "title": "Bubble sort stops one pass early",
    "description": "Debate demo: Fixer A patches the loop and crashes; Fixer B rebuilds from the contract; the Judge audits and calls the Critic on the sort property before selecting.",
    "request": {
      "schema_version": "stage2.v1",
      "source": "def sort_values(values):\n    result = list(values)\n    for i in range(len(result)):\n        for j in range(len(result) - i - 2):\n            if result[j] > result[j + 1]:\n                result[j], result[j + 1] = result[j + 1], result[j]\n    return result\n",
      "function_name": "sort_values",
      "contract_text": "Return a new list with the integers in ascending order, keeping every duplicate. Do not modify the input.",
      "domain_schema": [
        {
          "name": "values",
          "domain": {
            "kind": "list",
            "item_domain": {
              "kind": "integer",
              "min": -50,
              "max": 50
            },
            "min_length": 0,
            "max_length": 12
          }
        }
      ],
      "helper_interfaces": [],
      "requirements": [
        {
          "schema_version": "stage2.v1",
          "requirement_id": "sorted",
          "description": "Output is the input integers in ascending order, keeping every duplicate.",
          "source": "reviewed_contract",
          "approval_status": "approved",
          "property_template_id": "sort_ascending_ints",
          "parameters": {}
        }
      ],
      "supplied_tests": [
        {
          "schema_version": "stage2.v1",
          "test_id": "three",
          "inputs": [
            [
              3,
              1,
              2
            ]
          ],
          "expected": [
            1,
            2,
            3
          ],
          "requirement_ids": [
            "sorted"
          ]
        },
        {
          "schema_version": "stage2.v1",
          "test_id": "dupes",
          "inputs": [
            [
              5,
              -2,
              5,
              0
            ]
          ],
          "expected": [
            -2,
            0,
            5,
            5
          ],
          "requirement_ids": [
            "sorted"
          ]
        }
      ],
      "allowed_dependencies": [],
      "resource_profile": "mac-standard-v1",
      "policy_mode": "learned",
      "seed": 7
    }
  },
  {
    "example_id": "dedupe-last",
    "title": "Duplicate removal that keeps the last occurrence",
    "description": "Fixer A edits the buggy loop, Fixer B rewrites from the contract; the Critic checks the first-occurrence property.",
    "request": {
      "schema_version": "stage2.v1",
      "source": "def dedupe(values):\n    out = []\n    for value in reversed(values):\n        if value not in out:\n            out.insert(0, value)\n    return out\n",
      "function_name": "dedupe",
      "contract_text": "Return each integer once, keeping its first occurrence, in input order.",
      "domain_schema": [
        {
          "name": "values",
          "domain": {
            "kind": "list",
            "item_domain": {
              "kind": "integer",
              "min": -50,
              "max": 50
            },
            "min_length": 0,
            "max_length": 12
          }
        }
      ],
      "helper_interfaces": [],
      "requirements": [
        {
          "schema_version": "stage2.v1",
          "requirement_id": "first-order",
          "description": "Output keeps each integer once, in order of first occurrence.",
          "source": "reviewed_contract",
          "approval_status": "approved",
          "property_template_id": "unique_preserve_order_ints",
          "parameters": {}
        }
      ],
      "supplied_tests": [
        {
          "schema_version": "stage2.v1",
          "test_id": "repeat",
          "inputs": [
            [
              1,
              2,
              1,
              3
            ]
          ],
          "expected": [
            1,
            2,
            3
          ],
          "requirement_ids": [
            "first-order"
          ]
        }
      ],
      "allowed_dependencies": [],
      "resource_profile": "mac-standard-v1",
      "policy_mode": "learned",
      "seed": 7
    }
  },
  {
    "example_id": "sum-skip-first",
    "title": "Sum that skips the first element",
    "description": "Short case: one wrong slice. Shows the audit and the Critic's property exploration.",
    "request": {
      "schema_version": "stage2.v1",
      "source": "def total(values):\n    return sum(values[1:])\n",
      "function_name": "total",
      "contract_text": "Return the exact sum of all integers, including negative ones. An empty list returns 0.",
      "domain_schema": [
        {
          "name": "values",
          "domain": {
            "kind": "list",
            "item_domain": {
              "kind": "integer",
              "min": -50,
              "max": 50
            },
            "min_length": 0,
            "max_length": 12
          }
        }
      ],
      "helper_interfaces": [],
      "requirements": [
        {
          "schema_version": "stage2.v1",
          "requirement_id": "sum",
          "description": "Output is the exact integer sum, negatives included.",
          "source": "reviewed_contract",
          "approval_status": "approved",
          "property_template_id": "sum_ints",
          "parameters": {}
        }
      ],
      "supplied_tests": [
        {
          "schema_version": "stage2.v1",
          "test_id": "pair",
          "inputs": [
            [
              2,
              3
            ]
          ],
          "expected": 5,
          "requirement_ids": [
            "sum"
          ]
        }
      ],
      "allowed_dependencies": [],
      "resource_profile": "mac-standard-v1",
      "policy_mode": "learned",
      "seed": 7
    }
  },
  {
    "example_id": "isqrt-halves",
    "title": "Integer square root that halves instead",
    "description": "Refusal demo: the Judge orders revisions and AST searches, then abstains because no candidate qualifies.",
    "request": {
      "schema_version": "stage2.v1",
      "source": "def floor_sqrt(n):\n    return n // 2\n",
      "function_name": "floor_sqrt",
      "contract_text": "Return the largest integer r with r * r <= n, for 0 <= n <= 1000000. You may use math.isqrt.",
      "domain_schema": [
        {
          "name": "n",
          "domain": {
            "kind": "integer",
            "min": 0,
            "max": 1000000
          }
        }
      ],
      "helper_interfaces": [],
      "requirements": [
        {
          "schema_version": "stage2.v1",
          "requirement_id": "floor-root",
          "description": "Return the floor of the square root of n.",
          "source": "reviewed_contract",
          "approval_status": "approved",
          "property_template_id": null,
          "parameters": {}
        }
      ],
      "supplied_tests": [
        {
          "schema_version": "stage2.v1",
          "test_id": "sixteen",
          "inputs": [
            16
          ],
          "expected": 4,
          "requirement_ids": [
            "floor-root"
          ]
        },
        {
          "schema_version": "stage2.v1",
          "test_id": "fifteen",
          "inputs": [
            15
          ],
          "expected": 3,
          "requirement_ids": [
            "floor-root"
          ]
        },
        {
          "schema_version": "stage2.v1",
          "test_id": "zero",
          "inputs": [
            0
          ],
          "expected": 0,
          "requirement_ids": [
            "floor-root"
          ]
        },
        {
          "schema_version": "stage2.v1",
          "test_id": "big",
          "inputs": [
            999999
          ],
          "expected": 999,
          "requirement_ids": [
            "floor-root"
          ]
        }
      ],
      "allowed_dependencies": [
        "math.isqrt"
      ],
      "resource_profile": "mac-standard-v1",
      "policy_mode": "learned",
      "seed": 7
    }
  }
];
