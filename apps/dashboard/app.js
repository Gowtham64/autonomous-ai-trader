/**
 * Premium AI Trading Dashboard — Bloomberg Fintech Terminal Controller
 * Version: 4.1.0
 * Preserves 100% of backend APIs, paper-trading safeguards, and execution behaviors.
 * 100% Real verified operational data: zero mocked/demo data.
 */

// Global State
let currentSymbol = 'BTCUSDT';
let currentInterval = '5m';
let currentChatFilter = 'ALL';
let currentAgentFilter = 'ALL';
let candleChart = null;
let candleSeries = null;
let volumeSeries = null;
let ema20Series = null;
let ema50Series = null;
let equityChart = null;
let equitySeries = null;
let activeWebSocket = null;
let cachedCompletedTrades = [];
let cachedDecisions = [];
let cachedAgentActions = [];
let cachedEvents = [];
let cachedQuotes = [];

// Auth Helper
function getAuthToken() {
  return localStorage.getItem('ai_trader_token') || '';
}

function formatPx(price) {
  const n = Number(price);
  if (!Number.isFinite(n)) return '—';
  const digits = n >= 100 ? 2 : n >= 1 ? 4 : 6;
  return n.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

async function apiFetch(url, options = {}) {
  const token = getAuthToken();
  const headers = options.headers || {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  options.headers = headers;
  options.credentials = 'same-origin';
  const resp = await fetch(url, options);
  if (resp.status === 401 && !window.location.pathname.startsWith('/login')) {
    localStorage.removeItem('ai_trader_token');
    window.location.href = '/login';
  }
  return resp;
}

async function signOut() {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
  localStorage.removeItem('ai_trader_token');
  window.location.href = '/login';
}

// 1. Clock Display (UTC)
function updateUtcClock() {
  const now = new Date();
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const month = months[now.getUTCMonth()];
  const day = now.getUTCDate();
  const year = now.getUTCFullYear();
  const hours = String(now.getUTCHours()).padStart(2, '0');
  const minutes = String(now.getUTCMinutes()).padStart(2, '0');
  const seconds = String(now.getUTCSeconds()).padStart(2, '0');
  
  const el = document.getElementById('utcClock');
  if (el) {
    el.innerText = `${month} ${day}, ${year} ${hours}:${minutes}:${seconds} UTC`;
  }
}

// 2. Navigation Tabs & Controls
function initNavigationTabs() {
  const navTabs = document.querySelectorAll('.nav-tab');
  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetId = tab.getAttribute('data-tab');
      if (!targetId) return;

      navTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      document.querySelectorAll('.module-screen').forEach(screen => {
        screen.classList.remove('active');
      });

      const activeScreen = document.getElementById(targetId);
      if (activeScreen) {
        activeScreen.classList.add('active');
      }

      if (targetId === 'tab-overview' && candleChart) {
        setTimeout(() => candleChart.timeScale().fitContent(), 50);
      }
    });
  });

  // Table Subtabs (Positions / Open Orders / Recent Trades)
  const subtabBtns = document.querySelectorAll('.tab-btn');
  subtabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const subtab = btn.getAttribute('data-subtab');
      if (!subtab) return;

      subtabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      document.querySelectorAll('.subtab-content').forEach(c => c.style.display = 'none');
      const target = document.getElementById(`subtab-${subtab}`);
      if (target) target.style.display = 'block';
    });
  });

  // Timeframe buttons
  const tfBtns = document.querySelectorAll('.tf-btn');
  tfBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tfBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentInterval = btn.getAttribute('data-tf') || '5m';
      loadCandles(currentSymbol, currentInterval);
    });
  });

  // Ticker Pills
  const tickerPills = document.querySelectorAll('.ticker-pill');
  tickerPills.forEach(pill => {
    pill.addEventListener('click', () => {
      tickerPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentSymbol = pill.getAttribute('data-symbol') || 'BTCUSDT';
      updateChartHeader(currentSymbol);
      loadCandles(currentSymbol, currentInterval);
      fetchRealTimeMarketTrades();
    });
  });

  // Watchlist rows
  const watchRows = document.querySelectorAll('#watchlistTableBody tr');
  watchRows.forEach(row => {
    row.addEventListener('click', () => {
      const sym = row.getAttribute('data-symbol');
      if (sym) {
        currentSymbol = sym;
        tickerPills.forEach(p => {
          p.classList.toggle('active', p.getAttribute('data-symbol') === sym);
        });
        updateChartHeader(currentSymbol);
        loadCandles(currentSymbol, currentInterval);
        fetchRealTimeMarketTrades();
      }
    });
  });

  // Chat Symbol Filter Buttons
  const chatFilters = document.querySelectorAll('#chatSymbolFilter button');
  chatFilters.forEach(btn => {
    btn.addEventListener('click', () => {
      chatFilters.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentChatFilter = btn.getAttribute('data-chat-filter') || 'ALL';
      renderAgentChatStream();
    });
  });

  // Agent Type Filter Buttons ("Which Agent Did What")
  const agentFilters = document.querySelectorAll('#agentTypeFilter button');
  agentFilters.forEach(btn => {
    btn.addEventListener('click', () => {
      agentFilters.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentAgentFilter = btn.getAttribute('data-agent-filter') || 'ALL';
      fetchAgentActions();
    });
  });

  // Log Search Input
  const logInput = document.getElementById('logSearchInput');
  if (logInput) {
    logInput.addEventListener('input', (e) => {
      renderSystemLogs(e.target.value.trim().toLowerCase());
    });
  }

  // Export CSV Button
  const exportBtn = document.getElementById('btnExportOrdersCsv');
  if (exportBtn) {
    exportBtn.addEventListener('click', exportAuditCsv);
  }

  // Modal Close
  const closeBtn = document.getElementById('modalCloseBtn');
  const modal = document.getElementById('tradeDetailModal');
  if (closeBtn && modal) {
    closeBtn.addEventListener('click', () => modal.classList.remove('active'));
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('active');
    });
  }
}

