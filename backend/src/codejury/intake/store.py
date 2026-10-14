"""Durable local drafts, explicit item approvals and idempotent run admission."""

import copy
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from uuid import uuid4

from codejury.stage2_core.contracts import checked, json_hash
from codejury.stage2_core.intake import prepare
from codejury.stage2_core.teacher.redaction import clean
from codejury.stage2_tools.oracles.gate import check_intake

from .infer import infer

VERDICT_LABEL = "Verified against an interpreted specification, not user tests"


class DraftConflict(ValueError):
    pass


class DraftStore:
    def __init__(self, directory, interpreter):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "intake.sqlite3"
        self.interpreter = interpreter
        self.lock = threading.Lock()
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, input TEXT NOT NULL, "
                "draft TEXT NOT NULL, decision_hash TEXT, accepted TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, "
                "draft_id TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, "
                "created REAL NOT NULL)"
            )
        os.chmod(self.path, 0o600)

    def connect(self):
        return sqlite3.connect(self.path)

    def create(self, payload):
        if type(payload) is not dict or set(payload) != {"source", "function_name", "description"}:
            raise ValueError("Quick case requires exactly code, function name and description")
        if (
            any(type(v) is not str or not v.strip() for v in payload.values())
            or len(payload["source"]) > 48000
            or len(payload["description"]) > 12000
        ):
            raise ValueError("Quick case text is missing or too large")
        clean(json.dumps(payload))
        facts = infer(payload["source"], payload["function_name"])
        interpreted = self.interpreter.interpret(facts, payload["description"], payload["source"])
        identifier = "intake-" + uuid4().hex
        draft = {
            "spec_version": 1,
            "id": identifier,
            "function": facts["function"],
            **interpreted["spec"],
            "local_arg_domains": facts["arg_domains"],
            "interpreter": {
                "role": "interpreter",
                "label": "Interpreter (cloud, spec only)",
                "model": interpreted.get("model"),
                "request_hash": interpreted["request_hash"],
                "text": interpreted.get("response"),
                "validator": interpreted["validator"],
                "output_tokens": (interpreted.get("usage") or {}).get("completion_tokens"),
            },
            "approval_required": True,
            "authority_label": None,
        }
        with self.connect() as db:
            db.execute(
                "INSERT INTO drafts(id,input,draft) VALUES(?,?,?)",
                (identifier, json.dumps(payload), json.dumps(draft)),
            )
            db.execute(
                "INSERT INTO events(draft_id,kind,body,created) VALUES(?,?,?,?)",
                (identifier, "interpreted", json.dumps(draft), time.time()),
            )
        return draft

    def get(self, identifier):
        with self.connect() as db:
            row = db.execute("SELECT draft FROM drafts WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        return json.loads(row[0])

    def build(self, identifier, decisions):
        if type(decisions) is not dict or set(decisions) - {
            "approve_all",
            "items",
            "trust_interpreter",
        }:
            raise ValueError("Invalid approval decisions")
        if (
            type(decisions.get("approve_all", False)) is not bool
            or type(decisions.get("trust_interpreter", False)) is not bool
        ):
            raise ValueError("Approval flags must be booleans")
        items = decisions.get("items", [])
        if type(items) is not list:
            raise ValueError("Items must be a list")
        with self.connect() as db:
            row = db.execute("SELECT input,draft FROM drafts WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        payload, draft = map(json.loads, row)
        known = {f"domain:{d['param']}": d for d in draft["arg_domains"]}
        known.update({f"requirement:{r['id']}": r for r in draft["requirements"]})
        known.update({f"example:{e['id']}": e for e in draft["examples"]})
        approved = (
            {key: copy.deepcopy(value) for key, value in known.items()}
            if decisions.get("approve_all") or decisions.get("trust_interpreter")
            else {}
        )
        seen = set()
        for item in items:
            if (
                type(item) is not dict
                or set(item) - {"item_id", "decision", "value"}
                or not {"item_id", "decision"} <= set(item)
            ):
                raise ValueError("Invalid item decision")
            key, decision = item["item_id"], item["decision"]
            if key not in known or key in seen or decision not in {"approve", "edit", "reject"}:
                raise ValueError("Unknown, repeated or invalid item decision")
            seen.add(key)
            if decision == "reject":
                approved.pop(key, None)
            elif decision == "approve":
                approved[key] = copy.deepcopy(known[key])
            else:
                value = item.get("value")
                if type(value) is not dict:
                    raise ValueError("Edited item must be an object")
                allowed = (
                    {"domain"}
                    if key.startswith("domain:")
                    else {"text", "property_template_id"}
                    if key.startswith("requirement:")
                    else {"args", "expected"}
                )
                if set(value) - allowed:
                    raise ValueError("Edited item changes protected fields")
                approved[key] = {**copy.deepcopy(known[key]), **value}
        domains = []
        for d in draft["arg_domains"]:
            item = approved.get(f"domain:{d['param']}")
            if item is None:
                raise ValueError("Every positional argument needs an approved domain")
            domains.append({"name": d["param"], "domain": item["domain"]})
        requirements = []
        for r in draft["requirements"]:
            item = approved.get(f"requirement:{r['id']}")
            if item:
                requirements.append(
                    {
                        "schema_version": "stage2.v1",
                        "requirement_id": r["id"],
                        "description": item["text"],
                        "source": "user",
                        "approval_status": "approved",
                        "property_template_id": item["property_template_id"],
                        "parameters": {},
                    }
                )
        if not requirements:
            raise ValueError("At least one approved requirement is needed")
        tests = []
        for e in draft["examples"]:
            item = approved.get(f"example:{e['id']}")
            if item:
                tests.append(
                    {
                        "schema_version": "stage2.v1",
                        "test_id": e["id"],
                        "inputs": item["args"],
                        "expected": item["expected"],
                        "requirement_ids": [r["requirement_id"] for r in requirements],
                    }
                )
        if not tests:
            raise ValueError(
                "At least one approved example is needed; "
                "proposed observations cannot accept a patch"
            )
        create = {
            "schema_version": "stage2.v1",
            "source": payload["source"],
            "function_name": payload["function_name"],
            "contract_text": payload["description"],
            "domain_schema": domains,
            "helper_interfaces": [],
            "requirements": requirements,
            "supplied_tests": tests,
            "allowed_dependencies": [],
            "resource_profile": "mac-standard-v1",
            "policy_mode": "learned",
            "seed": 17,
        }
        checked(create, "RunCreate")
        check_intake(create)
        prepare(create)
        authority = (
            VERDICT_LABEL
            if decisions.get("trust_interpreter")
            else "Verified against user-approved inferred requirements and examples"
        )
        return create, authority

    def approve(self, identifier, decisions, submit):
        # Serialise claim + acceptance storage so repeat clicks cannot start two runs.
        with self.lock:
            decision_hash = json_hash(decisions)
            with self.connect() as db:
                row = db.execute(
                    "SELECT decision_hash,accepted FROM drafts WHERE id=?", (identifier,)
                ).fetchone()
            if row is None:
                raise KeyError(identifier)
            if row[1]:
                if row[0] != decision_hash:
                    raise DraftConflict("Draft already submitted with different decisions")
                return json.loads(row[1])
            create, authority = self.build(identifier, decisions)
            accepted = submit(create)
            result = {
                "spec_version": 1,
                "draft_id": identifier,
                "accepted": accepted,
                "authority_label": authority,
            }
            with self.connect() as db:
                db.execute(
                    "UPDATE drafts SET decision_hash=?,accepted=? WHERE id=?",
                    (decision_hash, json.dumps(result), identifier),
                )
                db.execute(
                    "INSERT INTO events(draft_id,kind,body,created) VALUES(?,?,?,?)",
                    (
                        identifier,
                        "approved",
                        json.dumps({"decisions": decisions, "result": result}),
                        time.time(),
                    ),
                )
            return result

    def provenance_for_run(self, run_id):
        with self.connect() as db:
            rows = db.execute(
                "SELECT draft,accepted FROM drafts WHERE accepted IS NOT NULL"
            ).fetchall()
        for draft, accepted in rows:
            draft, accepted = map(json.loads, (draft, accepted))
            if accepted["accepted"]["run_id"] == run_id:
                return {
                    "authority_label": accepted["authority_label"],
                    "interpreter": draft["interpreter"],
                }
        return None
