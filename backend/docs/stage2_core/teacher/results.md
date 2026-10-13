# Completed teacher A training experiment — 13 October 2026

The actual native MLX pilot completed **20 updates** and the full candidate completed **100 updates**. Both verified changed finite adapter tensors, assistant-completion masking, saved weights and fresh runtime reload. The full run took **87.90 seconds** and peaked at **3256.36 MB**; the pilot took 39.84 seconds. The current A weights were used as an explicitly declared warm start in a new immutable job, without old optimizer-state resume. Old role weights/jobs remain preserved.

| Local validation checkpoint | Solved / 20 | Incorrect accepted | Malformed |
|---|---:|---:|---:|
| Raw base | 0 | 0 | 20 |
| Current A | 5 | 0 | 1 |
| Teacher candidate, 50 updates | **6** | **0** | **0** |
| Teacher candidate, 100 updates | 6 | 1 | 0 |

**The 50-update checkpoint is the selected A candidate.** The 100-update checkpoint is rejected by the no-increased-incorrect-acceptance gate. Selection uses actual executable results, not training loss. Native full-job completion is distinct from selecting an earlier saved checkpoint.

The candidate has three paired newly solved variants and two lost variants, for a net gain of one. These 20 variants share only **10 independent base problems**. This is tentative evidence of a small improvement, with meaningful regressions, not a broad intelligence or superiority claim. Both current/new evaluations use identical local validation inputs, supplied evidence, greedy decoding, seed 17, a 1024-token generation cap and the same trusted private checks. Raw/current evidence was reused only after source/adapter/config/seed/cap identities matched; candidate checkpoints were actually regenerated and executed.

Rejoining the unchanged independent B checkpoint's real execution evidence gives **11/20 union solves**, versus 10/20 with current A. B's five solves remain complementary, with zero incorrect accepted B repairs. B was not retrained by this comparison; its original A-mining lineage is explicitly preserved. A fresh TRAIN-only mining run against the new A is required before finalizing that lineage.

The candidate is frozen in an isolated local artifact. **The live four-role registry has not been switched.** Before activation/final release, affected B lineage, Critic candidate-distribution validation, executed Judge continuation labels and Judge checkpoint, and General's teacher opportunities/completion exposure must be refreshed or verified. Old Judge labels remain compatible with the old deployed system; they are stale for the changed A candidate. The final benchmark remains sealed.

Private evidence: `artifacts/stage2_core/teacher/{student-pilot-v1,student-full-v1,comparison-v1.json,paired-comparison-v1.json,selected-a-v1}`. Provider collection cost is $0.0063987; 22 unique verified teacher targets were drawn into the disclosed 60/40 replay mixture. No additional teacher API collection or repeated training search was used to force a gain.

CPU verification: full backend suite **527 passed, 9 native-only checks skipped**; actual native training/reloads and dedicated Docker validations above were run separately. The historical Sarvesh exchange utilities and Ajay's native implementation were merged locally in commit `c05942c`. No automatic push or deployment was performed.