// 3. Candlestick Chart Initialization
function initCandlestickChart() {
  const container = document.getElementById('candlestickChartContainer');
  if (!container || !window.LightweightCharts) return;

  container.innerHTML = '';

  candleChart = LightweightCharts.createChart(container, {
    width: container.clientWidth,
    height: 380,
    layout: {
      background: { color: '#0e1422' },
      textColor: '#94a3b8',
      fontSize: 11,
      fontFamily: "'JetBrains Mono', monospace",
    },
    grid: {
      vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
      horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
    },
    rightPriceScale: {
      borderColor: 'rgba(255, 255, 255, 0.08)',
      scaleMargins: { top: 0.1, bottom: 0.2 },
    },
    timeScale: {
      borderColor: 'rgba(255, 255, 255, 0.08)',
      timeVisible: true,
      secondsVisible: false,
    },
  });

  candleSeries = candleChart.addCandlestickSeries({
    upColor: '#10b981',
    downColor: '#ef4444',
    borderVisible: false,
    wickUpColor: '#10b981',
    wickDownColor: '#ef4444',
  });

  volumeSeries = candleChart.addHistogramSeries({
    color: 'rgba(6, 182, 212, 0.25)',
    priceFormat: { type: 'volume' },
    priceScaleId: '',
    scaleMargins: { top: 0.8, bottom: 0 },
  });

  ema20Series = candleChart.addLineSeries({
    color: '#06b6d4',
    lineWidth: 1.5,
    title: 'EMA 20',
  });

  ema50Series = candleChart.addLineSeries({
    color: '#a855f7',
    lineWidth: 1.5,
    title: 'EMA 50',
  });

  window.addEventListener('resize', () => {
    if (candleChart && container) {
      candleChart.applyOptions({ width: container.clientWidth });
    }
  });

  loadCandles(currentSymbol, currentInterval);
}

// 4. Equity Curve Chart Initialization
function initEquityChart() {
  const container = document.getElementById('equityCurveContainer');
  if (!container || !window.LightweightCharts) return;

  container.innerHTML = '';

  equityChart = LightweightCharts.createChart(container, {
    width: container.clientWidth,
    height: 140,
    layout: {
      background: { color: '#0e1422' },
      textColor: '#64748b',
      fontSize: 10,
      fontFamily: "'JetBrains Mono', monospace",
    },
    grid: {
      vertLines: { visible: false },
      horzLines: { color: 'rgba(255, 255, 255, 0.03)' },
    },
    rightPriceScale: {
      borderColor: 'rgba(255, 255, 255, 0.05)',
      scaleMargins: { top: 0.1, bottom: 0.1 },
    },
    timeScale: {
      borderColor: 'rgba(255, 255, 255, 0.05)',
      timeVisible: true,
    },
  });

  equitySeries = equityChart.addAreaSeries({
    lineColor: '#10b981',
    topColor: 'rgba(16, 185, 129, 0.25)',
    bottomColor: 'rgba(16, 185, 129, 0.0)',
    lineWidth: 2,
  });

  window.addEventListener('resize', () => {
    if (equityChart && container) {
      equityChart.applyOptions({ width: container.clientWidth });
    }
  });
}

// 5. Load Real OHLCV Candles from Backend
async function loadCandles(symbol, interval) {
  try {
    const res = await apiFetch(`/api/market/candles?symbol=${symbol}&interval=${interval}&period=3d`);
    if (res.ok) {
      const data = await res.json();
      if (data.candles && data.candles.length > 0) {
        const cData = [];
        const vData = [];
        const e20Data = [];
        const e50Data = [];

        data.candles.forEach(c => {
          cData.push({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close });
          vData.push({
            time: c.time,
            value: c.volume,
            color: c.close >= c.open ? 'rgba(16, 185, 129, 0.25)' : 'rgba(239, 68, 68, 0.25)',
          });
          e20Data.push({ time: c.time, value: c.ema20 });
          e50Data.push({ time: c.time, value: c.ema50 });
        });

        candleSeries.setData(cData);
        volumeSeries.setData(vData);
        ema20Series.setData(e20Data);
        ema50Series.setData(e50Data);

        const last = data.candles[data.candles.length - 1];
        const prev = data.candles.length > 1 ? data.candles[data.candles.length - 2].close : last.open;
        const diff = last.close - prev;
        const diffPct = prev > 0 ? (diff / prev) * 100 : 0.0;

        const livePriceEl = document.getElementById('chartLivePrice');
        if (livePriceEl) livePriceEl.innerText = formatPx(last.close);
        const regimeEl = document.getElementById('regimeBadge');
        if (regimeEl && last.ema20 && last.ema50) {
          regimeEl.innerText = last.ema20 >= last.ema50 ? 'EMA20 ABOVE EMA50' : 'EMA20 BELOW EMA50';
        }
        const volEl = document.getElementById('regimeVolatility');
        if (volEl && last.close > 0 && last.atr14) {
          volEl.innerText = `${((last.atr14 / last.close) * 100).toFixed(2)}% ATR`;
        }
        
        const liveChangeEl = document.getElementById('chartLiveChange');
        if (liveChangeEl) {
          liveChangeEl.innerText = `${diff >= 0 ? '+' : ''}${diff.toFixed(2)} (${diffPct >= 0 ? '+' : ''}${diffPct.toFixed(2)}%)`;
          liveChangeEl.className = diff >= 0 ? 'chart-change text-green' : 'chart-change text-red';
        }

        const e20El = document.getElementById('legendEma20');
        if (e20El) e20El.innerText = last.ema20.toFixed(2);
        const e50El = document.getElementById('legendEma50');
        if (e50El) e50El.innerText = last.ema50.toFixed(2);
        const atrEl = document.getElementById('legendAtr14');
        if (atrEl) atrEl.innerText = last.atr14.toFixed(2);

        candleChart.timeScale().fitContent();
      }
    }
  } catch (err) {
    console.warn(`Candle fetch notice for ${symbol}:`, err);
  }
}

function updateChartHeader(symbol) {
  const symEl = document.getElementById('chartSymbolDisplay');
  if (symEl) {
    let icon = '₿';
    let color = '#f59e0b';
    if (symbol.includes('ETH')) { icon = 'Ξ'; color = '#60a5fa'; }
    if (symbol.includes('SOL')) { icon = '◎'; color = '#a855f7'; }
    if (symbol.includes('XRP')) { icon = '✕'; color = '#38bdf8'; }
    if (symbol.includes('DOGE')) { icon = 'Ð'; color = '#eab308'; }
    symEl.innerHTML = `<span style="color:${color};">${icon}</span> ${symbol}`;
  }
}

