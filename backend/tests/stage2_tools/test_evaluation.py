import copy
import json
import threading
import time

import pytest
from conftest import BACKEND

from codejury.stage2_tools.codec import errors, sha256_text
from codejury.stage2_tools.evaluation import (
    Harness,
    HarnessError,
    analyze,
    fixtures,
    load_config,
    paired_bootstrap,
    parity,
)
from codejury.stage2_tools.evaluation import config as cfg
from codejury.stage2_tools.evaluation.stats import outcome

VALID = BACKEND / "config/stage2_tools/evaluation-validation.yaml"
FINAL = BACKEND / "config/stage2_tools/evaluation.yaml"


@pytest.fixture
def config():
    return load_config(VALID)


def run_fixture(config, tmp_path, port=None, scorer=None, tasks=None, plan=None):
    h = Harness(
        config,
        port or fixtures.FixtureBaselinePort(),
        scorer or fixtures.FixtureScorer(),
        mode="fixture",
        out_dir=tmp_path,
    )
    tasks = tasks or fixtures.tasks()
    h.preflight(tasks)
    return h, h.run(tasks, plan), tasks


def test_config_rules():
    final = load_config(FINAL)
    assert final["split"] == "final_assessment" and final["seeds"][0] == final["public_seed"]
    assert load_config(VALID)["split"] == "validation"
    bad = copy.deepcopy(final)
    bad["seeds"] = [1, 2]
    with pytest.raises(cfg.ConfigError):
        cfg.load  # noqa: B018
        import yaml

        (BACKEND / "_tmp.yaml").write_text(yaml.safe_dump(bad))
        try:
            load_config(BACKEND / "_tmp.yaml")
        finally:
            (BACKEND / "_tmp.yaml").unlink()


def test_validation_profile_can_never_target_the_final_split(tmp_path):
    import yaml

    bad = yaml.safe_load(VALID.read_text())
    bad["split"] = "final_assessment"
    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump(bad))
    with pytest.raises(cfg.ConfigError, match="never use the sealed final"):
        load_config(path)


def test_plan_covers_every_method_ablation_and_time_matched_variants(config):
    methods = {(p["method"], p["regime"]) for p in cfg.plan(config)}
    for m in cfg.CORE:
        assert any(x[0] == m for x in methods)
    assert {m for m, _ in methods} >= set(cfg.ABLATIONS)
    assert ("CJ", "time_matched") in methods and ("CJ", "token_matched") in methods
    assert cfg.config_hash(config, "CJ", "token_matched") != cfg.config_hash(
        config, "CJ", "time_matched"
    )


def test_selected_patch_vs_pool_best_are_distinct(config, tmp_path):
    h, records, _ = run_fixture(config, tmp_path)
    row = next(
        r
        for r in records
        if r["method"] == "CJ"
        and r["task_id"] == "fx-7"
        and r["regime"] == "token_matched"
        and r["seed"] == 11
    )
    assert row["category"] == "incorrect_accepted" and row["pool_has_correct"] is True
    result = analyze(config, records, manifest_hash=None, dataset_id="fx", mode="fixture")
    cj = next(r for r in result["report"]["rows"] if r["method"] == "CJ")
    # the headline count comes from the selected patch, not the oracle-best candidate
    first = [
        r
        for r in records
        if r["method"] == "CJ" and r["regime"] == "token_matched" and r["seed"] == 11
    ]
    assert cj["solved"] == sum(1 for r in first if r["category"] == "solved")
    sec = result["secondary"]["CJ|token_matched"]
    assert sec["pool_contains_correct"] > cj["solved"]
    assert sec["selected_correct_given_pool_correct"] < 1.0


def test_commitments_precede_scoring_and_no_hidden_data_reaches_methods(config, tmp_path):
    events = []
    port = fixtures.FixtureBaselinePort()
    real_run = port.run

    def spy_run(request, cancel):
        events.append("run")
        return real_run(request, cancel)

    port.run = spy_run

    class Spy(fixtures.FixtureScorer):
        def score(self, task, source):
            events.append("score")
            return super().score(task, source)

    h, records, tasks = run_fixture(config, tmp_path, port=port, scorer=Spy())
    first_score = events.index("score")
    assert "score" not in events[:first_score] and events[:first_score].count("run") == len(
        [r for r in records]
    )
    assert events.index("score") > max(i for i, e in enumerate(events) if e == "run")
    blob = json.dumps(port.requests)
    for task in tasks:
        assert task.hidden["reference_source"] not in blob
        assert "hidden" not in blob and "fixture_correct_hashes" not in blob
        assert json.dumps(task.hidden["tests"][0]["inputs"]) not in blob


