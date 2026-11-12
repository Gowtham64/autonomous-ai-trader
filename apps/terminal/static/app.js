/* Daily Trend trading terminal. All data comes from the terminal API (/api/*), which reads the
   engine's records and live Delta prices. Actions are queued for the engine; nothing is shown as
   done until the engine reports the broker's answer. */
"use strict";

const TOKEN = document.querySelector('meta[name="terminal-token"]').content;
window.addEventListener("error", (e) => toast(`UI error: ${e.message}`, "bad"));
window.addEventListener("unhandledrejection", (e) => toast(`UI error: ${e.reason?.message || e.reason}`, "bad"));
const S = { state: null, view: "overview", markets: null, analytics: null, orders: [], risk: null, strategy: null,
  system: null, pending: {}, chartSym: null, chartTf: "1d", hiGroup: "monthly", sort: {}, chat: [], streamOk: false };
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

/* ------------------------------------------------------------------ utils */
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const isNum = (x) => typeof x === "number" && isFinite(x);
function px(x) { if (!isNum(x)) return "—"; const a = Math.abs(x);
  return a >= 1000 ? x.toLocaleString(undefined, { maximumFractionDigits: 2 }) : a >= 1 ? x.toFixed(4).replace(/\.?0+$/, "") || "0" : x.toPrecision(5); }
function usd(x, sign = false) { if (!isNum(x)) return "—"; const s = Math.abs(x).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: Math.abs(x) < 1 ? 4 : 2 });
  return (x < 0 ? "−$" : sign && x > 0 ? "+$" : "$") + s; }
const pct = (x, d = 2, sign = true) => isNum(x) ? `${sign && x > 0 ? "+" : ""}${x.toFixed(d)}%` : "—";
const rr = (x) => isNum(x) ? `${x > 0 ? "+" : ""}${x.toFixed(2)}R` : "—";
const cls = (x) => isNum(x) ? (x > 0 ? "up" : x < 0 ? "down" : "") : "";
const big = (x) => { if (!isNum(x)) return "—"; const a = Math.abs(x);
  return a >= 999.5e6 ? (x / 1e9).toFixed(2) + "B" : a >= 999.95e3 ? (x / 1e6).toFixed(2) + "M" : a >= 1e3 ? (x / 1e3).toFixed(1) + "K" : x.toFixed(0); };
function ago(s) { if (!isNum(s)) return "—"; if (s < 90) return `${Math.round(s)}s`; if (s < 5400) return `${Math.round(s / 60)}m`; if (s < 172800) return `${(s / 3600).toFixed(1)}h`; return `${(s / 86400).toFixed(1)}d`; }
function when(iso) { if (!iso) return "—"; const d = new Date(iso); return isNaN(d) ? esc(iso) : d.toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }); }
const dur = (h) => !isNum(h) ? "—" : h < 48 ? `${h.toFixed(1)}h` : `${(h / 24).toFixed(1)}d`;

async function api(path, opts = {}) {
  const res = await fetch(path, { ...opts, headers: { "Content-Type": "application/json", "X-Terminal-Token": TOKEN, ...(opts.headers || {}) } });
  let body; try { body = await res.json(); } catch { body = { error: `HTTP ${res.status}` }; }
  if (!res.ok) { const e = new Error(body.error || `HTTP ${res.status}`); e.status = res.status; throw e; }
  return body;
}
function toast(msg, kind = "") { const t = document.createElement("div"); t.className = `toast ${kind}`; t.textContent = msg;
  $("#toasts").appendChild(t); setTimeout(() => t.remove(), kind === "bad" ? 12000 : 7000); }

/* sortable table helper: cols = [{k, label, l (left), fmt(row)->html, sort(row)->value}] */
function table(el, id, cols, rows, opts = {}) {
  const st = S.sort[id] || (S.sort[id] = { k: opts.sortKey || null, dir: opts.sortDir || -1 });
  let data = rows.slice();
  if (st.k) { const c = cols.find((c) => c.k === st.k); const f = c?.sort || ((r) => r[st.k]);
    data.sort((a, b) => { const x = f(a), y = f(b); if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * st.dir; }); }
  const head = cols.map((c) => `<th class="${c.l ? "l " : ""}${c.stick ? "stick " : ""}${c.nosort ? "" : "sortable"} ${st.k === c.k ? (st.dir > 0 ? "sorted-asc" : "sorted-desc") : ""}" data-k="${c.k}">${esc(c.label)}</th>`).join("");
  const body = data.length ? data.map((r, i) => {
    const row = `<tr data-i="${i}">${cols.map((c) => `<td class="${c.l ? "l " : ""}${c.stick ? "stick " : ""}${c.txt ? "txt" : ""}">${c.fmt ? c.fmt(r) : esc(r[c.k] ?? "—")}</td>`).join("")}</tr>`;
    return row + (opts.expand && opts.expanded?.(r) ? `<tr class="expand"><td colspan="${cols.length}">${opts.expand(r)}</td></tr>` : "");
  }).join("") : `<tr><td colspan="${cols.length}" class="empty">${esc(opts.empty || "Nothing yet.")}</td></tr>`;
  el.innerHTML = `<thead><tr>${head}</tr></thead><tbody>${body}</tbody>`;
  $$("th.sortable", el).forEach((th) => th.onclick = () => { const k = th.dataset.k; st.dir = st.k === k ? -st.dir : -1; st.k = k; table(el, id, cols, rows, opts); });
  opts.after?.(el, data);
}