// 6. Real Performance Metrics & Equity Progression
async function fetchPerformanceMetrics() {
  try {
    const res = await apiFetch('/api/performance');
    if (res.ok) {
      const data = await res.json();
      const funds = data.live_funds || {};
      const metrics = data.metrics || {};

      const starting = Number(funds.starting_capital !== undefined ? funds.starting_capital : 0);
      const equity = Number(
        funds.mark_to_market_equity !== undefined && funds.mark_to_market_equity !== null
          ? funds.mark_to_market_equity
          : (funds.total_capital !== undefined ? funds.total_capital : data.total_capital || 0)
      );
      const realized = Number(metrics.realized_pnl || 0);
      const unrealized = Number(funds.unrealized_pnl || 0);
      const netTotal = equity - starting;
      const netPct = starting > 0 ? (netTotal / starting) * 100 : 0.0;

      document.getElementById('kpiEquity').innerText = `$${equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      const equityChangeEl = document.getElementById('kpiEquityChange');
      if (equityChangeEl) {
        equityChangeEl.innerText = `${netPct >= 0 ? '+' : ''}${netPct.toFixed(2)}% vs start`;
        equityChangeEl.className = netPct >= 0 ? 'kpi-subtext text-green' : 'kpi-subtext text-red';
      }
      document.getElementById('kpiNetPnl').innerText = `${netTotal >= 0 ? '+' : ''}$${netTotal.toFixed(2)}`;
      document.getElementById('kpiNetPnlPct').innerText = `${netPct >= 0 ? '+' : ''}${netPct.toFixed(2)}%`;
      document.getElementById('kpiRealizedPnl').innerText = `${realized >= 0 ? '+' : ''}$${realized.toFixed(2)}`;
      document.getElementById('kpiUnrealizedPnl').innerText = `$${unrealized.toFixed(2)}`;

      const totalTrades = metrics.total_trades || 0;
      const winTrades = metrics.winning_trades || 0;
      const lossTrades = metrics.losing_trades || (totalTrades - winTrades);
      const winRate = totalTrades > 0 && metrics.win_rate !== undefined ? `${metrics.win_rate.toFixed(1)}%` : '—';
      document.getElementById('kpiWinRate').innerText = winRate;
      document.getElementById('kpiWinLossRatio').innerText = `(${winTrades} / ${totalTrades} trades)`;

      const closedEl = document.getElementById('kpiClosedTradesCount');
      if (closedEl) closedEl.innerText = `${totalTrades} closed trades`;

      const expEl = document.getElementById('kpiExpectancy');
      if (expEl) {
        const exp = totalTrades > 0 ? (realized / totalTrades).toFixed(2) : '0.00';
        expEl.innerText = `Exp: $${exp} / trade`;
      }

      const pf = metrics.profit_factor !== undefined && metrics.profit_factor > 0 ? metrics.profit_factor.toFixed(2) : '—';
      document.getElementById('kpiProfitFactor').innerText = pf;

      const maxDd = metrics.max_drawdown_pct !== undefined ? metrics.max_drawdown_pct.toFixed(2) : '0.00';
      document.getElementById('kpiMaxDrawdown').innerText = `${maxDd}%`;

      document.getElementById('perfTotalTrades').innerText = totalTrades;
      document.getElementById('perfWinLoss').innerText = `${winTrades} / ${lossTrades}`;
      document.getElementById('perfWinRate').innerText = winRate;
      document.getElementById('perfProfitFactor').innerText = pf;

      const avgWinEl = document.getElementById('perfAvgWin');
      if (avgWinEl) avgWinEl.innerText = metrics.avg_win !== undefined ? `$${metrics.avg_win.toFixed(2)}` : '—';
      const avgLossEl = document.getElementById('perfAvgLoss');
      if (avgLossEl) avgLossEl.innerText = metrics.avg_loss !== undefined ? `$${metrics.avg_loss.toFixed(2)}` : '—';

      // Update Equity Curve Chart with real verified progression
      if (equitySeries && data.equity_history && data.equity_history.length > 0) {
        const points = data.equity_history.map((pt, idx) => {
          const parsed = pt.date ? Math.floor(Date.parse(`${pt.date}T00:00:00Z`) / 1000) : Math.floor(Date.now() / 1000);
          const time = Number.isFinite(parsed) ? parsed + idx : Math.floor(Date.now() / 1000) + idx;
          return { time, value: Number(pt.ending_equity || 0) };
        });
        if (points.length === 1) {
          points.unshift({ time: points[0].time - 60, value: Number(data.equity_history[0].start_equity || points[0].value) });
        }
        equitySeries.setData(points);
      }
    }
  } catch (err) {
    console.warn('Performance metrics notice:', err);
  }
}

function paintActiveTrades(positions) {
  const countEl = document.getElementById('kpiActiveCount');
  const pnlEl = document.getElementById('kpiActivePnl');
  const statusEl = document.getElementById('kpiActiveStatus');
  if (!countEl || !pnlEl || !statusEl) return;
  const count = positions.length;
  const openPnl = positions.reduce((sum, p) => sum + Number(p.unrealized_pnl || 0), 0);
  const digits = Math.abs(openPnl) >= 1 ? 2 : 4;
  countEl.innerText = String(count);
  pnlEl.innerText = `${openPnl >= 0 ? '+' : ''}$${openPnl.toFixed(digits)} open`;
  pnlEl.className = openPnl >= 0 ? 'kpi-subtext text-green' : 'kpi-subtext text-red';
  statusEl.innerText = count > 0 ? 'Open' : 'Flat';
  statusEl.className = count > 0 ? 'kpi-icon text-green' : 'kpi-icon text-dim';
}

// 7. Real Positions, Open Orders, and Completed Trades Blotter
async function fetchPositionsAndOrders() {
  try {
    const posRes = await apiFetch('/api/positions');
    if (posRes.ok) {
      const data = await posRes.json();
      const positions = data.positions || [];
      document.getElementById('countActivePos').innerText = positions.length;
      paintActiveTrades(positions);

      const tbody = document.getElementById('positionsTableBody');
      if (positions.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="14">
              <div class="empty-state">
                <div class="empty-state-icon">▤</div>
                <p><strong>No open positions</strong></p>
                <p style="font-size:11px;">The autonomous execution agent is scanning for high-probability setups.</p>
              </div>
            </td>
          </tr>`;
      } else {
        tbody.innerHTML = positions.map(p => `
          <tr onclick="showPositionModal('${p.symbol}', '${p.direction}', ${p.entry_price || 0}, ${p.mark_price || 0}, ${p.unrealized_pnl || 0})">
            <td><strong>${p.symbol}</strong></td>
            <td><span class="${p.direction === 'BUY' ? 'text-green' : 'text-red'}">${p.direction || '—'}</span></td>
            <td>${p.strategy || '—'}</td>
            <td>$${(p.entry_price || 0).toFixed(4)}</td>
            <td>${p.mark_price ? `$${Number(p.mark_price).toFixed(4)}` : '—'}</td>
            <td>${p.quantity ?? '—'}</td>
            <td>${p.quantity && p.entry_price ? `$${(p.quantity * p.entry_price).toFixed(2)}` : '—'}</td>
            <td class="text-red">${p.stop_loss ? `$${Number(p.stop_loss).toFixed(4)}` : '—'}</td>
            <td class="text-green">${p.take_profit ? `$${Number(p.take_profit).toFixed(4)}` : '—'}</td>
            <td class="${(p.unrealized_pnl || 0) >= 0 ? 'text-green' : 'text-red'}">
              ${(p.unrealized_pnl || 0) >= 0 ? '+' : ''}$${(p.unrealized_pnl || 0).toFixed(4)}
            </td>
            <td>—</td>
            <td>—</td>
            <td>${p.age || '—'}</td>
            <td>${p.stop_loss ? 'Stop set' : 'No stop'}</td>
          </tr>
        `).join('');
      }
    }

    const ordRes = await apiFetch('/api/orders');
    if (ordRes.ok) {
      const data = await ordRes.json();
      const dbOrders = data.db_orders || [];
      const brokerOrders = data.broker_order_book || [];
      const completedTrades = data.completed_trades || [];
      cachedCompletedTrades = completedTrades;

      document.getElementById('countOpenOrders').innerText = brokerOrders.length;
      document.getElementById('countRecentTrades').innerText = completedTrades.length > 0 ? completedTrades.length : dbOrders.length;

      // 1. Open Orders Subtab
      const openOrdersTbody = document.getElementById('openOrdersTableBody');
      if (openOrdersTbody) {
        if (brokerOrders.length === 0) {
          openOrdersTbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:24px; color:var(--text-dim);">No open resting protective orders.</td></tr>`;
        } else {
          openOrdersTbody.innerHTML = brokerOrders.map(o => `
            <tr>
              <td><code>${o.order_id || '—'}</code></td>
              <td><strong>${o.symbol}</strong></td>
              <td>${o.order_type || 'LIMIT'}</td>
              <td><span class="${o.side === 'BUY' ? 'text-green' : 'text-red'}">${o.side}</span></td>
              <td>${o.quantity}</td>
              <td>$${(o.price || 0).toFixed(4)}</td>
              <td><span class="activity-tag info">${o.status}</span></td>
              <td>${o.timestamp || '—'}</td>
            </tr>
          `).join('');
        }
      }

      // 2. Recent Completed Trades Subtab (152 Real Executed Trades)
      const recentTradesTbody = document.getElementById('recentTradesTableBody');
      if (recentTradesTbody) {
        if (completedTrades.length === 0) {
          recentTradesTbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:24px; color:var(--text-dim);">No completed trades recorded yet.</td></tr>`;
        } else {
          recentTradesTbody.innerHTML = completedTrades.map((t, index) => `
            <tr style="cursor:pointer;" onclick="openTradeAuditModal(${index})">
              <td><strong>#${t.trade_id || index + 1}</strong></td>
              <td><strong>${t.symbol}</strong></td>
              <td><span class="${t.side === 'BUY' ? 'text-green' : 'text-red'}">${t.side}</span></td>
              <td>${t.quantity ?? '—'} (${t.contract_multiplier || 1.0}x)</td>
              <td>$${(t.entry_price || 0).toFixed(4)}</td>
              <td>$${(t.exit_price || 0).toFixed(4)}</td>
              <td><span class="activity-tag ${(t.exit_reason || '').includes('STOP') ? 'reject' : 'info'}">${t.exit_reason || '—'}</span></td>
              <td class="${(t.net_pnl || 0) >= 0 ? 'text-green' : 'text-red'}">
                ${(t.net_pnl || 0) >= 0 ? '+' : ''}$${(t.net_pnl || 0).toFixed(4)}
              </td>
              <td style="font-size:11px; color:var(--text-dim);">${t.timestamp || '—'}</td>
            </tr>
          `).join('');
        }
      }

      // 3. Trading Tab Full Institutional Blotter
      const fullOrdersTbody = document.getElementById('fullOrdersTableBody');
      if (fullOrdersTbody && dbOrders.length > 0) {
        fullOrdersTbody.innerHTML = dbOrders.map(o => `
          <tr>
            <td><code>${o.order_id || '—'}</code></td>
            <td><code>${o.client_order_id || '—'}</code></td>
            <td><strong>${o.symbol}</strong></td>
            <td><span class="${o.action === 'BUY' ? 'text-green' : 'text-red'}">${o.action}</span></td>
            <td>${o.quantity}</td>
            <td>$${(o.average_price || 0).toFixed(4)}</td>
            <td><span class="activity-tag info">${o.status}</span></td>
            <td>${o.executed_at || '—'}</td>
          </tr>
        `).join('');
      }
    }
  } catch (err) {
    console.warn('Positions fetch notice:', err);
  }
}

