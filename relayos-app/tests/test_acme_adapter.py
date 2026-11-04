"""Automated tests for Acme ERP Adapter executed by @architect."""
import sys
from pathlib import Path

app_dir = Path(__file__).resolve().parent.parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from acme_erp_adapter import AcmeERPAdapter


def test_acme_adapter_health():
    adapter = AcmeERPAdapter(tenant_slug="acme", rate_limit_rpm=600)
    health = adapter.health_check()
    assert health["status"] == "healthy"
    assert health["tenant"] == "acme"
    assert health["adapter"] == "acme_erp_adapter.py"
    assert health["rate_limit_rpm"] == 600


def test_acme_adapter_sync():
    adapter = AcmeERPAdapter(tenant_slug="acme", rate_limit_rpm=600)
    res = adapter.sync_records({"records": [{"id": 1, "ledger": "general"}]})
    assert res["status"] == "success"
    assert res["synced_count"] == 1
    assert res["rate_limit_rpm"] == 600
    assert res["erp_destination"] == "Acme-Treasury-SAP"
