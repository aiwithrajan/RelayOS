"""FastMCP tools for @architect agent.

Scope:
- Works inside ./relayos-app
- Runs pytest
- Calls estimate_cost
- NO BILLING OR PROVISIONING TOOLS
"""
import subprocess
from pathlib import Path
from typing import Dict, Any
from core.cost_model import estimate_infra_cost

RELAYOS_APP_DIR = Path(__file__).resolve().parent.parent / "relayos-app"


def run_adapter_tests() -> Dict[str, Any]:
    """Execute pytest within ./relayos-app and report results."""
    cmd = ["pytest", str(RELAYOS_APP_DIR / "tests"), "-v"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "returncode": -1}


def estimate_cost_tool(rate_limit_rpm: int) -> Dict[str, Any]:
    """Estimate annual dedicated infrastructure cost deterministically."""
    cost = estimate_infra_cost(rate_limit_rpm)
    return {
        "rate_limit_rpm": rate_limit_rpm,
        "infra_cost_usd_year": cost,
        "formula": "$1,000 + ($7 * RPM)",
    }
