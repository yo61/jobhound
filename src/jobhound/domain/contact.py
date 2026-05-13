"""The Contact value object."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Contact:
    """A single contact attached to an opportunity. `name` is required."""

    name: str
    role: str | None = None
    channel: str | None = None
    company: str | None = None
    note: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Contact.name must be non-empty")

    def to_dict(self) -> dict[str, str]:
        out: dict[str, str] = {"name": self.name}
        if self.role is not None:
            out["role"] = self.role
        if self.channel is not None:
            out["channel"] = self.channel
        if self.company is not None:
            out["company"] = self.company
        if self.note is not None:
            out["note"] = self.note
        return out

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> Contact:
        if "name" not in data or not data["name"]:
            raise ValueError("contact dict must have a non-empty 'name'")
        return cls(
            name=data["name"],
            role=data.get("role"),
            channel=data.get("channel"),
            company=data.get("company"),
            note=data.get("note"),
        )
