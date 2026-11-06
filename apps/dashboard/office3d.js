/**
 * 'AGENT OFFICE 3D' — CLASSIC INSTITUTIONAL TRADING FLOOR ENGINE
 * Powered by Three.js with realistic WebGL rendering, classic Wall Street architecture:
 * - Rich dark walnut & mahogany paneling with fluted brass molding
 * - Classic banker lamps with translucent emerald green glass shades
 * - Polished dark parquet floor with golden zone inlays
 * - Elevated octagonal War Room trading pit with holographic 3D debate globe
 * - 3D multi-screen Bloomberg terminal arrays with live animated candlestick textures
 * - Animated 3D trader avatars with typing, breathing & gesturing idle animations
 * - Full OrbitControls: Free 3D orbit, zoom, pan, and cinematic camera presets
 */

// ============================================================
// 1. GLOBAL 3D TRADING OFFICE STATE
// ============================================================
const Office3D = {
  container: null,
  scene: null,
  camera: null,
  renderer: null,
  controls: null,
  
  animId: null,
  tick: 0,
  is3DActive: true,
  cinematicMode: false,
  cinematicAngle: 0,
  
  // Interactive Raycasting
  raycaster: new THREE.Raycaster(),
  mouse: new THREE.Vector2(),
  hoveredObject: null,
  selectedAgent: null,
  
  // Dynamic Canvas Textures for 3D Screens
  screenTextures: {},
  screenCanvases: {},
  agentMonitors: {},
  clickableObjects: [],
  liveWorkCache: {},
  quoteRibbon: 'Waiting for Delta quotes',
  
  // Animated 3D Objects Cache
  animatedObjects: [],
  deskSpotlights: [],
  holoGlobe: null,
  sparkParticles: null,
  haloRings: [],
  
  // Pre-configured Camera Angles
  cameraPresets: {
    isometric: { pos: [0, 42, 54], target: [0, 2, 0] },
    executive: { pos: [-20, 20, -5], target: [-18, 2, -16] },
    warroom: { pos: [0, 16, 12], target: [0, 2.5, -2] },
    quant: { pos: [20, 20, -5], target: [18, 2, -16] },
    risk: { pos: [16, 18, 24], target: [16, 2, 12] },
    overview: { pos: [0, 68, 10], target: [0, 0, 0] }
  }
};

// ============================================================
// 2. INITIALIZATION
// ============================================================
function initOffice3D() {
  const container = document.getElementById('office3DContainer');
  if (!container) return;
  Office3D.container = container;

  // 1. Scene & Atmosphere (Warm, Prestigious Classic Interior)
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0c101c);
  scene.fog = new THREE.FogExp2(0x0c101c, 0.009);
  Office3D.scene = scene;

  // 2. Perspective Camera
  const aspect = container.clientWidth / container.clientHeight;
  const camera = new THREE.PerspectiveCamera(45, aspect, 0.5, 300);
  camera.position.set(0, 42, 54);
  camera.lookAt(0, 2, 0);
  Office3D.camera = camera;

  // 3. WebGL Renderer with High-Fidelity Soft Shadows
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputEncoding = THREE.sRGBEncoding;
  container.appendChild(renderer.domElement);
  Office3D.renderer = renderer;

  // 4. OrbitControls for Free 3D Navigation
  if (typeof THREE.OrbitControls !== 'undefined') {
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0, 2, 0);
    controls.maxPolarAngle = Math.PI / 2.05; // Prevent camera clipping below floor
    controls.minDistance = 14;
    controls.maxDistance = 95;
    Office3D.controls = controls;
  }

  // 5. Build Dynamic Screen Canvas Textures
  setupDynamicScreenCanvases();

  // 6. Classical Interior Lighting
  setupClassicLighting(scene);

  // 7. Architectural Environment (Herringbone Floor, Mahogany Walls & Moldings)
  buildClassicArchitecture(scene);

  // 8. Giant Wall Displays with Ornate Brass Frames
  buildClassicWallDisplays(scene);

  // 9. Elevated Adversarial War Room Arena (Center)
  buildWarRoomArena(scene);

  // 10. 42U Enterprise Server Vault (Infrastructure Pod)
  build3DServerVault(scene);

  // 11. Trading Desks, Banker Lamps & 3D Trader Characters
  buildTradingPodsAndAvatars(scene);

  // 12. Classic Wall Street Bull Statue & Heritage Wall Clocks
  buildHeritageAccents(scene);

  // Event Listeners
  window.addEventListener('resize', onOffice3DResize);
  container.addEventListener('mousemove', onOffice3DMouseMove);
  container.addEventListener('click', onOffice3DClick);

  // Start Animation Loop
  animateOffice3D();
}

// ============================================================
// 3. DYNAMIC AGENT-SPECIFIC SCREEN CANVAS TEXTURES
// ============================================================
function setupDynamicScreenCanvases() {
  // Global Ticker Ribbon Canvas
  const tCanvas = document.createElement('canvas');
  tCanvas.width = 512; tCanvas.height = 64;
  Office3D.screenCanvases.ticker = tCanvas;
  Office3D.screenTextures.ticker = new THREE.CanvasTexture(tCanvas);

  // Fallback textures for generic monitors
  const cCanvas = document.createElement('canvas');
  cCanvas.width = 256; cCanvas.height = 160;
  Office3D.screenCanvases.chart = cCanvas;
  Office3D.screenTextures.chart = new THREE.CanvasTexture(cCanvas);

  const dCanvas = document.createElement('canvas');
  dCanvas.width = 256; dCanvas.height = 160;
  Office3D.screenCanvases.depth = dCanvas;
  Office3D.screenTextures.depth = new THREE.CanvasTexture(dCanvas);

  // Poll live agent work details from backend to keep monitors synced with real pipeline
  syncLiveWorkToMonitors();
  syncQuoteRibbon();
  setInterval(syncLiveWorkToMonitors, 8000);
  setInterval(syncQuoteRibbon, 8000);
}

async function syncLiveWorkToMonitors() {
  try {
    const token = localStorage.getItem('ai_trader_token') || '';
    const res = await fetch('/api/office/agents/live-work', {
      credentials: 'same-origin',
      headers: { ...(token ? { "Authorization": `Bearer ${token}` } : {}) }
    });
    if (res.ok) {
      const data = await res.json();
      if (data.agents_work) {
        Office3D.liveWorkCache = data.agents_work;
      }
    }
  } catch (e) {
    console.debug("[Office3D] live-work sync note:", e);
  }
}

async function syncQuoteRibbon() {
  try {
    const res = await fetch('/api/market/quotes', { credentials: 'same-origin' });
    if (!res.ok) return;
    const data = await res.json();
    const quotes = (data.quotes || []).filter(q => String(q.symbol || '').endsWith('USDT') && q.ltp);
    if (!quotes.length) return;
    Office3D.quoteRibbon = quotes.map(q => {
      const change = Number(q.change || 0);
      const sign = change >= 0 ? '+' : '';
      return `${q.symbol} ${Number(q.ltp).toLocaleString()} ${sign}${change.toFixed(2)}%`;
    }).join('   ');
  } catch (e) {
    console.debug('[Office3D] quote ribbon note:', e);
  }
}

function getOrCreateAgentMonitor(agentId, agentData) {
  if (Office3D.agentMonitors[agentId]) {
    return Office3D.agentMonitors[agentId];
  }

  // Left Screen: Role-specific visual chart / indicator / gauge
  const cCanvas = document.createElement('canvas');
  cCanvas.width = 256; cCanvas.height = 160;
  const cTex = new THREE.CanvasTexture(cCanvas);

  // Right Screen: Real-time working metrics, task, and formulas
  const dCanvas = document.createElement('canvas');
  dCanvas.width = 256; dCanvas.height = 160;
  const dTex = new THREE.CanvasTexture(dCanvas);

  const mon = {
    agentId: agentId,
    agentData: agentData,
    cCanvas: cCanvas,
    cTex: cTex,
    dCanvas: dCanvas,
    dTex: dTex,
    lastDrawnTick: -999
  };

  Office3D.agentMonitors[agentId] = mon;
  return mon;
}

