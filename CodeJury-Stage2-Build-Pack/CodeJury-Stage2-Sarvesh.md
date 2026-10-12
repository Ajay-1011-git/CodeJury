# CodeJury — Sarvesh's Complete Stage 2 Build Instructions

**Module:** typed domains/oracle gate, sandbox tools, AST search, mutation auditor, learned Critic, full evaluation/general comparator and UI. **Partner:** Ajay builds stage2_core with model worker, A/B/Judge and controller/API. You now own substantial backend/learning/research work as well as UI; the old easier-UI split does not apply.

**Grounding:** final architecture v2.0 and ORIGINAL Stage1 stage1.v1. Optional Stage1 quality upgrade not implemented and not required. Shared contract below concretizes the final system.

**Alignment:** final architecture governs safety/evidence/research; this document specifies tool ports, learning and analysis. You can develop/CPU-verify tools/UI using fixture ModelPort/core responses, and standalone native Critic/general trainers. Real data/benchmark/jobs depend on E2–E4 integration; don't present fake partner outputs as learning evidence.

## Operating contract — use as the coding agent's standing instructions

Read the actual repository, original Stage1 guide and finalized architecture first. The optional quality-upgrade pack is not part of the starting code. Preserve functioning Stage1 modules; finish missing foundation tasks before dependent work. Architecture wins on research/runtime principles; this Stage2 contract concretizes previously outlined interfaces and supersedes old Stage1 wire/scope limits for the new release.

1. Before third-party calls, inspect installed APIs/--help and current official documentation. Never invent a model module, MLX flag, trainer data key, Docker mount flag, EvalPlus adapter or browser API. Project-owned CLI commands below are required interfaces to implement/wrap, not preexisting tools.
2. Edit only task-listed owner paths. Import canonical ports/JSON definitions. Do not edit partner code, shared constraints/ports/schema or root/backend package manifests during independent work. Shared changes go through the single custodian at the listed integration checkpoint.
3. Use the existing stack: native macOS MLX worker, Linux VM sandbox, FastAPI,SQLite and static HTML/JS. No LangChain/AutoGen/cloud backend/second serving engine/mandatory premium service. One resident base, sequential roles/training jobs.
4. Validate every boundary. Never execute candidate modules/test assertions on host; static parsing is allowed. No hidden references/assessment tests in live prompts/UI/returned logs. No live online training or model auto-approval of oracles.
5. A CPU fake proves interface logic only. Label mock/replay/fixture and real raw/trained modes; never fabricate outputs, commands, training, confidence or success. Preserve regressions/failed benchmarks in reports.
6. For each task: state short plan/files, proceed within authorized scope, implement, run real VERIFY, repair failures, record actual output and local commit `stage2(<owner>): <task-id> <summary>`. No routine multi-file permission pauses. Do not push/deploy/publish/message automatically.
7. Done requires meaningful checks, correct contract/checksum, owner-only diff and a handoff recording actual versions/hashes/limits. Native-Mac/real-sandbox tests pending are not marked passed. Completion includes all four trained roles and final live integration, not a scaffold or fixture demo.

No timeline was supplied; tables are dependency checkpoints. Balanced ownership means comparable hard engineering, not guaranteed equal hours. Each module can be implemented and CPU-verified alone; real coupled training/evaluation requires the explicit integration/artefact exchanges below. Never fill absent partner outputs with invented data to claim final completion.

# Frozen shared Stage 2 contract — stage2.v1

This entire block and its canonical JSON Schema are identical in Ajay's and Sarvesh's guides. The machine schema is contracts/stage2.schema.json; SHA-256 **ee62388479918f0e33d4085d530dc210356ed104afe6170b1ff03687e53b6ee6**. Import interfaces from the common seeded backend/src/codejury/stage2_ports.py, copied byte-for-byte from contracts/shared/stage2_ports.py. Select named definitions with the full root $defs available. Do not fetch the $id URL, rename fields or independently recreate wire schemas. Domain DSL/parameter objects are nested typed values; all durable record/envelope definitions include schema_version:stage2.v1.

## 1. Starting point and ownership

Start from ORIGINAL Stage1 stage1.v1. The optional stage1.v1.1 quality upgrade was NOT implemented and is NOT a prerequisite. Stage2 implements candidate diversity, feedback, search and quality measurement as part of the full architecture. Audit actual code first; no repository or execution outputs were supplied when these docs were written.

