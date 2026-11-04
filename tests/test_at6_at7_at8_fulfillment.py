"""Acceptance Tests AT-6, AT-7, and AT-8 for Sprint 4 (Fulfillment, Isolation & Verification)."""
import pytest
from fastapi.testclient import TestClient
from core.main import app, seed_initial_deal_if_empty
from core.database import reset_db, get_deal_spec, get_audit_logs, get_tenant
from core.schemas import DealState
from core.rate_limiter import tenant_rate_limiter


@pytest.fixture(autouse=True)
def setup_db():
    reset_db()
    seed_initial_deal_if_empty()
    tenant_rate_limiter.reset()


def prepare_accepted_v2_deal(client: TestClient):
    """Helper to transition deal to CUSTOMER_ACCEPTED."""
    client.post("/api/v1/admin/deals/acme-2026-11/counter")
    client.post("/api/v1/admin/deals/acme-2026-11/founder-approve")
    client.post("/api/v1/customer/proposal/acme/accept")


def test_at6_architect_denied_from_billing():
    """AT-6: @architect calling create_invoice is denied (HTTP 403) and logged to audit."""
    with TestClient(app) as client:
        prepare_accepted_v2_deal(client)

        # 1. Attempt call with caller="@architect"
        denied_resp = client.post(
            "/api/v1/agent-tools/create-invoice",
            json={"deal_id": "acme-2026-11", "caller": "@architect"},
        )
        assert denied_resp.status_code == 403
        assert "Privilege Isolation Violation (AT-6)" in denied_resp.json()["detail"]

        # 2. Attempt call with Header X-Agent-Role: architect
        denied_resp_header = client.post(
            "/api/v1/agent-tools/create-invoice",
            json={"deal_id": "acme-2026-11"},
            headers={"X-Agent-Role": "architect"},
        )
        assert denied_resp_header.status_code == 403

        # 3. Verify audit log entry exists with status=DENIED
        logs = get_audit_logs(deal_id="acme-2026-11")
        denied_logs = [l for l in logs if l["actor"] == "@architect" and l["status"] == "DENIED"]
        assert len(denied_logs) > 0, "Expected DENIED audit log entry for @architect"
        assert denied_logs[0]["action"] == "CREATE_INVOICE"


def test_at7_tenant_provisioning_and_rate_limiting():
    """AT-7: Tenant provisioned at 600 req/min. 601st request returns 429; /t/unknown returns 404."""
    with TestClient(app) as client:
        prepare_accepted_v2_deal(client)

        # 1. Unknown slug returns 404
        unknown_resp = client.get("/t/unknown")
        assert unknown_resp.status_code == 404
        assert "Tenant 'unknown' not found" in unknown_resp.json()["detail"]

        # 2. Provision tenant acme
        prov_resp = client.post("/api/v1/agent-tools/provision-tenant", json={"deal_id": "acme-2026-11"})
        assert prov_resp.status_code == 200
        assert prov_resp.json()["rate_limit_rpm"] == 600

        # Verify tenant record in DB
        tenant = get_tenant("acme")
        assert tenant is not None
        assert tenant["rate_limit_rpm"] == 600
        assert tenant["is_active"] == 1

        # 3. Simulate hitting /t/acme with rate limiter: 600 requests allowed, 601st blocked
        for i in range(600):
            r = client.get("/t/acme?format=json")
            assert r.status_code == 200, f"Request {i+1} should succeed"
            if i == 0:
                data = r.json()
                assert "Acme FinTech" in data["branding"]
                assert data["rate_limit_rpm"] == 600

        # 601st request in the 60s window must return HTTP 429
        over_limit_resp = client.get("/t/acme?format=json")
        assert over_limit_resp.status_code == 429, "601st request must return HTTP 429"
        error_data = over_limit_resp.json()
        assert error_data["error"] == "Rate limit exceeded"
        assert error_data["allocated_quota_rpm"] == 600


def test_at8_commercial_artifacts_match_dealspec_v2():
    """AT-8: Order Form PDF and invoice match DealSpec v2 (price, term, RPM, Net-15, waived fee)."""
    with TestClient(app) as client:
        prepare_accepted_v2_deal(client)
        client.post("/api/v1/agent-tools/provision-tenant", json={"deal_id": "acme-2026-11"})

        # 1. Render Order Form PDF
        pdf_resp = client.post("/api/v1/agent-tools/render-order-form", json={"deal_id": "acme-2026-11"})
        assert pdf_resp.status_code == 200
        pdf_filename = pdf_resp.json()["pdf_filename"]

        # Verify PDF file can be downloaded
        download_resp = client.get(f"/api/v1/documents/{pdf_filename}")
        assert download_resp.status_code == 200
        assert download_resp.headers["content-type"] == "application/pdf"
        assert len(download_resp.content) > 1000  # Non-trivial PDF size

        # 2. Create Stripe Invoice
        inv_resp = client.post("/api/v1/agent-tools/create-invoice", json={"deal_id": "acme-2026-11"})
        assert inv_resp.status_code == 200
        inv_data = inv_resp.json()

        # Assert DealSpec v2 attributes match invoice
        deal = get_deal_spec("acme-2026-11")
        assert inv_data["amount_usd"] == deal.commercial.price_usd_year == 22000.0
        assert inv_data["payment_terms"] == deal.commercial.payment_terms == "Net-15"
        assert deal.engineering.rate_limit_rpm == 600
        assert deal.commercial.setup_fee_waived is True
        assert inv_data["status"] == "success"
        assert inv_data["invoice_status"] == "ISSUED"
        assert "stripe.com" in inv_data["hosted_invoice_url"]
        assert deal.state == DealState.INVOICED