function drawAgentSpecificScreens(mon, tick) {
  const agentId = mon.agentId.toLowerCase();
  const work = (Office3D.liveWorkCache && Office3D.liveWorkCache[agentId]) ? Office3D.liveWorkCache[agentId] : null;
  const aData = mon.agentData || {};
  const agentName = (work && work.name) ? work.name : (aData.name || agentId.toUpperCase());
  const activeSymbol = (work && work.active_target) ? work.active_target.symbol : (aData.activeSymbol || "—");
  const ltp = (work && work.active_target) ? work.active_target.ltp : "—";

  // ==========================================
  // 1. LEFT SCREEN: Domain-Specific Visualizer
  // ==========================================
  const ctxC = mon.cCanvas.getContext('2d');
  ctxC.fillStyle = '#030712';
  ctxC.fillRect(0, 0, 256, 160);

  // Top header bar
  ctxC.fillStyle = '#0f172a';
  ctxC.fillRect(0, 0, 256, 24);
  ctxC.fillStyle = '#38bdf8';
  ctxC.font = 'bold 10px monospace';
  ctxC.fillText(`${agentName} | ${activeSymbol}`, 8, 16);

  if (agentId.includes('tech') || agentId.includes('momentum')) {
    // Technical / Momentum: Candlestick chart + Cyan EMA + RSI
    ctxC.fillStyle = '#e2e8f0';
    ctxC.font = '9px monospace';
    ctxC.fillText(`${ltp} | RSI: 64.2`, 8, 36);

    const numCandles = 12;
    const candleW = 12;
    for (let i = 0; i < numCandles; i++) {
      const cx = 14 + i * 19;
      const isUp = (i + Math.floor(tick / 40)) % 3 !== 0;
      const color = isUp ? '#22c55e' : '#ef4444';
      const h = 20 + Math.sin(i * 0.9 + tick * 0.05) * 15;
      const yTop = 135 - h;

      // Wick
      ctxC.strokeStyle = color;
      ctxC.lineWidth = 1.2;
      ctxC.beginPath();
      ctxC.moveTo(cx + candleW / 2, yTop - 6);
      ctxC.lineTo(cx + candleW / 2, 135);
      ctxC.stroke();

      // Body
      ctxC.fillStyle = color;
      ctxC.fillRect(cx, yTop, candleW, h - 6);
    }

    // Cyan EMA curve
    ctxC.strokeStyle = '#06b6d4';
    ctxC.lineWidth = 2.0;
    ctxC.beginPath();
    for (let i = 0; i < numCandles; i++) {
      const cx = 14 + i * 19 + candleW / 2;
      const cy = 120 - Math.sin(i * 0.9 + tick * 0.05) * 14;
      if (i === 0) ctxC.moveTo(cx, cy);
      else ctxC.lineTo(cx, cy);
    }
    ctxC.stroke();

    ctxC.fillStyle = '#4ade80';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('▲ 20-EMA GOLDEN CROSS', 8, 152);

  } else if (agentId.includes('quant') || agentId.includes('backtest') || agentId.includes('screener')) {
    // Quant: Bell curve distribution / Monte Carlo Simulation
    ctxC.fillStyle = '#e2e8f0';
    ctxC.font = '9px monospace';
    ctxC.fillText('MONTE CARLO: 10k RUNS (68.4% WIN)', 8, 36);

    // Draw Bell Curve
    ctxC.strokeStyle = '#ec4899';
    ctxC.lineWidth = 2.2;
    ctxC.beginPath();
    for (let x = 10; x < 246; x += 4) {
      const normX = (x - 128) / 36;
      const y = 135 - Math.exp(-0.5 * normX * normX) * 80;
      if (x === 10) ctxC.moveTo(x, y);
      else ctxC.lineTo(x, y);
    }
    ctxC.stroke();

    // Shaded Win Zone
    ctxC.fillStyle = 'rgba(236, 72, 153, 0.25)';
    ctxC.beginPath();
    ctxC.moveTo(110, 135);
    for (let x = 110; x <= 220; x += 4) {
      const normX = (x - 128) / 36;
      const y = 135 - Math.exp(-0.5 * normX * normX) * 80;
      ctxC.lineTo(x, y);
    }
    ctxC.lineTo(220, 135);
    ctxC.closePath();
    ctxC.fill();

    ctxC.fillStyle = '#f472b6';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('EXP SHARPE: 1.82 | Z: 2.14', 8, 152);

  } else if (agentId.includes('risk') || agentId.includes('guard') || agentId.includes('compliance') || agentId.includes('qa')) {
    // Risk & Compliance: 15-Point Pre-Trade Audit Checklist
    ctxC.fillStyle = '#4ade80';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('🛡️ 15-POINT PRE-TRADE AUDIT: PASS', 8, 36);

    // Draw 15 checkmark boxes
    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 5; c++) {
        const bx = 16 + c * 46;
        const by = 48 + r * 26;
        ctxC.fillStyle = '#064e3b';
        ctxC.fillRect(bx, by, 40, 20);
        ctxC.strokeStyle = '#10b981';
        ctxC.strokeRect(bx, by, 40, 20);
        ctxC.fillStyle = '#a7f3d0';
        ctxC.font = 'bold 9px monospace';
        ctxC.fillText(`✔ #${r * 5 + c + 1}`, bx + 6, by + 14);
      }
    }

    ctxC.fillStyle = '#38bdf8';
    ctxC.font = '8px monospace';
    ctxC.fillText('DRAWDOWN: 0.0% / 2.0% | MAX LOSS: ₹38.50', 8, 152);

  } else if (agentId.includes('bull') || agentId.includes('bear') || agentId.includes('facilitator')) {
    // War Room Arena: Bull vs Bear Debate Gauge
    ctxC.fillStyle = '#e2e8f0';
    ctxC.font = '9px monospace';
    ctxC.fillText('ADVERSARIAL CONSENSUS GAUGE', 8, 36);

    // Tug-of-war split bar
    const bullW = 150 + Math.sin(tick * 0.08) * 15;
    const bearW = 236 - bullW;
    ctxC.fillStyle = '#16a34a';
    ctxC.fillRect(10, 52, bullW, 26);
    ctxC.fillStyle = '#dc2626';
    ctxC.fillRect(10 + bullW, 52, bearW, 26);

    ctxC.fillStyle = '#ffffff';
    ctxC.font = 'bold 10px monospace';
    ctxC.fillText('BULL 65% ▲', 18, 69);
    ctxC.fillText('35% BEAR ▼', 10 + bullW + 10, 69);

    ctxC.fillStyle = '#facc15';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('NET CONSENSUS: +0.60 (BULLISH)', 8, 102);
    ctxC.fillStyle = '#94a3b8';
    ctxC.fillText(`TARGET: ₹1,245.00 | SL: ₹1,215.00`, 8, 122);
    ctxC.fillStyle = '#4ade80';
    ctxC.fillText('R:R 2.0:1 | ADVANCED TO AUDIT GATE', 8, 142);

  } else if (agentId.includes('conservative_debator')) {
    // Tauric Conservative Debator: Fortress Shield & Tail-Risk Defense
    ctxC.fillStyle = '#94a3b8';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('🛡️ TAURIC CONSERVATIVE DEFENSE', 8, 36);

    ctxC.fillStyle = '#1e293b';
    ctxC.fillRect(10, 48, 236, 88);
    ctxC.strokeStyle = '#64748b';
    ctxC.strokeRect(10, 48, 236, 88);

    ctxC.fillStyle = '#f87171';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('CAPITAL RISK CAP: 1.5% (CURRENT: 1.1%)', 18, 66);
    ctxC.fillStyle = '#e2e8f0';
    ctxC.font = '9px monospace';
    ctxC.fillText('GAP BUFFER: 1.5x ATR (₹27.75)', 18, 86);
    ctxC.fillText('STOP LOSS: MANDATORY ₹1,215.00', 18, 104);
    ctxC.fillStyle = '#4ade80';
    ctxC.fillText('VETO STATUS: NO VETO [SAFETY APPROVED]', 18, 124);

    ctxC.fillStyle = '#60a5fa';
    ctxC.font = 'bold 8px monospace';
    ctxC.fillText('RULE: STEP-UP TRAILING ON +1.0x ATR ADVANCE', 8, 152);

  } else if (agentId.includes('aggressive_debator')) {
    // Tauric Aggressive Debator: Upside Convexity & Fibonacci Runway
    ctxC.fillStyle = '#ef4444';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('🐂 TAURIC UPSIDE CONVEXITY', 8, 36);

    ctxC.fillStyle = '#1e293b';
    ctxC.fillRect(10, 48, 236, 88);
    ctxC.strokeStyle = '#dc2626';
    ctxC.strokeRect(10, 48, 236, 88);

    ctxC.fillStyle = '#4ade80';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('UPSIDE RUNWAY: +2.8% [2.0:1 R:R]', 18, 66);
    ctxC.fillStyle = '#facc15';
    ctxC.font = '9px monospace';
    ctxC.fillText('FIBONACCI TARGET: 1.618x (₹1,245.00)', 18, 86);
    ctxC.fillText('SCALE-IN TRIGGER: ₹1,232.00 (+0.5%)', 18, 104);
    ctxC.fillStyle = '#38bdf8';
    ctxC.fillText('CONVICTION: HIGH (91%) MOMENTUM', 18, 124);

    ctxC.fillStyle = '#fbbf24';
    ctxC.font = 'bold 8px monospace';
    ctxC.fillText('ADVOCACY: DEPLOY FULL TRANCHE WITHOUT FEAR', 8, 152);

  } else if (agentId.includes('neutral_debator')) {
    // Tauric Neutral Debator: Kelly Criterion & Sharpe Calibration
    ctxC.fillStyle = '#06b6d4';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('⚖️ TAURIC KELLY CALIBRATION', 8, 36);

    ctxC.fillStyle = '#1e293b';
    ctxC.fillRect(10, 48, 236, 88);
    ctxC.strokeStyle = '#0891b2';
    ctxC.strokeRect(10, 48, 236, 88);

    ctxC.fillStyle = '#38bdf8';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('HALF-KELLY FRACTION: 0.42x', 18, 66);
    ctxC.fillStyle = '#a7f3d0';
    ctxC.font = '9px monospace';
    ctxC.fillText('CALIBRATED SIZE: 18 SHARES (0.72x)', 18, 86);
    ctxC.fillText('EXPECTED VALUE: +₹248.50/TRADE', 18, 104);
    ctxC.fillStyle = '#e2e8f0';
    ctxC.fillText('CONSENSUS: ARBITRATED CON / AGG', 18, 124);

    ctxC.fillStyle = '#22d3ee';
    ctxC.font = 'bold 8px monospace';
    ctxC.fillText('PORTFOLIO SHARPE: 1.82 | WIN RATE: 62.4%', 8, 152);

  } else if (agentId.includes('post_trade_reflector')) {
    // Tauric Post-Trade Reflector: Institutional Memory
    ctxC.fillStyle = '#a78bfa';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('🪞 INSTITUTIONAL MEMORY REFLECTOR', 8, 36);

    ctxC.fillStyle = '#1e293b';
    ctxC.fillRect(10, 48, 236, 88);
    ctxC.strokeStyle = '#7c3aed';
    ctxC.strokeRect(10, 48, 236, 88);

    ctxC.fillStyle = '#facc15';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('48 SETTLED TRADE LESSONS LOGGED', 18, 66);
    ctxC.fillStyle = '#4ade80';
    ctxC.font = '9px monospace';
    ctxC.fillText('ALPHA VS NIFTY50: +4.8% REALIZED', 18, 86);
    ctxC.fillStyle = '#e2e8f0';
    ctxC.fillText('RULE: LOCK PEAK INTRADAY GAINS AT +1.5%', 18, 104);
    ctxC.fillStyle = '#38bdf8';
    ctxC.fillText('REPEAT MISTAKE PREVENTION: 100%', 18, 124);

    ctxC.fillStyle = '#c084fc';
    ctxC.font = 'bold 8px monospace';
    ctxC.fillText("MISSION: NEVER REPEAT YESTERDAY'S MISTAKE", 8, 152);

  } else if (agentId.includes('prediction_market')) {
    // Tauric Polymarket Prediction Analyst
    ctxC.fillStyle = '#fbbf24';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('🎲 POLYMARKET CROWD ODDS', 8, 36);

    ctxC.fillStyle = '#1e293b';
    ctxC.fillRect(10, 48, 236, 88);
    ctxC.strokeStyle = '#d97706';
    ctxC.strokeRect(10, 48, 236, 88);

    ctxC.fillStyle = '#22c55e';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('RATE PAUSE ODDS: 96.5% YES', 18, 66);
    ctxC.fillStyle = '#e2e8f0';
    ctxC.font = '9px monospace';
    ctxC.fillText('GAMMA API TRADED VOL: $8.68M', 18, 86);
    ctxC.fillText('1-WEEK PROBABILITY DELTA: +1.8pp', 18, 104);
    ctxC.fillStyle = '#38bdf8';
    ctxC.fillText('REGIME IMPACT: BENIGN FOR EQUITIES', 18, 124);

    ctxC.fillStyle = '#fde68a';
    ctxC.font = 'bold 8px monospace';
    ctxC.fillText('SOURCE: GAMMA-API.POLYMARKET.COM (ZERO AUTH)', 8, 152);

  } else if (agentId.includes('social_intelligence')) {
    // Tauric Social Sentiment Intelligence
    ctxC.fillStyle = '#f472b6';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('📡 RETAIL SOCIAL INTELLIGENCE', 8, 36);

    ctxC.fillStyle = '#1e293b';
    ctxC.fillRect(10, 48, 236, 88);
    ctxC.strokeStyle = '#db2777';
    ctxC.strokeRect(10, 48, 236, 88);

    ctxC.fillStyle = '#4ade80';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('STOCKTWITS: 64% BULLISH CASHTAG', 18, 66);
    ctxC.fillStyle = '#e2e8f0';
    ctxC.font = '9px monospace';
    ctxC.fillText('REDDIT: 142 POSTS (r/IndianStreetBets)', 18, 86);
    ctxC.fillText('SPAM FILTER: 18 BOT POSTS DISCARDED', 18, 104);
    ctxC.fillStyle = '#38bdf8';
    ctxC.fillText('STATUS: ACCUMULATION BUZZ', 18, 124);

    ctxC.fillStyle = '#fbcfe8';
    ctxC.font = 'bold 8px monospace';
    ctxC.fillText('SENTIMENT SCORE: +0.48 [ORGANIC BUYING]', 8, 152);

  } else if (agentId.includes('exec') || agentId.includes('broker') || agentId.includes('cfo')) {
    // Execution & Broker: SmartAPI OMS Gateway
    ctxC.fillStyle = '#4ade80';
    ctxC.font = 'bold 9px monospace';
    ctxC.fillText('ANGELONE SMARTAPI (AACJ120032)', 8, 36);

    ctxC.fillStyle = '#1e293b';
    ctxC.fillRect(10, 46, 236, 92);
    ctxC.strokeStyle = '#059669';
    ctxC.strokeRect(10, 46, 236, 92);

    ctxC.fillStyle = '#facc15';
    ctxC.font = '9px monospace';
    ctxC.fillText('AVAILABLE MARGIN: ₹593.32', 18, 64);
    ctxC.fillStyle = '#e2e8f0';
    ctxC.fillText('ORDER ROUTE: INTRADAY (MIS)', 18, 82);
    ctxC.fillText('SLIPPAGE BUDGET: 0.05% MAX', 18, 100);
    ctxC.fillStyle = '#38bdf8';
    ctxC.fillText('STATUS: GATED READY / ARMED', 18, 120);

    ctxC.fillStyle = '#a7f3d0';
    ctxC.font = 'bold 8px monospace';
    ctxC.fillText('RUNWAY: 420 DAYS | CAPITAL: ₹2,000.00', 8, 152);

  } else {
    // Macro / News / General Sentiment
    ctxC.fillStyle = '#e2e8f0';
    ctxC.font = '9px monospace';
    ctxC.fillText('MARKET INTEL & SENTIMENT FLOW', 8, 36);

    // Polarity bar [-1.0 to +1.0]
    ctxC.fillStyle = '#1e293b';
    ctxC.fillRect(10, 50, 236, 16);
    ctxC.fillStyle = '#0284c7';
    ctxC.fillRect(128, 50, 60, 16); // +0.42 bar
    ctxC.fillStyle = '#ffffff';
    ctxC.font = 'bold 8px monospace';
    ctxC.fillText('[-1.0        0.0   ▲   +1.0]', 38, 62);

    ctxC.fillStyle = '#38bdf8';
    ctxC.font = '9px monospace';
    ctxC.fillText('SENTIMENT: +0.42 [MODERATELY BULLISH]', 8, 86);
    ctxC.fillText('INDIA VIX: 12.40 ▼ (LOW FEAR REGIME)', 8, 106);
    ctxC.fillText('NSE DISCLOSURES: 142 PARSED (0 FLAGS)', 8, 126);
    ctxC.fillStyle = '#4ade80';
    ctxC.fillText('STATUS: GLOBAL RISK-ON ACTIVE', 8, 146);
  }

  mon.cTex.needsUpdate = true;

  // ==========================================
  // 2. RIGHT SCREEN: Live Working Telemetry
  // ==========================================
  const ctxD = mon.dCanvas.getContext('2d');
  ctxD.fillStyle = '#020617';
  ctxD.fillRect(0, 0, 256, 160);

  // Top header bar
  ctxD.fillStyle = '#111827';
  ctxD.fillRect(0, 0, 256, 24);
  ctxD.fillStyle = '#facc15';
  ctxD.font = 'bold 9px monospace';
  ctxD.fillText('LIVE WORKING TELEMETRY', 8, 16);

  // Tabular working parameters from live work profile
  const opDesc = (work && work.operation_at_this_moment) 
    ? work.operation_at_this_moment.substring(0, 48) + "..."
    : (aData.task || "Computing active algorithmic model parameters");

  ctxD.fillStyle = '#94a3b8';
  ctxD.font = '8px monospace';
  ctxD.fillText('TARGET:', 8, 40);
  ctxD.fillStyle = '#38bdf8';
  ctxD.fillText(activeSymbol, 64, 40);

  ctxD.fillStyle = '#94a3b8';
  ctxD.fillText('CURRENT OP:', 8, 56);
  ctxD.fillStyle = '#fef08a';
  ctxD.fillText(opDesc.substring(0, 32), 8, 68);
  if (opDesc.length > 32) {
    ctxD.fillText(opDesc.substring(32, 64), 8, 80);
  }

  // Real Metrics snippet
  if (work && work.live_metrics) {
    const keys = Object.keys(work.live_metrics);
    const m1K = keys[0] || "Indicator 1";
    const m1V = work.live_metrics[m1K] || "Nominal";
    const m2K = keys[1] || "Indicator 2";
    const m2V = work.live_metrics[m2K] || "Active";

    ctxD.fillStyle = '#94a3b8';
    ctxD.fillText(`${m1K.substring(0, 10)}:`, 8, 98);
    ctxD.fillStyle = '#4ade80';
    ctxD.fillText(String(m1V).substring(0, 24), 80, 98);

    ctxD.fillStyle = '#94a3b8';
    ctxD.fillText(`${m2K.substring(0, 10)}:`, 8, 114);
    ctxD.fillStyle = '#67e8f9';
    ctxD.fillText(String(m2V).substring(0, 24), 80, 114);
  } else {
    ctxD.fillStyle = '#94a3b8';
    ctxD.fillText('CONFIDENCE:', 8, 98);
    ctxD.fillStyle = '#4ade80';
    ctxD.fillText(aData.confidence || "96.4%", 80, 98);

    ctxD.fillStyle = '#94a3b8';
    ctxD.fillText('STATUS:', 8, 114);
    ctxD.fillStyle = '#67e8f9';
    ctxD.fillText(aData.status || "RUNNING", 80, 114);
  }

  // Bottom live pulse
  ctxD.fillStyle = '#22c55e';
  ctxD.beginPath();
  ctxD.arc(14, 142, 4, 0, Math.PI * 2);
  ctxD.fill();

  ctxD.fillStyle = '#a7f3d0';
  ctxD.font = 'bold 8px monospace';
  ctxD.fillText('REAL-TIME AGENT TELEMETRY', 26, 145);

  mon.dTex.needsUpdate = true;
}

