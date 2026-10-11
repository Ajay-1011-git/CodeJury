# CodeJury Stage 1 — Mock API Specification & Guide (`stage1.v1`)

## Overview
The mock API (`web/tools/mock_api.py`) implements a zero-dependency, Python standard-library HTTP server that emulates all CodeJury `stage1.v1` endpoints strictly against `contracts/stage1-api.schema.json`.

This allows independent frontend development and testing without requiring Ajay's backend server, a Mac GPU, or model adapters.

## CLI Usage
```bash
python web/tools/mock_api.py --port 8001 --scenario supported
```

### Options:
- `--port PORT`: Port to listen on (default: `8001`).
- `--host HOST`: Bind host interface (default: `127.0.0.1`).
- `--contracts PATH`: Path to contracts directory (default: `contracts`).
- `--scenario SCENARIO`: Outcome scenario to simulate upon reaching terminal state.
  - `supported` (default): Produces `status: supported_patch` with selected candidate `cand-001`.
  - `unresolved`: Produces `status: unresolved` with null candidate and unresolved requirement.
  - `infrastructure_error`: Produces `status: infrastructure_error` (sandbox crash simulation).
  - `invalid_input`: Produces `status: invalid_input`.
  - `cancelled`: Simulates pre-terminal cancellation.
  - `completed_training`: `/stage1/training-report` returns genuine-shaped completed evaluation rows.
- `--unavailable`: Simulates 503 Service Unavailable across all routes.

## Implemented Endpoints
| Method | Path | Status | Response Type | Notes |
|---|---|---|---|---|
| `GET` | `/health` | 200 | `Health` | `runtime_mode: fixture`, model/sandbox readiness |
| `GET` | `/examples` | 200 | `Examples` | Canonical task examples with valid domains & tests |
| `POST` | `/runs` | 202 | `RunAccepted` | Initiates run slot, returns opaque `run-mock-<id>` |
| `GET` | `/runs/{run_id}` | 200 | `RunSnapshot` | Deterministic lifecycle: poll 0 (queued) -> poll 1 (running) -> poll >= 2 (terminal) |
| `GET` | `/runs/{run_id}/events?after=N` | 200 | `EventPage` | Filtered events with cursor idempotence and `next_after` |
| `GET` | `/runs/{run_id}/candidates/{cand_id}` | 200 | `Candidate` | Returns full candidate source, diff, and byte SHA-256 |
| `POST` | `/runs/{run_id}/cancel` | 200 | `RunSnapshot` | Terminates active run with `status: cancelled` |
| `GET` | `/runs/{run_id}/report` | 200 / 409 | `RunSnapshot` | Returns snapshot if terminal; returns 409 if still running |
| `GET` | `/stage1/training-report` | 200 | `TrainingReport` | Returns factual training report (`not_started` or `completed`) |

## Error Envelopes
All error responses strictly match the canonical `Error` definition:
```json
{
  "schema_version": "stage1.v1",
  "error": {
    "code": "RUN_NOT_FOUND",
    "message": "Run ID '...' not found.",
    "field_errors": []
  }
}
```
- `404 Not Found`: Unknown run ID or candidate ID.
- `409 Conflict`: Busy run slot when another run is in progress, or report requested before terminal state.
- `422 Unprocessable Content`: Non-JSON body, schema validation failure, or negative/non-integer `after` cursor.
- `503 Service Unavailable`: Model worker or sandbox runner offline before acceptance.

## CORS and Security
- Restricts origins to localhost development ports (`http://127.0.0.1:8080`, `http://localhost:8080`).
- Emits `Cache-Control: no-cache, no-store, must-revalidate` on all API responses.
- Handles `OPTIONS` preflight with `204 No Content`.
