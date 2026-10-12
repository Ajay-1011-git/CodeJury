# CodeJury — Ajay's Complete Stage 2 Build Instructions

**Module:** native model runtime, FixersA/B, Judge learning, investigation controller, durable API and integration. **Partner:** Sarvesh builds stage2_tools plus web, including Critic, search/auditor/oracles and research harness. This is a balanced engineering split, not the old easier-UI assignment.

**Grounding:** reference/CodeJury-Final-Architecture.md v2.0 and ORIGINAL Stage1 stage1.v1. The optional Stage1 quality upgrade was not implemented. Do not require or import it. The shared Stage2 schema/ports below make the outlined final architecture concrete.

**Alignment:** final architecture wins on scientific/runtime principles; this document defines exact Stage2 interfaces and limits. Report an actual unresolved architecture conflict before redesigning. You can implement/CPU-test your module with fixture ToolPort independently. Real episodes/Judge labels/final inference require the stated artifact and integration checkpoints; don't fabricate them to remove a dependency.

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

## B. Environment, files and prerequisites

Keep existing model/runner/artefact paths from Stage1. New config belongs backend/config/stage2_core/: runtime.yaml, profiles/mac-standard-v1.yaml, training/{fixer_a,fixer_b,judge}.yaml, collection.yaml, constraints-proposal.txt. CODEJURY_STAGE2_MODEL_MANIFEST points to real locally verified adapter registry; CODEJURY_STAGE2_ARTIFACTS points to ignored run/training artifacts; CODEJURY_STAGE2_EXCHANGE is ignored exchange root. No secret API key required. Config files contain actual local paths through env/config, never hardcoded /Users/Ajay or fake remote.

Package code: stage2_core/{factory,model_worker,views,training,data,controller,ledger,api,rollouts,baselines,cli}. Use existing Stage1 via readonly adapters, not copies with silently changed semantics. Own tests/stage2_core/, tools/stage2_core/, docs/stage2_core/,data/stage2_core/. Original API/package lock only custodian at E checkpoints. Shared constraints must be seeded and verified before owner-specific dependency installation. All project commands below must be implemented or wrapped around audited existing entrypoints.

## A2.01 · Audit original Stage1 and seed Stage2 · P0 · depends: none

**PROMPT**

Goal: establish the true baseline and one merge-safe common contract before parallel changes.

Files you may touch: backend/docs/stage2_core/audit.md, backend/tools/stage2_core/audit.py; one-time custodian seed paths from shared contract and integration/stage2/README.md. Additional task-owned entrypoints: backend/src/codejury/stage2_core/contract_check.py.

Inspect Git status, actual original build progress, folder/entrypoint layout, FastAPI/Pydantic/MLX/Python versions, Mac architecture/memory, runner image/VM mounts, model/checkpoint/tokenizer hashes, data splits and real Stage1 reports. Verify what is missing; complete missing M1–M5 prerequisites through original owner/integrator before dependent real jobs. No claim that original guide means implemented. Capture current repair failures in diagnostic buckets: format/truncation, wrong algorithm, local expression, weak test acceptance, mutation/effects, timeout/infra and adapter regression. Preserve current checkpoint/profile/baseline outcome before changing anything.

With both owners' code committed, seed stage2 schema/fixtures/ports/reference/legacy copies as specified; review exact writes and no unrelated resets. Create/commit common constraints from actual inspected compatible dependencies, package discovery and bootstrap stub; record common seed SHA. Sarvesh's schema/hash must match. No future partner code copied now. If unexpected stage1.v1.1 implementation is found despite the user report, inventory it and preserve it, but Stage2 remains separate; no blind destructive rollback.

**VERIFY**

`python tools/stage2_core/audit.py --out artifacts/stage2_core/audit.json`; `python -m codejury.stage2_core.contract_check --contracts ../contracts`; `git diff --name-only`. Implement checker loading canonical schema/fixtures/ports checksum. Record actual audit and seed SHA in docs/stage2_core/audit.md. CPU metadata checks do not establish Mac inference. Native/runner gaps clearly pending.

## A2.02 · Schema adapters, immutable ledger and compute lease · P0 · depends: A2.01

**PROMPT**

Goal: give all roles/tools a trustworthy state and one budget authority.

