# Continue CodeJury on Sarvesh's Mac — 13 October 2026

Ajay's integrated core work and Sarvesh's helper work are merged on `main`. This is a
training checkpoint, not a completed project. Do not discard any existing jobs or claim
that saved weights alone demonstrate quality. The live runtime still uses the previous
validated four-role registry.

## Files to receive

1. Pull `https://github.com/Ajay-1011-git/CodeJury` main for the merged source and tools.
   Saved adapter weights are transferred through the **private** repository
   `https://github.com/Ajay-1011-git/CodeJury-training-handoff`, release
   `training-snapshot-2026-10-13`. Ajay must grant Sarvesh access or send the files
   directly. No collaborator invitation has been sent. The release contains all
   127 saved weight files, configurations and freeze metadata; it omits case data.
2. Ajay must send `codejury-training-private-2026-10-13.tar.gz` (2.1 GB) and its
   `.sha256` sidecar by **direct local transfer, such as AirDrop or USB**. This
   contains the complete ignored backend
   artifacts, base model, private data, budget/cache databases, actual continuation
   ledgers, dependency inventory and the two exact Docker execution images. Do not
   upload this bundle to the public repository or a public release. A Git pull alone
   cannot resume this experiment exactly. An adapter-only snapshot is prepared
   locally, but public distribution was blocked by automatic approval review because
   explicit permission to distribute the weights publicly was unclear. The training
   adapter-only GitHub transfer remains private. Automatic review also rejected
   remote upload of the full-state bundle under the amendment's private
   validation/final/reference restrictions. The full bundle remains local for direct
   transfer. This is not the final project release.
3. Groq keys are deliberately absent. **No Groq key is needed for the next training
   phases:** the teacher collection and verified corpus are finished. If a separately
   justified future offline collection needs keys, obtain them privately and place
   them in the ignored root `.env`. Never include them in commits, logs or archives.

## Exact completed state

| Component | Preserved evidence |
|---|---|
| Offline teacher | 20 TRAIN bases, 40 proposals, 22 distinct accepted targets; 41 actual HTTP attempts including preflight; $0.0063987 charged/reserved; unknown usage zero |
| Teacher A | Genuine 20-update pilot and 100-update full job/reload. Step 50 selected: 6/20 executable solves versus old A's 5/20, zero wrong accepts; step 100 rejected for increased incorrect acceptance |
| Selected A identity | `ddb71053405be928d485b042fb6c7f2e49098f68e42c9b6492ddd9f8681a6df4` |
| B | Existing trained weights retained; fresh candidate-A mining completed, 120 real trials on 40 TRAIN bases. Paired A/B union 11/20 versus old pair 10/20, zero wrong accepts; B was not retrained in that comparison |
| Critic | Existing trained weights retained; new-distribution compatibility validated: 43/45 format/domain valid, five correct controls, zero false hard rejections |
| Judge data | Completed and scored 536 real alternative continuations from 96 states, 38 TRAIN bases and 10 validation bases. All alternatives were committed before private scoring. Two incomplete source runs excluded and retained |
| Judge next | Generate labels from those completed continuations, then a new native pilot/full job and executable checkpoint selection |
| General | Earlier 550-update full job preserved as baseline; teacher-aware comparator still needs a new corpus, pilot/full job, executable selection and measured completion-token parity |
| Final assessment | Still sealed and unevaluated; transfer/hash verification treats it as opaque bytes, not development data |

The 20 A validation variants share ten base problems. Greedy repeated seeds are not
independent stochastic samples. Keep these limits explicit.

## Restore the exact checkpoint

Use an Apple Silicon Mac with working native MLX and enough unified memory (Ajay used
16 GiB). This native pipeline cannot be completed by substituting CPU fixtures on
Windows, Linux or an Intel Mac. Recreate the environment; do not copy Ajay's `.venv`.
The captured environment is Python 3.11.16, MLX 0.32.3, MLX-LM 0.32.0 and Transformers
5.19.0. Colima was 0.10.3 and Node was 24.14.1. All installed Python versions are
recorded in the bundle's `handoff-metadata/runtime-requirements.txt`.

Preserve Sarvesh's local work on a backup branch/commit before switching branches.
Fetch and merge main without force-resetting or dropping local changes. In a clean
checkout the basic sequence is:

```sh
git clone https://github.com/Ajay-1011-git/CodeJury.git
cd CodeJury
git switch main
git pull --ff-only origin main
```

For an existing checkout, omit cloning and first inspect its branch and working tree.
Then verify the directly received full archive:

