# A2.06 native B training and complementarity

Status: genuine train-only selected-A failure mining, separate B pilot/full training, alpha/view controls and executable checkpoint selection completed on this Mac. This is limited synthetic-corpus evidence. The first real fixed-controller episode pilot is now described in [controller.md](controller.md). It remains limited by invalid raw Critic proposals; this file does not claim a final benchmark.

The public final seal is verified before learning using metadata only. Selected A is the actual 100-step refresh, hash784db8b11ff90aa2d84e3f883238b27a55f28db443da57df663d99f001cd1b5f. Its limited validation is documented in a-training.md. No private final contents are opened.

Failure fractions require exactly three fixed seeds (17, 29, 41) per training base, frozen A adapter/config identity, strict ModelResponse and answer hashes. Validation/final samples, duplicate/missing seeds, mixed fixture/native provenance and native errors mislabeled as student failures are refused. Infrastructure-affected bases require replay and receive no failure fraction. The sampler requires live measurements for every training base and cannot export a plan from fixture-mode evidence.

Focused weights are 1 + alpha * failure_fraction, with real validation trials still required for alpha 0/1/2/4. Bases are sampled before variants so variant counts do not create accidental extra weight. A deterministic broad stratum stays within 25–50% even for small sample counts. B receives only the established independent contract/interface/test view; neither buggy bodies nor A output enters its prompt. Offline reference targets remain explicit training targets. Alpha=0 and same-view comparisons require actual separate jobs; labels in a sampling plan do not claim these controls were trained.

## Actual train-only mining

120 actual A generations, seeds17/29/41 on each of40training bases, first sorted corruption per base.78/120trials solved,14/40bases failed all repeats,9malformed trials,0incorrect acceptances,378isolated function calls. Greedy decoding made the three trials deterministic repeats; they are not120independent problems or stochastic failure estimates. Each generation and visible answer was frozen before offline TRAINING assessment. These private samples are not canonical EpisodeBundles and are not sent to Critic training as completed E2 episodes.

Mining is bound to A/base/config/source/public-seal identities. Training re-joins all sample files, runtime prompts, generations, answer hashes and actual assessments before computing fractions. Validation/final failures cannot be added. Infrastructure interruption prevents a completed measurement and requires an explicit fresh collection; no fabricated semantic failure or automatic replay.

## Native B pipeline

B starts from fresh seeded LoRA on the common frozen raw base. A weights are not loaded into the B training model. Topology matches A: last4layers,qkv/o,rank8/scale16/dropout0. MLX-LM uses Adam0.0001,batch1,gradient checkpointing,max sequence768,seed17. The shared native trainer acquires the common compute lease before native imports; it checks masking/prefix/truncation, finite metrics/tensors, actual parameter changes, save and fresh-process parameter-hash equality.

Alpha2pilot completed20actual updates and fresh reload; peak3194.3MB. Its160sampled training records represent62unique existing records /37bases, with40broad samples (25%). Max tokenized chat504. The bounded200-step alpha2job also completed genuine updates and reload; peak3196.1MB. Weighted repetitions are not new corpus examples. Every changed alpha/view job requires its own matching real pilot; no fake pilot bypass.

B's independent prompt omits buggy code and A responses. Its target rationale refers only to reconstructing the visible approved contract; it does not pretend to diagnose a hidden corruption. Reference target sources are exactly those already validated in the sandbox. Validation uses all20variants /10bases. A's existing frozen one-shot validation can be reused only with matching data,adapter,view,seed and output cap; B receives none of those outputs or offline outcomes.

The experiment runs alpha2/0/1/4 sequentially, saves100/200-step candidates and validates each through Docker. Selection ranks incorrect acceptance ascending, union solved descending, B standalone solved descending, malformed ascending and token cost ascending. It then requires a genuinely trained/validated A-view B control with the selected weighting. Loss/disagreement do not rank checkpoints. Report union/rescue as available candidates, not controller final-answer quality. Control training costs are included in the audit, rather than implying identical training opportunity.

## Measured validation and selected checkpoint

All comparisons use the same 20 variants / 10 validation bases, seed17, greedy decoding and 1024-token caps. A's selected one-shot result is5/20solved. Each row below is a genuine separate trained checkpoint; B receives no A response.

