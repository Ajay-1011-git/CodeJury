"""Mutation auditor: probes expose observable blind spots in a frozen suite.

A mutant is an evidence probe, never a selectable candidate and never a jury vote. Only an
authoritative-test rejection kills a mutant; a survivor may be equivalent or a genuine test gap
and never accuses its parent on its own.
"""

from dataclasses import dataclass, field

from ..codec import typed_equal
from ..oracles import suite_hash
from ..runner import Evaluator, hard_rejection
from ..search.operators import FAMILIES, EditProposal, check_edit_result, enumerate_edits, sha

MAX_PER_VERSION = 24
MAX_PER_EPISODE = 48
PREFLIGHT = 96
OBSERVATION_CAP = 32


@dataclass
class AuditCache:
    """Outcomes keyed by (mutant source hash, suite hash); reuse costs no executions."""

    rows: dict = field(default_factory=dict)


@dataclass
class AuditOutcome:
    mutants: list[dict] = field(default_factory=list)
    gaps: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "ok"
    preflight: int = 0


def gap_is_stale(gap: dict, candidate_source_hash: str, current_suite_hash: str) -> bool:
    """A gap only accuses the exact source and suite it was observed on."""
    return gap["candidate_source_hash"] != candidate_source_hash or gap["suite_hash"] != (
        current_suite_hash
    )


def _order(proposals: list[EditProposal]) -> list[EditProposal]:
    """Round-robin across families so a small probe budget covers diverse sites."""
    by_family = {f: [] for f in FAMILIES}
    for p in proposals:
        by_family[p.family].append(p)
    for items in by_family.values():
        items.sort(key=lambda p: (p.location["lineno"], p.location["col_offset"]))
    out, queues = [], [list(v) for v in by_family.values() if v]
    while queues:
        for q in queues:
            out.append(q.pop(0))
        queues = [q for q in queues if q]
    return out


