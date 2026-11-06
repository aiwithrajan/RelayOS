"""RelayOS FastAPI Core Application."""
import json
import time
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, HTTPException, Request, Response, status, Header
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.database import (
    init_db,
    reset_db,
    save_deal_spec,
    get_deal_spec,
    get_all_deal_specs,
    get_audit_logs,
    log_audit,
    save_tenant,
    get_tenant,
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
from core.rate_limiter import tenant_rate_limiter
from core.pdf_generator import generate_order_form_pdf, DOCS_DIR
from core.mock_stripe import create_stripe_invoice

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


# --- HTML UI & Tenant Routes ---

@app.get("/god-mode", response_class=FileResponse)
def get_god_mode():
    """Serve the God-Mode Mission Control Dashboard."""
    template_path = TEMPLATES_DIR / "god_mode.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    return FileResponse(template_path)


@app.get("/t/{slug}")
def get_tenant_endpoint(slug: str, request: Request, format: Optional[str] = None):
    """Dynamic tenant routing at /t/{slug} enforcing rate limits & isolation (AT-7)."""
    tenant = get_tenant(slug)
    deal = get_deal_spec("acme-2026-11")

    # If slug is unknown and no tenant exists
    if not tenant and (not deal or deal.customer.slug != slug):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{slug}' not found",
        )

    # If tenant is provisioned, enforce rate limiting (AT-7)
    if tenant and tenant["is_active"]:
        allowed, count, limit = tenant_rate_limiter.is_allowed(slug, tenant["rate_limit_rpm"])
        if not allowed:
            return Response(
                content=json.dumps({
                    "error": "Rate limit exceeded",
                    "tenant": slug,
                    "allocated_quota_rpm": limit,
                    "current_requests_in_window": count,
                    "detail": f"429 Too Many Requests: Allocated quota of {limit} RPM reached.",
                }),
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
            )

        # Return active tenant payload if JSON requested
        if format == "json" or "application/json" in request.headers.get("accept", ""):
            return {
                "status": "online",
                "tenant": slug,
                "branding": "Acme FinTech White-Label",
                "rate_limit_rpm": tenant["rate_limit_rpm"],
                "adapter": tenant["adapter_file"],
                "requests_in_current_window": count,
            }

    # Otherwise serve customer proposal / portal
    template_path = TEMPLATES_DIR / "customer_portal.html"
    return FileResponse(template_path)


# --- Document Serving ---

@app.get("/api/v1/documents/{filename}")
def get_document(filename: str):
    """Download or view generated legal Order Form PDFs."""
    file_path = DOCS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")
    return FileResponse(file_path, media_type="application/pdf", filename=filename)


# --- Core REST API Routes ---

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


# --- Customer Endpoints ---

@app.get("/api/v1/customer/proposal/{slug}")
def get_customer_proposal(slug: str):
    deal = get_deal_spec("acme-2026-11")
    if not deal or deal.customer.slug != slug:
        raise HTTPException(status_code=404, detail=f"No active proposal found for '{slug}'")

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
        },
        "approvals": {
            "founder_approved": deal.approvals.founder is not None,
            "customer_approved": deal.approvals.customer is not None,
        },
    }


@app.post("/api/v1/customer/proposal/{slug}/accept")
def customer_accept_proposal(slug: str):
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


class CustomerChangeRequest(BaseModel):
    notes: Optional[str] = "Customer requested terms adjustment"
    requested_price: Optional[float] = None
    requested_rpm: Optional[int] = None


@app.post("/api/v1/customer/proposal/{slug}/request-changes")
def customer_request_changes_endpoint(slug: str, req: CustomerChangeRequest):
    """Log a change request from customer champion and notify Switch room."""
    deal = get_deal_spec("acme-2026-11")
    if not deal or deal.customer.slug != slug:
        raise HTTPException(status_code=404, detail=f"No active proposal for '{slug}'")

    details: Dict[str, Any] = {
        "notes": req.notes or "Revision requested",
        "channel": f"Switch deal room #{slug}-fintech-closing",
    }
    if req.requested_price is not None:
        details["requested_price"] = req.requested_price
    if req.requested_rpm is not None:
        details["requested_rpm"] = req.requested_rpm

    log_audit(
        deal_id=deal.deal_id,
        actor=f"{slug}_champion",
        action="REQUEST_CHANGES",
        status="SUBMITTED",
        details=details,
    )

    return {
        "status": "success",
        "message": f"Change request for {deal.customer.name} dispatched to Switch deal room #{slug}-fintech-closing.",
        "details": details,
    }


# --- Fulfillment Gated Endpoints & Privilege Isolation (AT-5, AT-6, AT-7, AT-8) ---

class DealActionRequest(BaseModel):
    deal_id: str
    caller: Optional[str] = None


def is_architect_caller(caller: Optional[str], x_agent_role: Optional[str]) -> bool:
    """Helper to detect @architect caller with or without @ prefix."""
    if x_agent_role and x_agent_role.lstrip("@").strip().lower() == "architect":
        return True
    if caller and caller.lstrip("@").strip().lower() == "architect":
        return True
    return False


