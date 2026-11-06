"""Deal state machine definitions and valid transition logic."""
from enum import Enum
from typing import Dict, Set


class DealState(str, Enum):
    DRAFT = "DRAFT"
    ENGINEERED = "ENGINEERED"
    PRICE_CHECKED = "PRICE_CHECKED"
    FOUNDER_APPROVED = "FOUNDER_APPROVED"
    CUSTOMER_ACCEPTED = "CUSTOMER_ACCEPTED"
    PROVISIONED = "PROVISIONED"
    INVOICED = "INVOICED"


# Allowed state transitions: from_state -> set of allowed to_states
VALID_TRANSITIONS: Dict[DealState, Set[DealState]] = {
    DealState.DRAFT: {DealState.ENGINEERED},
    DealState.ENGINEERED: {DealState.PRICE_CHECKED},
    # If price check passes or founder counters, can transition to FOUNDER_APPROVED or directly to CUSTOMER_ACCEPTED if compliant
    DealState.PRICE_CHECKED: {DealState.FOUNDER_APPROVED, DealState.CUSTOMER_ACCEPTED, DealState.ENGINEERED},
    # If customer rejects, can transition back to ENGINEERED with counter
    DealState.FOUNDER_APPROVED: {DealState.CUSTOMER_ACCEPTED, DealState.ENGINEERED},
    DealState.CUSTOMER_ACCEPTED: {DealState.PROVISIONED},
    DealState.PROVISIONED: {DealState.INVOICED},
    DealState.INVOICED: set(),  # Terminal state
}


def can_transition(current: DealState, target: DealState) -> bool:
    """Validate if a state transition is legal."""
    allowed = VALID_TRANSITIONS.get(current, set())
    return target in allowed
