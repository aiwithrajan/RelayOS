"""FastMCP tools for @deal-desk agent.

Scope:
- Evaluates pricing playbook rules R1 to R5
- Provisioning, PDF rendering, invoice creation (Strictly gated by deal state)
- NO CODE MODIFICATION ACCESS TO ./relayos-app
"""
from typing import Dict, Any, Optional
from core.playbook_engine import evaluate_playbook
from core.schemas import DealSpec, DealState
from core.database import get_deal_spec, save_deal_spec, log_audit


def check_playbook_tool(spec: DealSpec) -> Dict[str, Any]:
    """Execute deterministic pricing playbook checks citing rules R1 through R5."""
    verdict = evaluate_playbook(spec)
    updated_spec = spec.model_copy(deep=True)
    updated_spec.state = DealState.PRICE_CHECKED
    updated_spec.playbook = verdict
    save_deal_spec(updated_spec)

    log_audit(
        deal_id=spec.deal_id,
        actor="@deal-desk",
        action="CHECK_PLAYBOOK",
        status="PASS" if verdict.passed else "FAIL",
        details={
            "version": spec.version,
            "margin": verdict.margin,
            "rules": verdict.rules,
            "passed": verdict.passed,
        },
    )

    return {
        "deal_id": updated_spec.deal_id,
        "version": updated_spec.version,
        "state": updated_spec.state.value,
        "margin": verdict.margin,
        "margin_percent": f"{verdict.margin * 100:.1f}%",
        "rules": verdict.rules,
        "passed": verdict.passed,
    }
