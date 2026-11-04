"""Deterministic infrastructure cost model for RelayOS.

No LLMs or nondeterministic computations are used.
Formula:
    Annual dedicated-worker cost = $1,000 + $7 * (req/min)
"""


def estimate_infra_cost(rate_limit_rpm: int) -> float:
    """Calculate annual dedicated infrastructure cost in USD.

    Args:
        rate_limit_rpm: Allocated rate limit in requests per minute.

    Returns:
        float: Annual cost in USD.
    """
    if rate_limit_rpm < 0:
        raise ValueError("Rate limit RPM cannot be negative")

    base_cost = 1000.0
    rpm_multiplier = 7.0
    return float(base_cost + (rpm_multiplier * rate_limit_rpm))
