"""Acceptance Tests AT-2 and AT-3 for Sprint 2 (Negotiation & Margin Counter Loop)."""
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


def test_at2_intermediate_counter_scenarios():
    """AT-2: $22,000 at 1,000 req/min, then $20,000 at 600 req/min both fail R1 at 63.6% and 74.0%."""
    # Scenario A: Raise price only ($22k price, 1,000 RPM -> cost $8,000)
    spec_a = DealSpec(
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
            price_usd_year=22000.0,
            term_months=12,
            payment_terms="Net-30",
            setup_fee_waived=False,
            white_label=True,
        ),
    )
    result_a = evaluate_playbook(spec_a)
    # Margin: (22000 - 8000) / 22000 = 14000 / 22000 = 0.63636 -> 63.6%
    assert round(result_a.margin, 3) == 0.636 or round(result_a.margin * 100, 1) == 63.6
    assert result_a.rules["R1"] == "fail", "R1 must fail (63.6% < 75%)"
    assert result_a.rules["R2"] == "pass", "R2 passes ($22,000 >= $21,600 floor, 8.3% discount)"
    assert result_a.passed is False

    # Scenario B: Cap RPM only ($20k price, 600 RPM -> cost $5,200)
    spec_b = DealSpec(
        deal_id="acme-2026-11",
        version=1,
        state=DealState.ENGINEERED,
        customer=CustomerInfo(name="Acme FinTech", slug="acme"),
        engineering=EngineeringSpec(
            adapter="acme_erp_adapter.py",
            tests_passed=True,
            rate_limit_rpm=600,
            infra_cost_usd_year=estimate_infra_cost(600),  # $5,200.0
        ),
        commercial=CommercialSpec(
            price_usd_year=20000.0,
            term_months=12,
            payment_terms="Net-30",
            setup_fee_waived=False,
            white_label=True,
        ),
    )
    result_b = evaluate_playbook(spec_b)
    # Margin: (20000 - 5200) / 20000 = 14800 / 20000 = 0.7400 -> 74.0%
    assert round(result_b.margin, 3) == 0.740
    assert result_b.rules["R1"] == "fail", "R1 must fail (74.0% < 75%)"
    assert result_b.rules["R2"] == "fail", "R2 must fail ($20,000 < $21,600 floor, 16.7% discount)"
    assert result_b.passed is False


def test_at3_founder_counter_passes_all_rules():
    """AT-3: $22,000, 600 req/min, Net-15, setup fee waived, white-label yields 76.4% margin and R1-R5 all pass."""
    spec_v2 = DealSpec(
        deal_id="acme-2026-11",
        version=2,
        state=DealState.ENGINEERED,
        customer=CustomerInfo(name="Acme FinTech", slug="acme"),
        engineering=EngineeringSpec(
            adapter="acme_erp_adapter.py",
            tests_passed=True,
            rate_limit_rpm=600,
            infra_cost_usd_year=estimate_infra_cost(600),  # $5,200.0
        ),
        commercial=CommercialSpec(
            price_usd_year=22000.0,
            term_months=12,
            payment_terms="Net-15",
            setup_fee_waived=True,
            white_label=True,
        ),
    )

    result = evaluate_playbook(spec_v2)

    # Margin: (22000 - 5200) / 22000 = 16800 / 22000 = 0.763636 -> 76.4%
    assert round(result.margin, 3) == 0.764 or round(result.margin * 100, 1) == 76.4
    assert result.passed is True, "All rules should pass for Founder counter"
    assert result.rules["R1"] == "pass", "R1 passes (76.4% >= 75%)"
    assert result.rules["R2"] == "pass", "R2 passes (8.3% discount <= 10%)"
    assert result.rules["R3"] == "pass", "R3 passes (waived setup fee allowed at $22k and 12 mo)"
    assert result.rules["R4"] == "pass", "R4 passes (Net-15 allowed)"
    assert result.rules["R5"] == "pass", "R5 passes (White-label permitted)"
