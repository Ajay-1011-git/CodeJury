# A2.05 data and A validation checkpoint

Status: curation, native diagnostics and genuine A refresh are implemented. A 20-step pilot and bounded 100-step refresh have run with actual updates, save and fresh-process reload. Executable checkpoint selection and expanded Stage 2 learning are audited separately in [a-training.md](a-training.md).

Integration update, 12 October: Sarvesh's public `data/stage2_tools/manifests/stage2.json` is now adopted by the core. Its inherited final seal contains 10 bases / 19 records. The earlier absent-exchange-path blocker below is historical and resolved; private final verification/results and refreshed training remain pending. See integration/stage2/HANDOFF.md.

## Actual pools and provenance

The frozen Stage 1 manifest contains 80 training records / 40 bases / 8 families and 20 validation records / 10 bases / 2 families. Only those two allowlisted files are opened. Original assessment and Stage 2 final asset entries are filtered before any content access. Sarvesh's public Stage 2 seal is now verified before training; private final contents remain unopened.

All imported examples are project-authored synthetic bugs, with the original license string retained: repository redistribution license not declared. No external/student mistakes or expanded boolean/string/dictionary/helper pool is claimed. Family/base and identifier-normalized reference ASTs are disjoint across train/validation. Runtime problem fingerprints also include contract/domain: a common `return 0` corruption alone is not treated as a shared intended problem. This does not prove semantic independence of every possible near-duplicate. SFT target source must exactly match the reference source verified in the sandbox.

Actual isolated reference validation passed 200 calls across 50 unique reference bundles, using visible and authorized offline validation cases. No submitted/reference code ran on the host. Separately hashed train and validation ArtifactManifests export records, provenance, independent B views and A SFT chats into ignored private artifacts. They contain reference targets for authorized offline learning, without final tests or runtime exposure. Export requires matching successful sandbox evidence.

## Native evidence

Installed MLX-LM 0.32.0's actual ChatDataset.process checked all 100 converted chats, with completion masking enabled. Runtime prompt tokens exactly matched the training prefix. Maximum full example was 574 tokens: no completion truncation at 768 or the Stage 2 4096 context. The output target expands the Stage 1 three-field repair to the six-field Stage 2 RepairDraft; its system/user prompts also change. The retained A was trained on the old contract, so successful reload alone does not establish Stage 2 readiness.

Native diagnostic used one fixed corruption per each of 10 validation bases, seed 17, identical A runtime views, greedy decoding and 1024-token caps. Answers were frozen before offline candidate assessment. One resident base switched raw/A; adapter identity was checked by the actual registry/worker.

| Method | Solved | Accepted | Incorrect accepted | Malformed |
|---|---:|---:|---:|---:|
| Raw | 0/10 | 0 | 0 | 10 |
| Retained A | 1/10 | 1 | 0 | 1 |

Raw input/output tokens: 4155/1261, generation time 28,027 ms, peak 2769 MB. A: 4155/1669, 36,560 ms, peak 2840 MB. Candidate assessment used another 20 sandbox function calls. These are actual limited validation measurements, not a final benchmark, non-regression certification, or evidence of a strong repair system. Earlier A checkpoints and the other 10 validation variants remain unmeasured in Stage 2. No checkpoint was selected from these results or from loss.

Private evidence: artifacts/stage2_core/fixer-a-validation/native-v3/report.json. Registry hash: 94b04c2bfe86fbadd817324144df6e14193035f0815b165c271b3b6280ec4b7a. Source manifest hash: 37131bb3ccc0011c65f822475183ab5a878044d33e60fc060c891797459eb17d.

Earlier diagnostics remain unchanged with audit notes. Initial mask preflight used AutoTokenizer's dictionary return type; setting return_dict=False aligned the probe with the inspected MLX wrapper. Native-v2 incorrectly required every requirement ID in a draft; the frozen runtime permits a unique known subset. Native-v3 aligns with that rule and repeats the paired diagnostic. Native-v2's quality counts must not be used.

## Reproduction and remaining work

From backend, with the existing native model/adapter and dedicated Docker VM:

```sh
python -m codejury.stage2_core.data_cli validate --config config/stage2_core/training/fixer_a.yaml
python -m codejury.stage2_core.data_cli validate --config config/stage2_core/training/fixer_a.yaml --sandbox
python -m codejury.stage2_core.data_cli export --config config/stage2_core/training/fixer_a.yaml --verified-report artifacts/stage2_core/fixer-a-validation/data-sandbox.json --out artifacts/stage2_core/fixer-a-validation/pools
python -m codejury.stage2_core.training_cli evaluate --role fixer_a --config config/stage2_core/training/fixer_a.yaml --out artifacts/stage2_core/fixer-a-validation/native-fresh
python -m pytest tests/stage2_core/test_corpus.py -q
```

Commands refuse to overwrite evidence; use a fresh --out path for repeats. CPU data checks do not execute references. The train command now runs an explicit pilot or gated full refresh using the approved integer/list pools. The partner public seal is verified from metadata before learning. Full training requires a matching native pilot/save/reload proof; any promoted checkpoint requires executable validation. Expanded reviewed pools remain pending. Learning, B mining and final evaluation must not substitute fixtures or these validation failures for training failures. See a-training.md for the new commands and measurements.

API patterns were checked against installed source and official [MLX datasets](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/datasets.py), [tokenizer wrapper](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tokenizer_utils.py), and [LoRA entrypoint](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/lora.py).
