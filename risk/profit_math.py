"""Net profit after Delta paper costs.

A higher exit price is not a win until both taker fees and the adverse
exit fill are covered. The leftover is what compounds into the next size.
"""

TAKER_FEE_PCT = 0.0005
EXIT_SLIPPAGE_PCT = 0.0005


def expected_net_pnl(
    entry: float,
    exit_mark: float,
    quantity: float,
    multiplier: float,
    is_short: bool,
) -> float:
    """Cash change of a market exit, including the fee already paid on entry."""
    if entry <= 0 or exit_mark <= 0 or quantity <= 0 or multiplier <= 0:
        return 0.0
    if is_short:
        fill = exit_mark * (1.0 + EXIT_SLIPPAGE_PCT)
        gross = (entry - fill) * quantity * multiplier
    else:
        fill = exit_mark * (1.0 - EXIT_SLIPPAGE_PCT)
        gross = (fill - entry) * quantity * multiplier
    entry_notional = entry * quantity * multiplier
    exit_notional = fill * quantity * multiplier
    return gross - (TAKER_FEE_PCT * entry_notional) - (TAKER_FEE_PCT * exit_notional)


def planned_risk_usd(entry: float, stop: float, quantity: float, multiplier: float) -> float:
    """Dollars the stop can lose before fees. A win must clear at least this much."""
    if entry <= 0 or stop <= 0 or quantity <= 0 or multiplier <= 0:
        return 0.0
    return abs(entry - stop) * quantity * multiplier


def price_that_pays(
    entry: float,
    quantity: float,
    multiplier: float,
    is_short: bool,
    min_net: float,
) -> float:
    """Mark price whose market exit leaves at least min_net after fees and slippage."""
    unit = quantity * multiplier
    if entry <= 0 or unit <= 0 or min_net <= 0:
        return entry
    fee = TAKER_FEE_PCT
    slip = EXIT_SLIPPAGE_PCT
    per_unit = min_net / unit
    if is_short:
        return (entry * (1.0 - fee) - per_unit) / ((1.0 + slip) * (1.0 + fee))
    return (per_unit + entry * (1.0 + fee)) / ((1.0 - slip) * (1.0 - fee))


def exit_pays_the_risk(
    entry: float,
    exit_mark: float,
    quantity: float,
    multiplier: float,
    is_short: bool,
    stop: float,
) -> bool:
    """A win has to put back at least the dollars the stop was willing to lose."""
    risk = planned_risk_usd(entry, stop, quantity, multiplier)
    if risk <= 0:
        return False
    return expected_net_pnl(entry, exit_mark, quantity, multiplier, is_short) >= risk
