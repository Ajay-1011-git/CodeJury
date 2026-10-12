# A2.03 — native model port audit

The worker implementation and required raw/A/raw/A native acceptance are complete.
Full B/Critic/Judge/general switching is pending genuine trained adapters from
the later tasks. The live registry intentionally remains not ready for a complete
Stage 2 application. A2.04 intake/views/candidate parsing is next.

The diff is restricted to Ajay's A2.03 paths: `model_worker`, `registry`,
`factory.py`, `model_cli.py`, runtime configuration, the model-port test file and
this audit. Stage 1 implementation, weights/checkpoint, frozen shared schema and
ports, constraints, lockfile and Sarvesh's files are unchanged.

## Inspected implementation and compatibility

Native signatures/source were inspected in the installed MLX 0.32.3 / MLX-LM
0.32.0 environment before implementation: `load`, `stream_generate`,
`linear_to_lora_layers`, `remove_lora_layers`, `make_sampler`, chat-template
tokenization and peak-memory APIs. The actual conversion has model_type `phi3`,
32 layers, affine 4-bit quantization with group size 64. The retained A adapter
targets qkv/o projections in the last four layers, rank 8, scale 16, dropout 0.
Its 16 tensors are checked against actual inserted module shapes and dtypes.
No remembered generic LoRA family list substitutes for this inspection.

Upstream adapter loading checks unexpected tensors/shapes but permits a partial
weight load. The new worker first requires **exactly** the complete adapter tensor
set, then uses the inspected partial-load API to avoid supplying the frozen base
weights again. Unsupported topologies and mismatched keys/shapes/dtypes fail
closed. Adapters are never fused into the base.

The original base, tokenizer, quantization and topology hashes are registered
from real local bytes. Each AdapterCard and training freeze must agree. Distinct
roles cannot alias identical adapter bytes. Existing A is `pilot_only` for Stage
2, retaining the real 300-step Stage 1 trial and selected step-100 checkpoint;
Stage 2 revalidation/refresh remains A2.05. No B, Critic, Judge or general card is
invented. Changed file bytes/configs, incompatible cards, and fixture registries
are rejected. Base file inode/size/mtime changes are checked again before calls.

## Native process and boundaries

The live factory validates local configuration and registry metadata without
importing MLX or starting a process. First generation spawns one native child,
which acquires the common Mac compute lease before importing/loading MLX. It
loads one base, unwraps the old linear LoRA modules, and inserts/loads the next
complete adapter. The original quantized linear objects and base model object
remain resident. Fresh KV state, detokenizer state and allocation caches are
used for every request. Raw requests contain no adapter leaves.

JSON bytes cross the process boundary; request/response/usage records are schema
validated and copied. Startup manifest identity and response model/adapter/config
hashes must agree with the parent's frozen registry. Concurrent and duplicate
requests are rejected. Missing adapters return `adapter_unavailable`; compute
contention returns `compute_busy`. There is no live fake/raw fallback for missing
trained roles. Closed/failed workers report unavailable and require explicit
recreation rather than replaying generations. Idle children exit if their parent
dies; worker cleanup precedes compute-lease release.

Role/purpose caps, remaining episode/attempt budgets, and tokenized prompt plus
reserved completion <=4096 are enforced. Required content is never truncated to
fit. Raw text is returned privately through ModelResponse; the worker neither
parses role decisions nor executes generated source. Input costs come from the
runtime's processed-prefill callback; output costs come from generation token
counts. The controller ledger separately charges model/Judge attempts before
dispatch. MLX peak bytes are converted to decimal MB; elapsed_ms measures the
worker operation including switching/generation, with the episode controller's
monotonic clock covering startup/IPC as well.

Cancellation is checked before dispatch, after switching, at prefill boundaries
and between generated tokens. The parent forwards cancellation through a shared
event. A nonresponsive worker is terminated after the configured grace period;
reported token costs then remain explicitly the last known lower bound. No
partial output is a completed repair. The compute lease remains held while the
base is resident, including idle periods; close the port before training jobs.

## Actual verification

```text
python -m pytest tests/stage2_core/test_model_port.py -q
25 passed (1.99s in the full verification batch)
python -m pytest -m 'not sandbox and not mac' -q
171 passed, 9 hardware tests deselected in 7.22s
ruff check src/codejury/stage2_core/model_worker src/codejury/stage2_core/registry \
  src/codejury/stage2_core/factory.py src/codejury/stage2_core/model_cli.py \
  tests/stage2_core/test_model_port.py
All checks passed
python -m codejury.stage2_core.contract_check --contracts ../contracts
83 definitions, 49 synthetic fixtures, frozen schema and ports unchanged
python -m codejury.contracts.check ../contracts
8 original fixtures passed; original schema unchanged
```

