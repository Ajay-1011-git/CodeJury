# Bounded local improvement route

The user limited this work to a route taking at most 7–8 hours and chose local
training if moving to Colab would not shorten it. Work on this route began on
14 October 2026 at 17:09 IST; the eight-hour boundary is 01:09 IST on 15 October.

## Scope

1. Complete the independently authored 100-base, three-method, three-seed native
   development baseline already running. Keep the controller, adapters, prompts
   and registry frozen throughout that baseline.
2. Deliver Quick case with a reviewed draft and explicit **Approve all** as the
   default. Interpreter trust remains off until the user explicitly selects it.
3. Show the actual jury conversation, with concrete execution evidence, parent
   diffs, and the existing timeline alternative.
4. Prepare an execution-filtered corpus of multi-line, composed logic mutations
   using existing training identities. Run a bounded local Fixer A refresh trial
   after the baseline releases native compute, with a verified pilot and fresh
   reload. Preserve the existing base, topology and all other role adapters.
5. Validate the trial by execution; report any measured diagnostic improvement
   separately from the full baseline. Retain the current adapter unless the trial
   meets the declared validation gate.

The post-training jury diagnostic is declared before baseline hidden outcomes are
inspected: `balanced_parentheses`, `transpose_ragged`, `chunk_list`,
`interleave_unequal`, `sliding_window_sums`, `word_frequencies` (six T2 bases), and
`bracket_types`, `edit_distance`, `max_subarray`, `interval_union`,
`three_sum_unique`, `grid_paths` (six T3 bases). Seeds are 17, 29 and 43. This is a
12-base diagnostic, not a replacement for the 100-base baseline. Report per-seed
Wilson intervals without treating three seeds as 36 independent base problems.
Changing the app's default adapter also requires no lower solved count or higher
wrong acceptance on this paired diagnostic. A failure keeps the existing default.

This narrows the original roadmap. Model downloads, the v2 architecture bake-off,
rank 16/32 and learning-rate sweeps, a full four-role retraining campaign, stochastic
resampling and Critic ablations are deferred. This route does not claim acceptance
of those phases. A full minimal-input accuracy comparison also remains unmeasured;
the currently configured interpreter attempt limit cannot cover 100 problems.

## Why local

The current pipeline trains MLX adapters on Apple silicon. Existing native reports
recorded 100 Fixer A steps in 98.35 seconds, 200 Fixer B steps in 158.34 seconds,
100 Critic steps in 773.32 seconds, and 100 Judge steps in 370.00 seconds. These are
historical measurements for the old corpora, not forecasts for the new trial.

