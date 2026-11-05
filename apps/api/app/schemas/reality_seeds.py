"""API envelopes for this lab's seed selection, outside the PRD schema."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from .common import Stakeholder


class RealitySeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    prd: dict[str, Any]


class SeedMember(Stakeholder):
    source_uuid: str | None = None


class SeedPanel(BaseModel):
    # Explanatory envelope metadata (e.g. a synthetic-data notice) is harmless;
    # each member still validates against the strict Stakeholder schema.
    model_config = ConfigDict(extra="ignore")
    members: list[SeedMember] = Field(min_length=12, max_length=12)
