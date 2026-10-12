# A2.07 fixed controller and canonical episode export

Implemented: the fixed-v1 action loop, real native/Docker collection, immutable pre-action EpisodeBundles, compatible train exchange manifests, and separate private post-freeze TRAIN assessment. This is an initial coupled pilot, not completed Critic/Judge training or a final benchmark.

## Controller behavior

Semantic intake and reproduction precede the independently frozen A/B prompts. Initial B receives contracts, interfaces, domains and visible tests; it receives no buggy body or A result. Every model request/response is retained, including refused drafts. Candidate alternatives preserve proposal provenance and group observed behavior without a majority vote.

Qualification requires semantic receipts and complete passing results on the current authoritative suite, with exact runtime/source identities and clean input effects. A remains incumbent while eligible. New authoritative tests invalidate previous qualification and propagate to every candidate. Observations can expose disagreement but cannot reject or certify a candidate. Essential ambiguity, conflicting inputs, incomplete checks and unsuccessful Critic challenges prevent selection.

All seven action kinds use canonical ActionOptions. Fixed ordering is: revise a learned parent after a new hard counterexample; search local sites when no candidate qualifies; one resample; criticize consequential disagreement; audit agreement once per source/current suite; investigate a challenge; select only after required checks; otherwise abstain. Budgets, action limit and final execution reserve are fixed by POLICY. Selection spends the held reserve on a complete fresh sandbox replay. Cancellation or infrastructure failure overrides earlier successful evidence.

Each pre-action state, offered menu, chosen action, refusal, outcome and cumulative usage is retained in the append-only ledger. Terminal snapshots survive reopening and cannot resume dispatch. A frozen profile binds policy, resource ceilings, selected model manifest, sandbox runtime, controller source bytes and tool source bytes. The validation diagnostic checked fail-closed behavior; no policy quality improvement is claimed from one case.

Raw bootstrap Critic requests are explicitly role=raw/purpose=baseline. A malformed raw draft remains refused; Markdown is not stripped and missing fields are not manufactured. A learned Critic is used only when present in the verified registry.

Two exact reviewed runtime contracts bind the inspected sum_ints and count_occurrences_ints property templates after domain compatibility checks. Other contracts retain no new property authority. These bindings inspect the approved contract/domain only, never a reference solution or private test.

## Tool seam fixes

Tool trace references are archived using the tools' exact JSON codec before ledger settlement, including Unicode. Search/audit edits now preserve the parent bytes outside the reported span. Reformatting a whole function previously made an apparently local edit impossible to replay. UTF-8 offsets, comments, noncanonical literals and expression precedence are checked while constructing each replacement; the ledger still verifies the full hash chain.

The live collector requires the actual NativeModelPort, ToolPortImpl and DockerSandbox. CPU fixture ports cannot be relabeled as learning evidence. Candidate code runs exclusively in the isolated runner for live collection.

## Export and private labels

episodes.jsonl contains frozen pre-action EpisodeBundles, so later tests and outcomes cannot leak into earlier states. transports.jsonl contains actual runtime-only requests/responses. audit.jsonl records raw/bootstrap mode, actions, refusals and costs. Source/base/split provenance is rejoined against the sealed TRAIN asset before export. Referenced trace objects and every exchange file are hashed in ArtifactManifest. Validation, final assessment, active runs, fixture runs and infrastructure/cancelled runs are refused as training exports.

The private score-training command runs only after immutable final snapshots exist. It uses sealed TRAIN assessment checks in separate tool requests, saves labels under the ignored core artifacts directory, and verifies that scoring did not change any runtime snapshot. It never modifies the runtime ledger's tests, candidates or episodes. These candidate labels are not alternative-action Judge labels. No final-assessment contents are opened.

## Initial native evidence

Selected registry: 7e93cae723e1d0be7e6201a4c10ae2148a3b428f901e02985aa8134760b1b5d1. It contains the previously measured A/B adapters and the same frozen Phi-4-mini base. Critic/Judge adapters remain absent.

