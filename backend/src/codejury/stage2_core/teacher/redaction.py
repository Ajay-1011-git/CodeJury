"""Load only named credentials; fail closed before persisting secret-like payloads."""

import os
import re
from pathlib import Path

NAMES = ("GROQ_API_KEY", "groq_api_1", "groq_api_2", "groq_api_3")
SECRET = re.compile(r"gsk_[A-Za-z0-9_-]+|sk-[A-Za-z0-9_-]{16,}|-----BEGIN .*PRIVATE KEY")


def credentials(env_path=None):
    values = {name: os.environ.get(name, "") for name in NAMES}
    if env_path is not None:
        path = Path(env_path)
        if path.is_symlink():
            raise ValueError("Credential symlink forbidden")
        if path.is_file():
            for line in path.read_text().splitlines():
                name, sep, value = line.removeprefix("export ").partition("=")
                name = name.strip()
                if sep and name in NAMES and not values[name]:
                    values[name] = value.strip().strip("\"'")
    keys = list(dict.fromkeys(v for v in values.values() if v))
    if not keys:
        raise ValueError("Teacher credential unavailable")
    return keys


def clean(text, keys=()):
    if SECRET.search(text) or any(key and key in text for key in keys):
        raise ValueError("Secret-like content rejected")
    return text