```sh
# Run in the folder containing the locally received archive and sidecar.
shasum -a 256 -c codejury-training-private-2026-10-13.tar.gz.sha256
```

From the repository root, using an absolute path to the received archive:

```sh
python3.11 backend/tools/stage2_core/training_snapshot.py restore \
  --archive /absolute/path/to/codejury-training-private-2026-10-13.tar.gz
```

The restorer verifies every payload and the corresponding checked-in source before
writing, refuses symlinks and conflicting existing bytes, and preserves original
file contents. Repeated restore of identical files is allowed. If old local artifacts
conflict, preserve them in a separate checkout and restore into a clean checkout.
Do not overwrite or modify historical manifests to make a check pass.

```sh
export CODEJURY_STAGE2_ORIGINAL_ROOT=/Users/ajay_macm5/Desktop/CodeJury
uv venv --python 3.11.16 backend/.venv
uv pip install --python backend/.venv/bin/python \
  -r handoff-metadata/runtime-requirements.txt
uv pip install --python backend/.venv/bin/python --no-deps -e backend
```

Keep `CODEJURY_STAGE2_ORIGINAL_ROOT` in the shell/environment used by the training and
service processes. The code maps archived absolute paths to this checkout at read
time; archived JSON/YAML, their hashes and frozen identities remain unchanged. Do
not apply search-and-replace to the archived paths. The base model's exact revision
is `d848c30f6d5419b9892433cf6b1062626d15340e` from
`mlx-community/Phi-4-mini-instruct-mlx-4Bit`; it is included in the private transfer.

Create/start the dedicated ARM64 Colima profile `codejury-stage1` with 2 CPUs,
2 GiB VM memory, no host mounts and no agent forwarding. Reuse a matching isolated
profile if already present; inspect actual VM/container isolation rather than relying
on the configuration text. The Docker context must be `colima-codejury-stage1`, as
specified in `integration/stage2/runner.yaml`. Load the transferred images:

```sh
gzip -dc handoff-metadata/docker-images.tar.gz | \
  docker --context colima-codejury-stage1 load
export CODEJURY_STAGE2_RUNNER_IMAGE=sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f
cd backend
.venv/bin/python -m codejury.stage2_tools.runner_cli self-test \
  --config ../integration/stage2/runner.yaml \
  --out artifacts/stage2-integration/sarvesh-runner-v1
```

Require `overall: passed`, all 12 checks true, no host/agent shares, the same Stage 2
image identity, and compatibility with the captured runtime hash. Preserve Ajay's
proof at `artifacts/stage2-integration/runner-v2/runner-self-test.json`; a copied proof
does not establish that Sarvesh's machine is ready. Do not silently replace the
execution implementation used to generate the archived labels. The transferred
Stage 1 runner image is
`sha256:2e357513b8bd95894224280a265c6d4153d160aca1bb1f57a6370d6ceaf9e9f5`.

## Resume dependent training

After successful restore, environment setup and fresh native isolation checks:

```sh
# From backend; the original-root export must remain set.
.venv/bin/python -m codejury.stage2_core.teacher.cli complete-training \
  --config config/stage2_core/teacher.yaml \
  > artifacts/stage2_core/teacher/sarvesh-continuation.log 2>&1
```

The coordinator skips completed phases by their immutable manifests/reports. It
starts at Judge label generation from `teacher/current-continuations-v1`; it does
not recollect those 536 alternatives, call Groq, or retrain A. It then:

1. Creates `current-judge-corpus-v1`, trains a separate 20-update native Judge pilot
   and 100-update full job, verifies actual updates and fresh reload, and selects
   the earliest best executable validation checkpoint in `current-judge-selected-v1`.
   Require the configured valid-action gate; never label actions using teacher opinion.
2. Builds `current-general-corpus-v1` from genuine role targets plus all 100 sampled
   teacher-A opportunities, runs a fresh native General pilot/full job, and selects
   in `current-general-selected-v1`. Depending on Judge selection, General has 550
   or 600 updates. Pilot proof must match the full job's exact identity.
3. Audits actual learned completion-token exposure, including inherited A and the
   selected teacher refinement, against General. Require the declared 10% relative
   tolerance and comparable teacher opportunities. Do not substitute update counts
   for measured tokens or claim earlier General weights match the new curriculum.
4. Writes `dependent-training-v1.json` only after all its selection gates pass.
   This does not deploy the models, complete the app checks or run final assessment.

