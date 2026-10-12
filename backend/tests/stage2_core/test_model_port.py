"""CPU protocol tests use explicit test doubles; they do not establish native inference."""

import copy
import json
import multiprocessing
import subprocess
import sys
import time
from threading import Event
from types import SimpleNamespace

import pytest
from jsonschema import ValidationError

from codejury.stage2_core.budgets import CAPS, zero_usage
from codejury.stage2_core.contracts import checked
from codejury.stage2_core.factory import make_model_port
from codejury.stage2_core.model_cli import request_for
from codejury.stage2_core.model_worker import NativeModelPort
from codejury.stage2_core.model_worker.engine import ModelEngine, response
from codejury.stage2_core.model_worker.native import verify_tensors
from codejury.stage2_core.registry import (
    Registry,
    RegistryError,
    register_stage1,
    role_config,
)


@pytest.fixture
def registry(tmp_path):
    base = tmp_path / "base"
    adapter = tmp_path / "adapter"
    base.mkdir()
    adapter.mkdir()
    files = {
        "config.json": {
            "model_type": "phi3",
            "num_hidden_layers": 32,
            "quantization": {"bits": 4, "group_size": 64, "mode": "affine"},
        },
        "tokenizer.json": {},
        "tokenizer_config.json": {},
        "model.safetensors.index.json": {},
    }
    for name, content in files.items():
        (base / name).write_text(json.dumps(content))
    (base / "model.safetensors").write_bytes(b"unit test metadata only; not model weights")
    (base / "chat_template.jinja").write_text("unit test tokenizer identity")
    layout = {
        "fine_tune_type": "lora",
        "num_layers": 4,
        "lora_parameters": {
            "rank": 8,
            "scale": 16.0,
            "dropout": 0.0,
            "keys": ["self_attn.qkv_proj", "self_attn.o_proj"],
        },
    }
    (adapter / "adapter_config.json").write_text(json.dumps(layout))
    (adapter / "adapters.safetensors").write_bytes(b"unit test metadata only; not adapter weights")
    from codejury.models.worker import file_hash

    weight_hash = file_hash(adapter / "adapters.safetensors")
    freeze = {
        "model_id": "test-phi",
        "model_revision": "test-revision",
        "adapter_sha256": weight_hash,
        "training_steps": 3,
        "data_manifest_sha256": "a" * 64,
    }
    (adapter / "freeze.json").write_text(json.dumps(freeze))
    report = {
        "runtime_mode": "live",
        "adapter_sha256": weight_hash,
        "train_base_problems": 2,
        "train_records": 4,
        "loss_points": [],
    }
    report_path = tmp_path / "synthetic-metadata.json"
    report_path.write_text(json.dumps(report))
    return register_stage1(base, adapter, report_path, tmp_path / "registry.json")


class TestBackend:
    __test__ = False

    def __init__(self, *, tokens=20, fail_at=None, cancel_after=None):
        self.tokens = tokens
        self.fail_at = fail_at
        self.cancel_after = cancel_after
        self.closed_stream = False
        self.switched = []
        self.streamed = False

    def switch(self, role):
        self.switched.append(role)

    def tokenize(self, prompt):
        self.prompt = prompt
        return list(range(self.tokens))

    def stream(self, tokens, cap, seed, progress):
        self.streamed = True
        try:
            progress(len(tokens), len(tokens))
            for i in range(1, 4):
                if i == self.fail_at:
                    raise RuntimeError("synthetic runtime failure")
                yield SimpleNamespace(prompt_tokens=len(tokens), generation_tokens=i, text=str(i))
                if self.cancel_after and i == self.cancel_after[0]:
                    self.cancel_after[1].set()
        finally:
            self.closed_stream = True

    def peak_memory_mb(self):
        return 10.0


def run_engine(registry, request, backend=None, cancel=None):
    backend = backend if backend is not None else TestBackend()
    return ModelEngine(registry, backend).generate(
        request, cancel or Event(), deadline=time.monotonic() + 60
    )


def test_registered_adapter_identity_and_missing_roles(registry):
    ready = registry.readiness()
    assert not ready["ready"]
    assert ready["available_roles"] == ["raw", "fixer_a"]
    assert ready["missing_roles"] == ["critic", "fixer_b", "judge"]
    assert registry.identity("raw")["adapter_hash"] is None
    assert registry.identity("fixer_a")["adapter_hash"] is not None
    for role in ("fixer_b", "critic", "judge", "general"):
        backend = TestBackend()
        result = run_engine(registry, request_for(role, "unavailable-" + role), backend)
        assert result["error"]["code"] == "adapter_unavailable"
        assert result["text"] is None
        assert not backend.switched
        assert result["usage"] == {**zero_usage(), "elapsed_ms": result["usage"]["elapsed_ms"]}


