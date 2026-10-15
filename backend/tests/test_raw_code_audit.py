"""Code-only auditing must never edit code or choose between multiple proposals."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "raw_audit", Path(__file__).parents[1] / "tools/dev_bench_raw_audit.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize("fence", [None, "json", ""])
def test_extract_preserves_source_bytes_and_ignores_metadata_schema(fence):
    source = "def solve(x):\n    return x + 1\n\n"
    reply = json.dumps({"source": source, "suspected_sites": ["non-schema prose"]})
    if fence is not None:
        reply = f"```{fence}\n{reply}\n```"
    assert audit.extract_source(reply) == source


@pytest.mark.parametrize("reply", [
    'Here is the answer: {"source":"def solve(x): return x"}',
    '{"source":"first", "source":"second"}',
    '[{"source":"first"},{"source":"second"}]',
    '```python\ndef solve(x): return x\n```',
    '{"source":null}',
])
def test_ambiguous_or_non_json_source_is_not_salvaged(reply):
    with pytest.raises(ValueError):
        audit.extract_source(reply)
