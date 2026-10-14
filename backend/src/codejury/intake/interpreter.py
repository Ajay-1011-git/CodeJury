"""Spec-only Groq interpretation, sharing the existing teacher spend/attempt ledger."""

import json
import time

import yaml
from jsonschema import validate

from codejury.stage2_core.contracts import json_hash
from codejury.stage2_core.registry import local_path
from codejury.stage2_core.teacher.budget import CAP, INPUT_RATE, OUTPUT_RATE, Halt, Ledger
from codejury.stage2_core.teacher.redaction import clean, credentials
from codejury.stage2_tools.codec import typed_equal
from codejury.stage2_tools.domains import check_args, validate_domain
from codejury.stage2_tools.oracles.registry import TEMPLATES, expected_output, template_compatible

from .guard import validate_text
from .infer import KINDS, domain_for


def obj(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


SCHEMA = obj(
    {
        "arg_domains": {
            "type": "array",
            "items": obj(
                {
                    "param": {"type": "string"},
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "min": {"type": "integer"},
                    "max": {"type": "integer"},
                    "min_length": {"type": "integer"},
                    "max_length": {"type": "integer"},
                }
            ),
        },
        "requirements": {
            "type": "array",
            "items": obj(
                {
                    "text": {"type": "string"},
                    "property_template_id": {
                        "anyOf": [{"type": "null"}, {"type": "string", "enum": sorted(TEMPLATES)}]
                    },
                }
            ),
        },
        "examples": {
            "type": "array",
            "items": obj({"inputs_json": {"type": "string"}, "expected_json": {"type": "string"}}),
        },
        "ambiguities": {"type": "array", "items": {"type": "string"}},
    }
)
SYSTEM = (
    "Interpret the user description into requirements and example input/expected pairs. "
    "You are a specification interpreter, never a fixer. No source body is supplied. "
    "Do not infer or describe a bug, propose a patch, output code, Markdown, assignments "
    "or Python expressions. Use plain language. Domain suggestions are bounded envelopes. "
    "Use at most eight examples and six requirements. Report genuine ambiguities. "
    "Encode inputs as a JSON positional-argument array and expected as one JSON value. "
    "All numeric values must be integers, not floats. Never ask for or generate code."
    " Avoid the words def, return and lambda even in prose. Describe results with "
    "'The output is ...' or 'The result equals ...'. Use no operator symbols in text."
    " Infer domain bounds from the description: integers within negative one million "
    "to one million, strings at most 128 characters, lists at most 64 items, dictionaries "
    "at most 20 entries. min/max bound integer values; min_length/max_length bound "
    "container sizes or string lengths. Supply zero placeholders for unused bounds."
)


def request_body(facts, description, model):
    # Explicit projection: caller additions cannot smuggle source/body/trace into cloud.
    public = {
        "function_name": facts["function"]["name"],
        "signature": facts["function"]["signature"],
        "description": description,
        "ast_facts": facts["ast_facts"],
    }
    clean(json.dumps(public))
    validate_text(description, description=True)
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(public, sort_keys=True)},
        ],
        "temperature": 0,
        "reasoning_effort": "low",
        "max_completion_tokens": 4096,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "spec_interpretation", "strict": True, "schema": SCHEMA},
        },
    }


def parse_interpretation(text, facts, source, keys=()):
    clean(text, keys)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate interpreter key")
            result[key] = value
        return result

    value = json.loads(
        text,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
    )
    validate(value, SCHEMA)
    validate_text(value, source, keys)
    if (
        not 1 <= len(value["requirements"]) <= 6
        or len(value["examples"]) > 8
        or len(value["ambiguities"]) > 8
    ):
        raise ValueError("Interpreter item limits exceeded")
    names = [d["param"] for d in facts["arg_domains"]]
    if [d["param"] for d in value["arg_domains"]] != names:
        raise ValueError("Interpreter changed parameter names/order")
    domains = []
    for d in value["arg_domains"]:
        domain = domain_for(d["kind"])

        def bounds(node):
            if node["kind"] == "integer":
                node.update(min=d["min"], max=d["max"])
            elif node["kind"] in {"list", "string"}:
                node.update(min_length=d["min_length"], max_length=d["max_length"])
                if node["kind"] == "list":
                    bounds(node["item_domain"])
            elif node["kind"] == "dict":
                node.update(min_size=d["min_length"], max_size=d["max_length"])
                bounds(node["value_domain"])

        bounds(domain)
        validate_domain(domain)
        domains.append(
            {"param": d["param"], "domain": domain, "source": "groq", "confidence": "tentative"}
        )
    schema = [{"name": d["param"], "domain": d["domain"]} for d in domains]
    requirements = []
    for i, req in enumerate(value["requirements"]):
        template = req["property_template_id"]
        if template and not template_compatible(template, schema):
            raise ValueError("Template incompatible with inferred domains")
        requirements.append(
            {
                "id": f"requirement-{i + 1}",
                "text": req["text"],
                "property_template_id": template,
                "source": "groq",
                "tier": "proposed",
            }
        )
    examples = []
    disagreements = list(value["ambiguities"])
    decoded = []
    for i, example in enumerate(value["examples"]):
        inputs = json.loads(
            example["inputs_json"],
            object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
        )
        expected = json.loads(
            example["expected_json"],
            object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")),
        )
        from codejury.stage2_tools.codec import validate_value

        validate_value(expected)
        if type(inputs) is not list or len(inputs) != len(domains):
            raise ValueError("Interpreter example changed positional arguments")

        def mentioned_characters(domain, item):
            if domain["kind"] == "string" and type(item) is str:
                # The finite alphabet remains a visible, user-reviewed envelope.
                # Body string constants are never consulted. Unicode appearing in
                # examples can be reviewed without silently assuming ASCII only.
                domain["alphabet"] = "".join(dict.fromkeys(domain["alphabet"] + item))
                validate_domain(domain)
            elif domain["kind"] == "list" and type(item) is list:
                for child in item:
                    mentioned_characters(domain["item_domain"], child)
            elif domain["kind"] == "dict" and type(item) is dict:
                for key, child in item.items():
                    mentioned_characters(domain["key_domain"], key)
                    mentioned_characters(domain["value_domain"], child)

        for domain, item in zip(domains, inputs, strict=True):
            mentioned_characters(domain["domain"], item)
        decoded.append((inputs, expected))
    for i, (inputs, expected) in enumerate(decoded):
        if check_args(schema, inputs):
            raise ValueError("Interpreter example outside inferred domain")
        matched = [
            r["property_template_id"]
            for r in requirements
            if r["property_template_id"]
            and typed_equal(expected_output(r["property_template_id"], inputs), expected)
        ]
        conflicting = {
            r["property_template_id"]
            for r in requirements
            if r["property_template_id"] and r["property_template_id"] not in matched
        }
        for template in sorted(conflicting):
            disagreements.append(
                f"Example {i + 1} conflicts with proposed property {template}; "
                "confirm the expected result before approval."
            )
        examples.append(
            {
                "id": f"example-{i + 1}",
                "args": inputs,
                "expected": expected,
                "source": "groq",
                "tier": "corroborated" if matched else "proposed",
                "corroboration": matched,
            }
        )
    result = {
        "arg_domains": domains,
        "requirements": requirements,
        "examples": examples,
        "disagreements": disagreements,
    }
    # The alphabet in host-created ValueDomains contains punctuation such as
    # assignment symbols. It is a trusted constant, not cloud-generated prose.
    validate_text(
        {
            "requirements": [r["text"] for r in requirements],
            "examples": [{"args": e["args"], "expected": e["expected"]} for e in examples],
            "disagreements": result["disagreements"],
        },
        source,
        keys,
    )
    return result


