"""The Priority value object for an Opportunity."""

from __future__ import annotations

from enum import StrEnum


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