def test_commitment_log_is_append_only_per_run_and_tamper_evident(config, tmp_path):
    h, records, tasks = run_fixture(config, tmp_path)
    with pytest.raises(HarnessError, match="never overwritten"):
        h.commit_all(tasks, cfg.plan(config)[:1], [11])
    (tmp_path / "commitments.jsonl").write_text("tampered")
    with pytest.raises(HarnessError, match="Commitments changed"):
        h.score_all(records, tasks)


def test_identical_visible_inputs_and_caps_across_methods(config, tmp_path):
    h, records, _ = run_fixture(config, tmp_path)
    audit = parity.audit(config, records)
    assert audit["ok"], audit
    assert audit["reference_only"] == ["B0"]
    tampered = copy.deepcopy(records)
    tampered[0]["request_hash"] = "0" * 64
    assert not parity.audit(config, tampered)["ok"]
    weak = copy.deepcopy(config)
    weak["methods"]["B3"]["tools"] = ["evaluate"]
    assert any("B3 lacks" in p for p in parity.audit(weak, records)["problems"])
    caps = {
        r["method"]: h.request_for(fixtures.tasks()[0], r["method"], r["regime"], 11)
        for r in cfg.plan(config)
    }
    token = {
        m: v["resource_caps"]
        for m, v in caps.items()
        if config["methods"].get(m, {}).get("budget") == "token_matched"
    }
    assert len({json.dumps(c, sort_keys=True) for c in token.values()}) == 1


def test_denominators_partition_and_failures_stay_in_them(config, tmp_path):
    class Flaky(fixtures.FixtureBaselinePort):
        def run(self, request, cancel):
            if request["method"] == "B1" and "-fx-2-" in request["request_id"]:
                raise RuntimeError("port crashed")
            return super().run(request, cancel)

    h, records, _ = run_fixture(config, tmp_path, port=Flaky())
    crashed = [r for r in records if r["method"] == "B1" and r["task_id"] == "fx-2"]
    assert {r["category"] for r in crashed} == {"infrastructure_error"} and crashed[0]["error"]
    result = analyze(config, records, manifest_hash=None, dataset_id="fx", mode="fixture")
    for row in result["report"]["rows"]:
        total = sum(
            row[k]
            for k in (
                "solved",
                "incorrect_accepted",
                "unresolved",
                "invalid_input",
                "infrastructure_error",
                "cancelled",
            )
        )
        assert total == row["total_base_problems"] == 8
    b1 = next(r for r in result["report"]["rows"] if r["method"] == "B1")
    assert b1["infrastructure_error"] == 1


def test_time_matched_cutoff_cancels_slow_method_as_unsolved(config, tmp_path):
    cut = copy.deepcopy(config)
    cut["regimes"]["time_matched"]["cutoff_ms"] = 60

    class Slow(fixtures.FixtureBaselinePort):
        def run(self, request, cancel):
            result = super().run(request, cancel)
            if request["method"] == "CJ":
                cancel.wait(1.0)  # keeps working until the harness cutoff fires
            return result

    h, records, _ = run_fixture(
        cut,
        tmp_path,
        port=Slow(),
        plan=[{"method": "CJ", "regime": "time_matched", "budget": "time_matched"}],
    )
    # nothing finishing after the cutoff counts as an answer; unfinished work is unsolved
    assert {r["category"] for r in records} <= {"cancelled", "unresolved"}
    assert any(r["category"] == "cancelled" for r in records)
    assert all(r["selected_source_hash"] is None for r in records if r["category"] == "cancelled")


def test_invalid_or_mismatched_method_results_are_rejected(config, tmp_path):
    for mutate, message in (
        (lambda r: r.__setitem__("config_hash", "0" * 64), "config_hash"),
        (lambda r: r.__setitem__("selected_source_hash", "0" * 64), "does not match"),
        (lambda r: r.__setitem__("runtime_mode", "live"), "runtime_mode=fixture"),
        (lambda r: r.pop("candidate_pool"), "invalid MethodResult"),
    ):

        class Bad(fixtures.FixtureBaselinePort):
            def run(self, request, cancel, mutate=mutate):
                result = super().run(request, cancel)
                if result["selected_source"] is None:
                    return self.run(request, cancel) if False else result
                mutate(result)
                return result

        with pytest.raises(HarnessError, match=message):
            h = Harness(
                config,
                Bad(),
                fixtures.FixtureScorer(),
                mode="fixture",
                out_dir=tmp_path / message.replace(" ", "_"),
            )
            h.run(
                fixtures.tasks(),
                [{"method": "CJ", "regime": "token_matched", "budget": "token_matched"}],
            )  # noqa: E501


