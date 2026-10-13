# Critic data pipeline (S2.07)

Status: pipeline and tests done on synthetic fixtures. **No real data has been collected**: there are
no E2 TRAINING episodes on this branch, so every real count below is "not measured".

## What it does
`python -m codejury.stage2_tools.critic_cli collect|validate --config config/stage2_tools/training/critic.yaml`

1. **Intake** (`episodes.py`): reads an `stage2-episode-set.v1` index. Every episode must pass its
   sha256, a path-safety check (no absolute, `..` or symlinked paths), the frozen `EpisodeBundle`
   schema, a unique `run_id` and (real mode) the split manifest: base problem in the requested
   split and in no other split. Refused episodes are kept in the manifest with their reason.
2. **Fixture isolation**: a set declares `runtime_mode` (`fixture` or `real`). A real build refuses a
   fixture set and the reverse. Output manifests carry `fixture: true`.
3. **Situations** (`situations.py`): near-correct revision, mutation gap, shared incorrect
   agreement, disagreement, correct candidate. Labels come from the label sidecar
   (`stage2-critic-labels.v1`, source kind reviewed / reference_backed / teacher_filtered).
4. **Prompt** (`prompt.py`): `build_prompt(bundle, mode, pending)` takes only the runtime bundle, so
   references, hidden tests and labels cannot enter. `guard_prompt` additionally fails on
   label-side keys or hidden strings (reference source, target rationale).
5. **Targets** (`targets.py`): a positive target is accepted only if the same `Investigator` the
   runtime uses admits an authoritative domain-valid test that a target candidate fails **and** the
   TRAINING reference passes. Literal and observation oracles are never accepted as counterexamples,
   so model-invented literals stay proposed even when empirically right.
6. **No-objection**: for correct candidates the target is a schema-valid general observation proposal
   (`generator_spec` general, observation oracle) whose rationale says no authorized failure was found
   and that this is not proof. Never a null/null proposal source.
7. **Invalid proposals**: from each accepted episode, up to N synthetic pending proposals
   (out-of-domain input, unregistered property, conflicting literal) are added to the prompt together
   with the gate's own rejection reason; the target is still the valid draft. These are tagged
   `synthetic_invalid`. This record shape is a design choice of this task, not a frozen contract.
8. **Mix**: correct-candidate >= 25% and invalid-proposal >= 10% are *targets*. Shortfalls are
   reported in `counts.mix`, never padded by duplication.

Records store neutral `system`/`prompt`/`completion` text. The chat template and masking are for
S2.08 to apply after inspecting the real MLX format; nothing here assumes them.

## Execution filter and sandbox
`validate_draft` runs through whatever sandbox is passed. Without a sandbox, positive targets and
teacher drafts stay rejected with reason "execution filter pending" (tested). The real CLI builds the
`DockerSandbox` and fails without a built runner image. CPU tests use the labelled
`FIXTURE_HOST_EXEC` test double only.

## Verified here
`pytest tests/stage2_tools/test_critic_data.py`: 11 passed (situations, hidden-prompt guard,
execution filter accept/reject incl. literal and wrong reference, no-objection validity, invalid
variants rejected by the gate, collect/validate roundtrip with tamper detection, fixture/real
isolation, split/hash/path enforcement, teacher drafts pending without a sandbox).

## Not verified
Real accepted/rejected/domain/no-objection/correct-candidate counts, validation-tuned mix, the
native Docker execution filter.
