# Fixer A training card

Status: real seeded 10-step pilot and 300-step trial completed; selected step-100 adapter frozen on validation only. Evaluation remains pending A.08.

Chosen model: mlx-community/Phi-4-mini-instruct-mlx-4Bit at conversion revision d848c30f6d5419b9892433cf6b1062626d15340e. Microsoft upstream model currently reports revision cfbefacb99257ffa30c83adab238a50856ac3083 and MIT license. The community card identifies the Microsoft base but does not publish the exact original base revision used during conversion; the current upstream revision is an observation, not an asserted conversion lineage. Local weight/tokenizer/config hashes will be recorded by native smoke.

Installed native stack: Python 3.11.16, MLX 0.32.3, MLX-LM 0.32.0. The actual converted configuration is model_type phi3, hidden size 3072, 32 layers, 24 attention heads/8 KV heads, partial rotary factor 0.75, tied embeddings and 4-bit affine quantization with group size 64. No remote Python code is loaded.

Initial pilot/full configuration: rank 8, scale 16, dropout 0, last four layers, attention projections self_attn.qkv_proj and self_attn.o_proj, microbatch 1, max sequence 768, gradient checkpointing, accumulation 1, learning rate 0.0001, seed 17. Projection names and complete masked target lengths are checked on the loaded model/tokenizer before any step. Pilot is 10 steps; initial full trial is 300 steps. These are trial settings, not guaranteed convergence.

The launcher records inspected equivalent upstream CLI argv and the actual project-native command. The native bridge uses the installed MLX-LM parser, defaults, train_model and TrainingCallback directly to preserve machine-readable local loss/memory/time logs. Upstream lora.run replaces its callback argument in this installed release, so the bridge calls train_model after the verified load/dataset flow. It does not use an additional serving/training stack or paid telemetry.

Training consumes 80 synthetic train records and 20 validation records, with assistant-completion masking. No assessment/Stage2 targets are exported. Checkpoints at 100/200/300 will be selected by actual executable repair success on validation bases, then malformed output count and earlier step. Loss alone will not select the checkpoint. Reports will preserve any observed worsening.

Fixer/critic role switching destroys and reloads the entire model: adapter A for repairs, clean raw base for Critic, fresh prompt cache each call. A/raw/A parameter hashes and deterministic generated output are checked in a real native smoke. Raw operation needs explicit CODEJURY_ALLOW_RAW; readiness requires genuine smoke/freeze evidence and an adapter hash. Runtime prompts contain only supplied visible request/failure evidence and approved counterexamples.

Large weights, adapters, sessions, loss files, generated candidates and logs remain in ignored backend local storage. The handoff will record measured hashes, steps, memory, elapsed time and verification results after native checks finish.

## Actual training and validation evidence

Final seeded session: `artifacts/training/fixer_a_seed17/session.json`, with NumPy and MLX seeds both 17. The 300-step run took 136.217 seconds and peaked at 3144.468 MB. Assistant masking was verified on every exported record; the longest train sequence was 444 tokens. Train loss at step 10 was 1.52123, and step 300 was 0.0060056. Validation loss worsened from 0.185604 at iteration 99 to 0.321105 at iteration 299; those observations are retained. Loss logs and exact commands/config/data hashes are in the session directory.

An earlier pilot and full trial seeded MLX but omitted the NumPy shuffle seed. Audit found and fixed that omission. Their local logs remain in `fixer_a_pilot` and `fixer_a`, excluded from checkpoint selection. The final pilot/full trial were rerun in separate seed17 directories before validation.

All three saved checkpoints (100/200/300) solved 2/10 validation bases with 0 malformed outputs. Each generated patch ran all four visible/private validation tests in the sandbox. Tie breaking selected the earlier step 100. The frozen adapter SHA-256 is `274fd6b1a4a9abd04a8a2d3e56cfbde765c81e71fdb230682f4bf66509605fb4`, stored locally in `artifacts/training/fixer_a_selected`; its freeze manifest records the 300 actual training steps and checkpoint selection. Validation reports and full generations are retained in `artifacts/training/checkpoint-validation`.

The initial public unique-preserving-order smoke generated `return values`: valid/executable JSON, incorrect output. Its result is retained as `artifacts/training/model-smoke-unique-failed.json`. The raw base likewise failed strict repair JSON formatting, including its one charged retry; both raw smoke attempts are retained. No correctness claim is made for these failures.

The public sum mechanics demo generated `return sum(values)` and returned the independently expected value 5. It is separate from scored assessment; its algorithm family overlaps training. The native smoke uses this explicitly labelled demo to check executable generation and A/raw/A parameter restoration. This successful simple demo does not change the validation result of 2/10 or demonstrate general repair quality.

Weight SHA-256: `335fc22ddc8e9070a2359fa278c90e0cabdea0e31f16a4340524598abe0476d4`; tokenizer JSON: `7ea8bdf68c3e7549a3fb4342523288ce628f6ab56a618f9a4dfb234a0b4d46a8`. Other local hashes and A/raw/A parameter hashes are recorded in `artifacts/training/model-smoke.json`. The downloaded model license is MIT. No model switch occurred.

Native commands require local paths:

```sh
export CODEJURY_MODEL_DIR="$PWD/models/Phi4-mini"
export CODEJURY_ADAPTER_DIR="$PWD/artifacts/training/fixer_a_selected"
python -m codejury.models.cli smoke --config config/model.yaml
CODEJURY_MODEL_TESTS=1 python -m pytest tests/test_model_views.py tests/test_model_adapter.py -q
```

The config keeps machine-specific directories unset. Missing weights/adapter/proof fail readiness; no automatic download or fixture inference is used. Re-running training must use a new output directory, since launcher/freeze refuse overwriting existing evidence.