/* ------------------------------------------------------------- navigation */
function show(view) {
  S.view = view; location.hash = view;
  $$("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  $$("section.view").forEach((s) => s.classList.toggle("active", s.id === `view-${view}`));
  refreshView(true);
}
$$("#nav button").forEach((b) => b.onclick = () => show(b.dataset.view));

async function refreshView(first = false) {
  try {
    if (S.view === "overview") renderOverview();
    else if (S.view === "positions") renderPositions();
    else if (S.view === "markets") await loadMarkets();
    else if (S.view === "chart") await loadChart(first);
    else if (S.view === "orders") await loadOrders();
    else if (S.view === "history") await loadHistory();
    else if (S.view === "risk") await loadRisk();
    else if (S.view === "strategy") await loadStrategy();
    else if (S.view === "system") await loadSystem();
    else if (S.view === "assistant" && first) renderChat();
  } catch (e) { toast(`Could not load ${S.view}: ${e.message}`, "bad"); }
}

/* ----------------------------------------------------------- live stream */
function connect() {
  const es = new EventSource("/api/stream");
  es.addEventListener("state", (ev) => { S.streamOk = true; onState(JSON.parse(ev.data)); });
  es.onopen = () => { S.streamOk = true; paintLinks(); };
  es.onerror = () => { S.streamOk = false; paintLinks(); /* EventSource reconnects automatically (retry: 3s) */ };
}
function paintLinks() {
  const h = S.state?.health || {};
  const set = (id, ok, warn, text) => { const el = $(id); el.innerHTML = `<span class="dot ${ok ? "ok" : warn ? "warn" : "bad"}"></span>${esc(text)}`; };
  set("#tb-engine", h.engine_alive, false, h.engine_alive ? `engine ${ago(h.engine_heartbeat_age_s)}` : "engine DOWN");
  set("#tb-feed", !h.market_data_error && isNum(h.market_data_age_s), false, h.market_data_error ? "market data ERROR" : `prices ${ago(h.market_data_age_s)}`);
  set("#tb-stream", S.streamOk, false, S.streamOk ? "live" : "reconnecting…");
}
const tick = () => { $("#tb-clock").textContent = new Date().toLocaleTimeString(); };
tick(); setInterval(tick, 1000);

function onState(st) {
  const prev = S.state; S.state = st;
  if (st.error) { $("#global-alerts").innerHTML = `<div class="alert bad">${esc(st.error)}</div>`; return; }
  const b = $("#mode-badge"); b.textContent = st.mode; b.className = `badge ${st.mode === "LIVE" ? "live" : st.mode === "PAPER" ? "paper" : "unknown"}`;
  const a = st.account || {};
  $("#tb-equity").textContent = usd(a.equity);
  $("#tb-pnl").innerHTML = `<span class="${cls(a.total_pnl)}">${usd(a.total_pnl, true)} ${pct(a.total_pnl_pct)}</span>`;
  const today = (a.today_realized || 0) + (a.today_unrealized || 0);
  $("#tb-today").innerHTML = `<span class="${cls(a.today_realized)}" title="realized today">${usd(a.today_realized, true)}</span>`;
  $("#tb-open").textContent = `${st.positions.length}`; $("#nav-pos").textContent = st.positions.length;
  $("#tb-dd").textContent = pct(a.drawdown_pct, 1, false);
  paintLinks(); alerts(st);
  // notify on changes the engine confirmed
  if (prev) {
    const was = new Set(prev.positions.map((p) => p.symbol)), now = new Set(st.positions.map((p) => p.symbol));
    st.positions.filter((p) => !was.has(p.symbol)).forEach((p) => toast(`Opened ${p.symbol} ${p.qty} @ ${px(p.entry)} (stop ${px(p.stop)})`, "ok"));
    prev.positions.filter((p) => !now.has(p.symbol)).forEach((p) => toast(`Closed ${p.symbol} (see History)`, "warn"));
    if (st.kill_switch && !prev.kill_switch) toast(`Kill switch engaged: ${st.kill_switch}`, "bad");
  }
  renderOverview(); if (S.view === "positions") renderPositions(); if (S.view === "orders") renderCommands();
  if (S.view === "chart" && S.chartData) updateChartLines();
}
function alerts(st) {
  const h = st.health || {}, out = [];
  if (!st.has_engine_data) out.push(`<div class="alert warn">No engine data yet. Start the bot with <code>./start_auto.sh</code>; this terminal fills in after its first cycle.</div>`);
  else if (!h.engine_alive) out.push(`<div class="alert bad"><b>Engine not running</b> (last heartbeat ${ago(h.engine_heartbeat_age_s)} ago). Positions are not being managed and actions are disabled. Restart with <code>./start_auto.sh</code>.</div>`);
  if (st.kill_switch) out.push(`<div class="alert bad"><b>Kill switch engaged</b> — no new entries: ${esc(st.kill_switch)}</div>`);
  if (st.risk_config?.entries_paused) out.push(`<div class="alert warn">New entries are paused from the terminal. Open positions are still managed.</div>`);
  if (h.market_data_error) out.push(`<div class="alert bad">Market data: ${esc(h.market_data_error)}</div>`);
  if (st.mode === "LIVE") out.push(`<div class="alert bad"><b>LIVE MODE</b> — actions place real orders on Delta Exchange.</div>`);
  $("#global-alerts").innerHTML = out.join("");
}

/* -------------------------------------------------------------- overview */
function kpi(k, v, s = "", c = "") { return `<div class="kpi"><div class="k">${esc(k)}</div><div class="v ${c}">${v}</div>${s ? `<div class="s">${s}</div>` : ""}</div>`; }
function renderOverview() {
  const st = S.state; if (!st) return; const a = st.account, p = st.performance, r = st.risk;
  $("#ov-kpis").innerHTML = [
    kpi("Account equity", usd(a.equity), `started ${usd(a.starting_capital)}`),
    kpi("Total P&L", usd(a.total_pnl, true), pct(a.total_pnl_pct), cls(a.total_pnl)),
    kpi("Available margin", usd(a.available_margin), `used ${usd(a.used_margin)}`),
    kpi("Unrealized P&L", usd(a.unrealized_usd, true), `${st.positions.length} open`, cls(a.unrealized_usd)),
    kpi("Realized today", usd(a.today_realized, true), "", cls(a.today_realized)),
    kpi("Exposure", pct(r.exposure_pct, 1, false), `leverage ${isNum(r.effective_leverage) ? r.effective_leverage.toFixed(2) + "x" : "—"}`),
    kpi("Capital at risk", usd(r.capital_at_risk_usd), "if every stop fills now"),
    kpi("Drawdown", pct(a.drawdown_pct, 1, false), `limit ${r.drawdown_limit_pct}%`),
    kpi("Strategy", esc(st.risk_config?.entries_paused ? "Paused" : st.kill_switch ? "Halted" : "Active"), esc(st.rule)),
  ].join("");
  $("#ov-perf").innerHTML = [
    kpi("Trades", p.trades, `${p.wins} won · ${p.losses} lost`),
    kpi("Win rate", p.win_rate_pct == null ? "—" : `${p.win_rate_pct}%`, "backtest 41%"),
    kpi("Avg result", rr(p.avg_r), "backtest +0.54R", cls(p.avg_r)),
    kpi("Profit factor", p.profit_factor == null ? "—" : p.profit_factor.toFixed(2), "backtest 2.29"),
    kpi("Avg win / loss", `${usd(p.avg_win)} / ${usd(p.avg_loss)}`),
    kpi("Net after fees", usd(p.net_pnl, true), `fees ${usd(p.fees)}`, cls(p.net_pnl)),
  ].join("");
  $("#ov-positions").innerHTML = st.positions.length ? `<table><thead><tr><th class="l">Coin</th><th>Qty</th><th>Entry</th><th>Price</th><th>Stop</th><th>P&amp;L</th><th>R</th></tr></thead><tbody>${
    st.positions.map((p) => `<tr><td class="l">${esc(p.symbol)}</td><td>${p.qty}</td><td>${px(p.entry)}</td><td>${px(p.mark)}</td><td>${px(p.stop)}</td><td class="${cls(p.unrealized_usd)}">${usd(p.unrealized_usd, true)}</td><td class="${cls(p.r_now)}">${rr(p.r_now)}</td></tr>`).join("")}</tbody></table>`
    : `<div class="empty">No open positions. The bot waits for a daily close above a 55-day high; weeks without trades are normal.</div>`;
  const lc = st.last_cycle || {}, items = [...(lc.entries || []).map((x) => `Entered ${x}`), ...(lc.exits || []).map((x) => `Closed ${x}`), ...(lc.stops_moved || []).map((x) => `Stop raised ${x}`), ...(lc.skipped || [])];
  $("#ov-cycle").innerHTML = `<div class="muted" style="margin-bottom:6px">Cycle ${ago(st.health.cycle_age_s)} ago · last daily candle ${esc(st.last_daily_bar || "—")} · decides after 05:30 IST</div>` +
    (items.length ? `<ul style="margin:0;padding-left:18px">${items.slice(0, 14).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : `<div class="faint">Nothing to do: no signals, no stops hit.</div>`);
  $("#ov-commands").innerHTML = st.commands.length ? `<table><tbody>${st.commands.slice(0, 6).map((c) => `<tr><td class="l txt">${esc(c.kind.replaceAll("_", " ").toLowerCase())} ${esc(c.payload.symbol || "")}</td><td>${statusPill(c.status)}</td><td class="l txt muted">${esc(c.result?.message || c.result?.error || "")}</td><td>${when(c.created_at)}</td></tr>`).join("")}</tbody></table>` : `<div class="faint">None yet.</div>`;
}
const statusPill = (s) => `<span class="pill ${s === "DONE" || s === "FILLED" ? "ok" : s === "FAILED" || s === "REJECTED" ? "bad" : s === "PENDING" || s === "EXECUTING" || s === "SUBMITTED" ? "warn" : "neutral"}">${esc(s)}</span>`;

/* --------------------------------------------------------------- markets */
async function loadMarkets() { S.markets = await api("/api/markets"); renderMarkets(); }
function renderMarkets() {
  const m = S.markets; if (!m) return;
  $("#mk-age").textContent = m.error ? m.error : `updated ${new Date(m.ts * 1000).toLocaleTimeString()}`;
  const q = $("#mk-search").value.trim().toUpperCase(), tr = $("#mk-trend").value, only = $("#mk-signals").checked;
  const rows = m.items.filter((r) => (!q || r.symbol.includes(q)) && (!tr || r.trend === tr) && (!only || r.in_position || r.long_entry_signal));
  table($("#mk-table"), "mk", [
    { k: "symbol", label: "Coin", l: 1, fmt: (r) => `<a href="#" data-chart="${esc(r.symbol)}">${esc(r.symbol)}</a>${r.in_position ? ' <span class="pill long">POS</span>' : ""}${!r.enabled ? ' <span class="pill neutral">off</span>' : ""}${r.contract_mismatch ? ' <span class="pill bad" title="Bot contract size differs from Delta">SIZE?</span>' : ""}` },
    { k: "price", label: "Price", fmt: (r) => px(r.price) },
    { k: "change_24h_pct", label: "24h", fmt: (r) => `<span class="${cls(r.change_24h_pct)}">${pct(r.change_24h_pct)}</span>` },
    { k: "turnover_usd", label: "Volume $", fmt: (r) => big(r.turnover_usd) },
    { k: "spread_pct", label: "Spread", fmt: (r) => isNum(r.spread_pct) ? r.spread_pct.toFixed(3) + "%" : "—" },
    { k: "funding_rate_pct", label: "Funding", fmt: (r) => isNum(r.funding_rate_pct) ? r.funding_rate_pct.toFixed(4) + "%" : "—" },
    { k: "trend", label: "Trend", fmt: (r) => r.trend ? `<span class="pill ${r.trend === "UP" ? "ok" : r.trend === "DOWN" ? "bad" : "neutral"}">${esc(r.trend)}</span>` : "—" },
    { k: "rsi", label: "RSI", fmt: (r) => isNum(r.rsi) ? r.rsi.toFixed(0) : "—" },
    { k: "macd_hist", label: "MACD h", fmt: (r) => `<span class="${cls(r.macd_hist)}">${isNum(r.macd_hist) ? px(r.macd_hist) : "—"}</span>` },
    { k: "atr_pct", label: "ATR %", fmt: (r) => isNum(r.atr_pct) ? r.atr_pct.toFixed(2) + "%" : "—" },
    { k: "vwap20", label: "VWAP 20d", fmt: (r) => px(r.vwap20) },
    { k: "breakout_level", label: "55d high", fmt: (r) => px(r.breakout_level) },
    { k: "to_breakout_pct", label: "To breakout", fmt: (r) => isNum(r.to_breakout_pct) ? (r.to_breakout_pct <= 0 ? '<span class="up">above</span>' : r.to_breakout_pct.toFixed(2) + "%") : "—" },
    { k: "signal_action", label: "Last daily check", l: 1, txt: 1, fmt: (r) => r.signal_action ? `${statusPill(r.signal_action)} <span class="faint">${esc(r.signal_note || "")}</span>` : '<span class="faint">—</span>' },
  ], rows, { sortKey: "turnover_usd", empty: "No coins match.", after: (el) => $$("a[data-chart]", el).forEach((a) => a.onclick = (e) => { e.preventDefault(); S.chartSym = a.dataset.chart; show("chart"); }) });
}
["#mk-search", "#mk-trend", "#mk-signals"].forEach((id) => $(id).addEventListener("input", renderMarkets));

/* ----------------------------------------------------------------- chart */
const LC = window.LightweightCharts;
const chartOpts = () => ({ autoSize: true, layout: { background: { type: "solid", color: "#11151c" }, textColor: "#8b95a7", fontSize: 11 },
  grid: { vertLines: { color: "#1a202b" }, horzLines: { color: "#1a202b" } }, rightPriceScale: { borderColor: "#232a36" },
  timeScale: { borderColor: "#232a36", timeVisible: true, secondsVisible: false }, crosshair: { mode: 0 } });
let CH = null;
function buildCharts() {
  if (CH) return;
  const main = LC.createChart($("#chart-main"), chartOpts()), rsi = LC.createChart($("#chart-rsi"), chartOpts()), macd = LC.createChart($("#chart-macd"), chartOpts());
  const candles = main.addCandlestickSeries({ upColor: "#22c55e", downColor: "#ef4444", wickUpColor: "#22c55e", wickDownColor: "#ef4444", borderVisible: false });
  const vol = main.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", lastValueVisible: false, priceLineVisible: false });
  main.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  const line = (c, color, w = 1, style = 0) => c.addLineSeries({ color, lineWidth: w, lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
  CH = { main, rsi, macd, candles, vol, lines: [],
    ov: { ema20: line(main, "#f59e0b"), ema50: line(main, "#a78bfa"), sma20: line(main, "#38bdf8"), bb_upper: line(main, "#64748b", 1, 2), bb_lower: line(main, "#64748b", 1, 2), vwap: line(main, "#f472b6") },
    rsiS: line(rsi, "#a78bfa", 1.5), macdL: line(macd, "#38bdf8", 1.5), macdS: line(macd, "#f59e0b", 1.5),
    macdH: macd.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false }) };
  [70, 30].forEach((v) => CH.rsiS.createPriceLine({ price: v, color: "#475569", lineWidth: 1, lineStyle: 2, axisLabelVisible: false }));
  // keep the three panes scrolled together
  // All three panes are given the same time points (see padTo), so a logical range means the
  // same dates everywhere. Only push a range that actually differs, or the panes would keep
  // re-triggering each other forever.
  const charts = [main, rsi, macd];
  const same = (a, b) => a && b && Math.abs(a.from - b.from) < 1e-6 && Math.abs(a.to - b.to) < 1e-6;
  charts.forEach((c) => c.timeScale().subscribeVisibleLogicalRangeChange((r) => {
    if (!r) return;
    charts.forEach((o) => { if (o !== c && !same(o.timeScale().getVisibleLogicalRange(), r)) o.timeScale().setVisibleLogicalRange(r); });
  }));
  main.subscribeCrosshairMove((p) => { const d = p?.seriesData?.get(candles); if (d) legend(d); });
}
function legend(d) {
  const sd = S.chartData; if (!sd) return; const c = d || sd.candles.at(-1); if (!c) return;
  $("#ch-legend").innerHTML = `<span>${esc(sd.symbol)} · ${esc(sd.tf)}</span><span>O <b>${px(c.open)}</b></span><span>H <b>${px(c.high)}</b></span><span>L <b>${px(c.low)}</b></span><span>C <b class="${c.close >= c.open ? "up" : "down"}">${px(c.close)}</b></span>` +
    (sd.strategy_levels?.breakout ? `<span>55d high <b>${px(sd.strategy_levels.breakout)}</b></span><span>20d low <b>${px(sd.strategy_levels.exit)}</b></span>` : "");
}
async function loadChart(fit) {
  buildCharts();
  const sel = $("#ch-symbol");
  if (!sel.options.length) { const syms = (S.markets?.items || []).map((m) => m.symbol);
    const list = syms.length ? syms : (S.strategy?.symbols || []).map((s) => s.symbol);
    if (!list.length) { const st = await api("/api/strategy"); S.strategy = st; list.push(...st.symbols.map((s) => s.symbol)); }
    sel.innerHTML = list.map((s) => `<option>${esc(s)}</option>`).join(""); }
  if (S.chartSym) sel.value = S.chartSym; S.chartSym = sel.value;
  $("#ch-status").textContent = "loading…";
  const d = await api(`/api/candles?symbol=${encodeURIComponent(S.chartSym)}&tf=${S.chartTf}&bars=${S.chartTf === "1d" ? 365 : 400}`);
  S.chartData = d;
  if (d.error) { $("#ch-status").textContent = d.error; return; }
  const last = d.last?.close || 1, prec = last >= 1000 ? 2 : last >= 1 ? 4 : 6;
  CH.candles.applyOptions({ priceFormat: { type: "price", precision: prec, minMove: 1 / 10 ** prec } });
  CH.candles.setData(d.candles); CH.vol.setData(d.volume);
  Object.entries(CH.ov).forEach(([k, s]) => s.setData(d.overlays[k] || []));
  // pad indicator series with empty points so every pane has exactly the candle times
  const padTo = (pts) => { const m = new Map(pts.map((p) => [p.time, p])); return d.candles.map((c) => m.get(c.time) || { time: c.time }); };
  CH.rsiS.setData(padTo(d.rsi)); CH.macdL.setData(padTo(d.macd.macd)); CH.macdS.setData(padTo(d.macd.signal)); CH.macdH.setData(padTo(d.macd.hist));
  CH.candles.setMarkers(d.markers || []);
  applyOverlayToggles(); updateChartLines();
  if (fit) [CH.main, CH.rsi, CH.macd].forEach((c) => c.timeScale().fitContent());
  legend(); $("#ch-status").textContent = `${d.candles.length} candles · updated ${new Date().toLocaleTimeString()}`;
}
function updateChartLines() {
  if (!CH || !S.chartData) return;
  CH.lines.forEach((l) => CH.candles.removePriceLine(l)); CH.lines = [];
  const add = (price, title, color, style = 0) => isNum(price) && CH.lines.push(CH.candles.createPriceLine({ price, title, color, lineWidth: 1, lineStyle: style, axisLabelVisible: true }));
  const pos = S.state?.positions.find((p) => p.symbol === S.chartData.symbol);
  if (pos) { add(pos.entry, "Entry", "#3b82f6"); add(pos.stop, pos.stop_source === "MANUAL" ? "Stop (manual)" : "Stop (trailing)", "#ef4444");
    if (pos.initial_stop !== pos.stop) add(pos.initial_stop, "Initial stop", "#7f1d1d", 2); if (pos.take_profit) add(pos.take_profit, "Take profit", "#22c55e"); }
  else (S.chartData.lines || []).forEach((l) => add(l.price, l.title, l.color));
  if ($('[data-ov="levels"]').checked && S.chartData.tf === "1d" && S.chartData.strategy_levels?.breakout) {
    add(S.chartData.strategy_levels.breakout, "55d high (entry)", "#475569", 2); add(S.chartData.strategy_levels.exit, "20d low (exit)", "#475569", 2); }
}
function applyOverlayToggles() {
  const on = (k) => $(`[data-ov="${k}"]`).checked;
  CH.ov.ema20.applyOptions({ visible: on("ema20") }); CH.ov.ema50.applyOptions({ visible: on("ema50") }); CH.ov.sma20.applyOptions({ visible: on("sma20") });
  CH.ov.bb_upper.applyOptions({ visible: on("bb") }); CH.ov.bb_lower.applyOptions({ visible: on("bb") }); CH.ov.vwap.applyOptions({ visible: on("vwap") });
}
$$("[data-ov]").forEach((c) => c.onchange = () => { applyOverlayToggles(); updateChartLines(); });
$("#ch-symbol").onchange = (e) => { S.chartSym = e.target.value; loadChart(true).catch((er) => toast(er.message, "bad")); };
$$("#ch-tf button").forEach((b) => b.onclick = () => { $$("#ch-tf button").forEach((x) => x.classList.toggle("on", x === b)); S.chartTf = b.dataset.tf; loadChart(true).catch((er) => toast(er.message, "bad")); });

/* ------------------------------------------------------------- positions */
function renderPositions() {
  const st = S.state; if (!st) return; const live = st.mode === "LIVE", alive = st.health.engine_alive;
  table($("#pos-table"), "pos", [
    { k: "symbol", label: "Coin", l: 1, fmt: (p) => `<a href="#" data-chart="${esc(p.symbol)}">${esc(p.symbol)}</a>` },
    { k: "side", label: "Side", fmt: (p) => `<span class="pill ${p.side === "SELL" ? "short" : "long"}">${p.side === "SELL" ? "SHORT" : "LONG"}</span>` },
    { k: "qty", label: "Qty", fmt: (p) => `${p.qty}<span class="faint"> ×${p.multiplier}</span>` },
    { k: "entry", label: "Entry", fmt: (p) => px(p.entry) },
    { k: "mark", label: "Price", fmt: (p) => px(p.mark) },
    { k: "unrealized_usd", label: "P&L", fmt: (p) => `<span class="${cls(p.unrealized_usd)}">${usd(p.unrealized_usd, true)}</span>` },
    { k: "pnl_pct", label: "P&L %", fmt: (p) => `<span class="${cls(p.pnl_pct)}">${pct(p.pnl_pct)}</span>` },
    { k: "r_now", label: "R", fmt: (p) => `<span class="${cls(p.r_now)}">${rr(p.r_now)}</span>` },
    { k: "stop", label: "Stop", fmt: (p) => `${px(p.stop)}${p.stop_source === "MANUAL" ? ' <span class="pill warn">manual</span>' : ""}` },
    { k: "distance_to_stop_pct", label: "To stop", fmt: (p) => pct(p.distance_to_stop_pct, 2, false) },
    { k: "take_profit", label: "Take profit", fmt: (p) => p.take_profit ? px(p.take_profit) : '<span class="faint">none</span>' },
    { k: "risk_reward", label: "R:R", fmt: (p) => isNum(p.risk_reward) ? `1:${p.risk_reward}` : '<span class="faint">open</span>' },
    { k: "notional_usd", label: "Value", fmt: (p) => usd(p.notional_usd) },
    { k: "opened_at", label: "Opened", fmt: (p) => when(p.opened_at) },
    { k: "duration_hours", label: "Held", fmt: (p) => dur(p.duration_hours) },
    { k: "status", label: "Status", nosort: 1, fmt: (p) => S.pending[p.symbol] ? statusPill("PENDING") : statusPill("OPEN") },
    { k: "act", label: "Actions", nosort: 1, stick: 1, fmt: (p) => {
      const dis = S.pending[p.symbol] || !alive ? "disabled" : "";
      return `<button class="btn small" data-act="stop" data-s="${esc(p.symbol)}" ${dis}>Stop</button> <button class="btn small" data-act="tp" data-s="${esc(p.symbol)}" ${dis}>TP</button> <button class="btn small" data-act="partial" data-s="${esc(p.symbol)}" ${dis || (p.qty < 2 ? "disabled" : "")}>Partial</button> <button class="btn small danger" data-act="close" data-s="${esc(p.symbol)}" ${dis}>Close</button> <button class="btn small" data-act="details" data-s="${esc(p.symbol)}">${S.open?.[p.symbol] ? "Hide" : "Details"}</button>`; } },
  ], st.positions, { empty: "No open positions.", expanded: (p) => S.open?.[p.symbol], expand: (p) => posDetails(p),
    after: (el) => { $$("button[data-act]", el).forEach((b) => b.onclick = () => posAction(b.dataset.act, b.dataset.s));
      $$("a[data-chart]", el).forEach((a) => a.onclick = (e) => { e.preventDefault(); S.chartSym = a.dataset.chart; show("chart"); }); } });
}
function posDetails(p) {
  return `<div class="grid g3 xd"><div><b>Why this trade</b><br>Entered after the ${esc(p.entry_signal_date)} daily close broke the 55-day high (rule: Donchian 55/20, stop 3×ATR).<br>Initial stop ${px(p.initial_stop)} → initial risk ${usd(p.initial_risk_usd)} (1R).</div>
  <div><b>Protection</b><br>Current stop ${px(p.stop)} (${esc(p.stop_source === "MANUAL" ? "moved manually" : "trailing rule")}). If it fills now: ${usd(p.locked_in_usd, true)}.<br>Take profit: ${p.take_profit ? px(p.take_profit) : "none — exits on a 20-day low or the stop"}.</div>
  <div><b>Market</b><br>Bid ${px(p.bid)} · Ask ${px(p.ask)} · Mark ${px(p.mark)}<br>Value ${usd(p.notional_usd)} · contracts ${p.qty} × ${p.multiplier}</div></div>`;
}

/* --------------------------------------------------------------- actions */
function modal(html, onOk, okLabel = "Confirm", danger = false) {
  $("#modal").innerHTML = `${html}<div class="actions"><button class="btn" id="m-cancel">Cancel</button><button class="btn ${danger ? "danger" : "primary"}" id="m-ok">${esc(okLabel)}</button></div>`;
  $("#modal-bg").classList.add("open");
  const close = () => $("#modal-bg").classList.remove("open");
  $("#m-cancel").onclick = close; $("#modal-bg").onclick = (e) => { if (e.target.id === "modal-bg") close(); };
  $("#m-ok").onclick = async () => { const ok = await onOk(); if (ok !== false) close(); };
  setTimeout(() => $("#modal input")?.focus(), 30);
}
const liveNote = () => S.state?.mode === "LIVE" ? `<p class="livewarn">LIVE MODE: this sends a real order to Delta Exchange.</p>` : `<p class="muted">Paper mode: executed on the paper account at live prices.</p>`;
async function send(kind, payload, label) {
  try {
    const r = await api("/api/commands", { method: "POST", body: JSON.stringify({ kind, payload }) });
    if (payload.symbol) S.pending[payload.symbol] = r.id; renderPositions();
    toast(`${label}: sent to the engine…`);
    const t0 = Date.now();
    while (Date.now() - t0 < 90000) {
      await new Promise((res) => setTimeout(res, 1000));
      const c = await api(`/api/commands/${r.id}`);
      if (c.status === "DONE" || c.status === "FAILED") {
        delete S.pending[payload.symbol];
        toast(c.status === "DONE" ? `${label}: ${c.result?.message}` : `${label} failed: ${c.result?.error}`, c.status === "DONE" ? "ok" : "bad");
        renderPositions(); refreshView(); return c;
      }
    }
    delete S.pending[payload.symbol]; toast(`${label}: no answer from the engine yet — check Orders before retrying.`, "warn");
  } catch (e) { if (payload.symbol) delete S.pending[payload.symbol]; toast(`${label}: ${e.message}`, "bad"); renderPositions(); }
}
function posAction(act, sym) {
  const p = S.state.positions.find((x) => x.symbol === sym); if (!p) return;
  if (act === "details") { (S.open ||= {})[sym] = !S.open[sym]; return renderPositions(); }
  const est = (q) => ((p.side === "SELL" ? p.entry - p.mark : p.mark - p.entry) * q * p.multiplier);
  if (act === "close") return modal(`<h2>Close ${esc(sym)}</h2>${liveNote()}<div class="row">Market-close all <b>${p.qty}</b> contracts (≈ ${px(p.mark)}).<br>Estimated P&amp;L before fees: <b class="${cls(est(p.qty))}">${usd(est(p.qty), true)}</b></div>`,
    () => send("CLOSE_POSITION", { symbol: sym }, `Close ${sym}`), "Close position", true);
  if (act === "partial") return modal(`<h2>Partially close ${esc(sym)}</h2>${liveNote()}<div class="row">Contracts to close (1–${p.qty - 1}): <input type="number" id="m-q" min="1" max="${p.qty - 1}" step="1" value="${Math.max(1, Math.floor(p.qty / 2))}"></div><div class="row muted">The rest stays open with the same stop.</div>`,
    () => { const q = parseInt($("#m-q").value, 10); if (!(q >= 1 && q < p.qty)) { toast(`Enter 1–${p.qty - 1}`, "bad"); return false; } return send("CLOSE_POSITION", { symbol: sym, quantity: q }, `Partial close ${sym}`); }, "Close contracts", true);
  if (act === "stop") return modal(`<h2>Move stop — ${esc(sym)}</h2>${liveNote()}<div class="row">New stop: <input type="number" id="m-v" step="any" value="${p.stop}"></div>
    <div class="row muted">Must be below the price (${px(p.mark)}) and not below the initial stop ${px(p.initial_stop)} — that would risk more than planned. The trailing rule will still only raise it.</div>`,
    () => { const v = parseFloat($("#m-v").value); if (!(v > 0)) { toast("Enter a price", "bad"); return false; } return send("MOVE_STOP", { symbol: sym, stop: v }, `Move stop ${sym}`); }, "Move stop");
  if (act === "tp") return modal(`<h2>Take profit — ${esc(sym)}</h2>${liveNote()}<div class="row">Take-profit price (empty = none): <input type="number" id="m-v" step="any" value="${p.take_profit || ""}"></div>
    <div class="row warn">The tested rule has no take-profit: it lets winners run. Capping winners reduces the edge measured in the backtest.</div>`,
    () => { const raw = $("#m-v").value.trim(); const v = raw ? parseFloat(raw) : null; if (raw && !(v > 0)) { toast("Enter a price or leave empty", "bad"); return false; }
      return send("SET_TAKE_PROFIT", { symbol: sym, take_profit: v }, v ? `Set TP ${sym}` : `Remove TP ${sym}`); }, "Save");
}

/* ---------------------------------------------------------------- orders */
async function loadOrders() {
  const st = $("#or-status").value, sym = $("#or-symbol").value;
  S.orders = await api(`/api/orders?limit=500${st ? `&status=${st}` : ""}${sym ? `&symbol=${sym}` : ""}`);
  if ($("#or-symbol").options.length <= 1) { const st2 = S.strategy || await api("/api/strategy"); S.strategy = st2;
    $("#or-symbol").insertAdjacentHTML("beforeend", st2.symbols.map((s) => `<option>${esc(s.symbol)}</option>`).join("")); }
  const purpose = $("#or-purpose").value;
  table($("#or-table"), "or", [
    { k: "ts", label: "Time", l: 1, fmt: (o) => when(o.ts) },
    { k: "client_order_id", label: "Order ID", l: 1, fmt: (o) => `<span class="faint">${esc(o.client_order_id)}</span>` },
    { k: "symbol", label: "Coin", l: 1 },
    { k: "purpose", label: "Purpose", l: 1, txt: 1, fmt: (o) => esc(o.purpose.replace("_", " ").toLowerCase()) },
    { k: "side", label: "Side", fmt: (o) => `<span class="pill ${o.side === "BUY" ? "long" : "short"}">${esc(o.side)}</span>` },
    { k: "order_type", label: "Type", txt: 1 },
    { k: "quantity", label: "Qty" },
    { k: "reference_price", label: "Ref price", fmt: (o) => px(o.reference_price) },
    { k: "average_price", label: "Fill price", fmt: (o) => px(o.average_price) },
    { k: "slip", label: "Slippage", sort: (o) => o.average_price && o.reference_price ? (o.average_price - o.reference_price) / o.reference_price : null,
      fmt: (o) => o.average_price && o.reference_price ? pct(((o.average_price - o.reference_price) / o.reference_price) * 100 * (o.side === "BUY" ? 1 : -1), 3) : "—" },
    { k: "filled_quantity", label: "Filled" },
    { k: "fee_estimate", label: "Fee est.", fmt: (o) => usd(o.fee_estimate) },
    { k: "status", label: "Status", fmt: (o) => statusPill(o.status) },
    { k: "mode", label: "Mode", txt: 1 },
    { k: "reason", label: "Reason", l: 1, txt: 1, fmt: (o) => `<span class="muted" title="${esc(o.reason)}">${esc(o.reason.length > 22 ? o.reason.slice(0, 21) + "…" : o.reason)}</span>` },
    { k: "x", label: "", nosort: 1, stick: 1, fmt: (o) => `<button class="btn small" data-oid="${esc(o.client_order_id)}">${S.openOrder?.[o.client_order_id] ? "Hide" : "Response"}</button>` },
  ], S.orders.filter((o) => !purpose || o.purpose === purpose), { sortKey: "ts", empty: "No orders yet.", expanded: (o) => S.openOrder?.[o.client_order_id],
    expand: (o) => `<div class="muted" style="margin-bottom:4px">Broker order ID ${esc(o.broker_order_id)} — raw broker response:</div><pre class="json">${esc(JSON.stringify(o.response, null, 2))}</pre>`,
    after: (el) => $$("button[data-oid]", el).forEach((b) => b.onclick = () => { (S.openOrder ||= {})[b.dataset.oid] = !S.openOrder[b.dataset.oid]; loadOrders(); }) });
  renderCommands();
}
function renderCommands() {
  const c = S.state?.commands || [];
  table($("#cmd-table"), "cmd", [
    { k: "created_at", label: "Time", l: 1, fmt: (r) => when(r.created_at) },
    { k: "kind", label: "Command", l: 1, txt: 1, fmt: (r) => esc(r.kind.replaceAll("_", " ").toLowerCase()) },
    { k: "payload", label: "Details", l: 1, nosort: 1, fmt: (r) => `<span class="faint">${esc(JSON.stringify(r.payload))}</span>` },
    { k: "status", label: "Status", fmt: (r) => statusPill(r.status) },
    { k: "result", label: "Engine answer", l: 1, txt: 1, nosort: 1, fmt: (r) => esc(r.result?.message || r.result?.error || "") },
  ], c, { sortKey: "created_at", empty: "No terminal commands yet." });
}
["#or-status", "#or-symbol", "#or-purpose"].forEach((id) => $(id).addEventListener("change", () => loadOrders().catch((e) => toast(e.message, "bad"))));

/* --------------------------------------------------------------- history */
let HC = null;
async function loadHistory() {
  const [a, t] = await Promise.all([api("/api/analytics"), api("/api/trades?limit=5000")]);
  S.analytics = a; S.trades = t; const s = a.summary;
  $("#hi-kpis").innerHTML = [
    kpi("Closed trades", s.trades, `${s.wins} won · ${s.losses} lost`), kpi("Win rate", s.win_rate_pct == null ? "—" : `${s.win_rate_pct}%`),
    kpi("Net P&L", usd(s.net_pnl, true), `gross ${usd(s.gross_pnl, true)} · fees ${usd(s.fees)}`, cls(s.net_pnl)),
    kpi("Profit factor", s.profit_factor == null ? "—" : s.profit_factor.toFixed(2)), kpi("Expectancy", usd(s.expectancy, true), "per trade", cls(s.expectancy)),
    kpi("Avg result", rr(s.avg_r), "", cls(s.avg_r)), kpi("Avg win", usd(s.avg_win, true)), kpi("Avg loss", usd(s.avg_loss, true)),
    kpi("Max drawdown", pct(a.curve.max_drawdown_pct, 2, false)), kpi("Avg holding", dur(s.avg_hold_hours)),
    kpi("Best / worst", `${usd(s.best, true)} / ${usd(s.worst, true)}`), kpi("Max losing streak", s.max_consecutive_losses),
  ].join("");
  const b = a.backtest, wr = a.win_rate_trend.at(-1);
  $("#hi-bt").innerHTML = `<table><thead><tr><th class="l"></th><th>This bot</th><th>Backtest</th></tr></thead><tbody>
    <tr><td class="l txt">Win rate</td><td>${s.win_rate_pct == null ? "—" : s.win_rate_pct + "%"}</td><td>${b.win_rate_pct}%</td></tr>
    <tr><td class="l txt">Average result per trade</td><td class="${cls(s.avg_r)}">${rr(s.avg_r)}</td><td>+${b.avg_r}R (95% CI ${b.avg_r_95ci[0]} to ${b.avg_r_95ci[1]})</td></tr>
    <tr><td class="l txt">Profit factor</td><td>${s.profit_factor == null ? "—" : s.profit_factor.toFixed(2)}</td><td>${b.profit_factor}</td></tr>
    <tr><td class="l txt">Win rate, last 10 trades</td><td>${wr ? wr.win_rate_pct + "%" : "—"}</td><td></td></tr></tbody></table>
    <p class="faint" style="margin:8px 0 0">Backtest: ${esc(b.period)}, ${b.trades} trades. ${esc(b.note)} Fewer than ~30 live trades say little either way.</p>`;
  if (!HC) { HC = { eq: LC.createChart($("#eq-chart"), chartOpts()), dd: LC.createChart($("#dd-chart"), chartOpts()) };
    HC.eqS = HC.eq.addAreaSeries({ lineColor: "#3b82f6", topColor: "rgba(59,130,246,.25)", bottomColor: "rgba(59,130,246,0)", lineWidth: 2 });
    HC.ddS = HC.dd.addAreaSeries({ lineColor: "#ef4444", topColor: "rgba(239,68,68,0)", bottomColor: "rgba(239,68,68,.3)", lineWidth: 1 }); }
  const toPts = (arr) => { const seen = new Set(); return arr.map((p) => ({ time: Math.floor(new Date(p.time).getTime() / 1000), value: p.value })).filter((p) => !seen.has(p.time) && seen.add(p.time)); };
  HC.eqS.setData(toPts(a.curve.equity)); HC.ddS.setData(toPts(a.curve.drawdown)); HC.eq.timeScale().fitContent(); HC.dd.timeScale().fitContent();
  renderTrades(); renderGroups();
}
function renderTrades() {
  const q = $("#hi-search").value.trim().toUpperCase(), res = $("#hi-result").value;
  const rows = (S.trades || []).filter((t) => (!q || t.symbol.includes(q) || t.exit_reason.toUpperCase().includes(q)) && (!res || (res === "win" ? t.net_pnl > 0 : t.net_pnl <= 0)));
  table($("#hi-trades"), "hi", [
    { k: "exit_time", label: "Closed", l: 1, fmt: (t) => when(t.exit_time) }, { k: "symbol", label: "Coin", l: 1 },
    { k: "side", label: "Side", fmt: (t) => `<span class="pill ${t.side === "SELL" ? "short" : "long"}">${t.side === "SELL" ? "SHORT" : "LONG"}</span>` },
    { k: "strategy", label: "Strategy", txt: 1, fmt: () => "Daily trend" }, { k: "quantity", label: "Qty" },
    { k: "entry_time", label: "Opened", l: 1, fmt: (t) => when(t.entry_time) },
    { k: "entry_price", label: "Entry", fmt: (t) => px(t.entry_price) }, { k: "exit_price", label: "Exit", fmt: (t) => px(t.exit_price) },
    { k: "hold", label: "Held", sort: (t) => new Date(t.exit_time) - new Date(t.entry_time), fmt: (t) => dur((new Date(t.exit_time) - new Date(t.entry_time)) / 3.6e6) },
    { k: "exit_reason", label: "Exit reason", l: 1, txt: 1 }, { k: "gross_pnl", label: "Gross", fmt: (t) => usd(t.gross_pnl, true) },
    { k: "fees", label: "Fees", fmt: (t) => usd(t.fees) }, { k: "net_pnl", label: "Net", fmt: (t) => `<span class="${cls(t.net_pnl)}">${usd(t.net_pnl, true)}</span>` },
    { k: "r_multiple", label: "R", fmt: (t) => `<span class="${cls(t.r_multiple)}">${rr(t.r_multiple)}</span>` },
    { k: "res", label: "Result", sort: (t) => t.net_pnl > 0, fmt: (t) => t.net_pnl > 0 ? '<span class="pill ok">WIN</span>' : '<span class="pill bad">LOSS</span>' },
    { k: "mode", label: "Mode", txt: 1 },
  ], rows, { sortKey: "exit_time", empty: "No closed trades yet." });
}
function renderGroups() {
  const rows = (S.analytics?.groups?.[S.hiGroup] || []);
  table($("#hi-groups"), "hg-" + S.hiGroup, [
    { k: "key", label: { daily: "Day", weekly: "Week", monthly: "Month", by_symbol: "Coin", by_side: "Direction", by_exit_reason: "Exit reason" }[S.hiGroup], l: 1 },
    { k: "trades", label: "Trades" }, { k: "wins", label: "Wins" }, { k: "win_rate_pct", label: "Win rate", fmt: (r) => r.win_rate_pct + "%" },
    { k: "net_pnl", label: "Net P&L", fmt: (r) => `<span class="${cls(r.net_pnl)}">${usd(r.net_pnl, true)}</span>` },
    { k: "avg_r", label: "Avg R", fmt: (r) => `<span class="${cls(r.avg_r)}">${rr(r.avg_r)}</span>` },
  ], rows, { sortKey: "key", empty: "No closed trades yet." });
}
["#hi-search", "#hi-result"].forEach((id) => $(id).addEventListener("input", renderTrades));
$$("#hi-group button").forEach((b) => b.onclick = () => { $$("#hi-group button").forEach((x) => x.classList.toggle("on", x === b)); S.hiGroup = b.dataset.g; renderGroups(); });

/* ------------------------------------------------------------------ risk */
const meter = (v, lim) => { const f = isNum(v) && lim ? Math.min(100, (v / lim) * 100) : 0; return `<div class="bar ${f >= 100 ? "over" : f >= 70 ? "hot" : ""}"><i style="width:${f}%"></i></div>`; };
async function loadRisk() {
  const r = await api("/api/risk"); S.risk = r; const cfg = r.risk_config || S.state?.risk_config || {};
  $("#rk-kpis").innerHTML = [
    kpi("Exposure", usd(r.exposure_usd), `${pct(r.exposure_pct, 1, false)} of equity · ${isNum(r.effective_leverage) ? r.effective_leverage.toFixed(2) : "—"}x`),
    kpi("Capital at risk", usd(r.capital_at_risk_usd), `${pct(r.capital_at_risk_pct, 2, false)} if every stop fills now`),
    kpi("Daily loss", pct(r.daily_loss_pct, 2, false), `limit ${r.daily_loss_limit_pct}%${meter(r.daily_loss_pct, r.daily_loss_limit_pct)}`),
    kpi("Drawdown", pct(r.drawdown_pct, 2, false), `limit ${r.drawdown_limit_pct}%${meter(r.drawdown_pct, r.drawdown_limit_pct)}`),
    kpi("Positions", `${r.open_positions} / ${r.max_positions}`, meter(r.open_positions, r.max_positions)),
    kpi("Risk per trade", `${r.risk_per_trade_pct}%`, `≈ ${usd(r.risk_per_trade_pct / 100 * r.equity)} per trade`),
    kpi("Remaining risk budget", usd(r.remaining_new_trade_risk_usd), "for new trades at current limits"),
    kpi("Largest position", pct(r.largest_position_pct, 1, false), "of equity"),
  ].join("");
  const ks = S.state?.kill_switch, alive = S.state?.health?.engine_alive, dis = alive ? "" : "disabled";
  $("#rk-controls").innerHTML = `<div class="row" style="margin-bottom:10px">New entries: <b>${cfg.entries_paused ? "paused" : "allowed"}</b>
      <button class="btn small" id="rk-pause" ${dis}>${cfg.entries_paused ? "Resume entries" : "Pause entries"}</button></div>
    <div class="row">Kill switch: <b class="${ks ? "down" : "up"}">${ks ? "ENGAGED" : "off"}</b> ${ks ? `<span class="muted">${esc(ks)}</span>` : ""}
      ${ks ? `<button class="btn small" id="rk-reset" ${dis}>Reset…</button>` : `<button class="btn small danger" id="rk-engage" ${dis}>Engage</button>`}</div>
    <p class="faint">Pausing or the kill switch stops NEW entries only; open positions keep their stops and exits.${alive ? "" : " Engine not running: controls disabled."}</p>`;
  $("#rk-pause")?.addEventListener("click", () => modal(`<h2>${cfg.entries_paused ? "Resume" : "Pause"} new entries</h2>${liveNote()}`, () => send("PAUSE_ENTRIES", { paused: !cfg.entries_paused }, cfg.entries_paused ? "Resume entries" : "Pause entries")));
  $("#rk-engage")?.addEventListener("click", () => modal(`<h2>Engage kill switch</h2><div class="row">Reason: <input type="text" id="m-v" value="manual halt from terminal" style="width:100%"></div><p class="muted">Stops new entries until reset. Open positions are still managed.</p>`,
    () => send("ENGAGE_KILL_SWITCH", { reason: $("#m-v").value || "manual halt" }, "Kill switch"), "Engage", true));
  $("#rk-reset")?.addEventListener("click", () => modal(`<h2>Reset kill switch</h2><p class="warn">This re-allows new trades and restarts the drawdown measurement from current equity. Type RESET to confirm.</p><input type="text" id="m-v" placeholder="RESET">`,
    () => { if ($("#m-v").value !== "RESET") { toast("Type RESET to confirm", "bad"); return false; } return send("RESET_KILL_SWITCH", {}, "Kill switch reset"); }, "Reset", true));
  const lim = r.limits, f = (k, v, step, pctv) => `<div class="row" style="margin:8px 0"><label>${esc(lim[k].description)}<br>
    <input type="number" name="${k}" step="${step}" min="${pctv ? lim[k].min * 100 : lim[k].min}" max="${pctv ? lim[k].max * 100 : lim[k].max}" value="${pctv ? +(v * 100).toFixed(3) : v}"> ${pctv ? "%" : ""}</label></div>`;
  // never re-draw the form while someone is editing it (auto-refresh would wipe their input)
  if (S.rkDirty) return renderRiskTables(r);
  $("#rk-form").innerHTML = f("risk_pct", cfg.risk_pct, 0.1, 1) + f("max_positions", cfg.max_positions, 1, 0) + f("max_drawdown_pct", cfg.max_drawdown_pct, 1, 1) +
    f("max_daily_loss_pct", cfg.max_daily_loss_pct, 0.5, 1) + f("max_position_notional_pct", cfg.max_position_notional_pct, 5, 1) +
    `<button class="btn primary" type="submit" ${dis}>Save risk settings</button>`;
  $("#rk-form").oninput = () => { S.rkDirty = true; };
  $("#rk-form").onsubmit = (e) => { e.preventDefault(); const changes = {}, now = S.risk?.risk_config || S.state?.risk_config || {};
    $$("#rk-form input").forEach((i) => { const isPct = i.name !== "max_positions"; const v = isPct ? parseFloat(i.value) / 100 : parseInt(i.value, 10);
      if (!isNum(v) || Math.abs(v - now[i.name]) > 1e-12) changes[i.name] = v; });
    if (!Object.keys(changes).length) { S.rkDirty = false; return toast("No changes", "warn"); }
    modal(`<h2>Update risk settings</h2>${liveNote()}<pre class="json">${esc(JSON.stringify(changes, null, 2))}</pre>`,
      async () => { const c = await send("UPDATE_RISK_CONFIG", { changes }, "Risk settings"); if (c) { S.rkDirty = false; loadRisk(); } }); };
  renderRiskTables(r);
}
function renderRiskTables(r) {
  table($("#rk-pos"), "rkp", [{ k: "symbol", label: "Coin", l: 1 }, { k: "notional_usd", label: "Value", fmt: (p) => usd(p.notional_usd) },
    { k: "share_of_equity_pct", label: "% equity", fmt: (p) => pct(p.share_of_equity_pct, 1, false) }, { k: "risk_to_stop_usd", label: "Risk to stop", fmt: (p) => usd(p.risk_to_stop_usd) }],
    r.positions, { sortKey: "notional_usd", empty: "No open positions." });
  table($("#rk-viol"), "rkv", [{ k: "ts", label: "Time", l: 1, fmt: (e) => when(e.ts) }, { k: "kind", label: "Kind", l: 1, txt: 1, fmt: (e) => statusPill(e.kind) },
    { k: "message", label: "Detail", l: 1, txt: 1, fmt: (e) => `<span class="muted">${esc(e.message)}</span>` }], r.violations, { sortKey: "ts", empty: "No risk events recorded." });
}

/* -------------------------------------------------------------- strategy */
async function loadStrategy() {
  const [st, sig] = await Promise.all([api("/api/strategy"), api("/api/signals")]); S.strategy = st; const p = st.performance, b = st.backtest;
  $("#st-rule").innerHTML = `<h3>${esc(st.name)} <span class="pill ${st.status === "ACTIVE" ? "ok" : "warn"}">${esc(st.status)}</span> <span class="pill neutral">${esc(st.mode)}</span></h3>
    <table><tbody>${[["Type", st.type], ["Timeframe", st.timeframe], ["Market conditions", st.market_conditions], ["Entry", st.entry], ["Exit", st.exit], ["Stop", st.stop],
      ["Indicators", Object.entries(st.indicators).map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`).join(" · ")],
      ["Risk", `${(st.risk_config.risk_pct * 100).toFixed(2)}% of equity per trade · max ${st.risk_config.max_positions} positions`]]
      .map(([k, v]) => `<tr><td class="l txt muted" style="width:130px">${esc(k)}</td><td class="l txt" style="white-space:normal">${esc(v)}</td></tr>`).join("")}</tbody></table>
    <p class="faint" style="margin:8px 0 0">${esc(st.rule_note)} Risk settings are editable on the Risk page.</p>`;
  $("#st-perf").innerHTML = `<div class="kpis">${kpi("Trades", p.trades)}${kpi("Win rate", p.win_rate_pct == null ? "—" : p.win_rate_pct + "%", `backtest ${b.win_rate_pct}%`)}${kpi("Avg result", rr(p.avg_r), `backtest +${b.avg_r}R`, cls(p.avg_r))}${kpi("Profit factor", p.profit_factor == null ? "—" : p.profit_factor.toFixed(2), `backtest ${b.profit_factor}`)}${kpi("Net P&L", usd(p.net_pnl, true), "", cls(p.net_pnl))}</div>`;
  const alive = S.state?.health?.engine_alive;
  $("#st-symbols").innerHTML = st.symbols.map((s) => `<label class="chk" style="margin:0 14px 8px 0"><input type="checkbox" data-sym="${esc(s.symbol)}" ${s.enabled ? "checked" : ""} ${alive ? "" : "disabled"}> ${esc(s.symbol)}</label>`).join("") +
    `<p class="faint" style="margin:6px 0 0">Unchecking a coin stops NEW entries in it (open positions are still managed). Saved through the engine.</p>`;
  $$("#st-symbols input").forEach((c) => c.onchange = () => { const disabled = $$("#st-symbols input").filter((x) => !x.checked).map((x) => x.dataset.sym);
    send("UPDATE_RISK_CONFIG", { changes: { disabled_symbols: disabled } }, `${c.checked ? "Enable" : "Disable"} ${c.dataset.sym}`); });
  table($("#st-signals"), "sig", [
    { k: "symbol", label: "Coin", l: 1 }, { k: "close", label: "Close", fmt: (r) => px(r.close) },
    { k: "entry_level", label: "55d high", fmt: (r) => px(r.entry_level) }, { k: "exit_level", label: "20d low", fmt: (r) => px(r.exit_level) },
    { k: "atr", label: "ATR20", fmt: (r) => px(r.atr) },
    { k: "long_entry", label: "Entry signal", fmt: (r) => r.long_entry ? '<span class="pill ok">YES</span>' : '<span class="faint">no</span>' },
    { k: "long_exit", label: "Exit signal", fmt: (r) => r.long_exit ? '<span class="pill bad">YES</span>' : '<span class="faint">no</span>' },
    { k: "action", label: "Engine did", fmt: (r) => statusPill(r.action) }, { k: "note", label: "Why", l: 1, txt: 1, fmt: (r) => `<span class="muted">${esc(r.note)}</span>` },
  ], sig.items, { sortKey: "symbol", sortDir: 1, empty: sig.bar_date ? "No signals." : "No daily check recorded yet (runs after each daily close, 05:30 IST)." });
}

/* ---------------------------------------------------------------- system */
async function loadSystem() {
  const s = await api("/api/system"); S.system = s;
  $("#sy-comps").innerHTML = s.components.map((c) => `<div class="comp"><span class="dot ${c.status === "OK" ? "ok" : c.status === "WARN" ? "warn" : "bad"}"></span>
    <div><b>${esc(c.name)}</b><div class="role">${esc(c.role)}</div></div><div class="detail">${esc(c.detail)}${c.last_activity ? ` <span class="faint">· ${when(c.last_activity)}</span>` : ""}</div></div>`).join("");
  $("#sy-note").textContent = s.note;
  const kinds = [...new Set(s.events.map((e) => e.kind))].sort(), sel = $("#sy-kind"), cur = sel.value;
  sel.innerHTML = `<option value="">All events</option>` + kinds.map((k) => `<option ${k === cur ? "selected" : ""}>${esc(k)}</option>`).join("");
  const rows = s.events.filter((e) => !sel.value || e.kind === sel.value);
  table($("#sy-events"), "sye", [{ k: "ts", label: "Time", l: 1, fmt: (e) => when(e.ts) }, { k: "level", label: "Level", fmt: (e) => statusPill(e.level === "INFO" ? "DONE" : e.level === "WARN" ? "PENDING" : "FAILED").replace(/>[A-Z]+</, `>${esc(e.level)}<`) },
    { k: "kind", label: "Kind", l: 1, txt: 1 }, { k: "symbol", label: "Coin", l: 1 }, { k: "message", label: "Message", l: 1, txt: 1, fmt: (e) => esc(e.message) }],
    rows, { sortKey: "ts", empty: "No events yet." });
}
$("#sy-kind").onchange = () => loadSystem();

/* ------------------------------------------------------------- assistant */
const SUGGEST = ["Why did the bot enter its open positions?", "What are the current stops and take-profits?", "What is my current risk exposure?",
  "Why is my worst position losing?", "What caused the latest trade to close?", "How is live performance compared with the backtest?",
  "Which coins are closest to a breakout?", "How much capital is available?"];
function renderChat() {
  $("#chat-suggest").innerHTML = SUGGEST.map((q) => `<button class="btn small" type="button">${esc(q)}</button>`).join("");
  $$("#chat-suggest button").forEach((b) => b.onclick = () => { $("#chat-input").value = b.textContent; $("#chat-form").requestSubmit(); });
  $("#chat-log").innerHTML = S.chat.length ? S.chat.map((m) => `<div class="msg ${m.role === "user" ? "user" : m.error ? "err" : ""}"><div class="who">${m.role === "user" ? "You" : "Assistant" + (m.model ? ` · ${esc(m.model)}` : "")}</div><div class="body">${esc(m.text)}</div></div>`).join("")
    : `<div class="faint">Ask about positions, trades, orders, risk or signals. Answers use this bot's records only and show their sources.</div>`;
  $("#chat-log").scrollTop = 1e9;
}
$("#chat-form").onsubmit = async (e) => {
  e.preventDefault(); const q = $("#chat-input").value.trim(); if (!q) return;
  S.chat.push({ role: "user", text: q }); $("#chat-input").value = ""; $("#chat-send").disabled = true;
  S.chat.push({ role: "assistant", text: "Thinking…" }); renderChat();
  try { const r = await api("/api/chat", { method: "POST", body: JSON.stringify({ message: q, history: S.chat.slice(0, -2).filter((m) => !m.error).map((m) => ({ role: m.role, text: m.text })) }) });
    S.chat[S.chat.length - 1] = r.error ? { role: "assistant", text: r.error, error: true } : { role: "assistant", text: r.answer, model: r.model };
  } catch (er) { S.chat[S.chat.length - 1] = { role: "assistant", text: er.message, error: true }; }
  $("#chat-send").disabled = false; renderChat();
};

/* ------------------------------------------------------------------ boot */
(async function boot() {
  try { onState(await api("/api/state")); } catch (e) { $("#global-alerts").innerHTML = `<div class="alert bad">Cannot reach the terminal API: ${esc(e.message)}</div>`; }
  connect();
  const v = location.hash.slice(1); show($(`#nav button[data-view="${v}"]`) ? v : "overview");
  // views without a push channel refresh on a timer while visible
  setInterval(() => { if (document.hidden) return; if (S.view === "markets") loadMarkets().catch(() => {}); if (S.view === "risk") loadRisk().catch(() => {});
    if (S.view === "system") loadSystem().catch(() => {}); }, 10000);
  setInterval(() => { if (!document.hidden && S.view === "chart") loadChart(false).catch(() => {}); }, 30000);
})();