The pilot uses total, occurrence_count, clamp and negative_positions, one authorized TRAIN corruption per base. It is a deliberately small synthetic diagnostic. Earlier development repeats are retained separately and are not independent extra bases. The final profile-frozen artifact and audit below supersede those development exchanges.

All four profile-frozen pilot runs reached audit then criticize and ended unresolved. Seven committed fixer candidates passed their visible suite; a further A proposal was refused. Post-freeze private TRAIN checks passed for those seven committed candidates (14 real isolated function calls), while controller final success remained 0/4 because no patch was selected. This is candidate availability evidence, not broader accuracy or a final benchmark.

The raw Critic returned fenced or incomplete CriticDraft JSON on all four problems. No useful objection targets or authoritative counterexamples are claimed from these refusals. The exchange is suitable for interface acceptance and negative/refusal evidence; it is not a sufficient positive Critic training corpus. The next collection work must obtain and execution-filter valid proposals across correct candidates, shared wrong agreement, disagreement, local failures, audit gaps and revisions before Critic training is marked ready.

The final exchange has 8 pre-action states / 4 TRAIN bases, 12 native generations (8 fixer attempts + 4 raw Critic calls), 48 runtime function executions and 13 audit mutants. Summed runtime wall time is 41,093 ms; peak MLX memory is 3,630.29 MB. This excludes setup, earlier development repeats and private scoring. Raw bootstrap calls produced no admitted authoritative counterexample.

Local artifact: artifacts/stage2-exchange/ajay/episodes-fixed-v1-frozen-profile-pilot-v1, with an adjacent ZIP containing only the shared manifest-listed files. The private labels stay in artifacts/stage2_core/fixed-collection/private-training-labels-frozen-profile-v1.json. Public aggregate evidence is [controller-pilot.json](controller-pilot.json).

Episode JSONL SHA-256: 23f2646037cf1cdde02e132f79aa5d9220ebf0e72d06200e5f990d1b064cced0. Manifest SHA-256: 5678da022d1583833d9f86a9c4f7d67dcca857001da0c8f145d0db6c3ec8508f. Profile hash: 1390fcdbb6e4dfb9ab67b7e9475eef56c0fff421ebad49c09819d832768f22ba. Schema/hash/reference/independent-B/privacy checks passed, and private scoring preserved every frozen runtime snapshot.

Validation diagnostic: gcd, from the authorized validation split, also ended unresolved after audit/criticize. It is excluded from all training exchanges and private training joins. The final assessment and learned-Judge benchmark remain unrun.

Verification: 429 backend tests passed, 9 native checks skipped in the CPU suite. Actual native MLX/Docker collection ran separately. The real isolated search and auditor self-tests both passed after the edit fix. Frozen schemas/ports and 49 public fixtures passed the contract check unchanged. Fixture tests cover seven action shapes, actual action paths, stale state refusal, new hard-test invalidation/revision, observation disagreement, cancellation, budgets, contract conflicts, trace hashes and fixture/holdout export refusal.

## Reproduction

From backend, with the existing isolated VM, pinned Stage 2 runner image and selected local registry available. Use fresh output paths; reports/exchanges are immutable.

```sh
export CODEJURY_STAGE2_RUNNER_IMAGE=sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f
python -m codejury.stage2_core.cli collect --config config/stage2_core/collection.yaml \
  --record-id total-return-0 --record-id occurrence_count-return-0 \
  --record-id clamp-return-0 --record-id negative_positions-return-0 \
  --out artifacts/stage2_core/fixed-collection/new-pilot.json
python -m codejury.stage2_core.export_cli episodes --split train \
  --report artifacts/stage2_core/fixed-collection/new-pilot.json \
  --out artifacts/stage2-exchange/ajay/episodes-new-pilot
python -m codejury.stage2_core.export_cli score-training --split train \
  --report artifacts/stage2_core/fixed-collection/new-pilot.json \
  --out artifacts/stage2_core/fixed-collection/private-new-pilot-labels.json
```

A user request can also run through cli run --request PATH --policy fixed. Requests without verified training provenance cannot enter the training exchange. Local weights, raw episodes, assessment checks and private labels remain ignored; public Git contains implementation, reproduction commands and aggregate evidence only.
