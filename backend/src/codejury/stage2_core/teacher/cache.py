"""Request identity includes immutable prompt, settings, schema and input lineage."""

from ..contracts import json_hash


def identity(body, lineage):
    return json_hash({"version": "teacher-request.v1", "body": body, "lineage": lineage})
