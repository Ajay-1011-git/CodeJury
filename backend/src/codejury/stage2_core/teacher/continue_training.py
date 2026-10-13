"""Sequential dependent training through existing owned CLIs; no remote calls or final reader."""

import json
import os
import sqlite3
import subprocess
import sys

import yaml

from codejury.models.worker import file_hash

from ..data import write_report
from ..registry import local_path


def write_config(path, cfg):
    if path.exists():
        if yaml.safe_load(path.read_text()) != cfg:
            raise ValueError("Existing dependent job configuration changed")
    else:
        path.write_text(yaml.safe_dump(cfg, sort_keys=False))


def run(module, *args, env):
    command = [sys.executable, "-m", module, *map(str, args)]
    print(json.dumps({"phase": module, "operation": str(args[0]), "status": "started"}), flush=True)
    subprocess.run(command, env=env, check=True)


def learning_reports(root, reports):
    derived, exclusions = [], []
    database = root / "ledger.sqlite3"
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        for path in reports:
            report = json.loads(path.read_text())
            accepted = []
            for run_record in report["runs"]:
                run_id = run_record["run_id"]
                transport = db.execute(
                    "SELECT status,response FROM requests WHERE run_id=?", (run_id,)
                ).fetchall()
                bad = [
                    row
                    for row in transport
                    if row[0] != "settled" or not row[1] or json.loads(row[1])["status"] != "ok"
                ]
                if not transport or bad:
                    exclusions.append(
                        {
                            "run_id": run_id,
                            "source_report_hash": file_hash(path),
                            "reason": "incomplete/non-successful transport",
                            "response_statuses": [
                                json.loads(r[1])["status"] if r[1] else "missing" for r in bad
                            ],
                        }
                    )
                else:
                    accepted.append(run_record)
            target = path.with_name(path.stem + "-learning.json")
            value = {**report, "runs": accepted}
            if target.exists():
                if json.loads(target.read_text()) != value:
                    raise ValueError("Derived learning report changed")
            else:
                write_report(target, value)
            derived.append(target)
    audit_path = root / "learning-exclusions.json"
    if not audit_path.exists():
        write_report(
            audit_path,
            {
                "excluded": exclusions,
                "excluded_count": len(exclusions),
                "source_hashes": [file_hash(p) for p in reports],
                "derived_hashes": [file_hash(p) for p in derived],
                "raw_runs_preserved": True,
            },
        )
    return derived


