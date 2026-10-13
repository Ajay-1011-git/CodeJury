"""Single-flight offline transport. SDK retries disabled; ledger is the retry authority."""

import json
import time
from email.utils import parsedate_to_datetime

import groq

from .budget import CONTEXT, INPUT_RATE, MAX_OUTPUT, OUTPUT_RATE, Halt
from .cache import identity
from .redaction import clean
from .schemas import RESPONSE_FORMAT, parse

MODEL = "openai/gpt-oss-120b"


def retry_time(headers):
    value = headers.get("retry-after", "60")
    try:
        return time.time() + max(1, float(value))
    except ValueError:
        try:
            return max(time.time() + 1, parsedate_to_datetime(value).timestamp())
        except (ValueError, TypeError):
            return time.time() + 60


class Teacher:
    def __init__(self, keys, ledger, *, http_client=None):
        self.keys, self.ledger = keys, ledger
        self.http_client = http_client

    def connection(self, key):
        return groq.Groq(
            api_key=key,
            base_url="https://api.groq.com",
            timeout=60,
            max_retries=0,
            http_client=self.http_client,
        )

    def request(self, body, lineage, *, preflight=False, max_attempts=3):
        clean(json.dumps(body), self.keys)
        clean(json.dumps(lineage), self.keys)
        request_id = identity(body, lineage)
        with self.ledger.exclusive():
            cached = self.ledger.cached(request_id)
            if cached is not None:
                return cached
            for key in self.keys[:max_attempts]:
                attempt = self.ledger.reserve(request_id, completion=not preflight)
                client = self.connection(key)
                try:
                    if preflight:
                        response = client.models.with_raw_response.list()
                    else:
                        response = client.chat.completions.with_raw_response.create(**body)
                    parsed = response.parse()
                except groq.APIStatusError as error:
                    status = error.status_code
                    # Never retain exception bodies/headers: they may echo prompt or credentials.
                    if status in {400, 401, 403, 404, 422, 429}:
                        self.ledger.settle(
                            attempt,
                            status=f"http_{status}",
                            charge=0,
                            retry_at=retry_time(error.response.headers) if status == 429 else 0,
                        )
                        if status == 401:
                            continue
                        raise Halt(f"Teacher HTTP {status}; no automatic replay") from None
                    raise Halt("Teacher server error: usage unknown; dispatch halted") from None
                except Exception:
                    raise Halt(
                        "Teacher transport/parse failure: usage unknown; dispatch halted"
                    ) from None
                finally:
                    if self.http_client is None:
                        client.close()
                if preflight:
                    available = any(model.id == MODEL for model in parsed.data)
                    result = {
                        "model": MODEL,
                        "available": available,
                        "context_reservation": CONTEXT,
                        "sdk_retries": 0,
                    }
                    self.ledger.settle(attempt, status="ok", charge=0, result=result)
                    if not available:
                        raise Halt("Configured teacher model unavailable")
                    return result
                usage = parsed.usage
                if usage is None or any(
                    type(n) is not int or n < 0
                    for n in (usage.prompt_tokens, usage.completion_tokens)
                ):
                    raise Halt("Teacher usage unknown; dispatch halted")
                charge = usage.prompt_tokens * INPUT_RATE + usage.completion_tokens * OUTPUT_RATE
                try:
                    choice = parsed.choices[0]
                    if choice.finish_reason != "stop" or getattr(choice.message, "refusal", None):
                        raise ValueError("Refusal or incomplete generation")
                    content = clean(choice.message.content, self.keys)
                    draft = parse(content)
                    result = {
                        "request_hash": request_id,
                        "request": body,
                        "draft": draft,
                        "usage": {
                            "prompt_tokens": usage.prompt_tokens,
                            "completion_tokens": usage.completion_tokens,
                        },
                        "model": parsed.model,
                        "finish_reason": choice.finish_reason,
                    }
                except Exception:
                    self.ledger.settle(attempt, status="invalid_response", charge=charge)
                    raise Halt("Teacher response rejected; cost recorded") from None
                self.ledger.settle(attempt, status="ok", charge=charge, result=result)
                return result
        raise Halt("No usable teacher credential")

    def preflight(self):
        return self.request({}, {"operation": "models-preflight", "model": MODEL}, preflight=True)

    def propose(self, prompt, lineage, variant=0, *, max_attempts=3):
        if lineage.get("split") != "train" or lineage.get("role") != "fixer_a":
            raise ValueError("Only authorized training A views may leave this process")
        # prompt is rebuilt from a hash-verified training row by collect.remote_prompt.
        body = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "Repair the Python function from runtime-visible facts. "
                    "Preserve its exact "
                    "signature and pure behavior. No imports, I/O, test-specific branches or "
                    "hardcoded lookup tables. Return the required JSON projection only. "
                    "Keep diagnosis concise, under 50 words. "
                    "Include every approved requirement ID. "
                    "Return assumptions as an empty array; do not add preconditions. "
                    "Use plain executable code without docstrings or string literals. "
                    "Reason from the contract, including edge cases, not just supplied examples.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": RESPONSE_FORMAT,
            "max_completion_tokens": MAX_OUTPUT,
            "reasoning_effort": "low",
            "reasoning_format": "hidden",
            "temperature": 0.2 if variant == 0 else 0.4,
            "seed": 17 + variant,
            "stream": False,
        }
        return self.request(body, lineage, max_attempts=max_attempts)