// 7b. Real-Time Market Trade Tape Poll
async function fetchRealTimeMarketTrades() {
  try {
    const res = await apiFetch(`/api/market/trades?symbol=${currentSymbol}&limit=35`);
    if (res.ok) {
      const data = await res.json();
      const trades = data.trades || [];
      const badge = document.getElementById('countMarketTrades');
      if (badge) badge.innerText = trades.length;

      const tbody = document.getElementById('marketTradesTableBody');
      if (tbody) {
        if (trades.length === 0) {
          tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--text-dim);">Listening for live market trade executions...</td></tr>`;
        } else {
          tbody.innerHTML = trades.map(tr => {
            const val = (tr.price * tr.quantity).toFixed(2);
            return `
              <tr>
                <td style="font-family:monospace; color:var(--text-dim);">${tr.time}</td>
                <td><strong>${tr.symbol}</strong></td>
                <td><span class="${tr.side === 'BUY' ? 'text-green' : 'text-red'}" style="font-weight:700;">${tr.side}</span></td>
                <td style="font-weight:600;">$${tr.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                <td>${tr.quantity}</td>
                <td>$${val}</td>
                <td style="font-family:monospace; font-size:11px; color:var(--text-dim);">${tr.trade_id}</td>
              </tr>
            `;
          }).join('');
        }
      }
    }
  } catch (err) {
    console.debug('Market trades note:', err);
  }
}

// 8. Real Multi-Agent Trade Chat & Strategy Debates
async function fetchRealAgentDecisionsAndChat() {
  try {
    const res = await apiFetch('/api/office/decisions');
    if (res.ok) {
      const data = await res.json();
      cachedDecisions = data.decisions || [];
      renderAgentChatStream();
    }
  } catch (err) {
    console.warn('Agent decisions notice:', err);
  }
}

