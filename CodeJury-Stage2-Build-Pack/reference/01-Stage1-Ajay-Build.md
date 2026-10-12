# Stage 1 — Ajay's Complete Build Instructions

**Module:** Local repair backend, sandbox, Fixer A training, and first measured repair loop.  
**Partner:** Sarvesh implements `web/**` against the frozen HTTP contract. His code is not required for your API, CLI, training, or runner verification.  
**Grounding:** `reference/CodeJury-Final-Architecture.md` v2.0. Architecture wins on ultimate design; this document defines the approved Stage 1 subset.

Your deliverable must produce real local repairs and evidence before UI merge. Stage 1 uses one trained Fixer A, an unadapted/prompted Critic, and a fixed controller. It does not claim four trained agents. Fixer B, trained Critic/Judge, AST repair search, and mutation auditor remain Stage 2.

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

## B.1 Environment and module layout

Initial runtime: Apple Silicon Mac, native Python 3.11, MLX-LM, FastAPI/Pydantic, SQLite, Hypothesis; ARM64 Python 3.11 container through Colima. Use the installed runtime's verified versions, record them, and lock only inside `backend/`. Never copy speculative package version pins from an AI answer. If Python 3.11 does not satisfy the inspected MLX release, record the compatibility conflict before changing the project runtime.

| Configuration | Initial value / behaviour |
|---|---|
| `CODEJURY_MODEL_DIR` | Absolute local downloaded model path; required for live model mode |
| `CODEJURY_ADAPTER_DIR` | Local Fixer A adapter directory; null/unset means raw mode, never silently trained |
| `CODEJURY_RUNS_DIR` | Local ignored artefact directory under backend; default `backend/artifacts/runs` |
| `CODEJURY_TRAINING_DIR` | Local ignored training artefacts, separate from runtime data |
| `CODEJURY_RUNNER_IMAGE` | Verified locally built `codejury-runner:stage1`, record immutable image digest |
| `CODEJURY_ALLOWED_ORIGINS` | Default localhost:8080 only in dev; same-origin after merge |
| `CODEJURY_ALLOW_RAW` | Explicit dev override; professor Stage 1 acceptance requires trained A |
| `CODEJURY_PROFILE` | Only `stage1-demo` in this stage |

No API key is required. Model teacher generation is offline and optional; verified original solutions plus controlled bugs provide the zero-API route. Do not keep a 7B teacher and student resident together on 16GB.

Target ownership layout: `backend/pyproject.toml`, `backend/.gitignore`, `backend/config/`, `backend/src/codejury/{api,contracts,controller,models,runner,storage,properties,training,evaluation}`, `backend/tests/`, `backend/tools/`, `backend/data/{public_examples,train_source,manifests}`, `backend/docs/{handoff,dependency-audit}`. Large models/checkpoints, runtime database, hidden data, and generated logs are ignored/local. Package discovery must support `python -m codejury.*` after editable installation.

## B.2 Shared seam — immutable, identical to Sarvesh's guide

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

## A.01 · Audit dependencies and scaffold backend · P0 · depends: none

**PROMPT**

Goal: Establish a reproducible native-Mac backend without inventing runtime APIs.

