# Production Readiness

**Status:** Paper-mode code is safer than the build currently described by the old audit notes. It is not cleared for live capital, and the Render service does not contain this patch until you deploy.

## Holds that are in place

- `LIVE_TRADING_ENABLED` defaults to false in `core/config/settings.py`.
- `render.yaml` sets `TRADING_MODE=PAPER`, `LIVE_TRADING_ENABLED=false`, and `EXCHANGE=DELTA`.
- Broker factory returns a paper adapter whenever live trading is off or mode is `PAPER`.
- Health check path is `/health`.
- One trading loop and a cycle lock reduce duplicate paper orders from the API process.
- The kill switch is no longer cleared by that loop.

## Blockers before any live enablement

1. Deploy is a separate decision. Do not treat this worktree as what `https://autonomous-ai-trader.onrender.com/` is running.
2. `AUTH_REQUIRED=false` leaves kill switch, daemon, and skill routes open on the public URL.
3. `OLLAMA_BRIDGE_TOKEN` is unset. The Mac bridge will get 403 until the token exists on both sides. Cloud models still run.
4. SQLite on Render's ephemeral disk loses orders and journals on restart. A persistent disk or Postgres is required if the journal must survive deploys.
5. Order rows are not foreign-keyed to decisions. Reconciliation is application-side.
6. `/api/market/trades` is Binance. Marks and candles are Delta. Do not mix those prints into fills.
7. Local `.env` can set `EXCHANGE` independently of `render.yaml`. A laptop process without `EXCHANGE=DELTA` scans the NSE universe. Render's blueprint value is DELTA.

## Rollback

These edits are application code. Rolling back the git commit and redeploying the previous image restores the old behavior, including the kill-switch reset and the seeded quotes. No database migration was applied, so there is no schema rollback. Paper JSON in git was restored after the local UI check and should match HEAD for `data/paper_broker_state.json` and `data/daily_risk_state.json`.

## Recommended next steps

1. Review this diff.
2. Set `OLLAMA_BRIDGE_TOKEN` if the Mac tunnel should be used.
3. Decide whether to set `AUTH_REQUIRED=true` and wire the dashboard token before the next public deploy.
4. Deploy only when you want Render to pick up the patch.
5. Keep live trading off until a paper window is reviewed on the deployed build, not only on this laptop.