@app.post("/api/v1/agent-tools/provision-tenant")
def provision_tenant_endpoint(req: DealActionRequest, x_agent_role: Optional[str] = Header(None)):
    """Provision tenant at /t/{slug}. Strictly requires CUSTOMER_ACCEPTED state (AT-5)."""
    if is_architect_caller(req.caller, x_agent_role):
        log_audit(
            deal_id=req.deal_id,
            actor="@architect",
            action="PROVISION_TENANT",
            status="DENIED",
            details={"reason": "Privilege isolation violation: @architect has no provisioning permissions (AT-6)"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privilege Isolation Violation (AT-6): @architect is forbidden from provisioning tenants.",
        )

    deal = get_deal_spec(req.deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    if deal.state not in [DealState.CUSTOMER_ACCEPTED, DealState.PROVISIONED, DealState.INVOICED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"State Gate Violation (AT-5): Cannot provision tenant when deal is in '{deal.state.value}'. Must be in 'CUSTOMER_ACCEPTED'.",
        )

    save_tenant(
        slug=deal.customer.slug,
        deal_id=deal.deal_id,
        name=deal.customer.name,
        rate_limit_rpm=deal.engineering.rate_limit_rpm,
        adapter_file=deal.engineering.adapter,
        white_label=deal.commercial.white_label,
        is_active=True,
    )

    if deal.state == DealState.CUSTOMER_ACCEPTED:
        deal.state = DealState.PROVISIONED
        save_deal_spec(deal)

    log_audit(
        deal_id=deal.deal_id,
        actor="@deal-desk",
        action="PROVISION_TENANT",
        status="SUCCESS",
        details={
            "slug": deal.customer.slug,
            "rate_limit_rpm": deal.engineering.rate_limit_rpm,
            "adapter": deal.engineering.adapter,
        },
    )

    return {
        "status": "success",
        "state": deal.state.value,
        "slug": deal.customer.slug,
        "tenant_url": f"/t/{deal.customer.slug}",
        "rate_limit_rpm": deal.engineering.rate_limit_rpm,
    }


@app.post("/api/v1/agent-tools/render-order-form")
def render_order_form_endpoint(req: DealActionRequest, x_agent_role: Optional[str] = Header(None)):
    """Render Order Form PDF using ReportLab (AT-8). Strictly requires CUSTOMER_ACCEPTED or PROVISIONED state (AT-5)."""
    if is_architect_caller(req.caller, x_agent_role):
        log_audit(
            deal_id=req.deal_id,
            actor="@architect",
            action="RENDER_ORDER_FORM",
            status="DENIED",
            details={"reason": "Privilege isolation: @architect has no document generation permissions (AT-6)"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privilege Isolation Violation (AT-6): @architect is forbidden from document tools.",
        )

    deal = get_deal_spec(req.deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    if deal.state not in [DealState.CUSTOMER_ACCEPTED, DealState.PROVISIONED, DealState.INVOICED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"State Gate Violation (AT-5): Cannot render Order Form PDF when deal is in '{deal.state.value}'. Must be in 'CUSTOMER_ACCEPTED'.",
        )

    pdf_path = generate_order_form_pdf(deal)

    log_audit(
        deal_id=deal.deal_id,
        actor="@deal-desk",
        action="RENDER_ORDER_FORM",
        status="SUCCESS",
        details={
            "deal_id": deal.deal_id,
            "version": deal.version,
            "pdf_path": str(pdf_path),
        },
    )

    return {
        "status": "success",
        "deal_id": deal.deal_id,
        "version": deal.version,
        "pdf_filename": pdf_path.name,
        "pdf_url": f"/api/v1/documents/{pdf_path.name}",
    }


@app.post("/api/v1/agent-tools/create-invoice")
def create_invoice_endpoint(req: DealActionRequest, x_agent_role: Optional[str] = Header(None)):
    """Create Stripe invoice (AT-6, AT-8). Strictly requires CUSTOMER_ACCEPTED or PROVISIONED state (AT-5)."""
    if is_architect_caller(req.caller, x_agent_role):
        log_audit(
            deal_id=req.deal_id,
            actor="@architect",
            action="CREATE_INVOICE",
            status="DENIED",
            details={"reason": "Privilege isolation violation (AT-6): @architect attempted unauthorized call to billing endpoint"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Privilege Isolation Violation (AT-6): @architect is strictly forbidden from billing and invoicing tools.",
        )

    deal = get_deal_spec(req.deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    if deal.state not in [DealState.CUSTOMER_ACCEPTED, DealState.PROVISIONED, DealState.INVOICED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"State Gate Violation (AT-5): Cannot create invoice when deal is in '{deal.state.value}'. Must be in 'CUSTOMER_ACCEPTED'.",
        )

    invoice_record = create_stripe_invoice(deal)

    deal.state = DealState.INVOICED
    save_deal_spec(deal)

    return {
        "status": "success",
        "state": deal.state.value,
        "invoice_id": invoice_record["invoice_id"],
        "customer_slug": invoice_record["customer_slug"],
        "amount_usd": invoice_record["amount_usd"],
        "payment_terms": invoice_record["payment_terms"],
        "invoice_status": invoice_record["status"],
        "hosted_invoice_url": invoice_record["hosted_invoice_url"],
        "pdf_url": invoice_record["pdf_url"],
    }


@app.get("/api/v1/admin/audit-logs")
def get_logs(deal_id: Optional[str] = None, limit: int = 50):
    return get_audit_logs(deal_id=deal_id, limit=limit)


@app.post("/api/v1/admin/reset")
def reset_system_endpoint():
    """Reset the database to clean baseline and re-seed the initial Acme deal (v1)."""
    reset_db()
    seed_initial_deal_if_empty()
    return {"status": "success", "message": "RelayOS state reset to v1 (Acme Initial Ask)"}

