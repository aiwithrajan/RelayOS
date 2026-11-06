"""Acceptance Test AT-5: Strict Server-Side State Machine Gate and Customer Sign-off."""
import pytest
from fastapi.testclient import TestClient
from core.main import app, seed_initial_deal_if_empty
from core.database import reset_db, get_deal_spec
from core.schemas import DealState


@pytest.fixture(autouse=True)
def setup_db():
    reset_db()
    seed_initial_deal_if_empty()


def test_customer_proposal_redaction():
    """Ensure customer proposal strictly redacts internal margins, costs, and playbook rules."""
    with TestClient(app) as client:
        res = client.get("/api/v1/customer/proposal/acme")
        assert res.status_code == 200
        data = res.json()
        assert data["customer"]["slug"] == "acme"
        assert "price_usd_year" in data["commercial"]
        assert "rate_limit_rpm" in data["engineering"]
        
        # Security assertion: Redaction of internal financials
        assert "infra_cost_usd_year" not in data["engineering"], "Internal infra cost leaked to customer!"
        assert "playbook" not in data, "Internal margin playbook leaked to customer!"


def test_at5_premature_calls_rejected_across_all_early_states():
    """AT-5: In any state prior to CUSTOMER_ACCEPTED, money-moving calls are rejected."""
    with TestClient(app) as client:
        # Initial deal is in PRICE_CHECKED
        deal = get_deal_spec("acme-2026-11")
        assert deal.state == DealState.PRICE_CHECKED

        # 1. Attempt provisioning in PRICE_CHECKED -> must fail
        prov_resp = client.post("/api/v1/agent-tools/provision-tenant", json={"deal_id": "acme-2026-11"})
        assert prov_resp.status_code == 400
        assert "State Gate Violation (AT-5)" in prov_resp.json()["detail"]

        # 2. Attempt PDF generation in PRICE_CHECKED -> must fail
        pdf_resp = client.post("/api/v1/agent-tools/render-order-form", json={"deal_id": "acme-2026-11"})
        assert pdf_resp.status_code == 400
        assert "State Gate Violation (AT-5)" in pdf_resp.json()["detail"]

        # 3. Attempt invoice creation in PRICE_CHECKED -> must fail
        inv_resp = client.post("/api/v1/agent-tools/create-invoice", json={"deal_id": "acme-2026-11"})
        assert inv_resp.status_code == 400
        assert "State Gate Violation (AT-5)" in inv_resp.json()["detail"]

        # Transition to FOUNDER_APPROVED via counter offer
        client.post("/api/v1/admin/deals/acme-2026-11/counter")
        client.post("/api/v1/admin/deals/acme-2026-11/founder-approve")

        deal = get_deal_spec("acme-2026-11")
        assert deal.state == DealState.FOUNDER_APPROVED

        # 4. Attempt provisioning in FOUNDER_APPROVED -> must STILL fail (Customer has not accepted yet!)
        prov_resp2 = client.post("/api/v1/agent-tools/provision-tenant", json={"deal_id": "acme-2026-11"})
        assert prov_resp2.status_code == 400
        assert "State Gate Violation (AT-5)" in prov_resp2.json()["detail"]

        # 5. Attempt invoice creation in FOUNDER_APPROVED -> must STILL fail
        inv_resp2 = client.post("/api/v1/agent-tools/create-invoice", json={"deal_id": "acme-2026-11"})
        assert inv_resp2.status_code == 400
        assert "State Gate Violation (AT-5)" in inv_resp2.json()["detail"]


def test_at5_unlocked_only_after_customer_accepts():
    """Verify that once Customer Champion accepts in FOUNDER_APPROVED state, money tools unlock."""
    with TestClient(app) as client:
        # Founder counters and approves
        client.post("/api/v1/admin/deals/acme-2026-11/counter")
        client.post("/api/v1/admin/deals/acme-2026-11/founder-approve")

        # Customer accepts proposal
        accept_resp = client.post("/api/v1/customer/proposal/acme/accept")
        assert accept_resp.status_code == 200
        assert accept_resp.json()["state"] == "CUSTOMER_ACCEPTED"

        deal = get_deal_spec("acme-2026-11")
        assert deal.state == DealState.CUSTOMER_ACCEPTED
        assert deal.approvals.customer is not None
        assert deal.approvals.customer.approved_by == "acme_champion"

        # Now provisioning succeeds!
        prov_resp = client.post("/api/v1/agent-tools/provision-tenant", json={"deal_id": "acme-2026-11"})
        assert prov_resp.status_code == 200
        assert prov_resp.json()["status"] == "success"
        assert prov_resp.json()["state"] == "PROVISIONED"

        # Now PDF rendering succeeds!
        pdf_resp = client.post("/api/v1/agent-tools/render-order-form", json={"deal_id": "acme-2026-11"})
        assert pdf_resp.status_code == 200
        assert pdf_resp.json()["status"] == "success"

        # Now invoice creation succeeds!
        inv_resp = client.post("/api/v1/agent-tools/create-invoice", json={"deal_id": "acme-2026-11"})
        assert inv_resp.status_code == 200
        assert inv_resp.json()["status"] == "success"
        assert inv_resp.json()["state"] == "INVOICED"


def test_customer_request_changes_flow():
    """Verify customer champion can request changes and generate an audit log entry."""
    with TestClient(app) as client:
        req_payload = {
            "notes": "Requesting 800 RPM quota to handle month-end payroll spikes.",
            "requested_rpm": 800,
            "requested_price": 21000.0,
        }
        res = client.post("/api/v1/customer/proposal/acme/request-changes", json=req_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "Switch deal room #acme-fintech-closing" in data["message"]

        # Verify audit log
        logs_res = client.get("/api/v1/admin/audit-logs?deal_id=acme-2026-11")
        assert logs_res.status_code == 200
        logs = logs_res.json()
        change_logs = [l for l in logs if l["actor"] == "acme_champion" and l["action"] == "REQUEST_CHANGES"]
        assert len(change_logs) > 0
        assert "payroll spikes" in change_logs[0]["details"]
