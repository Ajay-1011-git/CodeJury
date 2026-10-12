# Frozen Stage 1 seam — `stage1.v1`

This exact section is copied into Ajay's and Sarvesh's guides. The canonical machine-readable file is `contracts/stage1-api.schema.json`. It must have SHA-256 `5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df`. Both developers read it; neither changes it. JSON Schema definitions win over informal examples for wire types. Business rules below supplement its structural validation. These are project-owned endpoints, not claims about a third-party API.

## Ownership and independence

Ajay owns `backend/**` (Python API, model worker, runner, controller, data, training, evaluation). Sarvesh owns `web/**` (UI, mock server, frontend tests, documentation/presentation). `contracts/**` and `reference/**` are immutable seed files committed before the branches diverge. Ajay owns root integration files only after merge. Neither developer edits the other's directory. No shared root package manager, lockfile, formatter config, or application state.

Backend: `http://127.0.0.1:8000`. Sarvesh mock: `http://127.0.0.1:8001`. Separate UI development server: `http://127.0.0.1:8080`. After merge, Ajay mounts the static `web/` directory and the UI defaults to same-origin. An optional query parameter `?api=http://127.0.0.1:8001` selects an explicit development backend; permit only localhost URLs. No cloud endpoint or account is required.

## HTTP mapping

| Method and path | Request | Success body | Status |
|---|---|---|---|
| `GET /health` | none | `Health` | 200 |
| `GET /examples` | none | `Examples` | 200 |
| `POST /runs` | `RunCreate` | `RunAccepted` | 202 |
| `GET /runs/{run_id}` | none | `RunSnapshot` | 200 |
| `GET /runs/{run_id}/events?after=N` | N defaults to 0, integer >=0 | `EventPage` | 200 |
| `GET /runs/{run_id}/candidates/{candidate_id}` | none | `Candidate` | 200 |
| `POST /runs/{run_id}/cancel` | empty body | current `RunSnapshot` | 200 |
| `GET /runs/{run_id}/report` | none | terminal `RunSnapshot` | 200 |
| `GET /stage1/training-report` | none | `TrainingReport` | 200 |

All success/error bodies use `schema_version: "stage1.v1"`. Unknown run/candidate => 404 `Error`; invalid structure/semantics => 422 `Error`; bad `after` => 422; busy model/run slot => 409 `Error`; report before terminal => 409; known unavailable model/sandbox before run starts => 503 `Error`. Runtime infrastructure loss after acceptance sets `infrastructure_error`. Replace FastAPI's default validation response with this exact error envelope. Clients must not assume a `detail` field. Backend and mock both emit `Content-Type: application/json` and no-cache API headers.

No WebSocket, SSE, authentication, uploads, or endpoint renaming in Stage 1. Poll the snapshot every 1,000ms and events with `after=next_after`; stop when terminal, on navigation, or cancellation. IDs are opaque. `next_after` is the maximum returned event ID, or the submitted `after` when there are no events. Events are ordered and a client deduplicates by ID. Their messages describe evidence; they are not hidden reasoning transcripts.

## Field rules

