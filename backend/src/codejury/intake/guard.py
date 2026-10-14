"""Reject code, body overlap and secrets before accepting interpreter text."""

import ast
import re
from difflib import SequenceMatcher

from codejury.stage2_core.teacher.redaction import clean

CODE = re.compile(
    r"`|\bdef\b|\breturn\b|\blambda\b|\bimport\s+\w+|"
    r"\b[a-zA-Z_]\w*\s*(?:=(?!=)|\+=|-=|\*=|/=)|"
    r"\b[a-zA-Z_]\w*\s*(?:\+|-|\*|/|//|==|!=|<=|>=|<|>)\s*(?:\w|\()|"
    r"\b[a-zA-Z_]\w*\([^\n)]*\)"
)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            # Decoded example dictionary keys are user-visible strings too. JSON
            # escapes must not provide a second route for code or secret leakage.
            yield from strings(key)
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def validate_text(value, source="", keys=(), *, description=False):
    body = ""
    if source:
        tree = ast.parse(source)
        body = "\n".join(
            ast.unparse(statement)
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            for statement in node.body
        )
    body_tokens = re.findall(r"\w+", body.lower())
    body_grams = {tuple(body_tokens[i : i + 5]) for i in range(max(0, len(body_tokens) - 4))}
    for text in strings(value):
        clean(text, keys)
        matches = list(CODE.finditer(text))
        if description and matches and all(m.group().startswith("return") for m in matches):
            try:
                ast.parse(text)
            except SyntaxError:
                matches = []
        if matches:
            raise ValueError("Interpreter code-like text rejected")
        tokens = re.findall(r"\w+", text.lower())
        grams = {tuple(tokens[i : i + 5]) for i in range(max(0, len(tokens) - 4))}
        if grams and body_grams and len(grams & body_grams) / len(grams) >= 0.5:
            raise ValueError("Interpreter text overlaps buggy body")
        if (
            len(tokens) >= 8
            and body_tokens
            and SequenceMatcher(None, tokens, body_tokens, autojunk=False).ratio() > 0.8
        ):
            raise ValueError("Interpreter text overlaps buggy body")
