"""Trusted entrypoint that runs INSIDE the runner image only. Never run candidates on the host.

Reads one job from stdin, executes each call against freshly instantiated function state and
prints one JSON result envelope. Standard library only; the canonical JSON/hash rules here are
kept identical to codejury.stage2_tools.codec (a unit test compares them).
"""

import builtins
import copy
import hashlib
import json
import signal
import sys
import time
import types

WORKER_VERSION = "stage2-runner-1"
MAX_INPUT = 262144
MAX_OUTPUT_BYTES = 65536
MAX_SAFE = 2**53 - 1
SAFE_BUILTINS = (
    "len range sum min max abs sorted reversed enumerate zip all any int bool str list dict set "
    "tuple Exception ValueError TypeError IndexError KeyError ZeroDivisionError AssertionError"
).split()
TRACE_EVENTS = 32
TRACE_BYTES = 4096


class CallTimeout(BaseException):  # not an Exception: candidate `except Exception` cannot hide it
    pass


class OutputCodecError(Exception):
    pass


class Sink:
    def write(self, text):
        return len(text)

    def flush(self):
        pass


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def check_json(value, depth=0, budget=None):
    budget = [4096] if budget is None else budget
    budget[0] -= 1
    if depth > 8 or budget[0] < 0:
        raise ValueError("JSON nesting or node limit exceeded")
    kind = type(value)
    if value is None or kind is bool:
        return
    if kind is int:
        if abs(value) > MAX_SAFE:
            raise ValueError("unsafe integer")
        return
    if kind is str:
        if len(value) > 8000:
            raise ValueError("string too long")
        return
    if kind is list:
        for item in value:
            check_json(item, depth + 1, budget)
        return
    if kind is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("non-string key")
            check_json(item, depth + 1, budget)
        return
    raise ValueError("unsupported output type " + kind.__name__)


def sanitize(value):
    try:
        check_json(value)
        text = canonical(value)
        return value if len(text) <= 200 else text[:200]
    except (ValueError, TypeError):
        return "<" + type(value).__name__ + ">"


def make_import(allowed):
    modules = {}
    for dotted in allowed:
        module, _, attr = dotted.partition(".")
        modules.setdefault(module, []).append(attr)

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level or name not in modules:
            raise ImportError("import not permitted")
        real = __import__(name)
        return types.SimpleNamespace(**{a: getattr(real, a) for a in modules[name]})

    return guarded_import


def traceback_line(tb):
    line = None
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == "<candidate>":
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def run_call(code, name, allowed, call, timeout):
    inputs = call["inputs"]
    before = digest(inputs)
    args = copy.deepcopy(inputs)
    result = {
        "status": "ok",
        "output": None,
        "exception": None,
        "before_hash": before,
        "after_hash": before,
        "mutated": False,
        "duration_ms": 0,
        "trace": None,
        "trace_truncated": False,
    }
    events, state = [], {"bytes": 0, "truncated": False}
    lines = call.get("trace_lines")

    def local_trace(frame, event, arg):
        if event == "line" and frame.f_lineno in wanted:
            if len(events) >= TRACE_EVENTS or state["bytes"] > TRACE_BYTES:
                state["truncated"] = True
                return local_trace
            row = {
                "line": frame.f_lineno,
                "locals": {k: sanitize(v) for k, v in list(frame.f_locals.items())[:12]},
            }
            state["bytes"] += len(canonical(row))
            events.append(row)
        return local_trace

    def global_trace(frame, event, arg):
        return local_trace if frame.f_code.co_filename == "<candidate>" else None

    wanted = set(lines or [])

    live = [False]

    def on_alarm(_signum, _frame):
        if live[0]:
            raise CallTimeout()

    namespace = {"__builtins__": {k: getattr(builtins, k) for k in SAFE_BUILTINS}}
    namespace["__builtins__"]["__import__"] = make_import(allowed)
    signal.signal(signal.SIGALRM, on_alarm)
    start = time.monotonic()
    real_stdout, real_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = Sink()
    signal.setitimer(signal.ITIMER_REAL, timeout, 0.05)
    try:
        if lines:
            sys.settrace(global_trace)
        live[0] = True
        exec(code, namespace)
        output = namespace[name](*args)
        live[0] = False
        sys.settrace(None)
        try:
            check_json(output)
            if len(canonical(output)) > MAX_OUTPUT_BYTES:
                raise ValueError("output too large")
        except (ValueError, TypeError) as bad:
            raise OutputCodecError(str(bad)) from None
        result["output"] = output
    except CallTimeout:
        live[0] = False
        result["status"] = "timeout"
    except BaseException as exc:  # noqa: BLE001 - every candidate failure is evidence
        live[0] = False
        sys.settrace(None)
        invalid = isinstance(exc, OutputCodecError)
        result["status"] = "output_invalid" if invalid else "exception"
        result["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc)[:200],
            "lineno": traceback_line(exc.__traceback__),
        }
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        sys.settrace(None)
        sys.stdout, sys.stderr = real_stdout, real_stderr
    result["duration_ms"] = int((time.monotonic() - start) * 1000)
    try:
        after = digest(args)
    except (ValueError, TypeError):
        after = "0" * 64
    result["after_hash"] = after
    result["mutated"] = after != before
    if lines:
        result["trace"] = events
        result["trace_truncated"] = state["truncated"]
    return result


def run_job(job):
    source, name = job["source"], job["function_name"]
    calls = job["calls"]
    timeout = float(job.get("call_timeout_s", 2))
    allowed = job.get("allowed_imports", [])
    unsupported = None
    try:
        code = compile(source, "<candidate>", "exec")
    except (SyntaxError, ValueError, RecursionError) as exc:
        unsupported = type(exc).__name__
    if unsupported:
        row = {
            "status": "unsupported",
            "output": None,
            "mutated": False,
            "duration_ms": 0,
            "exception": {
                "type": unsupported,
                "message": "source does not compile",
                "lineno": None,
            },
            "trace": None,
            "trace_truncated": False,
        }
        return {
            "worker_version": WORKER_VERSION,
            "results": [
                {**row, "before_hash": digest(c["inputs"]), "after_hash": digest(c["inputs"])}
                for c in calls
            ],
        }
    return {
        "worker_version": WORKER_VERSION,
        "results": [run_call(code, name, allowed, c, timeout) for c in calls],
    }


def main():
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        sys.stdout.write(json.dumps({"worker_version": WORKER_VERSION, "error": "job too large"}))
        return 2
    sys.stdout.write(json.dumps(run_job(json.loads(raw)), allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
