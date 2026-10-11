"""Trusted image entrypoint. Never run submitted source through this module on the host."""

import ast
import builtins
import contextlib
import copy
import json
import signal
import sys
import time

LIMIT = 4096
SAFE_NAMES = (
    "abs all any bool dict enumerate int len list max min range reversed round set sorted "
    "str sum zip print Exception ValueError TypeError IndexError KeyError AssertionError "
    "ZeroDivisionError"
).split()


class Capture:
    def __init__(self):
        self.text = ""
        self.truncated = False

    def write(self, text):
        available = LIMIT - len(self.text)
        self.text += text[:available]
        self.truncated |= len(text) > available
        return len(text)

    def flush(self):
        pass


def same(a, b, depth=0):
    if depth > 8:
        return False
    if type(a) is not type(b):
        return False
    if type(a) is list:
        return len(a) == len(b) and all(same(x, y, depth + 1) for x, y in zip(a, b))
    if type(a) is dict:
        return a.keys() == b.keys() and all(same(a[k], b[k], depth + 1) for k in a)
    return a == b


def bounded(value, depth=0, remaining=None):
    remaining = [4096] if remaining is None else remaining
    remaining[0] -= 1
    if depth > 8 or remaining[0] < 0:
        raise ValueError("Output limit exceeded")
    if value is None or type(value) is bool:
        return
    if type(value) is int and abs(value) <= 2**53 - 1:
        return
    if type(value) is str and len(value) <= 8000:
        return
    if type(value) is list:
        for item in value:
            bounded(item, depth + 1, remaining)
        return
    if type(value) is dict and all(type(k) is str and len(k) <= 8000 for k in value):
        for item in value.values():
            bounded(item, depth + 1, remaining)
        return
    raise ValueError("Unsupported output type or unsafe integer")


def main():
    job = json.loads(sys.stdin.buffer.read(65537))
    source, args, name = job["source"], job["args"], job["function_name"]
    tree = ast.parse(source)
    denied = {
        "eval",
        "exec",
        "compile",
        "open",
        "globals",
        "locals",
        "vars",
        "getattr",
        "setattr",
        "delattr",
        "dir",
        "type",
        "object",
        "input",
        "help",
        "breakpoint",
    }
    if len(tree.body) != 1 or type(tree.body[0]) is not ast.FunctionDef:
        raise ValueError("Only one function permitted")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal)):
            raise ValueError("Unsupported structure")
        if isinstance(node, ast.Name) and (node.id.startswith("__") or node.id in denied):
            raise ValueError("Introspection is unsupported")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Introspection is unsupported")
    before = copy.deepcopy(args)
    capture = Capture()
    start = time.monotonic()
    result = {
        "actual_output": None,
        "exception_type": None,
        "input_mutated": False,
        "duration_ms": 0,
        "trace": [],
        "trace_truncated": False,
    }
    namespace = {"__builtins__": {key: getattr(builtins, key) for key in SAFE_NAMES}}

    def timeout(_signal, _frame):
        raise TimeoutError("Function exceeded 2 seconds")

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, 2)
    try:
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            exec(compile(tree, "<candidate>", "exec"), namespace)
            output = namespace[name](*args)
            bounded(output)
            result["actual_output"] = output
    except BaseException as exc:
        result["exception_type"] = type(exc).__name__
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    result.update(
        input_mutated=not same(args, before),
        duration_ms=int((time.monotonic() - start) * 1000),
        trace=capture.text.splitlines(),
        trace_truncated=capture.truncated,
    )
    encoded = json.dumps(result, allow_nan=False)
    if len(encoded.encode()) > 65536:
        result.update(actual_output=None, exception_type="OutputLimitExceeded")
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()