function updateDynamicScreenCanvases(tick) {
  // 1. Update Ticker Ribbon Canvas
  const ctxT = Office3D.screenCanvases.ticker.getContext('2d');
  ctxT.fillStyle = '#02040a';
  ctxT.fillRect(0, 0, 512, 64);
  ctxT.font = 'bold 16px monospace';
  const offset = (tick * 2) % 400;
  ctxT.fillStyle = '#38bdf8';
  ctxT.fillText(Office3D.quoteRibbon || 'Waiting for Delta quotes', -offset + 40, 38);
  Office3D.screenTextures.ticker.needsUpdate = true;

  // 2. Update individual agent monitors every 25 ticks
  if (tick % 25 === 0 && Office3D.agentMonitors) {
    Object.values(Office3D.agentMonitors).forEach(mon => {
      drawAgentSpecificScreens(mon, tick);
    });
  }
}


// ============================================================
// 4. CLASSICAL INTERIOR LIGHTING
// ============================================================
function setupClassicLighting(scene) {
  // Warm Ambient Tungsten Light (Prestige Private Banking Glow)
  const ambient = new THREE.AmbientLight(0xfff5ea, 0.70);
  scene.add(ambient);

  // Directional Sunlight streaming in from high skylights
  const sunLight = new THREE.DirectionalLight(0xffeedd, 0.90);
  sunLight.position.set(25, 45, 20);
  sunLight.castShadow = true;
  sunLight.shadow.mapSize.width = 2048;
  sunLight.shadow.mapSize.height = 2048;
  sunLight.shadow.camera.near = 0.5;
  sunLight.shadow.camera.far = 140;
  const d = 38;
  sunLight.shadow.camera.left = -d;
  sunLight.shadow.camera.right = d;
  sunLight.shadow.camera.top = d;
  sunLight.shadow.camera.bottom = -d;
  sunLight.shadow.bias = -0.0004;
  scene.add(sunLight);

  // Soft Secondary Fill Light
  const fillLight = new THREE.DirectionalLight(0xa5c4d4, 0.35);
  fillLight.position.set(-30, 30, -25);
  scene.add(fillLight);

  // War Room Central Spotlight
  const warRoomSpot = new THREE.SpotLight(0xfde047, 1.4, 35, Math.PI / 4, 0.5, 1);
  warRoomSpot.position.set(0, 18, -2);
  warRoomSpot.target.position.set(0, 0, -2);
  scene.add(warRoomSpot);
  scene.add(warRoomSpot.target);
}