class Interpreter:
    def __init__(self, *, config=None, ledger=None, keys=None, connection=None):
        self.config = config or yaml.safe_load(
            local_path("config/stage2_core/teacher.yaml").read_text()
        )
        if self.config["max_cost_usd"] > 1 or self.config["max_in_flight"] != 1:
            raise ValueError("Interpreter must retain the configured shared cap and single flight")
        self.ledger = ledger
        self.keys = keys
        self.provided_connection = connection

    def interpret(self, facts, description, source):
        try:
            from codejury.stage2_core.teacher.client import Teacher, retry_time

            keys = self.keys if self.keys is not None else credentials(local_path("../.env"))
        except (ImportError, ValueError):
            raise Halt("Interpreter credentials or optional Groq dependency unavailable") from None
        self.ledger = self.ledger or Ledger(local_path(self.config["ledger"]))
        clean(source, keys)
        body = request_body(facts, description, self.config["model"])
        clean(json.dumps(body), keys)
        request_hash = json_hash({"version": "intake.interpreter.v1", "body": body})
        with self.ledger.exclusive():
            cached = self.ledger.cached(request_hash)
            if cached:
                # Recheck overlap against this body even for identical public facts.
                return {
                    **cached,
                    "spec": parse_interpretation(cached["response"], facts, source, keys),
                }
            summary = self.ledger.summary()
            from codejury.stage2_core.teacher.budget import RESERVATION

            if summary["charged_or_reserved_usd"] + RESERVATION / CAP > self.config["max_cost_usd"]:
                raise Halt("Interpreter configured spend cap reached")
            attempt = self.ledger.reserve(request_hash)
            connection = self.provided_connection or Teacher(keys, self.ledger).connection(keys[0])
            try:
                reply = connection.chat.completions.create(**body)
            except Exception as error:
                status = getattr(error, "status_code", None)
                if status in {400, 401, 403, 404, 422, 429}:
                    self.ledger.settle(
                        attempt,
                        status=f"http_{status}",
                        charge=0,
                        retry_at=retry_time(error.response.headers) if status == 429 else 0,
                    )
                # Unknown usage remains reserved; no replay or exception payload logging.
                raise Halt(
                    "Interpreter request failed; inspect budget state before retry"
                ) from None
            finally:
                if self.provided_connection is None:
                    connection.close()
            usage = getattr(reply, "usage", None)
            if usage is None or any(
                type(n) is not int or n < 0 for n in (usage.prompt_tokens, usage.completion_tokens)
            ):
                raise Halt("Interpreter usage unknown; dispatch halted")
            charge = usage.prompt_tokens * INPUT_RATE + usage.completion_tokens * OUTPUT_RATE
            content = reply.choices[0].message.content
            validator = "accepted"
            try:
                if reply.choices[0].finish_reason != "stop":
                    raise ValueError("Incomplete interpreter response")
                spec = parse_interpretation(content, facts, source, keys)
            except Exception as rejected:
                validator = "rejected"
                # A raw-text pass cannot prove nested JSON-escaped strings safe.
                # Retain rejection provenance and charges, never rejected content.
                self.ledger.settle(
                    attempt,
                    status="intake_rejected",
                    charge=charge,
                    result={
                        "request_hash": request_hash,
                        "response": None,
                        "validator": validator,
                        "rejection_type": type(rejected).__name__,
                        "timestamp": time.time(),
                    },
                )
                raise ValueError(
                    "Interpreter response rejected by specification/leak validation"
                ) from None
            result = {
                "request_hash": request_hash,
                "spec": spec,
                "response": clean(content, keys),
                "validator": validator,
                "model": self.config["model"],
                "timestamp": time.time(),
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                },
            }
            self.ledger.settle(attempt, status="ok", charge=charge, result=result)
            return result
