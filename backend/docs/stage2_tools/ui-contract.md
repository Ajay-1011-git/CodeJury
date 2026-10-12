# UI ↔ backend contract notes (S2.11)

The Stage 2 UI consumes exactly the HTTP table in the shared contract (`/health`, `/examples`,
`POST /runs`, `/runs/{id}`, `/runs/{id}/events?after=N`, `/runs/{id}/candidates/{cid}`,
`POST /runs/{id}/cancel`, `/runs/{id}/report`, `/stage2/training-report`,
`/stage2/benchmark-report`). Details the integrator should know:

1. The UI refuses to submit unless `GET /health` returns `service: codejury-stage2`,
   `schema_version: stage2.v1` and `contract_hash` equal to
   `ee62388479918f0e33d4085d530dc210356ed104afe6170b1ff03687e53b6ee6`.
2. Polling is every 1000 ms with cursor `after` (integer ≥ 0). Events are deduplicated by
   `event_id`; `next_after` is trusted as returned. Polling stops at a terminal status, on
   `pagehide`, and when a newer submission supersedes the run (stale responses are dropped).
3. A refused Judge action and a fixed fallback are recognised from `action_refused` events and
   from the phrase "fixed fallback" in an `action_selected` event message, because the contract has
   no dedicated flag. If core adds one, update `actionTimeline` in `web/src/s2/model.mjs`.
4. The Download control uses `decision.selected_candidate_id` only and re-hashes the exact
   source against `source_hash`; it is hidden for non-`supported_patch` statuses and for
   candidates whose `verification_suite_hash` differs from the snapshot `suite_hash`.
5. Status 409 (busy / report not terminal / archived Stage 1 run id), 404, 422 (including version
   mismatch) and 503 are shown with their own wording; old Stage 1 payloads are never accepted.
6. Fixture vs live: `runtime_mode: fixture` forces the banner and labels reports; fixture and
   live benchmark rows are never charted together.
