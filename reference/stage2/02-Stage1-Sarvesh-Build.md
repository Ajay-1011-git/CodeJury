# Stage 1 — Sarvesh's Complete Build Instructions

**Module:** Local UI, fixture-backed development API, frontend verification, and professor demonstration presentation.  
**Partner:** Ajay owns `backend/**`, the model, sandbox, data validation, training and evaluation. You do not need his code, a Mac GPU, or an adapter to finish your assigned module.  
**Grounding:** `reference/CodeJury-Final-Architecture.md` v2.0; the frozen `stage1.v1` seam below.

Your jobs are deliberately easier: build a clean evidence UI, exercise synthetic fixture states, prepare demo descriptions, and render genuine training/evaluation metrics supplied by Ajay. You do not implement or pretend to train agents. After merging, the same UI switches from fixture API to the real backend through its base URL.

## A. Operating contract — use as your agent's standing instructions

Implement only your assigned Stage 1 tasks. Preserve the final architecture as the Stage 2 destination. If an architecture conflict appears, report it and propose a focused amendment; do not silently redesign. The stage boundary deliberately defers components and does not claim their implementation.

1. Inspect the repository and actual dependencies before coding. Verify third-party APIs against current official documentation and installed signatures/`--help`. Project-owned commands in VERIFY sections are interfaces you must implement, not pre-existing library commands. If third-party details cannot be verified, continue independent tasks and identify the blocked API rather than invent it.
2. Read `contracts/stage1-api.schema.json`; use its exact types, enums, and required nullable fields. Never rename endpoints or add wire fields to make your implementation convenient.
3. Edit only task-listed paths inside your owned directory. Do not edit your partner's files, root config, or frozen contracts. Do not add a second model serving stack, LangChain, AutoGen, LangGraph, cloud backend, or paid API dependency.
4. Validate every external boundary. Never execute submitted code on the host. Never expose teacher targets or assessment tests to runtime prompts or the UI.
5. Distinguish synthetic fixtures, replay, raw-model inference, trained inference, and measured results. Do not manufacture confidence percentages, training curves, test results, or four-agent completion claims.
6. Before each task, state a short plan and its permitted files. Continue routine multi-file work within the user's authorization without asking for repeated permission. Ask a precise question only for an unresolved decision that changes the contract or project scope.
7. Implement, run the specified checks, repair failures, record real evidence, then make a local commit `stage1(<owner>): <task-id> <summary>`. Do not push, publish, or send messages automatically merely because this document mentions a partner.
8. Define completion as: real VERIFY checks pass, source/type validation succeeds, contract hash unchanged, only permitted files changed, and handoff evidence recorded. Tests of core execution, oracle handling, and API shape are mandatory; do not substitute screenshots for them.

No deadline or calendar was provided. The build-order tables specify dependency checkpoints, not invented estimates. The project is not complete merely because the UI shows five completed milestones.

## B.1 Environment and layout

Use plain HTML/CSS/JavaScript modules, not a framework requiring a separate build pipeline. Backend serves the resulting static files after merge. Local development uses a Python static server and a Python standard-library mock API. A verified Python JSON Schema validator can check fixtures; node's built-in test runner can test pure JavaScript modules. Record actual Python and Node versions. No cloud, hosting, paid icon pack, GPU, MLX, React, or AI API is needed.

| Configuration | Value |
|---|---|
| UI development address | `http://127.0.0.1:8080` |
| Mock API address | `http://127.0.0.1:8001` |
| Real API address | `http://127.0.0.1:8000` |
| API selection | Same-origin default; explicit localhost-only `?api=...` override |
| Polling | 1,000ms; stop on terminal state/navigation |

Own only `web/index.html`, `web/styles.css`, `web/src/*.mjs`, `web/package.json`, `web/tests/**`, `web/tools/**`, `web/docs/**`, `web/assets/**`. Keep all frontend dependency/lock files inside `web/`. Read frozen `contracts/` fixtures without changing them. Store manual screenshots/demo notes under `web/docs/`; do not invent training results in them.

## B.2 Shared seam — immutable, identical to Ajay's guide

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

## C. Tasks

## S.01 · Static UI scaffold and fixture validation · P0 · depends: none

**PROMPT**

Goal: Start independently using immutable fixtures.