@pytest.mark.parametrize(
    "change",
    [
        "base_bytes",
        "adapter_bytes",
        "card_tokenizer",
        "topology",
        "unknown_role",
        "fixture_mode",
        "duplicate_adapter",
    ],
)
def test_registry_rejects_incompatible_or_false_provenance(registry, change):
    record = copy.deepcopy(registry.record)
    if change == "base_bytes":
        (registry.model_dir / "tokenizer.json").write_text("changed")
    elif change == "adapter_bytes":
        (registry.verify_adapter("fixer_a") / "adapters.safetensors").write_bytes(b"changed")
    elif change == "card_tokenizer":
        record["adapters"]["fixer_a"]["card"]["tokenizer_hash"] = "0" * 64
    elif change == "topology":
        record["topology"]["num_layers"] = 2
    elif change == "unknown_role":
        record["adapters"]["oracle"] = record["adapters"]["fixer_a"]
    elif change == "fixture_mode":
        record["runtime_mode"] = "fixture"
    else:
        entry = copy.deepcopy(record["adapters"]["fixer_a"])
        entry["card"].update(
            role="fixer_b",
            config_hash=role_config(
                record["base"], record["topology_hash"], "fixer_b", entry["card"]["adapter_hash"]
            ),
        )
        record["adapters"]["fixer_b"] = entry
    registry.path.write_text(json.dumps(record))
    with pytest.raises((RegistryError, ValidationError)):
        Registry(registry.path)


def test_registry_checks_files_again_before_switch(registry):
    (registry.model_dir / "config.json").write_text("{}")
    with pytest.raises(RegistryError, match="changed"):
        registry.verify_current("raw")


def test_unknown_request_fields_and_bool_seed_rejected(registry):
    for field, value in (("hidden_reference", "sentinel"), ("seed", True)):
        request = {**request_for("fixer_a", "bad-field"), field: value}
        with pytest.raises(ValidationError):
            run_engine(registry, request)


@pytest.mark.parametrize("tokens,reserve,allowed", [(3904, 192, True), (3905, 192, False)])
def test_total_context_includes_reserved_completion_without_trimming(
    registry, tokens, reserve, allowed
):
    backend = TestBackend(tokens=tokens)
    request = request_for("fixer_a", "context")
    request["max_new_tokens"] = reserve
    request["prompt"] = "required-contract-source-and-tests-sentinel"
    result = run_engine(registry, request, backend)
    assert backend.prompt == request["prompt"]
    assert backend.streamed is allowed
    assert result["status"] == ("ok" if allowed else "budget_exhausted")
    if not allowed:
        assert result["error"]["code"] == "context_limit"
        assert result["usage"]["input_tokens"] == 0


@pytest.mark.parametrize(
    "change,code",
    [
        ("purpose", "role_budget"),
        ("output", "episode_budget"),
        ("input", "input_budget"),
        ("attempt", "attempt_budget"),
    ],
)
def test_role_and_remaining_budgets(registry, change, code):
    request = request_for("fixer_a", change)
    if change == "purpose":
        request["purpose"] = "action_choice"
    else:
        request["remaining_budget"][
            {"output": "output_tokens", "input": "input_tokens", "attempt": "learned_candidates"}[
                change
            ]
        ] = 0
    result = run_engine(registry, request)
    assert result["status"] != "ok" and result["error"]["code"] == code


def test_actual_reported_tokens_and_iterator_cleanup_for_cpu_double(registry):
    backend = TestBackend()
    result = run_engine(registry, request_for("fixer_a", "three-tokens"), backend)
    assert result["status"] == "ok" and result["text"] == "123"
    assert result["usage"]["input_tokens"] == 20
    assert result["usage"]["output_tokens"] == 3
    assert result["usage"]["peak_memory_mb"] == 10.0
    assert result["usage"]["function_executions"] == 0
    assert backend.closed_stream
    checked(result, "ModelResponse")


def test_cancel_before_and_during_generation_preserves_partial_usage(registry):
    cancel = Event()
    cancel.set()
    backend = TestBackend()
    result = run_engine(registry, request_for("raw", "before"), backend, cancel)
    assert result["status"] == "cancelled" and not backend.switched
    cancel.clear()
    backend = TestBackend(cancel_after=(1, cancel))
    result = run_engine(registry, request_for("raw", "during"), backend, cancel)
    assert result["status"] == "cancelled"
    assert result["usage"]["output_tokens"] == 2
    assert result["usage"]["input_tokens"] == 20
    assert backend.closed_stream


def test_worker_exception_and_deadline_preserve_truthful_partial_counts(registry):
    backend = TestBackend(fail_at=2)
    result = run_engine(registry, request_for("fixer_a", "failure"), backend)
    assert result["status"] == "error" and result["usage"]["output_tokens"] == 1
    assert result["text"] == "1" and backend.closed_stream
    backend = TestBackend()
    result = ModelEngine(registry, backend).generate(
        request_for("raw", "deadline"), Event(), deadline=time.monotonic() - 1
    )
    assert result["error"]["code"] == "wall_deadline" and not backend.switched