def test_final_profile_and_live_mode_reject_fixture_results(tmp_path):
    final = load_config(FINAL)
    with pytest.raises(HarnessError, match="rejects fixture"):
        Harness(
            final,
            fixtures.FixtureBaselinePort(),
            fixtures.FixtureScorer(),
            mode="fixture",
            out_dir=tmp_path,
        )
    live = Harness(
        load_config(VALID),
        fixtures.FixtureBaselinePort(),
        fixtures.FixtureScorer(),
        mode="live",
        out_dir=tmp_path,
    )
    with pytest.raises(HarnessError, match="Fixture results are rejected"):
        live.run(
            fixtures.tasks()[:1],
            [{"method": "CJ", "regime": "token_matched", "budget": "token_matched"}],
        )  # noqa: E501


def test_preflight_reports_original_population_and_exclusions(config, tmp_path):
    tasks = fixtures.tasks()
    bad = copy.deepcopy(tasks[0].run_create)
    bad["domain_schema"][0]["domain"]["item_domain"]["max"] = 10**9
    odd = type(tasks[0])("fx-bad", "fam-x", "natural", bad, tasks[0].hidden)
    h = Harness(
        config,
        fixtures.FixtureBaselinePort(),
        fixtures.FixtureScorer(),
        mode="fixture",
        out_dir=tmp_path,
    )
    report = h.preflight(tasks + [odd])
    assert report["original_population"] == 9 and report["eligible"] == 8
    assert report["excluded"][0]["task_id"] == "fx-bad"
    assert "unsupported by the frozen preflight" in report["excluded"][0]["reason"]


def test_duplicate_base_problems_are_refused(tmp_path):
    from codejury.stage2_tools.evaluation.tasks import load_tasks

    t = fixtures.tasks()[0]
    row = {
        "task_id": t.task_id,
        "family_id": t.family_id,
        "kind": t.kind,
        "run_create": t.run_create,
        "hidden": t.hidden,
    }
    path = tmp_path / "t.jsonl"
    path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="not independent"):
        load_tasks(path)


# ---- statistics ---------------------------------------------------------------------------


def test_bootstrap_is_deterministic_and_clusters_by_base_problem():
    a = {f"t{i}": 1.0 if i < 12 else 0.0 for i in range(20)}
    b = {f"t{i}": 0.0 for i in range(20)}
    one = paired_bootstrap(a, b, resamples=2000, seed=5)
    two = paired_bootstrap(a, b, resamples=2000, seed=5)
    assert one == two and one["n_problems"] == 20 and one["wins"] == 12 and one["ties"] == 8
    assert one["ci"][0] > 0 and abs(one["difference"] - 0.6) < 1e-9
    # more seeds of the same problems do not add independent problems
    records = []
    for seed in (1, 2, 3, 4, 5):
        for t in range(20):
            records.append(
                {
                    "method": "X",
                    "regime": "r",
                    "task_id": f"t{t}",
                    "seed": seed,
                    "category": "solved",
                }
            )
    from codejury.stage2_tools.evaluation import per_problem

    assert len(per_problem(records, "X", "r", "solved")) == 20


def test_empty_overlap_gives_nulls_not_zeros():
    result = paired_bootstrap({"a": 1.0}, {"b": 0.0}, resamples=10, seed=1)
    assert (
        result["difference"] is None and result["ci"] == [None, None] and result["n_problems"] == 0
    )
    assert outcome(result, result, 0.02) == "not_measured"


def test_outcome_improved_inconclusive_worse():
    def ci(d, lo, hi):
        return {"difference": d, "ci": [lo, hi]}

    assert outcome(ci(0.2, 0.05, 0.35), ci(0.0, -0.05, 0.05), 0.02) == "improved"
    assert outcome(ci(0.1, -0.05, 0.25), ci(0.0, -0.05, 0.05), 0.02) == "inconclusive"
    assert outcome(ci(-0.2, -0.35, -0.05), ci(0.0, -0.05, 0.05), 0.02) == "worse"
    # a solved gain bought with significantly more false acceptance is not an improvement
    assert outcome(ci(0.2, 0.05, 0.35), ci(0.1, 0.03, 0.17), 0.02) == "worse"
    assert outcome(ci(0.2, 0.05, 0.35), ci(0.03, -0.01, 0.07), 0.02) == "inconclusive"


