# Critic card (S2.08)

**Status: no real Critic exists.** The trainer runs natively, but the only run is a 10-step *fixture
plumbing pilot*. There is no Critic adapter trained on real episodes, no measured role evaluation and
no `card.json`; `handoff_check.py` reports the card as missing.

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

## Native trainer (written after reading Ajay's inspected MLX usage)
`critic_training/{sft,native,launch}.py`, `critic_cli train --pilot|--fixture`. Interface mirrors what
`codex/stage2-ajay-core` documents for mlx-lm 0.32.0 (`build_parser`, `train_model`,
`TrainingCallback`, `load_dataset`, chat JSONL with `--mask-prompt`); it does not import Ajay's runtime.
- SFT export splits by base problem, so train and validation never share a base problem.
- Before step 1 the bridge checks LoRA targets exist and that every completion is fully unmasked and
  untruncated.
- After training it reloads the saved adapter into a fresh model and requires every saved tensor to
  equal the loaded tensor (`reload_verified`).
- Full training refuses to start unless a real (non-fixture) pilot with verified reload exists.

## Fixture pilot actually run (not a Critic)
Phi-4-mini 4-bit (`mlx-community/Phi-4-mini-instruct-mlx-4Bit`, revision d848c30f), MLX 0.32.3,
mlx-lm 0.32.0, Python 3.12 on this Mac. Data: 14 synthetic fixture records from 6 invented base
problems (11 train / 3 validation records). Result: 10 of 10 steps, masking verified (longest example
780 tokens), 16 adapter tensors reloaded and equal, peak memory 3558 MB, 38.8 s, adapter sha256
`8010c6ae...e901e4d`. Loss fell to 0.09 because the fixture records are tiny and repetitive; it says
nothing about Critic quality. Logs stay in ignored `artifacts/`; no weights are in Git.

## Still not done
Full SFT, validation-controlled checkpoint selection on measured role metrics, measured role
evaluation, the exclusive Mac compute lease, the real export, and E3 registry load/switch in Ajay's
worker. All need real E2 episodes (A/B fixers run on training problems), which do not exist here.
Pending tests are not passed tests.