class Auditor:
    def __init__(
        self,
        evaluator: Evaluator,
        problem: dict,
        candidate: dict,
        tests: list[dict],
        *,
        max_mutants: int,
        suite: str,
        id_prefix: str,
        episode_remaining: int = MAX_PER_EPISODE,
        requirement_ids: list[str] | None = None,
        cache: AuditCache | None = None,
    ):
        self.ev = evaluator
        self.problem = problem
        self.candidate = candidate
        self.tests = [t for t in tests if t["domain_valid"] and t["oracle_status"] != "rejected"]
        self.hard = [t for t in self.tests if t["oracle_status"] == "authoritative"]
        self.observation = [t for t in self.tests if t["oracle_status"] != "authoritative"]
        self.observation = self.observation[:OBSERVATION_CAP]
        self.limit = max(0, min(max_mutants, MAX_PER_VERSION, episode_remaining, MAX_PER_EPISODE))
        self.suite = suite
        self.prefix = id_prefix
        self.requirement_ids = requirement_ids or []
        self.cache = cache if cache is not None else AuditCache()
        self.out = AuditOutcome()
        self._parent_obs: list[dict] | None = None

    # -- evidence -------------------------------------------------------------------------
    def _parent_observations(self) -> list[dict]:
        if self._parent_obs is None:
            shell = {
                "candidate_id": self.candidate["candidate_id"],
                "source": self.candidate["source"],
            }
            self._parent_obs = self.ev.evaluate(shell, self.observation, check=False)
        return self._parent_obs

    def _classify(self, proposal: EditProposal) -> dict:
        """Run one mutant; returns {outcome, test_ids, equivalence} or {} if not completed."""
        key = (proposal.result_source_hash, self.suite)
        if key in self.cache.rows:
            return self.cache.rows[key]
        shell = {"candidate_id": "mutant", "source": proposal.source}
        rows = self.ev.evaluate(shell, self.hard, stop_on_first_hard_failure=True, check=False)
        by_id = {t["test_id"]: t for t in self.hard}
        if self.ev.cancelled or (len(rows) < len(self.hard) and self.ev.exhausted):
            return {}
        rejects = [r for r in rows if hard_rejection(r, by_id[r["test_id"]])]
        if rejects:
            first = rejects[0]
            if first["outcome"] == "timeout":
                result = {
                    "outcome": "timeout",
                    "test_ids": [first["test_id"]],
                    "equivalence": "unknown",
                }
            elif first["exception"] and (
                first["exception"]["message"] == "source does not compile"
            ):
                result = {"outcome": "invalid", "test_ids": [], "equivalence": "unknown"}
            else:
                result = {
                    "outcome": "killed",
                    "test_ids": [first["test_id"]],
                    "equivalence": "observed_different",
                }
        else:
            result = {
                "outcome": "survived",
                "test_ids": [r["test_id"] for r in rows],
                "equivalence": self._equivalence(shell),
            }
        self.cache.rows[key] = result
        return result

    def _equivalence(self, shell: dict) -> str:
        if not self.observation:
            return "unknown"
        parent = {r["test_id"]: r for r in self._parent_observations()}
        rows = self.ev.evaluate(shell, self.observation, check=False)
        compared = 0
        for row in rows:
            base = parent.get(row["test_id"])
            if (
                base is None
                or "error" in (row["outcome"], base["outcome"])
                or "timeout" in (row["outcome"], base["outcome"])
            ):
                continue
            compared += 1
            if not typed_equal(row["actual_output"], base["actual_output"]):
                return "observed_different"
        return "observed_equivalent" if compared else "unknown"

    # -- run ------------------------------------------------------------------------------
    def run(self) -> AuditOutcome:
        out = self.out
        if self.limit == 0:
            out.status = "budget_exhausted"
            out.warnings.append("no audit probe budget remains")
            return out
        raw = enumerate_edits(self.candidate["source"], FAMILIES, limit=PREFLIGHT)
        out.preflight = len(raw)
        seen = {sha(self.candidate["source"])}
        records = []
        for p in _order(raw):
            if len(records) >= self.limit:
                break
            if p.result_source_hash in seen:
                records.append(
                    (p, {"outcome": "duplicate", "test_ids": [], "equivalence": "unknown"})
                )
                continue
            seen.add(p.result_source_hash)
            reason = check_edit_result(p, self.candidate["source"], self.problem)
            if reason == "no-op edit":
                records.append(
                    (p, {"outcome": "duplicate", "test_ids": [], "equivalence": "unknown"})
                )
            elif reason is not None:
                records.append(
                    (p, {"outcome": "invalid", "test_ids": [], "equivalence": "unknown"})
                )
            else:
                records.append((p, None))
        if len(raw) >= PREFLIGHT:
            out.warnings.append("96-proposal preflight cap reached")
        n = 0
        for proposal, preset in records:
            if self.ev.cancel.is_set():
                self.ev.cancelled = True
            result = preset if preset is not None else self._classify(proposal)
            if not result:
                break
            out.mutants.append(self._mutant(n, proposal, result))
            n += 1
        out.gaps = self._gaps()
        if self.ev.cancelled:
            out.status = "cancelled"
        elif self.ev.exhausted and len(out.mutants) < len(records):
            out.status = "budget_exhausted"
        if not self.hard:
            out.warnings.append("no authoritative tests: every probe is unresolved")
        return out

    def _mutant(self, n: int, p: EditProposal, result: dict) -> dict:
        return {
            "schema_version": "stage2.v1",
            "mutant_id": f"{self.prefix}-m{n:03d}",
            "parent_candidate_id": self.candidate["candidate_id"],
            "source": p.source,
            "source_hash": p.result_source_hash,
            "edit": p.edit(),
            "outcome": result["outcome"],
            "test_ids": result["test_ids"],
            "equivalence_status": result["equivalence"],
            "suite_hash": self.suite,
        }

    def _gaps(self) -> list[dict]:
        groups: dict[tuple, list[dict]] = {}
        for m in self.out.mutants:
            loc = m["edit"]["location"]
            key = (
                loc["lineno"],
                loc["col_offset"],
                loc["end_lineno"],
                loc["end_col_offset"],
                m["edit"]["operator_family"],
            )
            groups.setdefault(key, []).append(m)
        gaps = []
        for key in sorted(groups):
            members = groups[key]
            if not any(m["outcome"] == "survived" for m in members):
                continue
            n = len(gaps)
            gap_id = f"{self.prefix}-g{n:03d}"
            if not self.requirement_ids:
                self.out.warnings.append(f"{gap_id}: no reviewed requirement mapping")
            gaps.append(
                {
                    "schema_version": "stage2.v1",
                    "gap_id": gap_id,
                    "candidate_id": self.candidate["candidate_id"],
                    "candidate_source_hash": sha(self.candidate["source"]),
                    "location": members[0]["edit"]["location"],
                    "operator_family": key[4],
                    "mutant_ids": [m["mutant_id"] for m in members][:24],
                    "observed_outcomes": [
                        {"mutant_id": m["mutant_id"], "outcome": m["outcome"]} for m in members
                    ][:24],
                    "requirement_ids": list(self.requirement_ids),
                    "suite_hash": self.suite,
                    "interpretation": "unresolved_test_gap",
                }
            )
        return gaps


def verify_suite(tests: list[dict], claimed: str) -> bool:
    return suite_hash(tests) == claimed