| View |Alpha|Step|B solved|A/B union|A failures rescued|Incorrect accepted|Malformed|
|---|---:|---:|---:|---:|---:|---:|---:|
| Independent |0|100|2|7|2/15|2|1|
| Independent |0|200|3|8|3/15|0|1|
| Independent |1|100|6|9|4/15|0|3|
| Independent |1|200|4|9|4/15|0|4|
| Independent |2|100|4|9|4/15|0|3|
| Independent |2|200|4|9|4/15|0|3|
| Independent |4|100|2|7|2/15|0|7|
| **Independent, selected** |**4**|**200**|**5**|**10**|**5/15**|**0**|**5**|
| A view control |4|100|2|6|1/15|2|3|
| A view control |4|200|3|6|1/15|1|1|

Selected B hash:f62d5e7ed4322e956f4ac2fb3e2032463103822fcc872494c08f8a82af56b404. A/B registry hash:7e93cae723e1d0be7e6201a4c10ae2148a3b428f901e02985aa8134760b1b5d1. The runtime points at artifacts/stage2_core/fixer-b-training/selected/registry.json. The selected A/B cards describe completed real training and measured limited validation; Critic/Judge and complete system readiness remain pending.

Selected B has160weighted records,58unique imported records /37training bases and25%broad samples. Its validation used7540input /3319output tokens. The selected B and A successes have zero overlap: B rescues5of15A-failed variants (33.3%), leaving10joint failures. This is finite candidate-availability support, not final selection accuracy. Five B outputs were invalid; domain/helper/natural-error expansion remains pending. The same-view control did worse on this small pool, but this does not establish a broad or statistically secure result.

Actual offline training cost: five20-step pilots plus five200-step full jobs,1100updates total,999.8seconds summed trainer/save/reload wall time, peak3258.2MBMLXmemory. This excludes mining and executable validation; full logs retain each job's actual token/loss/cost records. All five jobs have separately verified actual updates and fresh parameter-hash equality. Weighted alpha0/1/2/4 pools cover39/39/37/37training bases and69/68/62/58unique records respectively; repeated samples never count as new bases.

Private evidence is under artifacts/stage2_core/fixer-b-training: mining-selected-a, all alpha/view pilot/full jobs, ten validation reports, selected/selection.json and experiment.json. Selected validation report SHA256:32f4f49dd71eed609afc4b38b3b6b7ac58744df319a48b3a1fee44ef0319223e. The schema-valid fixer_adapters handoff is selected/exchange/manifest.json with actual A/B weights/configs/freezes, split=none and no final contents. No weights or private records are pushed to Git.

The first orchestration process had loaded an incorrect handoff split label and rejected that metadata export after training/validation/selection. The exporter was corrected to the frozen split=none enum. finalize-b reverified all ten reports, actual job/adapter/config hashes and matching partial handoff bytes before completing the manifest. No training or validation was replayed and no evidence file was overwritten.

## Reproduction

From backend, with actual selected A/model/reference proof and isolated Docker ready; use new output paths for repeats:

```sh
python -m codejury.stage2_core.training_cli mine-b --config config/stage2_core/training/fixer_b.yaml --out artifacts/stage2_core/fixer-b-training/mining-fresh
python -m codejury.stage2_core.training_cli experiment-b --config config/stage2_core/training/fixer_b.yaml --mining-report artifacts/stage2_core/fixer-b-training/mining-fresh/report.json --baseline artifacts/stage2_core/fixer-a-refresh/validation-step100/report.json --out artifacts/stage2_core/fixer-b-training/fresh-experiment
python -m pytest tests/stage2_core/test_b_training.py -q
```

Individual train/evaluate/select commands are also implemented. Existing incomplete native jobs fail closed and are not replayed. An interrupted handoff export may be completed with export-fixers after matching actual selected adapter hashes; existing conflicting bytes or a completed manifest are refused. Weights/private sampling records/assessment evidence stay ignored by Git. CPU tests are provenance/arithmetic/boundary checks and never native learning evidence.

finalize-b verifies a completed selection and can finish a metadata-only interrupted export. CPU suite:412passed,9hardware checks skipped. Genuine native pilot/full/save/reload, mining and validation above ran separately; the skip count does not stand in for native execution.

Selected native integrity smoke passed raw/A/B/raw/B/A with one resident base, distinct role parameters, repeated outputs matching independent clean loads, context overflow refusal and cancellation. Evidence:selected-native-smoke.json. Actual raw/A/B are available with completed A/B cards; Critic/Judge are missing, so complete Stage 2 readiness remains false. The public-sum smoke is an integrity check and is not another repair score.

Earlier preparation-only counts are superseded by the native evidence above. B/Critic/Judge/application/final research readiness must still follow the measured dependency gates; genuine small-pool training does not imply broad mastery.