Files you may touch: backend/src/codejury/stage2_core/{contracts,ledger,leases,budgets}/**, backend/tests/stage2_core/test_state.py, backend/config/stage2_core/profiles/**. Additional task-owned entrypoints: backend/src/codejury/stage2_core/ledger_cli.py.

Read canonical JSON schema/ports, validate input/output at every model/tool/API boundary and reject unknown keys. Verify installed jsonschema Draft2020-12 and SQLite transaction APIs. Build deterministic canonical JSON hashing for test/oracle/profile manifests; source hashing exact bytes. Persist append-only events and content-addressed sources/trace artifacts, no hidden eval content. Commit CandidateDraft only after IDs/hash/parent/edits/requirements/model-config provenance verified; eligibility computed later, never trusted from tool/model. Preserve two-edit SourceArtifacts and hash chain. Restore state and reject duplicate/nonmonotonic event or request IDs.

Implement exclusive Mac lease for runtime/training/teacher/benchmark, PID/owner/job ID and stale owner recovery. No simultaneously resident competing model jobs. Thread/IPC cancellation checked between calls and propagated to current worker. Central budget preflight reserves final qualification; count actual output/input tokens, model attempts/invalid choices, candidate attempts, search/audit invocations and wall deadline. Tool deltas include shrink/relation/probe costs and are added once; validate against dispatched ceilings. Episode walltime from monotonic start, not sum of overlapped tool timers. Cache key exact source/test/oracle/runtime/resource hashes. Incomplete scope stays pending. Restart accepted/running episodes to infrastructure_error, never duplicate generation.

**VERIFY**

`python -m pytest tests/stage2_core/test_state.py -q`; `python -m codejury.stage2_core.ledger_cli self-test --out artifacts/stage2_core/ledger-test.json`. Required: crash/replay/event order, immutable source, bad tool hash/ref, stale parent, malformed delta/budget overflow, two simultaneous lease contenders, stale PID/cancel, relation2cost, shrinkcost, exact-cache reuse. Paste real evidence; no model quality claim.

## A2.03 · One-base multi-adapter ModelPort · P0 · depends: A2.02

**PROMPT**

Goal: expose a real sequential model worker with clean A/B/Critic/Judge switching.

Files you may touch: backend/src/codejury/stage2_core/{model_worker,registry,factory,model_cli}/**, backend/config/stage2_core/runtime.yaml, backend/tests/stage2_core/test_model_port.py, backend/docs/stage2_core/model-audit.md. Additional task-owned entrypoints: backend/src/codejury/stage2_core/{model_cli,factory}.py.

Verify current installed MLX-LM load/generate/chat-template/sampler/LoRA insertion-removal interfaces, exact Phi model type and train/save/reload compatibility; use upstream docs plus signatures/--help. Never hardcode remembered module names or target projection paths. Base/tokenizer/quantization/topology metadata in registry and AdapterCards must agree. One long-lived native process, one base, one complete adapter parameter set active; no four bases. Unload/reset LoRA fully for raw; clean all relevant caches/state each role. Missing/mismatched keys fail closed. role general is comparator-only additional adapter, not another jury member.

ModelRequest -> ModelResponse exact schema. Enforce role/purpose caps and prompt+reserved completion<=4096 before generation; trim only bounded nonessential trace, never contract/test/required source. Cancel/worker exception reported accurately. Parse structured RepairDraft/CriticDraft/JudgeDraft outside worker in controller; raw text retained private. No generated tool execution inside model. Record input/output token counts through inspected tokenizer/runtime, latency/memory/null, real adapter/config hashes. Required manifest roles absent -> readiness false/typed unavailable, no silent raw substitute. Optional Qwen3B contingency is an explicit whole-experiment configuration change and all adapters/results retrained/retested.

**VERIFY**

`python -m pytest tests/stage2_core/test_model_port.py -q`; `python -m codejury.stage2_core.model_cli smoke --config config/stage2_core/runtime.yaml --sequence raw,fixer_a,raw,fixer_a --out artifacts/stage2_core/model-smoke.json`. Once B/Critic/Judge cards arrive repeat actual sequence raw,A,B,Critic,Judge,A,general(if available),raw with independent clean-load comparison. Native smoke records parameter hashes and outputs; no fake placeholder role allowed. Memory/profile measurement separate from theoretical weight-size arithmetic.

## A2.04 · Problem intake, role views and candidate registry · P0 · depends: A2.02, A2.03

**PROMPT**

Goal: preserve complementary information boundaries and immutable repair provenance.

Files you may touch: backend/src/codejury/stage2_core/{intake,views,candidates}/**, backend/tests/stage2_core/test_views.py, backend/tests/stage2_core/test_candidates.py. Additional task-owned entrypoints: backend/src/codejury/stage2_core/views_cli.py.

Map new RunCreate to Problem and supplied TestCases with controller IDs/signature; ask ToolPort.validate for semantic support/oracle consistency. Parse host AST only, no candidate import. B initial view includes target/helper INTERFACES but no original/helper bodies, A candidates/diagnosis/trace or hidden data. A receives original bundle/visible tests/failure trace. Critic gets candidate evidence and approved registry; Judge gets structured frozen state plus bounded visible summaries. Retain full prompt hash/view config privately for audit. Evidence for revisions is exactly observed input/oracle/property/output/trace; no guessed expected values.

Register A incumbent only after complete hard checks. B must have separate actual adapter hash; initial independent views are frozen before cross-feedback. Deduplicate normalized AST/exact source while retaining all attempts/seeds/role hashes privately. Different descriptions aren't diversity; sampled behavioral equivalence isn't proof. Original is never a repair. Parse/bound role JSON, one format retry per role response charged to output/candidate/decision limits, fail malformed output honestly. Parent/requirement/source/hash validation enforced. Initial A+B are required; later resampling/revisions within8learned attempts can improve failures without assuming two agents agree correctly.

**VERIFY**

`python -m pytest tests/stage2_core/test_views.py tests/stage2_core/test_candidates.py -q`; `python -m codejury.stage2_core.views_cli audit --fixtures ../contracts/stage2-fixtures --out artifacts/stage2_core/view-check.json`. Sentinel strings prove original/helper bodies and A traces absent from B prompt, hidden target absent everywhere, revisions fact-preserving, duplicate provenance retained, stale/source-hash mismatch rejected. CPU tests use fixtures; real A/B outputs only after trained B handoff.

## A2.05 · Validate/refresh A and curate frozen learning pools · P0 · depends: A2.03, A2.04

**PROMPT**

Goal: improve the base repair signal and collect leakage-free Stage2 training data.

Files you may touch: backend/src/codejury/stage2_core/{data,training/fixer_a}/**, backend/data/stage2_core/**, backend/config/stage2_core/training/fixer_a.yaml, backend/tests/stage2_core/test_corpus.py, backend/docs/stage2_core/data-card.md. Additional task-owned entrypoints: backend/src/codejury/stage2_core/{data_cli,training_cli}.py.

Import original Stage1 corpus/checkpoints by actual manifest, preserve licenses/provenance/family IDs. Expand types/helpers through reviewed correct pure functions, controlled bugs and natural student mistakes. Sarvesh seals final benchmark before learning; do not ingest external benchmarks reserved for final assessment. Split base/family/near-duplicates BEFORE corruptions/views/traces. Training targets validated through trusted reference tests in sandbox; prompts contain only runtime-visible tests/evidence. Treat generated-reference tests as finite empirical support and manually review ambiguous contracts.

Compare raw/current/earlier A on validation under identical prompt/decoding budgets. Check tokenized chat template, completion masking, target truncation, full reload and bad-format rate. If A regressed, fix pipeline/checkpoint or retrain execution-verified examples; not blindly more steps. Rank checkpoint by executable final-repair correctness, malformed output, false acceptance and cost; no training-loss-only decision. A may be retained if genuinely trained/reloaded/evaluated and non-regression documented. Sequential native pilot10–20steps for changed configuration before full validation-controlled job. Record real counts/hashes/logs; target corpus sizes in common training doc are collection goals, not existing data.

Export training/validation ArtifactManifest separately with records and reference targets only for authorized offline learning. Public/runtime views strip reference/assessment fields. Shared exchange contains no final hidden set. Create train-only A failure episodes for B/Judge/Critic; CPU fake episodes stay segregated and never become measured student failures.

**VERIFY**

`python -m codejury.stage2_core.data_cli validate --config config/stage2_core/training/fixer_a.yaml`; `python -m codejury.stage2_core.training_cli train --role fixer_a --config config/stage2_core/training/fixer_a.yaml` only if justified; `python -m codejury.stage2_core.training_cli evaluate --role fixer_a --config config/stage2_core/training/fixer_a.yaml`; `python -m pytest tests/stage2_core/test_corpus.py -q`. Implement all entrypoints with inspected MLX calls. Prove split/near-duplicate disjointness, no leaked targets, real training/reload and raw/A comparison. Retained adapter branch records why train was skipped rather than fake new log.

## A2.06 · Failure-specialized B mining/training · P0 · depends: A2.05

**PROMPT**

Goal: train B to rescue A's failures through independent reconstruction.

Files you may touch: backend/src/codejury/stage2_core/training/fixer_b/**, backend/config/stage2_core/training/fixer_b.yaml, backend/data/stage2_core/fixer_b/**, backend/tests/stage2_core/test_b_training.py, backend/docs/stage2_core/b-card.md. Additional task-owned entrypoints: backend/src/codejury/stage2_core/training_cli.py.

Freeze selected A and sample3fixed generations per TRAINING base problem using A's runtime view. Offline trusted training assessment estimates failure fraction f_A; syntax/domain errors count, infra errors retried/labelled separately. Weight examples w=1+alpha*f_A, initial alpha2 with validation trials0/1/2/4; retain25–50% broad general mixture. Do not reward disagreement/text diversity or sample sealed assessment failures into training. B inputs independently reconstruct intended behaviour/signature/helper interfaces/tests; targets reviewed correct bundles or training-assessment-verified repairs. No buggy/helper body/A output sneaks into initial prompt, even if data was selected because A failed.

Verify actual MLX-LM format/masking and model module names. Train B separately on same base/quantization/topology; pilot save/reload first; then validation-controlled checkpoints. Select by B standalone correctness plus union of A/B successes and actual rescue rate, not B loss alone. Preserve alpha0/control and same-view B experiment configs for scientific ablations. Report data counts, repeated variants and actual coverage; no assumed gain. Emit complete AdapterCard and fixer_adapters ArtifactManifest with compatible A/B weights/config/data hashes, ignoring large bytes in Git.

**VERIFY**

`python -m codejury.stage2_core.training_cli mine-b --config config/stage2_core/training/fixer_b.yaml`; `python -m codejury.stage2_core.training_cli train --role fixer_b --config config/stage2_core/training/fixer_b.yaml`; `python -m codejury.stage2_core.training_cli evaluate --role fixer_b --config config/stage2_core/training/fixer_b.yaml`; `python -m pytest tests/stage2_core/test_b_training.py -q`. Real outputs include3samples/problem, failure weights, split/view guards, saved/reloaded B, A/B paired validation successes/joint failures and negative results. CPU weighting test is not trained B acceptance.

## A2.07 · Fixed-policy controller and real episode export · P0 · depends: A2.04, A2.06

**PROMPT**

Goal: build the tool/action state machine and a reliable learning-data collector before learned Judge.

Files you may touch: backend/src/codejury/stage2_core/{controller,episode_export,factory}/**, backend/config/stage2_core/collection.yaml, backend/tests/stage2_core/test_controller.py, backend/docs/stage2_core/controller.md. Additional task-owned entrypoints: backend/src/codejury/stage2_core/{cli,export_cli,factory}.py.

Use injected ToolPort at development, real Sarvesh tools at E2. Sequence validate/reproduce→A/B independent generation→parse/dedup/execute/group→fixed actions for failure search/revision, consequential disagreement Critic, agreement audit/challenge→new oracle-gated tests→requalification/final selection. Build schema-valid ActionOptions for seven allowed kinds with current targets/evidence, requested budgets clipped; preserve A incumbent unless new evidence justifies replacement. No majority vote. Candidate qualification from complete authoritative test results; common suites propagate new tests, mark previous eligibility stale, freeze/hash final scope. Essential ambiguity/contract conflict -> unresolved.

Fixed-v1 continuation priority: valid new counterexample revise responsible parent; no eligible candidate search local sites then one resample if available; eligible disagreement criticize; shared agreement audit once per eligible version, then investigate useful gap; select after no pending required hard checks, else abstain. Rule ordering and budget reservations frozen on validation. Log all chosen/refused actions/outcomes and cumulative usage. Raw/prompted Critic may bootstrap TRAINING collection before learned Critic arrives, labelled raw not completed Critic. Unapproved tests stay observations. Infrastructure/cancel overrides stale success.

Export training-only EpisodeBundles with state, source/test/action/audit evidence and no hidden assessment. Produce parallel offline label joins privately, not runtime exports. Fixed controller is baseline/data collection, never final learned-Judge completion. Real coupled verification requires E2 tools; schema-valid CPU fake paths can finish earlier but remain labelled.

**VERIFY**

`python -m pytest tests/stage2_core/test_controller.py -q`; `python -m codejury.stage2_core.cli run --config config/stage2_core/collection.yaml --request ../contracts/stage2-fixtures/run-create.json --policy fixed --out artifacts/stage2_core/fixed-run.json`; `python -m codejury.stage2_core.export_cli episodes --split train --out artifacts/stage2-exchange/ajay/episodes`. Tests cover all actions/refusals, stale select, new-test invalidation, mutant survivor not failure, budgets/cancel and no hidden exports. Record real E2 run separately from CPU fixture ports.

## A2.08 · Alternative-action rollouts and Judge supervision · P0 · depends: A2.07

**PROMPT**

Goal: learn action values from executable outcomes instead of plausible reasoning labels.

Files you may touch: backend/src/codejury/stage2_core/{rollouts,training/judge_labels}/**, backend/config/stage2_core/training/judge.yaml, backend/tests/stage2_core/test_rollouts.py, backend/data/stage2_core/judge/**, backend/docs/stage2_core/judge-labels.md. Additional task-owned entrypoints: backend/src/codejury/stage2_core/rollout_cli.py.

After E3 Critic/tools freeze, snapshot TRAINING states across initial disagreement, shared wrong agreement, no eligible repair, near-correct local failure, surviving audit probe, recent revision and low budget. Enumerate available concrete ActionOptions from identical state/budget; explore up to4useful options with2–3fixed continuation seeds using fixed-v1 policy and exact frozen adapter/tools profile. Each fork has isolated run IDs/source/events; parent immutable, fresh KV/sandbox state. No labels from final evaluation or optional hindsight in prompt. EpisodeBundle validated before restore; action state/option/IDs must match. RolloutPort returns final selected patch/evidence only; offline training scorer joins reviewed references/hidden TRAINING tests, never feeds that result back to fork.

Utility initial correct_selection1 - incorrect_selection1 -0.05*normalized_cost; abstention0 minus cost, coefficients tuned validation/frozen before final eval. Label best empirical mean option, log uncertainty/replicate disagreement and exclude/treat uncertain ties with declared rule. Use final returned patch correctness, not candidate existence or mutation score. Counterfactual actions need genuine executed continuations, not fabricated scores. Target>=200states across>=60train base problems; a smaller genuine dataset is reported as limited supervision, not padded through copies. Judge SFT prompt contains only runtime state/available options; target state_id/option_id/evidence/rationale from visible facts. Rename IDs in augmentation consistently; do not train lookup by benchmark problem IDs.

**VERIFY**

`python -m pytest tests/stage2_core/test_rollouts.py -q`; `python -m codejury.stage2_core.rollout_cli collect --config config/stage2_core/training/judge.yaml --out artifacts/stage2_core/judge-rollouts`; `python -m codejury.stage2_core.rollout_cli label --config config/stage2_core/training/judge.yaml --out data/stage2_core/judge`. Verify parent hash unchanged, same state/budget/continuation across options, repeated real outcomes, train-only split and target/prompt separation. CPU deterministic simulations test restoration, not substitute real label generation.

## A2.09 · Train Judge and enable validated learned policy · P0 · depends: A2.08

**PROMPT**

Goal: replace fixed action choice with genuine learned Judge while keeping hard safeguards.

Files you may touch: backend/src/codejury/stage2_core/{training/judge,controller/judge}/**, backend/config/stage2_core/training/judge.yaml, backend/tests/stage2_core/test_judge.py, backend/docs/stage2_core/judge-card.md. Additional task-owned entrypoints: backend/src/codejury/stage2_core/{training_cli,model_cli}.py.

Inspect current MLX SFT/masking/target tokenization and real module topology; pilot/save/reload then full validation-controlled Judge training on alternative-action labels. Same frozen base/rank-start/topology contract. Judge produces JudgeDraft, not code/actions outside menu. Validate state_id/current option/evidence/prerequisites/budgets before dispatch; select/revise/audit rules deterministic. Refusal logged and one schema retry allowed within8Judge calls, then fixed fallback explicitly recorded. Preserve all tokens/costs, including invalid choices; no invented action outcomes. Train/evaluate adversarial stale-ID/invalid-action examples and valid abstention cases.

Role-specific evaluation: action validity, final correctness/incorrect acceptance vs fixed SAME tools and budgets, cost and invalid fallback rate. Accurate imitation of noisy labels is not enough. Save Card/hash/config/real loss, emit judge_adapter manifest. All4 role switching tested after consuming Sarvesh Critic. Learned-policy readiness requires completed trained cards, actual ToolPort and schema; default live learned mode cannot silently stay fixed. RL fine-tuning optional and not introduced here.

**VERIFY**

`python -m codejury.stage2_core.training_cli train --role judge --config config/stage2_core/training/judge.yaml`; `python -m codejury.stage2_core.training_cli evaluate --role judge --config config/stage2_core/training/judge.yaml`; `python -m pytest tests/stage2_core/test_judge.py -q`; real `model_cli smoke` sequence with4roles. Record real adapter, valid/refused decisions, fixed-vs-learned validation and any worsening. No accuracy target invented.

## A2.10 · Versioned API, reports, baseline runtime adapters · P0 · depends: A2.09

**PROMPT**

Goal: expose the full evidence system and let the research harness compare it fairly.

Files you may touch: backend/src/codejury/stage2_core/{api,baselines,cli}/**, backend/tests/stage2_core/test_api.py, backend/config/stage2_core/runtime.yaml, backend/docs/stage2_core/api.md. Additional task-owned entrypoints: backend/src/codejury/stage2_core/{baseline_cli,factory}.py, backend/tools/stage2_core/api_smoke.py.

Verify actual FastAPI/Pydantic validation hooks/StaticFiles current APIs; exact canonical envelopes, all routes, accepted-before-dispatch atomic run slot. Persist/recover old-version IDs as archived409 through Stage2 without rewriting rows; unknown404. Cancellation kills native generation job and sandbox work safely; restart infra result. GET training cards from actual manifests, GET benchmark report from actual Sarvesh aggregate artifact, not fixtures; no metrics means not_run. No missing/extra field filtered into apparent valid result. Sanitize returned traces/errors/paths and exclude hidden assessment/reference data.

Expose research runner call interfaces under core.baselines without importing hidden eval: B0 raw single, B1 A execution-feedback, B2 A sampling/revision, B3 general adapter with same action/search/audit tools, B4 prompted4roles/fixed, CJ learned4roles. Baseline methods accept exactly same runtime-visible Problem/tests/profile and return RunResult/selected source; harness assesses after commitment. General adapter role is compatible optional registry entry trained by Sarvesh; same tool APIs/action validator apply, no handicapping baseline by withholding search/audit. Frozen configs distinguish token/time matching; all costs reported. Tool-disabled ablations are explicit methods, not silently changed full release.

**VERIFY**

`python -m pytest tests/stage2_core/test_api.py -q`; `python tools/stage2_core/api_smoke.py --base-url http://127.0.0.1:8000 --contracts ../contracts`; `python -m codejury.stage2_core.baseline_cli self-test --out artifacts/stage2_core/baseline-contracts.json`. Implement tools. Test every error/version/race/restart/cancel/report/privacy path and identical visible inputs/tool access in baseline methods. Fakes remain test-only; actual serving after merge.

## A2.11 · Real integration, Mac profile and system acceptance · P0 · depends: A2.10

**PROMPT**

Goal: complete final functional integration on actual Mac, preserving both owners' work.

Files you may touch: backend/tools/stage2_core/**, backend/docs/stage2_core/integration.md; custodian integration/**, root release README and actual package/API wiring only at E4. Additional task-owned entrypoints: backend/src/codejury/stage2_core/cli.py.

Merge partner handoff using common seed and fixtures; integrate make_tool_port, model registry4cards, Sarvesh UI/static mount and benchmark artifact path. Verify dependencies/lock from both owner lists; no second stack or duplicate worker. Inspect live VM host shares effectively disabled; no host home/credentials/repo/socket mounted. Profile actual memory/latency on target Mac, keep one model/adapter at time,2GBVM initially. Native train/infer+VM fit measured; lower sequence/layers/budgets only through frozen config validation, not silent evaluation advantage. No Linux MLX/CUDA requirement. Offline cached weights/runtime work when internet absent.

Real workflows include A/B repair, useful AST search, gap-driven Critic counterexample, learned Judge action/selection, rejected stale action, ambiguous/unresolved, cancel, loop watchdog and infra failure. A single problem need not exercise all components; use separate disclosed examples. RunDownload exact immutablehash and reportscopes consistent. Existing Stage1 control can still run separate originalrelease/CLI. No pending hardware test treated passed. Final evaluation target dataset supplied by Sarvesh; do not inspect hidden tests or tune after final results.

**VERIFY**

From repo root: `python -m codejury.stage2_core.cli serve --config integration/stage2/runtime.yaml`; in another terminal `python backend/tools/stage2_core/system_acceptance.py --base-url http://127.0.0.1:8000 --out backend/artifacts/stage2_core/system`. Run both owner CPU suites once, real role-switch/sandbox tests and full browser check. Retain actual model/tool manifest/profile hashes and each run report/patch/log. Tool system_acceptance is project-owned to implement. Do not start mock8001 for live verification.

## A2.12 · Reproducible core/release handoff and final research audit · P0 · depends: A2.11

**PROMPT**

Goal: make complete project behaviour and research conclusions independently reviewable.

Files you may touch: backend/docs/stage2_core/{handoff,release,limitations}.md, backend/tools/stage2_core/handoff_check.py, integration/stage2/release-manifest.json, root README after integration.

Record real completed task/milestone matrix, versions/commonseed/commit, exact4adapter/core data/profile hashes, actual commands, Mac memory/timings, tests/hardware skips and known failures. Verify Sarvesh final eval manifests tool/budget parity and general-comparator training opportunities,3seed clustered intervals/ablations and actual research_outcome; don't claim advantage if inconclusive/worse. Training/evaluation costs and baseline input/prefill cost included. Preserve failed trials not just best demonstration. Public release contains aggregate evidence, no hidden final sources/keys/weights in Git. Provide reproducible local run/train/eval commands through projectCLIs, no invented upstreamflags.

Final completion checks all original M1–M5 and M6–M10,4trained/reloaded roles,learned Judge used,search/audit operative,expanded domain/helper harness,live UI and truthful evaluation. If a core model role isn't genuinely trained, mark incomplete instead of calling it a prompted equivalent. Final learned-policy contribution can be scientifically negative even though feature-complete.

**VERIFY**

`python backend/tools/stage2_core/handoff_check.py --contracts contracts --out backend/docs/stage2_core/handoff.md`; `git diff --name-only <actual-common-stage2-seed>...stage2/ajay-core`; validate release/adapter/artifact hashes and both owner checks. Owner branch changes only assigned paths; integration exception paths belong integration branch/custodian commits. Record actual release result and research claims supported/unsupported. No push/publication implied.

## D. Dependency build order

| Window | Tasks | Evidence |
|---|---|---|
| E0/E1 |A2.01–A2.04|Baseline audit,ledger/worker/port/view CPU acceptance|
| E2 |A2.05–A2.07|Real A/B,training corpus,tool-driven fixed episodes|
| E3 |A2.08–A2.09|Real alternative continuations,trained Judge|
| E4 |A2.10–A2.12|Learned API/baselines,merged Mac release|

No assigned dates; execute in dependency order. Independent CPU work can proceed before partner live handoff; real coupled tasks wait for actual exchange hashes.

## E. Final acceptance

Mark✅ only with real evidence: original baseline audited; one common frozen schema/ports; owned-paths only; clean base/4adapter switches; genuinely validated A/B/Judge plus received real Critic; training splits/weights/helper information boundary; immutableledger/cancel/limits; all7actions guarded; real counterfactual labels with no hidden leakage; learned Judge used not fixed-only; real tool port/fullsuite selection; versionedAPI/UI integration; fair comparator runtime; Mac measured; final research/release manifests truthful. Training/UI fixtures never count as a completed learning milestone.
