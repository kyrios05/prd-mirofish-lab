from pydantic import BaseModel, Field
from typing import List

class Stakeholder(BaseModel):
    name: str = Field(..., min_length=1, description="Stakeholder name or role label")
    role: str = Field(..., min_length=1, description="Organizational role")
    review_angle: str = Field(
        ..., min_length=1, description="What aspect of the PRD this stakeholder evaluates"
    )
    likely_objections: List[str] = Field(
        default_factory=list, description="Anticipated objections this stakeholder might raise"
    )

class StakeholderProposalResponse(BaseModel):
    stakeholders: List[Stakeholder]
