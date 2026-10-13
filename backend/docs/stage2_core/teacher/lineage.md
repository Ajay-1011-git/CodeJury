# Teacher candidate lineage

Current four-role runtime remains frozen to its original A/B/Critic/Judge set. A separate teacher experiment has completed pilot/full training and executable validation. Its 50-update checkpoint improves individual A validation from 5/20 to 6/20 with zero incorrect accepted repairs; the later checkpoint is rejected. It is a candidate for integration, not a silently changed upstream role.

- A: inherited current A initialization, new 60/40 mixed TRAIN manifest, no optimizer-state continuation; selected at 50 actual extra updates after a verified 100-update full job.
- B: original weights and training lineage preserved. Rejoined unchanged independent-view execution evidence has 11/20 union success with the candidate A. Fresh candidate-A TRAIN mining is being recorded in a separate directory. Old B training is never described as newly trained against this A.
- Critic: original measured checkpoint remains deployed. Validate on newly collected candidate-A episodes before accepting its distribution compatibility; preserve its old reports.
- Judge: original completed checkpoint and pilot preserved. Existing continuation labels are valid for the original role set, and stale for the teacher candidate. Newly executed affected alternatives and a separate job/manifest are required before deploying a new Judge.
- General: 550-update pre-teacher full job saved/reloaded. Its measured 38,976 completion tokens were within 5.79% of the original council's 36,845. Quality selection and a teacher-opportunity refresh remain required for any teacher-upgraded research comparison.

Groq provides proposals only. It never provides Judge action correctness labels or replaces execution outcomes. Final assessment contents remain unopened. No shared schemas, ports or fixtures changed.
