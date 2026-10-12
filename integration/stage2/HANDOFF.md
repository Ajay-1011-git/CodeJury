# Stage 2 Mac integration and learning handoff

12 October 2026. Sarvesh's `stage2/sarvesh-tools` through 9e72c1d is integrated with Ajay's core through 056a05d. The subsequent integration/training commits add actual native tool checks and a genuine A refresh; this is not completion of Stage 2 learning or the final application. Current A evidence and commands are in [a-training.md](../../backend/docs/stage2_core/a-training.md).

## What the reported blockers mean

| Task | Actual remaining dependency |
|---|---|
| S2.07 | Ajay must supply canonical train-only EpisodeBundles from genuinely selected A/B and the real tools, with compatible manifests. |
| S2.08 | Execution-filtered Critic data, then a real pilot/train/save/reload/validation run. MLX execution can happen on this Mac. |
| S2.10 | Frozen training sources for A/B/Critic/Judge, opportunity-parity audit and genuine general-adapter training. |
| S2.12 | All learned roles, comparator and application must be frozen before the real final benchmark. This comes last; it is not a prerequisite to write/train the Critic. |

Sarvesh's earlier audit described his checkout: no MLX or reachable Docker daemon. This Mac has both. His choice not to invent unavailable training interfaces was correct. The installed native APIs are now inspected and recorded; trainers/data/role acceptance still need implementation and execution.

## Verified native environment and interfaces

- macOS ARM64; Python 3.11.16, MLX 0.32.3, MLX-LM 0.32.0, Transformers 5.19.0; Metal is available.
- The actual retained A validation already loaded weights and switched raw/A in one resident base (data-card.md): raw 0/10, A 1/10 solved on a limited one-seed validation diagnostic. This is not a selected Stage 2 A/B release.
- Subsequent genuine A refresh selection used all 20 authorized validation variants / 10 bases: raw0/20, retained A3/20 (1 incorrect acceptance), refresh50 4/20, refresh100 5/20 (both0 incorrect acceptances). The selected100-step adapter hash is 784db8b11ff90aa2d84e3f883238b27a55f28db443da57df663d99f001cd1b5f; runtime points to its private selected registry. It loses two formerly solved variants despite the aggregate gain. This is limited synthetic evidence; B and real A/B episodes remain pending.
- The global `codejury.stage2_core.leases.ComputeLease` must cover standalone training, teachers and model benchmarks as well as inference. It defaults to one per-user /private/tmp lock shared across clones. Do not invent a second independent lock or run concurrent native jobs on this 16 GB profile.
- Actual installed signatures: `train_model(args, model, train_set, valid_set, training_callback=None)`, `load_dataset(args, tokenizer)`, `ChatDataset(data, tokenizer, chat_key='messages', mask_prompt=False)`, `linear_to_lora_layers(model, num_layers, config, use_dora=False)`, `load_adapters(model, adapter_path)`, `remove_lora_layers(model)`.
- The real parser exposes --train, --mask-prompt, --num-layers, --fine-tune-type, --iters, --max-seq-length, --adapter-path, --grad-checkpoint and --seed. Verified complete prompt/completion masking in 100 converted chats, using the actual installed ChatDataset; no completion truncation, maximum 574 tokens.
- Phi3 conversion, 32 layers, 4-bit affine/group64. Existing common LoRA uses the last 4 layers, self_attn.qkv_proj/self_attn.o_proj, rank8/scale16/dropout0. Registry checks exact base/tokenizer/quantization/topology and all adapter tensor keys/shapes; save/reload must be verified for every new trained role.
- `inspect_mlx.py` imports and records interfaces/Metal availability without loading a model or training. Its success is not a substitute for a native pilot. `training_cli train` now uses inspected native APIs: an actual 20-step A pilot and bounded 100-step refresh passed update/save/fresh-reload checks on this Mac, with peak MLX memory 3192.4/3256.4 MB. Executable checkpoint selection is documented separately; B/episodes/Judge remain pending. Do not use the old Stage 1 launcher to import the entire manifest into a Stage 2 learning job; consume only authorized train/validation artifact files.

The primary upstream sources are [MLX LoRA](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/lora.py), [training loop](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py), [datasets](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/datasets.py) and [adapter utilities](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/utils.py). Installed source and executed behavior govern this checkpoint.

## Real tool integration

