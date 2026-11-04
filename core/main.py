"""RelayOS FastAPI Core Application."""
import json
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, Optional, List

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
    ApprovalRecord,
    can_transition,
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


@app.get("/t/{slug}", response_class=FileResponse)
def get_tenant_portal(slug: str):
    """Serve the Customer Enterprise Portal for tenant."""
    template_path = TEMPLATES_DIR / "customer_portal.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Portal template not found")
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


@app.get("/api/v1/deals/{deal_id}/history", response_model=List[DealSpec])
def get_deal_history(deal_id: str):
    history = get_all_deal_specs(deal_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"No history for deal '{deal_id}'")
    return history


@app.get("/api/v1/deals/{deal_id}/diff")
def get_deal_diff(deal_id: str):
    """Return diff between v1 and v2 for comparison in God-Mode."""
    v1 = get_deal_spec(deal_id, version=1)
    v2 = get_deal_spec(deal_id, version=2)
    if not v1:
        raise HTTPException(status_code=404, detail="Version 1 not found")
    return {
        "deal_id": deal_id,
        "has_v2": v2 is not None,
        "v1": {
            "price": v1.commercial.price_usd_year,
            "rpm": v1.engineering.rate_limit_rpm,
            "infra_cost": v1.engineering.infra_cost_usd_year,
            "margin": v1.playbook.margin if v1.playbook else None,
            "payment_terms": v1.commercial.payment_terms,
            "setup_fee_waived": v1.commercial.setup_fee_waived,
            "state": v1.state.value,
        },
        "v2": {
            "price": v2.commercial.price_usd_year,
            "rpm": v2.engineering.rate_limit_rpm,
            "infra_cost": v2.engineering.infra_cost_usd_year,
            "margin": v2.playbook.margin if v2.playbook else None,
            "payment_terms": v2.commercial.payment_terms,
            "setup_fee_waived": v2.commercial.setup_fee_waived,
            "state": v2.state.value,
        } if v2 else None,
    }


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
        version=2,
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


@app.post("/api/v1/admin/deals/{deal_id}/founder-approve")
def founder_approve_deal(deal_id: str):
    """Founder approves the commercial terms (advances state to FOUNDER_APPROVED)."""
    deal = get_deal_spec(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    if not can_transition(deal.state, DealState.FOUNDER_APPROVED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition deal from {deal.state.value} to {DealState.FOUNDER_APPROVED.value}",
        )

    if not deal.playbook or not deal.playbook.passed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve deal: Playbook check has not passed",
        )

    deal.state = DealState.FOUNDER_APPROVED
    deal.approvals.founder = ApprovalRecord(
        approved_by="founder",
        timestamp=datetime.utcnow().isoformat(),
        notes=f"Founder approved commercial terms: ${deal.commercial.price_usd_year:,.0f}/yr at {deal.engineering.rate_limit_rpm} RPM",
    )
    save_deal_spec(deal)

    log_audit(
        deal_id=deal_id,
        actor="founder",
        action="APPROVE_FOUNDER",
        status="SUCCESS",
        details={
            "version": deal.version,
            "state": deal.state.value,
            "approved_by": "founder",
            "margin": deal.playbook.margin,
        },
    )
    return deal


# --- Customer Endpoints (Sanitized - Internal Margins Redacted) ---

@app.get("/api/v1/customer/proposal/{slug}")
def get_customer_proposal(slug: str):
    """Return sanitized customer proposal. Internal infra cost and margin are strictly redacted."""
    # Find active deal for slug
    deal = get_deal_spec("acme-2026-11")
    if not deal or deal.customer.slug != slug:
        raise HTTPException(status_code=404, detail=f"No active proposal found for '{slug}'")

    # Sanitize payload: strip infra_cost_usd_year and playbook metrics
    return {
        "deal_id": deal.deal_id,
        "version": deal.version,
        "state": deal.state.value,
        "customer": {
            "name": deal.customer.name,
            "slug": deal.customer.slug,
        },
        "commercial": {
            "price_usd_year": deal.commercial.price_usd_year,
            "term_months": deal.commercial.term_months,
            "payment_terms": deal.commercial.payment_terms,
            "setup_fee_waived": deal.commercial.setup_fee_waived,
            "white_label": deal.commercial.white_label,
        },
        "engineering": {
            "adapter": deal.engineering.adapter,
            "rate_limit_rpm": deal.engineering.rate_limit_rpm,
            # infra_cost_usd_year is intentionally redacted!
        },
        "approvals": {
            "founder_approved": deal.approvals.founder is not None,
            "customer_approved": deal.approvals.customer is not None,
        },
    }