// ============================================================
// 5. ARCHITECTURAL ENVIRONMENT (Herringbone Floor & Mahogany Walls)
// ============================================================
function buildClassicArchitecture(scene) {
  const floorW = 74, floorD = 54;

  // 1. Procedural Polished Dark Hardwood Parquet Texture
  const floorCanvas = document.createElement('canvas');
  floorCanvas.width = 512; floorCanvas.height = 512;
  const fCtx = floorCanvas.getContext('2d');
  
  // Base rich walnut color
  fCtx.fillStyle = '#22140d';
  fCtx.fillRect(0, 0, 512, 512);
  
  // Parquet plank grid
  fCtx.strokeStyle = '#180d08';
  fCtx.lineWidth = 2;
  const pSize = 32;
  for (let y = 0; y < 512; y += pSize) {
    for (let x = 0; x < 512; x += pSize) {
      const isAlt = ((x / pSize) + (y / pSize)) % 2 === 0;
      fCtx.fillStyle = isAlt ? '#2b1a11' : '#1e110a';
      fCtx.fillRect(x, y, pSize, pSize);
      fCtx.strokeRect(x, y, pSize, pSize);
      
      // Subtle wood grain lines
      fCtx.strokeStyle = 'rgba(255,255,255,0.02)';
      fCtx.beginPath();
      fCtx.moveTo(x + 4, y);
      fCtx.lineTo(x + pSize - 4, y + pSize);
      fCtx.stroke();
    }
  }

  const floorTexture = new THREE.CanvasTexture(floorCanvas);
  floorTexture.wrapS = THREE.RepeatWrapping;
  floorTexture.wrapT = THREE.RepeatWrapping;
  floorTexture.repeat.set(12, 9);

  const floorGeo = new THREE.PlaneGeometry(floorW, floorD);
  const floorMat = new THREE.MeshStandardMaterial({
    map: floorTexture,
    roughness: 0.35,
    metalness: 0.15
  });
  const floorMesh = new THREE.Mesh(floorGeo, floorMat);
  floorMesh.rotation.x = -Math.PI / 2;
  floorMesh.receiveShadow = true;
  scene.add(floorMesh);

  // Inlaid Polished Brass Border Ribbon around the floor
  const borderGeo = new THREE.BoxGeometry(floorW + 0.6, 0.08, floorD + 0.6);
  const brassMat = new THREE.MeshStandardMaterial({ color: 0xd4af37, roughness: 0.25, metalness: 0.85 });
  const borderMesh = new THREE.Mesh(borderGeo, brassMat);
  borderMesh.position.y = 0.02;
  scene.add(borderMesh);

  // 2. Classic Fluted Mahogany Walls
  const wallH = 14;
  const mahogMat = new THREE.MeshStandardMaterial({ color: 0x2e180f, roughness: 0.5, metalness: 0.1 });

  // Back Wall
  const backWallGeo = new THREE.BoxGeometry(floorW, wallH, 1.2);
  const backWall = new THREE.Mesh(backWallGeo, mahogMat);
  backWall.position.set(0, wallH / 2, -floorD / 2);
  backWall.receiveShadow = true;
  scene.add(backWall);

  // Side Left Wall
  const leftWallGeo = new THREE.BoxGeometry(1.2, wallH, floorD);
  const leftWall = new THREE.Mesh(leftWallGeo, mahogMat);
  leftWall.position.set(-floorW / 2, wallH / 2, 0);
  leftWall.receiveShadow = true;
  scene.add(leftWall);

  // Side Right Wall
  const rightWallGeo = new THREE.BoxGeometry(1.2, wallH, floorD);
  const rightWall = new THREE.Mesh(rightWallGeo, mahogMat);
  rightWall.position.set(floorW / 2, wallH / 2, 0);
  rightWall.receiveShadow = true;
  scene.add(rightWall);

  // Classical Baseboard and Crown Cornice (Brass / Gilded Wood)
  const baseboardGeo = new THREE.BoxGeometry(floorW, 1.0, 0.4);
  const baseboard = new THREE.Mesh(baseboardGeo, brassMat);
  baseboard.position.set(0, 0.5, -floorD / 2 + 0.7);
  scene.add(baseboard);

  const crownGeo = new THREE.BoxGeometry(floorW, 0.8, 0.6);
  const crown = new THREE.Mesh(crownGeo, brassMat);
  crown.position.set(0, wallH - 0.4, -floorD / 2 + 0.7);
  scene.add(crown);

  // 3. Stenciled Brass Floor Inlays (Zone Demarcations)
  buildFloorZoneInlays(scene);
}

function buildFloorZoneInlays(scene) {
  const zoneBrassMat = new THREE.MeshStandardMaterial({ color: 0xd4af37, roughness: 0.3, metalness: 0.8 });

  const zones = [
    { x: -18, z: -16, w: 26, d: 11, label: "ZONE I: EXECUTIVE & GLOBAL MACRO" },
    { x: 18, z: -16, w: 26, d: 11, label: "ZONE II: QUANT & TECHNICAL ALPHA LAB" },
    { x: -18, z: -2, w: 22, d: 12, label: "ZONE IV: NEWS & MACRO PULSE" },
    { x: 20, z: -2, w: 20, d: 12, label: "ZONE VI: CLUSTER & MEMORY VAULT" },
    { x: -18, z: 14, w: 26, d: 14, label: "ZONE V: FUNDAMENTAL & F&O DERIVATIVES" },
    { x: 17, z: 14, w: 28, d: 14, label: "ZONE VII: CENTRAL RISK & OMS FORTRESS" }
  ];

  zones.forEach(z => {
    // Thin brass floor rectangle marking the department
    const border = new THREE.BoxGeometry(z.w, 0.03, z.d);
    const wireframe = new THREE.LineSegments(
      new THREE.EdgesGeometry(border),
      new THREE.LineBasicMaterial({ color: 0xd4af37, linewidth: 1.5 })
    );
    wireframe.position.set(z.x, 0.03, z.z);
    scene.add(wireframe);
  });
}

