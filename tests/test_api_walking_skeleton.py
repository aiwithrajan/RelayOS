"""End-to-End API and Walking Skeleton tests for Sprint 1 & Sprint 2."""
import pytest
from fastapi.testclient import TestClient
from core.main import app, seed_initial_deal_if_empty
from core.database import reset_db


@pytest.fixture(autouse=True)
def setup_db():
    reset_db()
    seed_initial_deal_if_empty()


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "relay-os-core"}


def test_god_mode_ui_serves():
    with TestClient(app) as client:
        response = client.get("/god-mode")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "RelayOS" in response.text
        assert "God-Mode" in response.text


def test_get_deal_v1_failing_ask():
    with TestClient(app) as client:
        response = client.get("/api/v1/deals/acme-2026-11")
        assert response.status_code == 200
        data = response.json()
        assert data["deal_id"] == "acme-2026-11"
        assert data["version"] == 1
        assert data["commercial"]["price_usd_year"] == 20000.0
        assert data["engineering"]["rate_limit_rpm"] == 1000
        assert data["engineering"]["infra_cost_usd_year"] == 8000.0
        assert data["playbook"]["margin"] == 0.6  # 60.0%
        assert data["playbook"]["passed"] is False
        assert data["playbook"]["rules"]["R1"] == "fail"
        assert data["playbook"]["rules"]["R2"] == "fail"


def test_estimate_cost_api():
    with TestClient(app) as client:
        resp1000 = client.post("/api/v1/agent-tools/estimate-cost", json={"rate_limit_rpm": 1000})
        assert resp1000.status_code == 200
        assert resp1000.json()["infra_cost_usd_year"] == 8000.0

        resp600 = client.post("/api/v1/agent-tools/estimate-cost", json={"rate_limit_rpm": 600})
        assert resp600.status_code == 200
        assert resp600.json()["infra_cost_usd_year"] == 5200.0


def test_founder_counter_transition_to_v2():
    with TestClient(app) as client:
        response = client.post("/api/v1/admin/deals/acme-2026-11/counter")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 2
        assert data["commercial"]["price_usd_year"] == 22000.0
        assert data["engineering"]["rate_limit_rpm"] == 600
        assert data["engineering"]["infra_cost_usd_year"] == 5200.0
        assert abs(data["playbook"]["margin"] - 0.764) < 0.001
        assert data["playbook"]["passed"] is True
        assert data["playbook"]["rules"]["R1"] == "pass"
        assert data["playbook"]["rules"]["R2"] == "pass"
        assert data["playbook"]["rules"]["R3"] == "pass"
        assert data["playbook"]["rules"]["R4"] == "pass"
        assert data["playbook"]["rules"]["R5"] == "pass"


def test_deal_diff_endpoint():
    with TestClient(app) as client:
        # Before counter: only v1 exists
        diff_resp = client.get("/api/v1/deals/acme-2026-11/diff")
        assert diff_resp.status_code == 200
        data = diff_resp.json()
        assert data["v1"]["price"] == 20000.0
        assert data["v1"]["rpm"] == 1000

        # Apply counter
        client.post("/api/v1/admin/deals/acme-2026-11/counter")

        # After counter: v1 and v2 exist
        diff_resp2 = client.get("/api/v1/deals/acme-2026-11/diff")
        assert diff_resp2.status_code == 200
        data2 = diff_resp2.json()
        assert data2["has_v2"] is True
        assert data2["v2"]["price"] == 22000.0
        assert data2["v2"]["rpm"] == 600


def test_founder_approval_flow():
    with TestClient(app) as client:
        # Attempt to approve failing v1 should fail
        fail_app = client.post("/api/v1/admin/deals/acme-2026-11/founder-approve")
        assert fail_app.status_code == 400
        assert "Playbook check has not passed" in fail_app.json()["detail"]

        # Apply counter (v2)
        counter_resp = client.post("/api/v1/admin/deals/acme-2026-11/counter")
        assert counter_resp.status_code == 200

        # Approve v2
        approve_resp = client.post("/api/v1/admin/deals/acme-2026-11/founder-approve")
        assert approve_resp.status_code == 200
        approved_deal = approve_resp.json()
        assert approved_deal["state"] == "FOUNDER_APPROVED"
        assert approved_deal["approvals"]["founder"] is not None
        assert approved_deal["approvals"]["founder"]["approved_by"] == "founder"

        # Check audit log contains APPROVE_FOUNDER
        logs_resp = client.get("/api/v1/admin/audit-logs")
        assert logs_resp.status_code == 200
        actions = [l["action"] for l in logs_resp.json()]
        assert "APPROVE_FOUNDER" in actions
