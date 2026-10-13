# Critic native training checkpoint

The 20-step pilot completed on the Mac with the inspected MLX 0.32.3 / MLX-LM 0.32.0 interfaces. It starts a fresh rank-8 LoRA from the same frozen 4-bit Phi-4-mini base as A/B, using the same four last-layer qkv/o targets. It does not inherit A's weights. Actual nonzero updates, finite tensors, prompt masking, exact runtime chat prefixes and checkpoint topology were checked. All 400 learning rows fit without token truncation; maximum encoded sequence was 3,322 tokens.

The pilot saved 16 adapter tensors and reloaded matching complete parameters in a fresh native process. Adapter SHA-256: `37383b714e8c3254c308fbcae135c575dc93e461191b9a2a2b60c8790398e997`. Peak memory: 6,139.7 MB. Pilot time including fresh reload: 341.0 seconds. There were 2,494 actual trained completion tokens in 20 optimizer updates. The exclusive compute lease covers training and native reload.

The full 100-update job completed and reloaded matching parameters in a fresh process. It trained 12,614 completion tokens in 100 actual optimizer updates, took 773.3 seconds including reload and peaked at 6,277.3 MB. The final checkpoint SHA-256 is `e835ddab982995663e4ad7e7a0e32e391c6aa28ec22c5589943b55efcabb74de`. Checkpoints at 50 and 100 now await measured format/domain validity, authorized failure yield, false hard rejection and cost selection. This document does not mark the Critic completed. Loss alone cannot select a release. A/B registry entries are retained when the new role is registered.

The [data limitations](critic-data.md) apply, including missing feedback-revision contexts. Weights, private labels and detailed validation receipts remain outside Git. There is no final benchmark claim.