- Every field in a named schema object is required unless the schema explicitly says otherwise. Nullable fields are present with null. Reject unknown fields. Read all `$defs` from the packaged JSON Schema; do not create a renamed TypeScript contract or a second Pydantic schema with incompatible semantics.
- `RunCreate` supplies source, function name, explicit prose contract, 1–3 positional-argument domain descriptors, at least one literal test, one optional approved property ID, and fixed profile `stage1-demo`. No kwargs, imports, helper functions, decorators, global state, float values, custom classes, or runtime installation in this stage.
- Domains use `kind=integer` with null length fields or `kind=list_integer` with bounded integer length fields. `min<=max`; list lengths satisfy `0<=min_length<=max_length<=30`; integer bounds lie within -1,000..1,000. Arguments must match descriptor count and types. Reject booleans as integers. Expected values use JSON null/bool/int/string/list/string-keyed dict only, with bounded nesting and integer range suitable for JavaScript exact integers.
- Stage 1 properties are `sort_ascending_ints`, `unique_preserve_order_ints`, `sum_ints`, all for exactly one list-of-integers argument. The user explicitly chooses/approves the property with the requirement wording shown. These are disclosed supplied contract oracles, not hidden ground truth. A conflicting supplied expected output is invalid input.
- `sort_ascending_ints`: output is a list of integers, nondecreasing, with identical input/output multiplicities. `unique_preserve_order_ints`: output contains exactly first occurrences, in input order. `sum_ints`: output is an integer equal to the specified mathematical sum. Each property has a reviewed deterministic implementation outside candidate code. Output equality is recursive and type-sensitive; true does not equal 1. Candidate input mutation is forbidden.
- `TestCase.expected` is null for property/observation tests. A model's invented literal expectation is `proposed`; its outcome is `observed`, never authoritative pass/fail. A generated input that uses an approved property is `authoritative`, source `reviewed_contract`, provenance `critic` or `property_engine`. No model or UI event can promote an oracle at runtime.
- `Candidate.origin=original` records the unmodified input. It is never selected as a repair. `eligibility` is calculated from runner results. Source hashes are lowercase SHA-256 of UTF-8 source bytes; never hashes of normalized display strings. An untested candidate is pending, not eligible.
- Snapshot status is queued/running or one terminal outcome: supported_patch, unresolved, invalid_input, infrastructure_error, cancelled. Success has a non-null decision and selected eligible candidate; other terminal outcomes have a decision with null selection and a reason. Only queued/running may have null decision. `adapter_role=fixer_a` requires an actual loaded adapter hash; raw mode says none. Model absence is not represented as a fabricated identity.
- `runtime_mode=fixture` is mandatory for mock/replay content, with a persistent "Fixture demonstration — no live inference" banner. Live backend data is live. A UI may never turn fixture data into live by changing labels. Training status not_started/pilot_only/completed is factual; completed requires saved adapter plus measured evaluation. Zero results must remain zero, missing metrics null.
- A run returns actual tested evidence only. Runtime fields contain no reference implementation, hidden assessment tests, teacher targets, API key, filesystem path, or external credential. Reports contain only visible evidence and aggregate offline evaluation metrics.

## Canonical schema inventory

`RunCreate`, `RunAccepted`, `RunSnapshot`, `Candidate`, `TestCase`, `Execution`, `Decision`, `Usage`, `Event`, `EventPage`, `Error`, `Health`, `Example`, `Examples`, `TrainingReport`, `EvaluationRow`, `Domain`, `SuppliedTest`, `JsonValue` are the only named wire types. For request and response validation, select the corresponding `$defs` entry while retaining the full root definitions. Schema files never execute candidate code.

## Fixture policy

`contracts/fixtures/` contains synthetic API examples solely for independent UI/API development. They are not model results. `fixture-manifest.json` maps each fixture filename to its schema definition. Validate every listed file. A live request seed in `run-create.json` is real input; the seeded resulting patch and metrics are fixture examples. A real live run is allowed to fail or abstain; never force its answer to match the fixture.

The schema is frozen even if Stage 2 will need additional fields. Stage 2 uses a versioned amendment after inspecting real Stage 1 code. Do not invent Stage 2 event fields now.

## Canonical wire schema — verbatim reference