def test_report_validates_status_null_zero_and_public_leakage(config, tmp_path):
    h, records, tasks = run_fixture(config, tmp_path)
    full = analyze(config, records, manifest_hash="a" * 64, dataset_id="fx", mode="fixture")
    assert (
        full["report"]["status"] == "completed" and errors(full["report"], "BenchmarkReport") == []
    )
    assert any("SYNTHETIC" in line for line in full["report"]["limitations"])
    blob = json.dumps(full["report"])
    for task in tasks:
        assert task.hidden["reference_source"] not in blob and str(tmp_path) not in blob
    row = full["report"]["rows"][0]
    assert row["mean_peak_memory_mb"] is None  # unmeasured stays null, never 0
    assert row["mean_input_tokens"] == 9000
    # a method that never accepted anything has null precision, while its zeros stay zeros
    none = [r for r in records if r["method"] == "CJ"]
    for r in none:
        r["category"] = "unresolved"
    zero = analyze(
        config,
        none + [r for r in records if r["method"] == "B3"],
        manifest_hash=None,
        dataset_id="fx",
        mode="fixture",
    )
    cj = next(r for r in zero["report"]["rows"] if r["method"] == "CJ")
    assert (
        cj["acceptance_precision"] is None and cj["solved"] == 0 and cj["incorrect_accepted"] == 0
    )
    # only some methods ran -> partial, not completed, and a gain cannot be claimed
    part = analyze(
        config,
        [r for r in records if r["method"] in ("CJ", "B3")],
        manifest_hash=None,
        dataset_id="fx",
        mode="fixture",
    )
    assert part["report"]["status"] == "partial"
    assert part["report"]["research_outcome"] != "improved"
    empty = analyze(config, [], manifest_hash=None, dataset_id=None, mode="fixture")
    assert empty["report"]["status"] == "not_run" and empty["report"]["rows"] == []
    assert (
        empty["report"]["dataset_id"] is None
        and empty["report"]["research_outcome"] == "not_measured"
    )


def test_missing_fair_baseline_means_comparison_incomplete(config, tmp_path):
    h, records, _ = run_fixture(config, tmp_path)
    no_b3 = [r for r in records if r["method"] != "B3"]
    result = analyze(config, no_b3, manifest_hash=None, dataset_id="fx", mode="fixture")
    assert result["report"]["research_outcome"] == "not_measured"
    assert "comparison incomplete" in result["report"]["paired_analysis_note"]


def test_worse_result_is_reported_as_worse(config, tmp_path):
    h, records, _ = run_fixture(config, tmp_path)
    for r in records:
        if r["method"] == "CJ" and r["regime"] == "token_matched":
            r["category"] = "incorrect_accepted"
        if r["method"] == "B3" and r["regime"] == "token_matched":
            r["category"] = "solved"
    result = analyze(config, records, manifest_hash=None, dataset_id="fx", mode="fixture")
    assert result["report"]["research_outcome"] == "worse"


def test_analysis_is_deterministic_byte_for_byte(config, tmp_path):
    h, records, _ = run_fixture(config, tmp_path)
    a = json.dumps(
        analyze(config, records, manifest_hash=None, dataset_id="fx", mode="fixture")["report"],
        sort_keys=True,
    )
    b = json.dumps(
        analyze(config, records, manifest_hash=None, dataset_id="fx", mode="fixture")["report"],
        sort_keys=True,
    )
    assert a == b


def test_cli_smoke_is_labelled_fixture_and_refuses_final(tmp_path, capsys):
    from codejury.stage2_tools.eval_cli import main

    assert main(["smoke", "--config", str(VALID), "--mode", "fixture", "--out", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "fixture" and "FIXTURE" in out["label"] and out["parity_ok"] is True
    report = json.loads((tmp_path / "smoke-report.json").read_text())
    assert report["runtime_mode"] == "fixture" and report["dataset_id"] == "fixture-smoke"
    assert (
        main(["smoke", "--config", str(FINAL), "--mode", "fixture", "--out", str(tmp_path / "x")])
        == 2
    )
    assert (
        main(["smoke", "--config", str(VALID), "--mode", "live", "--out", str(tmp_path / "y")]) == 2
    )
    assert main(["analyze", "--results", str(tmp_path), "--out", str(tmp_path / "again.json")]) == 0
    assert (tmp_path / "again.json").read_text() == (tmp_path / "smoke-report.json").read_text()
    assert (
        main(["run", "--config", str(FINAL), "--split", "validation", "--out", str(tmp_path / "z")])
        == 2
    )


def test_sha_helper_sanity():
    assert sha256_text("a") != sha256_text("b") and time.monotonic() >= 0 and threading.Event()