def complete(cfg):
    root = local_path(cfg["artifact_root"])
    episode_root = root / "candidate-episodes-v1"
    reports = [episode_root / f"{split}.json" for split in ("train", "validation")]
    if not all(path.is_file() for path in reports):
        raise ValueError("Current candidate TRAIN/validation collection must finish first")
    isolation = json.loads(
        local_path("artifacts/stage2-integration/runner-v2/runner-self-test.json").read_text()
    )
    if isolation["overall"] != "passed" or not all(isolation["checks"].values()):
        raise ValueError("Actual isolation checks are required")
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"GROQ_API_KEY", "groq_api_1", "groq_api_2", "groq_api_3"}
    }
    env["CODEJURY_STAGE2_RUNNER_IMAGE"] = isolation["environment"]["image_id"]
    registry = root / "selected-a-v1/registry.json"
    critic_cfg = yaml.safe_load(local_path("config/stage2_tools/training/critic.yaml").read_text())
    critic_reports = learning_reports(episode_root, reports)
    critic_cfg.update(
        runtime_config=str(root / "candidate-runtime.yaml"),
        registry=str(registry),
        ledger=str(episode_root),
        reports=list(map(str, critic_reports)),
        corpus=str(root / "current-critic-corpus-v2"),
    )
    cpath = root / "current-critic-config-v2.yaml"
    write_config(cpath, critic_cfg)
    if not (root / "current-critic-corpus-v2/manifest.json").exists():
        run("codejury.stage2_tools.critic_cli", "collect", "--config", cpath, env=env)
    critic_eval = root / "current-critic-validation-v1/report.json"
    if not critic_eval.exists():
        run(
            "codejury.stage2_tools.critic_cli",
            "evaluate",
            "--config",
            cpath,
            "--registry",
            registry,
            "--out",
            critic_eval.parent,
            env=env,
        )
    measured = json.loads(critic_eval.read_text())
    if measured["correct_cases"] == 0:
        from .critic_controls import controls

        control_corpus = root / "critic-correct-controls-v1"
        if not (control_corpus / "manifest.json").exists():
            # This step uses only local ToolPort calls; the supplied image environment is scoped.
            previous_image = os.environ.get("CODEJURY_STAGE2_RUNNER_IMAGE")
            os.environ["CODEJURY_STAGE2_RUNNER_IMAGE"] = env["CODEJURY_STAGE2_RUNNER_IMAGE"]
            try:
                controls(
                    root / "current-critic-corpus-v2",
                    episode_root,
                    critic_cfg["tool_config"],
                    control_corpus,
                )
            finally:
                if previous_image is None:
                    os.environ.pop("CODEJURY_STAGE2_RUNNER_IMAGE", None)
                else:
                    os.environ["CODEJURY_STAGE2_RUNNER_IMAGE"] = previous_image
        control_cfg = {**critic_cfg, "corpus": str(control_corpus)}
        control_path = root / "critic-correct-controls-config.yaml"
        write_config(control_path, control_cfg)
        control_eval = root / "critic-correct-controls-validation-v1/report.json"
        if not control_eval.exists():
            run(
                "codejury.stage2_tools.critic_cli",
                "evaluate",
                "--config",
                control_path,
                "--registry",
                registry,
                "--out",
                control_eval.parent,
                env=env,
            )
        controlled = json.loads(control_eval.read_text())
        if controlled["adapter_hash"] != measured["adapter_hash"]:
            raise ValueError("Correct-control validation changed the Critic weights")
        measured = {
            **measured,
            **{
                k: measured[k] + controlled[k]
                for k in (
                    "records",
                    "correct_cases",
                    "format_domain_valid",
                    "false_hard_rejections",
                )
            },
            "correct_control_report_hash": file_hash(control_eval),
            "ordinary_report_hash": file_hash(critic_eval),
        }
    if (
        measured["records"] < 1
        or measured["correct_cases"] < 1
        or measured["format_domain_valid"] < 0.8 * measured["records"]
        or measured["false_hard_rejections"] != 0
    ):
        raise ValueError("Current Critic distribution validation failed; preserve original runtime")
    cproof = root / "critic-compatibility-v1.json"
    if not cproof.exists():
        write_report(
            cproof,
            {
                "status": "retained_current_critic_validated_on_new_a",
                "evaluation_hash": file_hash(critic_eval),
                "adapter_hash": measured["adapter_hash"],
                "evaluation": measured,
                "retrained": False,
                "final_contents_opened": False,
            },
        )
    judge_cfg = yaml.safe_load(local_path("config/stage2_core/training/judge.yaml").read_text())
    judge_cfg.update(
        runtime_config=str(root / "candidate-runtime.yaml"),
        registry=str(registry),
        ledger=str(episode_root),
        reports=list(map(str, reports)),
    )
    jpath = root / "current-judge-config.yaml"
    write_config(jpath, judge_cfg)
    rollouts = root / "current-continuations-v1"
    corpus = root / "current-judge-corpus-v1"
    if not (rollouts / "manifest.json").exists():
        run(
            "codejury.stage2_core.rollout_cli",
            "collect",
            "--config",
            jpath,
            "--out",
            rollouts,
            env=env,
        )
    if not (corpus / "manifest.json").exists():
        run(
            "codejury.stage2_core.rollout_cli",
            "label",
            "--config",
            jpath,
            "--rollouts",
            rollouts,
            "--out",
            corpus,
            env=env,
        )
    for phase in ("pilot", "full"):
        out = root / f"current-judge-{phase}-v1"
        if not (out / "report.json").exists():
            args = ["train", "--config", jpath, "--corpus", corpus, "--phase", phase, "--out", out]
            if phase == "full":
                args += ["--pilot-proof", root / "current-judge-pilot-v1/report.json"]
            run("codejury.stage2_core.rollout_cli", *args, env=env)
    jselected = root / "current-judge-selected-v1"
    if not (jselected / "selection.json").exists():
        run(
            "codejury.stage2_core.rollout_cli",
            "select",
            "--config",
            jpath,
            "--corpus",
            corpus,
            "--training-report",
            root / "current-judge-full-v1/report.json",
            "--out",
            jselected,
            env=env,
        )
    jselection = json.loads((jselected / "selection.json").read_text())
    general_cfg = yaml.safe_load(local_path("config/stage2_core/training/general.yaml").read_text())
    general_cfg.update(
        registry=str(jselected / "registry.json"),
        runtime_config=str(root / "candidate-runtime.yaml"),
        critic_corpus=critic_cfg["corpus"],
        judge_corpus=str(corpus),
        judge_selection=str(jselected / "selection.json"),
    )
    general_cfg["teacher_training"] = {
        "corpus": str(root / "corpus-v1"),
        "training_report": str(root / "student-full-v1/report.json"),
        "selected_step": 50,
        "records": 100,
    }
    # Every verified teacher opportunity is shared; total deployed completion exposure is audited.
    # Original A replay still covers every original TRAIN base; repeated rows are disclosed.
    general_cfg["component_records"]["fixer_a"] = 150
    general_cfg["component_records"]["judge"] = jselection["selected"]["step"]
    general_cfg["recipe"]["steps"] = sum(general_cfg["component_records"].values()) + 100
    gpath = root / "current-general-config.yaml"
    write_config(gpath, general_cfg)
    gcorpus = root / "current-general-corpus-v1"
    if not (gcorpus / "manifest.json").exists():
        run(
            "codejury.stage2_core.general_cli",
            "build",
            "--config",
            gpath,
            "--out",
            gcorpus,
            env=env,
        )
    for phase in ("pilot", "full"):
        out = root / f"current-general-{phase}-v1"
        if not (out / "report.json").exists():
            args = ["train", "--config", gpath, "--corpus", gcorpus, "--phase", phase, "--out", out]
            if phase == "full":
                args += ["--pilot-proof", root / "current-general-pilot-v1/report.json"]
            run("codejury.stage2_core.general_cli", *args, env=env)
    selected = root / "current-general-selected-v1"
    if not (selected / "selection.json").exists():
        run(
            "codejury.stage2_core.general_cli",
            "select",
            "--config",
            gpath,
            "--training-report",
            root / "current-general-full-v1/report.json",
            "--out",
            selected,
            env=env,
        )
    result = {
        "status": "completed_dependent_native_training_and_selection",
        "registry_path": str(selected / "registry.json"),
        "registry_file_hash": file_hash(selected / "registry.json"),
        "critic_compatibility_hash": file_hash(cproof),
        "judge_selection_hash": file_hash(jselected / "selection.json"),
        "general_selection_hash": file_hash(selected / "selection.json"),
        "general_opportunity_hash": file_hash(selected / "opportunity.json"),
        "final_contents_opened": False,
        "activated_in_live_runtime": False,
        "remaining": [
            "All-role live validation and API/browser acceptance",
            "Clean freeze and sealed final benchmark",
            "Portable release package",
        ],
    }
    path = root / "dependent-training-v1.json"
    if not path.exists():
        write_report(path, result)
    return result
