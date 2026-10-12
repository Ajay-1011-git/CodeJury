"""Bounded single/two-edit search around committed parents.

Up to 3 parents are interleaved. Single edits run first; a beam (width 4) of partially
successful single-edit results seeds second edits. Candidates are executed on the known failing
checks first, then on the rest of the common suite. Partial success never qualifies; only
candidates that pass every authoritative test are returned.
"""

from dataclasses import dataclass, field

from ..domains import normalized_hash
from ..runner import Evaluator, hard_rejection
from .operators import FAMILIES, EditProposal, check_edit_result, enumerate_edits, overlaps, sha

MAX_EXECUTED = 48
MAX_PREFLIGHT = 192
BEAM = 4


@dataclass
class SearchOutcome:
    candidates: list[dict] = field(default_factory=list)
    executions: list[dict] = field(default_factory=list)
    edit_sources: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    search_candidates: int = 0
    preflight: int = 0
    status: str = "ok"


@dataclass
class _Item:
    source: str
    edits: list
    root: dict
    score: int
    full: bool
    intermediate: str | None = None


class SearchEngine:
    def __init__(
        self,
        evaluator: Evaluator,
        problem: dict,
        parents: list[dict],
        tests: list[dict],
        *,
        sites: list[dict],
        families: list[str],
        depth: int,
        candidate_limit: int,
        id_prefix: str,
        reserve_executions: int | None = None,
        max_preflight: int = MAX_PREFLIGHT,
    ):
        self.ev = evaluator
        self.problem = problem
        self.parents = parents[:3]
        self.tests = [t for t in tests if t["domain_valid"] and t["oracle_status"] != "rejected"]
        self.hard = [t for t in self.tests if t["oracle_status"] == "authoritative"]
        self.sites = sites
        self.families = [f for f in FAMILIES if f in families]
        self.depth = depth
        self.limit = min(candidate_limit, MAX_EXECUTED)
        self.prefix = id_prefix
        self.reserve = len(self.tests) if reserve_executions is None else reserve_executions
        self.max_preflight = max_preflight
        self.out = SearchOutcome()
        self._seen: set[str] = set()
        self._failing: dict[str, list[dict]] = {}
        self._hints: dict[str, list[int]] = {}
        self._n_candidates = 0

    # -- helpers --------------------------------------------------------------------------
    def _stop(self) -> bool:
        if self.ev.cancelled or self.ev.cancel.is_set():
            self.out.status = "cancelled"
            return True
        if self.out.search_candidates >= self.limit:
            return True
        if self.ev.remaining <= self.reserve:
            self.ev.exhausted = True
            self.out.status = "budget_exhausted"
            return True
        return False

    def _prepare_parents(self) -> list[dict]:
        usable = []
        for parent in self.parents:
            rows = self.ev.evaluate(parent, self.hard)
            if self.ev.cancelled:
                break
            if not rows and parent["candidate_id"] in self.ev.static_rejections:
                self.out.warnings.append(
                    f"parent {parent['candidate_id']} skipped: "
                    f"{self.ev.static_rejections[parent['candidate_id']]}"
                )
                continue
            self.out.executions.extend(rows)
            by_id = {t["test_id"]: t for t in self.hard}
            failing = [by_id[r["test_id"]] for r in rows if hard_rejection(r, by_id[r["test_id"]])]
            self._failing[parent["candidate_id"]] = failing
            self._hints[parent["candidate_id"]] = [
                r["exception"]["location"]["lineno"]
                for r in rows
                if r["exception"] and r["exception"]["location"]
            ]
            self._seen.add(normalized_hash(parent["source"]))
            usable.append(parent)
        return usable

    def _rank(self, proposals: list[EditProposal], root_id: str) -> list[EditProposal]:
        lines = set(self._hints.get(root_id, []))

        def key(p: EditProposal):
            hinted = any(overlaps(p.location, s) for s in self.sites)
            evidence = p.location["lineno"] in lines
            return (
                not hinted,
                not evidence,
                self.families.index(p.family),
                p.location["lineno"],
                p.location["col_offset"],
            )

        return sorted(proposals, key=key)

    def _proposals(self, source: str, root_id: str) -> list[EditProposal]:
        room = self.max_preflight - self.out.preflight
        if room <= 0:
            return []
        raw = enumerate_edits(source, self.families, limit=room)
        self.out.preflight += len(raw)
        ok = []
        for proposal in raw:
            if check_edit_result(proposal, source, self.problem) is not None:
                continue
            norm = normalized_hash(proposal.source)
            if norm in self._seen:
                continue
            self._seen.add(norm)
            ok.append(proposal)
        return self._rank(ok, root_id)

    def _run(self, parent: dict, source: str, edits: list[dict], intermediate=None):
        """Execute one search candidate; returns an _Item or None when nothing ran."""
        cid = f"{self.prefix}-c{self._n_candidates:03d}"
        shell = {"candidate_id": cid, "source": source}
        known = self._failing[parent["candidate_id"]]
        rows = self.ev.evaluate(shell, known, check=False)
        if not rows and known:
            return None
        self.out.search_candidates += 1
        by_id = {t["test_id"]: t for t in self.hard}
        passed = sum(1 for r in rows if r["outcome"] == "pass")
        full = passed == len(known) and len(rows) == len(known)
        if full:
            rest = [t for t in self.tests if t["test_id"] not in {r["test_id"] for r in rows}]
            more = self.ev.evaluate(shell, rest, stop_on_first_hard_failure=True, check=False)
            rows += more
            full = len(rows) == len(self.tests) and not any(
                hard_rejection(r, by_id.get(r["test_id"], {"oracle_status": ""})) for r in rows
            )
        item = _Item(source, edits, parent, passed, full, intermediate)
        if full:
            self._n_candidates += 1
            self.out.executions.extend(rows)
            self.out.candidates.append(self._draft(cid, item))
            if intermediate is not None:
                self.out.edit_sources.append(
                    {
                        "schema_version": "stage2.v1",
                        "source_hash": sha(intermediate),
                        "source": intermediate,
                    }
                )
        return item

    def _draft(self, cid: str, item: _Item) -> dict:
        edits = item.edits
        where = ", ".join(f"line {e['location']['lineno']} ({e['operator_family']})" for e in edits)
        return {
            "schema_version": "stage2.v1",
            "candidate_id": cid,
            "problem_id": self.problem["problem_id"],
            "parent_id": item.root["candidate_id"],
            "origin": "ast_search",
            "generation_view": "ast_search",
            "source": item.source,
            "source_hash": sha(item.source),
            "diagnosis": f"AST search edit {where}; qualification requires the full suite.",
            "assumptions": [],
            "requirement_ids": item.root.get("requirement_ids", []),
            "model_config_hash": None,
            "edits": edits,
        }

    # -- search ---------------------------------------------------------------------------
    def run(self) -> SearchOutcome:
        parents = self._prepare_parents()
        if not parents:
            if self.out.status == "ok" and not self.ev.cancelled:
                self.out.warnings.append("no usable parent to search around")
            return self._finish()
        level1: list[_Item] = []
        queues = {
            p["candidate_id"]: self._proposals(p["source"], p["candidate_id"]) for p in parents
        }
        progressed = True
        while progressed and not self._stop():
            progressed = False
            for parent in parents:  # interleave parents
                queue = queues[parent["candidate_id"]]
                if not queue or self._stop():
                    continue
                progressed = True
                p = queue.pop(0)
                item = self._run(parent, p.source, [p.edit()])
                if item is not None:
                    item.intermediate = None
                    level1.append(item)
        if self.depth == 2 and not self._stop():
            self._second_level(level1)
        return self._finish()

    def _second_level(self, level1: list[_Item]) -> None:
        promising = [i for i in level1 if not i.full and i.score > 0]
        promising.sort(key=lambda i: -i.score)
        beam = promising[:BEAM]
        if not beam:
            self.out.warnings.append("no partially successful parent for second edits")
            return
        queues = []
        for item in beam:
            first = item.edits[0]
            queues.append((item, self._proposals(item.source, item.root["candidate_id"]), first))
        progressed = True
        while progressed and not self._stop():
            progressed = False
            for item, queue, first in queues:
                if not queue or self._stop():
                    continue
                progressed = True
                p = queue.pop(0)
                edits = [first, p.edit()]
                self._run(item.root, p.source, edits, intermediate=item.source)

    def _finish(self) -> SearchOutcome:
        if self.ev.cancelled:
            self.out.status = "cancelled"
        elif self.out.status == "ok" and self.ev.exhausted:
            self.out.status = "budget_exhausted"
        seen, unique = set(), []
        for artifact in self.out.edit_sources:
            if artifact["source_hash"] not in seen:
                seen.add(artifact["source_hash"])
                unique.append(artifact)
        self.out.edit_sources = unique
        if self.out.search_candidates >= MAX_EXECUTED:
            self.out.warnings.append("48-candidate search cap reached")
        if self.out.preflight >= self.max_preflight:
            self.out.warnings.append("preflight proposal cap reached")
        return self.out
