"""End-to-End API and Walking Skeleton tests for Sprint 1."""
import pytest
from fastapi.testclient import TestClient
from core.main import app, seed_initial_deal_if_empty
from core.database import init_db


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
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


def test_audit_logs_contain_history():
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/audit-logs")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) > 0
        actions = [l["action"] for l in logs]
        assert "CHECK_PLAYBOOK" in actions
