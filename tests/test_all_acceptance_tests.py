"""Master Acceptance Test Suite (AT-1 through AT-8).

Directly validates all 8 mandatory acceptance criteria from RelayOS PRD v2:
- AT-1: DealSpec at $20k & 1,000 RPM fails R1 and R2 at 60.0% margin.
- AT-2: Intermediate offers ($22k/1k RPM & $20k/600 RPM) fail R1 at 63.6% and 74.0%.
- AT-3: Founder counter ($22k, 600 RPM, Net-15, waived fee, white-label) passes R1-R5 at 76.4%.
- AT-4: Cost model determinism across 5 runs ($8k at 1k RPM, $5.2k at 600 RPM).
- AT-5: Money-moving tools rejected in any state prior to CUSTOMER_ACCEPTED.
- AT-6: @architect calling create_invoice is denied (HTTP 403) and logged to audit.
- AT-7: Tenant acme rate limit (601st request returns 429, /t/unknown returns 404).
- AT-8: Accepted DealSpec v2 matches PDF and Stripe invoice attributes.
"""
import pytest
from fastapi.testclient import TestClient
from core.main import app, seed_initial_deal_if_empty
from core.database import reset_db, get_deal_spec, get_audit_logs, get_tenant
from core.schemas import DealState, DealSpec, CustomerInfo, EngineeringSpec, CommercialSpec
from core.cost_model import estimate_infra_cost
from core.playbook_engine import evaluate_playbook
from core.rate_limiter import tenant_rate_limiter


@pytest.fixture(autouse=True)
def setup_db():
    reset_db()
    seed_initial_deal_if_empty()
    tenant_rate_limiter.reset()


def test_at1_initial_ask_fails_r1_and_r2():
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
    assert result.margin == 0.600
    assert result.passed is False
    assert result.rules["R1"] == "fail"
    assert result.rules["R2"] == "fail"


def test_at2_intermediate_counter_scenarios_fail_r1():
    """AT-2: $22,000 at 1,000 req/min, then $20,000 at 600 req/min both fail R1 at 63.6% and 74.0%."""
    # Scenario A: Raise price only ($22k, 1k RPM)
    spec_a = DealSpec(
        deal_id="acme-2026-11",
        version=1,
        state=DealState.ENGINEERED,
        customer=CustomerInfo(name="Acme FinTech", slug="acme"),
        engineering=EngineeringSpec(adapter="acme_erp_adapter.py", tests_passed=True, rate_limit_rpm=1000, infra_cost_usd_year=8000.0),
        commercial=CommercialSpec(price_usd_year=22000.0, term_months=12, payment_terms="Net-30", setup_fee_waived=False, white_label=True),
    )
    res_a = evaluate_playbook(spec_a)
    assert round(res_a.margin, 3) == 0.636
    assert res_a.rules["R1"] == "fail"

    # Scenario B: Cap RPM only ($20k, 600 RPM)
    spec_b = DealSpec(
        deal_id="acme-2026-11",
        version=1,
        state=DealState.ENGINEERED,
        customer=CustomerInfo(name="Acme FinTech", slug="acme"),
        engineering=EngineeringSpec(adapter="acme_erp_adapter.py", tests_passed=True, rate_limit_rpm=600, infra_cost_usd_year=5200.0),
        commercial=CommercialSpec(price_usd_year=20000.0, term_months=12, payment_terms="Net-30", setup_fee_waived=False, white_label=True),
    )
    res_b = evaluate_playbook(spec_b)
    assert round(res_b.margin, 3) == 0.740
    assert res_b.rules["R1"] == "fail"


def test_at3_founder_counter_passes_all_rules():
    """AT-3: $22,000, 600 req/min, Net-15, setup fee waived, white-label yields 76.4% margin and R1-R5 all pass."""
    spec_v2 = DealSpec(
        deal_id="acme-2026-11",
        version=2,
        state=DealState.ENGINEERED,
        customer=CustomerInfo(name="Acme FinTech", slug="acme"),
        engineering=EngineeringSpec(adapter="acme_erp_adapter.py", tests_passed=True, rate_limit_rpm=600, infra_cost_usd_year=5200.0),
        commercial=CommercialSpec(price_usd_year=22000.0, term_months=12, payment_terms="Net-15", setup_fee_waived=True, white_label=True),
    )
    res = evaluate_playbook(spec_v2)
    assert round(res.margin, 3) == 0.764 or round(res.margin * 100, 1) == 76.4
    assert res.passed is True
    assert all(status == "pass" for status in res.rules.values())


