"""Operator-adjustable risk settings for the daily trend engine, with hard limits.

Stored in data/daily_trend_risk.json. Both the terminal server (before accepting a
change) and the engine (before applying one) validate with `validate_changes`, so a
bad value can't reach trading even if one side is bypassed.

The STRATEGY RULE itself (55/20 breakout, 3xATR stop) is deliberately NOT editable
here: changing it would trade something the backtest never tested.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.config.settings import settings

# field -> (min, max, description)
LIMITS: dict[str, tuple[float, float, str]] = {
    "risk_pct": (0.001, 0.02, "Equity risked per trade (0.1%–2%). The backtest used 1%."),
    "max_positions": (1, 15, "Maximum open positions at once."),
    "max_drawdown_pct": (0.05, 0.40, "Drawdown from peak that halts new entries until reset (5%–40%)."),
    "max_daily_loss_pct": (0.01, 0.20, "Loss within one UTC day that pauses entries until the next day (1%–20%)."),
    "max_position_notional_pct": (0.05, 1.0, "Largest single position value as a share of equity (5%–100%)."),
}


@dataclass
class RiskConfig:
    risk_pct: float = field(default_factory=lambda: settings.DAILY_TREND_RISK_PCT)
    max_positions: int = field(default_factory=lambda: settings.DAILY_TREND_MAX_POSITIONS)
    max_drawdown_pct: float = field(default_factory=lambda: settings.DAILY_TREND_MAX_DRAWDOWN_PCT)
    max_daily_loss_pct: float = field(default_factory=lambda: settings.DAILY_TREND_MAX_DAILY_LOSS_PCT)
    max_position_notional_pct: float = field(default_factory=lambda: settings.DAILY_TREND_MAX_POSITION_NOTIONAL_PCT)
    entries_paused: bool = False
    disabled_symbols: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "RiskConfig":
        cfg = cls()
        p = Path(path)
        if p.exists():
            try:
                raw = json.loads(p.read_text())
                clean, _ = validate_changes(raw, list(settings.DAILY_TREND_SYMBOLS))
                for k, v in clean.items():
                    setattr(cfg, k, v)
            except Exception:
                pass  # a corrupt file must never loosen risk: defaults apply
        return cfg

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2))
        os.replace(tmp, p)

    def to_dict(self) -> dict:
        return asdict(self)


def validate_changes(changes: dict, known_symbols: list[str]) -> tuple[dict, list[str]]:
    """Return (accepted values, errors). Unknown fields and out-of-range values are errors."""
    ok: dict = {}
    errors: list[str] = []
    for k, v in (changes or {}).items():
        if k in LIMITS:
            lo, hi, _ = LIMITS[k]
            try:
                num = int(v) if k == "max_positions" else float(v)
            except (TypeError, ValueError):
                errors.append(f"{k}: not a number")
                continue
            if k == "max_positions" and float(v) != int(v):
                errors.append(f"{k}: must be a whole number")
                continue
            if not (lo <= num <= hi):
                errors.append(f"{k}: {num} is outside the allowed range {lo}–{hi}")
                continue
            ok[k] = num
        elif k == "entries_paused":
            if not isinstance(v, bool):
                errors.append("entries_paused: must be true or false")
                continue
            ok[k] = v
        elif k == "disabled_symbols":
            if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
                errors.append("disabled_symbols: must be a list of symbols")
                continue
            unknown = [s for s in v if s not in known_symbols]
            if unknown:
                errors.append(f"disabled_symbols: unknown {unknown}")
                continue
            ok[k] = sorted(set(v))
        else:
            errors.append(f"{k}: not an adjustable setting")
    return ok, errors
