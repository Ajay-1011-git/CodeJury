# Critic card (S2.08)

**Status: not trained.** There is no Critic adapter, no training log, no reload evidence and no
measured role evaluation. `card.json` does not exist, and `handoff_check.py` reports it as missing.

## Done and tested on CPU
- `critic_training/selection.py`: picks a checkpoint from measured role metrics (format and domain
  validity floors, counterexample yield, false rejection of correct candidates, audit-gap challenge
  benefit, cost). Loss is not an input. A checkpoint with any unmeasured metric is ineligible, and
  if none is eligible nothing is selected.
- `critic_training/cards.py`: `build_card` refuses a `completed` card without the real weights file,
  a verified reload, the real log and the data manifest hash, and validates against the frozen
  `AdapterCard` schema. `export_manifest` hashes real files and refuses a directory inside Git.
- `critic_cli train|evaluate|export` exit 3 with `status: pending`. They run nothing.
- Tests: `tests/stage2_tools/test_critic_training.py` (6 passed).

## Not done (needs MLX hardware and real E2 episodes)
No trainer was written. The MLX JSONL chat format, masking, LoRA module targets and save/reload
APIs were not inspected (`mlx` is not installed here), so any trainer would have been guessed.
Pilot, full SFT, measured evaluation, the exclusive compute lease and E3 registry load/switch are all
pending. Pending tests are not passed tests.
