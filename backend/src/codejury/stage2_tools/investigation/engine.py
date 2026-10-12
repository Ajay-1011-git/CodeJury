"""Oracle-gated investigation: explore, shrink, replay, then admit.

Predicates run through the sandbox seam only. A model-proposed literal or observation can guide
exploration but is quarantined (never hard evidence). A failure is admitted as an authoritative
test only when the oracle is authorized, the shrunk input is domain-valid and an independent
replay fails again.
"""

import random
from dataclasses import dataclass, field

from hypothesis import HealthCheck, Phase, find, given, seed, settings
from hypothesis import strategies as st
from hypothesis.errors import NoSuchExample

from ..codec import value_hash
from ..domains import check_args
from ..oracles import OracleError, admit_test, oracle_version, relation_followup
from ..runner import Evaluator, hard_rejection
from .strategies import FAMILIES, for_family, general, invalid_missing_key

MAX_INPUTS = 128
MAX_TESTS_PER_RUN = 512
MAX_RESULT_TESTS = 128
SHRINK_EXAMPLES = 60
SHRINK_CALL_CAP = 64


class InvestigationError(ValueError):
    pass


class _Stop(Exception):
    """Budget or cancellation reached inside a Hypothesis predicate."""


@dataclass
class InvestigationOutcome:
    tests: list[dict] = field(default_factory=list)
    executions: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "ok"


def _int_constants(source: str) -> tuple[int, ...]:
    import ast

    return tuple(
        sorted(
            {
                n.value
                for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.Constant) and type(n.value) is int
            }
        )
    )


