#!/usr/bin/env python3
"""
Contracts and Fixtures Validator for CodeJury Stage 1 (stage1.v1)
Validates that:
1. Canonical schema matches exact frozen SHA-256: 5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df
2. All fixtures defined in fixture-manifest.json strictly validate against their target $defs definition in the root schema.
3. Wire and business rules from the specification are satisfied.
"""

import argparse
import hashlib
import json
import os
import re
import sys

EXPECTED_SCHEMA_SHA256 = "5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df"

class ValidationError(Exception):
    pass

class SchemaValidator:
    def __init__(self, root_schema):
        self.root_schema = root_schema
        self.defs = root_schema.get("$defs", {})

    def resolve_ref(self, ref):
        if ref.startswith("#/$defs/"):
            def_name = ref.split("/")[-1]
            if def_name not in self.defs:
                raise ValidationError(f"Unknown $defs reference: {ref}")
            return self.defs[def_name]
        elif ref == "#":
            return self.root_schema
        raise ValidationError(f"Unsupported $ref format: {ref}")

    def validate(self, instance, schema, path="root"):
        if "$ref" in schema:
            target_schema = self.resolve_ref(schema["$ref"])
            return self.validate(instance, target_schema, path)

        if "anyOf" in schema:
            errors = []
            for i, branch in enumerate(schema["anyOf"]):
                try:
                    self.validate(instance, branch, f"{path}.anyOf[{i}]")
                    return
                except ValidationError as e:
                    errors.append(str(e))
            raise ValidationError(f"Instance at {path} failed all anyOf branches: {'; '.join(errors)}")

        if "const" in schema:
            if instance != schema["const"]:
                raise ValidationError(f"At {path}: expected const {schema['const']!r}, got {instance!r}")

        if "enum" in schema:
            if instance not in schema["enum"]:
                raise ValidationError(f"At {path}: value {instance!r} not in enum {schema['enum']}")

        target_type = schema.get("type")
        if target_type:
            if target_type == "null":
                if instance is not None:
                    raise ValidationError(f"At {path}: expected null, got {type(instance).__name__}")
                return
            elif target_type == "boolean":
                if not isinstance(instance, bool):
                    raise ValidationError(f"At {path}: expected boolean, got {type(instance).__name__}")
                return
            elif target_type == "integer":
                # In Python bool is subclass of int; explicitly reject bool
                if isinstance(instance, bool) or not isinstance(instance, int):
                    raise ValidationError(f"At {path}: expected integer (not bool), got {type(instance).__name__}")
                if "minimum" in schema and instance < schema["minimum"]:
                    raise ValidationError(f"At {path}: integer {instance} < minimum {schema['minimum']}")
                if "maximum" in schema and instance > schema["maximum"]:
                    raise ValidationError(f"At {path}: integer {instance} > maximum {schema['maximum']}")
                return
            elif target_type == "number":
                if isinstance(instance, bool) or not (isinstance(instance, (int, float))):
                    raise ValidationError(f"At {path}: expected number, got {type(instance).__name__}")
                if "minimum" in schema and instance < schema["minimum"]:
                    raise ValidationError(f"At {path}: number {instance} < minimum {schema['minimum']}")
                if "maximum" in schema and instance > schema["maximum"]:
                    raise ValidationError(f"At {path}: number {instance} > maximum {schema['maximum']}")
                return
            elif target_type == "string":
                if not isinstance(instance, str):
                    raise ValidationError(f"At {path}: expected string, got {type(instance).__name__}")
                if "minLength" in schema and len(instance) < schema["minLength"]:
                    raise ValidationError(f"At {path}: string length {len(instance)} < minLength {schema['minLength']}")
                if "maxLength" in schema and len(instance) > schema["maxLength"]:
                    raise ValidationError(f"At {path}: string length {len(instance)} > maxLength {schema['maxLength']}")
                if "pattern" in schema:
                    if not re.search(schema["pattern"], instance):
                        raise ValidationError(f"At {path}: string does not match pattern {schema['pattern']}")
                return
            elif target_type == "array":
                if not isinstance(instance, list):
                    raise ValidationError(f"At {path}: expected array, got {type(instance).__name__}")
                if "minItems" in schema and len(instance) < schema["minItems"]:
                    raise ValidationError(f"At {path}: array length {len(instance)} < minItems {schema['minItems']}")
                if "maxItems" in schema and len(instance) > schema["maxItems"]:
                    raise ValidationError(f"At {path}: array length {len(instance)} > maxItems {schema['maxItems']}")
                if "items" in schema:
                    item_schema = schema["items"]
                    for idx, item in enumerate(instance):
                        self.validate(item, item_schema, f"{path}[{idx}]")
                return
            elif target_type == "object":
                if not isinstance(instance, dict):
                    raise ValidationError(f"At {path}: expected object, got {type(instance).__name__}")

                # Check required properties
                required = schema.get("required", [])
                for req_key in required:
                    if req_key not in instance:
                        raise ValidationError(f"At {path}: missing required property '{req_key}'")

                # Check properties
                properties = schema.get("properties", {})
                for k, v in instance.items():
                    if k in properties:
                        self.validate(v, properties[k], f"{path}.{k}")
                    else:
                        add_props = schema.get("additionalProperties", True)
                        if add_props is False:
                            raise ValidationError(f"At {path}: unexpected property '{k}' (additionalProperties=false)")
                        elif isinstance(add_props, dict):
                            self.validate(v, add_props, f"{path}.{k}")
                return

