"""ReportLab PDF Generator for RelayOS Enterprise Order Forms."""
from pathlib import Path
from typing import Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from core.schemas import DealSpec

DOCS_DIR = Path(__file__).resolve().parent / "static" / "documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


def generate_order_form_pdf(spec: DealSpec) -> Path:
    """Generate a legal Order Form PDF from DealSpec using ReportLab.

    Returns:
        Path: Path to generated PDF file.
    """
    filename = f"order-form-{spec.deal_id}-v{spec.version}.pdf"
    pdf_path = DOCS_DIR / filename

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1E293B"),
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B"),
    )

    heading2_style = ParagraphStyle(
        "Heading2Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#334155"),
        spaceBefore=10,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "BodyCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )

    bold_label = ParagraphStyle(
        "BoldLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
    )

    elements = []

    # Header
    elements.append(Paragraph("RelayOS Enterprise Order Form", title_style))
    elements.append(Paragraph(f"Legally Binding Commercial Schedule · Order ID: OF-{spec.deal_id.upper()}-V{spec.version}", subtitle_style))
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#6366F1"), spaceAfter=15))

    # Parties Section
    parties_data = [
        [Paragraph("Provider:", bold_label), Paragraph("RelayOS Technologies, Inc.", body_style)],
        [Paragraph("Customer:", bold_label), Paragraph(f"<b>{spec.customer.name}</b> (Tenant Slug: <i>{spec.customer.slug}</i>)", body_style)],
        [Paragraph("Effective Date:", bold_label), Paragraph(spec.updated_at[:10], body_style)],
    ]
    parties_table = Table(parties_data, colWidths=[110, 420])
    parties_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(parties_table)
    elements.append(Spacer(1, 15))

    # Commercial Terms Table
    elements.append(Paragraph("1. Commercial Terms & Pricing", heading2_style))
    commercial_data = [
        [Paragraph("Item / Description", bold_label), Paragraph("Specification", bold_label), Paragraph("Billing Term", bold_label)],
        [Paragraph("Dedicated Enterprise Platform Subscription", body_style), Paragraph(f"${spec.commercial.price_usd_year:,.2f} USD / year", bold_label), Paragraph("Annual Prepaid", body_style)],
        [Paragraph("Dedicated Throughput Quota", body_style), Paragraph(f"<b>{spec.engineering.rate_limit_rpm:,} RPM</b> (Requests / Minute)", body_style), Paragraph("Included", body_style)],
        [Paragraph("Payment Terms", body_style), Paragraph(f"<b>{spec.commercial.payment_terms}</b>", bold_label), Paragraph("Standard Terms", body_style)],
        [Paragraph("Standard Onboarding & Setup Fee", body_style), Paragraph("<b>WAIVED</b> ($0.00)", bold_label), Paragraph("Waived", body_style)],
        [Paragraph("Custom White-Label Branding", body_style), Paragraph("Included (/t/acme)", body_style), Paragraph("Included", body_style)],
        [Paragraph("Custom ERP Tenant Adapter", body_style), Paragraph(spec.engineering.adapter, body_style), Paragraph("Delivered & Tested", body_style)],
    ]
    comm_table = Table(commercial_data, colWidths=[190, 220, 120])
    comm_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(comm_table)
    elements.append(Spacer(1, 15))

    # Terms & SLA Summary
    elements.append(Paragraph("2. Scope of Service & Deployment", heading2_style))
    elements.append(Paragraph(
        f"This Order Form authorizes RelayOS to provision a dedicated enterprise instance configured with the "
        f"<b>{spec.engineering.adapter}</b> adapter, routed exclusively through <b>/t/{spec.customer.slug}</b>. "
        f"The dedicated environment guarantees throughput capacity of up to <b>{spec.engineering.rate_limit_rpm} requests per minute</b> "
        f"with automated burst protection and 99.9% uptime SLA.",
        body_style,
    ))
    elements.append(Spacer(1, 15))

    # Signatures Table
    elements.append(Paragraph("3. Dual Human Signatures & Authorization", heading2_style))
    founder_sig = spec.approvals.founder.approved_by if spec.approvals.founder else "PENDING"
    founder_time = spec.approvals.founder.timestamp[:19] if spec.approvals.founder else "—"
    customer_sig = spec.approvals.customer.approved_by if spec.approvals.customer else "PENDING"
    customer_time = spec.approvals.customer.timestamp[:19] if spec.approvals.customer else "—"

    sig_data = [
        [Paragraph("Authorized RelayOS Founder:", bold_label), Paragraph("Authorized Acme FinTech Champion:", bold_label)],
        [Paragraph(f"Signature: <b>{founder_sig}</b>", body_style), Paragraph(f"Signature: <b>{customer_sig}</b>", body_style)],
        [Paragraph(f"Timestamp: {founder_time} UTC", body_style), Paragraph(f"Timestamp: {customer_time} UTC", body_style)],
        [Paragraph("Status: <b>VERIFIED & APPROVED</b>", bold_label), Paragraph("Status: <b>ACCEPTED & BOUND</b>", bold_label)],
    ]
    sig_table = Table(sig_data, colWidths=[265, 265])
    sig_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    return pdf_path