@app.post("/api/v1/customer/proposal/{slug}/accept")
def customer_accept_proposal(slug: str):
    """Acme champion signs and accepts proposal (advances to CUSTOMER_ACCEPTED)."""
    deal = get_deal_spec("acme-2026-11")
    if not deal or deal.customer.slug != slug:
        raise HTTPException(status_code=404, detail=f"No active proposal for '{slug}'")

    if not can_transition(deal.state, DealState.CUSTOMER_ACCEPTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot accept deal in state '{deal.state.value}': Founder must approve the proposal first",
        )

    deal.state = DealState.CUSTOMER_ACCEPTED
    deal.approvals.customer = ApprovalRecord(
        approved_by=f"{slug}_champion",
        timestamp=datetime.utcnow().isoformat(),
        notes=f"Accepted by {deal.customer.name} champion",
    )
    save_deal_spec(deal)

    log_audit(
        deal_id=deal.deal_id,
        actor=f"{slug}_champion",
        action="ACCEPT_CUSTOMER",
        status="SUCCESS",
        details={
            "version": deal.version,
            "state": deal.state.value,
            "approved_by": f"{slug}_champion",
        },
    )
    return {
        "status": "success",
        "state": deal.state.value,
        "message": f"Proposal accepted by {deal.customer.name}. Tenant provisioning unlocked.",
    }


# --- Fulfillment Gated Endpoints (AT-5 Guardrails) ---

class DealActionRequest(BaseModel):
    deal_id: str


@app.post("/api/v1/agent-tools/provision-tenant")
def provision_tenant_endpoint(req: DealActionRequest):
    """Provision tenant at /t/{slug}. Strictly requires CUSTOMER_ACCEPTED state (AT-5)."""
    deal = get_deal_spec(req.deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    if deal.state != DealState.CUSTOMER_ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"State Gate Violation (AT-5): Cannot provision tenant when deal is in '{deal.state.value}'. Must be in 'CUSTOMER_ACCEPTED'.",
        )

    deal.state = DealState.PROVISIONED
    save_deal_spec(deal)
    log_audit(
        deal_id=deal.deal_id,
        actor="@deal-desk",
        action="PROVISION_TENANT",
        status="SUCCESS",
        details={"slug": deal.customer.slug, "rate_limit_rpm": deal.engineering.rate_limit_rpm},
    )
    return {
        "status": "success",
        "state": deal.state.value,
        "slug": deal.customer.slug,
        "tenant_url": f"/t/{deal.customer.slug}",
        "rate_limit_rpm": deal.engineering.rate_limit_rpm,
    }


@app.post("/api/v1/agent-tools/render-order-form")
def render_order_form_endpoint(req: DealActionRequest):
    """Render Order Form PDF. Strictly requires CUSTOMER_ACCEPTED or PROVISIONED state (AT-5)."""
    deal = get_deal_spec(req.deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    if deal.state not in [DealState.CUSTOMER_ACCEPTED, DealState.PROVISIONED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"State Gate Violation (AT-5): Cannot render Order Form PDF when deal is in '{deal.state.value}'. Must be in 'CUSTOMER_ACCEPTED'.",
        )

    log_audit(
        deal_id=deal.deal_id,
        actor="@deal-desk",
        action="RENDER_ORDER_FORM",
        status="SUCCESS",
        details={"deal_id": deal.deal_id, "version": deal.version},
    )
    return {
        "status": "success",
        "deal_id": deal.deal_id,
        "pdf_url": f"/api/v1/documents/order-form-{deal.deal_id}-v{deal.version}.pdf",
    }


@app.post("/api/v1/agent-tools/create-invoice")
def create_invoice_endpoint(req: DealActionRequest):
    """Create Stripe invoice. Strictly requires CUSTOMER_ACCEPTED or PROVISIONED state (AT-5)."""
    deal = get_deal_spec(req.deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    if deal.state not in [DealState.CUSTOMER_ACCEPTED, DealState.PROVISIONED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"State Gate Violation (AT-5): Cannot create invoice when deal is in '{deal.state.value}'. Must be in 'CUSTOMER_ACCEPTED'.",
        )

    deal.state = DealState.INVOICED
    save_deal_spec(deal)
    log_audit(
        deal_id=deal.deal_id,
        actor="@deal-desk",
        action="CREATE_INVOICE",
        status="SUCCESS",
        details={"amount": deal.commercial.price_usd_year, "terms": deal.commercial.payment_terms},
    )
    return {
        "status": "success",
        "state": deal.state.value,
        "invoice_id": f"in_mock_{deal.deal_id}_v{deal.version}",
        "amount_usd": deal.commercial.price_usd_year,
        "invoice_url": f"https://pay.stripe.com/invoice/mock_{deal.deal_id}",
    }


@app.get("/api/v1/admin/audit-logs")
def get_logs(deal_id: Optional[str] = None, limit: int = 50):
    return get_audit_logs(deal_id=deal_id, limit=limit)