CPU tests explicitly use test doubles to exercise token budgets, byte/card
mismatches, missing roles, complete tensor sets, partial cost reporting,
cooperative cancellation, actual child-process failure/forced shutdown, serial
IPC reuse and duplicate request IDs. They do not establish native inference.

Two real native smoke records are retained, never overwritten:

- `artifacts/stage2_core/model-smoke.json`: initial single-user chat policy.
  Raw/A/raw/A parameters and outputs matched independent clean loads; every
  generation hit the 192-token smoke cap and emitted prose.
- `artifacts/stage2_core/model-smoke-json-policy.json`: final system/user policy,
  with a frozen JSON-output system instruction. The same raw/A/raw/A sequence
  matched independent clean loads. One worker PID (61608), one base load and one
  unchanged model object served all four calls and boundary probes. Clean raw/A
  comparison workers were loaded sequentially only after that worker closed.

Exact parameter hashes match the previously recorded Stage 1 smoke:

| Role | Parameter hash |
| --- | --- |
| raw | `970ebb09dd0c16f90cd3c842a32aec1a194df41ee90def7b5a5a9af986c4888b` |
| A | `62ad79b24257fe107b1079068fce3b8224dabcadeab4c43345edcbf33b686546` |

Final policy manifest hash:
`94b04c2bfe86fbadd817324144df6e14193035f0815b165c271b3b6280ec4b7a`.
Genuine retained adapter:
`274fd6b1a4a9abd04a8a2d3e56cfbde765c81e71fdb230682f4bf66509605fb4`.

Each final-policy call consumed 108 input tokens. Raw consumed 75 output tokens
(2,008 / 1,698 ms; measured peak approximately 2,424 MB). A consumed the full
192-token smoke cap (4,451 / 4,196 ms; peak approximately 2,428 MB). These are
measurements of this public unscored generation, not throughput promises or a
repair-quality benchmark. Diagnostic full parameter hashing has separate costs.

Native oversized-context probe returned `budget_exhausted/context_limit` before
prefill, with zero input/output tokens. Native cancellation during a larger
prefill returned `cancelled`, 2,048 actually processed input tokens, zero output
tokens, 1,594 ms and measured 3,720 MB peak. The post-smoke common compute lease
could be acquired again, confirming the smoke left no resident worker holder.

**Observed format failures remain visible:** raw's final-policy text used Markdown
fences; A emitted a prose outline and reached the smoke cap. Neither is accepted
as RepairDraft. Parameter identity and deterministic clean-load agreement passed;
strict structured-output/repair quality did not. A2.04 must reject malformed role
JSON, and A2.05 must audit prompt/data compatibility and revalidate/refresh A.
No generated candidate ran on the host or in a sandbox during these checks; no
hidden or final assessment record was opened.

## Local reproduction and future roles

From `backend/`, with the actual local Stage 1 assets:

```sh
.venv/bin/python -m codejury.stage2_core.model_cli register-stage1 \
  --model-dir models/Phi4-mini \
  --adapter-dir artifacts/training/fixer_a_selected \
  --training-report artifacts/evaluation/training-report.json \
  --out artifacts/stage2_core/model-registry-json-policy.json
.venv/bin/python -m codejury.stage2_core.model_cli smoke \
  --config config/stage2_core/runtime.yaml \
  --sequence raw,fixer_a,raw,fixer_a \
  --out artifacts/stage2_core/model-smoke-new-run.json
```

Registry creation and smoke outputs refuse overwrite. For a new registry path,
set `CODEJURY_STAGE2_MODEL_MANIFEST` explicitly; model paths can be relocated only
with identical verified bytes. The original single-user manifest is retained
for its historical smoke and intentionally fails the final policy's config hash.
All registries, weights, raw text and experiment records remain ignored locally.

After genuine B/Critic/Judge cards arrive, repeat the full raw/A/B/Critic/Judge/A/
general-if-available/raw sequence against independent clean loads. Current
readiness remains false: three required roles are absent and A is still a Stage
2 pilot. No new training, research score, live Stage 2 release or push is claimed.

Official references inspected alongside installed source:
[MLX-LM LoRA](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md),
[adapter insertion/removal](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/utils.py),
[stream generation](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/generate.py).
