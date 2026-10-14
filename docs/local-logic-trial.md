# Bounded local logic training trial

14 October 2026. The local trial completed after the 900-run development baseline
was documented and committed as `db0c907`. **The existing Fixer A adapter was
retained.** Both new checkpoints accepted more wrong repairs during validation.

## Data and recipe

- 45 training variants across 24 existing train bases: 39 two-site corruptions and
  six single-site corruptions. No new base identities were invented.
- Separate validation: 20 variants across ten existing validation bases.
- 2,016 Docker function calls checked the initially generated references and bugs.
  Rejections were counted, including 88 overlapping mutation plans and four bugs
  surviving their offline tests. A conservative near-AST guard then excluded all
  variants of six train bases; the initial export was never used for training.
- Final corpus: `backend/artifacts/stage2_core/logic-training/corpus-v8/`.
  Its manifest hash, file hashes and negative overlap proof remain in the export.
  No development examples, outputs or repairs entered training; the overlap guard
  used only identity/family/reference-AST fields to reject train bases.
- Frozen Phi-4-mini base and v1 rank-eight, four-layer attention LoRA topology.
  Other role adapters were unchanged. This is not the deferred v2 all-linear,
  rank/learning-rate sweep or four-role retraining campaign.
- Ten pilot steps, 100 full steps, checkpoints at 50/100, batch one, sequence limit
  2048, learning rate 0.00005, gradient checkpointing, seed 17. Full training starts
  from the retained A adapter, rather than continuing the pilot's updates.
- All 65 examples passed the installed tokenizer/masking processor preflight;
  maximum full length 608 tokens and maximum prompt length 480.

## Native proof and validation

Both phases verified actual parameter updates and a fresh reload. The pilot took
38.11 seconds; full training and its verification took 100.37 seconds. Peak MLX
allocation for full training was 3,302.64 MB. These measurements exclude the later
repair validation and do not measure total system or Docker VM peak memory.

| Executed validation | Solved / variants | Accepted | Incorrect accepted | Malformed |
| --- | --- | --- | --- | --- |
| Retained A | 5/20 | 5 | 0 | 1 |
| Step 50 | 2/20 | 4 | 2 | 0 |
| Step 100 | 5/20 | 7 | 2 | 0 |

The 20 variants share ten base problems. They are not 20 independent problems.
The non-regression gate requires no fewer solved repairs, no more incorrect
acceptances and no more malformed outputs. Both trained checkpoints fail that
gate. Selection used executed correctness and then format/cost, never training
loss. Better formatting alone was insufficient.

The native logs, mask audits, update/reload proofs, checkpoints and all three
validation reports remain under
`backend/artifacts/stage2_core/logic-training/trial-v5/`. They are local ignored
artifacts; no weights or private corpora were added to Git. No model/dataset was
downloaded and no cloud teacher was used. The sealed final assessment stayed shut.

## Separate revision diagnostic: not adopted

The predeclared 12-base, three-seed diagnostic uses retained A weights and the
`stage2.views.v2-concrete-failure` view. It adds the first registered execution or
input-purity failure to the revision prompt, preserves unknown property
expectations, and refuses byte-identical revisions before committing or executing
them. Model attempts and tokens remain charged.

This measures the revision change; it cannot be described as a gain from adopting
the trained checkpoints. It compares the same 36 jury runs with their frozen
baseline counterparts. Each seed/tier must avoid losing solved count or gaining
wrong acceptance before adoption. Per-seed Wilson intervals keep the denominator
at 12 bases, or six per tier. All 36 runs completed. The change failed its per-seed/tier gate and the original
`stage2.views.v1` runtime was restored. It establishes no full 100-base improvement.

The [bounded route](bounded-local-route.md) records scope and deadlines. The full
[baseline measurements](dev-bench-baselines.md) remain separate from this trial.


| Seed | Before solved / 12 | After solved / 12 | Before / after incorrect accepted |
| --- | --- | --- | --- |
| 17 | 4/12 | 4/12 | 0 / 1 |
| 29 | 4/12 | 3/12 | 1 / 0 |
| 43 | 3/12 | 4/12 | 1 / 1 |

The combined solved total is 11/36 in each condition, and incorrect acceptance is
2/36 in each condition. Those aggregate counts conceal a lost T2 success for seed
29 and a new T3 wrong acceptance for seed 17. The declared gate rejects both.
Seed 43 gains one T2 success, which does not justify overlooking the other losses.

Per-seed all-tier Wilson 95% intervals are 13.8–60.9% for 4/12 and 8.9–53.2% for
3/12. Six-base tier intervals and all paired transitions are in the
[diagnostic record](experiments/revision-diagnostic.json). Repeated seeds never
increase the independent denominator to 36. No causal improvement is claimed.

The [experimental patch](experiments/concrete-failure-v2.patch) is retained for
review and reproduction, with its supporting projection helper. It is **unapplied**
and not the app default. To reproduce locally, apply it to this source revision,
then use `backend/tools/logic_trial_diagnostic.py` with the retained full baseline
and executed selection report. Private source snapshots and ledgers remain in the
original diagnostic directory. The current app retains its previous revisions
and adapters; only the reviewed intake and conversation work is delivered.
