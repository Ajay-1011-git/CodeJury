# Fixer A native refresh

12 October 2026. The Stage 2 trainer now performs real MLX training rather than reporting prerequisites. This first refresh uses the existing authorized synthetic integer/list corpus: 80 records / 40 training bases and 20 records / 10 validation bases. Expanded domain/helper/student-error collection remains pending. Final assessment contents are never opened.

## Pipeline

Before native imports, the training child acquires the common ComputeLease. It verifies the frozen base, tokenizer, topology and complete initialization adapter tensor set. Only freshly exported local train.jsonl and valid.jsonl reach MLX-LM; no test file, remote dataset or full-manifest loader is used. The matching sandbox reference proof binds the actual exported examples. SFT targets must equal their sandbox-validated reference source.

Installed MLX-LM 0.32.0 train_model/load_dataset and TrainingCallback are used directly. The resume load is guarded by the exact runtime tensor-key/shape/dtype verifier. Every chat is checked with the actual native dataset processor: completion masking, runtime prefix equality and no truncation. Training metrics must be finite. The saved tensors must be finite and differ from initialization. The trainer exits before a fresh native runtime loads the saved adapter and compares its full parameter hash with the trained model, then generates an actual output.

The full run requires a successful matching 10–20-step pilot proof bound to recipe, source corpus, reference proof, public final seal, base/topology and initial adapter. It starts from the same retained A initialization with fresh optimizer state; it does not silently continue the pilot's optimizer. Logs, actual arguments, immutable session, split manifests, masking details and hashes are retained privately. Existing output directories are refused. On failure there is no promotion or automatic replay.

## Actual runs

Retained A initialization hash: 274fd6b1a4a9abd04a8a2d3e56cfbde765c81e71fdb230682f4bf66509605fb4. Last 4 Phi layers, rank8/scale16/dropout0, qkv/o projections, batch1, sequence cap768, gradient checkpointing, Adam learning rate0.00005, seed17. All 100 full chats passed the actual prefix/mask/no-truncation checks; maximum574 tokens.

| Run | Refresh updates | Peak MLX memory | Fresh reload |
|---|---:|---:|---|
| Pilot |20|3192.4 MB|Matching full parameter hash; actual output|
| Bounded full trial |100|3256.4 MB|Matching full parameter hash; actual output|

Pilot weights: 0f3519bfc6ed3cb70477b201f9bf2f672d3547e23f4616124da0297edeca3a00. Full step100: 784db8b11ff90aa2d84e3f883238b27a55f28db443da57df663d99f001cd1b5f. The candidate cards stay pilot_only; the separate selected card records completed training/limited validation. The trial length is bounded exploration, not a convergence guarantee. Loss reduction is not repair correctness.

Private artifacts are under artifacts/stage2_core/fixer-a-refresh/{pilot-seed17,full-seed17}. Adapter weights and private records are ignored by Git. Reproduction requires the verified local model/initial adapter registry and sandbox reference proof; another checkout must establish its own genuine prerequisites.

## Validation policy

Use all 20 authorized validation variants under identical frozen views, greedy decoding, seed17 and 1024 output tokens. Freeze each generation and visible-test answer before offline validation tests. Raw, retained A and new A checkpoints are assessed through the isolated runner. Variants share 10 bases; report both counts. Never call these final-benchmark results.

Checkpoint eligibility requires aggregate non-regression in solved count, incorrect acceptance and malformed output against retained A. Rank eligible checkpoints by solved count descending, then incorrect acceptance, malformed output and input/output token cost ascending. Exact ties preserve the earlier supplied checkpoint. Record paired lost successes separately. Training loss never ranks checkpoints. Selection exports a compatible frozen registry/card with the limited evaluation scope; it does not declare expanded Stage 2 learning or the complete application finished.

Actual results, identical 20 variants / 10 bases:

| Method |Solved|Accepted|Incorrect accepted|Malformed|Output tokens|Generation ms|
|---|---:|---:|---:|---:|---:|---:|
| Raw |0/20|0|0|20|2514|59744|
| Retained Stage 1 A |3/20|4|1|4|3380|80495|
| Refresh step50 |4/20|4|0|1|1546|41718|
| Refresh step100 |5/20|5|0|1|2484|57448|

