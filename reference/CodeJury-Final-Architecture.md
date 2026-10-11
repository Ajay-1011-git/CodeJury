# CodeJury — Final Architecture (v2.0)

## 1. System Overview
CodeJury is an automated specification-directed program repair and verification framework. It integrates LLM-based program synthesis with verified property oracles, dynamic test execution in isolated sandboxes, and counterexample-guided candidate refinement.

Stage 1 establishes the verified communication seam, the local UI, deterministic mock API, candidate execution inspection, and presentation views.

## 2. Directory Ownership and Separation of Concerns
- `contracts/**`: Immutable API schema and synthetic fixture files. Frozen at `stage1.v1`.
- `reference/**`: Immutable architecture and specification documentation.
- `web/**` (Sarvesh): Local UI, static development server, fixture mock API, frontend client, evidence matrix, training/result visualizer, professor demonstration materials, and client tests.
- `backend/**` (Ajay): Real FastAPI backend, sandbox runner, model inference worker, training loop (LoRA / SFT), evaluation pipeline, and benchmark datasets.

## 3. Communication Seam (stage1.v1)
All communication adheres strictly to `contracts/stage1-api.schema.json` (SHA-256: `5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df`).

### Network Endpoints
- UI Development: `http://127.0.0.1:8080`
- Mock Development API: `http://127.0.0.1:8001`
- Real Backend API: `http://127.0.0.1:8000`

### API Routes
- `GET /health` -> `Health`
- `GET /examples` -> `Examples`
- `POST /runs` -> `RunAccepted` (202)
- `GET /runs/{run_id}` -> `RunSnapshot` (200)
- `GET /runs/{run_id}/events?after=N` -> `EventPage` (200)
- `GET /runs/{run_id}/candidates/{candidate_id}` -> `Candidate` (200)
- `POST /runs/{run_id}/cancel` -> `RunSnapshot` (200)
- `GET /runs/{run_id}/report` -> `RunSnapshot` (200)
- `GET /stage1/training-report` -> `TrainingReport` (200)

## 4. Agent and Role Topology (Stage 1 vs Stage 2)
### Stage 1 (Frozen Prototype Boundary)
- **Fixer A**: Single code repair model (trained adapter or raw baseline).
- **Critic**: Prompted test and counterexample generator; generates observations and property tests.
- **Controller**: Deterministic execution loop managing candidate generation, runner execution, and oracle admission.
- **Deferred to Stage 2**: Fixer B, learned Judge, adversarial auditor, tree-search MCTS, and multi-model consensus.

## 5. Oracles and Ground Truth Verification
To prevent oracle gaming and false confidence:
- Three approved deterministic properties:
  1. `sort_ascending_ints`: List of integers nondecreasing with identical multiset equality.
  2. `unique_preserve_order_ints`: List of integers with duplicate removal preserving first-occurrence order.
  3. `sum_ints`: Exact mathematical sum of list of integers.
- Oracles are strictly partitioned:
  - `authoritative`: User-supplied tests and approved property oracle executions.
  - `proposed` / `observation_only`: Model-generated test assertions. Never given a green "pass" badge.
- No teacher targets or hidden benchmark test cases are ever exposed to runtime prompts or the UI.
