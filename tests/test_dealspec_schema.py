"""Tests for DealSpec schema and State Machine transitions."""
import pytest
from core.schemas import (
    DealSpec,
    DealState,
    CustomerInfo,
    EngineeringSpec,
    CommercialSpec,
    PlaybookResult,
    can_transition,
)


def test_dealspec_prd_example_serialization():
    """Verify that the DealSpec example from the PRD parses and serializes identically."""
    sample_data = {
        "deal_id": "acme-2026-11",
        "version": 2,
        "state": "PRICE_CHECKED",
        "customer": {"name": "Acme FinTech", "slug": "acme"},
        "engineering": {
            "adapter": "acme_erp_adapter.py",
            "tests_passed": True,
            "rate_limit_rpm": 600,
            "infra_cost_usd_year": 5200.0,
        },
        "commercial": {
            "price_usd_year": 22000.0,
            "term_months": 12,
            "payment_terms": "Net-15",
            "setup_fee_waived": True,
            "white_label": True,
        },
        "playbook": {
            "margin": 0.764,
            "rules": {"R1": "pass", "R2": "pass", "R3": "pass", "R4": "pass", "R5": "pass"},
            "passed": True,
        },
        "approvals": {"founder": None, "customer": None},
    }

    spec = DealSpec(**sample_data)
    assert spec.deal_id == "acme-2026-11"
    assert spec.version == 2
    assert spec.state == DealState.PRICE_CHECKED
    assert spec.customer.slug == "acme"
    assert spec.engineering.rate_limit_rpm == 600
    assert spec.commercial.price_usd_year == 22000.0
    assert spec.playbook is not None
    assert spec.playbook.margin == 0.764
    assert spec.playbook.rules["R1"] == "pass"


def test_state_machine_valid_forward_flow():
    """Check standard happy path state transitions."""
    assert can_transition(DealState.DRAFT, DealState.ENGINEERED)
    assert can_transition(DealState.ENGINEERED, DealState.PRICE_CHECKED)
    assert can_transition(DealState.PRICE_CHECKED, DealState.FOUNDER_APPROVED)
    assert can_transition(DealState.FOUNDER_APPROVED, DealState.CUSTOMER_ACCEPTED)
    assert can_transition(DealState.CUSTOMER_ACCEPTED, DealState.PROVISIONED)
    assert can_transition(DealState.PROVISIONED, DealState.INVOICED)


def test_state_machine_invalid_skips():
    """Check that unauthorized skips are denied."""
    # Cannot jump straight from DRAFT to INVOICED or PROVISIONED
    assert not can_transition(DealState.DRAFT, DealState.INVOICED)
    assert not can_transition(DealState.DRAFT, DealState.PROVISIONED)
    assert not can_transition(DealState.ENGINEERED, DealState.CUSTOMER_ACCEPTED)
    assert not can_transition(DealState.FOUNDER_APPROVED, DealState.INVOICED)


def test_state_machine_rejections_to_engineered():
    """Failed playbook check or customer rejection returns to ENGINEERED for counter."""
    assert can_transition(DealState.PRICE_CHECKED, DealState.ENGINEERED)
    assert can_transition(DealState.FOUNDER_APPROVED, DealState.ENGINEERED)


def test_invalid_slug():
    """Customer slug validation should reject invalid symbols."""
    with pytest.raises(ValueError):
        CustomerInfo(name="Bad Org", slug="bad/slug*name")