The long running job is **evaluation**, not training. MLX also has a supported
[CUDA backend](https://github.com/ml-explore/mlx/blob/main/docs/src/install.rst),
so a PyTorch/PEFT conversion is not inherently necessary. A Colab route still
needs target-GPU setup and compatibility checks, asset transfer and local adapter
reload/selection validation. No Colab GPU was measured. Google states that available GPU types and
runtime limits vary in its [Colab FAQ](https://research.google.com/colaboratory/faq.html).
The existing [MLX-LM pipeline](https://github.com/ml-explore/mlx-lm) is already native
to this machine. This is an end-to-end time decision, not a claim that the Mac
outperforms every Colab GPU.

## Data boundaries

The new corpus uses only the inherited `train` base identities and families.
Existing validation stays separate. Its builder opens only the allowlisted
train/validation source assets through `load_stage1`; assessment and final entries
are filtered before any content is opened. It does not consume development
benchmark problems, tests, outputs or repairs. References and buggy variants run
only in Docker. Each retained bug must fail at least one offline test, and each
procedural target must match independently authored cases and the inherited
reference on deterministic extra inputs. Rejections remain counted. Function
names vary by train identity, with matching buggy/target interfaces. The inherited
Stage 1 validator still requires `solve`: a canonical-name copy passes that
unchanged validator, while the actual named implementations pass Docker checks.

Corpus files and weights stay in ignored local artifacts. No Google Drive upload
or Colab conversion is needed for the chosen route. No new model or dataset is
downloaded, and the sealed assessment remains unopened.

## Status

The initial Docker-filtered corpus contained 57 records across 30 train bases.
The user reaffirmed on 14 October that the full baseline takes priority and the
local training trial should run only if time remains. An interrupted baseline
resumed from 679 preserved selections under the same protocol; its interrupted
queue was retained and replaced by `trial-v5`, without starting training. A
guard stops matching task-owned compute at 00:50 IST on 15 October, leaving 19
minutes to finalize within the eight-hour boundary.

A second normalized-AST overlap guard conservatively excluded all variants of
six bases: `square_total`, `remove_endpoints`, `positive_values`,
`above_threshold`, `without_zero`, and `negative_positions`. These are different
semantic problems, but their procedural implementations crossed the same 0.90
similarity threshold used by the development benchmark. No development problem
was changed or removed. No model was trained on the initial export.

The final training corpus contains **45 records across 24 train bases**, with **39
composed** two-site corruptions and six single-site corruptions. The separate
validation pool retains its 20 records across 10 bases. Docker validation made
2,016 function calls. The builder counted 88 overlapping mutation plans rejected
before execution and four variants that survived the offline tests.

The immutable local export is at
`backend/artifacts/stage2_core/logic-training/corpus-v8/`. Its negative overlap
guard uses only development identity/family/reference-AST fields to reject train
bases; function names are canonicalized so interface renaming cannot bypass the
similarity gate. No development test values, outputs or repairs enter the training export.
The retained subset has zero exact, family or near-AST overlaps. Training ran in
`backend/artifacts/stage2_core/logic-training/trial-v5/` after the completed,
documented and committed 900-result baseline (`db0c907`). Recipe: ten pilot steps, 100 full steps, checkpoints at 50
and 100, batch one, sequence limit 2048, learning rate 0.00005, gradient
checkpointing, seed 17. Both phases start from the retained A adapter; the full
phase does not continue the pilot's exploratory updates. All native jobs stay
sequential. The queue refuses to start after 19:00 UTC, leaving time before the
eight-hour boundary to report results.

The native pilot completed ten updates with a verified fresh reload in 38.11
seconds. Full training completed 100 updates with a verified fresh reload in
100.37 seconds. Full-training peak MLX allocation was 3,302.64 MB; total system
and VM peak remain unmeasured. These are actual new-trial timings, including the
trainer's verification work, not forecasts or evidence of repair improvement.

Executed validation used all 20 variants across ten existing validation bases:

| Adapter | Solved / variants | Incorrect accepted | Malformed |
| --- | --- | --- | --- |
| Retained A | 5/20 | 0 | 1 |
| Step 50 | 2/20 | 2 | 0 |
| Step 100 | 5/20 | 2 | 0 |

Both new checkpoints fail the declared non-regression gate. The selector retained
the existing A weights. Lower training loss and better formatting did not justify
accepting more wrong repairs. The separate 12-base, three-seed diagnostic therefore
measures the concrete-failure revision change with the retained adapter; it does
not measure an adopted new training checkpoint. It failed the declared per-seed/tier gate: seed 29 lost a T2 success and seed 17 gained a wrong acceptance. The prior revision runtime was restored. See [trial and diagnostic results](local-logic-trial.md).

A tokenizer-only preflight checked all 65 train/validation examples through the
installed `ChatDataset.process` and the local frozen tokenizer: the longest complete example is 608 tokens and the longest
prompt is 480, within the declared 2,048-token training limit and runtime reserve.
This check loads no model weights and does not replace the native mask/update/
reload checks required by the trial. The paired diagnostic also rejects any
per-seed or per-tier loss of successes or increase in wrong acceptance, even when
the overall total improves.

Corpus generation is reproducible with:

```sh
backend/.venv/bin/python backend/tools/build_logic_corpus.py --out backend/artifacts/stage2_core/logic-training/corpus-new
backend/.venv/bin/python backend/tools/filter_logic_corpus.py --source backend/artifacts/stage2_core/logic-training/corpus-new --out backend/artifacts/stage2_core/logic-training/corpus-filtered
```

The full baseline, local training trial and paired revision diagnostic are complete.
Neither trained checkpoint nor the revision change passed its adoption gate. The
prior inference runtime and weights remain active. Two genuine Quick case runs
verified reviewed approval, local inference, Docker execution and final conversation
display: one supported patch and one unresolved Critic refusal. Evidence chips
opened the exact execution cell. These unscored mechanics checks are documented
in [Quick case and conversation evidence](quick-case-conversation.md); no repair-accuracy
improvement is claimed.

Training, evaluation, live UI checks and the final test suites were complete by
00:32 IST on 15 October, about 7 hours 23 minutes after the bounded route began.
No remaining training or evaluation job is queued for this route. The local dashboard preview
remains available; the compute cutoff guard was stopped after all owned jobs
finished.
