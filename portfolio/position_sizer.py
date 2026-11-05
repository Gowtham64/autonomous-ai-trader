import json
import os
from core.config.settings import settings
from core.logging import logger
from core.schemas.trade import RiskCheckResult, TradeDecision


DELTA_CONTRACT_MULTIPLIERS = {
    "BTC": 0.001,
    "ETH": 0.01,
    "SOL": 1.0,
    "DOGE": 100.0,
    "AVAX": 1.0,
    "LINK": 1.0,
    "NEAR": 1.0,
    "SUI": 1.0,
    "XRP": 1.0,
    "ADA": 1.0,
    "TAO": 0.01,
    "BNB": 0.1,
    "OP": 0.1,
    "AUCTION": 0.1,
    "ORDI": 0.1,
    "LTC": 0.1,
    "ZEC": 0.1,
    "TRB": 0.1,
    "BCH": 0.01,
    "XMR": 0.01,
    "1000PEPE": 1000.0,
    "1000BONK": 1000.0,
    "1000FLOKI": 100.0,
    "1000SHIB": 1000.0,
    "1000SATS": 1000.0,
    "DOGS": 1000.0,
    "NOT": 100.0,
    "PEOPLE": 100.0,
    "NEIRO": 1000.0,
    "JASMY": 100.0,
    "GALA": 100.0,
    "SEI": 10.0,
    "JUP": 10.0,
    "STRK": 100.0,
    "POL": 10.0,
    "ZK": 10.0,
    "AXS": 10.0,
    "ONDO": 10.0,
}

# Dynamically loaded comprehensive product catalog from Delta API (/v2/products)
_DYNAMIC_DELTA_MULTIPLIERS: dict[str, float] = {}
_MULTIPLIERS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "delta_contract_multipliers.json")
try:
    if os.path.exists(_MULTIPLIERS_PATH):
        with open(_MULTIPLIERS_PATH) as f:
            _DYNAMIC_DELTA_MULTIPLIERS = json.load(f)
except Exception as _e:
    logger.warning(f"[PositionSizer] Could not load dynamic contract multipliers: {_e}")


def get_delta_contract_multiplier(symbol: str) -> float | None:
    """Resolves exact contract value / multiplier for any Delta Exchange derivative.
    Returns None if the asset specification cannot be verified from the exchange.
    """
    sym_raw = symbol.upper().strip()
    sym_clean = sym_raw.replace("USDT", "").replace("USD", "").replace(".NS", "").replace(".BO", "")
    if sym_raw in _DYNAMIC_DELTA_MULTIPLIERS:
        return float(_DYNAMIC_DELTA_MULTIPLIERS[sym_raw])
    if sym_clean in _DYNAMIC_DELTA_MULTIPLIERS:
        return float(_DYNAMIC_DELTA_MULTIPLIERS[sym_clean])
    if sym_clean in DELTA_CONTRACT_MULTIPLIERS:
        return float(DELTA_CONTRACT_MULTIPLIERS[sym_clean])
    return None


