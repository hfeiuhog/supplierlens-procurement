from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")
    label: str = Field(min_length=1, max_length=200)
    mandatory: bool = True


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_key: str = Field(min_length=1, max_length=60)
    document_ref: str = Field(min_length=1, max_length=300)
    version: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=1, max_length=4000)
    valid_until: datetime


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vendor_ref: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    tender_ref: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    requirements: list[Requirement] = Field(min_length=1, max_length=100)
    evidence: list[Evidence] = Field(max_length=300)

    @model_validator(mode="after")
    def unique_requirements(self) -> ReviewInput:
        keys = [r.key for r in self.requirements]
        if len(set(keys)) != len(keys):
            raise ValueError("Requirement keys must be unique")
        if any(e.requirement_key not in keys for e in self.evidence):
            raise ValueError("Evidence refers to an unknown requirement")
        if any(e.valid_until.tzinfo is None for e in self.evidence):
            raise ValueError("Evidence expiry needs an explicit timezone")
        return self


class Decision(BaseModel):
    version: int = Field(ge=1)
    action: Literal["submit", "approve", "reject"]
    note: str = Field(default="", max_length=1000)


def validate_evidence(payload: dict[str, Any], now: datetime | None = None) -> None:
    review = ReviewInput.model_validate(payload)
    current = now or datetime.now(timezone.utc)
    valid = {e.requirement_key for e in review.evidence if e.valid_until > current}
    missing = [r.key for r in review.requirements if r.mandatory and r.key not in valid]
    if missing:
        raise ValueError("Current evidence is missing for: " + ", ".join(missing))
