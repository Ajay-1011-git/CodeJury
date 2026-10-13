"""Small strict remote projection, mapped into the frozen local draft."""

import json

from jsonschema import validate

from ..contracts import checked

SCHEMA = {
    "type": "object",
    "properties": {
        "source": {"type": "string"},
        "diagnosis": {"type": "string"},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "requirement_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["source", "diagnosis", "assumptions", "requirement_ids"],
    "additionalProperties": False,
}
RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {"name": "repair", "strict": True, "schema": SCHEMA},
}


def parse(text):
    if not isinstance(text, str) or len(text.encode()) > 48000:
        raise ValueError("Teacher response size")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate key")
            result[key] = value
        return result

    result = json.loads(text, object_pairs_hook=unique)
    validate(result, SCHEMA)
    return checked({**result, "suspected_sites": [], "suggested_families": []}, "RepairDraft")
