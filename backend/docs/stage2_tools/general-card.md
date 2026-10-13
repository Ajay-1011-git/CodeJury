# General comparator card (S2.10)

**Status: not trained.** No general adapter, log or reload evidence exists.

## Done and tested on CPU
- `general_training/merge.py`: merges the four frozen role datasets into one tagged distribution
  (repair / test / action). It refuses non-TRAINING data, mixed fixture/real data, a missing role and
  duplicate records, and keeps split/base-problem/view provenance.
- `general_training/audit.py`: opportunity parity from actual examples, tokens seen and optimizer
  steps. Any unmeasured input gives `not_measured`, never a pass. The 10% tolerance in
  `general.yaml` is the task owner's choice, to be tuned only before any final result exists.
- `general_cli validate` is pending (exit 3) until the four role manifests exist; `train` and
  `evaluate` are pending (exit 3).
- Tests: `tests/stage2_tools/test_general_training.py` (5 passed).

## Not done
Training, reload, checkpoint selection on validation, registering `general` in Ajay's worker and the
B3 tool-access smoke all need MLX, the frozen A/B/Critic/Judge datasets and Ajay's runtime. A missing
fair B3 means the research comparison is incomplete; it must not be replaced by a raw one-shot.
