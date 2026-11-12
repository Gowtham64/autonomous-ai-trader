"""Local dashboard for the daily trend bot.

    .venv/bin/python run_trend_dashboard.py          # opens http://localhost:8787
    .venv/bin/python run_trend_dashboard.py --port 9000 --no-browser

Read-only: it only reads files the bot writes (data/daily_trend_status.json,
data/daily_trend_equity.csv, data/daily_trend_state.json and the trade journal in
data/trader.db). It never places or changes orders. Standard library only.
Bound to 127.0.0.1, so only this computer can open it.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sqlite3
import webbrowser
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

# 8-year backtest of the same rule (tools/backtest_trend_daily.py --source binance)
BACKTEST = {"win_rate": 41.2, "avg_r": 0.54, "avg_win_r": 2.32, "avg_loss_r": -0.71, "trades_per_month": 3.9}


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def _equity_points() -> list[tuple[str, float]]:
    p = DATA / "daily_trend_equity.csv"
    if not p.exists():
        return []
    out = []
    with open(p) as f:
        for row in csv.DictReader(f):
            try:
                out.append((row["time"], float(row["equity"])))
            except (KeyError, ValueError):
                continue
    return out


def _db_path() -> Path:
    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/trader.db")
    m = re.match(r"sqlite(\+\w+)?:///(.+)", url)
    path = Path(m.group(2)) if m else DATA / "trader.db"
    return path if path.is_absolute() else ROOT / path


def _closed_trades() -> list[dict]:
    db = _db_path()
    if not db.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT symbol, entry_price, exit_price, pnl, exit_reason, holding_period_seconds, "
            "reflection_notes, logged_at FROM trade_journal WHERE market_regime = 'DAILY_TREND' "
            "ORDER BY logged_at DESC LIMIT 500"
        ).fetchall()
        con.close()
    except Exception:
        return []
    out = []
    for sym, entry, exit_, pnl, reason, held, notes, logged in rows:
        r = re.search(r"\br=(-?[\d.]+)", notes or "")
        out.append({
            "symbol": sym, "entry": entry, "exit": exit_, "pnl": pnl, "reason": reason,
            "days": (held or 0) / 86400, "r": float(r.group(1)) if r else None, "closed": str(logged)[:16],
        })
    return out


# ---------------------------------------------------------------- formatting

def money(x: float | None, sign: bool = False) -> str:
    if x is None:
        return "—"
    s = f"{x:+,.2f}" if sign else f"{x:,.2f}"
    return ("+$" + s[1:] if s.startswith("+") else "−$" + s[1:]) if sign else "$" + s


def num(x: float | None) -> str:
    if x is None:
        return "—"
    if x == 0:
        return "0"
    return f"{x:.6g}" if abs(x) < 1 else f"{x:,.4f}".rstrip("0").rstrip(".")


def cls(x: float | None) -> str:
    return "pos" if (x or 0) > 0 else ("neg" if (x or 0) < 0 else "")


def esc(x) -> str:
    return html.escape(str(x))


def equity_svg(points: list[tuple[str, float]], start: float) -> str:
    if len(points) < 2:
        return '<p class="muted">The equity curve appears after the bot has run for a couple of hours.</p>'
    w, h, pad = 760, 250, 40
    vals = [v for _, v in points] + ([start] if start else [])
    lo, hi = min(vals), max(vals)
    vmin, vmax = lo, hi
    if hi - lo < 1e-9:
        hi, lo = hi + 1, lo - 1
    span = hi - lo
    lo, hi = lo - span * 0.08, hi + span * 0.08
    n = len(points)
    x = lambda i: pad + (w - 2 * pad) * i / (n - 1)  # noqa: E731
    y = lambda v: h - pad - (h - 2 * pad) * (v - lo) / (hi - lo)  # noqa: E731
    line = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(points))
    area = f"{x(0):.1f},{h - pad} {line} {x(n - 1):.1f},{h - pad}"
    base = ""
    if start:
        yb = y(start)
        base = (f'<line x1="{pad}" x2="{w - pad}" y1="{yb:.1f}" y2="{yb:.1f}" class="base"/>'
                f'<text x="{w - pad}" y="{yb - 5:.1f}" text-anchor="end" class="axis">start {money(start)}</text>')
    t0, t1 = points[0][0][:10], points[-1][0][:10]
    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Equity over time">'
        f'<polygon points="{area}" class="area"/><polyline points="{line}" class="line"/>{base}'
        f'<text x="{pad}" y="{h - 6}" class="axis">{esc(t0)}</text>'
        f'<text x="{w - pad}" y="{h - 6}" text-anchor="end" class="axis">{esc(t1)}</text>'
        f'<text x="{pad}" y="{pad - 14}" class="axis">range {money(vmin)} – {money(vmax)}</text></svg>'
    )


# -------------------------------------------------------------------- page

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#16181d;--muted:#667085;--line:#e4e7ec;--pos:#067647;--neg:#b42318;
--accent:#2e5bff;--accent-soft:rgba(46,91,255,.12);--warn-bg:#fffaeb;--warn:#b54708;--bad-bg:#fef3f2}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--ink:#e6e8ec;--muted:#98a2b3;--line:#2a2f3a;
--pos:#47cd89;--neg:#f97066;--accent:#7a9cff;--accent-soft:rgba(122,156,255,.16);--warn-bg:#2b2111;--warn:#fdb022;--bad-bg:#2d1513}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 48px}
header{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:baseline;justify-content:space-between;margin-bottom:16px}
h1{font-size:22px;margin:0}h2{font-size:15px;margin:0 0 12px;color:var(--muted);font-weight:600;letter-spacing:.02em}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.04em}
.paper{background:var(--accent-soft);color:var(--accent)}.live{background:var(--bad-bg);color:var(--neg)}
.muted{color:var(--muted)}.pos{color:var(--pos)}.neg{color:var(--neg)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
.grid .card{margin:0}.big{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums}
.alert{border-radius:10px;padding:12px 14px;margin-bottom:16px;background:var(--warn-bg);color:var(--warn)}
.alert.bad{background:var(--bad-bg);color:var(--neg)}
.scroll{overflow-x:auto}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}th{font-size:12px;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:0}
svg{width:100%;height:auto;display:block}.line{fill:none;stroke:var(--accent);stroke-width:2}
.area{fill:var(--accent-soft)}.base{stroke:var(--muted);stroke-dasharray:4 4}.axis{fill:var(--muted);font-size:13px}
@media (max-width:600px){.axis{font-size:24px}}
.trades td:nth-child(2),.trades th:nth-child(2){text-align:left}
.cmp td:nth-child(2),.cmp td:nth-child(3){width:28%}ul{margin:0;padding-left:18px}li{margin:2px 0}
footer{color:var(--muted);font-size:12px;margin-top:8px}
"""


