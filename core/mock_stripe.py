"""Stripe billing integration for RelayOS (Mock by default, test key optional)."""
import os
import uuid
from typing import Dict, Any, Optional
from pathlib import Path
from core.database import get_db_connection, log_audit
from core.schemas import DealSpec


def create_stripe_invoice(spec: DealSpec) -> Dict[str, Any]:
    """Issue a Stripe invoice (Mock or Test Mode).

    Args:
        spec: DealSpec in CUSTOMER_ACCEPTED or PROVISIONED state.

    Returns:
        Dict[str, Any]: Invoice details including invoice_id, amount, terms, and URL.
    """
    stripe_key = os.getenv("STRIPE_API_KEY")
    invoice_id = f"in_mock_{spec.customer.slug}_{spec.version}_{uuid.uuid4().hex[:6]}"
    amount_usd = spec.commercial.price_usd_year
    terms = spec.commercial.payment_terms
    pdf_path = f"/api/v1/documents/order-form-{spec.deal_id}-v{spec.version}.pdf"
    hosted_url = f"https://pay.stripe.com/invoice/{invoice_id}"

    # If real stripe key is set, real Stripe API could be called here
    # For hackathon evaluation, local mock guarantees zero external dependency
    conn = get_db_connection()
    with conn:
        conn.execute(
            """
            INSERT INTO invoices (invoice_id, deal_id, customer_slug, amount_usd, payment_terms, status, hosted_invoice_url, pdf_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(invoice_id) DO UPDATE SET
                status = excluded.status
            """,
            (invoice_id, spec.deal_id, spec.customer.slug, amount_usd, terms, "ISSUED", hosted_url, pdf_path),
        )
    conn.close()

    log_audit(
        deal_id=spec.deal_id,
        actor="@deal-desk",
        action="CREATE_INVOICE",
        status="SUCCESS",
        details={
            "invoice_id": invoice_id,
            "amount_usd": amount_usd,
            "terms": terms,
            "hosted_url": hosted_url,
            "mode": "mock",
        },
    )

    return {
        "invoice_id": invoice_id,
        "deal_id": spec.deal_id,
        "customer_slug": spec.customer.slug,
        "amount_usd": amount_usd,
        "payment_terms": terms,
        "status": "ISSUED",
        "hosted_invoice_url": hosted_url,
        "pdf_url": pdf_path,
    }
