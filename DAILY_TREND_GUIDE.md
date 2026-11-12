# Daily Trend Strategy — Operating Guide

This is the only strategy in this repo with a backtested edge. The old hourly
scanner + AI debate bot lost money after costs in every test (-0.13R/trade over
~3,000 trades) and is no longer the default.

## The rule (fixed before testing — do not tune it on live results)

- **Enter long** when a completed daily close breaks the highest high of the previous 55 days.
- **Stop**: 3 × ATR(20) below the fill, trailing up from the best close. It only ever moves up.
- **Exit** when a completed daily close breaks the lowest low of the previous 20 days, or at the stop.
- **Risk**: 1% of current equity per trade, so position size compounds as equity grows or shrinks.
- **Universe**: 15 established coins (`DAILY_TREND_SYMBOLS`).

The code lives in `strategy/daily_trend.py` and is shared by the live engine
(`apps/daemon/daily_trend_engine.py`) and the backtest (`tools/backtest_trend_daily.py`).
A test drives the live engine through a year of days and checks it trades exactly the days the backtest does.

## What to expect (Binance history 2018–2026, as a proxy for Delta)

| | |
|---|---|
| Trades | 376 over 8 years (~4 a month across 15 coins) |
| Win rate | ~41%. Most trades are small losses; a few big trends pay for them |
| Average | +0.54R per trade, 95% CI [+0.26, +0.82] |
| $10 at 1% risk | $54.60 (+446%), worst drop 18% |
| 2022 crash | -8% (BTC -64%) |
| Since 2024 | roughly flat: 2024 +21%, 2025 -9%, 2026 +2% |

Caveats: the coin list is today's survivors (this flatters a long-only test), and the edge
has been weak since 2024. Holding BTC made more in total (+1,151%), with far deeper drops (~75%).
Expect months with no trades and losing streaks of 5–10 trades. That is normal for this strategy.

## Running it

```bash
python run_daily_trend.py --once   # one cycle, prints what it did
python run_daily_trend.py          # loop (checks every 15 minutes)
./start_auto.sh                    # supervisor; runs this strategy by default
```

It acts once a day, shortly after the daily candle closes (00:00 UTC = 05:30 IST).
Between closes it only watches stops. Logs go to `logs/daily_trend.log`.

### Paper first (default)

Unless all three of these are set in `.env`, the engine trades an **isolated $500 paper account**
(`DAILY_TREND_PAPER_CAPITAL`, stored in `data/daily_trend_paper_broker.json`):

```
TRADING_MODE=live
LIVE_TRADING_ENABLED=true
DAILY_TREND_ALLOW_LIVE=true
```

Run paper for **at least 2–3 months** before going live. Compare its trades with
`python tools/backtest_trend_daily.py --majors --source binance` over the same dates.

### Account size

A 1% risk with a ~12% stop means each position's value is about 8% of equity.
Below a few hundred dollars, most Delta contracts are too large to size correctly, and the
engine **skips** those trades rather than oversizing them. Check `logs/daily_trend.log` for
`account too small` messages. Realistic minimum: about $300.

## Safety

- **Exchange stop** (live): a stop order rests on Delta and moves up as the stop trails, so a crash or outage can't leave a position unprotected. The engine also checks stops every cycle.
- **Kill switch** (saved to disk, survives restarts):
  - a 25% drawdown halts new entries until you reset it;
  - a 6% daily loss halts entries for the rest of the UTC day.
  - Exits are always managed, even while halted.
  - To reset: `KILL_SWITCH_RESET_ON_START=1` for one start, or the CLI/API.
- **Realized-edge gate** (live): once 20+ daily-trend trades are closed, new live entries stop if their average net P&L is not positive. This uses only this strategy's own trades.
- **Stale signals**: no entries more than 6 hours after the daily close (e.g. after downtime).
- **Restarts**: all positions and stops are saved in `data/daily_trend_state.json`.

## Switching back to the old bot (not recommended)

Set `STRATEGY_MODE=hourly` in `.env`.