Files you may touch: backend/pyproject.toml, backend/.gitignore, backend/src/codejury/** skeletons, backend/config/**, backend/tools/check_environment.py, backend/tests/test_environment.py, backend/docs/**

Inspect Mac architecture/memory, Python, MLX-LM and MLX compatibility, actual Phi checkpoint model type, model license/revision, FastAPI/Pydantic installed majors, Colima/Docker CLI help, and ARM64 runner compatibility. Read official sources listed in the architecture and save accessed URLs, package versions, exact inspected flags, and unresolved facts in `backend/docs/dependency-audit.md`. Do not assume the generic LoRA model-family list proves Phi-4-mini training support. Verify native inference and a tiny train/save/reload pilot later in A.06. Qwen 3B is the documented contingency; an actual model switch must be recorded and used for all comparisons. No CUDA, vLLM, or Linux MLX acceleration requirement.

Create the package, backend-only dependency file/lock, ignored local artefact paths, and a `codejury.contracts` validator loading the canonical JSON Schema by path derived from the repo root. Use verified `jsonschema` Draft 2020-12 support or exact compatible Pydantic models with response validation against the packaged schema. Preserve validation envelope types. Inspect schemas without executing source. Implement the project-owned commands named in later VERIFY blocks as their tasks land.

**VERIFY**

From repo root, create/select Python 3.11 venv, install the editable `backend` package using its dependency manifest. From `backend/`, run `python tools/check_environment.py`, `python -m pytest tests/test_environment.py -q`, and `python -m codejury.contracts.check ../contracts`. The final checker validates every fixture against its named definition plus the schema checksum. Save real output; unavailable model/runner may be reported as pending at this task only.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## A.02 · Intake, approved oracles, and immutable records · P0 · depends: A.01

**PROMPT**

Goal: Implement the hard acceptance rules before a model proposes code.

Files you may touch: backend/src/codejury/contracts/**, backend/src/codejury/properties/**, backend/src/codejury/storage/**, backend/src/codejury/api/types.py, backend/tests/test_intake.py, backend/tests/test_oracles.py, backend/tests/test_storage.py

Limit Stage 1 to one top-level undecorated FunctionDef with 1–3 positional parameters, no imports/helpers/classes/global executable statements, and the shared value/domain subset. Parse but never import submitted source on the host. Bound nested JSON, source length, name validity, supplied test IDs and input ranges. Store exact source SHA-256 and authoritative supplied tests. Reproduce failures later through the runner; syntax rejection is not execution.

Implement the three reviewed property templates from the seam. Explicit user approval selects their contract semantics; inference cannot add new authoritative properties. A proposed literal expectation can produce an observation but never reject a patch. Reject inconsistent supplied expectations for approved template tasks using trusted deterministic property evaluators, not the candidate. No hidden tests enter runtime storage.

Use append-only event records and immutable candidate blobs. Events increment per run, outputs preserve recursive type-sensitive equality, and task state survives server restart. Add separate local paths for training/evaluation records so runtime modules cannot read them by default.

**VERIFY**

Run `python -m pytest tests/test_intake.py tests/test_oracles.py tests/test_storage.py -q`. Required cases: boolean rejected as integer; out-of-domain list; duplicate test ID; import attempt rejected; oracle conflict; proposed expected value never hard-fails a candidate; true != 1; old candidate unchanged after revision; event order/replay after restart. `python -m codejury.contracts.check ../contracts` must still pass.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## A.03 · Isolated execution and cancellation · P0 · depends: A.02

**PROMPT**

Goal: Execute functions safely with real returned values and watchdogs.

Files you may touch: backend/src/codejury/runner/**, backend/tools/runner/**, backend/tests/test_runner*.py, backend/config/runner*, backend/docs/dependency-audit.md

Verify current Docker/Colima flags before implementing. Configure a dedicated Colima VM with host personal-directory shares disabled; inspect effective mounts. Build an ARM64 runner image pinned to the verified Python patch version or image digest; include only required libraries. Never mount home, model directories, Git credentials, repo source, or Docker socket into candidate jobs. Use network-none, non-root UID, read-only root, bounded tmpfs, dropped capabilities, no-new-privileges, memory/process limits, and a host-controlled watchdog that kills the whole job/container on timeout or cancellation.

Deliver source and input to an ephemeral sandbox using fixed argv and private files/stdin, never shell interpolation. Compile/import candidate code only there. Return raw observed JSON output, exception class, input mutation state, bounded trace, and timings. A trusted controller checks expected values/properties; do not trust candidate-generated pass labels. Classify container/infrastructure errors separately from semantic failures. Fresh state per function invocation; do not allow one test to mutate the next test's inputs. Bound stdout/trace and mark truncation. Test the watchdog against a forked process where supported; AST rejection is not the sandbox.

**VERIFY**

Run `python -m codejury.runner.cli self-test --profile stage1-demo` and `python -m pytest tests/test_runner*.py -q` (use shell glob expansion only for known local test paths). Include real success, assertion mismatch, loop timeout, input mutation, oversized output, missing image, cancellation, network denial, forbidden mount inspection. Save image digest, sandbox inspection output with credentials omitted, and timings. No host fallback is acceptable.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## A.04 · Asynchronous API and durable lifecycle · P0 · depends: A.03

**PROMPT**

Goal: Expose the frozen contract independently of Sarvesh.

Files you may touch: backend/src/codejury/api/**, backend/src/codejury/controller/** scaffold, backend/tests/test_api*.py, backend/tools/api_smoke.py

Verify installed FastAPI and Pydantic validation hooks and static mounting APIs before coding; the wire schema stays fixed regardless of versions. Implement every endpoint in the seam, including 202 acceptance and 404/409/422/503 envelopes. Keep model work outside the request handler in one dedicated native worker process. Only one queued/running repair may occupy the run slot; a second submission returns typed busy 409. Atomic scheduling prevents simultaneous races. Persist accepted state before dispatch. Restart marks abandoned running work infrastructure_error; no duplicate generation.

Use a test-only fake model/runner dependency to exercise lifecycle shape, clearly segregated from live application mode. A live backend cannot report fixture inference as live. Add cancellation propagation and event polling. Public examples come from backend-owned files, never hidden data. Before UI merge, `/` can return local API information; serve no copied partner UI.

**VERIFY**

Run `python -m pytest tests/test_api*.py -q`. Required: all endpoint envelopes validate against schema; 2 concurrent POST requests accept at most one; event cursor semantics; invalid request envelope; report 409 before completion; cancellation idempotence; restart recovery. Start `python -m uvicorn codejury.api.app:app --host 127.0.0.1 --port 8000`, then `python tools/api_smoke.py --base-url http://127.0.0.1:8000 --contract ../contracts/stage1-api.schema.json`. Test-mode smoke is labelled test mode and is not professor live evidence.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## A.05 · Leakage-safe corpus and Fixer A examples · P0 · depends: A.03

**PROMPT**

Goal: Create validated local training data and sealed assessment splits.

Files you may touch: backend/src/codejury/training/data*.py, backend/src/codejury/training/cli.py, backend/data/train_source/**, backend/data/manifests/**, backend/tests/test_training_data.py, backend/docs/data-card.md

Collection target: 120 distinct base functions (80 train /20 validation /20 internal Stage 1 assessment); minimum defensible Stage 1 prototype: 60 (40/10/10). These are targets to collect, not existing datasets. Report actual counts. Keep professor demo examples separate from scored assessment, and disclose any training overlap. Sarvesh may contribute descriptions or manually labelled edge cases, but you own technical validation and all split manifests.

Create/review correct small functions across conditions, loop updates, aggregation, sequence handling, and boundaries. Each needs a contract, domain, correct source, visible tests, reference-backed training assessment tests, and licensing/provenance. Validate references in the sandbox. Split original functions and algorithm-family/near-duplicate clusters before deriving corruptions. Generate multiple controlled buggy variants within their base split; retain only syntactically supported variants failing at least one relevant test. Add actual student errors after A.06; do not fabricate them initially. Aim for 2–4 verified training variants per base problem (minimum 80 examples if 40 train bases), but repeated traces are not additional independent problems.

Required dataset record fields: base_problem_id, family_id, split, provenance, contract, domain, buggy_source, correct_source, visible_tests, assessment_tests, failure_evidence, response_target. Construct chat records with A's runtime input view and a short diagnosis plus correct replacement source in the same structured format runtime expects. No reference source or assessment test is inside the prompt. Completion targets include code/diagnosis only. Verify actual MLX-LM chat JSONL format and prompt masking support in the installed version; no guessed keys.

Do not train on QuixBugs or external benchmark tasks selected for Stage 2 evaluation. Seal manifests; A's failure-mining data for Stage 2 B comes from training-only problems, not Stage 1 assessment. Preserve a separate final Stage 2 sealed pool, since Stage 1 assessment becomes development evidence.

**VERIFY**

Implement and run `python -m codejury.training.cli validate-data --manifest data/manifests/stage1.json`, `python -m codejury.training.cli export-sft --manifest data/manifests/stage1.json --out artifacts/training/fixer_a_sft`, and `python -m pytest tests/test_training_data.py -q`. Checker must prove base/family split disjointness, target/prompt separation, no reference leaks, source validity, correct-reference pass and buggy-input fail. Save actual rejection counts and data-card counts; never silently relabel failed validation as valid data.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## A.06 · Real Fixer A training and model worker · P0 · depends: A.01, A.05

**PROMPT**

Goal: Produce a trained adapter that reloads and generates executable repairs.

Files you may touch: backend/src/codejury/models/**, backend/src/codejury/training/**, backend/config/training/**, backend/tests/test_model_views.py, backend/tests/test_model_adapter.py, backend/docs/training-card.md

Download the exact chosen MLX model conversion/revision outside Git and record upstream revision, conversion/hash, tokenizer and license. Inspect real load/generate APIs and CLI help. Run native raw inference, then a tiny 10–20-step train/save/reload pilot on training-only data before launching the full job. If Phi configuration fails, use the architecture's Qwen 3B contingency through a documented whole-experiment change; do not invent support or hide a model switch.

Start quantized-base LoRA, microbatch 1, rank 8, short sequences, verified attention projection targets, limited adapted layers and gradient accumulation/checkpointing only if actual runtime supports them. Train sequentially with VM stopped if unnecessary. Use assistant-completion prompt masking supported by installed format. Initial full-run exploration is 300–800 steps with validation checkpoints; this is a trial range, not a guaranteed convergence requirement. Select on validation executable repair success plus malformed-output rate, not training loss alone. Freeze the checkpoint and evaluate after training. Never optimize on sealed assessment. Log real loss, memory, elapsed time, seeds, data/config hashes and actual command invoked.

Model worker uses adapter A for repair and raw base + Critic prompt for challenge; it must completely remove/restore LoRA state between roles or sequentially reload a clean model. Fresh KV cache per role. Verify A→raw→A with deterministic settings and parameter hashes. Generated repair format is controller-local JSON with source, diagnosis, assumptions; validate and bound it; one format-repair attempt is allowed and charged. The model must not execute tools directly. API raw mode requires explicit override and says adapter_role none; acceptance requires actual trained A metadata. No invented confidence values.

**VERIFY**

Run `python -m codejury.training.cli pilot --config config/training/fixer_a.yaml`, then `python -m codejury.training.cli train --config config/training/fixer_a.yaml`, and `python -m codejury.models.cli smoke --config config/model.yaml`. The launcher must build argv from inspected current MLX flags and record it, not assume these project CLI flags are upstream commands. Run `python -m pytest tests/test_model_views.py tests/test_model_adapter.py -q`; model view tests are CPU-only, adapter smoke is real Mac-only. Save adapter/checkpoint hashes, >0 actual training steps, real loss file, reload output, switch test output and one generated candidate; label failed generation as failed.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## A.07 · Property-based challenge and bounded repair loop · P0 · depends: A.02, A.04, A.06

**PROMPT**

Goal: Deliver a real initial repair, challenge, one revision, and evidence-based selection.

Files you may touch: backend/src/codejury/controller/**, backend/src/codejury/properties/**, backend/src/codejury/models/prompts/**, backend/tests/test_loop.py, backend/tests/test_property_engine.py, backend/config/stage1-demo.yaml

Stage 1 protocol: reproduce failing supplied test; generate A once; run all supplied tests; ask raw/prompted Critic once for an input-family proposal referencing an already approved property or observation-only hypothesis; property engine explores at most 100 valid inputs and shrinks a failing case; if verified failure or supplied failure exists, request one A revision carrying exact counterexample; rerun every authoritative test and approved-property check; select eligible candidate or return unresolved. No B, trained Critic, learned Judge, AST repair search, or audit mutation in this stage.

Implement strict Critic internal proposal format `property_id`, `family` (general/empty/singleton/duplicates/descending/boundary), `reason`; constrained registry supplies input strategies from domain. Model literal expected values are observations only. General property testing still occurs if the Critic proposal is invalid, using a logged deterministic fallback; do not claim that fallback was an agent's discovery. Verify installed Hypothesis strategies/settings/find/shrinking APIs. Hypothesis should drive batched inputs inside isolated worker jobs; never call candidate functions from host property code. Record minimized input and actual output from independent execution. Domain-valid empty tests only when min_length allows zero.

Limits: input context 4,096, A output 1,024, Critic 512, one optional format retry, one revision, output-token cap 4,096, total executions 400 including shrinking, episode 10 min, per function 2 sec, one job slot. All stages charge their work; cancel checks before each operation. Original baseline cannot be selected. A previous eligible candidate remains available unless a new authoritative counterexample invalidates it. The fixed controller records action source; the UI must say fixed Stage 1 policy, not trained Judge.

**VERIFY**

Run `python -m pytest tests/test_loop.py tests/test_property_engine.py -q`. Use test-only deterministic bad/good candidates to verify a plausible patch fails an approved order property, revision corrects it, proposed oracle cannot reject it, duplicate tests cache correctly, budget exhaustion leaves explicit scope and no incomplete eligible candidate. Then run real local `python -m codejury.controller.cli run --request ../contracts/fixtures/run-create.json --config config/model.yaml --out artifacts/demo/live-run.json`; validate the resulting snapshot, inspect actual results, and retain evidence whether success or abstention.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## A.08 · Measured Stage 1 evaluation and training report · P0 · depends: A.05, A.07

**PROMPT**

Goal: Provide genuine training and preliminary repair results for the professor.

Files you may touch: backend/src/codejury/evaluation/**, backend/src/codejury/api/training_report.py, backend/tests/test_evaluation.py, backend/docs/stage1-results.md, backend/artifacts/** ignored outputs

Evaluate raw_single, trained_a_single, and stage1_loop on the same sealed Stage 1 assessment set using the same visible inputs. Assess only after committing a final answer; no hidden feedback revisions. Report exact solved/total, incorrect accepted, unresolved, generated tokens, elapsed time, dataset/profile/model/checkpoint IDs, and actual count. Loop has greater budget than single-shot: state this; no fair superiority claim yet. Stage 2 runs matched-tool/budget baselines.

TrainingReport must show not_started/pilot_only/completed truthfully and real loss_points (null absent values), adapter hash and base problem counts. Do not return private sources/assessment tests. A training run with no evaluation stays pilot_only for the UI completion criterion. Any measured worsening is retained. Create live evidence for at least one successful supported repair and one unresolved/rejected/error path, each independently reproducible. If current model cannot yield a successful live repair, debug/evaluate; mark the live demonstration milestone incomplete rather than swapping in fixtures. No fixed accuracy percentage is promised.

**VERIFY**

Run `python -m codejury.evaluation.cli stage1 --manifest data/manifests/stage1.json --config config/model.yaml --out artifacts/evaluation/stage1-results.json` and `python -m pytest tests/test_evaluation.py -q`. Export report with `python -m codejury.evaluation.cli export-report --results artifacts/evaluation/stage1-results.json --out artifacts/evaluation/training-report.json`. Validate against TrainingReport. Save a report, measured counts, full reproducibility manifest, raw outputs, and hash-only list of sealed assessment assets.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## A.09 · Backend handoff and Stage 2 data hooks · P1 · depends: A.08

**PROMPT**

Goal: Finish a independently verifiable module and retain research-ready evidence.

Files you may touch: backend/docs/handoff.md, backend/tools/handoff_check.py, backend/tools/export_episode.py, backend/tests/test_episode_export.py

Export runtime-visible repair episode JSONL with problem/candidate/test/action/outcome IDs and no hidden content. Offline assessment uses a separate join keyed by training IDs only. This is the Stage2 source for Critic/Judge data; do not train those roles now. Add train-only A failure mining export for B (source IDs/split provenance, repeated raw outcomes) without making hidden evaluation accessible.

Handoff contains commit ID, tested package versions, exact commands, contract hash, runtime profile, checkpoint hashes, evidence paths, known failures, and task completion table. Do not add weights or large corpus blobs to Git. A CPU API test suite with dependency-injected fakes and a separate labelled Mac/sandbox suite let Sarvesh/integrator verify the boundary without retraining.

**VERIFY**

Run `python -m pytest tests/test_episode_export.py -q`, `python tools/handoff_check.py --contracts ../contracts`, `git diff --name-only <shared-base>...HEAD` (substitute the real saved common commit ID), and the full backend CPU suite with real test selections. Every changed file must be under backend; no schema change. Document sandbox/model checks separately; skipped hardware tests cannot be presented as passed.

Paste actual command output and a short evidence summary into your module's handoff log. A failing check leaves this task incomplete. Do not fabricate output or claim commands were run when they were not.

## D. Build order and independent completion

| Checkpoint | Tasks | Concrete output |
|---|---|---|
| Foundation | A.01–A.03 | Contract validation, trusted oracle code, actual sandbox execution |
| API | A.04 | All endpoints usable via curl/CLI; no partner UI needed |
| Data and learning | A.05–A.06 | Leak-free splits, real saved/reloaded Fixer A adapter |
| Repair demonstration | A.07 | Actual patch, test evidence, property challenge/revision loop |
| Research evidence | A.08–A.09 | Preliminary results, training card, reproducible handoff |

## E. Final acceptance — Ajay

Mark ✅ only with real evidence: frozen-schema validation; secure runner tests; all endpoints; real adapter training and reload; clean A/raw/A switching; valid counterexample loop; candidate/test ledger; actual successful live repair; explicit unresolved path; preliminary evaluation and real training report; own-directory-only diff. Training and live repair are required for the full Stage 1 milestone, even if Sarvesh's UI is already finished.

Your handoff is code plus evidence, not a promise to complete the learning work in Stage 2. Preserve the finalized architecture and state Stage 2 deferrals honestly.
