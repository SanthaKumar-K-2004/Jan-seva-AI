"""
Jan-Seva AI — Pydantic Models for Schemes
"""

from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional


class SchemeBase(BaseModel):
    """Base scheme model with common fields."""
    name: str
    description: Optional[str] = None
    ministry: Optional[str] = None
    department: Optional[str] = None
    state: str = "Central"
    category: list[str] = []
    benefits: Optional[str] = None
    documents_required: list[str] = []
    how_to_apply: Optional[str] = None
    application_url: Optional[str] = None
    application_fee: float = 0.0
    deadline: Optional[date] = None
    source_url: str
    source_type: Optional[str] = None
    
    # --- New Structured Fields for "Ultimate" Analysis ---
    eligibility_rules: Optional[dict] = Field(
        default_factory=dict, 
        description="Structured JSON-Logic for deterministic checking (e.g. {'and': [{'<': ['age', 30]}]})"
    )
    graph_relations: Optional[dict] = Field(
        default_factory=dict,
        description="Relationships to other schemes (e.g. {'prerequisite': ['scheme_id_1'], 'related': ['scheme_id_2']})"
    )
    beneficiary_type: list[str] = Field(default_factory=list, description="Target audience (e.g. ['student', 'farmer'])")
    keywords: list[str] = Field(default_factory=list, description="Search keywords including regional terms")


class SchemeCreate(SchemeBase):
    """Model for creating a new scheme."""
    pass


class SchemeResponse(SchemeBase):
    """Model returned from API."""
    id: str
    slug: str
    is_active: bool = True
    last_verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SchemeSearchResult(BaseModel):
    """Result from vector similarity search."""
    scheme_id: str
    scheme_name: str
    chunk_text: str
    similarity_score: float
    source_url: Optional[str] = None