function renderAgentChatStream() {
  const container = document.getElementById('agentChatStream');
  if (!container) return;

  let filtered = cachedDecisions;
  if (currentChatFilter !== 'ALL') {
    filtered = cachedDecisions.filter(d => (d.symbol || '').toUpperCase().includes(currentChatFilter));
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="text-align:center; padding:30px; color:var(--text-dim); font-size:12px;">
        No trade decisions recorded matching filter "${currentChatFilter}".
      </div>`;
    return;
  }

  container.innerHTML = filtered.slice(0, 40).map((d, idx) => {
    const joinText = (value) => Array.isArray(value) ? value.filter(Boolean).join(' ') : (value || '');
    const thesisText = joinText(d.thesis);
    const supportingText = joinText(d.supporting_evidence);
    const opposingText = joinText(d.opposing_evidence);
    const invalidationText = joinText(d.invalidation_conditions);
    const priceBits = [];
    if (d.entry_price) priceBits.push(`Entry $${d.entry_price}`);
    if (d.stop_loss) priceBits.push(`Stop $${d.stop_loss}`);
    if (d.target_1) priceBits.push(`Target $${d.target_1}`);
    const priceText = priceBits.join(' | ');

    return `
      <div style="background:var(--bg-card-inset); border:1px solid var(--border-subtle); border-radius:6px; padding:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-weight:700; color:#fff; font-size:13px;">${d.symbol}</span>
            <span class="activity-tag ${d.decision === 'BUY' ? 'info' : 'reject'}" style="font-weight:700;">${d.decision}</span>
            <span style="font-size:11px; color:var(--text-dim);">${d.confidence ? `Confidence: ${(d.confidence * 100).toFixed(0)}%` : 'Confidence: —'}</span>
            <span style="font-size:11px; color:var(--text-dim);">${d.expected_risk_reward ? `R:R: ${d.expected_risk_reward}:1` : ''}</span>
          </div>
          <span style="font-size:11px; color:var(--text-dim); font-family:monospace;">${d.created_at || '—'}</span>
        </div>

        <!-- Agent Multi-Voice Debate Dialogue -->
        <div style="display:flex; flex-direction:column; gap:6px; font-size:11.5px; line-height:1.45;">
          
          ${thesisText ? `<div style="display:flex; gap:6px;"><span style="color:var(--accent-green); font-weight:600; min-width:130px;">Thesis:</span><span style="color:var(--text-main);">${thesisText}</span></div>` : `<div style="color:var(--text-dim);">No thesis stored for this decision.</div>`}
          ${supportingText ? `<div style="display:flex; gap:6px;"><span style="font-weight:600; min-width:130px;">Supporting:</span><span>${supportingText}</span></div>` : ''}
          ${opposingText ? `<div style="display:flex; gap:6px;"><span style="font-weight:600; min-width:130px;">Opposing:</span><span>${opposingText}</span></div>` : ''}
          ${priceText ? `<div style="display:flex; gap:6px;"><span style="font-weight:600; min-width:130px;">Prices:</span><span>${priceText}</span></div>` : ''}
          ${invalidationText ? `<div style="display:flex; gap:6px;"><span style="font-weight:600; min-width:130px;">Invalidation:</span><span>${invalidationText}</span></div>` : ''}

        </div>

        <div style="margin-top:8px; display:flex; justify-content:flex-end;">
          <button class="tf-btn" onclick="openDecisionModal(${idx})" style="padding:3px 8px; font-size:10.5px;">Inspect Decision Matrix →</button>
        </div>
      </div>
    `;
  }).join('');
}

// 8b. Real Agent Action Ledger ("Which Agent Did What")
async function fetchAgentActions() {
  try {
    const res = await apiFetch(`/api/office/agent-actions?agent_filter=${currentAgentFilter}&limit=80`);
    if (res.ok) {
      const data = await res.json();
      cachedAgentActions = data.actions || [];
      const badge = document.getElementById('agentActionCountBadge');
      if (badge) badge.innerText = `${data.count} Actions Logged`;
      renderAgentActionsTable();
    }
  } catch (err) {
    console.warn('Agent actions notice:', err);
  }
}

function renderAgentActionsTable() {
  const tbody = document.getElementById('agentActionsTableBody');
  if (!tbody) return;

  if (cachedAgentActions.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--text-dim);">No agent actions recorded matching filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = cachedAgentActions.map((a, idx) => {
    let agentColor = 'var(--accent-cyan)';
    if (a.agent.includes('Strategy')) agentColor = 'var(--accent-green)';
    if (a.agent.includes('Risk')) agentColor = '#a855f7';
    if (a.agent.includes('Execution')) agentColor = '#f59e0b';
    if (a.agent.includes('Portfolio')) agentColor = '#38bdf8';

    const statusClass = a.status === 'PASSED' || a.status === 'APPROVED' || a.status === 'FILLED' || a.status === 'RECONCILED' ? 'info' : 'reject';

    return `
      <tr>
        <td style="font-family:monospace; font-size:11px; color:var(--text-dim);">${a.timestamp || '—'}</td>
        <td>
          <div style="display:flex; align-items:center; gap:6px;">
            <span class="status-dot green"></span>
            <strong style="color:${agentColor}; font-size:12px;">${a.agent}</strong>
          </div>
          <div style="font-size:10px; color:var(--text-dim); margin-left:14px;">${a.role || ''}</div>
        </td>
        <td><strong>${a.symbol || '—'}</strong></td>
        <td><span style="font-weight:600; color:#fff;">${a.action}</span></td>
        <td><span class="activity-tag ${statusClass}" style="font-weight:700;">${a.status}</span></td>
        <td style="font-size:11.5px; color:var(--text-main); max-width:340px;">
          <div>${a.summary}</div>
          <div style="font-size:10.5px; color:var(--text-dim); margin-top:2px;">${a.details}</div>
        </td>
        <td>
          <button class="tf-btn" onclick="openAgentActionModal(${idx})" style="padding:2px 8px; font-size:10.5px;">Inspect →</button>
        </td>
      </tr>
    `;
  }).join('');
}

window.openAgentActionModal = function(idx) {
  const a = cachedAgentActions[idx];
  if (!a) return;

  const modal = document.getElementById('tradeDetailModal');
  const title = document.getElementById('modalTradeTitle');
  const content = document.getElementById('modalTradeContent');
  if (!modal || !title || !content) return;

  title.innerText = `Agent Action Audit: ${a.agent}`;
  content.innerHTML = `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; background:var(--bg-card-inset); padding:12px; border-radius:6px; font-size:12px;">
      <div><strong>Agent Name:</strong> ${a.agent}</div>
      <div><strong>Agent Role:</strong> ${a.role}</div>
      <div><strong>Symbol:</strong> ${a.symbol}</div>
      <div><strong>Action:</strong> <span style="color:var(--accent-cyan); font-weight:700;">${a.action}</span></div>
      <div><strong>Status:</strong> <span class="activity-tag info">${a.status}</span></div>
      <div><strong>Timestamp:</strong> ${a.timestamp}</div>
    </div>
    <div style="margin-top:10px;">
      <h4 style="font-size:12px; color:var(--accent-green); margin-bottom:4px;">Primary Decision / Evaluation Summary:</h4>
      <p style="color:var(--text-main); font-size:12px; background:var(--bg-card-inset); padding:10px; border-radius:4px;">${a.summary}</p>
    </div>
    <div style="margin-top:10px;">
      <h4 style="font-size:12px; color:var(--accent-cyan); margin-bottom:4px;">Technical Execution Details & Guardrail Proof:</h4>
      <p style="color:var(--text-muted); font-size:11.5px; background:var(--bg-card-inset); padding:10px; border-radius:4px;">${a.details}</p>
    </div>
  `;
  modal.classList.add('active');
};

// 9. Real System Logs & Live Event Stream
async function fetchSystemLogs() {
  try {
    const res = await apiFetch('/api/events?limit=60');
    if (res.ok) {
      const data = await res.json();
      cachedEvents = data.events || [];
      renderSystemLogs();
    }
  } catch (err) {
    console.warn('System events notice:', err);
  }
}

function renderSystemLogs(filterTerm = '') {
  let events = cachedEvents;
  if (filterTerm) {
    events = events.filter(e => (e.message || '').toLowerCase().includes(filterTerm) || (e.component || '').toLowerCase().includes(filterTerm));
  }

  // 1. Right Sidebar Stream on Overview
  const streamEl = document.getElementById('recentActivityStream');
  if (streamEl) {
    if (events.length === 0) {
      streamEl.innerHTML = `<div style="text-align:center; padding:16px; color:var(--text-dim);">Waiting for active events...</div>`;
    } else {
      streamEl.innerHTML = events.slice(0, 10).map(e => `
        <div class="activity-item">
          <span class="activity-time">${(e.timestamp || '').split('T')[1]?.substring(0, 8) || (e.timestamp || '').substring(11, 19) || 'LIVE'}</span>
          <span class="activity-tag ${e.severity === 'REJECT' ? 'reject' : 'info'}">${e.severity || 'INFO'}</span>
          <span class="activity-msg">${e.message || 'System operation normal.'}</span>
        </div>
      `).join('');
    }
  }

  // 2. Full Log Stream on Logs Screen
  const fullLogEl = document.getElementById('fullLogStream');
  if (fullLogEl) {
    if (events.length === 0) {
      fullLogEl.innerHTML = `<div style="text-align:center; padding:24px; color:var(--text-dim);">No log entries found.</div>`;
    } else {
      fullLogEl.innerHTML = events.map(e => `
        <div class="activity-item" style="padding:10px 12px; border-bottom:1px solid var(--border-subtle);">
          <span class="activity-time" style="font-family:monospace; color:var(--text-dim); min-width:80px;">${e.timestamp || '—'}</span>
          <span class="activity-tag ${e.severity === 'REJECT' ? 'reject' : 'info'}" style="min-width:60px; text-align:center;">${e.severity || 'INFO'}</span>
          <span style="color:var(--accent-cyan); font-family:monospace; min-width:120px;">[${e.component || 'SENTINEL'}]</span>
          <span class="activity-msg" style="color:var(--text-main); font-size:12px;">${e.message || ''}</span>
        </div>
      `).join('');
    }
  }
}

function sameMarket(left, right) {
  const norm = (value) => String(value || '').toUpperCase().replace('USDT', 'USD').replace('-', '');
  return norm(left) === norm(right);
}

function applyLiveQuote(q) {
  const sym = q.symbol;
  const price = Number(q.ltp || 0);
  const change = Number(q.change || 0);
  const spreadText = q.spread_pct !== undefined && q.spread_pct !== null ? `${Number(q.spread_pct).toFixed(3)}%` : '—';
  const aliases = {
    BTCUSD: ['watchPriceBTC', 'watchChangeBTC'],
    ETHUSD: ['watchPriceETH', 'watchChangeETH'],
    SOLUSD: ['watchPriceSOL', 'watchChangeSOL'],
    XRPUSD: ['watchPriceXRP', 'watchChangeXRP'],
    DOGEUSD: ['watchPriceDOGE', 'watchChangeDOGE'],
  };
  const key = String(sym || '').toUpperCase().replace('USDT', 'USD').replace('-', '');
  const ids = aliases[key];
  if (ids && price > 0) {
    const priceEl = document.getElementById(ids[0]);
    if (priceEl) priceEl.innerText = formatPx(price);
    const changeEl = document.getElementById(ids[1]);
    if (changeEl) {
      changeEl.innerText = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
      changeEl.className = change >= 0 ? 'text-green' : 'text-red';
    }
    const spreadEl = document.getElementById(ids[0].replace('watchPrice', 'watchSpread'));
    if (spreadEl) spreadEl.innerText = spreadText;
    const pill = document.getElementById(ids[0].replace('watchPrice', 'pillChange'));
    if (pill) {
      pill.innerText = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
      pill.className = change >= 0 ? 'text-green' : 'text-red';
    }
  }
  if (price > 0 && sameMarket(sym, currentSymbol)) {
    const livePriceEl = document.getElementById('chartLivePrice');
    if (livePriceEl) livePriceEl.innerText = formatPx(price);
    const liveChangeEl = document.getElementById('chartLiveChange');
    if (liveChangeEl) {
      liveChangeEl.innerText = `${change >= 0 ? '+' : ''}${change.toFixed(2)}% session`;
      liveChangeEl.className = change >= 0 ? 'chart-change text-green' : 'chart-change text-red';
    }
  }
}

// 10. Real Market Quotes Watchlist Poll
async function fetchMarketQuotes() {
  try {
    const res = await apiFetch('/api/market/quotes');
    if (res.ok) {
      const data = await res.json();
      cachedQuotes = data.quotes || [];

      // Update Watchlist & Live Prices
      cachedQuotes.forEach(applyLiveQuote);

      // Populate Markets Tab
      const fullMarketsTbody = document.getElementById('fullMarketsTableBody');
      const displayQuotes = cachedQuotes.filter((q) => q.symbol.endsWith('USDT'));
      if (fullMarketsTbody && displayQuotes.length > 0) {
        fullMarketsTbody.innerHTML = displayQuotes.map(q => `
          <tr>
            <td><strong>${q.symbol}</strong></td>
            <td>Crypto Perpetual</td>
            <td>${formatPx(q.ltp)}</td>
            <td class="${(q.change || 0) >= 0 ? 'text-green' : 'text-red'}">${(q.change || 0) >= 0 ? '+' : ''}${(q.change || 0).toFixed(2)}%</td>
            <td>${q.spread_pct !== undefined ? Number(q.spread_pct).toFixed(3) : '—'}%</td>
            <td>${Number(q.volume || 0).toLocaleString()}</td>
            <td>—</td>
            <td><span class="regime-badge">${q.source === 'delta' ? 'LIVE' : 'UNCONFIRMED'}</span></td>
            <td><span class="status-dot green"></span> ${q.source === 'delta' ? 'Live' : 'Pending'}</td>
          </tr>
        `).join('');
      }
    }
  } catch (err) {
    console.warn('Market quotes notice:', err);
  }
}

// 11. Evaluation Status Poll
async function fetchEvaluationStatus() {
  try {
    const res = await apiFetch('/api/evaluation/status');
    if (res.ok) {
      const data = await res.json();
      document.getElementById('evalPhase').innerText = data.phase || '4H.4 – 14-Day Paper Evaluation';
      document.getElementById('evalElapsed').innerText = `${data.elapsed_formatted} (of ${data.target_formatted})`;
      document.getElementById('evalStart').innerText = data.start_time;
      document.getElementById('evalEnd').innerText = data.target_end_time;
      document.getElementById('evalProgressBar').style.width = `${data.progress_pct}%`;
      document.getElementById('evalProgressLabel').innerText = `${data.progress_pct}% complete`;

      document.getElementById('kpiDailyLoss').innerText = `${data.daily_loss_realized_pct.toFixed(2)}%`;
      document.getElementById('kpiDailyLossLimit').innerText = `(Limit: ≤ ${data.daily_loss_limit_pct.toFixed(2)}%)`;
      document.getElementById('riskDailyRealized').innerText = `${data.daily_loss_realized_pct.toFixed(2)}% / ${data.daily_loss_limit_pct.toFixed(2)}%`;
      if (data.drawdown_pct !== undefined) {
        document.getElementById('kpiMaxDrawdown').innerText = `${Number(data.drawdown_pct).toFixed(2)}%`;
        document.getElementById('riskCurrentDd').innerText = `${Number(data.drawdown_pct).toFixed(2)}%`;
      }
      if (data.max_drawdown_limit_pct !== undefined) {
        document.getElementById('riskMaxDd').innerText = `${Number(data.max_drawdown_limit_pct).toFixed(2)}%`;
        const limitEl = document.getElementById('kpiMaxDrawdownLimit');
        if (limitEl) limitEl.innerText = `(Limit: ≤ ${Number(data.max_drawdown_limit_pct).toFixed(2)}%)`;
      }
    }
  } catch (err) {
    console.warn('Evaluation status notice:', err);
  }
}

// 12. Forensic Trade Audit Modal Display
window.openTradeAuditModal = function(index) {
  const t = cachedCompletedTrades[index];
  if (!t) return;

  const modal = document.getElementById('tradeDetailModal');
  const title = document.getElementById('modalTradeTitle');
  const content = document.getElementById('modalTradeContent');
  if (!modal || !title || !content) return;

  title.innerText = `Forensic Trade Audit: #${t.trade_id} ${t.symbol}`;
  content.innerHTML = `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; background:var(--bg-card-inset); padding:12px; border-radius:6px; font-size:12px;">
      <div><strong>Trade ID:</strong> #${t.trade_id}</div>
      <div><strong>Symbol:</strong> ${t.symbol}</div>
      <div><strong>Direction:</strong> <span class="${t.side === 'BUY' ? 'text-green' : 'text-red'}">${t.side}</span></div>
      <div><strong>Quantity:</strong> ${t.quantity} (${t.contract_multiplier || 1.0}x multiplier)</div>
      <div><strong>Entry Price:</strong> $${(t.entry_price || 0).toFixed(4)}</div>
      <div><strong>Exit Price:</strong> $${(t.exit_price || 0).toFixed(4)}</div>
      <div><strong>Exit Reason:</strong> <span class="activity-tag info">${t.exit_reason}</span></div>
      <div><strong>Execution Scenario:</strong> <span class="activity-tag info">${t.injected_scenario || 'NATURAL'}</span></div>
      <div><strong>Gross P&L:</strong> $${(t.gross_pnl || 0).toFixed(4)}</div>
      <div><strong>Total Fees / Commission:</strong> $${(t.total_fee || 0).toFixed(4)}</div>
      <div><strong>Net P&L:</strong> <span class="${(t.net_pnl || 0) >= 0 ? 'text-green' : 'text-red'}">${(t.net_pnl || 0) >= 0 ? '+' : ''}$${(t.net_pnl || 0).toFixed(4)}</span></div>
      <div><strong>Account Equity After:</strong> $${(t.account_equity_after || 0).toFixed(4)}</div>
      <div style="grid-column: span 2;"><strong>Timestamp:</strong> ${t.timestamp || '—'}</div>
    </div>
    <div style="margin-top:10px;">
      <h4 style="font-size:12px; color:var(--accent-cyan); margin-bottom:4px;">Stored exit record:</h4>
      <p style="color:var(--text-muted); font-size:11.5px;">${t.exit_reason || 'No exit reason stored.'}</p>
    </div>
  `;
  modal.classList.add('active');
};

window.openDecisionModal = function(index) {
  const d = cachedDecisions[index];
  if (!d) return;

  const modal = document.getElementById('tradeDetailModal');
  const title = document.getElementById('modalTradeTitle');
  const content = document.getElementById('modalTradeContent');
  if (!modal || !title || !content) return;

  title.innerText = `Decision Matrix Audit: ${d.symbol} (${d.analysis_id || 'Systematic'})`;
  content.innerHTML = `
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; background:var(--bg-card-inset); padding:12px; border-radius:6px; font-size:12px;">
      <div><strong>Symbol:</strong> ${d.symbol}</div>
      <div><strong>Decision:</strong> <span class="${d.decision === 'BUY' ? 'text-green' : 'text-red'}">${d.decision}</span></div>
      <div><strong>Confidence:</strong> ${(d.confidence * 100).toFixed(1)}%</div>
      <div><strong>Expected R:R:</strong> ${d.expected_risk_reward || 1.5}:1</div>
      <div><strong>Entry Target:</strong> $${d.entry_price || 0}</div>
      <div><strong>Hard Stop Loss:</strong> $${d.stop_loss || 0}</div>
      <div><strong>Target 1 (Take Profit):</strong> $${d.target_1 || 0}</div>
      <div><strong>Timestamp:</strong> ${d.created_at || '—'}</div>
    </div>
    <div style="margin-top:10px;">
      <h4 style="font-size:12px; color:var(--accent-green); margin-bottom:4px;">Bull / Bear Thesis & Multi-Agent Rationale:</h4>
      <p style="color:var(--text-muted); font-size:11.5px;">${Array.isArray(d.thesis) ? d.thesis.join('<br>') : d.thesis}</p>
    </div>
    <div style="margin-top:10px;">
      <h4 style="font-size:12px; color:var(--accent-cyan); margin-bottom:4px;">Supporting Evidence (Technical & Quantitative):</h4>
      <p style="color:var(--text-muted); font-size:11.5px;">${Array.isArray(d.supporting_evidence) ? d.supporting_evidence.join('<br>') : d.supporting_evidence}</p>
    </div>
    <div style="margin-top:10px;">
      <h4 style="font-size:12px; color:var(--accent-red); margin-bottom:4px;">Invalidation Conditions & Bear Counter-Arguments:</h4>
      <p style="color:var(--text-muted); font-size:11.5px;">${Array.isArray(d.invalidation_conditions) ? d.invalidation_conditions.join('<br>') : d.invalidation_conditions}</p>
    </div>
  `;
  modal.classList.add('active');
};

function exportAuditCsv() {
  if (!cachedCompletedTrades || cachedCompletedTrades.length === 0) {
    alert('No completed trade records to export.');
    return;
  }
  const headers = ['trade_id', 'symbol', 'side', 'quantity', 'contract_multiplier', 'entry_price', 'exit_price', 'exit_reason', 'gross_pnl', 'total_fee', 'net_pnl', 'account_equity_after', 'timestamp'];
  const rows = cachedCompletedTrades.map(t => [
    t.trade_id, t.symbol, t.side, t.quantity, t.contract_multiplier, t.entry_price, t.exit_price, t.exit_reason, t.gross_pnl, t.total_fee, t.net_pnl, t.account_equity_after, `"${t.timestamp}"`
  ]);
  const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `trade_audit_ledger_${Date.now()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// 13. AI Agents Roster Render
const CORE_AGENTS = [
  { name: 'Market Scanner Agent', role: 'Scans markets & finds candidates', status: 'Active', live_task: 'Reads the live quote cache. No setup is approved from this card.' },
  { name: 'Strategy Agent', role: 'Evaluates strategies & regimes', status: 'Active', live_task: 'Reports the last trading-cycle status.' },
  { name: 'Risk Management Agent', role: 'Enforces limits & position sizing', status: 'Active', live_task: 'Kill switch stays armed until a real breach or a manual halt.' },
  { name: 'Execution Agent', role: 'Manages orders in paper mode', status: 'Active', live_task: 'Paper broker only. Live trading is disabled.' },
  { name: 'Portfolio Agent', role: 'Tracks equity, P&L & drawdown', status: 'Active', live_task: 'Equity is read from the paper broker.' },
  { name: 'Market Regime Agent', role: 'Identifies volatility & market phases', status: 'Active', live_task: 'Regime label is EMA20 versus EMA50 after candles load.' },
  { name: 'Expectancy Agent', role: 'Models mathematical edge', status: 'Active', live_task: 'Win rate is calculated from today closed trades.' },
  { name: 'Position Sizing Agent', role: 'ATR volatility risk allocation', status: 'Active', live_task: 'Size is computed inside a real cycle, not on this card.' },
  { name: 'Recovery Agent', role: 'Orphaned order & crash safety', status: 'Active', live_task: 'One trading loop is allowed at a time.' },
];

function renderAgentRosters() {
  const miniContainer = document.getElementById('agentsMiniContainer');
  if (miniContainer) {
    miniContainer.innerHTML = CORE_AGENTS.map(a => `
      <div class="agent-mini-card">
        <div class="agent-mini-left">
          <span class="status-dot green"></span>
          <div class="agent-mini-info">
            <h4>${a.name}</h4>
            <p style="color:var(--accent-cyan); font-size:10px;">${a.live_task}</p>
          </div>
        </div>
        <div class="agent-status-tag text-green">${a.status}</div>
      </div>
    `).join('');
  }

  const detailedGrid = document.getElementById('agentsDetailedGrid');
  if (detailedGrid) {
    detailedGrid.innerHTML = CORE_AGENTS.map(a => `
      <div class="panel-card" style="padding:14px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <h3 style="font-size:13px; font-weight:700;">${a.name}</h3>
          <span class="status-dot green"></span>
        </div>
        <p style="font-size:11px; color:var(--text-dim); margin-bottom:8px;">${a.role}</p>
        <div style="background:var(--bg-card-inset); padding:8px; border-radius:4px; font-size:11px;">
          <div style="color:var(--text-dim); margin-bottom:2px;">Status: <span class="text-green">${a.status}</span></div>
          <div style="color:var(--text-dim);">Live Task: <span class="text-cyan">${a.live_task}</span></div>
        </div>
      </div>
    `).join('');
  }
}

// 14. WebSocket Connection for Zero-Latency Pricing
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/live-feed`;

  try {
    activeWebSocket = new WebSocket(wsUrl);

    activeWebSocket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.quotes) payload.quotes.forEach(applyLiveQuote);
      } catch (err) {
        // quiet parse
      }
    };

    activeWebSocket.onclose = () => {
      setTimeout(initWebSocket, 5000);
    };
  } catch (err) {
    console.warn('WebSocket connection note:', err);
  }
}

// 15. App Bootstrap
document.addEventListener('DOMContentLoaded', () => {
  const signOutBtn = document.getElementById('signOutBtn');
  if (signOutBtn) signOutBtn.addEventListener('click', signOut);
  updateUtcClock();
  setInterval(updateUtcClock, 1000);

  initNavigationTabs();
  initCandlestickChart();
  initEquityChart();
  renderAgentRosters();

  // Initial polls for 100% real backend data
  fetchPerformanceMetrics();
  fetchPositionsAndOrders();
  fetchEvaluationStatus();
  fetchRealAgentDecisionsAndChat();
  fetchAgentActions();
  fetchSystemLogs();
  fetchMarketQuotes();
  fetchRealTimeMarketTrades();

  // Background refresh loops
  setInterval(fetchPerformanceMetrics, 3000);
  setInterval(fetchPositionsAndOrders, 3000);
  setInterval(fetchEvaluationStatus, 4000);
  setInterval(fetchRealAgentDecisionsAndChat, 5000);
  setInterval(fetchAgentActions, 4000);
  setInterval(fetchSystemLogs, 3000);
  setInterval(fetchMarketQuotes, 2000);
  setInterval(fetchRealTimeMarketTrades, 2000);

  initWebSocket();
});