All methods consumed 8298 input tokens. Isolated validation assessment used 40 function calls for raw/retained, 46 for step50 and 48 for step100. Step100 won the frozen ranking and is exported under artifacts/stage2_core/fixer-a-refresh/selected-seed17. The runtime now points at this selected registry. Aggregate counts improved, but two previously solved variants (one base) were lost; four variants (three bases) were gained. This is weak, limited evidence, not certification of a robust Stage 2 repair model. Earlier Stage 1 checkpoints and expanded domains remain pending.

Evidence report SHA256: retained 0a935d69481da0b3adacdce90cc0d5cb99d147d2e83ac49ed36823518758a731; step50 c5ab30c979f04060b7e101ffa5ddaed8c0eb14db541f0079ccf3df02855fd328; step100 20857f20acee66202d8c1cf8e55c20d984712e0293963b51bd7c9e7c760c3997. Actual native job evidence and the detailed paired selection remain private. Backend CPU suite:408 passed,9 hardware checks skipped; this pilot/training/reload and validation ran separately on the Mac.

Selected runtime registry hash: c0e942cb9a6f19fb43ac0d51f9e9f8c7d00612594076521231d5faf0bb9799b2. Actual raw/A/raw/A switching used one resident base and matched independent clean loads; context overflow refusal and cancellation also passed. Evidence: artifacts/stage2_core/fixer-a-refresh/selected-native-smoke.json. These are native integrity checks, not additional repair-quality measurements. B/Critic/Judge are absent, so complete Stage 2 readiness remains false.

## Reproduction

From backend; choose new output paths for repeated runs. To repeat the recorded initialization rather than refreshing the newly selected A again, set CODEJURY_STAGE2_MODEL_MANIFEST to the original local registry as below:

```sh
export CODEJURY_STAGE2_MODEL_MANIFEST=artifacts/stage2_core/model-registry-json-policy.json
python -m codejury.stage2_core.training_cli preflight --role fixer_a --config config/stage2_core/training/fixer_a.yaml
python -m codejury.stage2_core.training_cli train --role fixer_a --config config/stage2_core/training/fixer_a.yaml --phase pilot --out artifacts/stage2_core/fixer-a-refresh/pilot-fresh
python -m codejury.stage2_core.training_cli train --role fixer_a --config config/stage2_core/training/fixer_a.yaml --phase full --pilot-proof artifacts/stage2_core/fixer-a-refresh/pilot-fresh/report.json --out artifacts/stage2_core/fixer-a-refresh/full-fresh
python -m codejury.stage2_core.training_cli evaluate --role fixer_a --config config/stage2_core/training/fixer_a.yaml --all-variants --out artifacts/stage2_core/fixer-a-refresh/retained-fresh
python -m codejury.stage2_core.training_cli evaluate --role fixer_a --config config/stage2_core/training/fixer_a.yaml --registry artifacts/stage2_core/fixer-a-refresh/full-fresh/checkpoint-50/registry.json --all-variants --a-only --out artifacts/stage2_core/fixer-a-refresh/step50-fresh
python -m codejury.stage2_core.training_cli evaluate --role fixer_a --config config/stage2_core/training/fixer_a.yaml --registry artifacts/stage2_core/fixer-a-refresh/full-fresh/checkpoint-100/registry.json --all-variants --a-only --out artifacts/stage2_core/fixer-a-refresh/step100-fresh
python -m codejury.stage2_core.training_cli select --role fixer_a --config config/stage2_core/training/fixer_a.yaml --baseline artifacts/stage2_core/fixer-a-refresh/retained-fresh/report.json --candidate artifacts/stage2_core/fixer-a-refresh/step50-fresh/report.json --candidate artifacts/stage2_core/fixer-a-refresh/step100-fresh/report.json --out artifacts/stage2_core/fixer-a-refresh/selected-fresh
```

Historical data-card.md diagnostics remain separate. B mining must use training problems and the actually selected A, never the validation failures above. The canonical A/B episode collector and later Judge/Critic/general training remain subsequent tasks.
