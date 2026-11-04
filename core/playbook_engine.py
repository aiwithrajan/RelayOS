"""Deterministic Playbook Engine for RelayOS.

Evaluates DealSpec commercial terms against enterprise pricing playbook rules R1 through R5.
Zero LLM or hallucination risk.
"""
from typing import Dict, Tuple
from core.schemas import DealSpec, PlaybookResult

LIST_PRICE_USD_YEAR = 24000.0
MARGIN_FLOOR = 0.75  # 75%
MAX_UNAPPROVED_DISCOUNT = 0.10  # 10% ($21,600 floor)
MIN_PRICE_FOR_FEE_WAIVER = 20000.0
MIN_TERM_FOR_FEE_WAIVER = 12


def evaluate_playbook(spec: DealSpec) -> PlaybookResult:
    """Evaluate a DealSpec against rules R1 to R5.

    Returns:
        PlaybookResult containing calculated margin, rule verdicts, and overall pass/fail status.
    """
    price = spec.commercial.price_usd_year
    cost = spec.engineering.infra_cost_usd_year
    term_months = spec.commercial.term_months
    payment_terms = spec.commercial.payment_terms.strip().lower()
    setup_fee_waived = spec.commercial.setup_fee_waived
    white_label = spec.commercial.white_label

    # Compute gross margin
    if price <= 0:
        margin = 0.0
    else:
        margin = round((price - cost) / price, 4)

    rules: Dict[str, str] = {}

    # R1: Margin floor (>= 75%)
    if margin >= MARGIN_FLOOR:
        rules["R1"] = "pass"
    else:
        rules["R1"] = "fail"

    # R2: Discount authority (List price $24,000; up to 10% discount without exception, floor $21,600)
    discount_pct = (LIST_PRICE_USD_YEAR - price) / LIST_PRICE_USD_YEAR if LIST_PRICE_USD_YEAR > 0 else 0.0
    if price >= (LIST_PRICE_USD_YEAR * (1.0 - MAX_UNAPPROVED_DISCOUNT)):
        rules["R2"] = "pass"
    else:
        rules["R2"] = "fail"

    # R3: Setup fee ($2,500 standard; waived when price >= $20,000 and term >= 12 months)
    if not setup_fee_waived:
        rules["R3"] = "pass"
    else:
        if price >= MIN_PRICE_FOR_FEE_WAIVER and term_months >= MIN_TERM_FOR_FEE_WAIVER:
            rules["R3"] = "pass"
        else:
            rules["R3"] = "fail"

    # R4: Payment terms (Net-30 standard, Net-15 allowed without exception, Net-60 needs exception)
    if payment_terms in ["net-15", "net-30"]:
        rules["R4"] = "pass"
    else:
        rules["R4"] = "fail"

    # R5: White-label (Allowed on Enterprise tier)
    # Since RelayOS is an Enterprise tier sales workflow, white-label is allowed
    rules["R5"] = "pass"

    # Overall pass: all rules R1-R5 must pass
    all_passed = all(status == "pass" for status in rules.values())

    return PlaybookResult(
        margin=margin,
        rules=rules,
        passed=all_passed,
    )
