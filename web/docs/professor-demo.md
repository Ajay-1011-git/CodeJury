# Stage 1 professor demonstration

Use the integrated live application started with `./start.sh`, at http://127.0.0.1:8000. Confirm the header shows trained Fixer A and the backend connection. No fixture banner should be present. Allow enough time for actual local inference and sandbox checks; this is not a fixed-duration replay.

1. **Scope:** “CodeJury repairs one pure Python function from a behavioral contract and user tests. Stage 1 uses a trained Fixer A, raw/prompted Critic and fixed controller. The sandbox supplies executable evidence.”
2. **Successful repair:** Select *Sum signed integers*. Show `return 0`, supplied input `[2, -4, 7]`, and expected output `5`. Explicitly approve `sum_ints`. Start the run and show failure reproduction, candidate source/diff, authoritative checks and the final decision. Disclose that this public unscored mechanics demo overlaps the training family.
3. **Artifacts:** Download `.py` and report JSON. Show the selected candidate ID and matching source SHA-256. Explain that the verdict supports only the admitted verification scope.
4. **Challenge and limits:** Select *Preserve first-occurrence order*. Approve its property. Show concrete failing inputs, actual/expected outputs and the bounded revision event if present. An unresolved outcome is real evidence of the current model's limitations, not a successful repair.
5. **Cancellation/error:** Cancel a newly started run. Confirm there is no selected patch. Demonstrate an invalid input rejection without executing user source on the host.
6. **Training/evaluation:** Show the real 300-step trial, selected step-100 adapter, 80 training records and 40/10/10 train/validation/assessment bases. Raw single-shot, trained A single-shot and Stage 1 loop each solved **1/10**, left **9 unresolved**, and had **0 incorrect accepted**. Training improved JSON formatting and single-shot costs, with no observed solved-count gain. Budgets differ, so no superiority claim follows.
7. **Milestones:** M1–M5 cover safe execution and durable runs, local model repair, real training, executable critique/revision, and integrated demonstration. Five of ten planned milestones is the Stage 1 rubric. Stage 2 adds complementary Fixer B, learned Critic/Judge, AST repair search, mutation auditing and full research evaluation.

Retained live reports, selected patch and screenshots are under `backend/artifacts/integration/` on the demonstration Mac. Training and evaluation cards are in `backend/docs/`. Mock tests and synthetic UI fixtures are development evidence only.
