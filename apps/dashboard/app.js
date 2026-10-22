// Dashboard JavaScript Controller for Autonomous AI Trading Office

function getAuthToken() {
  return localStorage.getItem('ai_trader_token') || '';
}

function setAuthToken(token) {
  if (token) {
    localStorage.setItem('ai_trader_token', token);
  } else {
    localStorage.removeItem('ai_trader_token');
  }
}

async function apiFetch(url, options = {}) {
  const token = getAuthToken();
  const headers = options.headers || {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  options.headers = headers;
  let resp = await fetch(url, options);
  if (resp.status === 401 && token) {
    setAuthToken(null);
    delete headers['Authorization'];
    options.headers = headers;
    resp = await fetch(url, options);
  }
  return resp;
}

function updateClock() {
  const now = new Date();
  const options = { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
  const istTime = new Intl.DateTimeFormat('en-GB', options).format(now);
  const clockEl = document.getElementById('liveClock');
  if (clockEl) {
    clockEl.innerText = `${istTime} IST`;
  }
}

async function fetchTreasury() {
  try {
    const res = await apiFetch('/api/treasury');
    if (res.ok) {
      const data = await res.json();
      applyTreasuryMetrics(data);
    }
  } catch (err) {
    console.warn('Failed to fetch treasury metrics:', err);
  }
}

function applyTreasuryMetrics(data) {
  const capEl = document.getElementById('valTotalCapital');
  if (capEl && data.total_equity !== undefined) {
    capEl.innerText = `₹${data.total_equity.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  }
  
  const subCapEl = document.getElementById('subTotalCapital');
  if (subCapEl) {
    if (data.broker_mode === 'LIVE') {
      subCapEl.innerText = `AngelOne Live RMS • Client: ${data.client_code || 'AACJ120032'}`;
    } else {
      const startCap = data.starting_capital !== undefined ? data.starting_capital : 0;
      subCapEl.innerText = `Bootstrap Initial: ₹${startCap.toLocaleString('en-IN')}`;
    }
  }

  const expEl = document.getElementById('valOperatingExpenses');
  if (expEl && data.operating_expenses !== undefined) {
    expEl.innerText = `₹${data.operating_expenses.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  }

  const netProfitEl = document.getElementById('valNetProfit');
  if (netProfitEl && data.net_trading_profit !== undefined) {
    netProfitEl.innerText = `₹${data.net_trading_profit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
    netProfitEl.className = data.net_trading_profit >= 0 ? 'metric-value text-green' : 'metric-value text-red';
  }

  const lossEl = document.getElementById('valDailyLoss');
  if (lossEl) {
    const loss = data.daily_realized_loss || 0;
    const limit = data.daily_loss_limit !== undefined ? data.daily_loss_limit : 0.0;
    lossEl.innerText = `₹${loss.toFixed(2)} / ₹${limit.toFixed(2)}`;
  }

  const subLossEl = document.getElementById('subDailyLoss');
  if (subLossEl) {
    const startCap = data.starting_capital !== undefined ? data.starting_capital : 0;
    subLossEl.innerText = `2.0% Hard Gate on ₹${startCap.toLocaleString('en-IN')}`;
  }

  // Trading Mode Badge
  const modeBadge = document.getElementById('tradingModeBadge');
  if (modeBadge && data.broker_mode) {
    modeBadge.innerText = `MODE: ${data.broker_mode}`;
    modeBadge.className = data.broker_mode === 'LIVE' ? 'status-pill pulse-green' : 'status-pill mode-pill';
  }

  // Survival Mode Badge
  const survivalEl = document.getElementById('survivalBadge');
  if (survivalEl) {
    if (data.is_survival_mode) {
      survivalEl.className = 'status-pill pulse-red';
      survivalEl.innerText = 'SURVIVAL MODE: ACTIVE';
    } else {
      survivalEl.className = 'status-pill pulse-green';
      survivalEl.innerText = 'SURVIVAL: NORMAL';
    }
  }
}

let cachedOfficeAgents = [];
let activeRosterDeptFilter = 'ALL';
let currentInspectedAgentId = null;

async function fetchOfficeRoster() {
  try {
    const res = await apiFetch('/api/office/state');
    if (res.ok) {
      const data = await res.json();
      cachedOfficeAgents = data.agents || [];
      renderFilteredOfficeRoster();
    }
  } catch (err) {
    console.warn('Failed to fetch office state roster:', err);
  }
}

function filterClassicRoster(dept) {
  activeRosterDeptFilter = dept;
  document.querySelectorAll('.dept-filter-chip').forEach(chip => {
    chip.classList.remove('active');
    if (chip.textContent.includes(dept) || (dept === 'ALL' && chip.textContent.includes('All'))) {
      chip.classList.add('active');
    }
  });
  renderFilteredOfficeRoster();
}

function renderFilteredOfficeRoster() {
  const listEl = document.getElementById('officeRosterList');
  if (!listEl) return;
  listEl.innerHTML = '';

  let filtered = cachedOfficeAgents;
  if (activeRosterDeptFilter !== 'ALL') {
    filtered = cachedOfficeAgents.filter(a => a.department === activeRosterDeptFilter);
  }

  if (!filtered || filtered.length === 0) {
    listEl.innerHTML = '<div class="text-muted text-center py-3">No agents found in this department.</div>';
    return;
  }

  filtered.forEach(a => {
    const item = document.createElement('div');
    item.className = 'office-agent-item';
    item.onclick = () => openClassicAgentModal(a.id);
    const statusColor = (a.status === 'ACTIVE' || a.status === 'RUNNING') ? 'text-green' : (a.status === 'ANALYZING' ? 'text-cyan' : 'text-yellow');
    const funcsCount = (a.executable_functions || []).length;
    item.innerHTML = `
      <div style="display:flex; align-items:center; gap:10px;">
        <span style="font-size:20px;">${a.avatar_icon || '🤖'}</span>
        <div class="agent-info">
          <span class="agent-name">${escapeHtml(a.name)}</span>
          <span class="agent-role">${escapeHtml(a.department)} • ${escapeHtml(a.role)}</span>
        </div>
      </div>
      <div class="agent-meta">
        ${funcsCount > 0 ? `<span class="badge badge-accent" style="font-size:10px;">⚡ ${funcsCount} Tools</span>` : ''}
        <span class="${statusColor}" style="font-weight:700; font-size:11px;">● ${escapeHtml(a.status || 'RUNNING')}</span>
      </div>
    `;
    listEl.appendChild(item);
  });
}

function openClassicAgentModal(agentId) {
  currentInspectedAgentId = agentId;
  const agent = cachedOfficeAgents.find(a => a.id === agentId);
  if (!agent) return;

  const modal = document.getElementById('classicAgentModal');
  if (!modal) return;
  modal.style.display = 'flex';

  document.getElementById('modalAgentIcon').textContent = agent.avatar_icon || '🤖';
  document.getElementById('modalAgentName').textContent = agent.name;
  document.getElementById('modalAgentRole').textContent = `${agent.department} • ${agent.role}`;
  
  const statusBadge = document.getElementById('modalAgentStatusBadge');
  if (statusBadge) {
    statusBadge.textContent = `STATUS: ${agent.status || 'RUNNING'}`;
    statusBadge.className = `status-pill ${(agent.status === 'ACTIVE' || agent.status === 'RUNNING') ? 'pulse-green' : 'pulse-cyan'}`;
  }

  // Mission
  const missionEl = document.getElementById('modalAgentMission');
  if (missionEl) missionEl.textContent = agent.current_mission || "Autonomous Market Intelligence & Execution";

  // Monitored universe
  const symbolsWrap = document.getElementById('modalAgentSymbols');
  if (symbolsWrap) {
    const syms = agent.monitored_symbols && agent.monitored_symbols.length > 0
      ? agent.monitored_symbols
      : ["RELIANCE", "TCS", "INFY", "TATAMOTORS", "NIFTY 50"];
    symbolsWrap.innerHTML = syms.map(s => `
      <span class="badge badge-secondary" style="font-family:'JetBrains Mono', monospace; font-size:10px;">${escapeHtml(s)}</span>
    `).join('');
  }

  // Metrics
  const metricsGrid = document.getElementById('modalAgentMetrics');
  if (metricsGrid) {
    const m = agent.metrics || {};
    const keys = Object.keys(m);
    if (keys.length > 0) {
      metricsGrid.innerHTML = keys.map(k => `
        <div style="background:rgba(0,0,0,0.3); border:1px solid var(--border-subtle); padding:6px 10px; border-radius:4px; display:flex; justify-content:space-between; font-size:11px;">
          <span class="text-muted">${escapeHtml(k.replace(/_/g, ' ').toUpperCase())}</span>
          <span class="text-cyan" style="font-family:'JetBrains Mono', monospace; font-weight:700;">${escapeHtml(String(m[k]))}</span>
        </div>
      `).join('');
    } else {
      metricsGrid.innerHTML = `
        <div style="background:rgba(0,0,0,0.3); border:1px solid var(--border-subtle); padding:6px 10px; border-radius:4px; display:flex; justify-content:space-between; font-size:11px;">
          <span class="text-muted">CONFIDENCE</span>
          <span class="text-cyan" style="font-family:'JetBrains Mono', monospace; font-weight:700;">${Math.round((agent.confidence_score || 0.88) * 100)}%</span>
        </div>
      `;
    }
  }

  // Thought
  const thoughtEl = document.getElementById('modalAgentThought');
  if (thoughtEl) {
    thoughtEl.textContent = agent.thought_bubble || agent.current_activity || "Monitoring real-time trading parameters.";
  }

  // Permissions
  const permsWrap = document.getElementById('modalAgentPermissions');
  if (permsWrap) {
    const perms = agent.permissions || ["READ_DATA"];
    permsWrap.innerHTML = perms.map(p => `
      <span class="badge badge-primary" style="font-size:10px;">🔒 ${escapeHtml(p)}</span>
    `).join('');
  }

  // Reset chat thread
  const chatThread = document.getElementById('modalAgentChatThread');
  if (chatThread) {
    chatThread.innerHTML = `
      <div style="background:rgba(139,92,246,0.15); border:1px solid rgba(139,92,246,0.3); border-radius:6px; padding:8px 10px; font-size:11.5px;">
        <b>${escapeHtml(agent.name)}:</b> Greetings operator. Operating in <b>${escapeHtml(agent.department)}</b> as <i>${escapeHtml(agent.role)}</i>. ${escapeHtml(agent.thought_bubble || agent.current_activity || '')}. You can ask questions or execute my live specialized tools below.
      </div>
    `;
  }

  // Render Live Executable Functions
  renderClassicAgentFunctions(agent);

  // Default to Tab 1
  switchClassicAgentTab('intel');
}

function closeClassicAgentModal() {
  const modal = document.getElementById('classicAgentModal');
  if (modal) modal.style.display = 'none';
  currentInspectedAgentId = null;
}

function switchClassicAgentTab(tabKey) {
  document.querySelectorAll('.modal-subtab').forEach(t => t.classList.remove('active'));
  event?.target?.classList?.add('active');

  document.querySelectorAll('.classic-agent-tab').forEach(c => c.classList.remove('active'));
  const target = document.getElementById(`modalTab${tabKey.charAt(0).toUpperCase() + tabKey.slice(1)}`);
  if (target) target.classList.add('active');
}

function renderClassicAgentFunctions(agent) {
  const container = document.getElementById('modalAgentFunctionsList');
  if (!container) return;

  const funcs = agent.executable_functions || [];
  if (funcs.length === 0) {
    container.innerHTML = `
      <div style="color:var(--text-muted); font-size:11px; padding:16px; text-align:center; background:rgba(0,0,0,0.2); border-radius:6px;">
        🤖 <i>No standalone executable tools configured for this agent.</i>
      </div>
    `;
    return;
  }

  container.innerHTML = funcs.map(fn => {
    const params = fn.parameters || {};
    const keys = Object.keys(params);
    const paramInputsHtml = keys.map(k => `
      <div class="func-param-field">
        <span>${escapeHtml(k)}:</span>
        <input type="text" class="func-param-input" id="classic_param_${agent.id}_${fn.name}_${k}" value="${escapeHtml(params[k])}">
      </div>
    `).join('');

    return `
      <div class="func-card">
        <div class="func-card-header">
          <div class="func-card-title">
            <span>⚡</span>
            <span>${escapeHtml(fn.display_name || fn.name)}</span>
          </div>
          <span class="func-badge">${escapeHtml(fn.category || 'Tool')}</span>
        </div>
        <div class="func-card-desc">${escapeHtml(fn.description || '')}</div>
        <div class="func-params-row">
          ${paramInputsHtml}
          <button class="func-run-btn" onclick="executeClassicAgentFunction('${agent.id}', '${fn.name}')">
            <span>⚡ Execute Live</span>
          </button>
        </div>
        <div class="func-result-box" id="classic_result_${agent.id}_${fn.name}"></div>
      </div>
    `;
  }).join('');
}

async function executeClassicAgentFunction(agentId, funcName) {
  const resultBox = document.getElementById(`classic_result_${agentId}_${funcName}`);
  if (resultBox) {
    resultBox.classList.add('active');
    resultBox.innerHTML = `<span style="color:var(--accent-cyan);">⏳ Invoking ${funcName} on ${agentId}...</span>`;
  }

  const payload = {};
  const agent = cachedOfficeAgents.find(a => a.id === agentId);
  const fnSpec = (agent?.executable_functions || []).find(f => f.name === funcName);
  if (fnSpec && fnSpec.parameters) {
    Object.keys(fnSpec.parameters).forEach(k => {
      const input = document.getElementById(`classic_param_${agentId}_${funcName}_${k}`);
      if (input) payload[k] = input.value;
    });
  } else {
    payload.symbol = "RELIANCE.NS";
  }

  try {
    const res = await apiFetch(`/api/office/agent/${agentId}/function/${funcName}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (resultBox) {
      if (data.result) {
        resultBox.innerHTML = `<span style="color:var(--color-green);">✔ Live Output:</span>\n` + 
          escapeHtml(JSON.stringify(data.result, null, 2));
      } else if (data.detail) {
        resultBox.innerHTML = `<span style="color:var(--color-red);">✖ Error:</span> ` + escapeHtml(data.detail);
      } else {
        resultBox.innerHTML = escapeHtml(JSON.stringify(data, null, 2));
      }
    }
  } catch (err) {
    if (resultBox) {
      resultBox.innerHTML = `<span style="color:var(--color-red);">✖ Execution Error:</span> ` + escapeHtml(err.message);
    }
  }
}

function askClassicAgentQuestion(q) {
  const input = document.getElementById('modalAgentChatInput');
  if (input) {
    input.value = q;
    handleClassicAgentChatSubmit();
  }
}

async function handleClassicAgentChatSubmit() {
  const input = document.getElementById('modalAgentChatInput');
  const thread = document.getElementById('modalAgentChatThread');
  if (!input || !input.value.trim() || !currentInspectedAgentId) return;

  const msg = input.value.trim();
  input.value = '';

  const userBubble = document.createElement('div');
  userBubble.style.cssText = 'background:rgba(255,255,255,0.06); padding:6px 10px; border-radius:6px; font-size:11px; align-self:flex-end; max-width:80%;';
  userBubble.innerHTML = `<b>Operator:</b> ${escapeHtml(msg)}`;
  thread.appendChild(userBubble);
  thread.scrollTop = thread.scrollHeight;

  try {
    const res = await apiFetch(`/api/office/agent/${currentInspectedAgentId}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg }),
    });
    const data = await res.json();

    const agentBubble = document.createElement('div');
    agentBubble.style.cssText = 'background:rgba(6,182,212,0.15); border:1px solid rgba(6,182,212,0.3); padding:6px 10px; border-radius:6px; font-size:11px; align-self:flex-start; max-width:85%;';
    agentBubble.innerHTML = `<b>${escapeHtml(data.agent_name || 'Specialist')}:</b> ${escapeHtml(data.response || '')}`;
    thread.appendChild(agentBubble);
    thread.scrollTop = thread.scrollHeight;
  } catch (err) {
    console.error(err);
  }
}

async function handleClassicAgentAction(action) {
  if (!currentInspectedAgentId) return;
  try {
    await apiFetch(`/api/office/agent/${currentInspectedAgentId}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    fetchOfficeRoster();
    openClassicAgentModal(currentInspectedAgentId);
  } catch (err) {
    console.error(err);
  }
}


async function fetchAgentActivities() {
  try {
    const res = await apiFetch('/api/events?limit=8');
    if (res.ok) {
      const data = await res.json();
      const feed = document.getElementById('agentActivityFeed');
      if (!feed) return;

      const events = data.events || [];
      if (events.length === 0) {
        feed.innerHTML = `
          <div class="activity-event-item">
            <span>👑 <b>CEO Chief Trading Officer:</b> Market synthesis active</span>
            <small class="text-cyan">LIVE</small>
          </div>
          <div class="activity-event-item">
            <span>📈 <b>Technical Analyst:</b> Multi-timeframe breakout checks</span>
            <small class="text-cyan">LIVE</small>
          </div>
          <div class="activity-event-item">
            <span>🛡️ <b>Risk Manager:</b> 14-Point Pre-Trade Gate enforced</span>
            <small class="text-cyan">LIVE</small>
          </div>
        `;
        return;
      }

      feed.innerHTML = '';
      events.slice(-8).reverse().forEach(e => {
        const item = document.createElement('div');
        item.className = 'activity-event-item';
        const sourceName = e.agent || e.source || 'Specialist Agent';
        const msgText = e.message || e.event_type || (typeof e.payload === 'string' ? e.payload : JSON.stringify(e.payload || ''));
        const timeStr = e.time || (e.timestamp ? e.timestamp.split('T')[1]?.slice(0, 8) : '');
        item.innerHTML = `
          <div style="display:flex; flex-direction:column; gap:2px;">
            <span style="font-weight:700; color:var(--accent-cyan);">${escapeHtml(sourceName)}</span>
            <span class="text-muted" style="font-size:10.5px; line-height:1.3;">${escapeHtml(msgText)}</span>
          </div>
          <small class="text-cyan" style="font-family:'JetBrains Mono', monospace; font-size:10px; white-space:nowrap;">${timeStr}</small>
        `;
        feed.appendChild(item);
      });
    }
  } catch (err) {
    console.warn('Failed to fetch agent events:', err);
  }
}

async function fetchLearningStats() {
  try {
    const res = await apiFetch('/api/learning-stats');
    if (res.ok) {
      const data = await res.json();
      document.getElementById('countGG').innerText = data.good_decision_good_outcome || 0;
      document.getElementById('countGB').innerText = data.good_decision_bad_outcome || 0;
      document.getElementById('countBG').innerText = data.bad_decision_good_outcome || 0;
      document.getElementById('countBB').innerText = data.bad_decision_bad_outcome || 0;
      document.getElementById('decisionSoundnessRate').innerText = `Soundness: ${data.decision_soundness_rate || '100%'}`;
    }
  } catch (err) {
    console.warn('Failed to fetch learning stats:', err);
  }
}

async function fetchKillSwitch() {
  try {
    const res = await apiFetch('/api/kill-switch');
    if (res.ok) {
      const data = await res.json();
      const badge = document.getElementById('killSwitchBadge');
      if (data.is_engaged) {
        badge.className = 'status-pill pulse-red';
        badge.innerText = '🚨 KILL SWITCH: ENGAGED';
      } else {
        badge.className = 'status-pill';
        badge.innerText = 'KILL SWITCH: OFF';
      }
    }
  } catch (err) {
    console.warn('Failed to fetch kill switch state:', err);
  }
}

async function toggleKillSwitch() {
  try {
    const checkRes = await apiFetch('/api/kill-switch');
    const data = await checkRes.json();
    const newEngage = !data.is_engaged;
    const confirmMsg = newEngage ? "Engage Emergency Kill Switch and halt all trading operations?" : "Reset Emergency Kill Switch and resume operations?";
    if (!confirm(confirmMsg)) return;

    await apiFetch(`/api/kill-switch?engage=${newEngage}&reason=Dashboard operator toggle`, { method: 'POST' });
    fetchKillSwitch();
  } catch (err) {
    alert(`Error toggling kill switch: ${err.message}`);
  }
}

async function fetchScan() {
  const tbody = document.getElementById('scannerTableBody');
  const universe = document.getElementById('selectUniverse') ? document.getElementById('selectUniverse').value : 'nifty50';
  tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-muted">Scanning ${universe.toUpperCase()} Universe concurrently...</td></tr>`;

  try {
    const res = await apiFetch(`/api/scan?top_n=8&universe=${universe}`);
    if (res.ok) {
      const data = await res.json();
      tbody.innerHTML = '';
      if (!data.candidates || data.candidates.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">No qualified candidates found.</td></tr>';
        return;
      }

      data.candidates.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${c.symbol}</strong></td>
          <td>₹${c.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
          <td>${c.relative_volume}x</td>
          <td><span class="text-green">${c.momentum_score}/100</span></td>
          <td>₹${c.atr_14}</td>
          <td><span class="status-pill">${c.regime}</span></td>
          <td>
            <button class="btn btn-primary" onclick="analyzeSymbol('${c.symbol}')">Analyze</button>
            <button class="btn btn-secondary btn-sm" onclick="selectKronosSymbol('${c.symbol}')" style="margin-left:4px; border-color: rgba(168,85,247,0.5); color:#c084fc;">🔮 Kronos</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-red">Scan Error: ${err.message}</td></tr>`;
  }
}

function selectKronosSymbol(sym) {
  const inp = document.getElementById('kronosSymbol');
  if (inp) inp.value = sym;
  runKronosForecastUI();
  const el = document.getElementById('kronosResultContainer');
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

async function runKronosForecastUI() {
  const symEl = document.getElementById('kronosSymbol');
  const horizonEl = document.getElementById('kronosHorizon');
  const container = document.getElementById('kronosResultContainer');
  const btn = document.getElementById('btnRunKronos');

  if (!symEl || !container) return;
  const symbol = symEl.value.trim().toUpperCase();
  const bars = horizonEl ? horizonEl.value : '10';

  if (!symbol) {
    alert('Please enter a symbol (e.g. PNB.NS, RELIANCE.NS, BTC-USD)');
    return;
  }

  btn.disabled = true;
  btn.innerText = '⏳ Inferencing on MPS...';
  container.innerHTML = `
    <div style="text-align:center; padding: 24px;">
      <div class="beacon-pulse" style="margin: 0 auto 12px auto;"></div>
      <div style="color: #c084fc; font-weight: 600;">Running Tsinghua Kronos Foundation Model on Apple Silicon Metal (MPS)...</div>
      <div class="text-muted" style="font-size: 12px; margin-top: 6px;">Zero-shot autoregressive K-line generation (${bars} forward bars) for ${symbol}</div>
    </div>
  `;

  try {
    const res = await apiFetch(`/api/forecast/kronos?symbol=${encodeURIComponent(symbol)}&bars=${bars}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server returned status ${res.status}`);
    }
    const data = await res.json();
    const curr = symbol.includes('-USD') ? '$' : '₹';
    const isBull = data.expected_direction === 'BULLISH';
    const isBear = data.expected_direction === 'BEARISH';
    const dirColor = isBull ? '#22c55e' : (isBear ? '#ef4444' : '#eab308');
    const dirBg = isBull ? 'rgba(34,197,94,0.15)' : (isBear ? 'rgba(239,68,68,0.15)' : 'rgba(234,179,8,0.15)');

    let barsTableHtml = '';
    if (data.predicted_bars && data.predicted_bars.length > 0) {
      barsTableHtml = `
        <div style="margin-top: 16px; overflow-x: auto;">
          <h4 style="font-size: 13px; text-transform: uppercase; color: #a855f7; margin-bottom: 8px;">📊 Predicted Candlestick Sequence</h4>
          <table class="custom-table" style="font-size: 12px;">
            <thead>
              <tr>
                <th>Bar #</th>
                <th>Open</th>
                <th>High</th>
                <th>Low</th>
                <th>Close</th>
                <th>Bar Delta</th>
              </tr>
            </thead>
            <tbody>
              ${data.predicted_bars.map(b => {
                const delta = b.close - b.open;
                const deltaPct = b.open > 0 ? (delta / b.open) * 100 : 0;
                const cColor = delta >= 0 ? '#22c55e' : '#ef4444';
                return `
                  <tr>
                    <td><strong>+${b.step}</strong></td>
                    <td>${curr}${b.open.toFixed(2)}</td>
                    <td style="color:#22c55e;">${curr}${b.high.toFixed(2)}</td>
                    <td style="color:#ef4444;">${curr}${b.low.toFixed(2)}</td>
                    <td><strong>${curr}${b.close.toFixed(2)}</strong></td>
                    <td style="color:${cColor}; font-weight:600;">${deltaPct >= 0 ? '+' : ''}${deltaPct.toFixed(2)}%</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    container.innerHTML = `
      <div style="background: rgba(15, 15, 25, 0.6); border-radius: 8px; border: 1px solid rgba(168, 85, 247, 0.3); padding: 18px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 12px;">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size:18px; font-weight:bold; color:#fff;">${data.symbol}</span>
              <span style="background:${dirBg}; color:${dirColor}; padding:3px 10px; border-radius:12px; font-weight:700; font-size:12px; border:1px solid ${dirColor};">${data.expected_direction}</span>
              <span style="font-size:12px; color:#a855f7;">${data.model_name} • ${data.device ? data.device.toUpperCase() : 'MPS'}</span>
            </div>
            <div style="font-size:12px; color:#9ca3af; margin-top:4px;">${data.notes}</div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:11px; color:#9ca3af; text-transform:uppercase;">Model Confidence</div>
            <div style="font-size:18px; font-weight:bold; color:#a855f7;">${(data.confidence_score * 100).toFixed(0)}%</div>
          </div>
        </div>

        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-top: 14px;">
          <div style="background:rgba(255,255,255,0.03); padding:10px; border-radius:6px;">
            <div style="font-size:11px; color:#9ca3af;">Last Price</div>
            <div style="font-size:15px; font-weight:bold; color:#fbbf24;">${curr}${data.last_price.toFixed(2)}</div>
          </div>
          <div style="background:rgba(255,255,255,0.03); padding:10px; border-radius:6px;">
            <div style="font-size:11px; color:#9ca3af;">Projected Close</div>
            <div style="font-size:15px; font-weight:bold; color:${dirColor};">${curr}${data.projected_price.toFixed(2)} (${data.projected_change_pct >= 0 ? '+' : ''}${data.projected_change_pct.toFixed(2)}%)</div>
          </div>
          <div style="background:rgba(255,255,255,0.03); padding:10px; border-radius:6px;">
            <div style="font-size:11px; color:#9ca3af;">Volatility Range</div>
            <div style="font-size:13px; font-weight:600; color:#e2e8f0;">Low ${curr}${data.projected_low.toFixed(2)}<br>High ${curr}${data.projected_high.toFixed(2)}</div>
          </div>
          <div style="background:rgba(239,68,68,0.08); padding:10px; border-radius:6px; border:1px solid rgba(239,68,68,0.2);">
            <div style="font-size:11px; color:#ef4444;">Neural Stop-Loss</div>
            <div style="font-size:15px; font-weight:bold; color:#ef4444;">${curr}${data.recommended_stop_loss.toFixed(2)}</div>
          </div>
          <div style="background:rgba(34,197,94,0.08); padding:10px; border-radius:6px; border:1px solid rgba(34,197,94,0.2);">
            <div style="font-size:11px; color:#22c55e;">Target 1</div>
            <div style="font-size:15px; font-weight:bold; color:#22c55e;">${curr}${data.recommended_target.toFixed(2)}</div>
          </div>
        </div>

        ${barsTableHtml}
      </div>
    `;
  } catch (err) {
    container.innerHTML = `
      <div style="background:rgba(239,68,68,0.1); border:1px solid #ef4444; border-radius:8px; padding:16px; color:#ef4444;">
        <strong>Prediction Error:</strong> ${err.message}
      </div>
    `;
  } finally {
    btn.disabled = false;
    btn.innerText = '⚡ Predict Trajectory';
  }
}

function analyzeSymbol(sym) {
  document.getElementById('inputSymbol').value = sym;
  runAnalysisForSymbol(sym);
}

async function runAnalysis() {
  const sym = document.getElementById('inputSymbol').value.trim();
  if (!sym) {
    autoPickAndDebateTopStock();
    return;
  }
  await runAnalysisForSymbol(sym);
}

async function autoPickAndDebateTopStock() {
  const bullEl = document.getElementById('bullThesisText');
  const bearEl = document.getElementById('bearThesisText');
  const badgeEl = document.getElementById('decisionBadge');
  const titleEl = document.getElementById('decisionTitle');
  const detailsEl = document.getElementById('decisionDetails');

  bullEl.innerText = '🤖 AI Scanning complete market universe (NIFTY 50) for momentum & volume breakouts...';
  bearEl.innerText = 'Filtering candidates through volatility, regime, and institutional filters...';
  badgeEl.className = 'banner-badge';
  badgeEl.innerText = 'AUTO-SCANNING';
  titleEl.innerText = 'AI Scanning & Candidate Selection';
  detailsEl.innerText = 'Evaluating 50 NSE stocks to autonomously pick the highest-ranked candidate...';

  try {
    const universe = document.getElementById('selectUniverse') ? document.getElementById('selectUniverse').value : 'nifty50';
    const scanRes = await apiFetch(`/api/scan?top_n=5&universe=${universe}`);
    if (!scanRes.ok) throw new Error('Market scan failed');
    const scanData = await scanRes.json();
    
    if (!scanData.candidates || scanData.candidates.length === 0) {
      badgeEl.innerText = 'NO_CANDIDATE';
      titleEl.innerText = 'No Breakout Opportunities Detected';
      detailsEl.innerText = 'All scanned stocks failed liquidity, regime, or volume breakout criteria.';
      return;
    }

    const topCandidate = scanData.candidates[0];
    document.getElementById('inputSymbol').value = topCandidate.symbol;
    titleEl.innerText = `AI Picked Top Candidate: ${topCandidate.symbol} (Score: ${topCandidate.momentum_score}/100, RelVol: ${topCandidate.relative_volume}x)`;
    detailsEl.innerText = `Launching 5 Specialist Analysts, Adversarial Bear Debate, and 14-Point Pre-Trade Audit for ${topCandidate.symbol}...`;

    await runAnalysisForSymbol(topCandidate.symbol);
  } catch (err) {
    badgeEl.innerText = 'ERROR';
    titleEl.innerText = 'Auto-Selection Error';
    detailsEl.innerText = err.message;
  }
}

async function runBatchDebateAll() {
  const universe = document.getElementById('selectUniverse') ? document.getElementById('selectUniverse').value : 'bootstrap';
  const grid = document.getElementById('multiStockGrid');
  const countEl = document.getElementById('sweepEvaluatedCount');
  
  if (countEl) countEl.innerText = 'Sweeping market & evaluating candidates...';

  try {
    const res = await apiFetch(`/api/batch-debate?top_n=6&universe=${universe}`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      renderMultiStockGrid(data);
      if (countEl) countEl.innerText = `${data.total_evaluated} Stocks Debated (${data.approved_count} Approved, ${data.rejected_count} Rejected)`;
    }
  } catch (err) {
    console.warn('Batch debate error:', err);
    if (grid) {
      grid.innerHTML = `<div class="text-center py-4 text-red" style="grid-column: 1 / -1;">Multi-Stock Sweep Error: ${err.message}</div>`;
    }
  }
}

function renderMultiStockGrid(data) {
  const grid = document.getElementById('multiStockGrid');
  if (!grid) return;

  const candidates = data.ranked_candidates || [];
  if (candidates.length === 0) {
    grid.innerHTML = '<div class="text-center py-4 text-muted" style="grid-column: 1 / -1;">No qualified candidates in current scan.</div>';
    return;
  }

  grid.innerHTML = '';
  candidates.forEach(c => {
    const sig = c.signal || {};
    const dec = c.decision || {};
    const deb = c.debate || {};
    const isApproved = dec.decision === 'BUY';
    const cardClass = isApproved ? 'multi-stock-card approved' : 'multi-stock-card rejected';
    const badgeColor = isApproved ? 'badge-primary' : 'badge';
    const statusText = isApproved ? `APPROVED BUY (${((dec.confidence || 0.6) * 100).toFixed(0)}%)` : 'NO_TRADE / REJECTED';

    const card = document.createElement('div');
    card.className = cardClass;
    card.innerHTML = `
      <div class="stock-card-header">
        <div>
          <div class="stock-symbol-title">
            <span>${sig.symbol}</span>
            <span class="badge ${badgeColor}">${sig.regime || 'MARKET'}</span>
          </div>
          <small class="text-muted">Momentum: ${sig.momentum_score || 0}/100 • RelVol: ${sig.relative_volume || 1.0}x • ATR: ₹${sig.atr_14 || 0}</small>
        </div>
        <div class="text-right">
          <div class="stock-ltp">₹${(sig.ltp || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
          <small class="text-muted">Rank: ${c.conviction_rank || 0}</small>
        </div>
      </div>

      <div class="stock-theses">
        <div class="stock-bull-thesis">
          <strong>🐂 Bull Thesis:</strong> ${deb.bull_thesis ? deb.bull_thesis.slice(0, 160) + '...' : 'Strong momentum and favorable volume expansion.'}
        </div>
        <div class="stock-bear-thesis">
          <strong>🐻 Bear Risk:</strong> ${deb.bear_thesis ? deb.bear_thesis.slice(0, 160) + '...' : 'Key support invalidation and intraday volatility risk.'}
        </div>
      </div>

      <div class="stock-levels-grid">
        <div><small class="text-muted">ENTRY</small><span class="text-cyan">₹${(dec.entry_price || sig.ltp || 0).toFixed(2)}</span></div>
        <div><small class="text-muted">STOP LOSS</small><span class="text-red">₹${(dec.stop_loss || 0).toFixed(2)}</span></div>
        <div><small class="text-muted">TARGET 1</small><span class="text-green">₹${(dec.target_1 || 0).toFixed(2)}</span></div>
      </div>

      <div class="stock-action-bar">
        <span class="${isApproved ? 'text-green' : 'text-yellow'}" style="font-weight:700; font-size:12px;">${statusText}</span>
        <span class="text-muted" style="font-size:11px;">R:R ${dec.expected_risk_reward || '1:2.0'}</span>
        <button class="btn btn-secondary btn-sm" onclick="runAnalysisForSymbol('${sig.symbol}')">🔍 Deep Audit</button>
      </div>
    `;
    grid.appendChild(card);
  });
}

// 24/7 Continuous Autonomous Market Sweeper
let sweepCountdown = 30;
function startContinuous24x7Sweep() {
  setInterval(() => {
    sweepCountdown--;
    const countdownEl = document.getElementById('sweepCountdownText');
    if (countdownEl) {
      countdownEl.innerText = `Next automated sweep in ${sweepCountdown}s`;
    }

    if (sweepCountdown <= 0) {
      sweepCountdown = 30;
      runBatchDebateAll();
      fetchScan();
    }
  }, 1000);
}

async function runAnalysisForSymbol(sym) {
  const countEl = document.getElementById('sweepEvaluatedCount');
  if (countEl) countEl.innerText = `Running 14-Point Pre-Trade Audit for ${sym}...`;

  try {
    const res = await apiFetch(`/api/analyze?symbol=${encodeURIComponent(sym)}`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      const dec = data.decision || {};
      alert(`📊 Multi-Agent 14-Point Audit for ${sym}:\n\n` +
            `• Decision: ${dec.decision}\n` +
            `• Confidence: ${((dec.confidence || 0) * 100).toFixed(0)}%\n` +
            `• Entry: ₹${dec.entry_price} | SL: ₹${dec.stop_loss} | Target: ₹${dec.target_1}\n` +
            `• Bull Thesis: ${data.debate?.bull_thesis?.slice(0, 120)}...\n` +
            `• Bear Risk: ${data.debate?.bear_thesis?.slice(0, 120)}...`);
    }
  } catch (err) {
    alert(`Audit failed for ${sym}: ${err.message}`);
  }
}

async function fetchGuardianStatus() {
  try {
    const res = await apiFetch('/api/guardian/status');
    if (!res.ok) return;
    const data = await res.json();

    // 1. Update Telemetry Ribbon
    const activeCountEl = document.getElementById('guardianActiveCount');
    if (activeCountEl) {
      activeCountEl.innerText = `${data.active_positions_count || 0} / ${data.active_positions_count || 0}`;
    }

    const atRiskEl = document.getElementById('guardianAtRiskCount');
    const riskSubEl = document.getElementById('guardianRiskSummary');
    if (atRiskEl) {
      const riskCount = data.positions_at_risk_count || 0;
      atRiskEl.innerText = riskCount;
      if (riskCount > 0) {
        atRiskEl.className = 'g-metric-val text-red';
        if (riskSubEl) riskSubEl.innerText = '🚨 Attention: Interventions pending';
      } else {
        atRiskEl.className = 'g-metric-val text-green';
        if (riskSubEl) riskSubEl.innerText = 'All positions in safe bounds';
      }
    }

    const syncEl = document.getElementById('guardianBrokerSyncVal');
    const syncSubEl = document.getElementById('guardianBrokerSyncSub');
    if (syncEl) {
      if (data.broker_synchronized) {
        syncEl.innerText = '🟢 SYNCHRONIZED';
        syncEl.className = 'g-metric-val text-green';
        if (syncSubEl) syncSubEl.innerText = 'AngelOne SmartAPI state matched';
      } else {
        syncEl.innerText = '🔴 STATE MISMATCH';
        syncEl.className = 'g-metric-val text-red';
        if (syncSubEl) syncSubEl.innerText = `Discrepancies: ${data.discrepancies?.length || 1} detected`;
      }
    }

    // 2. Render Live Monitored Positions Table
    const tbody = document.getElementById('guardianPositionsTableBody');
    if (tbody) {
      tbody.innerHTML = '';
      const positions = data.positions || [];

      if (positions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center py-4 text-muted">🛡️ All capital protected. Currently 0 active positions requiring real-time intervention.</td></tr>';
      } else {
        positions.forEach(p => {
          const tr = document.createElement('tr');
          const pnl = p.unrealized_pnl || 0.0;
          const pnlColor = pnl >= 0 ? 'text-green' : 'text-red';
          const pnlPct = p.unrealized_pnl_pct ? `(${p.unrealized_pnl_pct.toFixed(2)}%)` : '';

          let riskBadgeClass = 'badge-risk-low';
          let riskIcon = '🟢';
          if (p.risk_level === 'MEDIUM') { riskBadgeClass = 'badge-risk-med'; riskIcon = '🟡'; }
          else if (p.risk_level === 'HIGH') { riskBadgeClass = 'badge-risk-high'; riskIcon = '🔴'; }
          else if (p.risk_level === 'CRITICAL') { riskBadgeClass = 'badge-risk-crit'; riskIcon = '🚨'; }

          const thesisValidBadge = p.thesis_valid 
            ? `<span class="thesis-badge-valid">✓ Valid</span>` 
            : `<span class="thesis-badge-invalid">✕ ${p.invalidation_reason || 'Invalidated'}</span>`;

          const trailingInfo = p.current_stop_loss !== p.original_stop_loss 
            ? `<small class="text-green" title="Ratcheted by Guardian">₹${p.current_stop_loss.toFixed(2)} ⮤</small>`
            : `₹${(p.current_stop_loss || p.stop_loss || 0).toFixed(2)}`;

          tr.innerHTML = `
            <td>
              <strong>${p.symbol}</strong>
              <div style="font-size:10px; color:var(--text-muted); max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${p.trade_thesis || ''}">${p.trade_thesis || 'Momentum Breakout'}</div>
            </td>
            <td><strong>${p.quantity}</strong></td>
            <td>₹${p.entry_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
            <td>₹${(p.current_price || p.entry_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
            <td>${trailingInfo}</td>
            <td>₹${p.target_1 || '-'} / ₹${p.target_2 || '-'}</td>
            <td class="${pnlColor}"><strong>₹${pnl.toFixed(2)}</strong> <small>${pnlPct}</small></td>
            <td><span class="${riskBadgeClass}">${riskIcon} ${p.risk_level || 'LOW'}</span></td>
            <td>${thesisValidBadge}</td>
            <td>
              <div style="display:flex; gap:4px;">
                <button class="btn btn-outline-danger btn-sm" onclick="emergencyExitPosition('${p.symbol}')" style="padding:2px 8px; font-size:10.5px;" title="Guardian Force Close Position">⛔ Force Exit</button>
              </div>
            </td>
          `;
          tbody.appendChild(tr);
        });
      }
    }

    // 3. Render Post-Trade Audits Table (Section 19)
    const auditTbody = document.getElementById('guardianAuditsTableBody');
    const auditsCountEl = document.getElementById('guardianAuditsCount');
    if (auditTbody) {
      const audits = data.closed_positions_audit || [];
      if (auditsCountEl) auditsCountEl.innerText = `${audits.length} Closed Positions Audited`;

      if (audits.length === 0) {
        auditTbody.innerHTML = '<tr><td colspan="8" class="text-center py-3 text-muted">No completed trades yet in this session. Post-trade MFE/MAE reports will be stored here.</td></tr>';
      } else {
        auditTbody.innerHTML = '';
        audits.forEach(a => {
          const tr = document.createElement('tr');
          const pnl = a.realized_pnl || 0.0;
          const pnlClass = pnl >= 0 ? 'text-green' : 'text-red';
          tr.innerHTML = `
            <td><code>${a.trade_id.substring(0, 10)}...</code></td>
            <td><strong>${a.symbol}</strong></td>
            <td class="${pnlClass}"><strong>₹${pnl.toFixed(2)}</strong></td>
            <td class="text-green">+₹${(a.max_favorable_excursion || 0).toFixed(2)}</td>
            <td class="text-red">-₹${(a.max_adverse_excursion || 0).toFixed(2)}</td>
            <td>₹${(a.slippage || 0).toFixed(2)}</td>
            <td><span class="badge badge-secondary">${a.exit_reason || 'POLICY_EXIT'}</span></td>
            <td><span class="badge badge-accent">${a.learning_loop_quadrant || 'EDGE_VERIFIED'}</span></td>
          `;
          auditTbody.appendChild(tr);
        });
      }
    }

  } catch (err) {
    console.warn('Failed to fetch Guardian telemetry:', err);
  }
}

async function fetchPositions() {
  await fetchGuardianStatus();
}

async function reconcileBrokerNow() {
  try {
    const res = await apiFetch('/api/guardian/reconcile', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      if (data.status === 'MATCHED') {
        alert('✅ Broker Reconciled Successfully: AI State is 100% in sync with AngelOne SmartAPI.');
      } else {
        alert(`⚠️ Broker Discrepancy Detected:\n${JSON.stringify(data.discrepancies, null, 2)}`);
      }
      fetchGuardianStatus();
    }
  } catch (err) {
    alert(`Reconciliation failed: ${err.message}`);
  }
}

async function emergencyExitPosition(symbol) {
  if (!confirm(`🚨 EMERGENCY EXIT CONFIRMATION:\nAre you sure you want Trade Guardian to immediately market-exit position for ${symbol}?`)) {
    return;
  }
  try {
    const res = await apiFetch(`/api/guardian/emergency-exit/${encodeURIComponent(symbol)}`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      alert(`✅ Emergency exit executed: ${data.detail || data.status}`);
      fetchGuardianStatus();
      fetchOrders();
    } else {
      const err = await res.json();
      alert(`Emergency exit failed: ${err.detail || 'Unknown error'}`);
    }
  } catch (err) {
    alert(`Network error during emergency exit: ${err.message}`);
  }
}

async function fetchOrders() {
  try {
    const res = await apiFetch('/api/orders');
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById('ordersTableBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const brokerOrders = data.broker_order_book || [];
    const dbOrders = data.db_orders || [];

    if (brokerOrders.length === 0 && dbOrders.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">No live orders placed yet. AI agents scanning market.</td></tr>';
      return;
    }

    // 1. Render broker live order book if available
    if (brokerOrders.length > 0) {
      brokerOrders.forEach(o => {
        const tr = document.createElement('tr');
        const statusStr = (o.status || o.orderstatus || 'SUBMITTED').toUpperCase();
        const statusClass = statusStr.includes('COMPLETE') || statusStr.includes('SUCCESS') ? 'text-green' : (statusStr.includes('REJECT') ? 'text-red' : 'text-yellow');
        const sideClass = (o.transactiontype || 'BUY') === 'BUY' ? 'badge badge-accent' : 'badge badge-danger';
        
        tr.innerHTML = `
          <td><strong class="text-cyan">${o.orderid || o.uniqueorderid || 'ORD-LIVE'}</strong></td>
          <td><b>${o.tradingsymbol || o.symbol || '-'}</b></td>
          <td><span class="${sideClass}">${o.transactiontype || 'BUY'}</span></td>
          <td>${o.quantity || o.filledshares || 1}</td>
          <td>₹${Number(o.price || o.averageprice || 0).toFixed(2)}</td>
          <td><span class="${statusClass}">● ${statusStr}</span></td>
          <td class="text-muted" style="font-size:11px;">${o.updatetime || o.ordertime || new Date().toLocaleTimeString('en-IN')}</td>
        `;
        tbody.appendChild(tr);
      });
    } else {
      // 2. Render recorded DB orders
      dbOrders.slice(0, 10).forEach(o => {
        const tr = document.createElement('tr');
        const statusStr = (o.status || 'FILLED').toUpperCase();
        const statusClass = statusStr === 'FILLED' ? 'text-green' : 'text-yellow';
        const sideClass = o.action === 'BUY' ? 'badge badge-accent' : 'badge badge-danger';

        tr.innerHTML = `
          <td><strong class="text-cyan">${o.order_id}</strong></td>
          <td><b>${o.symbol}</b></td>
          <td><span class="${sideClass}">${o.action}</span></td>
          <td>${o.quantity}</td>
          <td>₹${Number(o.average_price).toFixed(2)}</td>
          <td><span class="${statusClass}">● ${statusStr}</span></td>
          <td class="text-muted" style="font-size:11px;">${o.executed_at ? o.executed_at.replace('T', ' ').substring(0, 19) : '-'}</td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    console.warn('Failed to fetch orders:', err);
  }
}


async function fetchCustomAgents() {
  try {
    const res = await apiFetch('/api/factory/agents');
    if (res.ok) {
      const data = await res.json();
      const grid = document.getElementById('customAgentsGrid');
      grid.innerHTML = '';

      if (!data.agents || data.agents.length === 0) {
        grid.innerHTML = '<div class="text-muted text-center py-4">No custom agents in library. Use the prompt bar above to create one!</div>';
        return;
      }

      data.agents.forEach(a => {
        const card = document.createElement('div');
        card.className = 'custom-agent-card';
        const statusColor = a.status === 'ACTIVE' ? 'text-green' : (a.status === 'SANDBOX' ? 'text-yellow' : 'text-red');
        const liveBadge = a.permissions.place_live_orders ? '<span class="badge badge-accent">LIVE TRADING</span>' : '<span class="badge">SANDBOX/PAPER</span>';

        card.innerHTML = `
          <div class="card-top">
            <div>
              <div class="card-agent-title">${a.name} <span style="font-size:11px; color:#8b949e;">${a.version}</span></div>
              <div class="card-agent-dept">${a.department} • ${a.role}</div>
            </div>
            <span class="${statusColor}" style="font-weight:700; font-size:12px;">${a.status}</span>
          </div>
          <div class="card-objective">${a.objective}</div>
          <div class="card-tags">
            ${a.tools.map(t => `<span class="card-tag">🛠️ ${t}</span>`).join('')}
            ${liveBadge}
          </div>
          <div class="card-actions">
            <button class="btn btn-primary btn-sm" onclick="testAgentSandbox('${a.agent_id}')">🧪 Test Sandbox</button>
            <button class="btn btn-secondary btn-sm" onclick="cloneAgentPrompt('${a.agent_id}', '${a.name}')">📋 Clone</button>
            <button class="btn btn-secondary btn-sm" onclick="toggleAgentStatus('${a.agent_id}', '${a.status}')">${a.status === 'ACTIVE' ? '⏸️ Pause' : '▶️ Activate'}</button>
            <button class="btn btn-secondary btn-sm" style="color:var(--color-red);" onclick="deleteCustomAgent('${a.agent_id}')">🗑️</button>
          </div>
        `;
        grid.appendChild(card);
      });
    }
  } catch (err) {
    console.warn('Failed to fetch custom agents:', err);
  }
}

async function createAgentFromPrompt() {
  const prompt = document.getElementById('inputAgentPrompt').value.trim();
  const name = document.getElementById('inputAgentName').value.trim() || 'Custom AI Specialist';
  const dept = document.getElementById('selectAgentDept').value;

  if (!prompt) {
    alert('Please enter instructions for the custom AI agent.');
    return;
  }

  try {
    const res = await apiFetch('/api/factory/agents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, name, department: dept }),
    });

    if (res.ok) {
      document.getElementById('inputAgentPrompt').value = '';
      document.getElementById('inputAgentName').value = '';
      fetchCustomAgents();
      alert(`✅ Agent '${name}' successfully generated and sandboxed!`);
    }
  } catch (err) {
    alert(`Failed to create agent: ${err.message}`);
  }
}

async function testAgentSandbox(agentId) {
  try {
    alert(`Running sandbox simulation test for ${agentId}...`);
    const res = await apiFetch(`/api/factory/agents/${agentId}/test`, { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      const report = data.test_result.simulated_report;
      alert(`✅ Sandbox Passed!\nStance: ${report.stance}\nConfidence: ${report.confidence}\nObservations: ${report.key_observations.join(' | ')}`);
      fetchCustomAgents();
    }
  } catch (err) {
    alert(`Sandbox simulation failed: ${err.message}`);
  }
}

async function cloneAgentPrompt(agentId, currentName) {
  const newName = prompt(`Enter name for the cloned agent:`, `${currentName} (Clone)`);
  if (!newName) return;

  try {
    const res = await apiFetch(`/api/factory/agents/${agentId}/clone?new_name=${encodeURIComponent(newName)}`, { method: 'POST' });
    if (res.ok) {
      fetchCustomAgents();
      alert(`✅ Cloned agent created: ${newName}`);
    }
  } catch (err) {
    alert(`Clone failed: ${err.message}`);
  }
}

async function toggleAgentStatus(agentId, currentStatus) {
  const newStatus = currentStatus === 'ACTIVE' ? 'PAUSED' : 'ACTIVE';
  try {
    const res = await apiFetch(`/api/factory/agents/${agentId}/status?status=${newStatus}`, { method: 'POST' });
    if (res.ok) {
      fetchCustomAgents();
    }
  } catch (err) {
    alert(`Failed to update status: ${err.message}`);
  }
}

async function deleteCustomAgent(agentId) {
  if (!confirm(`Are you sure you want to decommission and delete agent ${agentId}?`)) return;

  try {
    const res = await apiFetch(`/api/factory/agents/${agentId}`, { method: 'DELETE' });
    if (res.ok) {
      fetchCustomAgents();
    }
  } catch (err) {
    alert(`Delete failed: ${err.message}`);
  }
}

// Initial Bootstrapping
document.addEventListener('DOMContentLoaded', () => {
  updateClock();
  setInterval(updateClock, 1000);

  checkAuthStatus();
  fetchNetworkInfo();
  connectLiveMarketWebSocket();

  // 1. Immediate UI Telemetry Population
  fetchTreasury();
  fetchOfficeRoster();
  fetchAgentActivities();
  fetchCustomAgents();
  fetchLearningStats();
  fetchKillSwitch();
  fetchScan();
  fetchPositions();
  fetchOrders();
  fetchGuardianStatus();
  fetchTrainingStatus();

  // 2. Asynchronous Multi-Agent Debate Schedule (delayed by 2.5s)
  setTimeout(() => {
    runBatchDebateAll();
    startContinuous24x7Sweep();
  }, 2500);

  // 3. Periodic UI polling every 8s
  setInterval(() => {
    fetchTreasury();
    fetchPositions();
    fetchOrders();
    fetchKillSwitch();
    fetchCustomAgents();
    fetchAgentActivities();
    fetchGuardianStatus();
    fetchTrainingStatus();
  }, 8000);
});

// ==========================================
// REAL-TIME WEBSOCKET LIVE TICK STREAM
// ==========================================

let liveWs = null;
let previousPrices = {};

function connectLiveMarketWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/live-feed`;
  
  try {
    liveWs = new WebSocket(wsUrl);

    liveWs.onopen = () => {
      console.log('⚡ Connected to Sub-Second Live Market WebSocket!');
      const badge = document.querySelector('.ticker-badge');
      if (badge) badge.innerHTML = '<span class="pulse-live">●</span> LIVE FEED';
    };

    liveWs.onmessage = (event) => {
      try {
        const badge = document.querySelector('.ticker-badge');
        if (badge && !badge.innerHTML.includes('LIVE FEED')) {
          badge.innerHTML = '<span class="pulse-live">●</span> LIVE FEED';
        }
        const msg = JSON.parse(event.data);
        if (msg.type === 'MARKET_TICK_STREAM' && msg.quotes) {
          renderLiveTicker(msg.quotes);
          if (msg.treasury) {
            updateTreasuryFromWs(msg.treasury);
          }
        }
      } catch (e) {
        console.warn('Error parsing WS tick:', e);
      }
    };

    liveWs.onclose = () => {
      console.warn('WebSocket stream disconnected. Reconnecting in 3s...');
      const badge = document.querySelector('.ticker-badge');
      if (badge) badge.innerHTML = '<span style="color:#ff4757;">●</span> RECONNECTING...';
      setTimeout(connectLiveMarketWebSocket, 3000);
    };

    liveWs.onerror = (err) => {
      console.warn('WebSocket error:', err);
    };
  } catch (err) {
    console.warn('WebSocket initialization error:', err);
  }
}

function renderLiveTicker(quotes) {
  const track = document.getElementById('liveTickerTrack');
  if (!track) return;

  track.innerHTML = '';
  quotes.forEach(q => {
    const chip = document.createElement('div');
    const prev = previousPrices[q.symbol] || q.ltp;
    const isUp = q.ltp >= prev;
    previousPrices[q.symbol] = q.ltp;

    const flashClass = isUp ? 'flash-up' : 'flash-down';
    const tickClass = q.change >= 0 ? 'tick-up' : 'tick-down';
    const sign = q.change >= 0 ? '+' : '';

    chip.className = `ticker-chip ${flashClass}`;
    chip.innerHTML = `
      <span class="sym">${q.symbol.replace('.NS', '')}</span>
      <span class="price">₹${q.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
      <span class="${tickClass}">${sign}${q.change}%</span>
    `;
    track.appendChild(chip);

    setTimeout(() => {
      chip.classList.remove('flash-up', 'flash-down');
    }, 400);
  });
}

function updateTreasuryFromWs(data) {
  applyTreasuryMetrics(data);
}


// ==========================================
// AUTHENTICATION & SESSION MANAGEMENT
// ==========================================

function getAuthToken() {
  return localStorage.getItem('ai_trader_token') || '';
}

async function checkAuthStatus() {
  try {
    const res = await apiFetch('/api/auth/me');
    if (res.ok) {
      const data = await res.json();
      const userNameEl = document.getElementById('userName');
      const userRoleEl = document.getElementById('userRole');
      const btnLogout = document.getElementById('btnLogout');

      if (userNameEl) userNameEl.innerText = data.username || 'Admin';
      if (userRoleEl) userRoleEl.innerText = data.role || 'OWNER';
      if (btnLogout) btnLogout.style.display = data.is_guest ? 'none' : 'inline-block';
    }
  } catch (err) {
    console.warn('Auth check error:', err);
  }
}

function openLoginModal() {
  const modal = document.getElementById('loginModal');
  if (modal) {
    modal.style.display = 'flex';
    document.getElementById('loginErrorMsg').style.display = 'none';
    document.getElementById('loginSuccessMsg').style.display = 'none';
  }
}

function closeLoginModal() {
  const modal = document.getElementById('loginModal');
  if (modal) modal.style.display = 'none';
}

async function handleLoginSubmit(event) {
  event.preventDefault();
  const username = document.getElementById('inputUsername').value.trim();
  const password = document.getElementById('inputPassword').value.trim();
  const errorMsg = document.getElementById('loginErrorMsg');
  const successMsg = document.getElementById('loginSuccessMsg');
  const btnSubmit = document.getElementById('btnLoginSubmit');

  errorMsg.style.display = 'none';
  successMsg.style.display = 'none';
  btnSubmit.disabled = true;
  btnSubmit.innerText = 'Authenticating...';

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    if (res.ok) {
      const data = await res.json();
      setAuthToken(data.access_token);
      successMsg.innerText = 'Login successful! Access granted.';
      successMsg.style.display = 'block';

      await checkAuthStatus();
      setTimeout(() => {
        closeLoginModal();
        btnSubmit.disabled = false;
        btnSubmit.innerText = 'Sign In';
      }, 700);
    } else {
      const err = await res.json();
      errorMsg.innerText = err.detail || 'Authentication failed. Check credentials.';
      errorMsg.style.display = 'block';
      btnSubmit.disabled = false;
      btnSubmit.innerText = 'Sign In';
    }
  } catch (err) {
    errorMsg.innerText = `Network error: ${err.message}`;
    errorMsg.style.display = 'block';
    btnSubmit.disabled = false;
    btnSubmit.innerText = 'Sign In';
  }
}

function handleLogout() {
  setAuthToken('');
  alert('You have logged out.');
  window.location.reload();
}

// ==========================================
// REMOTE ACCESS ANYWHERE MODAL
// ==========================================

let cachedLanUrl = 'http://localhost:8000';

async function fetchNetworkInfo() {
  try {
    const res = await apiFetch('/api/system/network-info');
    if (res.ok) {
      const data = await res.json();
      cachedLanUrl = data.lan_url;
      const lanEl = document.getElementById('lanUrlDisplay');
      if (lanEl) lanEl.innerText = data.lan_url;
    }
  } catch (err) {
    console.warn('Network info fetch error:', err);
  }
}

function openRemoteAccessModal() {
  const modal = document.getElementById('remoteAccessModal');
  if (modal) {
    modal.style.display = 'flex';
    fetchNetworkInfo();
  }
}

function closeRemoteAccessModal() {
  const modal = document.getElementById('remoteAccessModal');
  if (modal) modal.style.display = 'none';
}

function copyLanUrl() {
  navigator.clipboard.writeText(cachedLanUrl).then(() => {
    alert(`Copied ${cachedLanUrl} to clipboard! Paste it into your mobile browser on the same Wi-Fi.`);
  }).catch(() => {
    prompt('Copy this URL to open on your phone:', cachedLanUrl);
  });
}

// ==========================================
// AI AGENT TRAINING & SKILL MASTERY CONTROLLER
// ==========================================

async function fetchTrainingStatus() {
  try {
    const res = await apiFetch('/api/training/status');
    if (res.ok) {
      const data = await res.json();
      renderTrainingStatus(data);
    }
  } catch (err) {
    console.warn('Failed to fetch training status:', err);
  }
}

function renderTrainingStatus(data) {
  if (!data) return;

  const epEl = document.getElementById('trainEpisodesCount');
  if (epEl) epEl.innerText = data.total_episodes_completed || 0;

  const statusLabel = document.getElementById('trainStatusLabel');
  if (statusLabel) {
    if (data.status === 'TRAINING') {
      statusLabel.innerHTML = '<span class="text-green">⚡ Historical Simulation Cycle In Progress...</span>';
    } else {
      statusLabel.innerHTML = '<span class="text-cyan">🌙 Continuous Off-Market Daemon Active</span>';
    }
  }

  const winRateEl = document.getElementById('trainWinRate');
  if (winRateEl) {
    const wr = data.win_rate_pct || 0;
    winRateEl.innerText = `${wr.toFixed(1)}%`;
    winRateEl.className = wr >= 50 ? 't-metric-val text-green' : 't-metric-val text-yellow';
  }

  const pfEl = document.getElementById('trainProfitFactor');
  if (pfEl) {
    const pf = data.profit_factor || 0;
    pfEl.innerText = pf.toFixed(2);
    pfEl.className = pf >= 1.5 ? 't-metric-val text-cyan' : 't-metric-val text-yellow';
  }

  const skillsEl = document.getElementById('trainSkillsMastered');
  if (skillsEl) {
    skillsEl.innerText = `${data.skills_mastered_count || 0} / ${data.total_skills_count || 12}`;
  }

  // Render 12 Skills Curriculum Grid
  const gridEl = document.getElementById('skillsCurriculumGrid');
  if (gridEl && Array.isArray(data.modules)) {
    gridEl.innerHTML = data.modules.map(mod => {
      let badgeClass = 'badge-mastery-novice';
      if (mod.mastery_level === 'INSTITUTIONAL_MASTER') badgeClass = 'badge-mastery-master';
      else if (mod.mastery_level === 'PROFICIENT') badgeClass = 'badge-mastery-proficient';
      else if (mod.mastery_level === 'COMPETENT') badgeClass = 'badge-mastery-competent';

      let barColor = '#f59e0b';
      if (mod.current_accuracy_pct >= 85) barColor = '#8b5cf6';
      else if (mod.current_accuracy_pct >= 75) barColor = '#10b981';
      else if (mod.current_accuracy_pct >= 60) barColor = '#3b82f6';

      return `
        <div class="skill-card glass">
          <div>
            <div class="skill-header">
              <div class="skill-title">${mod.name}</div>
              <span class="${badgeClass}">${mod.mastery_level.replace('_', ' ')}</span>
            </div>
            <div class="skill-desc mt-1">${mod.description}</div>
          </div>
          <div>
            <div class="skill-progress-bar-wrap">
              <div class="skill-progress-bar" style="width: ${Math.min(100, Math.max(5, mod.current_accuracy_pct))}%; background: ${barColor};"></div>
            </div>
            <div class="skill-footer">
              <span>Accuracy: <strong style="color:#fff;">${mod.current_accuracy_pct.toFixed(1)}%</strong> (Target ${mod.target_accuracy_pct}%)</span>
              <span><strong>${mod.episodes_trained}</strong> eps</span>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  // Render Recent Simulated Episodes Table
  const episodesBadge = document.getElementById('recentEpisodesCountBadge');
  if (episodesBadge) {
    episodesBadge.innerText = `${(data.recent_episodes || []).length} Episodes`;
  }

  const tableBody = document.getElementById('trainingEpisodesTableBody');
  if (tableBody) {
    if (!data.recent_episodes || data.recent_episodes.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center py-3 text-muted">Continuous offline simulation daemon is initializing episode batches...</td>
        </tr>
      `;
    } else {
      tableBody.innerHTML = data.recent_episodes.slice().reverse().map(ep => {
        const isWin = ep.pnl >= 0;
        const pnlColor = isWin ? 'text-green' : 'text-red';
        const pnlSign = isWin ? '+' : '';

        let qBadge = 'badge-accent';
        if (ep.decision_quality === 'EXCELLENT') qBadge = 'badge-risk-safe';
        else if (ep.decision_quality === 'GOOD') qBadge = 'badge-risk-moderate';
        else if (ep.decision_quality === 'FLAWED') qBadge = 'badge-risk-crit';

        return `
          <tr>
            <td style="font-family:monospace; font-weight:700; color:var(--accent-cyan);">${ep.episode_id}</td>
            <td style="font-weight:700;">${ep.symbol}</td>
            <td>₹${ep.entry_price.toFixed(2)} → ₹${ep.exit_price.toFixed(2)}</td>
            <td class="${pnlColor}" style="font-weight:700;">${pnlSign}₹${ep.pnl.toFixed(2)} (${pnlSign}${ep.pnl_pct.toFixed(2)}%)</td>
            <td><span class="text-green">+${ep.mfe_pct.toFixed(1)}%</span> / <span class="text-red">-${ep.mae_pct.toFixed(1)}%</span></td>
            <td><span class="badge badge-secondary" style="font-size:10px;">${ep.exit_reason}</span></td>
            <td><span class="${qBadge}">${ep.decision_quality}</span></td>
            <td style="font-size:11px; color:var(--text-muted); max-width:280px;">${ep.reflection_takeaway}</td>
          </tr>
        `;
      }).join('');
    }
  }
}

async function triggerTrainingCycle() {
  try {
    const res = await apiFetch('/api/training/start', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      alert(`🚀 ${data.message}`);
      fetchTrainingStatus();
    }
  } catch (err) {
    alert(`Failed to trigger training cycle: ${err.message}`);
  }
}

window.openDailyReportModal = async function openDailyReportModal() {
  const modal = document.getElementById('dailyReportModal') || document.getElementById('modalDailyReport');
  if (modal) {
    modal.style.display = 'flex';
  }
  await window.loadDailyReport();
};

window.closeDailyReportModal = function closeDailyReportModal() {
  const modal = document.getElementById('dailyReportModal') || document.getElementById('modalDailyReport');
  if (modal) modal.style.display = 'none';
};

window.loadDailyReport = async function loadDailyReport() {
  const contentEl = document.getElementById('dailyReportContent');
  const titleEl = document.getElementById('dailyReportTitle');
  const subtitleEl = document.getElementById('dailyReportSubtitle');
  if (!contentEl) return;

  contentEl.innerText = '⏳ Loading latest End-of-Day report...';
  try {
    const res = await apiFetch('/api/reports/daily/latest');
    if (res.ok) {
      const data = await res.json();
      if (titleEl && data.report) {
        titleEl.innerText = `Daily Market Close Report — ${data.report.date}`;
        subtitleEl.innerText = `Generated at ${data.report.generated_at} • Mode: ${data.report.broker_mode} (${data.report.client_code})`;
      }
      contentEl.innerText = data.markdown || JSON.stringify(data.report, null, 2);
    } else {
      contentEl.innerText = '❌ Failed to load daily report.';
    }
  } catch (err) {
    contentEl.innerText = `❌ Error: ${err.message}`;
  }
};

window.refreshDailyReport = async function refreshDailyReport() {
  const contentEl = document.getElementById('dailyReportContent');
  if (contentEl) contentEl.innerText = '🔄 Re-generating latest End-of-Day report...';
  try {
    const res = await apiFetch('/api/reports/daily/generate', { method: 'POST' });
    if (res.ok) {
      await window.loadDailyReport();
    } else {
      alert('Failed to re-generate report.');
    }
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
};




