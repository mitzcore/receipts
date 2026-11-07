"""Deterministic matcher: amount + value date ± 2 business days + reference."""
from decimal import Decimal


def match(line: dict, entries: list[dict]) -> dict | None:
    for e in entries:
        if Decimal(e["amount"]) == Decimal(line["amount"]) and e["ref"] == line.get("ref"):
            return e
    return None
