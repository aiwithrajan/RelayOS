"""RelayOS FastAPI Core Application."""
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.database import (
    init_db,
    save_deal_spec,
    get_deal_spec,
    get_all_deal_specs,
    get_audit_logs,
    log_audit,
)
from core.schemas import (
    DealSpec,
    DealState,
    CustomerInfo,
    EngineeringSpec,
    CommercialSpec,
)
from core.cost_model import estimate_infra_cost
from core.playbook_engine import evaluate_playbook

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"


def seed_initial_deal_if_empty():
    """Seed Acme initial deal (v1 - Acme Ask) if not already present."""
    deal = get_deal_spec("acme-2026-11")
    if not deal:
        cost = estimate_infra_cost(1000)  # $8,000
        spec_v1 = DealSpec(
            deal_id="acme-2026-11",
            version=1,
            state=DealState.PRICE_CHECKED,
            customer=CustomerInfo(name="Acme FinTech", slug="acme"),
            engineering=EngineeringSpec(
                adapter="acme_erp_adapter.py",
                tests_passed=True,
                rate_limit_rpm=1000,
                infra_cost_usd_year=cost,
            ),
            commercial=CommercialSpec(
                price_usd_year=20000.0,
                term_months=12,
                payment_terms="Net-30",
                setup_fee_waived=False,
                white_label=True,
            ),
        )
        verdict = evaluate_playbook(spec_v1)
        spec_v1.playbook = verdict
        save_deal_spec(spec_v1)
        log_audit(
            deal_id="acme-2026-11",
            actor="@deal-desk",
            action="CHECK_PLAYBOOK",
            status="FAIL",
            details={
                "version": 1,
                "margin": verdict.margin,
                "rules": verdict.rules,
                "note": "Initial Acme ask fails R1 (margin 60.0% < 75%) and R2 (discount 16.7% > 10%)",
            },
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize SQLite DB and seed initial deal
    init_db()
    seed_initial_deal_if_empty()
    yield


app = FastAPI(
    title="RelayOS Core API",
    version="1.0.0",
    description="Autonomous Deal Closing Control Plane",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- HTML UI Routes ---

@app.get("/god-mode", response_class=FileResponse)
def get_god_mode():
    """Serve the God-Mode Mission Control Dashboard."""
    template_path = TEMPLATES_DIR / "god_mode.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    return FileResponse(template_path)


# --- API Routes ---

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "relay-os-core"}


@app.get("/api/v1/deals/{deal_id}", response_model=DealSpec)
def get_deal(deal_id: str, version: Optional[int] = None):
    deal = get_deal_spec(deal_id, version=version)
    if not deal:
        raise HTTPException(status_code=404, detail=f"Deal '{deal_id}' not found")
    return deal


@app.get("/api/v1/deals/{deal_id}/history")
def get_deal_history(deal_id: str):
    history = get_all_deal_specs(deal_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"No history for deal '{deal_id}'")
    return history


class CostEstimateRequest(BaseModel):
    rate_limit_rpm: int


@app.post("/api/v1/agent-tools/estimate-cost")
def estimate_cost_endpoint(req: CostEstimateRequest):
    cost = estimate_infra_cost(req.rate_limit_rpm)
    return {
        "rate_limit_rpm": req.rate_limit_rpm,
        "infra_cost_usd_year": cost,
        "formula": "$1,000 + ($7 * RPM)",
    }


@app.post("/api/v1/agent-tools/check-playbook")
def check_playbook_endpoint(spec: DealSpec):
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
    return updated_spec


@app.post("/api/v1/admin/deals/{deal_id}/counter")
def apply_founder_counter(deal_id: str):
    """Apply Founder Counter: $22k/yr, 600 RPM, Net-15, waived fee, white-label (creates DealSpec v2)."""
    current_deal = get_deal_spec(deal_id)
    if not current_deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    new_cost = estimate_infra_cost(600)  # $5,200
    spec_v2 = DealSpec(
        deal_id=deal_id,
        version=current_deal.version + 1,
        state=DealState.ENGINEERED,
        customer=current_deal.customer,
        engineering=EngineeringSpec(
            adapter="acme_erp_adapter.py",
            tests_passed=True,
            rate_limit_rpm=600,
            infra_cost_usd_year=new_cost,
        ),
        commercial=CommercialSpec(
            price_usd_year=22000.0,
            term_months=12,
            payment_terms="Net-15",
            setup_fee_waived=True,
            white_label=True,
        ),
    )

    verdict = evaluate_playbook(spec_v2)
    spec_v2.state = DealState.PRICE_CHECKED
    spec_v2.playbook = verdict
    save_deal_spec(spec_v2)

    log_audit(
        deal_id=deal_id,
        actor="founder",
        action="COUNTER_OFFER",
        status="SUCCESS",
        details={
            "version": spec_v2.version,
            "price": 22000.0,
            "rate_limit_rpm": 600,
            "margin": verdict.margin,
            "verdict": "PASS" if verdict.passed else "FAIL",
            "note": "Founder counter-offer passes R1-R5 at 76.4% margin",
        },
    )
    return spec_v2


@app.get("/api/v1/admin/audit-logs")
def get_logs(deal_id: Optional[str] = None, limit: int = 50):
    return get_audit_logs(deal_id=deal_id, limit=limit)
