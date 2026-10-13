import json

import httpx
import pytest

from codejury.stage2_core.teacher.budget import CAP, RESERVATION, Halt, Ledger
from codejury.stage2_core.teacher.client import Teacher
from codejury.stage2_core.teacher.redaction import clean, credentials

KEY = "gsk_test_sentinel_secret"
DRAFT = {
    "source": "def solve(x):\n    return x",
    "diagnosis": "Identity.",
    "assumptions": [],
    "requirement_ids": ["r-one"],
}
LINEAGE = {"split": "train", "role": "fixer_a"}


def completion(**changes):
    body = {
        "id": "test",
        "created": 1,
        "object": "chat.completion",
        "model": "openai/gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(DRAFT)},
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    body.update(changes)
    return body


def client(tmp_path, handler, keys=None):
    ledger = Ledger(tmp_path / "budget.sqlite")
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return Teacher(keys or [KEY], ledger, http_client=http)


def test_sdk_cache_resume(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        body = json.loads(request.content)
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["max_completion_tokens"] == 4096
        assert KEY not in request.content.decode()
        return httpx.Response(200, json=completion())

    teacher = client(tmp_path, handler)
    assert teacher.propose("facts", LINEAGE) == client(tmp_path, handler).propose("facts", LINEAGE)
    assert len(seen) == 1
    assert teacher.ledger.summary()["charged_or_reserved_usd"] == 0.000045
    assert KEY.encode() not in (tmp_path / "budget.sqlite").read_bytes()


def test_429_backoff_no_key_cycling(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "120"}, json={"error": KEY})

    teacher = client(tmp_path, handler, [KEY, "gsk_second_sentinel"])
    with pytest.raises(Halt, match="HTTP 429") as error:
        teacher.propose("facts", LINEAGE)
    assert KEY not in str(error.value)
    with pytest.raises(Halt, match="backoff"):
        teacher.propose("facts", LINEAGE)
    assert len(calls) == 1
    assert teacher.ledger.summary()["charged_or_reserved_usd"] == 0


def test_401_rotation(tmp_path):
    seen = []

    def handler(request):
        seen.append(1)
        return (
            httpx.Response(401, json={"error": KEY})
            if len(seen) == 1
            else httpx.Response(200, json=completion())
        )

    teacher = client(tmp_path, handler, [KEY, "gsk_second_sentinel"])
    teacher.propose("facts", LINEAGE)
    assert len(seen) == teacher.ledger.summary()["attempts"] == 2


@pytest.mark.parametrize("mode", ["timeout", "missing_usage", "server"])
def test_unknown_charge_stops_dispatch(tmp_path, mode):
    seen = []

    def handler(request):
        seen.append(1)
        if mode == "timeout":
            raise httpx.ReadTimeout("secret: " + KEY)
        if mode == "server":
            return httpx.Response(500, json={"error": KEY})
        return httpx.Response(200, json=completion(usage=None))

    teacher = client(tmp_path, handler)
    with pytest.raises(Halt) as error:
        teacher.propose("facts", LINEAGE)
    assert KEY not in str(error.value)
    with pytest.raises(Halt):
        teacher.propose("different facts", LINEAGE)
    assert len(seen) == 1
    assert teacher.ledger.summary()["unknown_usage_attempts"] == 1
    assert teacher.ledger.summary()["charged_or_reserved_usd"] == RESERVATION / CAP


@pytest.mark.parametrize("change", ["length", "json", "extra", "refusal", "secret"])
def test_bad_response_cost_recorded(tmp_path, change):
    body = completion()
    choice = body["choices"][0]
    if change == "length":
        choice["finish_reason"] = "length"
    elif change == "json":
        choice["message"]["content"] = "{"
    elif change == "extra":
        choice["message"]["content"] = json.dumps({**DRAFT, "extra": True})
    elif change == "refusal":
        choice["message"]["refusal"] = "No"
    else:
        choice["message"]["content"] = json.dumps({**DRAFT, "diagnosis": KEY})
    teacher = client(tmp_path, lambda _: httpx.Response(200, json=body))
    with pytest.raises(Halt, match="response rejected"):
        teacher.propose("facts", LINEAGE)
    assert teacher.ledger.summary()["charged_or_reserved_usd"] > 0
    assert teacher.ledger.summary()["unknown_usage_attempts"] == 0
    assert KEY.encode() not in (tmp_path / "budget.sqlite").read_bytes()


def test_cap_persists(tmp_path):
    ledger = Ledger(tmp_path / "budget.sqlite")
    attempt = ledger.reserve("1")
    ledger.settle(attempt, status="ok", charge=CAP - RESERVATION + 1)
    with pytest.raises(Halt):
        Ledger(ledger.path).reserve("2")
    assert ledger.summary()["attempts"] == 1


def test_secret_nontrain_rejected_before_http(tmp_path):
    def handler(_):
        pytest.fail("Must not dispatch")

    teacher = client(tmp_path, handler)
    for split in ["validation", "final_assessment", "stage2_final"]:
        with pytest.raises(ValueError):
            teacher.propose("facts", {**LINEAGE, "split": split})
    with pytest.raises(ValueError):
        teacher.propose(KEY, LINEAGE)
    with pytest.raises(ValueError):
        clean(KEY)
    assert teacher.ledger.summary()["attempts"] == 0


def test_env_whitelist(tmp_path, monkeypatch):
    for name in ["GROQ_API_KEY", "groq_api_1", "groq_api_2", "groq_api_3"]:
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / ".env"
    path.write_text("groq_api_1=" + KEY + "\nunrelated=not_loaded\ngroq_api_2=" + KEY)
    assert credentials(path) == [KEY]


def test_attempt_limit(tmp_path):
    ledger = Ledger(tmp_path / "budget.sqlite")
    for n in range(60):
        attempt = ledger.reserve(str(n), completion=False)
        ledger.settle(attempt, status="http_401", charge=0)
    with pytest.raises(Halt):
        ledger.reserve("next", completion=False)


def test_teacher_not_imported_by_runtime():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src/codejury/stage2_core"
    for path in root.rglob("*.py"):
        if "teacher" not in path.parts and "training" not in path.parts:
            assert "import groq" not in path.read_text()
            assert "from .teacher" not in path.read_text()