Files you may touch: web/index.html, web/styles.css, web/src/** skeletons, web/package.json, web/tools/validate_contract.py, web/tests/fixtures.test.mjs, web/docs/handoff.md

Read the entire schema and frozen seam. Build module script loading without global eval or script injection. Use local assets/system fonts. Keep placeholder views labelled placeholder, not completed functionality. `package.json` defines `test: node --test tests/*.test.mjs`; verify the actual Node version supports this. Implement Python fixture validation by selecting each manifest definition with the full root schema, checking checksum and recursive wire rules. Do not redefine partner API fields from memory.

Use responsive cards with useful information density: input, repair progress, candidate/code, execution matrix, final result, and training summary. App header must explicitly show "Stage 1 prototype" and role status: A trained/raw as supplied by backend, Critic prompted, controller fixed, B/Judge/auditor/search deferred. Never render four avatars suggesting four learned agents exist.

**VERIFY**

From repo root run `python web/tools/validate_contract.py --contracts contracts`, then from web run `npm test`. Launch `python -m http.server 8080 --directory web` and verify module loading without console errors. Save actual versions/output; fixture source remains unchanged.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## S.02 · Fixture-only mock API · P0 · depends: S.01

**PROMPT**

Goal: Emulate the seam so frontend work never waits for Ajay.

Files you may touch: web/tools/mock_api.py, web/tests/test_mock_api.py, web/docs/mock-api.md

Implement every endpoint exactly using a stdlib HTTP server and canonical JSON fixtures; verify stdlib server APIs in the installed Python docs. Use localhost CORS only for port8080; handle JSON headers and OPTIONS. Copy fixtures in memory; do not mutate originals. Each POST creates an opaque fixture run ID, has one simulated active slot, moves queued→running→terminal based on deterministic poll count, and rewrites references consistently. Clear slot on terminal/cancel. Mode always fixture. Unknown IDs 404, bad after 422, busy 409, unavailable test scenario 503, invalid POST 422 in exact Error envelope.

CLI scenarios select supported/unresolved/infrastructure_error; cancellation and invalid-input response paths must work. No submitted code is executed, no model is called, no loss/accuracy generated. `/stage1/training-report` returns the packaged not_started fixture unless a separate clearly fixture-labelled scenario is used. Real run timings/metrics are never simulated as measured. This mock stays under web/tools and is never mounted as the production backend.

**VERIFY**

Run `python -m unittest discover -s web/tests -p 'test_mock_api.py' -v` from root. Start `python web/tools/mock_api.py --port 8001 --scenario supported` (project CLI to implement), then validate GET health/examples and a POST→poll→events→candidate→report sequence against the schema using your checker. Required tests: cancel, cursor idempotence, repeated run IDs, non-JSON input, unknown IDs, every body fixture mode.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## S.03 · Typed seam client and run lifecycle · P0 · depends: S.02

**PROMPT**

Goal: Connect UI to either mock or backend without changing payloads.

Files you may touch: web/src/api.mjs, web/src/state.mjs, web/src/app.mjs, web/tests/api.test.mjs, web/tests/state.test.mjs

Implement an API client with the exact route methods, JSON content-type, schema version guard, typed error envelope handling, and network/503/409 notices. Read wire fields from the canonical definitions and fixtures; client-side runtime checks cover the consumed fields without inventing another incompatible contract. A GET report may return 409 while running; do not treat it as a finished report.

Maintain current run ID and generation token in UI state so responses from an old run cannot overwrite a new screen. Prevent duplicate submit; restore on failure. Poll snapshots and ordered events, deduplicate event IDs, and cancel timers/requests on terminal/navigation. Fetch health to display readiness, not to claim a model is trained because adapter_role happens to be set in a fixture. Fixture banner remains visible throughout. Include strict localhost-only api query parsing and same-origin deployment default.

**VERIFY**

Run `npm test` with fake fetch responses for every status, stale polls, duplicate events, wrong schema version, inaccessible backend, 503 and busy 409. Manually run against supported and unresolved mock scenarios; browser network log must use only the defined routes and stop polling on terminal state. Record actual results.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## S.04 · Source/contract input and explicit property approval · P0 · depends: S.03

**PROMPT**

Goal: Submit supported Python tasks with no guessed semantics.

Files you may touch: web/src/input.mjs, web/src/app.mjs, web/index.html, web/styles.css, web/tests/input.test.mjs

Build editable text areas for source and contract, function name, argument domains, and supplied literal tests using exact request schema. Examples are loaded from GET/examples, not hardcoded repaired outputs. Provide approved-property selector with None and the three names, showing full meaning and an explicit approval checkbox before serializing a non-null choice. Explain Stage1 argument/type restrictions and pure-function assumptions; no imports/helpers in this subset.

Validate parseable JSON, finite safe integers, list dimensions, input-domain bounds and test IDs before POST; backend remains authoritative. Preserve user text on errors. Render all code via textContent; never eval, execute, inject HTML, or upload to a third-party service. A malformed user string should appear as text, not become DOM markup.

**VERIFY**

Run `npm test` for valid example payload, missing consent, unknown property, boolean-as-integer, malformed tests JSON, repeated test IDs and escaped HTML input. Inspect POST body against RunCreate schema using the checker/mock. Prove source edits appear in request unchanged and no expected repaired code is included.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## S.05 · Evidence views, candidates and verdict · P0 · depends: S.04

**PROMPT**

Goal: Make real backend evidence understandable to the professor.

Files you may touch: web/src/evidence.mjs, web/src/result.mjs, web/src/app.mjs, web/styles.css, web/tests/evidence.test.mjs

Render original failure and candidate sources/diffs; distinguish pending/eligible/rejected based on fields, not inferred wording. Show one row per candidate and one column per test, keyed by immutable IDs. Display pass/fail/timeout/error/observed distinctly, and authoritative/proposed/observation_only oracle badges. No green pass badge for observed model predictions. Counterexample inspector shows input, expected (or property), actual output, source/status, and execution ID.

Final supported_patch displays selected candidate and verification_scope, unresolved_requirements and actual usage. Unresolved has no accepted patch/copy button. Cancelling/error cannot display stale success. Download visible report JSON and candidate source only from existing API data; no fabricated Markdown prose. Event timeline is factual action history; do not call it hidden chain-of-thought or trained Judge reasoning. Keep deferred Stage2 modules visibly deferred.

**VERIFY**

Run `npm test` including observed!=pass, null expected property tests, missing executions remain pending, wrong candidate not selected, stale-success clearing, copy/download on eligible selected candidate only. Browser inspection on fixture supported/cancelled/error/unresolved demonstrates all variants. Use keyboard navigation and width 375px plus desktop; no dangerous HTML rendering.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## S.06 · Training/results display and evidence contribution · P0 · depends: S.05

**PROMPT**

Goal: Present real learning work with lightweight UI tasks.

Files you may touch: web/src/training.mjs, web/tests/training.test.mjs, web/docs/demo-catalog.md, web/docs/data-review.md, web/styles.css

Consume GET/stage1/training-report. Render real base problem counts, record counts, steps, adapter hash, train/validation losses and evaluation solved/total per method. Plot with simple SVG/canvas or table; no chart package required. Empty metrics say not yet measured. Do not substitute display-friendly fake curves or claim loop superiority from unequal single-shot budgets. Missing memory remains unknown, not 0.

Training allocation: Sarvesh owns presentation and optional manual data review, not GPU jobs. Prepare 6–10 demo descriptions with intended behaviour, easy visible failing example, and edge-case explanation. Include order preservation, duplicate handling, empty/singleton input, boundary comparison, aggregation, and an unsupported/error case. Submit text in web/docs/demo-catalog.md; Ajay ports validated tasks into backend data. Review up to 20 training descriptions/expected examples for ambiguous wording, record reviewer notes and suspect cases; do not change split manifests or inspect sealed evaluation targets. No model training job is assigned to Sarvesh.

The UI completion state comes from backend reports. Synthetic fixtures have a badge even when illustrating completed-training layouts. A screenshot used in the professor handoff must identify live versus fixture clearly.

**VERIFY**

Run `npm test` on zero/empty report, real-shape nonempty loss/evaluation, null metrics and bad counters. Check solved<=total (malformed data yields an error state). Verify no metrics are hardcoded in UI. Save data-review notes with actual reviewed count and findings; unreviewed rows are not marked reviewed.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## S.07 · Browser acceptance, rehearsal and isolated handoff · P1 · depends: S.06

**PROMPT**

Goal: Deliver merge-ready UI with honest professor-facing output.

Files you may touch: web/tests/**, web/tools/frontend_smoke.py, web/docs/handoff.md, web/docs/professor-demo.md, web/assets/**

Create browser smoke instructions or optional automation after verifying actual browser-test tooling; do not assume a Playwright browser is installed. Cover submit, fixture banner, original fail, candidate pass, counterexample drilldown, cancelled/error path, source download and report. Keep screenshots optional/manual evidence, not fabricated assets. Include steps for replacing ?api=8001 with ?api=8000 and same-origin after merge.

Write a 3–5-minute rehearsal outline showing input→original failure→trained repair→test evidence→property challenge/revision if it actually occurs→measured training summary. State that Stage1 has a trained A, prompted Critic and fixed policy, with advanced roles/search/auditor deferred. Have a clearly labelled fixture fallback if backend is unavailable; fixture fallback does not satisfy the merged live acceptance.

Handoff includes commit ID, owned-file diff, schema hash, local commands, browser observations, fixture scenario tests, screenshots only where actually captured, known issues and data-review contribution. No checkpoint/training claims on partner's behalf.

**VERIFY**

Run `python web/tools/validate_contract.py --contracts contracts`, `npm test` from web, mock unittest suite, and manual/browser smoke checklist. Run `git diff --name-only <shared-base>...HEAD` with the actual common commit; every changed file must be under web. Record actual results. Your module is independently complete when this passes; the full Stage1 is complete only after Ajay's real backend and training acceptance.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## D. Build order

| Checkpoint | Tasks | Concrete output |
|---|---|---|
| Independent foundation | S.01–S.02 | Static shell and fixture API on any suitable laptop |
| Interaction | S.03–S.04 | Exact requests, polling, cancel, input approval |
| Evidence | S.05 | Candidate/test/verdict views for all states |
| Presentation | S.06–S.07 | Real-report renderer, demo/data notes, merge-ready handoff |

## E. Final acceptance — Sarvesh

Mark ✅ with evidence: frozen contract hash; all mock endpoints; no code execution; every fixture visibly fixture-labelled; request editor and explicit property consent; correct polling/cancel/error behaviour; safe source rendering; observed outcome never green pass; evidence matrix and selected source/report download; real-metric rendering without fabrication; mobile/keyboard checks; own-directory-only Git diff. GPU availability and Ajay's backend are not required for your isolated completion.
