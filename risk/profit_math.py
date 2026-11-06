"""Net profit after Delta paper costs.

A higher exit price is not a win until both taker fees and the adverse
exit fill are covered. The leftover is what compounds into the next size.
"""

TAKER_FEE_PCT = 0.0005
EXIT_SLIPPAGE_PCT = 0.0005
# Price move that clears entry fee, exit fee, and exit slippage, plus a remainder.
LOCK_PROFIT_PCT = 0.0030


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


def exit_adds_capital(
    entry: float,
    exit_mark: float,
    quantity: float,
    multiplier: float,
    is_short: bool,
) -> bool:
    return expected_net_pnl(entry, exit_mark, quantity, multiplier, is_short) > 0.0
