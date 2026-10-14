"""Serve the Stage 2 jury API under /s2 of the main dashboard.

The Stage 2 wire contract is unchanged; this module only mounts it, keeps a single model
run across both stages (16 GB machines cannot hold two), and exposes the stored model
exchange of a finished debate for the Action history.
"""

import json
import logging
import os
import re
import sqlite3

log = logging.getLogger(__name__)

PREFIX = "/s2"
RUN_ID = re.compile(r"run-[0-9a-f]{32}")


def load_stage2_app():
    """Build the Stage 2 app when CODEJURY_STAGE2=1; return None if it cannot start."""
    if os.getenv("CODEJURY_STAGE2") != "1":
        return None
    try:
        from ..stage2_core.api import create_app

        return create_app()
    except Exception:  # Stage 1 must keep working when Stage 2 cannot be built.
        log.exception("Stage 2 is unavailable; serving Stage 1 only")
        return None


def stage2_busy(stage2_app) -> bool:
    worker = getattr(stage2_app.state, "worker", None)
    return bool(worker is not None and worker.lock.locked())


def _facts(prompt: str):
    """The Judge prompt embeds its runtime-visible state as one JSON object."""
    start = prompt.find("{", prompt.find("Runtime-visible facts:"))
    if start < 0:
        return None
    try:
        facts, _ = json.JSONDecoder().raw_decode(prompt[start:])
    except ValueError:
        return None
    return facts.get("state") if isinstance(facts, dict) else None


def transcript(ledger_directory, run_id: str) -> dict:
    """Ordered model calls of one run: role, purpose and the reply text.

    For the Judge, the action menu and candidate scoreboard it was shown are attached so
    the UI can show what it chose between. Prompts themselves are not returned.
    """
    body = {"schema_version": "stage2.v1", "run_id": run_id, "calls": []}
    path = ledger_directory / "ledger.sqlite3"
    if not RUN_ID.fullmatch(run_id) or not path.is_file():
        return body
    with sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT body, status, response FROM requests "
            "WHERE run_id=? AND definition='ModelRequest' ORDER BY rowid",
            (run_id,),
        ).fetchall()
    for raw, status, raw_response in rows:
        try:
            request = json.loads(raw)
            response = json.loads(raw_response) if raw_response else {}
        except ValueError:
            continue
        call = {
            "request_id": request.get("request_id"),
            "role": request.get("role"),
            "output_tokens": (response.get("usage") or {}).get("output_tokens"),
            "purpose": request.get("purpose"),
            "status": response.get("status") or status,
            "text": response.get("text"),
        }
        if call["role"] == "judge":
            state = _facts(request.get("prompt") or "")
            if state:
                call["options"] = [
                    {
                        "option_id": o.get("option_id"),
                        "kind": (o.get("action") or {}).get("kind"),
                        "target_ids": (o.get("action") or {}).get("target_ids", []),
                        "summary": o.get("prerequisite_summary"),
                    }
                    for o in state.get("available_actions", [])
                ]
                call["scoreboard"] = state.get("candidate_summaries", [])
        body["calls"].append(call)
    return body