Read the shipped `contracts/stage1-api.schema.json` when implementing. This exact copy makes the document self-contained; do not regenerate or reformat the canonical file, because the seed checksum applies to its bytes. Select the named definition for each endpoint.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://codejury.local/contracts/stage1.v1",
  "$comment": "Local project identifier, not a hosted service. Validate an instance against a named $defs entry.",
  "title": "CodeJury Stage 1 HTTP contract",
  "type": "object",
  "$defs": {
    "JsonValue": {
      "anyOf": [
        {
          "type": "null"
        },
        {
          "type": "boolean"
        },
        {
          "type": "integer"
        },
        {
          "type": "string"
        },
        {
          "type": "array",
          "items": {
            "$ref": "#/$defs/JsonValue"
          }
        },
        {
          "type": "object",
          "additionalProperties": {
            "$ref": "#/$defs/JsonValue"
          }
        }
      ]
    },
    "Domain": {
      "type": "object",
      "properties": {
        "kind": {
          "enum": [
            "integer",
            "list_integer"
          ]
        },
        "min": {
          "type": "integer"
        },
        "max": {
          "type": "integer"
        },
        "min_length": {
          "anyOf": [
            {
              "type": "integer",
              "minimum": 0
            },
            {
              "type": "null"
            }
          ]
        },
        "max_length": {
          "anyOf": [
            {
              "type": "integer",
              "minimum": 0
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "kind",
        "min",
        "max",
        "min_length",
        "max_length"
      ],
      "additionalProperties": false
    },
    "SuppliedTest": {
      "type": "object",
      "properties": {
        "test_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "args": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/JsonValue"
          }
        },
        "expected": {
          "$ref": "#/$defs/JsonValue"
        }
      },
      "required": [
        "test_id",
        "args",
        "expected"
      ],
      "additionalProperties": false
    },
    "RunCreate": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage1.v1"
        },
        "source": {
          "type": "string",
          "minLength": 1,
          "maxLength": 24000
        },
        "function_name": {
          "type": "string",
          "pattern": "^[A-Za-z_][A-Za-z0-9_]*$"
        },
        "contract_text": {
          "type": "string",
          "minLength": 1,
          "maxLength": 8000
        },
        "input_domain": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Domain"
          },
          "minItems": 1,
          "maxItems": 3
        },
        "supplied_tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/SuppliedTest"
          },
          "minItems": 1,
          "maxItems": 30
        },
        "approved_property": {
          "anyOf": [
            {
              "enum": [
                "sort_ascending_ints",
                "unique_preserve_order_ints",
                "sum_ints"
              ]
            },
            {
              "type": "null"
            }
          ]
        },
        "resource_profile": {
          "const": "stage1-demo"
        }
      },
      "required": [
        "schema_version",
        "source",
        "function_name",
        "contract_text",
        "input_domain",
        "supplied_tests",
        "approved_property",
        "resource_profile"
      ],
      "additionalProperties": false
    },
    "RunAccepted": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage1.v1"
        },
        "run_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "status": {
          "enum": [
            "queued",
            "running",
            "supported_patch",
            "unresolved",
            "invalid_input",
            "infrastructure_error",
            "cancelled"
          ]
        },
        "runtime_mode": {
          "enum": [
            "live",
            "fixture"
          ]
        }
      },
      "required": [
        "schema_version",
        "run_id",
        "status",
        "runtime_mode"
      ],
      "additionalProperties": false
    },
    "Candidate": {
      "type": "object",
      "properties": {
        "candidate_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "parent_id": {
          "anyOf": [
            {
              "type": "string",
              "minLength": 1,
              "maxLength": 120
            },
            {
              "type": "null"
            }
          ]
        },
        "origin": {
          "enum": [
            "original",
            "fixer_a",
            "fixer_a_revision"
          ]
        },
        "source": {
          "type": "string"
        },
        "source_sha256": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "diagnosis": {
          "type": "string"
        },
        "diff": {
          "type": "string"
        },
        "eligibility": {
          "enum": [
            "pending",
            "eligible",
            "rejected"
          ]
        },
        "rejection_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "candidate_id",
        "parent_id",
        "origin",
        "source",
        "source_sha256",
        "diagnosis",
        "diff",
        "eligibility",
        "rejection_reason"
      ],
      "additionalProperties": false
    },
    "TestCase": {
      "type": "object",
      "properties": {
        "test_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "args": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/JsonValue"
          }
        },
        "oracle_kind": {
          "enum": [
            "literal",
            "property",
            "observation"
          ]
        },
        "expected": {
          "$ref": "#/$defs/JsonValue"
        },
        "property_id": {
          "anyOf": [
            {
              "enum": [
                "sort_ascending_ints",
                "unique_preserve_order_ints",
                "sum_ints"
              ]
            },
            {
              "type": "null"
            }
          ]
        },
        "oracle_status": {
          "enum": [
            "authoritative",
            "proposed",
            "observation_only",
            "rejected"
          ]
        },
        "oracle_source": {
          "enum": [
            "user",
            "reviewed_contract",
            "model"
          ]
        },
        "requirement_id": {
          "anyOf": [
            {
              "type": "string",
              "minLength": 1,
              "maxLength": 120
            },
            {
              "type": "null"
            }
          ]
        },
        "provenance": {
          "enum": [
            "supplied",
            "critic",
            "property_engine"
          ]
        },
        "reason": {
          "type": "string"
        }
      },
      "required": [
        "test_id",
        "args",
        "oracle_kind",
        "expected",
        "property_id",
        "oracle_status",
        "oracle_source",
        "requirement_id",
        "provenance",
        "reason"
      ],
      "additionalProperties": false
    },
    "Execution": {
      "type": "object",
      "properties": {
        "execution_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "candidate_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "test_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "outcome": {
          "enum": [
            "pass",
            "fail",
            "timeout",
            "error",
            "observed"
          ]
        },
        "actual_output": {
          "$ref": "#/$defs/JsonValue"
        },
        "exception_type": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "input_mutated": {
          "type": "boolean"
        },
        "duration_ms": {
          "type": "integer",
          "minimum": 0
        },
        "trace": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "trace_truncated": {
          "type": "boolean"
        }
      },
      "required": [
        "execution_id",
        "candidate_id",
        "test_id",
        "outcome",
        "actual_output",
        "exception_type",
        "input_mutated",
        "duration_ms",
        "trace",
        "trace_truncated"
      ],
      "additionalProperties": false
    },
    "Usage": {
      "type": "object",
      "properties": {
        "input_tokens": {
          "type": "integer",
          "minimum": 0
        },
        "output_tokens": {
          "type": "integer",
          "minimum": 0
        },
        "function_executions": {
          "type": "integer",
          "minimum": 0
        },
        "elapsed_ms": {
          "type": "integer",
          "minimum": 0
        },
        "peak_memory_mb": {
          "anyOf": [
            {
              "type": "number",
              "minimum": 0
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "input_tokens",
        "output_tokens",
        "function_executions",
        "elapsed_ms",
        "peak_memory_mb"
      ],
      "additionalProperties": false
    },
    "Decision": {
      "type": "object",
      "properties": {
        "selected_candidate_id": {
          "anyOf": [
            {
              "type": "string",
              "minLength": 1,
              "maxLength": 120
            },
            {
              "type": "null"
            }
          ]
        },
        "verification_scope": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "unresolved_requirements": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "evidence_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "reason": {
          "type": "string"
        }
      },
      "required": [
        "selected_candidate_id",
        "verification_scope",
        "unresolved_requirements",
        "evidence_ids",
        "reason"
      ],
      "additionalProperties": false
    },
    "RunSnapshot": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage1.v1"
        },
        "run_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "status": {
          "enum": [
            "queued",
            "running",
            "supported_patch",
            "unresolved",
            "invalid_input",
            "infrastructure_error",
            "cancelled"
          ]
        },
        "runtime_mode": {
          "enum": [
            "live",
            "fixture"
          ]
        },
        "phase": {
          "enum": [
            "queued",
            "reproduce",
            "generate",
            "supplied_tests",
            "challenge",
            "revise",
            "finalize",
            "finished"
          ]
        },
        "model_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "model_revision": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "adapter_role": {
          "enum": [
            "none",
            "fixer_a"
          ]
        },
        "adapter_sha256": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "original_failure_reproduced": {
          "anyOf": [
            {
              "type": "boolean"
            },
            {
              "type": "null"
            }
          ]
        },
        "candidates": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Candidate"
          }
        },
        "tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TestCase"
          }
        },
        "executions": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Execution"
          }
        },
        "decision": {
          "anyOf": [
            {
              "$ref": "#/$defs/Decision"
            },
            {
              "type": "null"
            }
          ]
        },
        "usage": {
          "$ref": "#/$defs/Usage"
        },
        "termination_reason": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "schema_version",
        "run_id",
        "status",
        "runtime_mode",
        "phase",
        "model_id",
        "model_revision",
        "adapter_role",
        "adapter_sha256",
        "original_failure_reproduced",
        "candidates",
        "tests",
        "executions",
        "decision",
        "usage",
        "termination_reason"
      ],
      "additionalProperties": false
    },
    "Event": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage1.v1"
        },
        "run_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "event_id": {
          "type": "integer",
          "minimum": 1
        },
        "type": {
          "enum": [
            "run_started",
            "original_checked",
            "candidate_created",
            "execution_completed",
            "test_admitted",
            "test_rejected",
            "revision_requested",
            "run_finished"
          ]
        },
        "timestamp_utc": {
          "type": "string"
        },
        "payload": {
          "type": "object",
          "properties": {
            "message": {
              "type": "string"
            },
            "candidate_id": {
              "anyOf": [
                {
                  "type": "string",
                  "minLength": 1,
                  "maxLength": 120
                },
                {
                  "type": "null"
                }
              ]
            },
            "test_id": {
              "anyOf": [
                {
                  "type": "string",
                  "minLength": 1,
                  "maxLength": 120
                },
                {
                  "type": "null"
                }
              ]
            },
            "evidence_ids": {
              "type": "array",
              "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 120
              }
            }
          },
          "required": [
            "message",
            "candidate_id",
            "test_id",
            "evidence_ids"
          ],
          "additionalProperties": false
        }
      },
      "required": [
        "schema_version",
        "run_id",
        "event_id",
        "type",
        "timestamp_utc",
        "payload"
      ],
      "additionalProperties": false
    },
    "EventPage": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage1.v1"
        },
        "run_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "events": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Event"
          }
        },
        "next_after": {
          "type": "integer",
          "minimum": 0
        }
      },
      "required": [
        "schema_version",
        "run_id",
        "events",
        "next_after"
      ],
      "additionalProperties": false
    },
    "Error": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage1.v1"
        },
        "error": {
          "type": "object",
          "properties": {
            "code": {
              "type": "string"
            },
            "message": {
              "type": "string"
            },
            "field_errors": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          },
          "required": [
            "code",
            "message",
            "field_errors"
          ],
          "additionalProperties": false
        }
      },
      "required": [
        "schema_version",
        "error"
      ],
      "additionalProperties": false
    },
    "Health": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage1.v1"
        },
        "service": {
          "const": "codejury-stage1"
        },
        "runtime_mode": {
          "enum": [
            "live",
            "fixture"
          ]
        },
        "model_ready": {
          "type": "boolean"
        },
        "sandbox_ready": {
          "type": "boolean"
        },
        "fixer_a_trained": {
          "type": "boolean"
        },
        "stage2_enabled": {
          "const": false
        }
      },
      "required": [
        "schema_version",
        "service",
        "runtime_mode",
        "model_ready",
        "sandbox_ready",
        "fixer_a_trained",
        "stage2_enabled"
      ],
      "additionalProperties": false
    },
    "Example": {
      "type": "object",
      "properties": {
        "example_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "title": {
          "type": "string"
        },
        "description": {
          "type": "string"
        },
        "request": {
          "$ref": "#/$defs/RunCreate"
        }
      },
      "required": [
        "example_id",
        "title",
        "description",
        "request"
      ],
      "additionalProperties": false
    },
    "Examples": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage1.v1"
        },
        "examples": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Example"
          }
        }
      },
      "required": [
        "schema_version",
        "examples"
      ],
      "additionalProperties": false
    },
    "EvaluationRow": {
      "type": "object",
      "properties": {
        "method": {
          "enum": [
            "raw_single",
            "trained_a_single",
            "stage1_loop"
          ]
        },
        "total": {
          "type": "integer",
          "minimum": 0
        },
        "solved": {
          "type": "integer",
          "minimum": 0
        },
        "unresolved": {
          "type": "integer",
          "minimum": 0
        },
        "incorrect_accepted": {
          "type": "integer",
          "minimum": 0
        },
        "mean_elapsed_ms": {
          "anyOf": [
            {
              "type": "integer",
              "minimum": 0
            },
            {
              "type": "null"
            }
          ]
        },
        "mean_output_tokens": {
          "anyOf": [
            {
              "type": "integer",
              "minimum": 0
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "method",
        "total",
        "solved",
        "unresolved",
        "incorrect_accepted",
        "mean_elapsed_ms",
        "mean_output_tokens"
      ],
      "additionalProperties": false
    },
    "TrainingReport": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage1.v1"
        },
        "runtime_mode": {
          "enum": [
            "live",
            "fixture"
          ]
        },
        "status": {
          "enum": [
            "not_started",
            "pilot_only",
            "completed"
          ]
        },
        "model_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "model_revision": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "adapter_sha256": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "train_base_problems": {
          "type": "integer",
          "minimum": 0
        },
        "validation_base_problems": {
          "type": "integer",
          "minimum": 0
        },
        "evaluation_base_problems": {
          "type": "integer",
          "minimum": 0
        },
        "train_records": {
          "type": "integer",
          "minimum": 0
        },
        "steps": {
          "type": "integer",
          "minimum": 0
        },
        "loss_points": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "step": {
                "type": "integer",
                "minimum": 0
              },
              "train_loss": {
                "anyOf": [
                  {
                    "type": "number"
                  },
                  {
                    "type": "null"
                  }
                ]
              },
              "validation_loss": {
                "anyOf": [
                  {
                    "type": "number"
                  },
                  {
                    "type": "null"
                  }
                ]
              }
            },
            "required": [
              "step",
              "train_loss",
              "validation_loss"
            ],
            "additionalProperties": false
          }
        },
        "evaluation": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/EvaluationRow"
          }
        },
        "provenance_note": {
          "type": "string"
        }
      },
      "required": [
        "schema_version",
        "runtime_mode",
        "status",
        "model_id",
        "model_revision",
        "adapter_sha256",
        "train_base_problems",
        "validation_base_problems",
        "evaluation_base_problems",
        "train_records",
        "steps",
        "loss_points",
        "evaluation",
        "provenance_note"
      ],
      "additionalProperties": false
    }
  }
}
```