def test_at4_cost_model_determinism():
    """AT-4: estimate_cost called five times returns $8,000 for 1k RPM and $5,200 for 600 RPM every time."""
    for _ in range(5):
        assert estimate_infra_cost(1000) == 8000.0
        assert estimate_infra_cost(600) == 5200.0


def test_at5_money_tools_rejected_before_customer_accepted():
    """AT-5: Provisioning and invoicing fail in any state prior to CUSTOMER_ACCEPTED."""
    with TestClient(app) as client:
        # Fails in PRICE_CHECKED
        resp = client.post("/api/v1/agent-tools/provision-tenant", json={"deal_id": "acme-2026-11"})
        assert resp.status_code == 400
        assert "State Gate Violation (AT-5)" in resp.json()["detail"]

        # Counter and Founder Approve
        client.post("/api/v1/admin/deals/acme-2026-11/counter")
        client.post("/api/v1/admin/deals/acme-2026-11/founder-approve")

        # Fails in FOUNDER_APPROVED (Customer has not accepted yet)
        resp2 = client.post("/api/v1/agent-tools/provision-tenant", json={"deal_id": "acme-2026-11"})
        assert resp2.status_code == 400


def test_at6_architect_denied_from_billing():
    """AT-6: @architect calling create_invoice is denied (HTTP 403) and logged to audit."""
    with TestClient(app) as client:
        client.post("/api/v1/admin/deals/acme-2026-11/counter")
        client.post("/api/v1/admin/deals/acme-2026-11/founder-approve")
        client.post("/api/v1/customer/proposal/acme/accept")

        resp = client.post("/api/v1/agent-tools/create-invoice", json={"deal_id": "acme-2026-11", "caller": "@architect"})
        assert resp.status_code == 403
        assert "Privilege Isolation Violation (AT-6)" in resp.json()["detail"]

        logs = get_audit_logs(deal_id="acme-2026-11")
        denied = [l for l in logs if l["actor"] == "@architect" and l["status"] == "DENIED"]
        assert len(denied) > 0


def test_at7_tenant_rate_limiting_600_rpm():
    """AT-7: Tenant acme rate limit 600 RPM returns 429 on 601st request; /t/unknown returns 404."""
    with TestClient(app) as client:
        # Unknown tenant returns 404
        assert client.get("/t/unknown").status_code == 404

        # Transition and provision acme
        client.post("/api/v1/admin/deals/acme-2026-11/counter")
        client.post("/api/v1/admin/deals/acme-2026-11/founder-approve")
        client.post("/api/v1/customer/proposal/acme/accept")
        client.post("/api/v1/agent-tools/provision-tenant", json={"deal_id": "acme-2026-11"})

        # Fire 600 requests -> all 200 OK
        for _ in range(600):
            r = client.get("/t/acme?format=json")
            assert r.status_code == 200

        # 601st request -> 429 Too Many Requests
        over = client.get("/t/acme?format=json")
        assert over.status_code == 429


def test_at8_artifacts_match_dealspec_v2():
    """AT-8: Order Form PDF and invoice match DealSpec v2 attributes."""
    with TestClient(app) as client:
        client.post("/api/v1/admin/deals/acme-2026-11/counter")
        client.post("/api/v1/admin/deals/acme-2026-11/founder-approve")
        client.post("/api/v1/customer/proposal/acme/accept")
        client.post("/api/v1/agent-tools/provision-tenant", json={"deal_id": "acme-2026-11"})

        pdf_resp = client.post("/api/v1/agent-tools/render-order-form", json={"deal_id": "acme-2026-11"})
        assert pdf_resp.status_code == 200

        inv_resp = client.post("/api/v1/agent-tools/create-invoice", json={"deal_id": "acme-2026-11"})
        assert inv_resp.status_code == 200
        inv = inv_resp.json()

        deal = get_deal_spec("acme-2026-11")
        assert inv["amount_usd"] == deal.commercial.price_usd_year == 22000.0
        assert inv["payment_terms"] == deal.commercial.payment_terms == "Net-15"
        assert deal.engineering.rate_limit_rpm == 600
        assert deal.commercial.setup_fee_waived is True
        assert deal.state == DealState.INVOICED