The existing dedicated CodeJury ARM64 VM has no host directories or SSH-agent shares. Integration reuses that VM sequentially with a separate pinned Stage 2 image; Stage 1 code/config/image remain intact. Candidate execution is non-root, network-none, read-only, without mounts, with a 512 MB cgroup cap/64 pids and bounded watchdog/output.

Image: sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f. Runtime: c1e25f67d21b65c259f551de98578e1dacd2c297ae4c7b19b0c8b3b83f44fe8f.

Actual checks passed:

- Runner: 12 checks covering helpers, nested JSON, two-call relations, mutation, output overflow, infinite-loop timeout, memory containment, cancellation, network/mount denial, hardened flags and missing-image failure.
- Search: comparator repair, genuine two-edit/hash-chain case, single-edit insufficiency and caps.
- Auditor: weak-test survivor, distinguishing follow-up, unresolved-gap interpretation and caps.
- Live ToolPort evaluates 2 published fixture candidates; factory imports no test double.
- Core/ToolPort seam: real semantic receipts and sandbox outcomes settle in the immutable ledger, 2 calls charged exactly once, current-suite qualification passes for the fixture candidates. This generates no learned model outputs and is explicitly not a training episode.

The integration image uses CMD rather than an image ENTRYPOINT, because the runner supplies its fixed command and trusted network/isolation probes must replace it. A memory-limit probe killed by Docker produces an infrastructure exception, not invented semantic rows. The diagnostic now verifies actual OOMKilled state and VM readiness so that successful containment is not mislabeled as an unrun check.

## Corpus seal and episode status

The core now uses the benchmark owner's public stage2.json instead of looking for a nonexistent exchange filename. It verifies derivation/hash/counts and the unchanged inherited Stage 1 final seal using metadata only. Final assessment contains 10 bases / 19 records, below the 200-base collection goal; it remains limited evidence. Private final sources/tests are not runtime/training exports and the final benchmark has not run.

Integration exposed Python 3.12's empty type_params AST field changing public training-cluster hashes relative to 3.11. Normalization now removes only that empty metadata structurally. Public train cluster IDs were rebuilt from public training source only; private split hashes/counts and source bytes remain unchanged. The shipped-manifest CPU test uses a temporary public-only root and cannot inspect the real private holdout.

Ignored old artifacts in artifacts/stage2 contain episode.v1 A-only episodes and two-repeat Stage 1 train-failure mining. They are not canonical Stage 2 A/B EpisodeBundles or the required three-seed runtime-view measurements. They must not be relabeled or supplied to S2.07 as completed E2 evidence. FixtureHostSandbox tests are controlled CPU logic checks, not isolated execution or measured student failures.

## Reproduction

From backend, after the existing isolated VM is running:

```sh
python ../integration/stage2/build_runner.py
# Use the actual image ID printed by that build; the verified ID for this checkpoint is:
export CODEJURY_STAGE2_RUNNER_IMAGE=sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f
python ../integration/stage2/inspect_mlx.py --out artifacts/stage2-integration/mlx-interfaces-fresh.json
python -m codejury.stage2_tools.runner_cli self-test --config ../integration/stage2/runner.yaml --out artifacts/stage2-integration/runner-fresh
python -m codejury.stage2_tools.search_cli self-test --config ../integration/stage2/search.yaml --out artifacts/stage2-integration/search-fresh
python -m codejury.stage2_tools.audit_cli self-test --config ../integration/stage2/auditor.yaml --out artifacts/stage2-integration/auditor-fresh
python -m codejury.stage2_tools.cli self-test --config ../integration/stage2/tools.yaml --out artifacts/stage2-integration/tool-port-fresh
python ../integration/stage2/seam_check.py --config ../integration/stage2/tools.yaml --out artifacts/stage2-integration/seam-fresh.json
python -m pytest -q
```

Merged CPU suite: 396 passed / 9 hardware checks skipped. Actual native checks above ran separately. Stage 2 JS: 35 passed; 49 UI fixtures validated. Test-module imports were namespaced to keep both Stage 1 and Stage 2 collection working. No dependency/lock/schema/port/fixture changes. No weights, private episodes or hidden assessment sources are pushed to Git.

Next dependency chain: finish A validation/refresh and selected A freeze → three actual train-only generations/base → separate B pilot/training/reload/paired validation → fixed controller and real canonical EpisodeBundles → S2.07/S2.08 and Judge training → fair general comparator → frozen final benchmark. Passing the current tool checks does not waive these gates.
