"""Reuse the audited native MLX trainer; never create a separate optimization engine."""

import json

import yaml

from ..data import write_report
from ..registry import local_path
from ..training.roles import train
from .export import export


def train_student(cfg, *, phase="pilot"):
    root = local_path(cfg["artifact_root"])
    corpus = root / "corpus-v1"
    if not corpus.exists():
        export(cfg, corpus)
    # Freeze initialization before pilot; the full candidate must use that exact registry.
    baseline = root / "baseline-registry.json"
    if not baseline.exists():
        runtime = yaml.safe_load(local_path("config/stage2_core/runtime.yaml").read_text())
        write_report(baseline, json.loads(local_path(runtime["model_manifest"]).read_text()))
    return train(
        "fixer_a",
        corpus,
        baseline,
        local_path("config/stage2_core/runtime.yaml"),
        cfg["student"],
        root / ("student-" + phase + "-v1"),
        phase=phase,
        pilot=root / "student-pilot-v1/report.json" if phase == "full" else None,
    )