def validate_business_rules(fixture_name, def_name, data):
    """Semantic checks specified in the operating contract and seam."""
    if def_name == "Domain":
        _check_domain(data, fixture_name)
    elif def_name == "RunCreate":
        for idx, d in enumerate(data.get("input_domain", [])):
            _check_domain(d, f"{fixture_name}.input_domain[{idx}]")
    elif def_name == "RunSnapshot":
        status = data.get("status")
        decision = data.get("decision")
        if status in ("queued", "running"):
            pass  # decision may be null
        else:
            if decision is None:
                raise ValidationError(f"In {fixture_name}: terminal status '{status}' requires a non-null Decision object")
            if status == "supported_patch":
                if not decision.get("selected_candidate_id"):
                    raise ValidationError(f"In {fixture_name}: supported_patch status requires selected_candidate_id")
                # original cannot be selected
                selected_id = decision.get("selected_candidate_id")
                for cand in data.get("candidates", []):
                    if cand.get("candidate_id") == selected_id and cand.get("origin") == "original":
                        raise ValidationError(f"In {fixture_name}: Candidate with origin=original cannot be selected as repair")

def _check_domain(domain, loc):
    kind = domain.get("kind")
    min_val = domain.get("min")
    max_val = domain.get("max")
    if min_val > max_val:
        raise ValidationError(f"At {loc}: min ({min_val}) cannot be greater than max ({max_val})")
    if min_val < -1000 or max_val > 1000:
        raise ValidationError(f"At {loc}: integer bounds must lie within [-1000, 1000]")
    if kind == "integer":
        if domain.get("min_length") is not None or domain.get("max_length") is not None:
            raise ValidationError(f"At {loc}: integer domain must have null length fields")
    elif kind == "list_integer":
        min_len = domain.get("min_length")
        max_len = domain.get("max_length")
        if min_len is None or max_len is None:
            raise ValidationError(f"At {loc}: list_integer requires bounded integer length fields")
        if not (0 <= min_len <= max_len <= 30):
            raise ValidationError(f"At {loc}: list lengths must satisfy 0 <= min_length <= max_length <= 30")

def main():
    parser = argparse.ArgumentParser(description="Validate contracts and synthetic fixtures.")
    parser.add_argument("--contracts", default="contracts", help="Path to contracts directory")
    args = parser.parse_args()

    schema_file = os.path.join(args.contracts, "stage1-api.schema.json")
    if not os.path.isfile(schema_file):
        print(f"ERROR: Canonical schema not found at {schema_file}", file=sys.stderr)
        return 1

    with open(schema_file, "rb") as f:
        schema_bytes = f.read()

    actual_sha = hashlib.sha256(schema_bytes).hexdigest()
    print(f"Checking schema SHA-256: {actual_sha}")
    if actual_sha != EXPECTED_SCHEMA_SHA256:
        print(f"ERROR: Schema SHA-256 mismatch!\n  Expected: {EXPECTED_SCHEMA_SHA256}\n  Actual:   {actual_sha}", file=sys.stderr)
        return 1
    print("✓ Schema SHA-256 exact match.")

    root_schema = json.loads(schema_bytes.decode("utf-8"))
    validator = SchemaValidator(root_schema)

    manifest_path = os.path.join(os.path.dirname(__file__), "..", "fixtures", "fixture-manifest.json")
    if not os.path.isfile(manifest_path):
        print(f"ERROR: Manifest not found at {manifest_path}", file=sys.stderr)
        return 1

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"Validating {len(manifest)} fixtures from manifest...")
    errors = 0
    for fixture_rel, def_name in manifest.items():
        fixture_path = os.path.join(os.path.dirname(args.contracts), fixture_rel)
        if not os.path.isfile(fixture_path):
            print(f"  ✗ {fixture_rel}: file not found", file=sys.stderr)
            errors += 1
            continue

        if def_name not in root_schema.get("$defs", {}):
            print(f"  ✗ {fixture_rel}: definition '{def_name}' not in $defs", file=sys.stderr)
            errors += 1
            continue

        try:
            with open(fixture_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            target_schema = root_schema["$defs"][def_name]
            validator.validate(data, target_schema, path=fixture_rel)
            validate_business_rules(fixture_rel, def_name, data)
            print(f"  ✓ {fixture_rel} -> $defs.{def_name}")
        except Exception as e:
            print(f"  ✗ {fixture_rel}: {e}", file=sys.stderr)
            errors += 1

    if errors > 0:
        print(f"\nFAILED: {errors} validation error(s).", file=sys.stderr)
        return 1

    print("\nSUCCESS: All fixtures and contract checksum validated perfectly.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
