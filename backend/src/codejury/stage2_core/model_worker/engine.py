"""Validated generation engine. Role JSON parsing stays in the controller."""

import time

from ..budgets import zero_usage
from ..contracts import checked
from ..registry import RegistryError

PURPOSES = {
    "raw": {"repair", "baseline"},
    "fixer_a": {"repair", "revise"},
    "fixer_b": {"reconstruct", "revise"},
    "critic": {"test_proposal"},
    "judge": {"action_choice"},
    "general": {"baseline"},
}


class Refused(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def response(registry, request, *, status="ok", text=None, usage=None, code=None, message=None):
    return checked(
        {
            "schema_version": "stage2.v1",
            "request_id": request["request_id"],
            "role": request["role"],
            **registry.identity(request["role"]),
            "status": status,
            "text": text,
            "usage": usage if usage is not None else zero_usage(),
            "error": None
            if code is None
            else {"code": code, "message": message, "field_errors": []},
        },
        "ModelResponse",
    )


def preflight(request, registry) -> None:
    role = request["role"]
    cap = 192 if role == "judge" else 512 if role == "critic" else 1024
    if request["purpose"] not in PURPOSES[role] or request["max_new_tokens"] > cap:
        raise Refused("error", "role_budget", "Model role/purpose or output cap mismatch")
    if role != "raw" and role not in registry.record["adapters"]:
        raise Refused("error", "adapter_unavailable", "Trained adapter unavailable for " + role)
    remaining = request["remaining_budget"]
    if request["max_new_tokens"] > remaining["output_tokens"] or remaining["elapsed_ms"] == 0:
        raise Refused(
            "budget_exhausted", "episode_budget", "Remaining episode budget is insufficient"
        )
    counter = "judge_decisions" if role == "judge" else "learned_candidates"
    if role in {"fixer_a", "fixer_b", "judge"} and remaining[counter] < 1:
        raise Refused("budget_exhausted", "attempt_budget", "No role attempts remain")
    if len(request["prompt"].encode()) > 256000:
        raise Refused("error", "prompt_size", "Prompt exceeds the local IPC byte cap")


class ModelEngine:
    def __init__(self, registry, backend):
        self.registry, self.backend = registry, backend

    def generate(self, request, cancel, *, deadline, on_usage=lambda usage: None):
        request = checked(request, "ModelRequest")
        usage = zero_usage()
        started = time.monotonic()
        text = ""
        status, code, message = "ok", None, None
        iterator = None

        def ensure_running():
            if cancel.is_set():
                raise Refused("cancelled", "cancelled", "Model generation cancelled")
            if time.monotonic() >= deadline:
                raise Refused("budget_exhausted", "wall_deadline", "Episode wall deadline reached")

        def publish():
            usage["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            on_usage(dict(usage))

        def progress(processed, total):
            usage["input_tokens"] = processed
            usage["peak_memory_mb"] = self.backend.peak_memory_mb()
            publish()
            ensure_running()

        try:
            ensure_running()
            preflight(request, self.registry)
            self.backend.switch(request["role"])
            ensure_running()
            tokens = self.backend.tokenize(request["prompt"])
            if len(tokens) + request["max_new_tokens"] > 4096:
                raise Refused(
                    "budget_exhausted",
                    "context_limit",
                    "Prompt plus reserved completion "
                    "exceeds 4096 tokens; required content was not trimmed",
                )
            if len(tokens) > request["remaining_budget"]["input_tokens"]:
                raise Refused(
                    "budget_exhausted", "input_budget", "Prompt exceeds remaining input budget"
                )
            ensure_running()
            iterator = self.backend.stream(
                tokens, request["max_new_tokens"], request["seed"], progress
            )
            for step in iterator:
                usage.update(
                    input_tokens=step.prompt_tokens,
                    output_tokens=step.generation_tokens,
                    peak_memory_mb=self.backend.peak_memory_mb(),
                )
                text += step.text
                publish()
                ensure_running()
                if usage["output_tokens"] > request["max_new_tokens"] or len(text.encode()) > 96000:
                    raise Refused(
                        "error", "generation_overflow", "Runtime exceeded generation ceiling"
                    )
        except Refused as exc:
            status, code, message = exc.status, exc.code, exc.message
        except RegistryError:
            status, code, message = (
                "error",
                "registry_mismatch",
                "Frozen model/adapter identity changed",
            )
        except Exception as exc:
            status, code, message = (
                "error",
                "worker_exception",
                type(exc).__name__ + " in native worker",
            )
        finally:
            if iterator is not None:
                iterator.close()
            usage["elapsed_ms"] = int((time.monotonic() - started) * 1000)
        return response(
            self.registry,
            request,
            status=status,
            text=text or None,
            usage=usage,
            code=code,
            message=message,
        )