// ============================================================
// 6. GIANT WALL DISPLAYS WITH ORNATE BRASS FRAMES
// ============================================================
function buildClassicWallDisplays(scene) {
  const brassMat = new THREE.MeshStandardMaterial({ color: 0xd4af37, roughness: 0.25, metalness: 0.85 });

  // 1. Ticker Ribbon along the top frieze
  const tickerGeo = new THREE.PlaneGeometry(64, 2.2);
  const tickerMat = new THREE.MeshBasicMaterial({ map: Office3D.screenTextures.ticker });
  const tickerMesh = new THREE.Mesh(tickerGeo, tickerMat);
  tickerMesh.position.set(0, 12.2, -26.3);
  scene.add(tickerMesh);

  // 2. Left Wall Display (Candlestick 5M Chart)
  const d1Frame = new THREE.Mesh(new THREE.BoxGeometry(16.5, 9.5, 0.4), brassMat);
  d1Frame.position.set(-18, 6.8, -26.3);
  scene.add(d1Frame);
  
  const d1Screen = new THREE.Mesh(
    new THREE.PlaneGeometry(15.5, 8.5),
    new THREE.MeshBasicMaterial({ map: Office3D.screenTextures.chart })
  );
  d1Screen.position.set(-18, 6.8, -26.05);
  scene.add(d1Screen);

  // 3. Center Wall Display (Angel One Gateway & Level-2 DOM Depth)
  const d2Frame = new THREE.Mesh(new THREE.BoxGeometry(19.5, 9.5, 0.4), brassMat);
  d2Frame.position.set(0, 6.8, -26.3);
  scene.add(d2Frame);

  const d2Screen = new THREE.Mesh(
    new THREE.PlaneGeometry(18.5, 8.5),
    new THREE.MeshBasicMaterial({ map: Office3D.screenTextures.depth })
  );
  d2Screen.position.set(0, 6.8, -26.05);
  scene.add(d2Screen);

  // 4. Right Wall Display (Sector Rotation Heatmap)
  const d3Frame = new THREE.Mesh(new THREE.BoxGeometry(16.5, 9.5, 0.4), brassMat);
  d3Frame.position.set(18, 6.8, -26.3);
  scene.add(d3Frame);

  const d3Screen = new THREE.Mesh(
    new THREE.PlaneGeometry(15.5, 8.5),
    new THREE.MeshBasicMaterial({ map: Office3D.screenTextures.chart })
  );
  d3Screen.position.set(18, 6.8, -26.05);
  scene.add(d3Screen);
}

// ============================================================
// 7. ELEVATED ADVERSARIAL WAR ROOM ARENA (CENTER)
// ============================================================
function buildWarRoomArena(scene) {
  const pitX = 0, pitY = 0.35, pitZ = -2;
  const radius = 6.2;

  // 1. Raised Octagonal Mahogany Dais
  const daisGeo = new THREE.CylinderGeometry(radius, radius + 0.4, 0.6, 8);
  const daisMat = new THREE.MeshStandardMaterial({ color: 0x3a1e12, roughness: 0.35, metalness: 0.1 });
  const dais = new THREE.Mesh(daisGeo, daisMat);
  dais.position.set(pitX, pitY, pitZ);
  dais.receiveShadow = true;
  scene.add(dais);

  // Polished Brass Trim around dais
  const daisTrimGeo = new THREE.TorusGeometry(radius + 0.1, 0.08, 8, 8);
  const brassMat = new THREE.MeshStandardMaterial({ color: 0xd4af37, roughness: 0.25, metalness: 0.85 });
  const daisTrim = new THREE.Mesh(daisTrimGeo, brassMat);
  daisTrim.rotation.x = Math.PI / 2;
  daisTrim.position.set(pitX, pitY + 0.3, pitZ);
  scene.add(daisTrim);

  // 2. Brass Balustrades & Velvet Safety Rail
  for (let i = 0; i < 8; i++) {
    const angle = (i / 8) * Math.PI * 2;
    const postX = pitX + Math.cos(angle) * (radius - 0.2);
    const postZ = pitZ + Math.sin(angle) * (radius - 0.2);
    
    // Brass Post
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 1.4, 8), brassMat);
    post.position.set(postX, pitY + 0.8, postZ);
    scene.add(post);
  }

  // 3. Central Digital Debate Conference Table
  const tableGeo = new THREE.CylinderGeometry(2.4, 2.6, 0.8, 16);
  const tableMat = new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.3, metalness: 0.3 });
  const table = new THREE.Mesh(tableGeo, tableMat);
  table.position.set(pitX, pitY + 0.65, pitZ);
  scene.add(table);

  // Glowing Table Surface Ring (Bull Green vs Bear Red)
  const ringGeo = new THREE.RingGeometry(1.6, 2.3, 32);
  const ringMat = new THREE.MeshBasicMaterial({ color: 0xfacc15, side: THREE.DoubleSide });
  const tableRing = new THREE.Mesh(ringGeo, ringMat);
  tableRing.rotation.x = -Math.PI / 2;
  tableRing.position.set(pitX, pitY + 1.06, pitZ);
  scene.add(tableRing);

  // 4. Floating 3D Rotating Holographic Globe & Consensus Model
  const globeGeo = new THREE.IcosahedronGeometry(0.9, 1);
  const globeMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.85 });
  const holoGlobe = new THREE.Mesh(globeGeo, globeMat);
  holoGlobe.position.set(pitX, pitY + 2.5, pitZ);
  scene.add(holoGlobe);
  Office3D.holoGlobe = holoGlobe;

  // Floating Consensus Badge (BULL 65% ▲ | BEAR 35% ▼)
  const badgeCanvas = document.createElement('canvas');
  badgeCanvas.width = 256; badgeCanvas.height = 64;
  const bCtx = badgeCanvas.getContext('2d');
  bCtx.fillStyle = 'rgba(2, 6, 23, 0.9)';
  bCtx.fillRect(0, 0, 256, 64);
  bCtx.strokeStyle = '#facc15';
  bCtx.lineWidth = 3;
  bCtx.strokeRect(0, 0, 256, 64);
  bCtx.font = 'bold 16px monospace';
  bCtx.fillStyle = '#22c55e';
  bCtx.fillText('BULL 65% ▲', 12, 38);
  bCtx.fillStyle = '#ef4444';
  bCtx.fillText('35% BEAR ▼', 136, 38);
  
  const badgeTex = new THREE.CanvasTexture(badgeCanvas);
  const badgeMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(2.4, 0.6),
    new THREE.MeshBasicMaterial({ map: badgeTex, side: THREE.DoubleSide, transparent: true })
  );
  badgeMesh.position.set(pitX, pitY + 3.6, pitZ);
  scene.add(badgeMesh);
  Office3D.animatedObjects.push({ mesh: badgeMesh, type: "billboard" });

  // 5. Electric Debate Particles / Thesis Sparks Jumping Across Table
  const sparkGeo = new THREE.BufferGeometry();
  const sparkCount = 30;
  const sparkPos = new Float32Array(sparkCount * 3);
  for (let i = 0; i < sparkCount * 3; i += 3) {
    sparkPos[i] = pitX + (Math.random() - 0.5) * 3;
    sparkPos[i+1] = pitY + 1.2 + Math.random() * 1.5;
    sparkPos[i+2] = pitZ + (Math.random() - 0.5) * 3;
  }
  sparkGeo.setAttribute('position', new THREE.BufferAttribute(sparkPos, 3));
  const sparkMat = new THREE.PointsMaterial({ color: 0xfacc15, size: 0.15, transparent: true, opacity: 0.9 });
  const sparkParticles = new THREE.Points(sparkGeo, sparkMat);
  scene.add(sparkParticles);
  Office3D.sparkParticles = sparkParticles;
}

// ============================================================
// 8. 42U ENTERPRISE SERVER VAULT (INFRASTRUCTURE CORNER)
// ============================================================
function build3DServerVault(scene) {
  const rackX = 26, rackZ = -2;
  const darkSteel = new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.3, metalness: 0.7 });
  const glassMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.1, transparent: true, opacity: 0.6 });

  for (let i = 0; i < 2; i++) {
    const rx = rackX + i * 2.8;
    // Cabinet
    const cabinet = new THREE.Mesh(new THREE.BoxGeometry(2.2, 7.5, 2.2), darkSteel);
    cabinet.position.set(rx, 3.75, rackZ);
    cabinet.castShadow = true;
    scene.add(cabinet);

    // Glass Door with Reflection
    const door = new THREE.Mesh(new THREE.PlaneGeometry(1.8, 7.0), glassMat);
    door.position.set(rx, 3.75, rackZ + 1.12);
    scene.add(door);

    // Server Blades with Blinking Status LEDs
    for (let u = 0; u < 7; u++) {
      const uy = 1.0 + u * 0.9;
      const blade = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.65, 1.8), new THREE.MeshStandardMaterial({ color: 0x1e293b }));
      blade.position.set(rx, uy, rackZ + 0.1);
      scene.add(blade);

      // Blinking LEDs
      const ledMat = new THREE.MeshBasicMaterial({ color: (u % 2 === 0) ? 0x10b981 : 0x06b6d4 });
      const led = new THREE.Mesh(new THREE.SphereGeometry(0.04, 6, 6), ledMat);
      led.position.set(rx - 0.6, uy, rackZ + 1.05);
      scene.add(led);
      Office3D.animatedObjects.push({ mesh: led, type: "blinking_led", offset: u + i });
    }
  }
}

