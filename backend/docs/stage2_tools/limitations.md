# Known limitations and missing gates

- No real training anywhere: no Critic or general adapter, no real E2 episodes, no measured role
  evaluation. S2.07-S2.10 deliver tested pipeline code only; S2.08/S2.10 training is pending.
- No final benchmark was run. The final pool in the manifest has 10 base problems against a target of
  200, so any result would be limited evidence.
- Sandbox: the runner image builds on Docker Desktop (arm64), but the self-test correctly refuses it:
  the gate requires the dedicated no-mount Colima profile `codejury-stage2`, which is not installed.
  All 12 native sandbox checks remain `pending_native`.
- MLX: a 10-step Critic *fixture* pilot ran natively (masking and reload verified). No real Critic
  was trained. Python 3.12 was used instead of 3.11.
- Integration items for the core: per-method config hashes must match the harness; the core owns the
  hard-suite hash; `make_baseline_port` does not exist on Ajay's branch yet; the merged Mac
  browser/system acceptance with all four trained roles has not happened.
- EvalPlus adaptation is not built.
- UI: mobile layout, a keyboard-only walkthrough and headless-browser automation are not covered.
