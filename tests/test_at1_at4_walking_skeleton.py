"""Acceptance Tests AT-1 and AT-4 for Sprint 1 (Walking Skeleton)."""
import pytest
from core.cost_model import estimate_infra_cost
from core.playbook_engine import evaluate_playbook
from core.schemas import (
    DealSpec,
    DealState,
    CustomerInfo,
    EngineeringSpec,
    CommercialSpec,
)


def test_at4_cost_model_determinism():
    """AT-4: estimate_cost called five times per input returns $8,000 and $5,200 every time."""
    for _ in range(5):
        cost_1000 = estimate_infra_cost(1000)
        assert cost_1000 == 8000.0, f"Expected 8000.0, got {cost_1000}"

    for _ in range(5):
        cost_600 = estimate_infra_cost(600)
        assert cost_600 == 5200.0, f"Expected 5200.0, got {cost_600}"


def test_at1_initial_ask_fails_playbook():
    """AT-1: A DealSpec at $20,000 and 1,000 req/min yields 60.0% margin, fails citing R1 and R2."""
    spec_v1 = DealSpec(
        deal_id="acme-2026-11",
        version=1,
        state=DealState.ENGINEERED,
        customer=CustomerInfo(name="Acme FinTech", slug="acme"),
        engineering=EngineeringSpec(
            adapter="acme_erp_adapter.py",
            tests_passed=True,
            rate_limit_rpm=1000,
            infra_cost_usd_year=estimate_infra_cost(1000),  # $8,000.0
        ),
        commercial=CommercialSpec(
            price_usd_year=20000.0,
            term_months=12,
            payment_terms="Net-30",
            setup_fee_waived=False,
            white_label=True,
        ),
    )

    result = evaluate_playbook(spec_v1)

    # Margin check: (20000 - 8000) / 20000 = 12000 / 20000 = 0.6 (60.0%)
    assert result.margin == 0.6, f"Expected 0.6 margin, got {result.margin}"
    assert result.passed is False, "Expected playbook check to fail"
    assert result.rules["R1"] == "fail", "Expected R1 (Margin floor 75%) to fail"
    assert result.rules["R2"] == "fail", "Expected R2 (Discount authority floor $21,600) to fail"
    assert result.rules["R3"] == "pass"
    assert result.rules["R4"] == "pass"
    assert result.rules["R5"] == "pass"
