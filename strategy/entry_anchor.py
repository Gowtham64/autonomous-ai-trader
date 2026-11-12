"""Keep stop and target tied to the price a trade is actually entered at.

Stops and targets are planned from the scan-time price, but the multi-agent debate
runs for minutes before the order goes out. Sending the old absolute levels with a
market order at a different price silently changes the risk and reward: a fill 1%
higher on a long turns a 1.5% stop into 2.5% and shrinks the target. These helpers
shift the plan to the real price and refuse setups that have already drifted.
"""

MAX_DRIFT_FRACTION_OF_STOP = 0.5


def reanchor_levels(
    planned_entry: float,
    stop_loss: float,
    target: float,
    fresh_price: float,
    is_short: bool,
    max_drift_fraction: float = MAX_DRIFT_FRACTION_OF_STOP,
) -> tuple[float, float, float] | None:
    """Return (entry, stop, target) shifted to fresh_price, or None if the setup is stale.

    The trade is skipped when price has moved more than `max_drift_fraction` of the
    stop distance away from the planned entry, in either direction: favorable drift
    means the move already happened (chasing), adverse drift means it is already failing.
    """
    if planned_entry <= 0 or fresh_price <= 0 or stop_loss <= 0 or target <= 0:
        return None
    stop_dist = abs(planned_entry - stop_loss)
    tgt_dist = abs(target - planned_entry)
    if stop_dist <= 0 or tgt_dist <= 0:
        return None
    if abs(fresh_price - planned_entry) > max_drift_fraction * stop_dist:
        return None
    if is_short:
        return fresh_price, fresh_price + stop_dist, fresh_price - tgt_dist
    return fresh_price, fresh_price - stop_dist, fresh_price + tgt_dist


def shift_levels_to_fill(
    reference_entry: float,
    stop_loss: float,
    target: float,
    fill_price: float,
) -> tuple[float, float]:
    """Move stop and target by the same amount the fill differed from the reference."""
    if reference_entry <= 0 or fill_price <= 0:
        return stop_loss, target
    delta = fill_price - reference_entry
    new_stop = stop_loss + delta if stop_loss and stop_loss > 0 else stop_loss
    new_target = target + delta if target and target > 0 else target
    return new_stop, new_target
