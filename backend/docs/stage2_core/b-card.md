# A2.06 B preparation checkpoint

Status: weighting and sampling controls implemented and CPU-audited. No native train-only A failure mining, B pilot, B training, adapter reload, rescue comparison, or trained B AdapterCard exists. A2.06 is not complete.

Failure fractions require exactly three fixed seeds (17, 29, 41) per training base, frozen A adapter/config identity, strict ModelResponse and answer hashes. Validation/final samples, duplicate/missing seeds, mixed fixture/native provenance and native errors mislabeled as student failures are refused. Infrastructure-affected bases require replay and receive no failure fraction. The sampler requires live measurements for every training base and cannot export a plan from fixture-mode evidence.

Focused weights are 1 + alpha * failure_fraction, with real validation trials still required for alpha 0/1/2/4. Bases are sampled before variants so variant counts do not create accidental extra weight. A deterministic broad stratum stays within 25–50% even for small sample counts. B receives only the established independent contract/interface/test view; neither buggy bodies nor A output enters its prompt. Offline reference targets remain explicit training targets. Alpha=0 and same-view comparisons require actual separate jobs; labels in a sampling plan do not claim these controls were trained.

The existing A diagnostic does not select an A checkpoint, and Sarvesh's new final-pool seal is absent. These prerequisites block genuine mining/training and E2 fixed-policy acceptance. No fake episodes were generated to bypass them. CPU tests use synthetic records solely for arithmetic/provenance/view checks and are never learning evidence.

Verification: `python -m pytest tests/stage2_core/test_b_training.py -q`: 15 passed. Combined CPU suite after A2.04/A2.05/B preparation: 227 passed, 9 hardware/sandbox skips. Actual A validation and reference sandbox runs are reported separately in data-card.md.