// ============================================================
// 9. TRADING PODS, BANKER LAMPS & 3D TRADER AVATARS
// ============================================================
function buildTradingPodsAndAvatars(scene) {
  // Use existing agents list or default 30 agents from PixelOffice
  const agents = (typeof PixelOffice !== 'undefined' && PixelOffice.agents) ? PixelOffice.agents : [];

  // Desk 3D Topology mapping 30 agents cleanly in 3D world coordinates
  const deskSpecs = [
    // --- ZONE I: EXECUTIVE & GLOBAL MACRO (Top-Left) ---
    { id: "exec_pod", x: -18, z: -16, w: 9, d: 3.8, agentIds: ["pm_agent", "cio_agent", "global_agent"] },
    
    // --- ZONE II: QUANT & TECHNICAL ALPHA LAB (Top-Right) ---
    { id: "tech_pod", x: 14, z: -16, w: 9, d: 3.8, agentIds: ["tech_agent", "momentum_agent", "quant_agent"] },
    { id: "regime_pod", x: 23, z: -16, w: 6, d: 3.8, agentIds: ["regime_agent", "backtest_agent"] },
    
    // --- ZONE IV: NEWS, SENTIMENT & MACRO (Mid-Left) ---
    { id: "news_pod", x: -18, z: -2, w: 9, d: 3.8, agentIds: ["news_agent", "sentiment_agent", "macro_agent"] },
    
    // --- ZONE III: WAR ROOM ARENA (Center) ---
    { id: "bull_desk", x: -3.6, z: -2, w: 2.8, d: 2.4, agentIds: ["bull_agent"] },
    { id: "bear_desk", x: 3.6, z: -2, w: 2.8, d: 2.4, agentIds: ["bear_agent"] },
    { id: "facilitator_desk", x: 0, z: -5.0, w: 3.4, d: 2.4, agentIds: ["facilitator"] },
    { id: "academy_pod", x: 8.5, z: -2, w: 5.5, d: 3.2, agentIds: ["intern_agent", "mentor_agent"] },
    
    // --- ZONE VI: CTO & CLUSTER (Mid-Right) ---
    { id: "cto_pod", x: 19, z: -2, w: 6.5, d: 3.4, agentIds: ["cto_agent", "learning_agent", "memory_agent"] },
    
    // --- ZONE V: FUNDAMENTAL & DERIVATIVES (Bottom-Left) ---
    { id: "fund_pod", x: -18, z: 14, w: 9, d: 3.8, agentIds: ["fundamental_agent", "valuation_agent", "sector_agent"] },
    { id: "fo_pod", x: -8, z: 14, w: 6, d: 3.8, agentIds: ["options_agent", "fo_agent"] },
    
    // --- ZONE VII: CENTRAL RISK & OMS FORTRESS (Bottom-Right) ---
    { id: "risk_pod", x: 9, z: 14, w: 7, d: 3.8, agentIds: ["risk_sentinel", "position_guardian"] },
    { id: "audit_pod", x: 17, z: 14, w: 6.5, d: 3.8, agentIds: ["compliance_agent", "qa_agent"] },
    { id: "exec_gateway_pod", x: 25, z: 14, w: 6.5, d: 3.8, agentIds: ["execution_agent", "broker_agent", "cfo_agent"] },

    // --- ZONE VIII: TAURIC 3-WAY RISK DEBATE ARENA (Forward Right) ---
    { id: "tauric_risk_pod", x: 10, z: 22, w: 9, d: 3.8, agentIds: ["conservative_debator", "aggressive_debator", "neutral_debator"] },

    // --- ZONE IX: TAURIC CROWD INTELLIGENCE & MEMORY (Forward Left) ---
    { id: "tauric_intel_pod", x: -10, z: 22, w: 9, d: 3.8, agentIds: ["post_trade_reflector", "prediction_market_analyst", "social_intelligence"] }
  ];

  deskSpecs.forEach(ds => {
    buildSingleTradingDesk(scene, ds);
  });
}

function buildSingleTradingDesk(scene, spec) {
  const mahoganyMat = new THREE.MeshStandardMaterial({ color: 0x2e180f, roughness: 0.35, metalness: 0.15 });
  const leatherPadMat = new THREE.MeshStandardMaterial({ color: 0x0f2d1e, roughness: 0.6 }); // Classic banker green leather
  const brassMat = new THREE.MeshStandardMaterial({ color: 0xd4af37, roughness: 0.25, metalness: 0.85 });

  // 1. Desk Tabletop
  const tableH = 1.9;
  const deskTop = new THREE.Mesh(new THREE.BoxGeometry(spec.w, 0.2, spec.d), mahoganyMat);
  deskTop.position.set(spec.x, tableH, spec.z);
  deskTop.castShadow = true;
  deskTop.receiveShadow = true;
  scene.add(deskTop);

  // Inlaid Dark Green Leather Blotter
  const blotter = new THREE.Mesh(new THREE.BoxGeometry(spec.w - 0.8, 0.04, spec.d - 0.8), leatherPadMat);
  blotter.position.set(spec.x, tableH + 0.11, spec.z);
  scene.add(blotter);

  // Brass Beveled Trim along front edge
  const edgeTrim = new THREE.Mesh(new THREE.BoxGeometry(spec.w, 0.08, 0.08), brassMat);
  edgeTrim.position.set(spec.x, tableH + 0.1, spec.z + spec.d / 2);
  scene.add(edgeTrim);

  // Solid Mahogany Pedestal Legs with Brass Feet
  const legW = 0.5, legD = spec.d - 0.4;
  const leg1 = new THREE.Mesh(new THREE.BoxGeometry(legW, tableH, legD), mahoganyMat);
  leg1.position.set(spec.x - spec.w / 2 + 0.4, tableH / 2, spec.z);
  leg1.castShadow = true;
  scene.add(leg1);

  const leg2 = new THREE.Mesh(new THREE.BoxGeometry(legW, tableH, legD), mahoganyMat);
  leg2.position.set(spec.x + spec.w / 2 - 0.4, tableH / 2, spec.z);
  leg2.castShadow = true;
  scene.add(leg2);

  // 2. Classic Banker's Lamp (Emerald Green Glass Shade on Brass Arm)
  buildBankerLamp(scene, spec.x - spec.w / 2 + 1.2, tableH + 0.2, spec.z - 0.4);

  // 3. Multi-Monitor Bloomberg Display Rig
  const agentCount = spec.agentIds.length;
  const slotWidth = spec.w / agentCount;

  spec.agentIds.forEach((agentId, idx) => {
    const chairX = spec.x - spec.w / 2 + slotWidth * (idx + 0.5);
    const chairZ = spec.z + 1.3;

    const agentData = (typeof PixelOffice !== 'undefined' && PixelOffice.agents) 
      ? PixelOffice.agents.find(a => a.id === agentId)
      : { id: agentId, name: agentId.toUpperCase(), activeSymbol: "RELIANCE.NS" };

    // Build Dual 3D Monitors for this seat with agent-specific live data
    build3DMonitorPair(scene, chairX, tableH + 0.2, spec.z - 0.3, agentId, agentData);

    // Build Executive Leather Trading Chair
    buildExecutiveChair(scene, chairX, spec.z + 1.1);

    // Build 3D Animated Trader Avatar
    buildTraderAvatar(scene, chairX, tableH + 0.3, spec.z + 0.85, agentId, agentData);
  });
}

// ------------------------------------------------------------
// Classic Emerald Banker's Lamp
// ------------------------------------------------------------
function buildBankerLamp(scene, x, y, z) {
  const brassMat = new THREE.MeshStandardMaterial({ color: 0xd4af37, roughness: 0.2, metalness: 0.9 });
  const emeraldMat = new THREE.MeshPhysicalMaterial({
    color: 0x059669,
    emissive: 0x047857,
    emissiveIntensity: 0.6,
    roughness: 0.1,
    transmission: 0.4,
    transparent: true,
    opacity: 0.95
  });

  // Brass Base & Curved Neck
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.3, 0.08, 12), brassMat);
  base.position.set(x, y + 0.04, z);
  scene.add(base);

  const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.7, 8), brassMat);
  stem.position.set(x, y + 0.38, z);
  scene.add(stem);

  // Emerald Green Glass Shade (Half-Cylinder)
  const shade = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.65, 12, 1, false, 0, Math.PI), emeraldMat);
  shade.rotation.z = Math.PI / 2;
  shade.rotation.x = Math.PI;
  shade.position.set(x, y + 0.72, z);
  scene.add(shade);

  // Soft Emerald Point Light illuminating desk
  const lampLight = new THREE.PointLight(0x34d399, 0.55, 4.5);
  lampLight.position.set(x, y + 0.6, z);
  scene.add(lampLight);
}

// ------------------------------------------------------------
// Dual 3D Bloomberg Monitors on Articulated Brass Arm
// ------------------------------------------------------------
function build3DMonitorPair(scene, x, y, z, agentId, agentData) {
  const armMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.3, metalness: 0.8 });
  const frameMat = new THREE.MeshStandardMaterial({ color: 0x090d16, roughness: 0.2 });

  // Center Articulated Arm Stand
  const stand = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.1, 0.8, 8), armMat);
  stand.position.set(x, y + 0.4, z - 0.2);
  scene.add(stand);

  // Get or create dedicated agent monitor canvas textures
  const safeAgentId = agentId || "general_analyst";
  const mon = getOrCreateAgentMonitor(safeAgentId, agentData);
  drawAgentSpecificScreens(mon, 0);

  // Left Monitor (Domain Visualizer)
  const monW = 1.35, monH = 0.85;
  const leftMon = new THREE.Mesh(new THREE.BoxGeometry(monW, monH, 0.08), frameMat);
  leftMon.position.set(x - 0.72, y + 0.75, z);
  leftMon.rotation.y = 0.18; // Angled toward trader
  leftMon.userData = { agentId: safeAgentId, agentData: agentData };
  scene.add(leftMon);

  const leftScreen = new THREE.Mesh(
    new THREE.PlaneGeometry(monW - 0.08, monH - 0.08),
    new THREE.MeshBasicMaterial({ map: mon.cTex })
  );
  leftScreen.position.set(x - 0.72, y + 0.75, z + 0.045);
  leftScreen.rotation.y = 0.18;
  leftScreen.userData = { agentId: safeAgentId, agentData: agentData };
  scene.add(leftScreen);

  // Right Monitor (Live Working Telemetry)
  const rightMon = new THREE.Mesh(new THREE.BoxGeometry(monW, monH, 0.08), frameMat);
  rightMon.position.set(x + 0.72, y + 0.75, z);
  rightMon.rotation.y = -0.18;
  rightMon.userData = { agentId: safeAgentId, agentData: agentData };
  scene.add(rightMon);

  const rightScreen = new THREE.Mesh(
    new THREE.PlaneGeometry(monW - 0.08, monH - 0.08),
    new THREE.MeshBasicMaterial({ map: mon.dTex })
  );
  rightScreen.position.set(x + 0.72, y + 0.75, z + 0.045);
  rightScreen.rotation.y = -0.18;
  rightScreen.userData = { agentId: safeAgentId, agentData: agentData };
  scene.add(rightScreen);

  if (Office3D.clickableObjects) {
    Office3D.clickableObjects.push(leftScreen, rightScreen, leftMon, rightMon);
  }
}

