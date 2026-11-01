from typing import Literal, Optional

from pydantic import BaseModel, Field


class FeedbackIn(BaseModel):
    usability_rating: int = Field(ge=1, le=5, description="Facilidade de uso (1–5)")
    usefulness_rating: int = Field(ge=1, le=5, description="Utilidade percebida (1–5)")
    would_use_again: Literal["sim", "talvez", "nao"]
    difficulties: str = Field(default="", max_length=2000)
    suggestions: str = Field(default="", max_length=2000)


class IssueFilters(BaseModel):
    q: Optional[str] = None
    columns: list[str] = []
    categories: list[str] = []
    severities: list[str] = []
    sort_by: str = "row"
    descending: bool = False