Ajay owns backend/src/codejury/stage2_core/**, backend/tests/stage2_core/**, backend/config/stage2_core/**, backend/docs/stage2_core/**, backend/tools/stage2_core/** and backend/data/stage2_core/**. Sarvesh owns corresponding stage2_tools/** directories plus web/**. Original Stage1 modules stay unchanged during parallel work: each owner writes adapters inside their new module for reuse. Neither edits the other's files or backend/pyproject.toml/lockfiles while branching. Owner-specific requirements go under their config directory and must obey the one seeded common constraints file.

Before branches diverge, Ajay is contract/integration custodian: seed contracts/stage2.schema.json, contracts/STAGE2-SHA256SUMS and contracts/stage2-fixtures/ from the pack, copy shared ports into backend/src/codejury/stage2_ports.py, preserve contracts/legacy/stage1-v1-api.schema.json, and seed reference/stage2/ plus integration/stage2/README.md. Existing Stage1 schema/checksum/fixtures remain unchanged. The pack stores fixtures under contracts/fixtures/; repository checkers explicitly select contracts/stage2-fixtures/ for Stage2, with pack fallback only when validating the downloaded pack. This is a one-time shared seed, not both owners editing contracts. Afterwards contract/ports/reference are immutable. Ajay owns integration/** and existing API routing/package manifest changes ONLY at integration checkpoints. Sarvesh supplies dependency changes as a manifest diff proposal; one integrator applies and locks them. Preserve Stage1 baseline code/weights/assessment records in Git/local artefact history.

## 2. Runtime seam and factories

The contract unifies HTTP, Python ports and artifact exchange. Do not add internal network services just to make the split. ModelPort.generate(ModelRequest,cancel_event) -> ModelResponse is Ajay's long-lived native-worker facade. ToolPort.call(ToolRequest,cancel_event) -> ToolResult is Sarvesh's runner/search/audit/investigation facade. RolloutPort.continue_episode(RolloutRequest,cancel_event) -> RolloutResult is Ajay's training-only continuation facade. All use JSON-serializable dicts and a threading.Event cancellation token; serialize requests before worker IPC. Pure Protocol types do not run anything. Worker processes, IPC framing and local tests stay behind these ports.

Required factories: codejury.stage2_core.factory.make_model_port(config_path), make_rollout_port(config_path,model_port,tool_port), make_baseline_port(config_path,model_port,tool_port); codejury.stage2_tools.factory.make_tool_port(config_path). Application factory: codejury.stage2_core.api.create_app(config_path,model_port,tool_port). BaselinePort.run(MethodRequest,cancel_event) -> MethodResult is Ajay's exact research-runtime facade. Sarvesh's harness consumes this port, never imports private core controller internals. MethodRequest config_hash must match the registered frozen method configuration; MethodResult commits selected source/hash and runtime-visible candidate pool BEFORE external hidden scoring. Final assessment rejects fixture results. These are project-owned interfaces to implement, not installed APIs. Standard-library pathlib.Path is accepted for config_path. CPU tests inject schema-valid fixture ports; fakes never load in live factories or report real inference. Tests of one half import no running partner implementation. Final CLI bootstraps both factories after merge.

ToolRequest carries complete runtime-visible Problem and tagged operation parameters. Controller generates IDs, including a unique id_prefix for delegated tool result IDs; tools append deterministic c/t/e/m/g suffixes, never collide with other requests. Candidates returned by tools are Drafts; Ajay commits events and adds created_event_id/eligibility. Model responses are raw text plus actual usage; parse with RepairDraft, CriticDraft or JudgeDraft after validation. Neither tool nor model verdict can overwrite controller eligibility.

| Operation | Required tool result content | Side effects |
|---|---|---|
| validate | ValidationReceipt, other arrays empty |Parse and semantic-check only; no code import on host|
| evaluate |Execution records for supplied candidate/test pairs; all other arrays empty|Actual sandbox calls, including related inputs|
| search |CandidateDrafts + executions; other arrays empty|Bounded AST edits, fail-first execution|
| audit |ProbeMutants + AuditGaps; no selectable CandidateDrafts|Mutants are evidence probes, not jury votes|
| investigate |Admitted/quarantined TestCases + executions; candidates/mutants/gaps empty|Generator exploration, replayed shrinking, oracle gate|

Response request_id must match. status:error/infra/budget/cancel never becomes semantic failure. Arrays empty means no content, not fabricated work. Every invocation reports delta ResourceUsage; caller adds deltas once, does not count child work twice. Model/in-process wrapper timings are attributed without double-counting episode walltime. Tool responses may contain partial completed evidence on budget/cancel; incomplete candidates cannot qualify.

## 3. HTTP contract

Local API8000, mock8001, UI8080 before merge; same-origin after merge. Explicit localhost-only ?api= override remains. One active repair owns model/runner; no training while live inference. Poll snapshot/events every1,000ms, cursor after>=0, default0; max500 events per page; next_after is max returned ID or previous cursor; deduplicate IDs. Stop polling terminal/navigation; cancelled work terminates worker jobs.

| Method/path | Input | Success definition | HTTP |
|---|---|---|---:|
| GET /health |none|Health|200|
| GET /examples |none|Examples|200|
| POST /runs |RunCreate|RunAccepted|202|
| GET /runs/{run_id} |none|RunSnapshot|200|
| GET /runs/{run_id}/events?after=N |N>=0|EventPage|200|
| GET /runs/{run_id}/candidates/{candidate_id} |none|Candidate|200|
| POST /runs/{run_id}/cancel |empty body|RunSnapshot|200|
| GET /runs/{run_id}/report |terminal only|RunSnapshot|200|
| GET /stage2/training-report |none|TrainingReport|200|
| GET /stage2/benchmark-report |none|BenchmarkReport|200|

Error envelope is Error for422 invalid structure/semantics/version,409 busy/report-not-terminal/known archived Stage1 ID,404 unknown ID,503 unavailable live dependencies before scheduling. Persist accepted state before dispatch; post-acceptance infrastructure loss is infrastructure_error. Keep old Stage1 API/records available through an explicitly separate old-version release/CLI export; do not relabel old candidates or silently accept mixed payload versions. Stage2 UI checks health version/hash before submit. No-cache application/json; all unknown keys rejected and required nullable fields present. No authentication/hosting account/streaming requirement.

## 4. Input domain, helpers and dependencies

Extend Stage1 to architecture's JSON domain: null/bool/int/string/list/string-keyed dict, with explicit json.v1 codec. No implicit tuple/list, set/list, arbitrary object or float conversion; booleans never equal integers. Inputs use recursive ValueDomain DSL: integer bounds within +/-1,000,000; strings explicit alphabet and <=128 codepoints; lists<=64; dictionaries<=20 explicit required keys plus bounded key/value domains; union2–6 disjoint/overlapping alternatives validated recursively. Enforce min<=max, required keys valid/unique, nesting<=4, aggregate JSON nodes<=4,096, and type-sensitive recursive comparison. Outputs use safe JSON integers within +/- (2^53-1); codec violations are explicit candidate errors. Do not coerce output Counter/deque into JSON silently.

Allow one target plus<=3 supplied pure helpers and approved top-level imports; no classes/decorators/async/generators, mutable global state or installation during runs. Fixed1–6 positional parameter signature; no kwargs/default-argument guesses. Every helper has explicit reviewed name/signature/behaviour interface so B can reconstruct without seeing its buggy body; missing essential helper semantics -> unresolved. Candidate bundle must preserve target/helper interfaces; in-place effects remain a separate future scope and are rejected here.

Initial dependency allowlist: math.gcd, math.isqrt, bisect.bisect_left, bisect.bisect_right, collections.Counter, collections.deque. Reviewed builtin call names: len,range,sum,min,max,abs,sorted,reversed,enumerate,zip,all,any,int,bool,str,list,dict,set,tuple. Internal containers may be used, but output codec rules still reject implicit tuple/set/custom conversion. Imports are restricted to declared symbols/module attributes; no dynamic import/eval/exec/open/getattr/dunder traversal. Static rejection supplements, never replaces VM isolation. Verify allowlist purity/version and AST alias handling before enabling; exclude unsupported dependencies explicitly. Names/classes from arbitrary external libraries and nondeterminism remain outside scope. Source cap48k bytes; per-model context must fit without silently dropping tests/contract/helper semantics. Report context-limit unresolved when it cannot fit the selected profile.

## 5. Oracle registry and admission

Approved Requirements come only from user/reviewed_contract before run. Initial property templates: sort_ascending_ints, unique_preserve_order_ints, sum_ints, reverse_string, count_occurrences_ints (list,int -> exact integer count). Reviewed implementations are pure controller/tool-side functions; candidate outputs remain untrusted. Maintain exact signature/domain compatibility and executable template version hash. Approved metamorphic templates: permutation_invariant for the explicitly approved sum/sort contract; idempotent for explicitly approved pure sorting contract. Those relations are additional finite checks, not sufficient proofs alone. General arbitrary natural-language requirements stay proposed until reviewed; no model auto-approval.

Literal supplied tests are authoritative; model-invented literals remain proposed/observed even when they happen to pass a training reference. TestProposal must specify EXACTLY ONE non-null generator_spec or concrete_inputs. Metamorphic tests require related_inputs and registered relation justification; ordinary tests require related_inputs null. Each relation test executes fresh base and followup calls, counts2 invocations and compares according to registry. actual_output encodes {base:...,followup:...} only for relation evidence. Input effects record each call. Unapproved proposals can guide observation/discrimination but cannot reject or certify patches. Contradictory authoritative requirements/tests suspend selection; no majority vote resolves them.

Property-engine pools and Critic-generated inputs are within domain and finite budgets. A new hard test marks previous qualification stale; apply to all candidates still selectable. Shrink only domain-valid failures, independently replay minimal result, charge all probes, then admit justified test. Final suite freeze/hash includes exact test inputs/oracle versions. Required tests must all pass with no unsupported effects before eligibility. Passing subset or proposed observation never qualifies. If an essential requirement remains ambiguous between survivors, unresolved; disclose other untested requirements explicitly in Decision scope.

## 6. Candidate and audit semantics

Original never selected. A initial view includes buggy bundle, requirement/tests/trace; B initial view includes signature/contract/domain/dependency/helper interfaces/tests, excluding buggy bodies, A code/diagnosis/trace and hidden targets. After commitment B may receive real counterexamples for revision. B is a separate trained adapter, not a reference oracle. Candidate source hashes are exact UTF-8 bytes. AST normalization deduplicates alternatives without deleting private proposal provenance; sampled behavioural signatures group only observed equivalence. Parent chains are acyclic; revisions/search are descendants, not independent opinions. Draft IDs/model/config hashes preserved at controller commit.

Search supports5 edit families and bounded depth2, max48 executed search candidates/episode; single edits first, beam width4 for second edits around evidence-promising parents. Every Edit records parent_source_hash/result_source_hash and immediate-parent locations. ToolResult.edit_sources carries exact intermediate source artifacts; core stores them immutably. A two-edit descendant may link the root candidate ID, but its hash chain must reconstruct both edits in order. Intermediate sources are provenance, not extra independent candidate opinions. Prefer failure-supported sites; hints aren't proof. Parse on host, compile/execute only sandbox, reject changed signatures/dependencies/unknown names, no test-specific constants/branches. Search never rewrites user file/test/harness.

Auditor creates<=24 probes per version,<=48 total. Only actual hard-test rejection is killed; survivors may be equivalent or a genuine test gap. Timeouts separate, invalid/duplicate separate; no100% mutation target or implicit mutant wrongness. AuditGap ties exact candidate source and suite hash to locations/requirements; stale gaps cannot accuse a revised candidate. Probe mutants are not selectable patches; promoting a useful edit requires explicit search/candidate registration and full acceptance. Critic uses gap as experiment-design input; Judge chooses further investigation. Audit-loop success is new valid failures/final correctness, not raw kill count.

## 7. Judge actions, eligibility and budgets

Controller constructs concrete available ActionOptions from state and remaining resources. Learned Judge returns state_id/action_option_id/evidence IDs/rationale only; lookup yields frozen InvestigationAction. No new code/IDs/budget powers in Judge output. Validate state freshness, option prerequisites, targets/requirements/evidence IDs, budget and action kind/parameter tag. select must name one eligible current candidate; audit needs a current eligible candidate; revise needs a committed parent plus actual feedback; criticize mode/targets must exist. Refused action logged; one retry maximum within8 Judge calls then deterministic fallback marked fixed fallback, never fabricated learned action. Action counters include invalid decisions/retries; final action records may be fewer than consumed Judge calls.

Initial A then B commit before learned choices. Allowed actions: generate,criticize,search,audit,revise,select,abstain. Judge sees StateSnapshot plus bounded runtime-visible source/test/outcome/gap summaries assembled by core; never whole hidden corpus. Retain A incumbent when eligible and no new hard evidence justifies replacing it; otherwise deterministic eligible tie-break smaller edit distance then proposal order. Final qualification propagates all admitted hard tests. Cancel/infra error prevents stale success. Budget exit may select only fully qualified incumbent under disclosed frozen suite, else unresolved.

Mac-standard-v1: one 4-bit base3.8B, one active LoRA at a time; four trained roles A/B/Critic/Judge, optional general comparator. Context4,096 total prompt+reserved completion; repair/reconstruction/revision<=1,024 output, Critic<=512, Judge<=192. Episode<=10,000 generated tokens and100,000 input tokens,8 learned candidates including revisions,48 search candidates,48 audit probes,8 Judge decisions,3,000 actual function invocations,15min walltime. Format retries charge tokens and appropriate role attempt. Per-call2s, initial runner512MB; VM2CPU/2GB. Stop live services during sequential training when unnecessary. Actual memory/throughput unmeasured; no promise these caps finish on every Mac. Clip every request to remaining budget and reserve final qualification; early failures prune but incomplete tests stay pending. Record measured peak memory or null. One exclusive Mac compute queue prevents simultaneous live/training/teacher jobs.

## 8. Training and exchange invariants

Keep exact base revision/tokenizer/quantization/topology across all adapters. A may be retained only after executable validation/reload; fix data/masking/loading regression before expanding roles. B uses frozen A training-only failure rates w=1+alpha*f, with general mixture and independent view; tune alpha on validation. Critic execution-filtered targets include valid counterexamples, invalid-proposal rejection and correct-candidate no-objection cases. Judge labels compare alternative actions from identical runtime states, same fixed continuation policy/budget and repeated seeds; hidden TRAINING assessment scores labels offline and is never inference input. Use SFT/action-outcome supervision; RL optional, not completion prerequisite.

Ajay owns A/B/Judge training/data code. Sarvesh owns Critic and general-comparator training/data code plus benchmark harness. Both inspect real MLX-LM data format/CLI, use completion masking, rank8/microbatch1 initial pilots, verified module targets and saved/reloaded manifests; never assume Phi LoRA support from a generic family list. Optional teacher local7B runs separately, not resident with student. Free path is reviewed sources, controlled bugs, filtered local drafts. Paid teachers optional and never replace validation. Model switch contingency Qwen2.5-Coder3B is a recorded whole-experiment switch; never merge incompatible adapter families.

ArtifactManifest has actual relative paths/hashes/counts/owner/split. Exchange ignored backend/artifacts/stage2-exchange/{ajay,sarvesh}/ files, not shared code edits or Git weights. Validate paths (no absolute/traversal/symlink escape), sizes, hashes, role compatibility and split lineage before consuming. Train/validation exports contain only authorized pool records; final_assessment manifests/hidden files stay with benchmark owner, never copied into runtime/training exchange. Stage1 assessment already inspected becomes development data; seal new final Stage2 holdout before model selection/label collection. Split base problems/families before variants/traces. Counts refer to actual independent base problems, not repeated mutations/seeds.

## 9. Reports and release truth

TrainingReport contains real AdapterCards with statuses not_started/pilot_only/completed; completed requires saved/reloaded actual training plus role-specific evaluation. All4 required cards completed for full_stage2_ready; general comparator required for the claimed B3 research comparison, not local user repair. Core/tools live readiness must also be real. No fake adapters, fixture replay or fixed-only fallback masquerades as full trained system.

BenchmarkReport counts are from final selected patches, not oracle-best candidate in pool. Per row total_base_problems equals sum of six disjoint outcome counts for ONE stated seed aggregate (public default first fixed seed); seed_count records experiments and full3-seed per-problem table stays in research artifacts. Paired clustered analysis uses all seeds without treating repeats as independent base problems. Null metrics unavailable;0 remains0. Report not_run empty rows/null dataset, partial actual rows, completed every declared run recorded including failures. research_outcome improved/inconclusive/worse is determined by paired uncertainty and false acceptance/cost, not number of components implemented. No hidden code/tests/paths/secrets in API aggregates.

Stage2 fixtures under the pack contracts/fixtures/ (repository contracts/stage2-fixtures/) are SYNTHETIC: all envelope runtime_mode fixture and persistent UI banner. They enable independent CPU/API/UI tests, never real training/quality evidence. Benchmark baseline tool parity and resource matching are required before any claim that the council beats a strong single AI. Feature-complete and statistically supported benefit are separate release statements.

## 10. Canonical shared Python interface

```python
"""Frozen Stage 2 Python interfaces. No model/tool implementations live here."""
from typing import Any, Protocol
from threading import Event

Record = dict[str, Any]

class ModelPort(Protocol):
    def generate(self, request: Record, cancel: Event) -> Record:
        """ModelRequest -> ModelResponse; validates both sides, actual usage only."""
        ...

class ToolPort(Protocol):
    def call(self, request: Record, cancel: Event) -> Record:
        """ToolRequest -> ToolResult; no candidate execution on the host."""
        ...

class RolloutPort(Protocol):
    def continue_episode(self, request: Record, cancel: Event) -> Record:
        """RolloutRequest -> RolloutResult; training-only isolated fork, no hidden labels."""
        ...

class BaselinePort(Protocol):
    def run(self, request: Record, cancel: Event) -> Record:
        """MethodRequest -> MethodResult; commits answer before external hidden scoring."""
        ...
```

## 11. Canonical schema — verbatim

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://codejury.local/contracts/stage2.v1",
  "title": "CodeJury Stage 2 canonical API, model, tool and artifact contract",
  "type": "object",
  "$comment": "Select a named $defs entry. Business invariants in both guides supplement structural validation. This ID is not a hosted URL.",
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
          "type": "integer",
          "minimum": -9007199254740991,
          "maximum": 9007199254740991
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
    "NullDomain": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "null"
        }
      },
      "required": [
        "kind"
      ],
      "additionalProperties": false
    },
    "BooleanDomain": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "boolean"
        }
      },
      "required": [
        "kind"
      ],
      "additionalProperties": false
    },
    "IntegerDomain": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "integer"
        },
        "min": {
          "type": "integer",
          "minimum": -1000000,
          "maximum": 1000000
        },
        "max": {
          "type": "integer",
          "minimum": -1000000,
          "maximum": 1000000
        }
      },
      "required": [
        "kind",
        "min",
        "max"
      ],
      "additionalProperties": false
    },
    "StringDomain": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "string"
        },
        "alphabet": {
          "type": "string",
          "minLength": 1,
          "maxLength": 256
        },
        "min_length": {
          "type": "integer",
          "minimum": 0
        },
        "max_length": {
          "type": "integer",
          "minimum": 0,
          "maximum": 128
        }
      },
      "required": [
        "kind",
        "alphabet",
        "min_length",
        "max_length"
      ],
      "additionalProperties": false
    },
    "ListDomain": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "list"
        },
        "item_domain": {
          "$ref": "#/$defs/ValueDomain"
        },
        "min_length": {
          "type": "integer",
          "minimum": 0
        },
        "max_length": {
          "type": "integer",
          "minimum": 0,
          "maximum": 64
        }
      },
      "required": [
        "kind",
        "item_domain",
        "min_length",
        "max_length"
      ],
      "additionalProperties": false
    },
    "DictDomain": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "dict"
        },
        "key_domain": {
          "$ref": "#/$defs/StringDomain"
        },
        "value_domain": {
          "$ref": "#/$defs/ValueDomain"
        },
        "required_keys": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "maxItems": 20
        },
        "min_size": {
          "type": "integer",
          "minimum": 0
        },
        "max_size": {
          "type": "integer",
          "minimum": 0,
          "maximum": 20
        }
      },
      "required": [
        "kind",
        "key_domain",
        "value_domain",
        "required_keys",
        "min_size",
        "max_size"
      ],
      "additionalProperties": false
    },
    "UnionDomain": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "union"
        },
        "options": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ValueDomain"
          },
          "maxItems": 6,
          "minItems": 2
        }
      },
      "required": [
        "kind",
        "options"
      ],
      "additionalProperties": false
    },
    "ValueDomain": {
      "oneOf": [
        {
          "$ref": "#/$defs/NullDomain"
        },
        {
          "$ref": "#/$defs/BooleanDomain"
        },
        {
          "$ref": "#/$defs/IntegerDomain"
        },
        {
          "$ref": "#/$defs/StringDomain"
        },
        {
          "$ref": "#/$defs/ListDomain"
        },
        {
          "$ref": "#/$defs/DictDomain"
        },
        {
          "$ref": "#/$defs/UnionDomain"
        }
      ]
    },
    "ArgDomain": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "domain": {
          "$ref": "#/$defs/ValueDomain"
        }
      },
      "required": [
        "name",
        "domain"
      ],
      "additionalProperties": false
    },
    "HelperInterface": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "signature": {
          "type": "string"
        },
        "contract_text": {
          "type": "string"
        }
      },
      "required": [
        "name",
        "signature",
        "contract_text"
      ],
      "additionalProperties": false
    },
    "Requirement": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "requirement_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "description": {
          "type": "string"
        },
        "source": {
          "enum": [
            "user",
            "reviewed_contract",
            "model"
          ]
        },
        "approval_status": {
          "enum": [
            "approved",
            "proposed",
            "rejected"
          ]
        },
        "property_template_id": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "parameters": {
          "$ref": "#/$defs/JsonValue"
        }
      },
      "required": [
        "schema_version",
        "requirement_id",
        "description",
        "source",
        "approval_status",
        "property_template_id",
        "parameters"
      ],
      "additionalProperties": false
    },
    "SuppliedTest": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "test_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "inputs": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/JsonValue"
          },
          "maxItems": 6,
          "minItems": 1
        },
        "expected": {
          "$ref": "#/$defs/JsonValue"
        },
        "requirement_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        }
      },
      "required": [
        "schema_version",
        "test_id",
        "inputs",
        "expected",
        "requirement_ids"
      ],
      "additionalProperties": false
    },
    "RunCreate": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "source": {
          "type": "string",
          "minLength": 1,
          "maxLength": 48000
        },
        "function_name": {
          "type": "string",
          "pattern": "^[A-Za-z_][A-Za-z0-9_]*$"
        },
        "contract_text": {
          "type": "string",
          "minLength": 1,
          "maxLength": 12000
        },
        "domain_schema": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ArgDomain"
          },
          "maxItems": 6,
          "minItems": 1
        },
        "helper_interfaces": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/HelperInterface"
          },
          "maxItems": 3
        },
        "requirements": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Requirement"
          },
          "maxItems": 30,
          "minItems": 1
        },
        "supplied_tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/SuppliedTest"
          },
          "maxItems": 50,
          "minItems": 1
        },
        "allowed_dependencies": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "maxItems": 10
        },
        "resource_profile": {
          "const": "mac-standard-v1"
        },
        "policy_mode": {
          "enum": [
            "learned",
            "fixed"
          ]
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        }
      },
      "required": [
        "schema_version",
        "source",
        "function_name",
        "contract_text",
        "domain_schema",
        "helper_interfaces",
        "requirements",
        "supplied_tests",
        "allowed_dependencies",
        "resource_profile",
        "policy_mode",
        "seed"
      ],
      "additionalProperties": false
    },
    "Problem": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "problem_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "source_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "source": {
          "type": "string"
        },
        "function_name": {
          "type": "string"
        },
        "signature": {
          "type": "string"
        },
        "contract_text": {
          "type": "string"
        },
        "domain_schema": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ArgDomain"
          },
          "maxItems": 6,
          "minItems": 1
        },
        "helper_interfaces": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/HelperInterface"
          },
          "maxItems": 3
        },
        "requirements": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Requirement"
          },
          "maxItems": 30
        },
        "supplied_test_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          },
          "maxItems": 50
        },
        "allowed_dependencies": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "maxItems": 10
        },
        "resource_profile": {
          "const": "mac-standard-v1"
        },
        "input_codec_version": {
          "const": "json.v1"
        }
      },
      "required": [
        "schema_version",
        "problem_id",
        "source_hash",
        "source",
        "function_name",
        "signature",
        "contract_text",
        "domain_schema",
        "helper_interfaces",
        "requirements",
        "supplied_test_ids",
        "allowed_dependencies",
        "resource_profile",
        "input_codec_version"
      ],
      "additionalProperties": false
    },
    "LiteralOracle": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "literal"
        },
        "expected": {
          "$ref": "#/$defs/JsonValue"
        }
      },
      "required": [
        "kind",
        "expected"
      ],
      "additionalProperties": false
    },
    "PropertyOracle": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "property"
        },
        "property_id": {
          "type": "string"
        },
        "parameters": {
          "$ref": "#/$defs/JsonValue"
        }
      },
      "required": [
        "kind",
        "property_id",
        "parameters"
      ],
      "additionalProperties": false
    },
    "MetamorphicOracle": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "metamorphic"
        },
        "relation_id": {
          "type": "string"
        },
        "parameters": {
          "$ref": "#/$defs/JsonValue"
        }
      },
      "required": [
        "kind",
        "relation_id",
        "parameters"
      ],
      "additionalProperties": false
    },
    "ObservationOracle": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "observation"
        },
        "hypothesis": {
          "type": "string"
        }
      },
      "required": [
        "kind",
        "hypothesis"
      ],
      "additionalProperties": false
    },
    "OracleSpec": {
      "oneOf": [
        {
          "$ref": "#/$defs/LiteralOracle"
        },
        {
          "$ref": "#/$defs/PropertyOracle"
        },
        {
          "$ref": "#/$defs/MetamorphicOracle"
        },
        {
          "$ref": "#/$defs/ObservationOracle"
        }
      ]
    },
    "TestCase": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "test_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "input_codec_version": {
          "const": "json.v1"
        },
        "inputs": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/JsonValue"
          },
          "maxItems": 6,
          "minItems": 1
        },
        "related_inputs": {
          "anyOf": [
            {
              "type": "array",
              "items": {
                "$ref": "#/$defs/JsonValue"
              },
              "maxItems": 6,
              "minItems": 1
            },
            {
              "type": "null"
            }
          ]
        },
        "oracle_spec": {
          "$ref": "#/$defs/OracleSpec"
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
        "domain_valid": {
          "type": "boolean"
        },
        "requirement_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "provenance": {
          "enum": [
            "supplied",
            "critic",
            "property_engine",
            "audit_followup",
            "revision_regression"
          ]
        }
      },
      "required": [
        "schema_version",
        "test_id",
        "input_codec_version",
        "inputs",
        "related_inputs",
        "oracle_spec",
        "oracle_status",
        "oracle_source",
        "domain_valid",
        "requirement_ids",
        "provenance"
      ],
      "additionalProperties": false
    },
    "GeneratorSpec": {
      "type": "object",
      "properties": {
        "family": {
          "enum": [
            "general",
            "empty",
            "singleton",
            "duplicates",
            "ascending",
            "descending",
            "boundary",
            "negative",
            "unicode",
            "missing_key",
            "audit_site"
          ]
        },
        "argument_index": {
          "type": "integer",
          "minimum": 0
        },
        "parameters": {
          "$ref": "#/$defs/JsonValue"
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        }
      },
      "required": [
        "family",
        "argument_index",
        "parameters",
        "seed"
      ],
      "additionalProperties": false
    },
    "TestProposal": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "proposal_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "requirement_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "generator_spec": {
          "anyOf": [
            {
              "$ref": "#/$defs/GeneratorSpec"
            },
            {
              "type": "null"
            }
          ]
        },
        "concrete_inputs": {
          "anyOf": [
            {
              "type": "array",
              "items": {
                "type": "array",
                "items": {
                  "$ref": "#/$defs/JsonValue"
                },
                "maxItems": 6,
                "minItems": 1
              },
              "maxItems": 32,
              "minItems": 1
            },
            {
              "type": "null"
            }
          ]
        },
        "oracle_spec": {
          "$ref": "#/$defs/OracleSpec"
        },
        "rationale": {
          "type": "string"
        },
        "target_candidate_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          },
          "maxItems": 8
        }
      },
      "required": [
        "schema_version",
        "proposal_id",
        "requirement_ids",
        "generator_spec",
        "concrete_inputs",
        "oracle_spec",
        "rationale",
        "target_candidate_ids"
      ],
      "additionalProperties": false
    },
    "Location": {
      "type": "object",
      "properties": {
        "lineno": {
          "type": "integer",
          "minimum": 1
        },
        "col_offset": {
          "type": "integer",
          "minimum": 0
        },
        "end_lineno": {
          "type": "integer",
          "minimum": 1
        },
        "end_col_offset": {
          "type": "integer",
          "minimum": 0
        }
      },
      "required": [
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset"
      ],
      "additionalProperties": false
    },
    "Edit": {
      "type": "object",
      "properties": {
        "location": {
          "$ref": "#/$defs/Location"
        },
        "operator_family": {
          "enum": [
            "comparison",
            "boundary_constant",
            "boolean_negation",
            "arithmetic",
            "variable_reference"
          ]
        },
        "before": {
          "type": "string"
        },
        "after": {
          "type": "string"
        },
        "parent_source_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "result_source_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      },
      "required": [
        "location",
        "operator_family",
        "before",
        "after",
        "parent_source_hash",
        "result_source_hash"
      ],
      "additionalProperties": false
    },
    "SourceArtifact": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "source_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "source": {
          "type": "string"
        }
      },
      "required": [
        "schema_version",
        "source_hash",
        "source"
      ],
      "additionalProperties": false
    },
    "CandidateDraft": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "candidate_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "problem_id": {
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
            "fixer_b",
            "fixer_a_revision",
            "fixer_b_revision",
            "ast_search"
          ]
        },
        "generation_view": {
          "enum": [
            "original",
            "targeted_repair",
            "independent_reconstruction",
            "feedback_revision",
            "ast_search"
          ]
        },
        "source": {
          "type": "string"
        },
        "source_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "diagnosis": {
          "type": "string"
        },
        "assumptions": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "maxItems": 12
        },
        "requirement_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "model_config_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        },
        "edits": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Edit"
          },
          "maxItems": 2
        }
      },
      "required": [
        "schema_version",
        "candidate_id",
        "problem_id",
        "parent_id",
        "origin",
        "generation_view",
        "source",
        "source_hash",
        "diagnosis",
        "assumptions",
        "requirement_ids",
        "model_config_hash",
        "edits"
      ],
      "additionalProperties": false,
      "allOf": [
        {
          "if": {
            "properties": {
              "origin": {
                "const": "original"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "original"
              },
              "edits": {
                "maxItems": 0
              },
              "parent_id": {
                "type": "null"
              },
              "model_config_hash": {
                "type": "null"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "origin": {
                "const": "fixer_a"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "targeted_repair"
              },
              "edits": {
                "maxItems": 0
              },
              "model_config_hash": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "origin": {
                "const": "fixer_b"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "independent_reconstruction"
              },
              "edits": {
                "maxItems": 0
              },
              "model_config_hash": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "origin": {
                "const": "fixer_a_revision"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "feedback_revision"
              },
              "edits": {
                "maxItems": 0
              },
              "model_config_hash": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$"
              },
              "parent_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 120
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "origin": {
                "const": "fixer_b_revision"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "feedback_revision"
              },
              "edits": {
                "maxItems": 0
              },
              "model_config_hash": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$"
              },
              "parent_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 120
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "origin": {
                "const": "ast_search"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "ast_search"
              },
              "edits": {
                "minItems": 1,
                "maxItems": 2
              },
              "parent_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 120
              },
              "model_config_hash": {
                "type": "null"
              }
            }
          }
        }
      ]
    },
    "Candidate": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "candidate_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "problem_id": {
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
            "fixer_b",
            "fixer_a_revision",
            "fixer_b_revision",
            "ast_search"
          ]
        },
        "generation_view": {
          "enum": [
            "original",
            "targeted_repair",
            "independent_reconstruction",
            "feedback_revision",
            "ast_search"
          ]
        },
        "source": {
          "type": "string"
        },
        "source_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "diagnosis": {
          "type": "string"
        },
        "assumptions": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "maxItems": 12
        },
        "requirement_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "model_config_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        },
        "edits": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Edit"
          },
          "maxItems": 2
        },
        "created_event_id": {
          "type": "integer",
          "minimum": 1
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
        },
        "verification_suite_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "schema_version",
        "candidate_id",
        "problem_id",
        "parent_id",
        "origin",
        "generation_view",
        "source",
        "source_hash",
        "diagnosis",
        "assumptions",
        "requirement_ids",
        "model_config_hash",
        "edits",
        "created_event_id",
        "eligibility",
        "rejection_reason",
        "verification_suite_hash"
      ],
      "additionalProperties": false,
      "allOf": [
        {
          "if": {
            "properties": {
              "origin": {
                "const": "original"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "original"
              },
              "edits": {
                "maxItems": 0
              },
              "parent_id": {
                "type": "null"
              },
              "model_config_hash": {
                "type": "null"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "origin": {
                "const": "fixer_a"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "targeted_repair"
              },
              "edits": {
                "maxItems": 0
              },
              "model_config_hash": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "origin": {
                "const": "fixer_b"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "independent_reconstruction"
              },
              "edits": {
                "maxItems": 0
              },
              "model_config_hash": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "origin": {
                "const": "fixer_a_revision"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "feedback_revision"
              },
              "edits": {
                "maxItems": 0
              },
              "model_config_hash": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$"
              },
              "parent_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 120
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "origin": {
                "const": "fixer_b_revision"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "feedback_revision"
              },
              "edits": {
                "maxItems": 0
              },
              "model_config_hash": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$"
              },
              "parent_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 120
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "origin": {
                "const": "ast_search"
              }
            },
            "required": [
              "origin"
            ]
          },
          "then": {
            "properties": {
              "generation_view": {
                "const": "ast_search"
              },
              "edits": {
                "minItems": 1,
                "maxItems": 2
              },
              "parent_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 120
              },
              "model_config_hash": {
                "type": "null"
              }
            }
          }
        }
      ]
    },
    "InputEffect": {
      "type": "object",
      "properties": {
        "call_index": {
          "type": "integer",
          "minimum": 0
        },
        "mutated": {
          "type": "boolean"
        },
        "before_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "after_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      },
      "required": [
        "call_index",
        "mutated",
        "before_hash",
        "after_hash"
      ],
      "additionalProperties": false
    },
    "ExceptionInfo": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string"
        },
        "message": {
          "type": "string"
        },
        "location": {
          "anyOf": [
            {
              "$ref": "#/$defs/Location"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "type",
        "message",
        "location"
      ],
      "additionalProperties": false
    },
    "Execution": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
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
        "runtime_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "actual_output": {
          "$ref": "#/$defs/JsonValue"
        },
        "input_effects": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/InputEffect"
          },
          "maxItems": 2
        },
        "exception": {
          "anyOf": [
            {
              "$ref": "#/$defs/ExceptionInfo"
            },
            {
              "type": "null"
            }
          ]
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
        "duration_ms": {
          "type": "integer",
          "minimum": 0
        },
        "trace_ref": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        },
        "trace_truncated": {
          "type": "boolean"
        }
      },
      "required": [
        "schema_version",
        "execution_id",
        "candidate_id",
        "test_id",
        "runtime_hash",
        "actual_output",
        "input_effects",
        "exception",
        "outcome",
        "duration_ms",
        "trace_ref",
        "trace_truncated"
      ],
      "additionalProperties": false
    },
    "ProbeMutant": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "mutant_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "parent_candidate_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "source": {
          "type": "string"
        },
        "source_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "edit": {
          "$ref": "#/$defs/Edit"
        },
        "outcome": {
          "enum": [
            "invalid",
            "killed",
            "survived",
            "timeout",
            "duplicate"
          ]
        },
        "test_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "equivalence_status": {
          "enum": [
            "unknown",
            "observed_equivalent",
            "observed_different"
          ]
        },
        "suite_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      },
      "required": [
        "schema_version",
        "mutant_id",
        "parent_candidate_id",
        "source",
        "source_hash",
        "edit",
        "outcome",
        "test_ids",
        "equivalence_status",
        "suite_hash"
      ],
      "additionalProperties": false
    },
    "MutantObservation": {
      "type": "object",
      "properties": {
        "mutant_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "outcome": {
          "enum": [
            "invalid",
            "killed",
            "survived",
            "timeout",
            "duplicate"
          ]
        }
      },
      "required": [
        "mutant_id",
        "outcome"
      ],
      "additionalProperties": false
    },
    "AuditGap": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "gap_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "candidate_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "candidate_source_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "location": {
          "$ref": "#/$defs/Location"
        },
        "operator_family": {
          "type": "string"
        },
        "mutant_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          },
          "maxItems": 24
        },
        "observed_outcomes": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/MutantObservation"
          },
          "maxItems": 24
        },
        "requirement_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "suite_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "interpretation": {
          "const": "unresolved_test_gap"
        }
      },
      "required": [
        "schema_version",
        "gap_id",
        "candidate_id",
        "candidate_source_hash",
        "location",
        "operator_family",
        "mutant_ids",
        "observed_outcomes",
        "requirement_ids",
        "suite_hash",
        "interpretation"
      ],
      "additionalProperties": false
    },
    "Budget": {
      "type": "object",
      "properties": {
        "output_tokens": {
          "type": "integer",
          "minimum": 0,
          "maximum": 10000
        },
        "input_tokens": {
          "type": "integer",
          "minimum": 0,
          "maximum": 100000
        },
        "function_executions": {
          "type": "integer",
          "minimum": 0,
          "maximum": 3000
        },
        "elapsed_ms": {
          "type": "integer",
          "minimum": 0,
          "maximum": 900000
        },
        "learned_candidates": {
          "type": "integer",
          "minimum": 0,
          "maximum": 8
        },
        "search_candidates": {
          "type": "integer",
          "minimum": 0,
          "maximum": 48
        },
        "audit_mutants": {
          "type": "integer",
          "minimum": 0,
          "maximum": 48
        },
        "judge_decisions": {
          "type": "integer",
          "minimum": 0,
          "maximum": 8
        }
      },
      "required": [
        "output_tokens",
        "input_tokens",
        "function_executions",
        "elapsed_ms",
        "learned_candidates",
        "search_candidates",
        "audit_mutants",
        "judge_decisions"
      ],
      "additionalProperties": false
    },
    "ResourceUsage": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "output_tokens": {
          "type": "integer",
          "minimum": 0
        },
        "input_tokens": {
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
        "learned_candidates": {
          "type": "integer",
          "minimum": 0
        },
        "search_candidates": {
          "type": "integer",
          "minimum": 0
        },
        "audit_mutants": {
          "type": "integer",
          "minimum": 0
        },
        "judge_decisions": {
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
        "schema_version",
        "output_tokens",
        "input_tokens",
        "function_executions",
        "elapsed_ms",
        "learned_candidates",
        "search_candidates",
        "audit_mutants",
        "judge_decisions",
        "peak_memory_mb"
      ],
      "additionalProperties": false
    },
    "GenerateParams": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "generate"
        },
        "role": {
          "enum": [
            "fixer_a",
            "fixer_b"
          ]
        },
        "count": {
          "const": 1
        }
      },
      "required": [
        "kind",
        "role",
        "count"
      ],
      "additionalProperties": false
    },
    "CriticizeParams": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "criticize"
        },
        "mode": {
          "enum": [
            "discriminate",
            "challenge_agreement",
            "audit_gap",
            "validate_revision"
          ]
        }
      },
      "required": [
        "kind",
        "mode"
      ],
      "additionalProperties": false
    },
    "SearchParams": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "search"
        },
        "sites": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Location"
          },
          "maxItems": 6
        },
        "families": {
          "type": "array",
          "items": {
            "enum": [
              "comparison",
              "boundary_constant",
              "boolean_negation",
              "arithmetic",
              "variable_reference"
            ]
          },
          "maxItems": 5,
          "minItems": 1
        },
        "depth": {
          "enum": [
            1,
            2
          ]
        }
      },
      "required": [
        "kind",
        "sites",
        "families",
        "depth"
      ],
      "additionalProperties": false
    },
    "AuditParams": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "audit"
        },
        "max_mutants": {
          "type": "integer",
          "minimum": 1,
          "maximum": 24
        }
      },
      "required": [
        "kind",
        "max_mutants"
      ],
      "additionalProperties": false
    },
    "ReviseParams": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "revise"
        },
        "role": {
          "enum": [
            "fixer_a",
            "fixer_b"
          ]
        }
      },
      "required": [
        "kind",
        "role"
      ],
      "additionalProperties": false
    },
    "SelectParams": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "select"
        },
        "candidate_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        }
      },
      "required": [
        "kind",
        "candidate_id"
      ],
      "additionalProperties": false
    },
    "AbstainParams": {
      "type": "object",
      "properties": {
        "kind": {
          "const": "abstain"
        },
        "reason": {
          "type": "string"
        }
      },
      "required": [
        "kind",
        "reason"
      ],
      "additionalProperties": false
    },
    "ActionParams": {
      "oneOf": [
        {
          "$ref": "#/$defs/GenerateParams"
        },
        {
          "$ref": "#/$defs/CriticizeParams"
        },
        {
          "$ref": "#/$defs/SearchParams"
        },
        {
          "$ref": "#/$defs/AuditParams"
        },
        {
          "$ref": "#/$defs/ReviseParams"
        },
        {
          "$ref": "#/$defs/SelectParams"
        },
        {
          "$ref": "#/$defs/AbstainParams"
        }
      ]
    },
    "InvestigationAction": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "action_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "kind": {
          "enum": [
            "generate",
            "criticize",
            "search",
            "audit",
            "revise",
            "select",
            "abstain"
          ]
        },
        "target_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          },
          "maxItems": 8
        },
        "requirement_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
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
        "parameters": {
          "$ref": "#/$defs/ActionParams"
        },
        "requested_budget": {
          "$ref": "#/$defs/Budget"
        },
        "rationale": {
          "type": "string"
        }
      },
      "required": [
        "schema_version",
        "action_id",
        "kind",
        "target_ids",
        "requirement_ids",
        "evidence_ids",
        "parameters",
        "requested_budget",
        "rationale"
      ],
      "additionalProperties": false,
      "allOf": [
        {
          "if": {
            "properties": {
              "kind": {
                "const": "generate"
              }
            },
            "required": [
              "kind"
            ]
          },
          "then": {
            "properties": {
              "parameters": {
                "$ref": "#/$defs/GenerateParams"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "kind": {
                "const": "criticize"
              }
            },
            "required": [
              "kind"
            ]
          },
          "then": {
            "properties": {
              "parameters": {
                "$ref": "#/$defs/CriticizeParams"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "kind": {
                "const": "search"
              }
            },
            "required": [
              "kind"
            ]
          },
          "then": {
            "properties": {
              "parameters": {
                "$ref": "#/$defs/SearchParams"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "kind": {
                "const": "audit"
              }
            },
            "required": [
              "kind"
            ]
          },
          "then": {
            "properties": {
              "parameters": {
                "$ref": "#/$defs/AuditParams"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "kind": {
                "const": "revise"
              }
            },
            "required": [
              "kind"
            ]
          },
          "then": {
            "properties": {
              "parameters": {
                "$ref": "#/$defs/ReviseParams"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "kind": {
                "const": "select"
              }
            },
            "required": [
              "kind"
            ]
          },
          "then": {
            "properties": {
              "parameters": {
                "$ref": "#/$defs/SelectParams"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "kind": {
                "const": "abstain"
              }
            },
            "required": [
              "kind"
            ]
          },
          "then": {
            "properties": {
              "parameters": {
                "$ref": "#/$defs/AbstainParams"
              }
            }
          }
        }
      ]
    },
    "ActionOption": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "option_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "action": {
          "$ref": "#/$defs/InvestigationAction"
        },
        "prerequisite_summary": {
          "type": "string"
        }
      },
      "required": [
        "schema_version",
        "option_id",
        "action",
        "prerequisite_summary"
      ],
      "additionalProperties": false
    },
    "CandidateSummary": {
      "type": "object",
      "properties": {
        "candidate_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "origin": {
          "enum": [
            "original",
            "fixer_a",
            "fixer_b",
            "fixer_a_revision",
            "fixer_b_revision",
            "ast_search"
          ]
        },
        "eligibility": {
          "enum": [
            "pending",
            "eligible",
            "rejected"
          ]
        },
        "source_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "assumptions": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "hard_passes": {
          "type": "integer",
          "minimum": 0
        },
        "hard_failures": {
          "type": "integer",
          "minimum": 0
        }
      },
      "required": [
        "candidate_id",
        "origin",
        "eligibility",
        "source_hash",
        "assumptions",
        "hard_passes",
        "hard_failures"
      ],
      "additionalProperties": false
    },
    "StateSnapshot": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "state_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "problem_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "candidate_summaries": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/CandidateSummary"
          },
          "maxItems": 57
        },
        "behaviour_groups": {
          "type": "array",
          "items": {
            "type": "array",
            "items": {
              "type": "string",
              "minLength": 1,
              "maxLength": 120
            }
          }
        },
        "authoritative_counterexample_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "audit_gap_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "unresolved_requirement_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "previous_action_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "remaining_budget": {
          "$ref": "#/$defs/Budget"
        },
        "available_actions": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ActionOption"
          },
          "maxItems": 20,
          "minItems": 1
        },
        "incumbent_candidate_id": {
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
        "suite_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      },
      "required": [
        "schema_version",
        "state_id",
        "problem_id",
        "candidate_summaries",
        "behaviour_groups",
        "authoritative_counterexample_ids",
        "audit_gap_ids",
        "unresolved_requirement_ids",
        "previous_action_ids",
        "remaining_budget",
        "available_actions",
        "incumbent_candidate_id",
        "suite_hash"
      ],
      "additionalProperties": false
    },
    "JudgeDraft": {
      "type": "object",
      "properties": {
        "state_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "action_option_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "evidence_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "rationale": {
          "type": "string"
        }
      },
      "required": [
        "state_id",
        "action_option_id",
        "evidence_ids",
        "rationale"
      ],
      "additionalProperties": false
    },
    "RepairDraft": {
      "type": "object",
      "properties": {
        "source": {
          "type": "string"
        },
        "diagnosis": {
          "type": "string"
        },
        "assumptions": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "maxItems": 12
        },
        "requirement_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "suspected_sites": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Location"
          },
          "maxItems": 6
        },
        "suggested_families": {
          "type": "array",
          "items": {
            "type": "string"
          },
          "maxItems": 5
        }
      },
      "required": [
        "source",
        "diagnosis",
        "assumptions",
        "requirement_ids",
        "suspected_sites",
        "suggested_families"
      ],
      "additionalProperties": false
    },
    "CriticDraft": {
      "type": "object",
      "properties": {
        "mode": {
          "enum": [
            "discriminate",
            "challenge_agreement",
            "audit_gap",
            "validate_revision"
          ]
        },
        "requirement_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          }
        },
        "generator_spec": {
          "anyOf": [
            {
              "$ref": "#/$defs/GeneratorSpec"
            },
            {
              "type": "null"
            }
          ]
        },
        "concrete_inputs": {
          "anyOf": [
            {
              "type": "array",
              "items": {
                "type": "array",
                "items": {
                  "$ref": "#/$defs/JsonValue"
                },
                "maxItems": 6,
                "minItems": 1
              },
              "maxItems": 32,
              "minItems": 1
            },
            {
              "type": "null"
            }
          ]
        },
        "oracle_spec": {
          "$ref": "#/$defs/OracleSpec"
        },
        "target_candidate_ids": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 120
          },
          "maxItems": 8
        },
        "rationale": {
          "type": "string"
        }
      },
      "required": [
        "mode",
        "requirement_ids",
        "generator_spec",
        "concrete_inputs",
        "oracle_spec",
        "target_candidate_ids",
        "rationale"
      ],
      "additionalProperties": false
    },
    "ModelRequest": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "request_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "run_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "role": {
          "enum": [
            "raw",
            "fixer_a",
            "fixer_b",
            "critic",
            "judge",
            "general"
          ]
        },
        "purpose": {
          "enum": [
            "repair",
            "reconstruct",
            "revise",
            "test_proposal",
            "action_choice",
            "baseline"
          ]
        },
        "prompt": {
          "type": "string"
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        },
        "max_new_tokens": {
          "type": "integer",
          "minimum": 1,
          "maximum": 1024
        },
        "remaining_budget": {
          "$ref": "#/$defs/Budget"
        }
      },
      "required": [
        "schema_version",
        "request_id",
        "run_id",
        "role",
        "purpose",
        "prompt",
        "seed",
        "max_new_tokens",
        "remaining_budget"
      ],
      "additionalProperties": false
    },
    "ErrorBody": {
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
    },
    "ModelResponse": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "request_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "status": {
          "enum": [
            "ok",
            "error",
            "cancelled",
            "budget_exhausted"
          ]
        },
        "role": {
          "enum": [
            "raw",
            "fixer_a",
            "fixer_b",
            "critic",
            "judge",
            "general"
          ]
        },
        "text": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "model_revision_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "adapter_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        },
        "model_config_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "usage": {
          "$ref": "#/$defs/ResourceUsage"
        },
        "error": {
          "anyOf": [
            {
              "$ref": "#/$defs/ErrorBody"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "schema_version",
        "request_id",
        "status",
        "role",
        "text",
        "model_revision_hash",
        "adapter_hash",
        "model_config_hash",
        "usage",
        "error"
      ],
      "additionalProperties": false
    },
    "ValidationReceipt": {
      "type": "object",
      "properties": {
        "valid": {
          "type": "boolean"
        },
        "signature": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "error": {
          "anyOf": [
            {
              "$ref": "#/$defs/ErrorBody"
            },
            {
              "type": "null"
            }
          ]
        },
        "warnings": {
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      },
      "required": [
        "valid",
        "signature",
        "error",
        "warnings"
      ],
      "additionalProperties": false
    },
    "EvaluateParams": {
      "type": "object",
      "properties": {
        "operation": {
          "const": "evaluate"
        },
        "candidates": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/CandidateDraft"
          },
          "maxItems": 57
        },
        "tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TestCase"
          },
          "maxItems": 512
        },
        "stop_on_first_hard_failure": {
          "type": "boolean"
        }
      },
      "required": [
        "operation",
        "candidates",
        "tests",
        "stop_on_first_hard_failure"
      ],
      "additionalProperties": false
    },
    "ValidateParams": {
      "type": "object",
      "properties": {
        "operation": {
          "const": "validate"
        },
        "source": {
          "type": "string"
        },
        "tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TestCase"
          },
          "maxItems": 50
        }
      },
      "required": [
        "operation",
        "source",
        "tests"
      ],
      "additionalProperties": false
    },
    "SearchToolParams": {
      "type": "object",
      "properties": {
        "operation": {
          "const": "search"
        },
        "parents": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/CandidateDraft"
          },
          "maxItems": 3,
          "minItems": 1
        },
        "tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TestCase"
          },
          "maxItems": 512
        },
        "sites": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Location"
          },
          "maxItems": 6
        },
        "families": {
          "type": "array",
          "items": {
            "enum": [
              "comparison",
              "boundary_constant",
              "boolean_negation",
              "arithmetic",
              "variable_reference"
            ]
          },
          "maxItems": 5,
          "minItems": 1
        },
        "depth": {
          "enum": [
            1,
            2
          ]
        },
        "candidate_limit": {
          "type": "integer",
          "minimum": 1,
          "maximum": 48
        }
      },
      "required": [
        "operation",
        "parents",
        "tests",
        "sites",
        "families",
        "depth",
        "candidate_limit"
      ],
      "additionalProperties": false
    },
    "AuditToolParams": {
      "type": "object",
      "properties": {
        "operation": {
          "const": "audit"
        },
        "candidate": {
          "$ref": "#/$defs/CandidateDraft"
        },
        "tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TestCase"
          },
          "maxItems": 512
        },
        "max_mutants": {
          "type": "integer",
          "minimum": 1,
          "maximum": 24
        },
        "suite_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      },
      "required": [
        "operation",
        "candidate",
        "tests",
        "max_mutants",
        "suite_hash"
      ],
      "additionalProperties": false
    },
    "InvestigateParams": {
      "type": "object",
      "properties": {
        "operation": {
          "const": "investigate"
        },
        "proposal": {
          "$ref": "#/$defs/TestProposal"
        },
        "candidates": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/CandidateDraft"
          },
          "maxItems": 8
        },
        "existing_tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TestCase"
          },
          "maxItems": 512
        },
        "max_inputs": {
          "type": "integer",
          "minimum": 1,
          "maximum": 128
        }
      },
      "required": [
        "operation",
        "proposal",
        "candidates",
        "existing_tests",
        "max_inputs"
      ],
      "additionalProperties": false
    },
    "ToolParams": {
      "oneOf": [
        {
          "$ref": "#/$defs/EvaluateParams"
        },
        {
          "$ref": "#/$defs/ValidateParams"
        },
        {
          "$ref": "#/$defs/SearchToolParams"
        },
        {
          "$ref": "#/$defs/AuditToolParams"
        },
        {
          "$ref": "#/$defs/InvestigateParams"
        }
      ]
    },
    "ToolRequest": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "request_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "run_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "id_prefix": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "problem": {
          "$ref": "#/$defs/Problem"
        },
        "parameters": {
          "$ref": "#/$defs/ToolParams"
        },
        "remaining_budget": {
          "$ref": "#/$defs/Budget"
        }
      },
      "required": [
        "schema_version",
        "request_id",
        "run_id",
        "id_prefix",
        "problem",
        "parameters",
        "remaining_budget"
      ],
      "additionalProperties": false
    },
    "ToolResult": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "request_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "status": {
          "enum": [
            "ok",
            "invalid_input",
            "infrastructure_error",
            "budget_exhausted",
            "cancelled"
          ]
        },
        "validation": {
          "anyOf": [
            {
              "$ref": "#/$defs/ValidationReceipt"
            },
            {
              "type": "null"
            }
          ]
        },
        "candidates": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/CandidateDraft"
          },
          "maxItems": 48
        },
        "tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TestCase"
          },
          "maxItems": 128
        },
        "executions": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Execution"
          },
          "maxItems": 3000
        },
        "mutants": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ProbeMutant"
          },
          "maxItems": 24
        },
        "audit_gaps": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/AuditGap"
          },
          "maxItems": 24
        },
        "edit_sources": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/SourceArtifact"
          },
          "maxItems": 96
        },
        "usage": {
          "$ref": "#/$defs/ResourceUsage"
        },
        "warnings": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "error": {
          "anyOf": [
            {
              "$ref": "#/$defs/ErrorBody"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "schema_version",
        "request_id",
        "status",
        "validation",
        "candidates",
        "tests",
        "executions",
        "mutants",
        "audit_gaps",
        "edit_sources",
        "usage",
        "warnings",
        "error"
      ],
      "additionalProperties": false
    },
    "Decision": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
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
            "type": "string",
            "minLength": 1,
            "maxLength": 120
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
        },
        "suite_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        }
      },
      "required": [
        "schema_version",
        "selected_candidate_id",
        "verification_scope",
        "unresolved_requirements",
        "evidence_ids",
        "reason",
        "suite_hash"
      ],
      "additionalProperties": false
    },
    "RunResult": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
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
            "type": "string",
            "minLength": 1,
            "maxLength": 120
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
        "resource_usage": {
          "$ref": "#/$defs/ResourceUsage"
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
        "selected_candidate_id",
        "verification_scope",
        "unresolved_requirements",
        "evidence_ids",
        "resource_usage",
        "termination_reason"
      ],
      "additionalProperties": false
    },
    "RunSnapshot": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
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
            "validate",
            "reproduce",
            "generate",
            "evaluate",
            "investigate",
            "search",
            "audit",
            "revise",
            "judge",
            "finalize",
            "finished"
          ]
        },
        "problem": {
          "$ref": "#/$defs/Problem"
        },
        "candidates": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Candidate"
          },
          "maxItems": 57
        },
        "tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TestCase"
          },
          "maxItems": 512
        },
        "executions": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Execution"
          },
          "maxItems": 3000
        },
        "audit_gaps": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/AuditGap"
          }
        },
        "probe_mutants": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ProbeMutant"
          },
          "maxItems": 48
        },
        "edit_sources": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/SourceArtifact"
          },
          "maxItems": 96
        },
        "actions": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/InvestigationAction"
          },
          "maxItems": 8
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
        "resource_usage": {
          "$ref": "#/$defs/ResourceUsage"
        },
        "policy_mode": {
          "enum": [
            "learned",
            "fixed"
          ]
        },
        "model_manifest_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        },
        "profile_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "suite_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
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
        "problem",
        "candidates",
        "tests",
        "executions",
        "audit_gaps",
        "probe_mutants",
        "edit_sources",
        "actions",
        "decision",
        "resource_usage",
        "policy_mode",
        "model_manifest_hash",
        "profile_hash",
        "suite_hash",
        "termination_reason"
      ],
      "additionalProperties": false
    },
    "EpisodeBundle": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "run_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "problem": {
          "$ref": "#/$defs/Problem"
        },
        "candidates": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Candidate"
          },
          "maxItems": 57
        },
        "tests": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/TestCase"
          },
          "maxItems": 512
        },
        "executions": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Execution"
          },
          "maxItems": 3000
        },
        "audit_gaps": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/AuditGap"
          }
        },
        "probe_mutants": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/ProbeMutant"
          },
          "maxItems": 48
        },
        "edit_sources": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/SourceArtifact"
          },
          "maxItems": 96
        },
        "actions": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/InvestigationAction"
          },
          "maxItems": 8
        },
        "state": {
          "$ref": "#/$defs/StateSnapshot"
        },
        "model_manifest_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "profile_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      },
      "required": [
        "schema_version",
        "run_id",
        "problem",
        "candidates",
        "tests",
        "executions",
        "audit_gaps",
        "probe_mutants",
        "edit_sources",
        "actions",
        "state",
        "model_manifest_hash",
        "profile_hash"
      ],
      "additionalProperties": false
    },
    "RolloutRequest": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "request_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "episode": {
          "$ref": "#/$defs/EpisodeBundle"
        },
        "forced_option_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "seed": {
          "type": "integer",
          "minimum": 0
        },
        "continuation_policy": {
          "const": "fixed-v1"
        },
        "remaining_budget": {
          "$ref": "#/$defs/Budget"
        }
      },
      "required": [
        "schema_version",
        "request_id",
        "episode",
        "forced_option_id",
        "seed",
        "continuation_policy",
        "remaining_budget"
      ],
      "additionalProperties": false
    },
    "RolloutResult": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "request_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "final_result": {
          "$ref": "#/$defs/RunResult"
        },
        "selected_source": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "selected_source_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        },
        "episode": {
          "$ref": "#/$defs/EpisodeBundle"
        }
      },
      "required": [
        "schema_version",
        "request_id",
        "final_result",
        "selected_source",
        "selected_source_hash",
        "episode"
      ],
      "additionalProperties": false
    },
    "RunAccepted": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "run_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "status": {
          "const": "queued"
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
    "Error": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "error": {
          "$ref": "#/$defs/ErrorBody"
        }
      },
      "required": [
        "schema_version",
        "error"
      ],
      "additionalProperties": false
    },
    "Event": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
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
            "candidate_created",
            "execution_completed",
            "test_admitted",
            "test_rejected",
            "audit_gap_found",
            "action_selected",
            "action_refused",
            "candidate_invalidated",
            "budget_exhausted",
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
            "action_id": {
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
            "gap_id": {
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
            "action_id",
            "gap_id",
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
          "const": "stage2.v1"
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
          },
          "maxItems": 500
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
    "AdapterCard": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "role": {
          "enum": [
            "fixer_a",
            "fixer_b",
            "critic",
            "judge",
            "general"
          ]
        },
        "status": {
          "enum": [
            "not_started",
            "pilot_only",
            "completed"
          ]
        },
        "adapter_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        },
        "base_revision_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "tokenizer_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "quantization_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "topology_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "data_manifest_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        },
        "config_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "train_base_problems": {
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
        "evaluation_summary": {
          "type": "string"
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
        }
      },
      "required": [
        "schema_version",
        "role",
        "status",
        "adapter_hash",
        "base_revision_hash",
        "tokenizer_hash",
        "quantization_hash",
        "topology_hash",
        "data_manifest_hash",
        "config_hash",
        "train_base_problems",
        "train_records",
        "steps",
        "evaluation_summary",
        "loss_points"
      ],
      "additionalProperties": false
    },
    "TrainingReport": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "runtime_mode": {
          "enum": [
            "live",
            "fixture"
          ]
        },
        "cards": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/AdapterCard"
          },
          "maxItems": 5
        },
        "note": {
          "type": "string"
        }
      },
      "required": [
        "schema_version",
        "runtime_mode",
        "cards",
        "note"
      ],
      "additionalProperties": false
    },
    "Health": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "service": {
          "const": "codejury-stage2"
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
        "tools_ready": {
          "type": "boolean"
        },
        "trained_roles": {
          "type": "array",
          "items": {
            "enum": [
              "fixer_a",
              "fixer_b",
              "critic",
              "judge",
              "general"
            ]
          },
          "maxItems": 5
        },
        "full_stage2_ready": {
          "type": "boolean"
        },
        "default_policy": {
          "enum": [
            "learned",
            "fixed"
          ]
        },
        "contract_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      },
      "required": [
        "schema_version",
        "service",
        "runtime_mode",
        "model_ready",
        "tools_ready",
        "trained_roles",
        "full_stage2_ready",
        "default_policy",
        "contract_hash"
      ],
      "additionalProperties": false
    },
    "Example": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
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
        "schema_version",
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
          "const": "stage2.v1"
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
    "BenchmarkRow": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "method": {
          "type": "string"
        },
        "total_base_problems": {
          "type": "integer",
          "minimum": 0
        },
        "seed_count": {
          "type": "integer",
          "minimum": 0
        },
        "solved": {
          "type": "integer",
          "minimum": 0
        },
        "incorrect_accepted": {
          "type": "integer",
          "minimum": 0
        },
        "unresolved": {
          "type": "integer",
          "minimum": 0
        },
        "invalid_input": {
          "type": "integer",
          "minimum": 0
        },
        "infrastructure_error": {
          "type": "integer",
          "minimum": 0
        },
        "cancelled": {
          "type": "integer",
          "minimum": 0
        },
        "acceptance_precision": {
          "anyOf": [
            {
              "type": "number",
              "minimum": 0,
              "maximum": 1
            },
            {
              "type": "null"
            }
          ]
        },
        "mean_input_tokens": {
          "anyOf": [
            {
              "type": "number",
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
              "type": "number",
              "minimum": 0
            },
            {
              "type": "null"
            }
          ]
        },
        "mean_executions": {
          "anyOf": [
            {
              "type": "number",
              "minimum": 0
            },
            {
              "type": "null"
            }
          ]
        },
        "mean_elapsed_ms": {
          "anyOf": [
            {
              "type": "number",
              "minimum": 0
            },
            {
              "type": "null"
            }
          ]
        },
        "mean_peak_memory_mb": {
          "anyOf": [
            {
              "type": "number",
              "minimum": 0
            },
            {
              "type": "null"
            }
          ]
        },
        "inference_config_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "training_token_opportunity": {
          "type": "integer",
          "minimum": 0
        },
        "budget_comparison": {
          "enum": [
            "reference",
            "token_matched",
            "time_matched"
          ]
        },
        "note": {
          "type": "string"
        }
      },
      "required": [
        "schema_version",
        "method",
        "total_base_problems",
        "seed_count",
        "solved",
        "incorrect_accepted",
        "unresolved",
        "invalid_input",
        "infrastructure_error",
        "cancelled",
        "acceptance_precision",
        "mean_input_tokens",
        "mean_output_tokens",
        "mean_executions",
        "mean_elapsed_ms",
        "mean_peak_memory_mb",
        "inference_config_hash",
        "training_token_opportunity",
        "budget_comparison",
        "note"
      ],
      "additionalProperties": false
    },
    "BenchmarkReport": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "runtime_mode": {
          "enum": [
            "live",
            "fixture"
          ]
        },
        "status": {
          "enum": [
            "not_run",
            "partial",
            "completed"
          ]
        },
        "dataset_id": {
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
        "dataset_manifest_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        },
        "rows": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/BenchmarkRow"
          }
        },
        "paired_analysis_note": {
          "type": "string"
        },
        "limitations": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "research_outcome": {
          "enum": [
            "not_measured",
            "improved",
            "inconclusive",
            "worse"
          ]
        }
      },
      "required": [
        "schema_version",
        "runtime_mode",
        "status",
        "dataset_id",
        "dataset_manifest_hash",
        "rows",
        "paired_analysis_note",
        "limitations",
        "research_outcome"
      ],
      "additionalProperties": false
    },
    "ArtifactManifest": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "exchange_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "owner": {
          "enum": [
            "ajay",
            "sarvesh"
          ]
        },
        "kind": {
          "enum": [
            "training_corpus",
            "fixer_adapters",
            "critic_adapter",
            "judge_adapter",
            "general_adapter",
            "episodes",
            "judge_labels",
            "evaluation"
          ]
        },
        "base_revision_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "split": {
          "enum": [
            "train",
            "validation",
            "final_assessment",
            "none"
          ]
        },
        "files": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "relative_path": {
                "type": "string"
              },
              "sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$"
              },
              "size_bytes": {
                "type": "integer",
                "minimum": 0
              }
            },
            "required": [
              "relative_path",
              "sha256",
              "size_bytes"
            ],
            "additionalProperties": false
          }
        },
        "record_count": {
          "type": "integer",
          "minimum": 0
        },
        "base_problem_count": {
          "type": "integer",
          "minimum": 0
        },
        "contains_hidden_assessment": {
          "type": "boolean"
        },
        "note": {
          "type": "string"
        }
      },
      "required": [
        "schema_version",
        "exchange_id",
        "owner",
        "kind",
        "base_revision_hash",
        "split",
        "files",
        "record_count",
        "base_problem_count",
        "contains_hidden_assessment",
        "note"
      ],
      "additionalProperties": false
    },
    "MethodRequest": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "request_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "method": {
          "enum": [
            "B0",
            "B1",
            "B2",
            "B3",
            "B4",
            "CJ",
            "B-unweighted",
            "B-same-view",
            "Generic-Critic",
            "No-search",
            "No-gap-feedback",
            "Audit-at-end",
            "Fixed-Judge"
          ]
        },
        "input": {
          "$ref": "#/$defs/RunCreate"
        },
        "config_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        },
        "resource_caps": {
          "$ref": "#/$defs/Budget"
        }
      },
      "required": [
        "schema_version",
        "request_id",
        "method",
        "input",
        "config_hash",
        "resource_caps"
      ],
      "additionalProperties": false
    },
    "MethodResult": {
      "type": "object",
      "properties": {
        "schema_version": {
          "const": "stage2.v1"
        },
        "request_id": {
          "type": "string",
          "minLength": 1,
          "maxLength": 120
        },
        "method": {
          "enum": [
            "B0",
            "B1",
            "B2",
            "B3",
            "B4",
            "CJ",
            "B-unweighted",
            "B-same-view",
            "Generic-Critic",
            "No-search",
            "No-gap-feedback",
            "Audit-at-end",
            "Fixed-Judge"
          ]
        },
        "runtime_mode": {
          "enum": [
            "live",
            "fixture"
          ]
        },
        "final_result": {
          "$ref": "#/$defs/RunResult"
        },
        "selected_source": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ]
        },
        "selected_source_hash": {
          "anyOf": [
            {
              "type": "string",
              "pattern": "^[0-9a-f]{64}$"
            },
            {
              "type": "null"
            }
          ]
        },
        "candidate_pool": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/Candidate"
          },
          "maxItems": 57
        },
        "config_hash": {
          "type": "string",
          "pattern": "^[0-9a-f]{64}$"
        }
      },
      "required": [
        "schema_version",
        "request_id",
        "method",
        "runtime_mode",
        "final_result",
        "selected_source",
        "selected_source_hash",
        "candidate_pool",
        "config_hash"
      ],
      "additionalProperties": false
    }
  }
}
```

Read CodeJury-Stage2-Training-and-Evaluation.md before learning or final measurement jobs.

## B. Environment, ownership and target layout

Own backend/src/codejury/stage2_tools/{domains,codec,oracles,runner,search,auditor,investigation,factory,critic_training,general_training,evaluation,cli}/**, backend/tests/stage2_tools/**, backend/config/stage2_tools/**, backend/data/stage2_tools/**, backend/tools/stage2_tools/**, backend/docs/stage2_tools/** and web/**. Extend original Stage1 through wrappers inside your namespace while preserving its original modules. Ajay applies package-lock/API wiring changes at integration; submit dependency proposals inside your config directory.

CODEJURY_STAGE2_RUNNER_IMAGE identifies the actual ARM64 image; CODEJURY_STAGE2_EXCHANGE points to the ignored transfer directory; CODEJURY_STAGE2_EVAL_DIR stores private assessment data/results; CODEJURY_STAGE2_MODEL_MANIFEST supplies compatible local model metadata for standalone trainers. No paid API is required. CPU development can use a compatible machine; MLX training uses the project Apple Silicon Mac through one exclusive compute lease. Keep the original static HTML/CSS/JS UI, Node built-in tests and Python standard-library mock.

## S2.01 · Audit original tools/UI, seal final pools and adopt contract · P0 · depends: none

**PROMPT**

Goal: establish actual reusable capabilities and a protected research boundary.

Files you may touch: backend/docs/stage2_tools/audit.md, backend/tools/stage2_tools/audit.py, backend/data/stage2_tools/manifests/**, web/docs/stage2/audit.md. Additional task-owned entrypoints: backend/src/codejury/stage2_tools/{eval_cli,contract_cli}.py.

Read actual original Stage1 code/reports. Inventory runner, properties, UI, mock routes, installed versions, image/model/data provenance and missing foundation work. Coordinate the single E0 seed with Ajay; contract/ports/constraints are read-only afterwards. An earlier guide does not prove implementation. Missing isolation must be completed before any candidate executes; no host fallback.

Inventory training/validation/assessment IDs and previously inspected data. Stage1 assessment used in development becomes development data. Seal a new final holdout, disjoint by base problem, algorithm family and near-duplicate cluster, before Stage2 learning. Target at least200 distinct base problems if the curated corpus supports it; report smaller actual counts as limited evidence. Include natural bugs, synthetic variants and a held-out mutation-family subset. Do not count variants or inference seeds as independent problems.

QuixBugs is a secondary external benchmark; optional EvalPlus tasks need an explicitly documented repair adaptation, verified license and supported helpers/types. Never train on reserved final tasks. Define visible tests/approved properties from the contract before repair. You retain private final reference/test bytes; Ajay receives public IDs, hashes and aggregate outcomes rather than hidden data.

**VERIFY**

From backend/: `python tools/stage2_tools/audit.py --out artifacts/stage2_tools/audit.json`; `python -m codejury.stage2_tools.eval_cli validate-splits --manifest data/stage2_tools/manifests/stage2.json`; `python -m codejury.stage2_tools.contract_cli check --contracts ../contracts`. Implement these interfaces. Record actual counts, overlap, excluded cases, licenses and contract/dependency hashes. Do not pad the dataset to meet a target.

## S2.02 · Recursive domains, JSON codec and reviewed oracle gate · P0 · depends: S2.01

**PROMPT**

Goal: support the final architecture's values and helpers without weakening acceptance rules.

Files you may touch: backend/src/codejury/stage2_tools/{domains,codec,oracles}/**, backend/tests/stage2_tools/test_domains.py, backend/tests/stage2_tools/test_oracles.py, backend/config/stage2_tools/registry.yaml.

Implement the exact ValueDomain/json.v1 contract and type-sensitive recursive equality. Separate bool from int, preserve null, count Unicode codepoints, bound lists/dictionaries/depth/total nodes and reject unsafe integers, floats/NaN, implicit tuple/set conversion and arbitrary objects. Validate min/max, alphabet, union alternatives, required keys, argument names/types and helper signatures. Parse source statically only on the host. Approved import aliases must resolve to the fixed allowlist; no arbitrary dependencies or guessed helper behaviour. Inspect actual Python3.11 AST/library APIs and purity before enabling each allowlisted symbol.

Implement the five property templates and two metamorphic relations specified in the shared contract. Maintain signature/domain compatibility, reviewed requirement justification and version hashes. Sorting checks order AND multiplicity; uniqueness checks exact first-occurrence order; sum includes negatives; string reversal uses the specified codepoint semantics; occurrence count returns the exact integer. Metamorphic tests use two fresh executions and are not sufficient correctness evidence by themselves.

Only user/reviewed-contract approval can authorize executable expectations. Reject contradictory supplied literals/approved properties at intake. Model literals and inferred relations remain proposed/observed. Reference agreement during training is empirical validation, not authority to promote a runtime model expectation.

**VERIFY**

`python -m pytest tests/stage2_tools/test_domains.py tests/stage2_tools/test_oracles.py -q`. Cover nested bool/int/null, Unicode length, duplicates/negative values, missing required dict keys, invalid alphabets/depth, unknown helper/import, changed signature, tuple/float output, conflicting expectations, proposed literal handling, valid/invalid relations and oracle-version caching. Paste real output; arbitrary prose is not automatically verified.

## S2.03 · Expanded isolated execution, trace and cancellation · P0 · depends: S2.02

**PROMPT**

Goal: execute bundles and relations safely and return factual evidence with correct costs.

Files you may touch: backend/src/codejury/stage2_tools/runner/**, backend/tools/stage2_tools/runner/**, backend/config/stage2_tools/runner.yaml, backend/tests/stage2_tools/test_runner.py, backend/docs/stage2_tools/runner.md. Additional task-owned entrypoints: backend/src/codejury/stage2_tools/runner_cli.py.

Wrap the original runner without cross-editing it during parallel work. Verify real Colima/Docker flags, config and effective mounts. Use a dedicated ARM64 VM with personal-directory shares disabled, network disabled, non-root UID, read-only root, dropped capabilities, bounded tmpfs/process/memory/output and external watchdog. Never mount home, repository, Docker socket, credentials or model directories into candidate jobs. Static checks supplement this isolation.

Compile/import/execute candidate helpers, imports and assertions only inside the sandbox. Trusted host oracle/codec code checks returned data; candidate code cannot assign pass labels. Use fixed argv and private IPC/files, never source interpolation in a shell. Copy inputs and instantiate fresh function state per invocation; detect mutation with before/after hashes. A relation executes two fresh calls and counts both. Timeouts use the declared2s policy; infrastructure loss is not a semantic bug.

Trace selected candidate-source locations/locals with strict count/size limits, codec sanitization, truncation flag and content hash. Do not return host paths or unbounded traceback content. Watchdog/cancel kills the entire job process tree without orphan containers. Report all actual call/probe/shrink/replay usage as deltas; let core calculate whole-episode walltime.

**VERIFY**

`python -m codejury.stage2_tools.runner_cli self-test --config config/stage2_tools/runner.yaml --out artifacts/stage2_tools/runner`; `python -m pytest tests/stage2_tools/test_runner.py -q`. Actual checks: helper/allowlist execution, nested JSON, relation cost2, input mutation, output/trace overflow, infinite loop/process tree, network/mount denial, missing image, cancel and infrastructure classification. Save inspected digest/mount evidence; pending native tests remain pending.

## S2.04 · Evidence-directed single/two-edit AST repair · P0 · depends: S2.03

**PROMPT**

Goal: systematically explore nearby repairs while retaining exact lineage and budgets.

Files you may touch: backend/src/codejury/stage2_tools/search/**, backend/config/stage2_tools/search.yaml, backend/tests/stage2_tools/test_search.py, backend/docs/stage2_tools/search.md. Additional task-owned entrypoints: backend/src/codejury/stage2_tools/search_cli.py.

Inspect installed ast NodeTransformer, copy_location, fix_missing_locations and unparse; parse success does not establish compilability. Deep-copy a parent per edit. Parse/transform on the host; compile/execute only in the sandbox. Implement comparison replacements, integer boundary +/-1 excluding bool/unsafe values, Boolean condition negation, integer arithmetic replacements and compatible in-scope variable references. Exclude float-producing division/exponentiation, unknown/global names, changed signatures/dependencies and test-specific branches. Scope/type heuristics only prioritize candidates; runtime validation decides outcomes.

Use up to3 parents: original plus promising failed A/B candidates. Interleave parents and rank sites with actual failing evidence or model hints, never claim a hint proves causality. Single edits first; a depth2 beam of width4 uses partial hard-test coverage for exploration. Maximum48 actually executed unique search candidates per episode and192 preflight proposals; reserve final-qualification resources. Known failing checks first, then full common supplied/property suite. Partial success never qualifies.

Each Edit has immediate-parent source hash/location and result hash. Return intermediate SourceArtifacts for two-edit reconstruction; core stores them immutably. A final descendant links the committed root candidate ID and ordered edit chain. Deduplicate exact/normalized source and preserve private proposal provenance; do not create independent jury opinions from descendants. Reject unknown IDs/hash chains/signatures before execution.

**VERIFY**

`python -m pytest tests/stage2_tools/test_search.py -q`; `python -m codejury.stage2_tools.search_cli self-test --config config/stage2_tools/search.yaml --out artifacts/stage2_tools/search`. Include a comparator repair, a genuine two-edit case, incompatible variable rejection, regression after partial success and wrong algorithm outside operators. Check fresh parent copies, exact intermediate hashes/locations, signature/import guards,48/192 caps and cancel. Controlled cases validate the engine; later heldout results measure usefulness.

## S2.05 · Mutation auditor and requirement-linked gaps · P0 · depends: S2.04

**PROMPT**

Goal: expose observable test blind spots without misclassifying survivors as bugs.

Files you may touch: backend/src/codejury/stage2_tools/auditor/**, backend/config/stage2_tools/auditor.yaml, backend/tests/stage2_tools/test_auditor.py, backend/docs/stage2_tools/auditor.md. Additional task-owned entrypoints: backend/src/codejury/stage2_tools/audit_cli.py.

Reuse transformation operators with a distinct probe purpose. Audit a current eligible version, at most24 probes/version and48/episode; cap preflight proposals at96/action. Preserve mutant source/hash/edit/parent/suite. Classify invalid, killed, survived, timeout and duplicate separately. Killed requires an authoritative rejection; observations cannot kill. Unknown equivalence is default; observed equivalence on sampled behaviour is not a proof. A survivor alone does not accuse the parent.

Return ProbeMutants/AuditGaps, no selectable CandidateDrafts. Promoting a potentially useful probe edit requires explicit search registration and full acceptance. Group survivor gaps by exact source/suite/location/family; attach reviewed requirement mappings only when justified, otherwise leave IDs empty with a warning. Coverage shows executed locations, not semantic requirement correctness. Revisions or new tests make old gaps stale. No100% kill threshold or automatic equivalent-mutant solver is required.

Budget all probe executions and hash-keyed cache reuse. Critic follows a gap with a domain-valid proposed experiment; oracle admission establishes any actual failure. Auditor effectiveness is later measured by new valid failures and selected-patch correctness, not kill count.

**VERIFY**

`python -m pytest tests/stage2_tools/test_auditor.py -q`; `python -m codejury.stage2_tools.audit_cli self-test --config config/stage2_tools/auditor.yaml --out artifacts/stage2_tools/audit`. Cases: weak boundary tests permit a survivor and approved followup distinguishes it; equivalent/sample-equivalent survivor is not an accusation; invalid/duplicate/timeout separate; proposed oracle cannot kill; stale gap refused;24/48 caps. Record actual sandbox evidence.

## S2.06 · Oracle-gated investigation/shrinking and complete ToolPort · P0 · depends: S2.02, S2.03, S2.04, S2.05

**PROMPT**

Goal: expose all five tool operations through one independently testable interface.

Files you may touch: backend/src/codejury/stage2_tools/{investigation,factory,port,contract_cli}/**, backend/tests/stage2_tools/test_tool_port.py, backend/tests/stage2_tools/test_investigation.py. Additional task-owned entrypoints: backend/src/codejury/stage2_tools/{factory,contract_cli,cli}.py.

Implement make_tool_port and validate requests/results against the canonical definitions. Request IDs and delegated prefixes must match; returned evidence/hash chains/reference IDs must be valid. Operation-specific arrays remain empty when no such content exists. Count real deltas once, including related calls and shrinking. Budget/cancel returns only completed partial facts; no unperformed execution rows. Tests require no Ajay implementation.

Investigate accepts EXACTLY ONE generator_spec or concrete_inputs. Validate requirement/target IDs, domains, oracle status and family compatibility. Registered families cover supported edges, Unicode, dictionaries and audit sites; an unsupported family is rejected or observation-only, not guessed. A/B disagreement is an observation until approved contract semantics distinguish the winner.

Inspect current public Hypothesis strategies/find/settings/replay APIs; no undocumented internal shrinker API. Predicates execute through sandbox IPC, never import/call candidates on the host. Shrink within domain, independently replay minimal failure, account for every attempt, then admit an authorized test. At most128 input proposals/action and512 registered tests/run; all within remaining execution budget. Deduplicate exact input/oracle-version tests while retaining provenance privately. Model literal agreement with a reference never auto-approves it at runtime.

**VERIFY**

`python -m pytest tests/stage2_tools/test_tool_port.py tests/stage2_tools/test_investigation.py -q`; `python -m codejury.stage2_tools.cli self-test --config config/stage2_tools/runtime.yaml --out artifacts/stage2_tools/tool-port`. Cover all operation schemas, wrong IDs/prefixes/oracles, observation-only disagreement, replayed domain-valid minimal failures, shrink budget/cancel, stale gaps and truthful deterministic fallback. Publish E1/E2 tool-factory handoff; live factory cannot import fake dependencies.

## S2.07 · Execution-filtered Critic data and no-objection cases · P0 · depends: S2.06

**PROMPT**

Goal: train useful experiment design without encouraging false accusations.

Files you may touch: backend/src/codejury/stage2_tools/critic_training/data/**, backend/data/stage2_tools/critic/**, backend/config/stage2_tools/training/critic.yaml, backend/tests/stage2_tools/test_critic_data.py, backend/docs/stage2_tools/critic-data.md. Additional task-owned entrypoints: backend/src/codejury/stage2_tools/critic_cli.py.

Consume E2 real TRAINING A/B episodes and compatible manifests, validating paths/hashes/splits. Fixtures can test the pipeline before arrival but are not real student failures. Collect disagreement, shared incorrect agreement, near-correct revisions, mutation gaps and correct candidates. Reviewed sources and reference-backed TRAINING assessment validate labels offline. Optional raw/local-teacher drafts still require execution filtering.

Critic prompt contains runtime contracts/candidates/evidence/gaps only. Hidden TRAINING targets remain label-side. Teach four modes, valid bounded generator/concrete proposals, invalid-test rejection and honest no-useful-objection. The no-objection case uses a valid general observation proposal with a rationale that no authorized failure was found; never emit illegal null/null proposal sources or claim proof. Model-invented literal expectations stay proposed even when empirically correct.

Start with at least25% correct-candidate cases and10% invalid/conflicting-proposal cases, tune on validation. These are mix targets, not available counts. Preserve natural/synthetic/base-family provenance. Measure valid counterexample yield and false hard rejection, not raw tests or mutation kills. Only original train pool is expanded; no final assessment leak.

**VERIFY**

`python -m codejury.stage2_tools.critic_cli collect --config config/stage2_tools/training/critic.yaml`; `python -m codejury.stage2_tools.critic_cli validate --config config/stage2_tools/training/critic.yaml`; `python -m pytest tests/stage2_tools/test_critic_data.py -q`. Record real accepted/rejected/domain/no-objection/correct-candidate counts, hidden-prompt guard and fixture isolation. Emit actual training manifest.

## S2.08 · Train/reload Critic and deliver E3 artifact · P0 · depends: S2.07

**PROMPT**

Goal: deliver a genuinely learned Critic compatible with the shared model registry.

Files you may touch: backend/src/codejury/stage2_tools/critic_training/**, backend/config/stage2_tools/training/critic.yaml, backend/tests/stage2_tools/test_critic_training.py, backend/docs/stage2_tools/critic-card.md. Additional task-owned entrypoints: backend/src/codejury/stage2_tools/critic_cli.py.

Standalone MLX training verifies the common base/tokenizer/quantization/topology. Inspect actual JSONL chat format, masking, module targets and LoRA save/reload APIs. Pilot10–20 steps, save/reload, then full validation-controlled SFT. Start rank8/microbatch1; profile memory. Schedule the exclusive Mac lease, releasing on failure; no live worker and trainer resident together. Standalone training need not import Ajay's runtime, but produced keys/topology must pass E3 registry compatibility.

Select checkpoints using format/domain validity, authorized counterexample yield, false rejection of correct candidates, audit-gap challenge benefit and cost. Loss alone is insufficient. Private validation references stay outside inference/export prompts. Freeze Card/checkpoint/data/config hashes and real logs; completed needs genuine training, reload and measured role evaluation. Export critic_adapter manifest/weight bytes outside Git. Incompatibility cannot be solved by renaming hashes or substituting raw prompts.

**VERIFY**

`python -m codejury.stage2_tools.critic_cli train --config config/stage2_tools/training/critic.yaml`; `python -m codejury.stage2_tools.critic_cli evaluate --config config/stage2_tools/training/critic.yaml`; `python -m pytest tests/stage2_tools/test_critic_training.py -q`; `python -m codejury.stage2_tools.critic_cli export --out artifacts/stage2-exchange/sarvesh/critic`. Record actual steps/loss/reload/validity/false-rejection/hashes and E3 core load/switch. Pending hardware tests are not passed.

## S2.09 · Benchmark harness, baseline contracts and statistical analysis · P0 · depends: S2.01, S2.06, S2.08

**PROMPT**

Goal: prepare a sealed, fair evaluation harness before the final general baseline is trained.

Files you may touch: backend/src/codejury/stage2_tools/evaluation/**, backend/config/stage2_tools/evaluation.yaml, backend/tests/stage2_tools/test_evaluation.py, backend/data/stage2_tools/manifests/**, backend/docs/stage2_tools/results/**. Additional task-owned entrypoints: backend/src/codejury/stage2_tools/eval_cli.py.

Implement the harness against Ajay's documented runtime interface or fixture ports. This task runs CPU fixture checks/validation experiments only; FINAL assessment waits for S2.10 and S2.12, avoiding a circular dependency. Final hidden tests are applied once after selected source/hash commitment, with no repair feedback. Preflight references and unsupported input exclusions before comparing methods; report original population and eligible subset. During runs retain infrastructure/cancel/invalid outcomes in denominator.

Inspect actual QuixBugs/EvalPlus APIs/licenses. Document helper/type/bug adaptations. Never execute EvalPlus's host trusted_exec on candidate code; translate compatible test data/harness into the project sandbox. Final evaluation-only tasks never enter training/teacher generation. All methods receive identical visible contract/domain/tests/dependencies/approval.

Implement B0 raw one-shot, B1 A+execution feedback, B2 A sampling/revision, B3 single trained general agent with identical test/search/audit tools and comparable aggregate training opportunities, B4 four prompted roles/fixed, CJ four trained roles/learned. General baseline may choose its own actions/budget allocation. Token-matched and time-matched trials separate; count prefill/input/output/retry and non-LLM execution costs. Training/checkpoint tuning uses validation. Run all specified ablations and actual3-seed replication only after every model/config freezes.

Metrics: selected-patch correctness over all tasks, acceptance precision/coverage/false acceptance, unresolved, candidate-pool/conditional selection success, B rescue/joint failure, Critic authorized yield/false rejection, gaps leading to new failures, Judge versus fixed outcome, costs/memory. Secondary pool assessment happens after all final commitments, never oracle-best selection. Public rows use the first fixed seed; private per-problem tables retain all seeds. Clustered paired bootstrap95% CI with10,000 resamples as initial analysis setting, verified implementation; repeats/seeds are nested within base problems, not independent tasks. Report wins/losses, natural/synthetic/held-out-family subsets and inconclusive results when uncertainty includes no gain.

**VERIFY**

`python -m pytest tests/stage2_tools/test_evaluation.py -q`; `python -m codejury.stage2_tools.eval_cli smoke --config config/stage2_tools/evaluation.yaml --mode fixture --out artifacts/stage2_tools/harness-check`. Implement smoke mode explicitly labelled fixture; validation runs use a separate validation config. Verify selected-versus-best distinction, no hidden feedback, identical visible inputs/tool parity, all costs/denominators, deterministic clustered analysis, null/0 handling and worse/inconclusive reporting. Do not run final assessment yet.

## S2.10 · Train general single-agent comparator and audit opportunity parity · P0 · depends: S2.08, S2.09

**PROMPT**

Goal: build the strong baseline needed to distinguish council benefit from extra tools/data.

Files you may touch: backend/src/codejury/stage2_tools/general_training/**, backend/config/stage2_tools/training/general.yaml, backend/tests/stage2_tools/test_general_training.py, backend/docs/stage2_tools/general-card.md. Additional task-owned entrypoints: backend/src/codejury/stage2_tools/general_cli.py.

After A/B/Critic/Judge training sources freeze, merge authorized TRAINING records into one adapter distribution with explicit repair/test/action task tags. Preserve split/target/view provenance. Same base/tokenizer/quantization/topology; aggregate example and token opportunity comparable to all four role datasets. Record actual training tokens, repetitions and optimizer steps, not simply dataset line count or four-times epochs. General inference has the same tool/action APIs and approved evidence and can allocate its own budget; no forced disadvantage from CodeJury's role sequence.

Inspect current MLX format/masking/interfaces; standalone pilot/full training/save/reload under compute lease. Select checkpoint on validation correctness, task format/action validity and cost. Freeze Card/manifest, register general in Ajay's worker and prove native tool use. General is a fifth comparator adapter, not another jury role. Missing fair B3 means research comparison incomplete, not permission to replace it with raw one-shot while claiming parity. Do not tune any model after final results.

**VERIFY**

`python -m codejury.stage2_tools.general_cli validate --config config/stage2_tools/training/general.yaml`; `python -m codejury.stage2_tools.general_cli train --config config/stage2_tools/training/general.yaml`; `python -m codejury.stage2_tools.general_cli evaluate --config config/stage2_tools/training/general.yaml`; `python -m pytest tests/stage2_tools/test_general_training.py -q`. Record aggregate opportunity audit, genuine reload/card and E4 B3 tool-access smoke. Final comparison remains S2.12.

## S2.11 · Full UI/mock: provenance, audit gaps, actions and reports · P0 · depends: S2.06, S2.09, S2.10

**PROMPT**

Goal: present the full evidence system through independently verifiable UI/mock code.

Files you may touch: web/**; backend/docs/stage2_tools/ui-contract.md.

Preserve original static UI. Migrate client/mock to stage2.v1, all routes/errors/cursors/cancel, new typed domains/helpers/requirements/dependency consent/profile/policy. Python standard-library mock never executes input or trains and always advertises fixture mode/banner. Client health-version/hash guard, localhost-only API override, same-origin after merge,1s polling, terminal/navigation stop and stale-request guards. Verify installed Node/Python/browser APIs; no new framework needed.

Show A/B independent initial-view labels and actual role cards; revision/search parent/hash/edit lineage; authoritative/proposed test matrix; stale qualification/invalidation; audit gap bound to source/suite and unknown equivalence. Mutants are probes, never selectable votes. Show learned Judge action/refusal/fixed fallback and remaining resources, not invented confidence/progress. Handle up to57 candidates plus expandable probe details. Selected download comes from backend decision and exact immutable source/hash; source/error textContent only, no innerHTML/eval/new Function.

Property/template approval happens before a live run, with requirement wording visible. Benchmarks never get human oracle rescue. Reports show real loss/counts, general comparator distinction, exact solved/total/costs/paired notes, not_run/partial/completed and improved/inconclusive/worse. Missing metrics null, zero remains0. Fixture report never mixed into live chart. Cancel/infra/legacy409/version422 and invalidated success clear stale display/download. UI prototypes may start earlier once seed exists; task dependencies are final correctness gates.

**VERIFY**

From repo root: `python3 web/tools/check_stage2_fixtures.py --contracts contracts`; `node --test web/tests/stage2_*.test.mjs`; `python3 web/tools/stage2_mock.py --port 8001 --scenario audit-gap`; `python3 web/tools/stage2_browser_check.py --base-url http://127.0.0.1:8080`. Implement tools. Browser automation only through verified installed public API; otherwise record actual manual checks, not a generated checklist marked passed. Cover stale invalidation, probe/parent lineage, refusal/fallback, exact hash download, nested JSON, cancel/budget, null/0 metrics and inert markup. Independent checks do not need native inference.

## S2.12 · Final real benchmark, merged acceptance and handoff · P0 · depends: S2.11

**PROMPT**

Goal: complete the full research and live evidence only after all models/configurations are frozen.

Files you may touch: backend/docs/stage2_tools/{handoff,release,limitations}.md, backend/tools/stage2_tools/handoff_check.py, backend/config/stage2_tools/evaluation.yaml, web/docs/stage2/**; ignored backend/artifacts/stage2_tools/evaluation/**. Additional task-owned entrypoints: backend/src/codejury/stage2_tools/eval_cli.py.

At E4 freeze A/B/Critic/Judge/general manifests, hardware/profile/continuation/baselines/ablation parameters and the sealed final dataset. Run the real final benchmark and analysis, no hidden-feedback retries. Include every declared method/ablation/seed, final selected hashes and exact costs. Inspecting results then changing configuration consumes the set as development data; a new final claim requires fresh untouched assessment. Retain failed/inconclusive trials. Public BenchmarkReport contains aggregates, never hidden sources/tests or secret paths.

Record common seed/own commit, versions, tool/image/allowlist hashes, Critic/general data/config/cards, all operator/auditor/domain tests and actual paired confidence/cost results. Validate artifact paths/hashes/split; no weights or hidden corpus in Git. Help Ajay run actual merged Mac browser/system acceptance with learned Judge and all four real trained roles. Separate module checks from pending joint checks; a fixed-only release is not final learned architecture.

Prepare multiple disclosed live demos for A/B repair, search rescue, gap-guided challenge, learned choice/refusal, immutable patch/report and unresolved/cancel. Do not force every action into one easy task. Actual research_outcome must match paired evidence and false acceptance; component completion alone cannot certify superiority. No publication/push implied.

**VERIFY**

From backend/: `python -m codejury.stage2_tools.eval_cli run --config config/stage2_tools/evaluation.yaml --split final_assessment --out artifacts/stage2_tools/evaluation`; `python -m codejury.stage2_tools.eval_cli analyze --results artifacts/stage2_tools/evaluation --out artifacts/stage2_tools/benchmark-report.json`. From repo root: `python backend/tools/stage2_tools/handoff_check.py --contracts contracts --out backend/docs/stage2_tools/handoff.md`; `git diff --name-only <actual-common-stage2-seed>...stage2/sarvesh-tools`. Run both owner CPU suites once plus actual native/sandbox/browser checks. Owner diff only stage2_tools+web paths; record true missing gates.

## D. Dependency build order

| Checkpoint | Tasks | Evidence |
|---|---|---|
| E0/E1 |S2.01–S2.03|Audit, protected datasets, domains/oracles/runner|
| E1/E2 |S2.04–S2.07|Search/audit/investigation/ToolPort, real Critic data|
| E3 |S2.08–S2.09|Trained Critic, validated research harness|
| E4 |S2.10–S2.12|Fair general baseline, full UI, final real evaluation|

Independent prototypes can proceed once their contract exists; final acceptance respects the listed dependencies. No invented deadline. Real label/evaluation jobs wait for actual exchange hashes.

## E. Final acceptance

Mark✅ only with evidence: common contract/owner paths; recursive codec/helpers/allowlist; real isolated traces/watchdog; bounded five-family single/two-edit search; audit without false certainty; replayed authorized counterexamples; exact ToolPort provenance/usage; real trained/reloaded Critic; protected no-feedback holdout; fair trained general baseline; full baselines/ablations/3-seed clustered analysis; truthful mock/UI/live reports; merged Mac workflow; honest research outcome. False rejections/incorrect acceptance remain reported.