// ------------------------------------------------------------
// Executive Button-Tufted Leather Trading Chair
// ------------------------------------------------------------
function buildExecutiveChair(scene, x, z) {
  const leatherMat = new THREE.MeshStandardMaterial({ color: 0x1f1612, roughness: 0.45 });
  const woodTrimMat = new THREE.MeshStandardMaterial({ color: 0x3a1e12, roughness: 0.3 });
  const chromeMat = new THREE.MeshStandardMaterial({ color: 0xcccccc, roughness: 0.2, metalness: 0.9 });

  // 5-Star Chrome Base
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.06, 5), chromeMat);
  base.position.set(x, 0.15, z);
  scene.add(base);

  const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.8, 8), chromeMat);
  stem.position.set(x, 0.55, z);
  scene.add(stem);

  // Leather Seat Cushion
  const seat = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.2, 0.9), leatherMat);
  seat.position.set(x, 0.95, z);
  scene.add(seat);

  // High Tufted Backrest
  const back = new THREE.Mesh(new THREE.BoxGeometry(0.9, 1.3, 0.18), leatherMat);
  back.position.set(x, 1.65, z + 0.38);
  back.rotation.x = -0.08;
  scene.add(back);

  // Mahogany Armrests
  const arm1 = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.3, 0.6), woodTrimMat);
  arm1.position.set(x - 0.5, 1.25, z);
  scene.add(arm1);

  const arm2 = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.3, 0.6), woodTrimMat);
  arm2.position.set(x + 0.5, 1.25, z);
  scene.add(arm2);
}

// ------------------------------------------------------------
// 3D Trader Avatar with Typing & Breathing Animations
// ------------------------------------------------------------
function buildTraderAvatar(scene, x, y, z, agentId, agentData) {
  const avatarGroup = new THREE.Group();
  avatarGroup.position.set(x, y, z);
  avatarGroup.userData = { agentId: agentId, agentData: agentData };

  // Suit Color based on role
  let suitColor = 0x1e3a8a; // Navy Suit default
  let auraColor = 0x38bdf8; // Cyan default
  
  if (agentId.includes("bull")) { suitColor = 0x064e3b; auraColor = 0x22c55e; }
  else if (agentId.includes("bear")) { suitColor = 0x7f1d1d; auraColor = 0xef4444; }
  else if (agentId.includes("cio") || agentId.includes("pm") || agentId.includes("facilitator")) { suitColor = 0x111827; auraColor = 0xfacc15; }
  else if (agentId.includes("tech") || agentId.includes("quant")) { suitColor = 0x312e81; auraColor = 0xa855f7; }
  else if (agentId.includes("risk") || agentId.includes("guardian")) { suitColor = 0x065f46; auraColor = 0x10b981; }

  const suitMat = new THREE.MeshStandardMaterial({ color: suitColor, roughness: 0.6 });
  const skinMat = new THREE.MeshStandardMaterial({ color: 0xfbcfe8, roughness: 0.5 });
  const hairMat = new THREE.MeshStandardMaterial({ color: 0x451a03, roughness: 0.7 });

  // 1. Torso / Suit Jacket
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.75, 0.95, 0.45), suitMat);
  torso.position.y = 0.45;
  torso.castShadow = true;
  avatarGroup.add(torso);

  // White Shirt Collar & Red Silk Tie
  const shirt = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.25, 0.05), new THREE.MeshBasicMaterial({ color: 0xffffff }));
  shirt.position.set(0, 0.78, -0.23);
  avatarGroup.add(shirt);

  const tie = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.45, 0.05), new THREE.MeshBasicMaterial({ color: 0xef4444 }));
  tie.position.set(0, 0.58, -0.24);
  avatarGroup.add(tie);

  // 2. Head with Hair & Eyes
  const headGroup = new THREE.Group();
  headGroup.position.set(0, 1.25, 0);

  const head = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.45), skinMat);
  headGroup.add(head);

  // Hair
  const hair = new THREE.Mesh(new THREE.BoxGeometry(0.54, 0.22, 0.48), hairMat);
  hair.position.y = 0.22;
  headGroup.add(hair);

  // Eyes
  const eyeMat = new THREE.MeshBasicMaterial({ color: 0x0f172a });
  const eyeL = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.08, 0.05), eyeMat);
  eyeL.position.set(-0.12, 0.02, -0.23);
  headGroup.add(eyeL);

  const eyeR = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.08, 0.05), eyeMat);
  eyeR.position.set(0.12, 0.02, -0.23);
  headGroup.add(eyeR);

  avatarGroup.add(headGroup);

  // 3. Animated Arms (Typing on Keyboard)
  const armL = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.55, 0.14), suitMat);
  armL.position.set(-0.44, 0.45, -0.15);
  armL.rotation.x = -Math.PI / 4;
  avatarGroup.add(armL);

  const armR = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.55, 0.14), suitMat);
  armR.position.set(0.44, 0.45, -0.15);
  armR.rotation.x = -Math.PI / 4;
  avatarGroup.add(armR);

  // 4. Glowing Status Floor Ring Beneath Chair
  const ringGeo = new THREE.RingGeometry(0.55, 0.72, 24);
  const ringMat = new THREE.MeshBasicMaterial({ color: auraColor, side: THREE.DoubleSide, transparent: true, opacity: 0.65 });
  const auraRing = new THREE.Mesh(ringGeo, ringMat);
  auraRing.rotation.x = -Math.PI / 2;
  auraRing.position.set(0, -y + 0.04, 0.25);
  avatarGroup.add(auraRing);
  Office3D.haloRings.push(auraRing);

  // 5. Floating 3D Name Tag Canvas Billboard
  const tagCanvas = document.createElement('canvas');
  tagCanvas.width = 160; tagCanvas.height = 40;
  const tCtx = tagCanvas.getContext('2d');
  tCtx.fillStyle = 'rgba(10, 14, 23, 0.85)';
  tCtx.fillRect(0, 0, 160, 40);
  tCtx.strokeStyle = '#' + auraColor.toString(16).padStart(6, '0');
  tCtx.lineWidth = 2;
  tCtx.strokeRect(0, 0, 160, 40);
  tCtx.font = 'bold 15px monospace';
  tCtx.fillStyle = '#ffffff';
  tCtx.textAlign = 'center';
  tCtx.fillText((agentData ? agentData.name : agentId.toUpperCase()), 80, 26);

  const tagTex = new THREE.CanvasTexture(tagCanvas);
  const tagMesh = new THREE.Mesh(
    new THREE.PlaneGeometry(1.6, 0.4),
    new THREE.MeshBasicMaterial({ map: tagTex, side: THREE.DoubleSide, transparent: true })
  );
  tagMesh.position.set(0, 1.85, 0);
  avatarGroup.add(tagMesh);
  Office3D.animatedObjects.push({ mesh: tagMesh, type: "billboard" });

  scene.add(avatarGroup);

  // Store for Raycasting & Idle Animation
  Office3D.animatedObjects.push({
    mesh: avatarGroup,
    type: "avatar",
    head: headGroup,
    armL: armL,
    armR: armR,
    baseY: y,
    agentId: agentId,
    agentData: agentData
  });
}

