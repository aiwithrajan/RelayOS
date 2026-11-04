"""DealSpec Pydantic v2 schemas and models."""
from datetime import datetime
from typing import Dict, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from .deal_state import DealState


class CustomerInfo(BaseModel):
    name: str = Field(..., description="Customer enterprise organization name")
    slug: str = Field(..., description="URL slug for tenant routing (e.g. acme)")
    contact_email: Optional[str] = Field(None, description="Primary billing/technical contact email")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean.isalnum() and "-" not in clean and "_" not in clean:
            raise ValueError("Slug must contain only alphanumeric characters, dashes, or underscores")
        return clean


class EngineeringSpec(BaseModel):
    adapter: str = Field(..., description="Adapter file name, e.g. acme_erp_adapter.py")
    tests_passed: bool = Field(False, description="Whether automated pytest tests passed")
    rate_limit_rpm: int = Field(..., ge=1, le=100000, description="Allocated rate limit in requests per minute")
    infra_cost_usd_year: float = Field(0.0, ge=0.0, description="Calculated infrastructure cost in USD/year")


class CommercialSpec(BaseModel):
    price_usd_year: float = Field(..., ge=0.0, description="Annual contract value in USD")
    term_months: int = Field(12, ge=1, le=60, description="Contract term in months")
    payment_terms: str = Field("Net-30", description="Payment terms, e.g. Net-15, Net-30, Net-60")
    setup_fee_waived: bool = Field(False, description="Whether the standard $2,500 setup fee is waived")
    white_label: bool = Field(False, description="Whether custom white-label branding is enabled")


class PlaybookRuleVerdict(BaseModel):
    status: Literal["pass", "fail"] = Field(..., description="Verdict: pass or fail")
    reason: str = Field("", description="Human-readable reason for the rule evaluation")


class PlaybookResult(BaseModel):
    margin: float = Field(..., description="Gross margin computed as (price - infra_cost) / price")
    rules: Dict[str, str] = Field(
        default_factory=dict,
        description="Dictionary of rule verdicts, e.g. {'R1': 'pass', 'R2': 'pass'}"
    )
    passed: bool = Field(False, description="True if all critical rules passed")


class ApprovalRecord(BaseModel):
    approved_by: str = Field(..., description="Identifier of the approver (founder or champion)")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    notes: Optional[str] = Field(None, description="Optional notes or signing message")


class Approvals(BaseModel):
    founder: Optional[ApprovalRecord] = Field(None, description="Founder commercial approval")
    customer: Optional[ApprovalRecord] = Field(None, description="Customer acceptance approval")


class DealSpec(BaseModel):
    deal_id: str = Field(..., description="Unique deal identifier, e.g. acme-2026-11")
    version: int = Field(1, ge=1, description="Immutable version counter, starts at 1")
    state: DealState = Field(DealState.DRAFT, description="Current lifecycle state of the deal")
    customer: CustomerInfo
    engineering: EngineeringSpec
    commercial: CommercialSpec
    playbook: Optional[PlaybookResult] = Field(None, description="Playbook validation output")
    approvals: Approvals = Field(default_factory=Approvals)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
