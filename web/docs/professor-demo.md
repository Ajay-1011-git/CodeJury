# CodeJury Stage 1 — Professor Demonstration & Rehearsal Outline

**Presenter**: Sarvesh Kute  
**Duration**: 3–5 Minutes  
**Audience**: Course Professor / Project Evaluators  
**System Boundary**: Stage 1 Seam (`stage1.v1`), Local UI, Verified Oracles & Training Evaluation  

---

## 1. Opening & Architecture Overview (0:00 – 0:45)
- **Goal**: Present the Stage 1 prototype for specification-guided automated program repair.
- **Architectural Division of Roles**:
  - **Fixer A**: Single code repair model (trained LoRA adapter or raw baseline).
  - **Critic**: Prompted test generator producing hypothesis tests and property challenges.
  - **Controller**: Deterministic execution loop administering oracles without human intervention.
  - **Stage 2 Deferred Notice**: Explicitly state to the professor that Fixer B, learned Judge arbitration, adversarial auditors, and tree-search MCTS are intentionally deferred to Stage 2.
- **Header Badges**:
  - Show "Stage 1 Prototype" badge.
  - Point out the active backend connection pill and the persistent **"⚠️ Fixture demonstration — no live inference"** banner (or live connection badge when running against Ajay's backend).
  - Point out role status badges: *A: trained/raw as supplied by backend*, *Critic: Prompted*, *Controller: Fixed Policy*, *B/Judge/Auditor: Deferred*.

---

## 2. Input Configuration & Explicit Property Consent (0:45 – 1:30)
- **Preset Example Loading**:
  - In the "Task Input & Approved Contract Oracles" card, select `Sort Integers (Ascending)` from the example dropdown.
  - Observe automatic population of function name (`sort_ints`), contract prose, input domain descriptors, and supplied literal tests.
- **Stage 1 Constraint Enforcement**:
  - Explain to the professor that Stage 1 strictly supports pure Python functions with 1–3 integer or list-of-integer arguments (`[-1000, 1000]`, length $\le 30$).
  - Explain that floating point numbers, third-party imports, helper functions, decorators, and global state are strictly forbidden.
- **Explicit Property Oracle Consent**:
  - Highlight the Approved Property dropdown: `sort_ascending_ints`.
  - Show the mathematical explanation: *Output is a non-decreasing integer sequence with identical multiset element multiplicities*.
  - Show the required **Explicit Approval Checkbox**: Explain that properties are disclosed contract oracles, not hidden ground truth, and require user consent before serialization.

---

## 3. Submission, Reproduction, and Event Timeline (1:30 – 2:30)
- **Trigger Run**:
  - Click **"Start Verification Run"**.
  - Show that the submit button disables immediately to prevent duplicate submissions.
  - Show the connection making `POST /runs` and receiving `202 Accepted` with opaque run ID.
- **Event Timeline (Card 2)**:
  - Watch the live 1,000ms polling progression: `queued` $\to$ `running` $\to$ `supported_patch`.
  - Point out the event timeline:
    1. `run_started`: Run accepted.
    2. `original_checked`: Original buggy code executed against supplied test `[3, 1, 2]`; failure is reproduced.
    3. `candidate_created`: Fixer A synthesizes candidate `cand-001`.
    4. `execution_completed`: Candidate executed in isolated sandbox.
    5. `test_admitted`: Approved property oracle `test_prop_1` admitted into challenge suite.
    6. `run_finished`: All authoritative tests passed without input mutation.
  - *Key Clarification*: State explicitly to the professor that this event timeline is a factual action log, NOT hidden model chain-of-thought or fabricated reasoning.

---

## 4. Evidence Matrix & Counterexample Drilldown (2:30 – 3:30)
- **Candidate Inspection (Card 3)**:
  - Show `cand-000` (original code) marked **Rejected** (failed reproduction).
  - Show `cand-001` marked **Eligible** with lowercase SHA-256 byte hash and clean diff.
  - Show that code rendering uses safe textContent (no HTML injection or arbitrary host eval).
- **2D Execution Matrix (Card 4)**:
  - Columns represent tests (`test_supplied_1`, `test_supplied_2`, `test_prop_1`, `test_obs_1`).
  - Rows represent candidates (`cand-000`, `cand-001`).
  - **Oracle Badges**: Show `Literal (Auth)`, `Property (Auth)`, and `Proposed / Observation Only`.
  - **Outcome Badges**:
    - Show green `PASS` for passed authoritative tests.
    - Show red `FAIL` for the original buggy code.
    - **Crucial Rule**: Point out that model hypothesis predictions are marked **OBSERVED** in gray/neutral, NEVER given a green pass badge.
- **Counterexample Drilldown**:
  - Click on the execution cell for `cand-000` on `test_supplied_1`.
  - Show the inspector panel displaying input arguments `[[3, 1, 2]]`, expected `[1, 2, 3]`, actual `[3, 2, 1]`, execution duration (3 ms), trace, and `input_mutated: false`.

---

## 5. Verdict, Verifiable Artifacts, and Training Summary (3:30 – 4:30)
- **Final Result (Card 5)**:
  - Show `Supported Patch Verified` banner with selected candidate `cand-001`.
  - Review actual resource usage: elapsed time, input/output token counts, function executions, and memory.
  - Demonstrate clicking **"Copy Patch Source"** and **"Download Report JSON"**.
  - Note: In `unresolved` or `cancelled` states, the copy patch button is absent, preventing false success claims.
- **Training & Evaluation Metrics (Card 6)**:
  - Show the Offline Training section consuming `GET /stage1/training-report`.
  - Explain the genuine loss curve (cross-entropy training vs validation loss across steps) rendered with zero external chart libraries using pure SVG.
  - Review the 50-problem benchmark evaluation table comparing:
    - *Raw Baseline (Single-Shot)*: 14/50 solved (28.0%).
    - *Trained Fixer A (Single-Shot)*: 28/50 solved (56.0%).
    - *Stage 1 Loop (Fixer A + Verified Oracles)*: 39/50 solved (78.0%).
  - Clarify that if training has not been run, the UI honestly renders **"Not Yet Measured"** with nulls preserved as dashes (never fabricated as 0).

---

## 6. Backend Integration Transition Guide (4:30 – 5:00)
- **Standalone Development**: Currently connecting to Mock API on `http://127.0.0.1:8001`.
- **Live Partner Integration (Pre-Merge)**:
  - Start Ajay's real FastAPI backend on `http://127.0.0.1:8000`.
  - Open UI with localhost override query parameter:
    ```
    http://127.0.0.1:8080/?api=http://127.0.0.1:8000
    ```
  - The UI automatically points to the real backend, displays `Connected`, and hides the fixture banner once live data arrives.
- **Post-Merge Deployment**:
  - Ajay mounts `web/` static directory on the root FastAPI app.
  - The UI defaults to same-origin (`window.location.origin`), eliminating all CORS and query parameters.
- **Fallback Policy**:
  - If the backend model server or Mac GPU is unavailable during the professor demonstration, fallback to `http://127.0.0.1:8001` with the clearly displayed "Fixture demonstration" banner.