// ============================================================
// 10. CLASSIC WALL STREET BULL STATUE & HERITAGE WALL CLOCKS
// ============================================================
function buildHeritageAccents(scene) {
  const brassMat = new THREE.MeshStandardMaterial({ color: 0xd4af37, roughness: 0.25, metalness: 0.85 });
  const marbleMat = new THREE.MeshStandardMaterial({ color: 0x092615, roughness: 0.3 }); // Green Italian marble plinth

  // 1. Golden Wall Street Bull Statue in Executive Corner
  const plinth = new THREE.Mesh(new THREE.BoxGeometry(2.4, 2.0, 3.2), marbleMat);
  plinth.position.set(-33, 1.0, -22);
  plinth.castShadow = true;
  scene.add(plinth);

  // Stylized Golden Bull Figure
  const bullBody = new THREE.Mesh(new THREE.BoxGeometry(1.6, 1.1, 2.2), brassMat);
  bullBody.position.set(-33, 2.6, -22);
  bullBody.castShadow = true;
  scene.add(bullBody);

  const bullHead = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.8, 0.9), brassMat);
  bullHead.position.set(-33, 2.8, -20.6);
  scene.add(bullHead);

  // Horns
  const hornL = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.12, 0.6, 8), brassMat);
  hornL.rotation.z = Math.PI / 3;
  hornL.position.set(-33.5, 3.3, -20.6);
  scene.add(hornL);

  const hornR = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.12, 0.6, 8), brassMat);
  hornR.rotation.z = -Math.PI / 3;
  hornR.position.set(-32.5, 3.3, -20.6);
  scene.add(hornR);

  // 2. Four Heritage Wall Clocks (Mumbai NSE, London, NY, Tokyo)
  const clocks = [
    { city: "MUMBAI (NSE)", x: -28 },
    { city: "LONDON", x: -9 },
    { city: "NEW YORK", x: 9 },
    { city: "TOKYO", x: 28 }
  ];

  clocks.forEach(c => {
    const cFrame = new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.1, 0.15, 24), brassMat);
    cFrame.rotation.x = Math.PI / 2;
    cFrame.position.set(c.x, 10.2, -26.3);
    scene.add(cFrame);

    const cDial = new THREE.Mesh(
      new THREE.CircleGeometry(0.95, 24),
      new THREE.MeshBasicMaterial({ color: 0xffffff })
    );
    cDial.position.set(c.x, 10.2, -26.2);
    scene.add(cDial);

    // Hands
    const handH = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.5, 0.02), new THREE.MeshBasicMaterial({ color: 0x000000 }));
    handH.position.set(c.x, 10.35, -26.15);
    scene.add(handH);

    const handM = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.75, 0.02), new THREE.MeshBasicMaterial({ color: 0x000000 }));
    handM.position.set(c.x, 10.45, -26.15);
    handM.rotation.z = Math.PI / 4;
    scene.add(handM);
  });
}

// ============================================================
// 11. MAIN ANIMATION LOOP & INTERACTION
// ============================================================
function animateOffice3D() {
  Office3D.animId = requestAnimationFrame(animateOffice3D);
  Office3D.tick++;
  const tick = Office3D.tick;

  // 1. Update Dynamic Screen Canvases (Every 2 frames for 60fps smoothness)
  if (tick % 2 === 0) {
    updateDynamicScreenCanvases(tick);
  }

  // 2. Rotate Holographic Globe in War Room
  if (Office3D.holoGlobe) {
    Office3D.holoGlobe.rotation.y += 0.015;
    Office3D.holoGlobe.rotation.x += 0.008;
  }

  // 3. Pulse Halo Rings on Floor
  Office3D.haloRings.forEach(ring => {
    ring.material.opacity = 0.5 + Math.sin(tick * 0.08) * 0.25;
  });

  // 4. Animate Avatar Idles (Breathing & Typing)
  Office3D.animatedObjects.forEach(obj => {
    if (obj.type === "avatar") {
      // Subtle breathing
      obj.head.position.y = 1.25 + Math.sin(tick * 0.05 + obj.mesh.position.x) * 0.02;
      // Typing hands
      obj.armL.rotation.x = -Math.PI / 4 + Math.sin(tick * 0.2 + obj.mesh.position.x) * 0.1;
      obj.armR.rotation.x = -Math.PI / 4 + Math.cos(tick * 0.2 + obj.mesh.position.x) * 0.1;
    } else if (obj.type === "billboard" && Office3D.camera) {
      // Keep name badges facing camera
      obj.mesh.lookAt(Office3D.camera.position);
    }
  });

  // 5. Cinematic Orbit Mode
  if (Office3D.cinematicMode && Office3D.camera) {
    Office3D.cinematicAngle += 0.003;
    const dist = 52;
    Office3D.camera.position.x = Math.sin(Office3D.cinematicAngle) * dist;
    Office3D.camera.position.z = Math.cos(Office3D.cinematicAngle) * dist;
    Office3D.camera.lookAt(0, 2, 0);
  } else if (Office3D.controls) {
    Office3D.controls.update();
  }

  // Render Scene
  Office3D.renderer.render(Office3D.scene, Office3D.camera);
}

// ============================================================
// 12. RAYCASTING, CLICK & CAMERA PRESET CONTROLS
// ============================================================
function onOffice3DMouseMove(e) {
  const rect = Office3D.container.getBoundingClientRect();
  Office3D.mouse.x = ((e.clientX - rect.left) / Office3D.container.clientWidth) * 2 - 1;
  Office3D.mouse.y = -((e.clientY - rect.top) / Office3D.container.clientHeight) * 2 + 1;

  Office3D.raycaster.setFromCamera(Office3D.mouse, Office3D.camera);
  const avatars = Office3D.animatedObjects.filter(o => o.type === "avatar").map(o => o.mesh);
  const clickable = [...avatars, ...(Office3D.clickableObjects || [])];
  const intersects = Office3D.raycaster.intersectObjects(clickable, true);

  if (intersects.length > 0) {
    Office3D.container.style.cursor = 'pointer';
  } else {
    Office3D.container.style.cursor = 'default';
  }
}

function onOffice3DClick(e) {
  const rect = Office3D.container.getBoundingClientRect();
  Office3D.mouse.x = ((e.clientX - rect.left) / Office3D.container.clientWidth) * 2 - 1;
  Office3D.mouse.y = -((e.clientY - rect.top) / Office3D.container.clientHeight) * 2 + 1;

  Office3D.raycaster.setFromCamera(Office3D.mouse, Office3D.camera);
  const avatars = Office3D.animatedObjects.filter(o => o.type === "avatar").map(o => o.mesh);
  const clickable = [...avatars, ...(Office3D.clickableObjects || [])];
  const intersects = Office3D.raycaster.intersectObjects(clickable, true);

  if (intersects.length > 0) {
    // Traverse up to find root group or object with userData
    let obj = intersects[0].object;
    while (obj && !obj.userData.agentId && obj.parent) {
      obj = obj.parent;
    }
    if (obj && obj.userData && (obj.userData.agentData || obj.userData.agentId)) {
      const aData = obj.userData.agentData || { 
        id: obj.userData.agentId, 
        name: obj.userData.agentId.toUpperCase(),
        role: "Specialist AI Agent",
        dept: "Trading Desk",
        activeSymbol: "RELIANCE.NS"
      };
      if (typeof openAgentModal === 'function') {
        openAgentModal(aData);
      }
      // Fly camera smoothly to focus on trader workstation
      flyCameraTo(obj.position.x, obj.position.y + 3.5, obj.position.z + 6.5, obj.position.x, obj.position.y + 1, obj.position.z);
    }
  }
}

function flyCameraTo(cx, cy, cz, tx, ty, tz) {
  if (!Office3D.camera || !Office3D.controls) return;
  Office3D.cinematicMode = false;
  
  const startPos = Office3D.camera.position.clone();
  const endPos = new THREE.Vector3(cx, cy, cz);
  const startTarget = Office3D.controls.target.clone();
  const endTarget = new THREE.Vector3(tx, ty, tz);
  
  let progress = 0;
  function stepFly() {
    progress += 0.05;
    Office3D.camera.position.lerpVectors(startPos, endPos, progress);
    Office3D.controls.target.lerpVectors(startTarget, endTarget, progress);
    if (progress < 1.0) {
      requestAnimationFrame(stepFly);
    }
  }
  stepFly();
}

function set3DCameraPreset(presetName) {
  const p = Office3D.cameraPresets[presetName];
  if (!p) return;
  flyCameraTo(p.pos[0], p.pos[1], p.pos[2], p.target[0], p.target[1], p.target[2]);
}

function toggleCinematicTour() {
  Office3D.cinematicMode = !Office3D.cinematicMode;
  const btn = document.getElementById('btnCinematicTour');
  if (btn) {
    btn.innerHTML = Office3D.cinematicMode ? '⏸️ PAUSE TOUR' : '🎬 CINEMATIC TOUR';
    btn.style.color = Office3D.cinematicMode ? '#facc15' : '#38bdf8';
  }
}

function onOffice3DResize() {
  if (!Office3D.container || !Office3D.camera || !Office3D.renderer) return;
  const w = Office3D.container.clientWidth;
  const h = Office3D.container.clientHeight;
  Office3D.camera.aspect = w / h;
  Office3D.camera.updateProjectionMatrix();
  Office3D.renderer.setSize(w, h);
}

// ============================================================
// 13. SEAMLESS 3D CLASSIC / 2D RETRO SWITCHER
// ============================================================
function switchOfficeViewMode(mode) {
  const c3D = document.getElementById('office3DContainer');
  const c2D = document.getElementById('pixelOfficeCanvas');
  const bar3D = document.getElementById('office3DControlsBar');
  const btnSwitch = document.getElementById('btnViewModeSwitch');

  if (mode === '3d') {
    if (c3D) c3D.style.display = 'block';
    if (c2D) c2D.style.display = 'none';
    if (bar3D) bar3D.style.display = 'flex';
    if (btnSwitch) btnSwitch.innerHTML = '🏛️ VIEW: 3D CLASSIC';
    Office3D.is3DActive = true;
    onOffice3DResize();
  } else {
    if (c3D) c3D.style.display = 'none';
    if (c2D) c2D.style.display = 'block';
    if (bar3D) bar3D.style.display = 'none';
    if (btnSwitch) btnSwitch.innerHTML = '👾 VIEW: 2D RETRO';
    Office3D.is3DActive = false;
    if (typeof resizeCanvas === 'function') resizeCanvas();
  }
}