class Investigator:
    def __init__(
        self,
        evaluator: Evaluator,
        problem: dict,
        proposal: dict,
        candidates: list[dict],
        existing_tests: list[dict],
        *,
        max_inputs: int,
        id_prefix: str,
    ):
        self.ev = evaluator
        self.problem = problem
        self.proposal = proposal
        self.candidates = candidates
        self.existing = existing_tests
        self.max_inputs = min(max_inputs, MAX_INPUTS)
        self.prefix = id_prefix
        self.out = InvestigationOutcome()
        self._n_tests = 0
        self._cache: dict[tuple[str, str], bool] = {}
        self._shrink_calls = 0

    # -- validation -----------------------------------------------------------------------
    def validate(self) -> None:
        p = self.proposal
        if (p["generator_spec"] is None) == (p["concrete_inputs"] is None):
            raise InvestigationError("Exactly one of generator_spec or concrete_inputs is required")
        known = {r["requirement_id"] for r in self.problem["requirements"]}
        if set(p["requirement_ids"]) - known:
            raise InvestigationError("Proposal cites unknown requirements")
        ids = {c["candidate_id"] for c in self.candidates}
        if set(p["target_candidate_ids"]) - ids:
            raise InvestigationError("Proposal targets unknown candidates")
        spec = p["generator_spec"]
        if spec is not None:
            if spec["family"] not in FAMILIES:
                raise InvestigationError(f"Unregistered generator family {spec['family']}")
            if spec["argument_index"] >= len(self.problem["domain_schema"]):
                raise InvestigationError("argument_index is outside the signature")
            if self._strategy(spec) is None and spec["family"] != "missing_key":
                raise InvestigationError(
                    f"Family {spec['family']} is unsupported for this argument domain"
                )
        oracle = p["oracle_spec"]
        if oracle["kind"] == "metamorphic" and oracle["relation_id"] not in (
            "permutation_invariant",
            "idempotent",
        ):
            raise InvestigationError("Unregistered metamorphic relation")
        if oracle["kind"] == "property" and oracle["property_id"] not in {
            "sort_ascending_ints",
            "unique_preserve_order_ints",
            "sum_ints",
            "reverse_string",
            "count_occurrences_ints",
        }:
            raise InvestigationError("Unregistered property template")

    def _targets(self) -> list[dict]:
        wanted = self.proposal["target_candidate_ids"]
        return [c for c in self.candidates if not wanted or c["candidate_id"] in wanted]

    # -- tests ----------------------------------------------------------------------------
    def _provenance(self) -> str:
        spec = self.proposal["generator_spec"]
        if spec is None:
            return "critic"
        return "audit_followup" if spec["family"] == "audit_site" else "property_engine"

    def _make_test(self, inputs: list, test_id: str) -> dict | None:
        p = self.proposal
        oracle = p["oracle_spec"]
        related = None
        if oracle["kind"] == "metamorphic":
            related = relation_followup(
                oracle["relation_id"], inputs, (p["generator_spec"] or {"seed": 0})["seed"]
            )
        has_auth = any(
            r["approval_status"] == "approved" and r["requirement_id"] in p["requirement_ids"]
            for r in self.problem["requirements"]
        )
        test = {
            "schema_version": "stage2.v1",
            "test_id": test_id,
            "input_codec_version": "json.v1",
            "inputs": inputs,
            "related_inputs": related,
            "oracle_spec": oracle,
            "oracle_status": "proposed",
            "oracle_source": "reviewed_contract"
            if has_auth and oracle["kind"] != "literal"
            else "model",
            "domain_valid": True,
            "requirement_ids": p["requirement_ids"],
            "provenance": self._provenance(),
        }
        try:
            return admit_test(test, self.problem)
        except OracleError as exc:
            self.out.warnings.append(f"{test_id}: {exc}")
            return None

    def _duplicate(self, test: dict, registered: list[dict]) -> bool:
        key = (
            value_hash(test["inputs"]),
            value_hash(test["related_inputs"]),
            oracle_version(test["oracle_spec"]),
            value_hash(test["oracle_spec"]),
        )
        for existing in self.existing + registered:
            other = (
                value_hash(existing["inputs"]),
                value_hash(existing["related_inputs"]),
                oracle_version(existing["oracle_spec"]),
                value_hash(existing["oracle_spec"]),
            )
            if other == key:
                return True
        return False

    def _next_id(self) -> str:
        test_id = f"{self.prefix}-t{self._n_tests:03d}"
        self._n_tests += 1
        return test_id

    # -- generation -------------------------------------------------------------------------
    def _strategy(self, spec: dict):
        schema = self.problem["domain_schema"]
        index = spec["argument_index"]
        constants = _int_constants(self.problem["source"]) if spec["family"] == "audit_site" else ()
        focus = for_family(schema[index]["domain"], spec["family"], constants=constants)
        if focus is None:
            return None
        parts = [focus if i == index else general(a["domain"]) for i, a in enumerate(schema)]
        return st.tuples(*parts).map(list)

    def _generate(self) -> list[list]:
        p = self.proposal
        if p["concrete_inputs"] is not None:
            return p["concrete_inputs"][: self.max_inputs]
        spec = p["generator_spec"]
        if spec["family"] == "missing_key":
            bad = invalid_missing_key(
                self.problem["domain_schema"][spec["argument_index"]]["domain"]
            )
            if bad is None:
                return []
            schema = self.problem["domain_schema"]
            parts = [
                bad if i == spec["argument_index"] else general(a["domain"])
                for i, a in enumerate(schema)
            ]
            strategy = st.tuples(*parts).map(list)
        else:
            strategy = self._strategy(spec)
        seen: dict[str, list] = {}
        n = self.max_inputs

        @seed(spec["seed"])
        @settings(
            max_examples=n,
            database=None,
            deadline=None,
            phases=[Phase.generate],
            suppress_health_check=list(HealthCheck),
            derandomize=False,
        )
        @given(strategy)
        def collect(value):
            seen.setdefault(value_hash(value), value)

        try:
            collect()
        except Exception as exc:  # noqa: BLE001 - generation failures are reported, not hidden
            self.out.warnings.append(f"generation stopped: {type(exc).__name__}")
        return list(seen.values())[:n]

    # -- evaluation -------------------------------------------------------------------------
    def _fails(self, candidate: dict, inputs: list) -> bool:
        """Predicate for shrinking: a real, charged sandbox call, memoized per candidate/input."""
        key = (candidate["candidate_id"], value_hash(inputs))
        if key in self._cache:
            return self._cache[key]
        if (
            self.ev.cancel.is_set()
            or self._shrink_calls >= SHRINK_CALL_CAP
            or self.ev.remaining < 1
        ):
            raise _Stop()
        probe = self._make_test(inputs, "probe")
        if probe is None or not probe["domain_valid"]:
            self._cache[key] = False
            return False
        self._shrink_calls += 1
        rows = self.ev.evaluate(candidate, [probe], check=False)
        if not rows:
            raise _Stop()
        failed = hard_rejection(rows[0], probe)
        self._cache[key] = failed
        return failed

    def _shrink(self, candidate: dict, inputs: list) -> list:
        spec = self.proposal["generator_spec"]
        if spec is None or spec["family"] == "missing_key":
            return inputs
        strategy = self._strategy(spec)
        try:
            return find(
                strategy,
                lambda value: self._fails(candidate, value),
                settings=settings(
                    max_examples=SHRINK_EXAMPLES,
                    database=None,
                    deadline=None,
                    suppress_health_check=list(HealthCheck),
                    derandomize=False,
                ),
                random=random.Random(spec["seed"]),
            )
        except _Stop:
            self.out.warnings.append(
                "shrinking stopped by budget/cancel; smallest observed failure kept"
            )
        except NoSuchExample:
            self.out.warnings.append("shrink search found no failing input; original kept")
        return inputs

    def run(self) -> InvestigationOutcome:
        self.validate()
        targets = self._targets()
        if not targets:
            self.out.warnings.append("no target candidates")
            return self.out
        inputs = self._generate()
        if not inputs:
            self.out.warnings.append("generator produced no inputs")
            return self.out
        registered: list[dict] = []
        scratch = []
        for vector in inputs:
            test = self._make_test(vector, f"{self.prefix}-x{len(scratch):03d}")
            if test is None:
                continue
            scratch.append(test)
        runnable = [t for t in scratch if t["domain_valid"] and t["oracle_status"] != "rejected"]
        for t in scratch:
            if not t["domain_valid"] or t["oracle_status"] == "rejected":
                self._register(registered, t, quarantine=True)
        authoritative = bool(runnable) and runnable[0]["oracle_status"] == "authoritative"
        failures: dict[str, tuple[dict, list]] = {}
        explore = not (authoritative and self.proposal["concrete_inputs"] is not None)
        for candidate in targets if explore else []:
            rows = self.ev.evaluate(
                candidate, runnable, stop_on_first_hard_failure=True, check=False
            )
            by_id = {t["test_id"]: t for t in runnable}
            for row in rows:
                if hard_rejection(row, by_id[row["test_id"]]):
                    failures[candidate["candidate_id"]] = (
                        candidate,
                        by_id[row["test_id"]]["inputs"],
                    )
                    break
            if self.ev.cancelled or self.ev.exhausted:
                break
        if authoritative and self.proposal["concrete_inputs"] is not None:
            # The Critic chose these experiments: every domain-valid one joins the suite.
            for t in runnable:
                self._register(registered, {**t, "test_id": self._next_id()})
        elif authoritative:
            chosen: list[list] = []
            for candidate, vector in failures.values():
                minimal = self._shrink(candidate, vector)
                if (
                    check_args(self.problem["domain_schema"], minimal) is None
                    and minimal not in chosen
                ):
                    chosen.append(minimal)
            for vector in chosen:
                self._register(registered, self._make_test(vector, self._next_id()))
            if not failures:
                self.out.warnings.append("no authorized failure found; nothing admitted")
        else:
            # Quarantine: keep the (bounded) experiment as observation/proposed evidence only.
            for t in runnable[:8]:
                self._register(registered, {**t, "test_id": self._next_id()}, quarantine=True)
        self._evaluate_registered(registered, targets, failures if authoritative else {})
        self.out.tests = registered[:MAX_RESULT_TESTS]
        if self.ev.cancelled:
            self.out.status = "cancelled"
        elif self.ev.exhausted:
            self.out.status = "budget_exhausted"
        return self.out

    def _register(self, registered, test, quarantine=False):
        if test is None:
            return
        if len(self.existing) + len(registered) >= MAX_TESTS_PER_RUN:
            self.out.warnings.append("512-test registry cap reached")
            return
        if test["domain_valid"] and self._duplicate(test, registered):
            self.out.warnings.append(
                f"duplicate of an existing test ignored for {test['inputs']!r}"
            )
            return
        if quarantine and test["oracle_status"] == "authoritative":
            test = {**test, "oracle_status": "proposed"}
        registered.append(test)

    def _evaluate_registered(self, registered, targets, failures):
        runnable = [t for t in registered if t["domain_valid"] and t["oracle_status"] != "rejected"]
        rows_by_test: dict[str, list[dict]] = {}
        for candidate in targets:
            if self.ev.cancelled or self.ev.exhausted:
                break
            for row in self.ev.evaluate(candidate, runnable, check=False):
                rows_by_test.setdefault(row["test_id"], []).append(row)
                self.out.executions.append(row)
        # Independent replay: an admitted authoritative failure must fail again, or it is
        # downgraded to quarantine rather than certified.
        for index, test in enumerate(registered):
            if test["oracle_status"] != "authoritative" or test["test_id"] not in rows_by_test:
                continue
            replayed = [r for r in rows_by_test[test["test_id"]] if r["candidate_id"] in failures]
            expected_fail = [cid for cid, (_, vec) in failures.items() if vec == test["inputs"]]
            for cid in expected_fail:
                row = next((r for r in replayed if r["candidate_id"] == cid), None)
                if row is not None and not hard_rejection(row, test):
                    self.out.warnings.append(
                        f"replay of {test['test_id']} did not fail for {cid}; test quarantined"
                    )
                    registered[index] = {**test, "oracle_status": "proposed"}