def render() -> str:
    st = _read_json(DATA / "daily_trend_status.json")
    trades = _closed_trades()
    points = _equity_points()
    now = datetime.now(UTC)

    if not st:
        body = ('<div class="alert">No status yet. Start the bot (<code>./start_auto.sh</code>) — '
                'this page fills in after its first check.</div>')
        return page("Daily Trend", body)

    mode = st.get("mode", "PAPER")
    start = float(st.get("starting_capital") or 0.0)
    equity = float(st.get("equity") or 0.0)
    pnl = equity - start if start else None
    pnl_pct = (pnl / start * 100) if start else None
    updated = datetime.fromisoformat(st["updated_at"]) if st.get("updated_at") else None
    age_min = (now - updated).total_seconds() / 60 if updated else 1e9
    stale = age_min > 2.5 * float(st.get("poll_minutes") or 15)

    alerts = ""
    if stale:
        alerts += (f'<div class="alert bad"><b>The bot may be stopped.</b> Last check was {age_min:.0f} minutes ago '
                   f'(it checks every {st.get("poll_minutes", 15)}). Restart it with <code>./start_auto.sh</code>.</div>')
    if st.get("kill_switch"):
        alerts += f'<div class="alert bad"><b>Kill switch engaged</b> — no new trades: {esc(st["kill_switch"])}</div>'

    wins = [t for t in trades if (t["pnl"] or 0) > 0]
    rs = [t["r"] for t in trades if t["r"] is not None]
    total_net = sum(t["pnl"] or 0 for t in trades)
    win_rate = 100 * len(wins) / len(trades) if trades else None
    avg_r = sum(rs) / len(rs) if rs else None

    cards = f"""
<div class="grid">
  <div class="card"><h2>Equity</h2><div class="big">{money(equity)}</div>
    <div class="muted">started {money(start)}</div></div>
  <div class="card"><h2>Profit / loss</h2><div class="big {cls(pnl)}">{money(pnl, True)}</div>
    <div class="{cls(pnl)}">{"" if pnl_pct is None else f"{pnl_pct:+.2f}%"}</div></div>
  <div class="card"><h2>Drawdown from peak</h2><div class="big">{float(st.get("drawdown_pct") or 0):.1f}%</div>
    <div class="muted">halts new trades at 25%</div></div>
  <div class="card"><h2>Trades closed</h2><div class="big">{len(trades)}</div>
    <div class="muted">{len(st.get("positions") or [])} open now</div></div>
</div>"""

    pos_rows = "".join(
        f"<tr><td>{esc(p['symbol'])}</td><td>{esc('Long' if p['side'] == 'BUY' else 'Short')}</td><td>{p['qty']}</td>"
        f"<td>{num(p['entry'])}</td><td>{num(p.get('mark'))}</td><td>{num(p['stop'])}</td>"
        f"<td class='{cls(p['unrealized_usd'])}'>{money(p['unrealized_usd'], True)}</td>"
        f"<td class='{cls(p['locked_in_usd'])}'>{money(p['locked_in_usd'], True)}</td>"
        f"<td>{esc(str(p['opened_at'])[:10])}</td></tr>"
        for p in (st.get("positions") or [])
    )
    positions = (
        '<div class="card"><h2>Open positions</h2>'
        + ('<div class="scroll"><table><thead><tr><th>Coin</th><th>Side</th><th>Contracts</th><th>Entry</th>'
           '<th>Price now</th><th>Stop</th><th>Open P&amp;L</th><th>If stopped out</th><th>Opened</th></tr></thead>'
           f'<tbody>{pos_rows}</tbody></table></div>' if pos_rows else
           '<p class="muted">None. The bot waits for a coin to close above its 55-day high; '
           'weeks with no trades are normal.</p>')
        + "</div>"
    )

    def r_txt(r):
        return "—" if r is None else f"{r:+.2f}R"

    trade_rows = "".join(
        f"<tr><td>{esc(t['closed'])}</td><td>{esc(t['symbol'])}</td><td>{num(t['entry'])}</td><td>{num(t['exit'])}</td>"
        f"<td>{t['days']:.1f}</td><td>{esc(t['reason'].split(' ')[0])}</td>"
        f"<td class='{cls(t['r'])}'>{r_txt(t['r'])}</td>"
        f"<td class='{cls(t['pnl'])}'>{money(t['pnl'], True)}</td></tr>"
        for t in trades
    )
    closed = (
        '<div class="card"><h2>Closed trades</h2>'
        + ('<div class="scroll"><table class="trades"><thead><tr><th>Closed (UTC)</th><th>Coin</th><th>Entry</th><th>Exit</th>'
           '<th>Days</th><th>Why</th><th>Result</th><th>Net $</th></tr></thead>'
           f'<tbody>{trade_rows}</tbody></table></div>' if trade_rows else
           '<p class="muted">No closed trades yet.</p>')
        + "</div>"
    )

    def cmp_row(label, live, bt):
        return f"<tr><td>{label}</td><td>{live}</td><td>{bt}</td></tr>"

    compare = f"""
<div class="card"><h2>Live vs 8-year backtest</h2><div class="scroll"><table class="cmp">
<thead><tr><th></th><th>This bot so far</th><th>Backtest expectation</th></tr></thead><tbody>
{cmp_row("Win rate", "—" if win_rate is None else f"{win_rate:.0f}%", f"{BACKTEST['win_rate']:.0f}%")}
{cmp_row("Average result per trade", "—" if avg_r is None else f"<span class='{cls(avg_r)}'>{avg_r:+.2f}R</span>", f"+{BACKTEST['avg_r']:.2f}R")}
{cmp_row("Average win / loss", (f"{sum(r for r in rs if r > 0) / max(1, len([r for r in rs if r > 0])):+.2f}R / "
                                 f"{sum(r for r in rs if r <= 0) / max(1, len([r for r in rs if r <= 0])):+.2f}R") if rs else "—",
         f"+{BACKTEST['avg_win_r']:.2f}R / {BACKTEST['avg_loss_r']:.2f}R")}
{cmp_row("Total net", f"<span class='{cls(total_net)}'>{money(total_net, True)}</span>", "—")}
</tbody></table></div>
<p class="muted" style="margin:10px 0 0">R = profit ÷ the amount risked to the initial stop. With fewer than ~30 trades,
big differences from the backtest are normal and mean little; a 5–10 trade losing streak is expected.</p></div>"""

    lc = st.get("last_cycle") or {}
    notes = [*(f"Entered {x}" for x in lc.get("entries") or []), *(f"Closed {x}" for x in lc.get("exits") or []),
             *(f"Stop raised {x}" for x in lc.get("stops_moved") or []), *(lc.get("skipped") or [])]
    last = ('<div class="card"><h2>Last check</h2>'
            + (f"<ul>{''.join(f'<li>{esc(n)}</li>' for n in notes[:20])}</ul>" if notes else
               '<p class="muted">Nothing to do — no signals, no stops hit.</p>')
            + (f'<p class="muted" style="margin:10px 0 0">{esc(st["realized_edge"])}</p>' if st.get("realized_edge") else "")
            + "</div>")

    upd = updated.astimezone().strftime("%d %b %H:%M:%S") if updated else "—"
    body = f"""
<header><div><h1>Daily Trend Bot <span class="badge {'live' if mode == 'LIVE' else 'paper'}">{esc(mode)}</span></h1>
<div class="muted">{esc(st.get("rule", ""))} · risks {float(st.get("risk_pct") or 0) * 100:.0f}% per trade ·
{len(st.get("symbols") or [])} coin{"" if len(st.get("symbols") or []) == 1 else "s"}</div></div>
<div class="muted">Last check {esc(upd)} · decides once a day after 05:30 IST</div></header>
{alerts}{cards}
<div class="card"><h2>Equity over time</h2>{equity_svg(points, start)}</div>
{positions}{compare}{closed}{last}
<footer>Read-only view of the bot's files. Refreshes every minute. Last daily candle processed: {esc(st.get("last_daily_bar") or "—")}.</footer>"""
    return page("Daily Trend Bot", body)


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="refresh" content="60"><title>{esc(title)}</title><style>{CSS}</style></head>'
            f"<body><main>{body}</main></body></html>")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        try:
            out = render().encode()
            code = 200
        except Exception as e:  # show the problem instead of a blank page
            out = page("Error", f'<div class="alert bad">Dashboard error: {esc(e)}</div>').encode()
            code = 500
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):  # keep the terminal quiet
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://localhost:{a.port}"
    print(f"Daily Trend dashboard: {url}  (Ctrl+C to stop; the bot keeps running)")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