class PositionSizer:
    """Calculates deterministic order quantities based on ATR volatility, stop loss distance, and capital caps."""

    def __init__(self, total_equity: float = settings.MAX_CAPITAL, available_margin: float | None = None):
        self.total_equity = total_equity
        self.available_margin = available_margin if available_margin is not None else total_equity

    def calculate_quantity(
        self,
        decision: TradeDecision,
        risk_result: RiskCheckResult,
    ) -> int:
        if not risk_result.approved or decision.entry_price is None or decision.stop_loss is None:
            return 0

        is_crypto = (decision.exchange and decision.exchange.upper() in ["DELTA", "CRYPTO"]) or ("USD" in decision.symbol.upper())
        if is_crypto:
            resolved_mult = get_delta_contract_multiplier(decision.symbol)
            if resolved_mult is None or resolved_mult <= 0:
                logger.warning(f"🛡️ [PositionSizer Zero-Trust] Rejecting {decision.symbol}: Contract specification unverified on Delta Exchange.")
                return 0
            contract_mult = resolved_mult
        else:
            contract_mult = 1.0
        
        # Effective capital/margin per 1 unit (using dynamically configured safe leverage on crypto, 1x on equity)
        crypto_lev = getattr(settings, "DELTA_MAX_LEVERAGE", 5.0)
        effective_unit_cost = ((decision.entry_price * contract_mult) / crypto_lev) if is_crypto else decision.entry_price

        # Available margin for new positions
        avail = getattr(self, "available_margin", None)
        if avail is None or avail <= 0:
            avail = self.total_equity

        # 1. Standard Risk-based Sizing: Risk Amount / Stop Loss Distance
        # Micro accounts get a modest bump over the configured risk, not a 4x-8x one:
        # 4% risk with a 45% exposure cap at 5x leverage was compounding losses fast.
        is_micro_crypto = is_crypto and self.total_equity < 25.0
        risk_pct = max(settings.MAX_RISK_PER_TRADE_PCT, 0.015) if is_micro_crypto else settings.MAX_RISK_PER_TRADE_PCT
        risk_amount = self.total_equity * risk_pct
        stop_distance = abs(decision.entry_price - decision.stop_loss) * contract_mult

        if stop_distance <= 0:
            logger.warning("Stop distance is zero or negative; quantity is 0")
            return 0

        raw_quantity = int(risk_amount / stop_distance) if stop_distance > 0 else 1

        # 2. Maximum Capital Cap (20% on micro crypto accounts; 45% per position left no
        # room for diversification and let 2-3 positions consume the whole account)
        max_cap_pct = 0.20 if is_micro_crypto else settings.MAX_SINGLE_STOCK_EXPOSURE_PCT
        max_capital_for_asset = min(self.total_equity * max_cap_pct, avail * 0.95)
        max_qty_by_capital = int(max_capital_for_asset / effective_unit_cost) if effective_unit_cost > 0 else 0

        # 3. Handle bootstrap / small capital constraints
        curr_sym = "$" if is_crypto else "₹"
        unit_type = "contracts" if is_crypto else "shares"

        if effective_unit_cost > avail:
            logger.warning(
                f"Required margin {curr_sym}{effective_unit_cost:.2f} exceeds available margin {curr_sym}{avail:.2f}; cannot size trade {decision.symbol}."
            )
            return 0

        # Safety Check: Prevent taking a trade if the risk on 1 unit exceeds maximum acceptable account risk
        max_acceptable_trade_risk = max(risk_amount, self.total_equity * (0.06 if is_micro_crypto else 0.035))
        if stop_distance > max_acceptable_trade_risk:
            logger.warning(
                f"Trade risk for 1 unit ({curr_sym}{stop_distance:.2f}) exceeds maximum acceptable account risk "
                f"({curr_sym}{max_acceptable_trade_risk:.2f}) on total equity {curr_sym}{self.total_equity:.2f}. "
                f"Rejecting trade on high-risk/high-priced asset {decision.symbol} to protect capital."
            )
            return 0

        # If 1 unit fits within total capital, allow 1 unit for testing/bootstrap if risk cap permits
        if max_qty_by_capital == 0 and effective_unit_cost <= max_capital_for_asset:
            max_qty_by_capital = 1

        final_quantity = min(raw_quantity, max_qty_by_capital)
        if final_quantity <= 0:
            if effective_unit_cost <= avail and stop_distance <= max_acceptable_trade_risk:
                final_quantity = 1

        logger.info(
            f"Position Sizer: Total Eq {curr_sym}{self.total_equity:.2f}, Risk Amount {curr_sym}{risk_amount:.2f}, "
            f"Stop Dist {curr_sym}{stop_distance:.2f} -> Sized Quantity: {final_quantity} {unit_type} "
            f"(Margin: {curr_sym}{final_quantity * effective_unit_cost:.2f})"
        )
        return final_quantity