Serialize all native model work through `ComputeLease`; never steal/delete a lock
or run simultaneous native trainers/runtime workers. Inspect retained failures and
logs if a gate fails. Completed phases can resume; partial native jobs/collections
are not automatically resumable merely because an output directory exists. Preserve
interrupted jobs and create an explicitly separate job/config after diagnosing them;
never pretend a fresh run resumed an old optimizer. No unfinished optimizer job
is active in this transfer: it stopped after the completed Judge collection phase.

If teacher work is expanded later, retain the shared budget/cache databases: the
original budget is 60 total HTTP attempts and $1 across all keys, with 41 attempts
already spent and zero unknown charges. Respect organization-wide rate limits and
persisted backoff. Halt on unknown usage. Do not increase caps, reset the ledger,
send private validation/final/reference data remotely, or add Groq to live repair.

## Finish the project after training

1. Inspect all actual selection, compatibility, lineage and parity evidence. Use the
   compatible selected A/B/C/J/General registry only after their gates pass. Update
   `config/stage2_core/runtime.yaml` to the new selected registry and
   `config/stage2_core/methods.yaml` to the new General opportunity report. Populate
   measured training opportunities in the evaluation configuration; its current
   zero placeholders must not survive the final freeze. Preserve actual B-unweighted
   and B-same-view control weights and keep every baseline/ablation runnable.
2. Run the complete backend suite and frontend checks, frozen contract checks,
   fresh sandbox/search/auditor checks, and real native all-method validation.
   Fix real failures without editing frozen schemas, ports, public fixtures or
   sealed data. Read the relevant CLI help and existing test/build commands.
3. Exercise the merged live API/UI through actual repair, revision, queueing,
   cancellation, restart/recovery, supported and unresolved outcomes, and download.
   Launch `.venv/bin/python -m codejury.stage2_core.serve` on loopback port 8002
   as needed. Verify actual trained weights are loaded and Groq is unnecessary.
4. Commit a clean, reviewable experiment freeze after these gates. All source,
   model identities, runtime, controls, configurations and opportunity proofs must
   be frozen before the first semantic read of the final pool. Do not inspect
   `data/private/stage2_final.jsonl` while developing. The declared final pool has
   only ten independent bases, not 480 independent examples.
5. Create E4 and perform the single real final assessment with all 16 method/regime
   plans, ten bases and seeds 11/23/37: 480 actual runs. Use the configured fixed
   representative-per-base rule, budgets and base-cluster bootstrap. These commands
   run from backend only after the preceding gates:

   ```sh
   .venv/bin/python -m codejury.stage2_tools.eval_cli run \
     --config config/stage2_tools/evaluation.yaml --split final_assessment \
     --freeze artifacts/stage2_core/e4.json --freeze-only \
     --out artifacts/stage2_tools/final-unused
   .venv/bin/python -m codejury.stage2_tools.eval_cli run \
     --config config/stage2_tools/evaluation.yaml --split final_assessment \
     --freeze artifacts/stage2_core/e4.json \
     --out artifacts/stage2_tools/final-v1
   ```

   Final consumption markers remain meaningful after interruption/failure. Do not
   remove them, tune on final outcomes or repeat the experiment as a fresh final
   claim; a new claim requires a fresh sealed pool. Commit all actual run outcomes
   before private scoring. Report improved, inconclusive or worse exactly as measured.
6. Produce the final aggregate report, truthful model/data cards and portable
   five-adapter release with the genuine benchmark:

   ```sh
   .venv/bin/python -m codejury.stage2_core.release_cli \
     --registry artifacts/stage2_core/teacher/current-general-selected-v1/registry.json \
     --benchmark artifacts/stage2_tools/final-v1/benchmark-report.json \
     --out artifacts/stage2_core/release-v1
   ```

   Require all five actual completed role cards, matching final run metadata/freeze
   and archive integrity. Keep private corpora/ledgers, credentials and base weights
   out of the public project release. The private training snapshot is not this release.
7. Merge any remaining local fixes safely, commit documentation with the final state,
   push main and aggregate reports. Keep weight releases private until Ajay explicitly
   approves public distribution; preserve the local-only private-case transfer restriction.
   Give Ajay the commit/release links,
   actual test/native evidence, measured benchmark outcome and any real limitations.

Proceed autonomously through authorized implementation, audits, fixes, merge and push.
Do not stop at a plan or ask routine permission. If a genuine hardware/access block
prevents completion, finish all independent work and report the exact blocker without
claiming that the project or training is complete.