def test_exact_tensor_set_shape_and_dtype_required():
    tensor = SimpleNamespace(shape=(8, 12), dtype="float32")
    verify_tensors({"lora_a": tensor}, {"lora_a": tensor})
    for weights in (
        {},
        {"lora_a": tensor, "base.weight": tensor},
        {"lora_a": SimpleNamespace(shape=(12, 8), dtype="float32")},
        {"lora_a": SimpleNamespace(shape=(8, 12), dtype="float16")},
    ):
        with pytest.raises(ValueError):
            verify_tensors(weights, {"lora_a": tensor})


def test_factory_is_lazy_and_rejects_mock_configuration(registry, tmp_path, monkeypatch):
    import yaml

    config = {
        "profile": "mac-standard-v1",
        "model_manifest": str(registry.path),
        "startup_timeout_s": 10,
        "shutdown_grace_s": 0.2,
        "poll_interval_s": 0.01,
    }
    path = tmp_path / "runtime.yaml"
    path.write_text(yaml.safe_dump(config))
    monkeypatch.delenv("CODEJURY_STAGE2_MODEL_MANIFEST", raising=False)
    monkeypatch.delenv("CODEJURY_MODEL_DIR", raising=False)
    with make_model_port(path) as port:
        assert port.process is None
        assert port.readiness()["worker_state"] == "lazy"
        result = port.generate(request_for("critic", "missing"), Event())
        assert result["error"]["code"] == "adapter_unavailable"
        assert port.process is None
    assert port.readiness()["worker_state"] == "closed" and not port.readiness()["ready"]
    config["fixture"] = True
    path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError):
        make_model_port(path)
    command = (
        "import sys; import codejury.stage2_core.factory; "
        "print(any(n.startswith('mlx') for n in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", command], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False"


def _cpu_transport(connection, cancel, stop, manifest):
    registry = Registry(manifest)
    try:
        while not stop.is_set():
            if not connection.poll(0.05):
                continue
            envelope = json.loads(connection.recv_bytes())
            request = envelope["request"]
            usage = {**zero_usage(), "input_tokens": 2, "output_tokens": 1}
            connection.send_bytes(
                json.dumps(
                    {"kind": "usage", "request_id": request["request_id"], "usage": usage}
                ).encode()
            )
            if request["prompt"] == "simulate-crash":
                return
            if request["prompt"] == "simulate-unresponsive":
                Event().wait(5)
                return
            if request["prompt"] == "wait-for-cancel":
                cancel.wait(2)
            result = response(
                registry,
                request,
                status="cancelled" if cancel.is_set() else "ok",
                text="synthetic CPU transport",
                usage=usage,
                code="cancelled" if cancel.is_set() else None,
                message="cancelled" if cancel.is_set() else None,
            )
            connection.send_bytes(json.dumps({"kind": "response", "response": result}).encode())
    finally:
        connection.close()


@pytest.fixture
def cpu_port(registry, monkeypatch):
    settings = {"startup_timeout_s": 10, "shutdown_grace_s": 0.1, "poll_interval_s": 0.01}
    port = NativeModelPort(registry, settings)

    def start(cancel, deadline):
        if port.process is not None:
            return
        context = multiprocessing.get_context("spawn")
        port.connection, child = context.Pipe()
        port.cancel_event, port.stop_event = context.Event(), context.Event()
        port.process = context.Process(
            target=_cpu_transport, args=(child, port.cancel_event, port.stop_event, registry.path)
        )
        port.process.start()
        child.close()

    monkeypatch.setattr(port, "_start", start)
    yield port
    port.close()


def test_serial_json_ipc_reuses_process_and_rejects_duplicate_ids(cpu_port):
    result = cpu_port.generate(request_for("raw", "first"), Event())
    assert result["status"] == "ok"
    pid = cpu_port.process.pid
    result = cpu_port.generate(request_for("fixer_a", "second"), Event())
    assert result["status"] == "ok" and cpu_port.process.pid == pid
    result = cpu_port.generate(request_for("raw", "first"), Event())
    assert result["error"]["code"] == "duplicate_request"


@pytest.mark.parametrize("prompt", ["simulate-crash", "simulate-unresponsive"])
def test_process_failure_and_forced_stop_keep_last_cost_lower_bound(cpu_port, prompt):
    request = request_for("raw", "crash")
    request["prompt"] = prompt
    if prompt == "simulate-unresponsive":
        request["remaining_budget"] = {**CAPS, "elapsed_ms": 600}
    result = cpu_port.generate(request, Event())
    assert result["status"] != "ok"
    assert "partial_cost" in result["error"]["code"]
    assert result["usage"]["input_tokens"] == 2
    assert not cpu_port.process.is_alive()


def test_cooperative_cancel_via_ipc(cpu_port):
    from concurrent.futures import ThreadPoolExecutor

    cancel = Event()
    request = request_for("raw", "cancel-ipc")
    request["prompt"] = "wait-for-cancel"
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(cpu_port.generate, request, cancel)
        # Synchronize on actual child launch, rather than assumed startup timing.
        limit = time.monotonic() + 5
        while cpu_port.process is None and time.monotonic() < limit:
            cancel.wait(0.01)
        assert cpu_port.process is not None
        cancel.set()
        result = future.result(timeout=5)
    assert result["status"] == "cancelled"
