"""Interne datamodeller for queue-opbygningen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class WeekInterval:
    """Et manglende uge-item, der skal oprettes."""

    date_from: date
    date_to_exclusive: date
    reference: str


@dataclass
class WeekData:
    """De tre rå lister, der hentes for en uge."""

    interval: WeekInterval
    creditor_invoices: list[dict[str, Any]]
    invoice_sources: list[dict[str, Any]]
    document_references: list[dict[str, Any]]
