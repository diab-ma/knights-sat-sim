"""Managed connection hook; KSAT-17/20 add packet and receive helpers here."""

import json
from pathlib import Path


def load_connection() -> dict[str, str]:
    """Read fresh Attempt context on every invocation; never cache credentials."""
    return json.loads(Path("/attempt/connection.json").read_text())
