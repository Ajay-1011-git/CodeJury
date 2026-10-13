"""Reviewed template bindings from explicit runtime contracts, never reference solutions."""

from ..contracts import checked
from ..data import runtime_example

# Each exact approved contract has the same semantics as this inspected registered template.
# Other contracts retain no property binding; generated expected values remain observations.
REVIEWED_BINDINGS = {
    "Return the mathematical sum of the integers.": "sum_ints",
    "Return the number of occurrences of target.": "count_occurrences_ints",
}


def runtime_input(row):
    if row["split"] not in {"train", "validation"}:
        raise ValueError("Only authorized train/validation runtime inputs are allowed")
    problem, tests = runtime_example(row)
    template = REVIEWED_BINDINGS.get(problem["contract_text"])
    if template:
        from codejury.stage2_tools.oracles.registry import template_compatible

        if not template_compatible(template, problem["domain_schema"]):
            raise ValueError("Reviewed property does not match the runtime domains")
        for requirement in problem["requirements"]:
            if requirement["approval_status"] != "approved":
                raise ValueError("Property binding requires an approved contract")
            requirement["property_template_id"] = template
    return checked(problem, "Problem"), tests


def training_input(row):
    if row["split"] != "train":
        raise ValueError("Collection consumes training records only")
    return runtime_input(row)
