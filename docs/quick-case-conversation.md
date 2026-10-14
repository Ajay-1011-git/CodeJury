# Reviewed Quick case and actual jury conversation

The user chose **review the draft, then click Approve all**. Interpreter trust is
off by default. Quick case accepts only buggy code, function name and a description.
New `/s2x/intake` endpoints return a durable draft and accept explicit per-item
approve/edit/reject decisions. Approval joins the existing Stage 2 run lifecycle;
the frontend does not submit a second repair run.

Quick case currently supports one pure function with plain positional arguments
and the bounded domain kinds listed by its interpreter. Helper bundles and
explicit supported imports use Advanced case. Both modes retain the core source
and interface restrictions; Quick case does not extend Python language support.

The local AST reader derives interfaces, use sites and bounded integer constants.
The cloud request is an explicit projection of function name, signature,
description and those facts. Body strings, the buggy source, traces, candidates
and reference repairs are absent. Groq uses the existing configured model,
single-flight budget ledger, credentials loader and unchanged $1 cap. Strict
structured output is revalidated locally, including decoded example strings.
Code, secrets and high body overlap are rejected. Rejected code/secret responses
are not retained in logs. Cached responses are revalidated against the current
schema and local body guard before reuse.

Domains remain visible finite envelopes. Unicode characters mentioned in examples
can enter the proposed alphabet; this does not claim coverage of all Unicode.
Registered property matches mark examples **corroborated**, which still requires
approval. Conflicts with proposed properties appear as clarification warnings.
The buggy function's behavior is never used to invent an oracle.

Only approved items enter the jury's authoritative checks. The explicit trust
option gives a visible interpreted-specification verdict label. Foreign origins
and hosts cannot spend interpreter budget or retrieve a draft. A busy native
worker leaves the reviewed draft retryable, without another cloud call.

The transcript projection uses actual stored model replies and durable controller
and sandbox events. It preserves exact counterexample inputs, registered expected
values, observed outputs, exceptions and authority. A property violation retains
its property ID and leaves a literal expected value unknown. Parent diffs come
from actual candidate sources, and output tokens come from recorded usage. No
display dialogue is synthesized. Execution chips open the matching matrix cell;
the earlier timeline remains available.

## Evidence and limits

- Final backend suite: **636 passed, nine skipped** with the retained inference
  runtime. Frontend: **85 passed**. The separate fixture HTTP integration suite
  passed all 11 cases; both existing contract validators passed. The frozen
  Stage 2 schema hash is unchanged.
- Quick intake suite: 44 tests, including code/secret/body-overlap guard cases,
  decoded example values and Unicode-escaped dictionary keys, raw rejection log exclusion, budget/cache handling, approval authority, Unicode
  envelopes, property conflicts, idempotent admission and foreign-origin guards.
  Tests use fakes and make no cloud calls or downloads. Passing these cases is
  evidence for the tested boundaries, not a universal leak-proof guarantee.
- One real, explicitly approved spec-only Groq smoke case was accepted. An earlier
  natural-language response hit the conservative code guard and was rejected and
  charged; the prompt and validator were corrected and the same authorized case
  rechecked. All spending stayed within the existing cap.
- Two genuine local Quick case repairs exercised draft creation, explicit approval,
  native inference, Docker execution and the final transcript. Both used the same
  authorized `total(values)` description and cached spec-only interpretation,
  with interpreter trust off. The first run (`run-9c7ef3068797441c8c4a6aab99271a60`)
  accepted a supported patch after six native calls, 31 function executions and
  19,806 ms. The repeat (`run-64a4cbfca74c4523a0f939ac98ab4377`) ended unresolved
  after a refused Critic challenge, despite both proposals passing the supplied
  examples. Its recorded refusal and final verdict remain visible.
- Live review cards show readable domains/examples and trust off. Conversation
  evidence for `[[-5,10,-2]]`, expected `3`, actual `0`, opened the exact original
  execution cell. The proposal diff shows `return 0` becoming `return sum(values)`.
  The timeline remains available. A live display bug was fixed: terminal state
  now fetches the complete transcript even after earlier replies were fetched;
  late replies cannot overwrite a final or different run. Pending model requests
  stay in the raw transcript but do not create empty chat bubbles. Controller
  refusals are no longer labelled as Judge replies in the timeline.
- Screenshots: [recorded proposal and evidence](ui/quick-case-live-conversation.jpg)
  and [recorded final verdict](ui/quick-case-live-verdict.jpg). These come from the
  genuine repeat run, not fixtures. The sum algorithm family overlaps training;
  these are unscored mechanics checks and do not establish repair accuracy.
- A full minimal-input solve-rate comparison and the requested within-ten-point
  accuracy gate remain unmeasured. Mid-run user clarification and differential
  Critic testing are deferred with the corresponding inference work.

Use `./start.sh`, open **Repair desk → Quick case**, draft the intended behavior,
review each item, and approve. **Advanced case** remains available for manually
supplied domains and tests. See [the bounded route](bounded-local-route.md) for
local training scope and timing.
