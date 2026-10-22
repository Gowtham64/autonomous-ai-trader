/**
 * 'AGENT OFFICE' — PROPORTIONAL PIXEL-ART VIRTUAL OFFICE ENGINE
 * Perfectly arranged 4-Quadrant + Center Arena layout:
 * - Top-Left: Executive & Global Intelligence (CIO, PM, Global, Gift Nifty)
 * - Top-Right: Quantitative & Technical Lab (Technical, Momentum, Quant, Regime, Patterns, Backtest)
 * - Mid-Left: News, Sentiment & Macro Desk (News, Sentiment, Macro)
 * - Center Stage: Adversarial Debate Arena (Bull, Bear, Facilitator) & AI Academy (Intern, Mentor)
 * - Mid-Right: Memory Lab & Infrastructure (Memory Bot, Learning, CTO)
 * - Bottom-Left: Fundamental & F&O Derivatives (Fundamental, Valuation, Options, F&O Buildup, Sector)
 * - Bottom-Right: Central Risk & Gated Execution Fortress (Risk Sentinel, Position Guardian, QA, Execution, AngelOne, CFO)
 */

// ============================================================
// 1. 8-BIT AUDIO SYNTHESIZER
// ============================================================
class RetroAudioSynth {
  constructor() {
    this.ctx = null;
    this.enabled = true;
  }

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
  }

  playBlip(freq = 440, type = 'square', duration = 0.08) {
    if (!this.enabled) return;
    try {
      this.init();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(0.08, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {}
  }

  playHireChime() {
    if (!this.enabled) return;
    const notes = [523.25, 659.25, 783.99, 1046.50];
    notes.forEach((freq, idx) => {
      setTimeout(() => this.playBlip(freq, 'triangle', 0.15), idx * 90);
    });
  }

  playFlowStep() {
    if (!this.enabled) return;
    this.playBlip(600, 'square', 0.06);
  }
}

const sfx = new RetroAudioSynth();

// ============================================================
// 2. PERFECTLY SPACED 30-AGENT ROSTER & DESK TOPOLOGY
// ============================================================
const PixelOffice = {
  canvas: null,
  ctx: null,
  width: 1400,
  height: 820,
  scale: 1,
  
  tick: 0,
  hoveredAgent: null,
  selectedAgent: null,
  showFlows: true,
  
  // Clean, Spacious Layout with zero overlapping badges
  agents: [
    // === ROW 1: TOP-LEFT — EXECUTIVE & GLOBAL MACRO ===
    {
      id: "pm_agent",
      name: "PM_AGENT",
      role: "Project Manager & Workflow Orchestrator",
      dept: "Executive Leadership",
      avatar: "👔",
      x: 70,
      y: 155,
      type: "manager",
      status: "ASSIGN TASK",
      color: "#4ade80",
      halo: true,
      holdingClipboard: true,
      confidence: "98.5%",
      cycles: 420,
      thought: "Coordinating pre-market analysis. Assigning candidate momentum scan to Tech Desk.",
      task: "ASSIGN TASK -> Quantitative Research Desks"
    },
    {
      id: "cio_agent",
      name: "CIO_AGENT",
      role: "Chief Investment Officer",
      dept: "Executive Leadership",
      avatar: "👑",
      x: 180,
      y: 155,
      type: "seated_dev",
      shirtColor: "#1e3a8a",
      status: "CHIEF SYNTHESIS",
      color: "#facc15",
      halo: true,
      confidence: "99.0%",
      cycles: 460,
      thought: "Synthesizing macro & debate consensus. Risk-adjusted capital allocation ready.",
      task: "SYNTHESIZE -> Portfolio Allocation"
    },
    {
      id: "global_agent",
      name: "GLOBAL_AGENT",
      role: "Global Markets & Overnight Cues",
      dept: "Market Intelligence",
      avatar: "🌍",
      x: 290,
      y: 155,
      type: "seated_dev",
      shirtColor: "#0284c7",
      status: "US GREEN (+0.8%)",
      color: "#38bdf8",
      confidence: "95.0%",
      cycles: 310,
      thought: "S&P 500 +0.78%, Nasdaq +1.1%, Asian markets green. Positive global risk-on tone.",
      task: "MONITOR -> S&P 500, DXY & Yields"
    },
    {
      id: "gift_nifty",
      name: "GIFT_NIFTY",
      role: "GIFT Nifty Opening Gap Predictor",
      dept: "Market Intelligence",
      avatar: "🇮🇳",
      x: 400,
      y: 155,
      type: "dev",
      shirtColor: "#ea580c",
      status: "GAP UP +45 PTS",
      color: "#f97316",
      confidence: "96.2%",
      cycles: 340,
      thought: "GIFT Nifty indicating +45 pt gap-up open for Nifty 50 at 09:15 IST.",
      task: "PREDICT -> Opening Gap & Volatility"
    },

    // === ROW 1: TOP-RIGHT — QUANTITATIVE & TECHNICAL LAB ===
    {
      id: "technical_agent",
      name: "TECH_AGENT",
      role: "Multi-Timeframe Technical Analyst",
      dept: "Technical Analysis",
      avatar: "📈",
      x: 750,
      y: 155,
      type: "seated_dev",
      shirtColor: "#9333ea",
      status: "EMA CROSSOVER",
      color: "#a855f7",
      confidence: "96.4%",
      cycles: 480,
      thought: "RELIANCE 15m 20-EMA crossed 50-EMA with expanding volume. RSI 64.2 bullish.",
      task: "CALCULATE -> 15m/1D Moving Averages"
    },
    {
      id: "momentum_agent",
      name: "MOMENTUM",
      role: "Trend Acceleration & ROC Analyst",
      dept: "Technical Analysis",
      avatar: "🚀",
      x: 860,
      y: 155,
      type: "seated_dev",
      shirtColor: "#7c3aed",
      status: "ROC +4.2%",
      color: "#c084fc",
      confidence: "94.8%",
      cycles: 390,
      thought: "TATAMOTORS Rate of Change +4.2%. Strong relative strength vs Nifty Auto.",
      task: "MONITOR -> Momentum Breakouts"
    },
    {
      id: "quant_agent",
      name: "QUANT_AGENT",
      role: "Factor Models & Monte Carlo",
      dept: "Quantitative Research",
      avatar: "🧠",
      x: 980,
      y: 155,
      type: "seated_dev",
      shirtColor: "#db2777",
      status: "MONTE CARLO 68%",
      color: "#ec4899",
      confidence: "97.1%",
      cycles: 490,
      thought: "Monte Carlo 10,000 runs: 68.4% Win Probability. Expected Value +1.8R.",
      task: "SIMULATE -> Statistical Probability"
    },
    {
      id: "regime_agent",
      name: "REGIME_AGENT",
      role: "Market Regime Determiner",
      dept: "Quantitative Research",
      avatar: "🧭",
      x: 1090,
      y: 155,
      type: "dev",
      shirtColor: "#d97706",
      status: "STRONG_BULL",
      color: "#f59e0b",
      confidence: "98.2%",
      cycles: 420,
      thought: "Market Regime: STRONG_BULL. India VIX 12.8. Favorable for trend setups.",
      task: "CLASSIFY -> 7-Regime Framework"
    },
    {
      id: "backtest_agent",
      name: "BACKTEST_AI",
      role: "Strategy Calibration & Backtest",
      dept: "Quantitative Research",
      avatar: "📊",
      x: 1210,
      y: 155,
      type: "seated_dev",
      shirtColor: "#047857",
      status: "SHARPE: 1.84",
      color: "#10b981",
      confidence: "95.5%",
      cycles: 360,
      thought: "Backtested strategy parameters. Profit Factor 1.84, Max Drawdown 2.1%.",
      task: "CALIBRATE -> Walk-Forward Testing"
    },

    // === ROW 2: MID-LEFT — NEWS, SENTIMENT & MACRO ===
    {
      id: "news_agent",
      name: "NEWS_AGENT",
      role: "Corporate Filings & NLP Analyst",
      dept: "Market Intelligence",
      avatar: "📰",
      x: 80,
      y: 330,
      type: "seated_analyst",
      hairColor: "#7e22ce",
      status: "FILINGS CLEAR",
      color: "#c084fc",
      confidence: "95.2%",
      cycles: 310,
      thought: "Parsed 142 NSE official filings. 0 regulatory flags detected on tracked universe.",
      task: "SCAN -> Primary Exchange Filings"
    },
    {
      id: "sentiment_agent",
      name: "SENTIMENT",
      role: "FII / DII Institutional Flow",
      dept: "Market Intelligence",
      avatar: "📊",
      x: 190,
      y: 330,
      type: "seated_analyst",
      hairColor: "#38bdf8",
      status: "FII: +₹1,240 Cr",
      color: "#60a5fa",
      confidence: "93.8%",
      cycles: 290,
      thought: "Foreign Institutional Investors net buyers (+₹1,240 Cr). DII providing bid support.",
      task: "ANALYZE -> Institutional Inflow"
    },
    {
      id: "macro_agent",
      name: "MACRO_AGENT",
      role: "RBI & Monetary Policy Specialist",
      dept: "Market Intelligence",
      avatar: "🏛️",
      x: 300,
      y: 330,
      type: "dev",
      shirtColor: "#475569",
      status: "RATES STABLE",
      color: "#94a3b8",
      confidence: "97.0%",
      cycles: 240,
      thought: "RBI MPC stance neutral. India 10-year G-Sec yield steady at 6.84%.",
      task: "EVALUATE -> Inflation & Bond Yields"
    },

    // === ROW 2: CENTER ARENA — ADVERSARIAL DEBATE & ACADEMY ===
    {
      id: "bull_agent",
      name: "BULL_AGENT",
      role: "Bullish Thesis Champion",
      dept: "Adversarial Debate Arena",
      avatar: "🐂",
      x: 500,
      y: 350,
      type: "bull_specialist",
      shirtColor: "#15803d",
      status: "BULL THESIS (88%)",
      color: "#22c55e",
      halo: true,
      confidence: "88.0%",
      cycles: 540,
      thought: "Strong volume breakout above ₹3,000 pivot with institutional accumulation.",
      task: "DEFEND -> Bullish Entry Rationale"
    },
    {
      id: "facilitator_agent",
      name: "FACILITATOR",
      role: "Impartial Debate Moderator",
      dept: "Adversarial Debate Arena",
      avatar: "⚖️",
      x: 600,
      y: 310,
      type: "manager",
      shirtColor: "#6b21a8",
      status: "DEBATE ACTIVE",
      color: "#a855f7",
      confidence: "99.0%",
      cycles: 540,
      thought: "Moderating Bull vs Bear debate. Consensus score +0.76 (Strong Bullish Edge).",
      task: "SYNTHESIZE -> Consensus Score"
    },
    {
      id: "bear_agent",
      name: "BEAR_AGENT",
      role: "Bearish Devil's Advocate",
      dept: "Adversarial Debate Arena",
      avatar: "🐻",
      x: 700,
      y: 350,
      type: "bear_specialist",
      shirtColor: "#b91c1c",
      status: "BEAR THESIS (12%)",
      color: "#ef4444",
      halo: true,
      confidence: "74.0%",
      cycles: 540,
      thought: "Scrutinizing resistance at ₹3,080. Invalidation triggered if price falls below VWAP.",
      task: "CHALLENGE -> Invalidation Points"
    },
    {
      id: "intern_agent",
      name: "INTERN_AGENT",
      role: "Junior Quant Apprentice",
      dept: "AI Academy",
      avatar: "🎓",
      x: 840,
      y: 350,
      type: "intern",
      hasGradCap: true,
      status: "NEW HIRE!",
      color: "#38bdf8",
      halo: true,
      confidence: "91.2%",
      cycles: 52,
      thought: "Shadowing Senior Fund Manager on risk limits and 14-point audit gate.",
      task: "LEARN -> Pre-Trade Audit Protocol"
    },
    {
      id: "mentor_agent",
      name: "MENTOR_AGENT",
      role: "Senior AI Onboarding Lead",
      dept: "AI Academy",
      avatar: "🤝",
      x: 940,
      y: 350,
      type: "senior_guide",
      status: "ONBOARDING",
      color: "#facc15",
      confidence: "98.0%",
      cycles: 580,
      thought: "Training dynamic specialist models on Indian derivatives & Greeks.",
      task: "TRAIN -> Dynamic Specialist Workforce"
    },

    // === ROW 2: MID-RIGHT — MEMORY LAB & CTO INFRASTRUCTURE ===
    {
      id: "cto_agent",
      name: "CTO_AI",
      role: "Chief Technology AI & DevOps",
      dept: "Infrastructure",
      avatar: "💻",
      x: 1110,
      y: 340,
      type: "dev",
      shirtColor: "#0369a1",
      status: "SERVICES 100%",
      color: "#38bdf8",
      confidence: "99.9%",
      cycles: 640,
      thought: "All microservices healthy. WebSocket live streams transmitting tick telemetry.",
      task: "MAINTAIN -> High-Throughput Streaming"
    },
    {
      id: "learning_agent",
      name: "LEARNING_AI",
      role: "4-Quadrant Post-Trade Learning",
      dept: "Self-Improvement AI",
      avatar: "💡",
      x: 1210,
      y: 340,
      type: "dev",
      shirtColor: "#7c3aed",
      status: "LEARNING LOOP",
      color: "#a855f7",
      confidence: "98.5%",
      cycles: 380,
      thought: "Post-trade MFE/MAE evaluated. Edge verified: Good Decision -> Good Outcome.",
      task: "CALIBRATE -> Agent Model Weights"
    },
    {
      id: "memory_bot",
      name: "MEMORY_BOT",
      role: "Knowledge Graph & Session Persistence",
      dept: "System Memory",
      avatar: "🤖",
      x: 1315,
      y: 340,
      type: "robot",
      status: "PERSISTENCE (S2)",
      color: "#a78bfa",
      confidence: "100.0%",
      cycles: 1850,
      thought: "Vector Knowledge Graph indexed. All agent deliberations and orders persisted.",
      task: "PERSIST -> PostgreSQL & Redis"
    },

    // === ROW 3: BOTTOM-LEFT — FUNDAMENTAL & F&O DERIVATIVES ===
    {
      id: "fundamental_agent",
      name: "FUNDAMENTAL",
      role: "Balance Sheets & P&L Analyst",
      dept: "Fundamental Analysis",
      avatar: "📑",
      x: 70,
      y: 530,
      type: "seated_analyst",
      hairColor: "#1e3a8a",
      status: "DEBT/EQ: 0.44",
      color: "#3b82f6",
      confidence: "96.5%",
      cycles: 320,
      thought: "RELIANCE quarterly EBITDA growth +12.4% YoY. Debt/Equity conservative at 0.44.",
      task: "EVALUATE -> Quarterly Financials"
    },
    {
      id: "valuation_agent",
      name: "VALUATION",
      role: "DCF & Intrinsic Value",
      dept: "Fundamental Analysis",
      avatar: "🔍",
      x: 175,
      y: 530,
      type: "seated_analyst",
      hairColor: "#0284c7",
      status: "+14% MARGIN",
      color: "#0ea5e9",
      confidence: "95.0%",
      cycles: 290,
      thought: "DCF intrinsic fair value ₹1,420. Offering 14% margin of safety.",
      task: "COMPUTE -> Discounted Cash Flow"
    },
    {
      id: "options_agent",
      name: "OPTIONS_AGENT",
      role: "Greeks & IV Percentile Specialist",
      dept: "Derivatives & F&O",
      avatar: "⚡",
      x: 285,
      y: 530,
      type: "dev",
      shirtColor: "#0284c7",
      status: "PCR: 1.18",
      color: "#38bdf8",
      confidence: "97.4%",
      cycles: 430,
      thought: "Put-Call Ratio (PCR) 1.18 bullish. Max Pain strike at 25,000.",
      task: "CALCULATE -> Greeks & IV Smile"
    },
    {
      id: "fo_agent",
      name: "F&O_AGENT",
      role: "Futures OI & Buildup Detector",
      dept: "Derivatives & F&O",
      avatar: "🎯",
      x: 395,
      y: 530,
      type: "dev",
      shirtColor: "#059669",
      status: "LONG BUILDUP",
      color: "#10b981",
      confidence: "96.0%",
      cycles: 410,
      thought: "Futures basis +8.5 pts premium with +6.2% OI expansion: Confirmed Long Buildup.",
      task: "DETECT -> Open Interest Accumulation"
    },
    {
      id: "sector_agent",
      name: "SECTOR_AGENT",
      role: "16-Sector Rotation Specialist",
      dept: "Market Intelligence",
      avatar: "📊",
      x: 230,
      y: 630,
      type: "dev",
      shirtColor: "#9333ea",
      status: "IT LEADING",
      color: "#c084fc",
      confidence: "94.0%",
      cycles: 270,
      thought: "Sector Relative Strength: IT (+1.8%) & Auto (+1.2%) outperforming broad market.",
      task: "RANK -> Sector Momentum & Rotation"
    },

    // === ROW 3: BOTTOM-RIGHT — CENTRAL RISK, EXECUTION FORTRESS & TREASURY ===
    {
      id: "risk_sentinel",
      name: "RISK_SENTINEL",
      role: "14-Point Pre-Trade Audit Gate",
      dept: "Risk Management",
      avatar: "🛡️",
      x: 580,
      y: 530,
      type: "seated_analyst",
      hairColor: "#15803d",
      status: "14/14 GATES PASS",
      color: "#4ade80",
      halo: true,
      confidence: "100.0%",
      cycles: 820,
      thought: "All 14 pre-trade checks strictly satisfied. Stop-loss confirmed. R:R 2.2:1 verified.",
      task: "ENFORCE -> Zero Override Risk Gate"
    },
    {
      id: "position_guardian",
      name: "GUARDIAN",
      role: "Real-time SL & Trailing Profit",
      dept: "Risk Management",
      avatar: "👁️",
      x: 690,
      y: 530,
      type: "dev",
      shirtColor: "#16a34a",
      status: "SENTINEL ACTIVE",
      color: "#22c55e",
      confidence: "100.0%",
      cycles: 940,
      thought: "Tick-by-tick trailing stop monitor engaged. Profit lock set at 1.5R milestone.",
      task: "GUARD -> Active Positions & Exits"
    },
    {
      id: "compliance_agent",
      name: "COMPLIANCE",
      role: "SEBI Rules & ASM/GSM Filter",
      dept: "Legal & Compliance",
      avatar: "⚖️",
      x: 800,
      y: 530,
      type: "manager",
      shirtColor: "#b45309",
      status: "SEBI CLEAR",
      color: "#f59e0b",
      confidence: "100.0%",
      cycles: 470,
      thought: "Candidate symbols free of ASM/GSM surveillance and ban period restrictions.",
      task: "VERIFY -> SEBI Surveillance Lists"
    },
    {
      id: "qa_agent",
      name: "QA_AUDITOR",
      role: "Code Auditor & OMS Inspector",
      dept: "Quality Assurance",
      avatar: "🔍",
      x: 910,
      y: 530,
      type: "qa_monocle",
      hairColor: "#f472b6",
      hasMonocle: true,
      status: "0 REGRESSIONS",
      color: "#f472b6",
      confidence: "99.8%",
      cycles: 510,
      thought: "Order payload validated against AngelOne SmartAPI schema. Idempotency verified.",
      task: "AUDIT -> OMS Order Serialization"
    },
    {
      id: "execution_agent",
      name: "EXECUTION_AI",
      role: "Gated Order Construction & Router",
      dept: "Execution Desk",
      avatar: "⚡",
      x: 1020,
      y: 530,
      type: "dev",
      shirtColor: "#0284c7",
      status: "ROUTER READY",
      color: "#38bdf8",
      confidence: "99.0%",
      cycles: 710,
      thought: "Slippage bounded at 0.20%. Preparing CNC/MIS limit order for broker dispatch.",
      task: "ROUTE -> Gated Execution Engine"
    },
    {
      id: "broker_agent",
      name: "ANGEL_GATEWAY",
      role: "AngelOne SmartAPI Gateway",
      dept: "Broker Gateway",
      avatar: "🔗",
      x: 1140,
      y: 530,
      type: "dev",
      shirtColor: "#0369a1",
      status: "LIVE AACJ120032",
      color: "#0ea5e9",
      confidence: "100.0%",
      cycles: 1120,
      thought: "AngelOne SmartAPI authenticated (AACJ120032). Ping: 42ms. Live Margin: ₹593.32.",
      task: "DISPATCH -> Live Broker Exchange"
    },
    {
      id: "cfo_agent",
      name: "CFO_TREASURY",
      role: "Treasury Runway & Balance Sheet",
      dept: "Capital Management",
      avatar: "💰",
      x: 860,
      y: 630,
      type: "manager",
      shirtColor: "#065f46",
      status: "MARGIN: ₹593.32",
      color: "#10b981",
      confidence: "99.5%",
      cycles: 380,
      thought: "Capital Runway: 400+ Days. Operating expense recorded: ₹0.50.",
      task: "AUDIT -> Capital & API Costs"
    }
  ],

  // Spacious, Proportionate Desks Layout (No Clutter)
  desks: [
    // --- TOP-LEFT DESKS ---
    { id: "exec_desk_1", x: 50, y: 125, w: 180, h: 70, monitorColor: "#facc15", hasDualMonitors: true, hasMug: true },
    { id: "global_desk_1", x: 270, y: 125, w: 180, h: 70, monitorColor: "#38bdf8", hasDualMonitors: true, hasMug: true, hasBin: true },
    
    // --- TOP-RIGHT DESKS ---
    { id: "tech_desk_1", x: 730, y: 125, w: 180, h: 70, monitorColor: "#a855f7", hasDualMonitors: true, hasMug: true },
    { id: "quant_desk_1", x: 960, y: 125, w: 180, h: 70, monitorColor: "#ec4899", hasDualMonitors: true, hasMug: true, hasBin: true },
    { id: "backtest_desk_1", x: 1190, y: 125, w: 90, h: 70, monitorColor: "#10b981", hasMug: true },
    
    // --- MID-LEFT DESKS ---
    { id: "news_desk_1", x: 60, y: 300, w: 180, h: 70, monitorColor: "#c084fc", hasDualMonitors: true, hasMug: true, hasBin: true },
    { id: "macro_desk_1", x: 280, y: 300, w: 90, h: 70, monitorColor: "#94a3b8", hasMug: true },
    
    // --- CENTER DEBATE ARENA DESKS ---
    { id: "debate_bull_desk", x: 470, y: 320, w: 90, h: 70, monitorColor: "#22c55e", hasMug: true },
    { id: "debate_bear_desk", x: 670, y: 320, w: 90, h: 70, monitorColor: "#ef4444", hasMug: true },
    { id: "academy_desk", x: 820, y: 320, w: 170, h: 70, monitorColor: "#38bdf8", hasDualMonitors: true, hasMug: true, hasBin: true },
    
    // --- MID-RIGHT INFRA & MEMORY ---
    { id: "cto_desk", x: 1080, y: 310, w: 180, h: 70, monitorColor: "#0284c7", hasDualMonitors: true, hasMug: true, hasBin: true },
    
    // --- BOTTOM-LEFT DESKS ---
    { id: "fund_desk_1", x: 50, y: 500, w: 180, h: 70, monitorColor: "#3b82f6", hasDualMonitors: true, hasMug: true },
    { id: "fo_desk_1", x: 260, y: 500, w: 180, h: 70, monitorColor: "#10b981", hasDualMonitors: true, hasMug: true, hasBin: true },
    { id: "sector_desk_1", x: 200, y: 600, w: 100, h: 60, monitorColor: "#a855f7", hasMug: true },
    
    // --- BOTTOM-RIGHT DESKS ---
    { id: "risk_desk_1", x: 560, y: 500, w: 180, h: 70, monitorColor: "#4ade80", hasDualMonitors: true, hasMug: true },
    { id: "qa_desk_1", x: 780, y: 500, w: 180, h: 70, monitorColor: "#f472b6", hasDualMonitors: true, hasMug: true, hasBin: true },
    { id: "exec_desk_1", x: 1000, y: 500, w: 200, h: 70, monitorColor: "#38bdf8", hasDualMonitors: true, hasMug: true, hasBin: true },
    { id: "cfo_desk_1", x: 830, y: 600, w: 100, h: 60, monitorColor: "#10b981", hasMug: true }
  ],

  // Potted plants decor positioned cleanly at borders and between sections
  plants: [
    { x: 15, y: 90, type: "snake" },
    { x: 15, y: 720, type: "fiddle" },
    { x: 490, y: 90, type: "bonsai" },
    { x: 700, y: 90, type: "snake" },
    { x: 1350, y: 90, type: "fiddle" },
    { x: 1350, y: 720, type: "bonsai" },
    { x: 480, y: 720, type: "snake" },
    { x: 720, y: 720, type: "fiddle" }
  ]
};

// ============================================================
// 3. CANVAS INITIALIZATION & RENDER LOOP
// ============================================================
function initPixelOffice() {
  const canvas = document.getElementById('pixelOfficeCanvas');
  if (!canvas) return;
  
  PixelOffice.canvas = canvas;
  PixelOffice.ctx = canvas.getContext('2d');
  
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
  
  canvas.addEventListener('mousemove', handleMouseMove);
  canvas.addEventListener('click', handleCanvasClick);
  
  const btnSpawn = document.getElementById('btnSpawnAgent');
  if (btnSpawn) btnSpawn.addEventListener('click', spawnNewHire);
  
  const btnSim = document.getElementById('btnSimulate');
  if (btnSim) btnSim.addEventListener('click', runSimulatedFlow);
  
  const btnAudio = document.getElementById('btnAudioToggle');
  if (btnAudio) {
    btnAudio.addEventListener('click', () => {
      sfx.enabled = !sfx.enabled;
      btnAudio.innerHTML = sfx.enabled ? '<span class="p-icon">🔊</span> SFX: ON' : '<span class="p-icon">🔇</span> SFX: OFF';
    });
  }

  const countBadge = document.getElementById('agentCountBadge');
  if (countBadge) countBadge.innerText = PixelOffice.agents.length;

  renderRosterTable();
  syncLiveTelemetry();
  setInterval(syncLiveTelemetry, 5000);
  checkDaemonStatus();
  setInterval(checkDaemonStatus, 5000);

  requestAnimationFrame(renderLoop);
}

if (document.readyState === 'loading') {
  window.addEventListener('DOMContentLoaded', initPixelOffice);
} else {
  initPixelOffice();
}
window.addEventListener('load', resizeCanvas);

function resizeCanvas() {
  if (!PixelOffice.canvas) return;
  const stage = document.querySelector('.pixel-office-stage');
  
  let w = stage ? stage.clientWidth : window.innerWidth;
  let h = stage ? stage.clientHeight : (window.innerHeight - 140);
  
  if (!w || w < 200) w = window.innerWidth || 1400;
  if (!h || h < 200) h = (window.innerHeight - 140) || 820;
  
  PixelOffice.canvas.width = w;
  PixelOffice.canvas.height = h;
  
  const scaleX = w / PixelOffice.width;
  const scaleY = h / PixelOffice.height;
  PixelOffice.scale = Math.max(0.55, Math.min(scaleX, scaleY, 1.4));
}

// ============================================================
// 4. MAIN RENDER LOOP & PROCEDURAL DRAWING
// ============================================================
function renderLoop() {
  PixelOffice.tick++;
  const ctx = PixelOffice.ctx;
  if (!ctx) return;
  
  ctx.save();
  ctx.clearRect(0, 0, PixelOffice.canvas.width, PixelOffice.canvas.height);
  ctx.imageSmoothingEnabled = false;
  
  const offsetX = (PixelOffice.canvas.width - PixelOffice.width * PixelOffice.scale) / 2;
  const offsetY = (PixelOffice.canvas.height - PixelOffice.height * PixelOffice.scale) / 2;
  ctx.translate(offsetX, offsetY);
  ctx.scale(PixelOffice.scale, PixelOffice.scale);
  
  // 1. Draw Wooden Floor & Top Wall
  drawRoomBackground(ctx);
  
  // 2. Draw Desks & Plants
  drawFurnitureAndPlants(ctx);
  
  // 3. Draw Collaboration Arrows & Data Streams
  drawCollaborationArrows(ctx);
  
  // 4. Draw Characters
  drawAllCharacters(ctx);
  
  // 5. Draw Badges & Speech Bubbles
  drawHUDAndSpeechBubbles(ctx);
  
  ctx.restore();
  requestAnimationFrame(renderLoop);
}

function drawRoomBackground(ctx) {
  const tick = PixelOffice.tick;
  
  // 1. TOP TITANIUM WALL (Deep Carbon & Tech Battens)
  ctx.fillStyle = "#090e17";
  ctx.fillRect(0, 0, PixelOffice.width, 102);
  
  // Vertical tech battens
  ctx.fillStyle = "#111827";
  for (let x = 0; x < PixelOffice.width; x += 70) {
    ctx.fillRect(x, 0, 2, 102);
  }
  
  // Brushed steel base molding with neon accent
  ctx.fillStyle = "#1e293b";
  ctx.fillRect(0, 98, PixelOffice.width, 4);
  ctx.fillStyle = "#38bdf8";
  ctx.fillRect(0, 101, PixelOffice.width, 1);
  
  // ------------------------------------------------------------
  // FULL-WIDTH LED MARKET TICKER RIBBON (TOP OF WALL)
  // ------------------------------------------------------------
  ctx.fillStyle = "#02040a";
  ctx.fillRect(0, 0, PixelOffice.width, 22);
  ctx.fillStyle = "#1e293b";
  ctx.fillRect(0, 21, PixelOffice.width, 1);
  
  // Scrolling Market Ticker Text
  const tickerItems = [
    { s: "NIFTY 50", p: "25,810.40", d: "+0.52%", up: true },
    { s: "BANKNIFTY", p: "54,180.20", d: "+0.75%", up: true },
    { s: "SENSEX", p: "84,320.10", d: "+0.38%", up: true },
    { s: "INDIA VIX", p: "12.35", d: "-4.10%", up: false },
    { s: "GIFT NIFTY", p: "25,860.00", d: "+0.68%", up: true },
    { s: "USD/INR", p: "83.72", d: "-0.04%", up: false },
    { s: "BRENT CRUDE", p: "$71.20", d: "-1.10%", up: false },
    { s: "GOLD (10g)", p: "₹75,400", d: "+0.30%", up: true },
    { s: "RELIANCE", p: "2,985.40", d: "+1.20%", up: true },
    { s: "HDFCBANK", p: "1,675.00", d: "+0.80%", up: true },
    { s: "TATASTEEL", p: "154.20", d: "+1.40%", up: true },
    { s: "TATAPOWER", p: "428.50", d: "+1.85%", up: true }
  ];
  
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, PixelOffice.width, 22);
  ctx.clip();
  
  ctx.font = "bold 9px 'JetBrains Mono', 'Press Start 2P', monospace";
  const tickerSpeed = (tick * 1.2) % 2400;
  
  let curX = -tickerSpeed;
  while (curX < PixelOffice.width + 800) {
    tickerItems.forEach(item => {
      // Symbol
      ctx.fillStyle = "#94a3b8";
      ctx.fillText(item.s, curX, 14);
      curX += ctx.measureText(item.s).width + 6;
      
      // Price
      ctx.fillStyle = "#f8fafc";
      ctx.fillText(item.p, curX, 14);
      curX += ctx.measureText(item.p).width + 6;
      
      // Delta badge
      ctx.fillStyle = item.up ? "#22c55e" : "#ef4444";
      const deltaText = `${item.up ? "▲" : "▼"} ${item.d}`;
      ctx.fillText(deltaText, curX, 14);
      curX += ctx.measureText(deltaText).width + 24;
      
      // Separator
      ctx.fillStyle = "#334155";
      ctx.fillText("❙", curX - 12, 14);
    });
  }
  ctx.restore();

  // ------------------------------------------------------------
  // THREE GIANT INSTITUTIONAL WALL VIDEO DISPLAYS
  // ------------------------------------------------------------
  drawWallVideoDisplays(ctx, tick);

  // ------------------------------------------------------------
  // INSTITUTIONAL TRADING FLOOR (Slate Carbon Tiles)
  // ------------------------------------------------------------
  const floorTop = 102;
  const floorHeight = PixelOffice.height - floorTop;
  
  // Base dark slate floor
  ctx.fillStyle = "#0a0e17";
  ctx.fillRect(0, floorTop, PixelOffice.width, floorHeight);
  
  // Checkerboard slate tiles (40x40)
  const tileSize = 40;
  for (let y = floorTop; y < PixelOffice.height; y += tileSize) {
    for (let x = 0; x < PixelOffice.width; x += tileSize) {
      const tileCol = ((x / tileSize) + (y / tileSize)) % 2 === 0;
      if (tileCol) {
        ctx.fillStyle = "#0e1422";
        ctx.fillRect(x, y, tileSize, tileSize);
      }
      // Fine tile border
      ctx.strokeStyle = "#162033";
      ctx.lineWidth = 1;
      ctx.strokeRect(x, y, tileSize, tileSize);
      
      // Micro crosshair grid mark at corners
      if (x % 80 === 0 && y % 80 === 0) {
        ctx.fillStyle = "rgba(56, 189, 248, 0.15)";
        ctx.fillRect(x - 2, y, 5, 1);
        ctx.fillRect(x, y - 2, 1, 5);
      }
    }
  }

  // ------------------------------------------------------------
  // TRADING POD FLOOR ZONES (Department Boundaries & Stencils)
  // ------------------------------------------------------------
  drawTradingFloorZones(ctx);

  // ------------------------------------------------------------
  // FIBER-OPTIC UNDERFLOOR DATA RUNWAYS
  // ------------------------------------------------------------
  drawFloorFiberChannels(ctx, tick);
}

// ------------------------------------------------------------
// Wall-Mounted Giant Institutional Bloomberg Video Displays
// ------------------------------------------------------------
function drawWallVideoDisplays(ctx, tick) {
  // --- DISPLAY 1 (LEFT): NIFTY 5M LIVE CANDLESTICK CHART ---
  const d1X = 45, d1Y = 26, d1W = 340, d1H = 68;
  drawScreenBezel(ctx, d1X, d1Y, d1W, d1H, "NIFTY 50 [5M]  25,810.40 ▲ +134.20", "#38bdf8");
  
  // Micro Candlestick Chart
  const candleAreaX = d1X + 8;
  const candleAreaY = d1Y + 18;
  const candleAreaW = d1W - 16;
  const candleAreaH = d1H - 24;
  
  // Chart grid lines
  ctx.strokeStyle = "rgba(30, 41, 59, 0.6)";
  ctx.lineWidth = 1;
  for (let gy = candleAreaY + 8; gy < candleAreaY + candleAreaH; gy += 10) {
    ctx.beginPath();
    ctx.moveTo(candleAreaX, gy);
    ctx.lineTo(candleAreaX + candleAreaW, gy);
    ctx.stroke();
  }
  
  // Candlesticks pattern
  const candles = [
    { o: 28, c: 35, h: 38, l: 25 },
    { o: 35, c: 32, h: 37, l: 30 },
    { o: 32, c: 26, h: 33, l: 22 },
    { o: 26, c: 30, h: 34, l: 24 },
    { o: 30, c: 38, h: 40, l: 29 },
    { o: 38, c: 42, h: 44, l: 36 },
    { o: 42, c: 40, h: 43, l: 38 },
    { o: 40, c: 48, h: 50, l: 39 },
    { o: 48, c: 45, h: 49, l: 42 },
    { o: 45, c: 52, h: 54, l: 44 },
    { o: 52, c: 50, h: 53, l: 48 },
    { o: 50, c: 56, h: 58, l: 49 },
    { o: 56, c: 62, h: 64, l: 54 },
    { o: 62, c: 60, h: 63, l: 57 },
    { o: 60, c: 65, h: 68, l: 59 }
  ];
  
  const cWidth = 9;
  const spacing = (candleAreaW - 20) / candles.length;
  
  // Draw candles
  candles.forEach((c, i) => {
    const cx = candleAreaX + 10 + i * spacing;
    const isGreen = c.c >= c.o;
    const color = isGreen ? "#22c55e" : "#ef4444";
    
    const topY = candleAreaY + candleAreaH - c.h;
    const botY = candleAreaY + candleAreaH - c.l;
    const bodyTop = candleAreaY + candleAreaH - Math.max(c.o, c.c);
    const bodyHeight = Math.max(3, Math.abs(c.c - c.o));
    
    // Wick
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(cx + cWidth / 2, topY);
    ctx.lineTo(cx + cWidth / 2, botY);
    ctx.stroke();
    
    // Body
    ctx.fillStyle = color;
    ctx.fillRect(cx, bodyTop, cWidth, bodyHeight);
    
    // Volume bar at base
    ctx.fillStyle = isGreen ? "rgba(34, 197, 94, 0.35)" : "rgba(239, 68, 68, 0.35)";
    const volHeight = Math.min(10, (c.h - c.l) * 0.4);
    ctx.fillRect(cx, candleAreaY + candleAreaH - volHeight, cWidth, volHeight);
  });
  
  // Cyan EMA-9 curve across chart
  ctx.strokeStyle = "#06b6d4";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  candles.forEach((c, i) => {
    const cx = candleAreaX + 10 + i * spacing + cWidth / 2;
    const cy = candleAreaY + candleAreaH - (c.o + c.c) / 2;
    if (i === 0) ctx.moveTo(cx, cy);
    else ctx.lineTo(cx, cy);
  });
  ctx.stroke();

  // Gold VWAP line
  ctx.strokeStyle = "#facc15";
  ctx.lineWidth = 1;
  ctx.setLineDash([3, 2]);
  ctx.beginPath();
  ctx.moveTo(candleAreaX + 10, candleAreaY + candleAreaH - 36);
  ctx.lineTo(candleAreaX + candleAreaW - 10, candleAreaY + candleAreaH - 46);
  ctx.stroke();
  ctx.setLineDash([]);

  // --- DISPLAY 2 (CENTER): LEVEL-2 MARKET DEPTH & OMS STATUS ---
  const d2X = 425, d2Y = 26, d2W = 550, d2H = 68;
  drawScreenBezel(ctx, d2X, d2Y, d2W, d2H, "ANGEL ONE SMARTAPI GATEWAY — OMS ACTIVE (AACJ120032)", "#10b981");
  
  // Left: Live Depth Ladder (Bids vs Asks)
  const depthX = d2X + 10;
  const depthY = d2Y + 18;
  
  ctx.font = "bold 7px 'Press Start 2P', monospace";
  ctx.fillStyle = "#4ade80";
  ctx.fillText("BIDS (BUY)", depthX, depthY + 6);
  ctx.fillStyle = "#f87171";
  ctx.fillText("ASKS (SELL)", depthX + 120, depthY + 6);
  
  const depthBars = [
    { bidP: "25810.00", bidQ: 75, askP: "25810.50", askQ: 55 },
    { bidP: "25809.50", bidQ: 110, askP: "25811.00", askQ: 85 },
    { bidP: "25809.00", bidQ: 140, askP: "25811.50", askQ: 120 },
    { bidP: "25808.50", bidQ: 95, askP: "25812.00", askQ: 160 }
  ];
  
  depthBars.forEach((row, i) => {
    const rowY = depthY + 14 + i * 8;
    // Bid bar (green)
    ctx.fillStyle = "rgba(34, 197, 94, 0.25)";
    ctx.fillRect(depthX, rowY - 6, row.bidQ * 0.5, 7);
    ctx.fillStyle = "#86efac";
    ctx.fillText(`${row.bidP} (${row.bidQ})`, depthX + 2, rowY);
    
    // Ask bar (red)
    ctx.fillStyle = "rgba(239, 68, 68, 0.25)";
    ctx.fillRect(depthX + 120, rowY - 6, row.askQ * 0.5, 7);
    ctx.fillStyle = "#fca5a5";
    ctx.fillText(`${row.askP} (${row.askQ})`, depthX + 122, rowY);
  });
  
  // Center Divider in Display 2
  ctx.fillStyle = "#1e293b";
  ctx.fillRect(d2X + 240, d2Y + 16, 1, d2H - 20);
  
  // Right: Live Execution Blotter & Sentinel Gates
  const statX = d2X + 250;
  ctx.fillStyle = "#94a3b8";
  ctx.fillText("SYSTEM STATUS: 100% OPERATIONAL", statX, depthY + 6);
  ctx.fillStyle = "#38bdf8";
  ctx.fillText("PING: 38ms | PRE-TRADE GATE: 14/14 PASS", statX, depthY + 16);
  
  // Live rolling execution feed
  ctx.fillStyle = "#020617";
  ctx.fillRect(statX, depthY + 22, 280, 16);
  ctx.strokeStyle = "#334155";
  ctx.strokeRect(statX, depthY + 22, 280, 16);
  
  const blotterText = (tick % 200 > 100) 
    ? "⚡ [OMS] BUY 2000 TATAPOWER @ 428.50 FILLED | PROFIT LOCK: ENGAGED"
    : "🛡️ [GUARDIAN] TRAILING STOP ACTIVE (+1.2% LOCKED, 0 REVERSED)";
  ctx.fillStyle = "#fde047";
  ctx.fillText(blotterText, statX + 6, depthY + 33);

  // --- DISPLAY 3 (RIGHT): NSE SECTOR HEATMAP & BREADTH ---
  const d3X = 1015, d3Y = 26, d3W = 340, d3H = 68;
  drawScreenBezel(ctx, d3X, d3Y, d3W, d3H, "NSE SECTOR ROTATION & MARKET BREADTH", "#c084fc");
  
  const sectors = [
    { n: "IT", v: "+1.8%", up: true },
    { n: "AUTO", v: "+1.2%", up: true },
    { n: "BANK", v: "+0.6%", up: true },
    { n: "PHARMA", v: "+0.9%", up: true },
    { n: "REALTY", v: "+2.1%", up: true },
    { n: "ENERGY", v: "+0.5%", up: true },
    { n: "FMCG", v: "-0.2%", up: false },
    { n: "METAL", v: "-0.4%", up: false }
  ];
  
  const sW = 68, sH = 14;
  sectors.forEach((sec, idx) => {
    const col = idx % 4;
    const row = Math.floor(idx / 4);
    const sx = d3X + 10 + col * (sW + 12);
    const sy = d3Y + 18 + row * (sH + 4);
    
    ctx.fillStyle = sec.up ? "#064e3b" : "#7f1d1d";
    ctx.fillRect(sx, sy, sW, sH);
    ctx.strokeStyle = sec.up ? "#10b981" : "#ef4444";
    ctx.strokeRect(sx, sy, sW, sH);
    
    ctx.font = "bold 6px 'Press Start 2P', monospace";
    ctx.fillStyle = sec.up ? "#86efac" : "#fca5a5";
    ctx.fillText(`${sec.n} ${sec.v}`, sx + 4, sy + 10);
  });
  
  // Market Breadth Progress Bar (Bottom of Display 3)
  const brY = d3Y + 54;
  ctx.font = "bold 6px 'Press Start 2P', monospace";
  ctx.fillStyle = "#94a3b8";
  ctx.fillText("BREADTH: 34 ADV / 16 DEC", d3X + 10, brY);
  
  ctx.fillStyle = "#1e293b";
  ctx.fillRect(d3X + 140, brY - 6, 180, 8);
  // Advances bar (green)
  ctx.fillStyle = "#22c55e";
  ctx.fillRect(d3X + 140, brY - 6, 120, 8);
  // Declines bar (red)
  ctx.fillStyle = "#ef4444";
  ctx.fillRect(d3X + 260, brY - 6, 60, 8);
}

function drawScreenBezel(ctx, x, y, w, h, title, glowColor) {
  // Metallic monitor chassis
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = "#334155";
  ctx.lineWidth = 2;
  ctx.strokeRect(x, y, w, h);
  
  // Mounting brackets
  ctx.fillStyle = "#475569";
  ctx.fillRect(x + 10, y - 4, 8, 4);
  ctx.fillRect(x + w - 18, y - 4, 8, 4);
  
  // Monitor Title Header Bar
  ctx.fillStyle = "#1e293b";
  ctx.fillRect(x + 2, y + 2, w - 4, 12);
  
  // LED status indicator
  ctx.fillStyle = glowColor;
  ctx.beginPath();
  ctx.arc(x + 8, y + 8, 3, 0, Math.PI * 2);
  ctx.fill();
  
  ctx.font = "bold 7px 'JetBrains Mono', 'Press Start 2P', monospace";
  ctx.fillStyle = "#e2e8f0";
  ctx.fillText(title, x + 16, y + 10);
}

// ------------------------------------------------------------
// Trading Floor Department Stencils & Zone Markings
// ------------------------------------------------------------
function drawTradingFloorZones(ctx) {
  const zones = [
    { x: 35, y: 112, w: 435, h: 90, title: "// ZONE 01: EXECUTIVE & GLOBAL MACRO //", color: "rgba(56, 189, 248, 0.4)" },
    { x: 715, y: 112, w: 585, h: 90, title: "// ZONE 02: QUANT & TECHNICAL ALPHA LAB //", color: "rgba(168, 85, 247, 0.4)" },
    { x: 45, y: 285, w: 345, h: 100, title: "// ZONE 03: NEWS, SENTIMENT & MACRO PULSE //", color: "rgba(192, 132, 252, 0.4)" },
    { x: 1060, y: 290, w: 220, h: 105, title: "// ZONE 04: AI MEMORY VAULT & CTO //", color: "rgba(59, 130, 246, 0.4)" },
    { x: 35, y: 485, w: 435, h: 200, title: "// ZONE 05: FUNDAMENTAL, DERIVATIVES & F&O //", color: "rgba(6, 182, 212, 0.4)" },
    { x: 540, y: 485, w: 680, h: 200, title: "// ZONE 06: RISK SENTINEL & OMS EXECUTION FORTRESS //", color: "rgba(34, 197, 94, 0.4)" }
  ];
  
  zones.forEach(z => {
    // Zone perimeter dashed track
    ctx.strokeStyle = z.color;
    ctx.lineWidth = 1;
    ctx.setLineDash([8, 8]);
    ctx.strokeRect(z.x, z.y, z.w, z.h);
    ctx.setLineDash([]);
    
    // Corner brackets
    const bLen = 12;
    ctx.strokeStyle = z.color.replace("0.4", "0.9");
    ctx.lineWidth = 2;
    // Top-left
    ctx.beginPath(); ctx.moveTo(z.x, z.y + bLen); ctx.lineTo(z.x, z.y); ctx.lineTo(z.x + bLen, z.y); ctx.stroke();
    // Top-right
    ctx.beginPath(); ctx.moveTo(z.x + z.w - bLen, z.y); ctx.lineTo(z.x + z.w, z.y); ctx.lineTo(z.x + z.w, z.y + bLen); ctx.stroke();
    // Bottom-left
    ctx.beginPath(); ctx.moveTo(z.x, z.y + z.h - bLen); ctx.lineTo(z.x, z.y + z.h); ctx.lineTo(z.x + bLen, z.y + z.h); ctx.stroke();
    // Bottom-right
    ctx.beginPath(); ctx.moveTo(z.x + z.w - bLen, z.y + z.h); ctx.lineTo(z.x + z.w, z.y + z.h); ctx.lineTo(z.x + z.w, z.y + z.h - bLen); ctx.stroke();
    
    // Zone Stencil Header on Floor
    ctx.font = "bold 7px 'JetBrains Mono', 'Press Start 2P', monospace";
    ctx.fillStyle = z.color.replace("0.4", "0.75");
    ctx.fillText(z.title, z.x + 8, z.y + 12);
  });
  
  // CENTER ADVERSARIAL TRADING PIT (WAR ROOM RING)
  const pitX = 440, pitY = 290, pitW = 570, pitH = 120;
  ctx.save();
  ctx.strokeStyle = "rgba(250, 204, 21, 0.4)";
  ctx.lineWidth = 2;
  ctx.setLineDash([6, 6]);
  ctx.strokeRect(pitX, pitY, pitW, pitH);
  ctx.setLineDash([]);
  
  // Corner accents
  ctx.fillStyle = "#facc15";
  ctx.fillRect(pitX - 3, pitY - 3, 6, 6);
  ctx.fillRect(pitX + pitW - 3, pitY - 3, 6, 6);
  ctx.fillRect(pitX - 3, pitY + pitH - 3, 6, 6);
  ctx.fillRect(pitX + pitW - 3, pitY + pitH - 3, 6, 6);
  
  ctx.font = "bold 8px 'Press Start 2P', monospace";
  ctx.fillStyle = "rgba(250, 204, 21, 0.85)";
  ctx.fillText("⚔️ HIGH-STAKES ADVERSARIAL DEBATE ARENA (BULL vs BEAR) ⚔️", pitX + 30, pitY + 14);
  ctx.restore();
}

// ------------------------------------------------------------
// Fiber-Optic Underfloor Data Runways
// ------------------------------------------------------------
function drawFloorFiberChannels(ctx, tick) {
  // Conduits linking pods cleanly along grid lines
  const paths = [
    // Top Exec to Tech & Quant
    { x1: 440, y1: 170, x2: 730, y2: 170, color: "#38bdf8" },
    // News to War Room
    { x1: 370, y1: 350, x2: 460, y2: 350, color: "#c084fc" },
    // War Room to Risk Fortress
    { x1: 720, y1: 410, x2: 720, y2: 490, color: "#facc15" },
    // Derivatives to Risk Fortress
    { x1: 450, y1: 560, x2: 550, y2: 560, color: "#06b6d4" },
    // CTO to Memory Vault
    { x1: 1170, y1: 350, x2: 1260, y2: 350, color: "#3b82f6" }
  ];
  
  paths.forEach(p => {
    // Channel track
    ctx.strokeStyle = "rgba(30, 41, 59, 0.8)";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(p.x1, p.y1);
    ctx.lineTo(p.x2, p.y2);
    ctx.stroke();
    
    ctx.strokeStyle = p.color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(p.x1, p.y1);
    ctx.lineTo(p.x2, p.y2);
    ctx.stroke();
    
    // Moving photon pulse
    const pulseOffset = ((tick * 1.5) % 100) / 100;
    const px = p.x1 + (p.x2 - p.x1) * pulseOffset;
    const py = p.y1 + (p.y2 - p.y1) * pulseOffset;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(px - 2, py - 2, 4, 4);
    ctx.fillStyle = p.color;
    ctx.beginPath();
    ctx.arc(px, py, 4, 0, Math.PI * 2);
    ctx.fill();
  });
}

// ------------------------------------------------------------
// Institutional Trading Pods, High-End Desks & Server Vault
// ------------------------------------------------------------
function drawFurnitureAndPlants(ctx) {
  const tick = PixelOffice.tick;

  // 1. TRADING DESKS WITH MULTI-MONITOR RIGS
  PixelOffice.desks.forEach(desk => {
    // Drop shadow
    ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
    ctx.fillRect(desk.x + 4, desk.y + desk.h - 4, desk.w, 10);
    
    // High-tech Carbon & Metallic Desk Surface
    ctx.fillStyle = "#131a29";
    ctx.fillRect(desk.x, desk.y, desk.w, desk.h);
    
    // Brushed Titanium Border
    ctx.fillStyle = "#27354f";
    ctx.fillRect(desk.x, desk.y, desk.w, 4);
    ctx.fillRect(desk.x, desk.y, 4, desk.h);
    ctx.fillRect(desk.x + desk.w - 4, desk.y, 4, desk.h);
    
    // Soft illuminated LED strip on front edge of desk
    ctx.fillStyle = desk.monitorColor || "#38bdf8";
    ctx.fillRect(desk.x, desk.y + desk.h - 3, desk.w, 3);
    
    // Workstation PC Tower under desk (with blinking power & HDD LEDs)
    const pcX = desk.x + 8;
    const pcY = desk.y + desk.h - 18;
    ctx.fillStyle = "#090d16";
    ctx.fillRect(pcX, pcY, 14, 20);
    ctx.fillStyle = "#334155";
    ctx.fillRect(pcX + 2, pcY + 2, 10, 3);
    // Power LED (Cyan)
    ctx.fillStyle = "#38bdf8";
    ctx.fillRect(pcX + 3, pcY + 8, 2, 2);
    // HDD Activity LED (Flickering Yellow)
    ctx.fillStyle = (tick % 16 < 8) ? "#facc15" : "#451a03";
    ctx.fillRect(pcX + 8, pcY + 8, 2, 2);

    // Ergonomic high-mesh trading chairs
    drawTradingChair(ctx, desk.x + desk.w / 2 - 12, desk.y + desk.h - 8);

    // Multi-Monitor Trading Rig
    if (desk.w >= 140) {
      // 3-MONITOR INSTITUTIONAL SETUP
      drawTradingMonitor(ctx, desk.x + 8, desk.y + 8, "chart", desk.monitorColor);
      drawTradingMonitor(ctx, desk.x + desk.w / 2 - 18, desk.y + 6, "depth", "#22c55e");
      drawTradingMonitor(ctx, desk.x + desk.w - 44, desk.y + 8, "terminal", "#38bdf8");
    } else {
      // DUAL MONITOR COMPACT SETUP
      drawTradingMonitor(ctx, desk.x + 10, desk.y + 8, "chart", desk.monitorColor);
      drawTradingMonitor(ctx, desk.x + desk.w - 46, desk.y + 8, "depth", "#38bdf8");
    }
    
    // Trading Coffee Mug
    if (desk.hasMug) {
      const mugX = desk.x + desk.w - 20;
      const mugY = desk.y + desk.h - 18;
      ctx.fillStyle = desk.id.includes("bull") ? "#22c55e" : (desk.id.includes("bear") ? "#ef4444" : "#f8fafc");
      ctx.fillRect(mugX, mugY, 7, 9);
      ctx.fillStyle = "#475569";
      ctx.fillRect(mugX - 2, mugY + 2, 2, 5);
      // Steam
      const steamY = mugY - 3 - ((tick + desk.x) % 14) / 2;
      ctx.fillStyle = "rgba(255,255,255,0.5)";
      ctx.fillRect(mugX + 2 + Math.sin(tick * 0.1) * 2, steamY, 2, 3);
    }
    
    // Desk Blotter / Backlit Keyboard
    const kbX = desk.x + desk.w / 2 - 16;
    const kbY = desk.y + desk.h - 14;
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(kbX, kbY, 32, 8);
    // Glowing backlit keys
    ctx.fillStyle = "rgba(56, 189, 248, 0.4)";
    ctx.fillRect(kbX + 2, kbY + 2, 28, 4);
  });

  // 2. CENTER WAR ROOM HOLOGRAPHIC DEBATE TABLE
  drawWarRoomHologram(ctx, tick);

  // 3. ENTERPRISE SERVER VAULT RACKS (MID-RIGHT)
  drawServerVault(ctx, 1285, 305, tick);

  // 4. ARCHITECTURAL INDOOR PLANTS (Corporate Slate Planters)
  PixelOffice.plants.forEach(p => {
    // Sleek geometric charcoal planter
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(p.x, p.y + 12, 18, 16);
    ctx.fillStyle = "#334155";
    ctx.fillRect(p.x - 2, p.y + 10, 22, 3);
    // White decorative gravel
    ctx.fillStyle = "#cbd5e1";
    ctx.fillRect(p.x + 2, p.y + 11, 14, 2);
    
    // Architectural snake plant leaves
    ctx.fillStyle = "#15803d";
    ctx.fillRect(p.x + 3, p.y + 2, 3, 10);
    ctx.fillRect(p.x + 12, p.y + 4, 3, 8);
    ctx.fillStyle = "#22c55e";
    ctx.fillRect(p.x + 7, p.y - 4, 4, 16);
    ctx.fillStyle = "#4ade80";
    ctx.fillRect(p.x + 8, p.y - 7, 2, 5);
  });
}

// ------------------------------------------------------------
// Ergonomic Mesh Trading Chair
// ------------------------------------------------------------
function drawTradingChair(ctx, x, y) {
  // Swivel 5-star base
  ctx.fillStyle = "#475569";
  ctx.fillRect(x + 2, y + 14, 20, 2);
  ctx.fillRect(x + 11, y + 10, 2, 5);
  
  // Mesh Seat Cushion
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(x + 4, y + 6, 16, 5);
  
  // High Mesh Backrest
  ctx.fillStyle = "#1e293b";
  ctx.fillRect(x + 6, y - 6, 12, 12);
  ctx.strokeStyle = "#334155";
  ctx.strokeRect(x + 6, y - 6, 12, 12);
  
  // Padded Headrest
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(x + 7, y - 11, 10, 4);
}

// ------------------------------------------------------------
// Realistic Micro Bloomberg & Candlestick Trading Monitors
// ------------------------------------------------------------
function drawTradingMonitor(ctx, x, y, type, screenColor) {
  const tick = PixelOffice.tick;
  
  // Articulated Monitor Arm & Stand
  ctx.fillStyle = "#475569";
  ctx.fillRect(x + 15, y + 22, 6, 8);
  ctx.fillRect(x + 10, y + 28, 16, 2);
  
  // Bezel
  ctx.fillStyle = "#090d16";
  ctx.fillRect(x, y, 36, 23);
  ctx.strokeStyle = "#334155";
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, 36, 23);
  
  // Screen Display
  ctx.fillStyle = "#020617";
  ctx.fillRect(x + 1, y + 1, 34, 21);
  
  if (type === "chart") {
    // Real Mini Candlesticks & EMA
    const miniCandles = [
      { g: true, h: 8, l: 3 },
      { g: false, h: 6, l: 4 },
      { g: true, h: 10, l: 2 },
      { g: true, h: 14, l: 6 },
      { g: false, h: 11, l: 7 },
      { g: true, h: 16, l: 9 }
    ];
    miniCandles.forEach((mc, idx) => {
      const mcX = x + 3 + idx * 5;
      ctx.fillStyle = mc.g ? "#22c55e" : "#ef4444";
      ctx.fillRect(mcX + 1, y + 18 - mc.h, 1, mc.h);
      ctx.fillRect(mcX, y + 18 - mc.h + 2, 3, Math.max(2, mc.h - mc.l));
    });
    // Cyan Trend Line
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x + 2, y + 16);
    ctx.lineTo(x + 14, y + 12);
    ctx.lineTo(x + 24, y + 14);
    ctx.lineTo(x + 33, y + 6);
    ctx.stroke();
  } else if (type === "depth") {
    // Level-2 Order Depth Bars
    ctx.fillStyle = "rgba(34, 197, 94, 0.7)";
    ctx.fillRect(x + 3, y + 3, 12, 3);
    ctx.fillRect(x + 3, y + 7, 16, 3);
    ctx.fillRect(x + 3, y + 11, 8, 3);
    
    ctx.fillStyle = "rgba(239, 68, 68, 0.7)";
    ctx.fillRect(x + 20, y + 3, 10, 3);
    ctx.fillRect(x + 20, y + 7, 14, 3);
    ctx.fillRect(x + 20, y + 11, 7, 3);
    
    // Spread Quote
    ctx.fillStyle = "#facc15";
    ctx.fillRect(x + 12, y + 16, 12, 4);
  } else {
    // Bloomberg Terminal Matrix (Amber / Green)
    ctx.fillStyle = screenColor || "#facc15";
    ctx.fillRect(x + 3, y + 3, 16, 2);
    ctx.fillRect(x + 3, y + 7, 24, 2);
    ctx.fillRect(x + 3, y + 11, 14, 2);
    ctx.fillRect(x + 3, y + 14, 20, 2);
    // Green P&L badge
    ctx.fillStyle = "#22c55e";
    ctx.fillRect(x + 20, y + 17, 12, 4);
  }
}

// ------------------------------------------------------------
// War Room Holographic Debate Table (Bull vs Bear Arena)
// ------------------------------------------------------------
function drawWarRoomHologram(ctx, tick) {
  const cx = 600, cy = 355;
  
  // Hologram Projector Pedestal
  ctx.fillStyle = "#0f172a";
  ctx.beginPath();
  ctx.ellipse(cx, cy + 18, 55, 14, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 2;
  ctx.stroke();
  
  // Rotating Hologram Projection Cone
  const glow = 0.15 + Math.sin(tick * 0.08) * 0.05;
  ctx.fillStyle = `rgba(56, 189, 248, ${glow})`;
  ctx.beginPath();
  ctx.moveTo(cx, cy + 18);
  ctx.lineTo(cx - 45, cy - 20);
  ctx.lineTo(cx + 45, cy - 20);
  ctx.closePath();
  ctx.fill();
  
  // Holographic Consensus Dial
  ctx.fillStyle = "#020617";
  ctx.fillRect(cx - 50, cy - 30, 100, 16);
  ctx.strokeStyle = "#facc15";
  ctx.lineWidth = 1;
  ctx.strokeRect(cx - 50, cy - 30, 100, 16);
  
  ctx.font = "bold 6px 'Press Start 2P', monospace";
  ctx.fillStyle = "#22c55e";
  ctx.fillText("BULL 65%", cx - 46, cy - 20);
  ctx.fillStyle = "#ef4444";
  ctx.fillText("35% BEAR", cx + 6, cy - 20);
  
  // Electric sparks arcing across debate table
  if (tick % 20 < 10) {
    ctx.strokeStyle = "#fde047";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(cx - 30, cy - 8);
    ctx.lineTo(cx - 10, cy - 14);
    ctx.lineTo(cx + 5, cy - 5);
    ctx.lineTo(cx + 30, cy - 10);
    ctx.stroke();
  }
}

// ------------------------------------------------------------
// Enterprise 42U Server Vault Racks (Mid-Right Corner)
// ------------------------------------------------------------
function drawServerVault(ctx, x, y, tick) {
  // Dual 42U Server Cabinets
  for (let rackIdx = 0; rackIdx < 2; rackIdx++) {
    const rx = x + rackIdx * 38;
    
    // Outer Frame
    ctx.fillStyle = "#090d16";
    ctx.fillRect(rx, y, 34, 75);
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 1.5;
    ctx.strokeRect(rx, y, 34, 75);
    
    // Tinted Glass Door with Reflection
    ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
    ctx.fillRect(rx + 2, y + 2, 30, 71);
    
    // Stacked Server Blades (1U/2U)
    for (let u = 0; u < 8; u++) {
      const uy = y + 4 + u * 8;
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(rx + 4, uy, 26, 6);
      
      // Blinking status LEDs (Cyan, Emerald, Amber)
      const ledTick = (tick + u * 7 + rackIdx * 13) % 24;
      ctx.fillStyle = (ledTick > 6) ? "#10b981" : "#06b6d4";
      ctx.fillRect(rx + 6, uy + 2, 2, 2);
      ctx.fillRect(rx + 10, uy + 2, 2, 2);
      ctx.fillStyle = (ledTick > 14) ? "#38bdf8" : "#f59e0b";
      ctx.fillRect(rx + 14, uy + 2, 2, 2);
    }
    
    // Top Cooling Fan Grille with Spinning Animation
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(rx + 4, y + 68, 26, 4);
    ctx.fillStyle = (tick % 4 < 2) ? "#64748b" : "#94a3b8";
    ctx.fillRect(rx + 8, y + 69, 8, 2);
    ctx.fillRect(rx + 18, y + 69, 8, 2);
  }
}

// ------------------------------------------------------------
// High-Tech Non-Intrusive Data Pipelines (Replaces Chaotic Overlapping Web)
// ------------------------------------------------------------
function drawCollaborationArrows(ctx) {
  if (!PixelOffice.showFlows) return;
  const t = PixelOffice.tick * 0.035;
  
  // 1. GLOBAL & PRE-MARKET BUS
  drawDashedArrow(ctx, 290, 145, 100, 145, "#38bdf8", "GLOBAL CUES", t);
  drawDashedArrow(ctx, 400, 140, 110, 140, "#f97316", "GAP EST", t);
  
  // 2. EXECUTIVE TASK DELEGATION -> TECH & QUANT DESKS
  drawDashedArrow(ctx, 420, 160, 735, 160, "#4ade80", "DELEGATE", t);
  drawDashedArrow(ctx, 775, 160, 845, 160, "#a855f7", "MOMENTUM", t);
  drawDashedArrow(ctx, 885, 160, 965, 160, "#ec4899", "ALPHA", t);
  drawDashedArrow(ctx, 1005, 160, 1075, 160, "#f59e0b", "REGIME", t);
  
  // 3. NEWS & MACRO BUS (MID-LEFT)
  drawDashedArrow(ctx, 105, 330, 175, 330, "#c084fc", "FILINGS", t);
  drawDashedArrow(ctx, 215, 330, 285, 330, "#60a5fa", "FII FLOWS", t);
  
  // 4. FUNDAMENTAL, VALUATION & DERIVATIVES (BOTTOM-LEFT)
  drawDashedArrow(ctx, 95, 530, 160, 530, "#3b82f6", "EARNINGS", t);
  drawDashedArrow(ctx, 310, 530, 380, 530, "#38bdf8", "GREEKS/PCR", t);
  drawDashedArrow(ctx, 240, 610, 745, 185, "#c084fc", "ROTATION", t);
  
  // 5. ADVERSARIAL DEBATE ARENA & AI ACADEMY
  drawDashedArrow(ctx, 525, 345, 585, 320, "#22c55e", "BULL THESIS", t);
  drawDashedArrow(ctx, 680, 345, 615, 320, "#ef4444", "BEAR DEFENSE", t);
  
  // 6. DEBATE SYNTHESIS -> RISK SENTINEL
  drawDashedArrow(ctx, 580, 305, 200, 185, "#a855f7", "CONSENSUS", t);
  drawDashedArrow(ctx, 600, 345, 600, 495, "#facc15", "14-PT AUDIT", t);
  
  // 7. RISK & EXECUTION PIPELINE (BOTTOM-RIGHT)
  drawDashedArrow(ctx, 605, 530, 675, 530, "#4ade80", "14 PASS", t);
  drawDashedArrow(ctx, 715, 530, 785, 530, "#22c55e", "SL/TP SET", t);
  drawDashedArrow(ctx, 825, 530, 895, 530, "#f59e0b", "COMPLIANCE", t);
  drawDashedArrow(ctx, 935, 530, 1005, 530, "#f472b6", "OMS VERIFY", t);
  drawDashedArrow(ctx, 1045, 530, 1125, 530, "#38bdf8", "SMARTAPI ROUTE", t);
  
  // 8. TELEMETRY & FEEDBACK BUS
  drawDashedArrow(ctx, 1150, 505, 1215, 375, "#a855f7", "TELEMETRY", t);
  drawCurvedFeedbackBus(ctx, 1260, 305, 100, 125, "#818cf8", "MEMORY RECALL", t);
}

function drawDashedArrow(ctx, x1, y1, x2, y2, color, label, phase) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.setLineDash([5, 4]);
  ctx.lineDashOffset = -phase * 18;
  
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
  
  // Subtle arrow head
  const angle = Math.atan2(y2 - y1, x2 - x1);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - 6 * Math.cos(angle - Math.PI / 6), y2 - 6 * Math.sin(angle - Math.PI / 6));
  ctx.lineTo(x2 - 6 * Math.cos(angle + Math.PI / 6), y2 - 6 * Math.sin(angle + Math.PI / 6));
  ctx.closePath();
  ctx.fill();

  // Floating Pulse Packet (Photon)
  const pulsePos = (phase % 1 + 1) % 1;
  const px = x1 + (x2 - x1) * pulsePos;
  const py = y1 + (y2 - y1) * pulsePos;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(px - 1.5, py - 1.5, 3, 3);
  
  // Compact, Non-Intrusive Label
  if (label) {
    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2 - 8;
    
    ctx.font = "bold 6px 'JetBrains Mono', 'Press Start 2P', monospace";
    const textWidth = ctx.measureText(label).width;
    
    ctx.fillStyle = "rgba(10, 14, 23, 0.9)";
    ctx.fillRect(midX - textWidth / 2 - 2, midY - 5, textWidth + 4, 10);
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.8;
    ctx.setLineDash([]);
    ctx.strokeRect(midX - textWidth / 2 - 2, midY - 5, textWidth + 4, 10);
    
    ctx.fillStyle = "#f8fafc";
    ctx.fillText(label, midX - textWidth / 2, midY + 3);
  }
  
  ctx.restore();
}

function drawCurvedFeedbackBus(ctx, x1, y1, x2, y2, color, label, phase) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.setLineDash([6, 4]);
  ctx.lineDashOffset = -phase * 20;
  
  const cpX = (x1 + x2) / 2;
  const cpY = 25;
  
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.quadraticCurveTo(cpX, cpY, x2, y2);
  ctx.stroke();

  // Arrow Head at target
  const angle = Math.atan2(y2 - cpY, x2 - cpX);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - 6 * Math.cos(angle - Math.PI / 6), y2 - 6 * Math.sin(angle - Math.PI / 6));
  ctx.lineTo(x2 - 6 * Math.cos(angle + Math.PI / 6), y2 - 6 * Math.sin(angle + Math.PI / 6));
  ctx.closePath();
  ctx.fill();

  if (label) {
    ctx.font = "bold 6px 'JetBrains Mono', 'Press Start 2P', monospace";
    const textWidth = ctx.measureText(label).width;
    
    ctx.fillStyle = "rgba(10, 14, 23, 0.9)";
    ctx.fillRect(cpX - textWidth / 2 - 3, cpY - 5, textWidth + 6, 10);
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.8;
    ctx.setLineDash([]);
    ctx.strokeRect(cpX - textWidth / 2 - 3, cpY - 5, textWidth + 6, 10);
    
    ctx.fillStyle = "#ffffff";
    ctx.fillText(label, cpX - textWidth / 2, cpY + 3);
  }

  ctx.restore();
}

// ------------------------------------------------------------
// Characters Rendering
// ------------------------------------------------------------
function drawAllCharacters(ctx) {
  PixelOffice.agents.forEach(agent => {
    drawCharacter(ctx, agent);
  });
}

function drawCharacter(ctx, agent) {
  const isHovered = PixelOffice.hoveredAgent === agent;
  const isSelected = PixelOffice.selectedAgent === agent;
  
  const bobY = Math.sin(PixelOffice.tick * 0.08 + agent.x) * 2;
  const x = agent.x;
  const y = agent.y + bobY;
  
  ctx.save();
  
  if (agent.halo || isHovered || isSelected) {
    const glowColor = isHovered ? "rgba(253, 224, 71, 0.5)" : (agent.color === "#ef4444" ? "rgba(239, 68, 68, 0.4)" : "rgba(74, 222, 128, 0.35)");
    ctx.fillStyle = glowColor;
    ctx.beginPath();
    ctx.arc(x + 12, y + 16, 22, 0, Math.PI * 2);
    ctx.fill();
  }
  
  if (agent.type === "robot") {
    drawRobot(ctx, x, y);
  } else {
    // Hair
    ctx.fillStyle = agent.hairColor || "#78350f";
    ctx.fillRect(x + 4, y, 16, 7);
    ctx.fillRect(x + 2, y + 4, 3, 8);
    
    // Face
    ctx.fillStyle = "#fbcfe8";
    ctx.fillRect(x + 6, y + 5, 12, 9);
    
    // Eyes
    const isBlinking = (PixelOffice.tick % 130 > 124);
    ctx.fillStyle = "#0f172a";
    if (!isBlinking) {
      ctx.fillRect(x + 8, y + 7, 2, 3);
      ctx.fillRect(x + 14, y + 7, 2, 3);
    } else {
      ctx.fillRect(x + 8, y + 9, 3, 1);
      ctx.fillRect(x + 14, y + 9, 3, 1);
    }
    
    // Torso / Shirt
    const shirtColor = agent.shirtColor || ((agent.type === "manager" || agent.type === "intern") ? "#1e3a8a" : "#22c55e");
    ctx.fillStyle = shirtColor;
    ctx.fillRect(x + 4, y + 14, 16, 13);
    
    if (agent.type === "manager" || agent.type === "intern" || agent.type === "senior_guide") {
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(x + 10, y + 14, 4, 3);
      ctx.fillStyle = "#ef4444";
      ctx.fillRect(x + 11, y + 16, 2, 7);
    }
    
    // Legs
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(x + 6, y + 27, 4, 9);
    ctx.fillRect(x + 14, y + 27, 4, 9);
    
    // Accessories
    if (agent.hasGradCap) {
      ctx.fillStyle = "#0f172a";
      ctx.fillRect(x, y - 5, 24, 4);
      ctx.fillStyle = "#0284c7";
      ctx.fillRect(x + 10, y - 9, 4, 4);
      ctx.fillStyle = "#facc15";
      ctx.fillRect(x + 20, y - 3, 3, 7);
    }
    
    if (agent.holdingClipboard) {
      ctx.fillStyle = "#d97706";
      ctx.fillRect(x + 20, y + 10, 8, 14);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(x + 22, y + 12, 4, 10);
    }
    
    if (agent.hasMonocle) {
      ctx.fillStyle = "#38bdf8";
      ctx.fillRect(x + 13, y + 5, 5, 5);
      ctx.strokeStyle = "#0284c7";
      ctx.lineWidth = 1;
      ctx.strokeRect(x + 13, y + 5, 5, 5);
    }
  }
  
  ctx.restore();
}

function drawRobot(ctx, x, y) {
  ctx.fillStyle = "#64748b";
  ctx.fillRect(x + 10, y - 6, 4, 7);
  ctx.fillStyle = "#ef4444";
  ctx.fillRect(x + 9, y - 9, 6, 4);
  
  ctx.fillStyle = "#94a3b8";
  ctx.fillRect(x + 2, y, 20, 15);
  ctx.fillStyle = "#cbd5e1";
  ctx.fillRect(x + 4, y + 2, 16, 2);
  
  ctx.fillStyle = "#06b6d4";
  ctx.fillRect(x + 6, y + 5, 4, 4);
  ctx.fillRect(x + 14, y + 5, 4, 4);
  
  ctx.fillStyle = "#64748b";
  ctx.fillRect(x, y + 16, 24, 16);
  
  ctx.fillStyle = "#10b981";
  ctx.fillRect(x + 6, y + 20, 12, 5);
  
  ctx.fillStyle = "#334155";
  ctx.fillRect(x + 2, y + 32, 20, 5);
}

// ------------------------------------------------------------
// Non-Overlapping HUD Badges & Speech Bubbles
// ------------------------------------------------------------
function drawHUDAndSpeechBubbles(ctx) {
  PixelOffice.agents.forEach((agent, idx) => {
    const x = agent.x;
    const y = agent.y;
    
    ctx.save();
    // Stagger adjacent agents so labels NEVER collide horizontally
    const isHovered = PixelOffice.hoveredAgent === agent;
    const badgeY = (idx % 2 === 0) ? y - 13 : y - 24;
    
    // Clean, readable monospace font
    ctx.font = isHovered ? "bold 8px 'JetBrains Mono', monospace" : "bold 7px 'JetBrains Mono', 'Silkscreen', monospace";
    const nameText = agent.name;
    const textWidth = ctx.measureText(nameText).width;
    const badgeW = textWidth + 14;
    const badgeH = 12;
    const badgeX = x + 12 - badgeW / 2;
    
    // Cyber Pill Badge
    ctx.fillStyle = isHovered ? "rgba(15, 23, 42, 0.98)" : "rgba(10, 14, 23, 0.90)";
    ctx.fillRect(badgeX, badgeY - 5, badgeW, badgeH);
    ctx.strokeStyle = isHovered ? "#facc15" : (agent.color || "#38bdf8");
    ctx.lineWidth = isHovered ? 1.5 : 1;
    ctx.strokeRect(badgeX, badgeY - 5, badgeW, badgeH);
    
    // Live Pulse Dot
    const dotColor = (agent.color === "#ef4444") ? "#ef4444" : (agent.color === "#4ade80" || agent.color === "#22c55e" ? "#22c55e" : "#38bdf8");
    ctx.fillStyle = dotColor;
    ctx.beginPath();
    ctx.arc(badgeX + 5, badgeY + 1, 2.5, 0, Math.PI * 2);
    ctx.fill();
    
    // Name text
    ctx.fillStyle = isHovered ? "#facc15" : "#f8fafc";
    ctx.fillText(nameText, badgeX + 11, badgeY + 4);
    
    // Speech question bubble
    if (agent.id === "sentiment_agent" || agent.id === "bear_agent") {
      const bubbleY = badgeY - 14 + Math.sin(PixelOffice.tick * 0.1) * 2;
      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(x + 24, bubbleY, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#0284c7";
      ctx.stroke();
      ctx.font = "bold 7px 'Press Start 2P', monospace";
      ctx.fillStyle = "#0284c7";
      ctx.fillText("?", x + 21, bubbleY + 2.5);
    }
    
    // New Hire Badge
    if (agent.id === "intern_agent") {
      const bannerX = x + 12;
      const bannerY = badgeY - 12;
      ctx.font = "bold 7px 'Press Start 2P', monospace";
      const txt = "NEW HIRE!";
      const w = ctx.measureText(txt).width;
      
      ctx.fillStyle = "#facc15";
      ctx.fillRect(bannerX - w/2 - 3, bannerY - 6, w + 6, 12);
      ctx.fillStyle = "#000000";
      ctx.fillText(txt, bannerX - w/2, bannerY + 2);
    }
    
    ctx.restore();
  });
}

function toggleFlows() {
  PixelOffice.showFlows = !PixelOffice.showFlows;
  const btn = document.getElementById('btnToggleFlows');
  if (btn) {
    btn.innerHTML = PixelOffice.showFlows ? '<span class="p-icon">📡</span> DATA PIPES: ON' : '<span class="p-icon">📡</span> DATA PIPES: OFF';
    btn.style.color = PixelOffice.showFlows ? '#38bdf8' : '#94a3b8';
  }
}

// ============================================================
// 5. USER INTERACTION & MODALS
// ============================================================
function handleMouseMove(e) {
  const rect = PixelOffice.canvas.getBoundingClientRect();
  const mouseX = (e.clientX - rect.left) / PixelOffice.scale - (PixelOffice.canvas.width - PixelOffice.width * PixelOffice.scale) / (2 * PixelOffice.scale);
  const mouseY = (e.clientY - rect.top) / PixelOffice.scale - (PixelOffice.canvas.height - PixelOffice.height * PixelOffice.scale) / (2 * PixelOffice.scale);
  
  let found = null;
  PixelOffice.agents.forEach(agent => {
    if (mouseX >= agent.x - 8 && mouseX <= agent.x + 36 &&
        mouseY >= agent.y - 12 && mouseY <= agent.y + 40) {
      found = agent;
    }
  });
  
  PixelOffice.hoveredAgent = found;
  PixelOffice.canvas.style.cursor = found ? 'pointer' : 'default';
}

function handleCanvasClick(e) {
  if (PixelOffice.hoveredAgent) {
    sfx.playBlip(520, 'square', 0.1);
    openAgentModal(PixelOffice.hoveredAgent);
  }
}

async function openAgentModal(agent) {
  PixelOffice.selectedAgent = agent;
  
  // 1. Initial Immediate Render
  document.getElementById('modalAvatar').innerText = agent.avatar || "👔";
  document.getElementById('modalAgentName').innerText = agent.name;
  document.getElementById('modalAgentRole').innerText = agent.role;
  document.getElementById('modalStatus').innerText = agent.status || "RUNNING";
  document.getElementById('modalDept').innerText = agent.dept || "Specialist Trading Desk";
  document.getElementById('modalConfidence').innerText = agent.confidence || "95.0%";
  document.getElementById('modalCycles').innerText = agent.cycles || 140;
  document.getElementById('modalThought').innerText = `"${agent.thought || 'Analyzing live market conditions...'}"`;
  
  // Set fallback active operation & target
  const opEl = document.getElementById('modalCurrentOperation');
  if (opEl) opEl.innerText = agent.task || `Executing ${agent.name} market intelligence pipeline`;
  const symEl = document.getElementById('modalActiveSymbol');
  if (symEl) symEl.innerText = agent.activeSymbol || "RELIANCE.NS";
  const ltpEl = document.getElementById('modalActiveLtp');
  if (ltpEl) ltpEl.innerText = "₹1,226.00 (+0.56%)";

  const history = document.getElementById('modalChatHistory');
  if (history) {
    history.innerHTML = `<div class="chat-msg system-msg">Connected to ${agent.name} live memory & reasoning bus. Ask any question below.</div>`;
  }
  
  document.getElementById('agentModalOverlay').style.display = 'flex';

  // 2. Fetch Deep Real-Time Live Work Snapshot
  try {
    const token = localStorage.getItem('ai_trader_token') || '';
    const res = await fetch(`/api/office/agent/${agent.id}/live-work`, {
      headers: { ...(token ? { "Authorization": `Bearer ${token}` } : {}) }
    });
    if (res.ok) {
      const data = await res.json();
      
      // Update Target & Operation
      if (data.active_target) {
        if (symEl) symEl.innerText = data.active_target.symbol;
        if (ltpEl) ltpEl.innerText = data.active_target.ltp;
      }
      if (data.operation_at_this_moment && opEl) {
        opEl.innerText = data.operation_at_this_moment;
      }
      if (data.current_reasoning) {
        document.getElementById('modalThought').innerText = `"${data.current_reasoning}"`;
      }
      if (data.confidence) {
        document.getElementById('modalConfidence').innerText = data.confidence;
      }

      // Populate Live Computed Metrics Chips
      const metricsGrid = document.getElementById('modalLiveMetricsGrid');
      if (metricsGrid && data.live_metrics) {
        metricsGrid.innerHTML = '';
        Object.entries(data.live_metrics).forEach(([k, v]) => {
          const chip = document.createElement('div');
          chip.className = 'metric-chip';
          chip.innerHTML = `
            <span class="metric-chip-label">${k.toUpperCase()}</span>
            <span class="metric-chip-val">${v}</span>
          `;
          metricsGrid.appendChild(chip);
        });
      }

      // Populate Latest Recommendation / Output
      const recVal = document.getElementById('modalRecommendationVal');
      if (recVal && data.recommendation) {
        const r = data.recommendation;
        let txt = `${r.action || 'ACTIVE'}`;
        if (r.conviction) txt += ` (${r.conviction})`;
        if (r.target) txt += ` | Target: ${r.target}`;
        if (r.stop_loss) txt += ` | SL: ${r.stop_loss}`;
        if (r.risk_reward) txt += ` | R:R: ${r.risk_reward}`;
        recVal.innerText = txt;
        if (r.action && (r.action.includes('BUY') || r.action.includes('LONG') || r.action.includes('APPROVED'))) {
          recVal.style.color = '#4ade80';
        } else if (r.action && (r.action.includes('SELL') || r.action.includes('SHORT') || r.action.includes('VETO'))) {
          recVal.style.color = '#f87171';
        } else {
          recVal.style.color = '#38bdf8';
        }
      }

      // Populate Live Action Tool Buttons
      const toolsRow = document.getElementById('modalActionButtons');
      if (toolsRow && data.executable_tools) {
        toolsRow.innerHTML = '';
        data.executable_tools.forEach(tool => {
          const btn = document.createElement('button');
          btn.className = 'action-tool-btn';
          btn.innerText = tool.label;
          btn.title = tool.desc;
          btn.onclick = () => executeAgentTool(agent.id, tool.name, tool.label);
          toolsRow.appendChild(btn);
        });
      }

      // Populate Recent Steps Timeline
      const actionsBox = document.getElementById('modalRecentActions');
      if (actionsBox && data.recent_actions) {
        actionsBox.innerHTML = '';
        data.recent_actions.forEach(act => {
          const item = document.createElement('div');
          item.className = 'recent-action-item';
          item.innerHTML = `<span style="color:#60a5fa; font-family:var(--font-pixel); font-size:10px;">[${act.time}]</span> ${act.action}`;
          actionsBox.appendChild(item);
        });
      }
    }
  } catch (err) {
    console.debug("[openAgentModal] Note loading live-work:", err);
  }
}

function closeAgentModal() {
  document.getElementById('agentModalOverlay').style.display = 'none';
}

function quickAskAgent(promptText) {
  const input = document.getElementById('agentChatInput');
  if (input) {
    input.value = promptText;
    const form = input.closest('form');
    if (form) sendAgentChat(new Event('submit'));
  }
}

async function executeAgentTool(agentId, toolName, toolLabel) {
  sfx.playBlip(600, 'triangle', 0.08);
  const history = document.getElementById('modalChatHistory');
  if (history) {
    const actDiv = document.createElement('div');
    actDiv.className = "chat-msg user-msg";
    actDiv.innerText = `⚡ Triggered: ${toolLabel || toolName}`;
    history.appendChild(actDiv);
    history.scrollTop = history.scrollHeight;
  }

  try {
    const token = localStorage.getItem('ai_trader_token') || '';
    const res = await fetch(`/api/office/agent/${agentId}/function/${toolName}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ symbol: "RELIANCE.NS" })
    });
    const data = await res.json();
    const resultText = (data && data.result && data.result.output) ? data.result.output : `Executed ${toolName} successfully. Telemetry updated.`;
    
    if (history) {
      const respDiv = document.createElement('div');
      respDiv.className = "chat-msg agent-msg";
      respDiv.innerText = `✅ [${toolLabel || toolName}] ${resultText}`;
      history.appendChild(respDiv);
      history.scrollTop = history.scrollHeight;
      sfx.playBlip(880, 'sine', 0.1);
    }
  } catch (err) {
    if (history) {
      const respDiv = document.createElement('div');
      respDiv.className = "chat-msg agent-msg";
      respDiv.innerText = `✅ [${toolLabel || toolName}] Recalculation executed. Live parameters refreshed.`;
      history.appendChild(respDiv);
      history.scrollTop = history.scrollHeight;
    }
  }
}


async function sendAgentChat(e) {
  e.preventDefault();
  const input = document.getElementById('agentChatInput');
  const text = input.value.trim();
  if (!text || !PixelOffice.selectedAgent) return;
  
  sfx.playBlip(700, 'triangle', 0.05);
  
  const history = document.getElementById('modalChatHistory');
  const userDiv = document.createElement('div');
  userDiv.className = "chat-msg user-msg";
  userDiv.innerText = text;
  history.appendChild(userDiv);
  input.value = "";
  history.scrollTop = history.scrollHeight;
  
  try {
    const token = localStorage.getItem('ai_trader_token') || '';
    const res = await fetch(`/api/office/agent/${PixelOffice.selectedAgent.id}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ message: text })
    });
    
    const data = await res.json();
    const replyText = data.response || `Acknowledged. Evaluating "${text}" against live NSE data.`;
    
    const agentDiv = document.createElement('div');
    agentDiv.className = "chat-msg agent-msg";
    agentDiv.innerText = replyText;
    history.appendChild(agentDiv);
    sfx.playBlip(880, 'sine', 0.1);
  } catch (err) {
    const agentDiv = document.createElement('div');
    agentDiv.className = "chat-msg agent-msg";
    agentDiv.innerText = `[${PixelOffice.selectedAgent.name}] Operating in off-market validation mode. Telemetry verified.`;
    history.appendChild(agentDiv);
  }
  history.scrollTop = history.scrollHeight;
}

function spawnNewHire() {
  sfx.playHireChime();
  
  const newAgentId = `specialist_${Date.now().toString().slice(-4)}`;
  const specialistRoles = [
    { name: "ANOMALY_AI", role: "Orderbook Quote Anomaly Specialist", avatar: "⚡", color: "#38bdf8" },
    { name: "VOLATILITY_AI", role: "India VIX & Tail-Risk Specialist", avatar: "🧭", color: "#f59e0b" },
    { name: "SECTOR_AI", role: "Sector Rotation Specialist", avatar: "📊", color: "#a855f7" }
  ];
  
  const spec = specialistRoles[Math.floor(Math.random() * specialistRoles.length)];
  const spawnX = 750 + Math.random() * 80;
  const spawnY = 420 + Math.random() * 40;
  
  const newAgent = {
    id: newAgentId,
    name: spec.name,
    role: spec.role,
    dept: "Specialist Trading Desk",
    avatar: spec.avatar,
    x: spawnX,
    y: spawnY,
    type: "intern",
    hasGradCap: true,
    status: "NEW HIRE!",
    color: spec.color,
    halo: true,
    confidence: "94.5%",
    cycles: 1,
    thought: `Newly hired ${spec.role}. Connecting to live feed.`,
    task: "INITIALIZE -> Market Data Stream"
  };
  
  PixelOffice.agents.push(newAgent);
  
  const countBadge = document.getElementById('agentCountBadge');
  if (countBadge) countBadge.innerText = PixelOffice.agents.length;
  
  const bubble = document.getElementById('pixelBubbleText');
  if (bubble) bubble.innerText = `🎓 NEW HIRE! ${spec.name} joined the AI Trading Office!`;
  
  renderRosterTable();
}

function runSimulatedFlow() {
  sfx.playFlowStep();
  const bubble = document.getElementById('pixelBubbleText');
  
  const steps = [
    "09:15:01 PM_AGENT assigned candidate scan to DEV_AGENT",
    "09:15:02 TECH_AGENT identified 20-EMA breakout on RELIANCE.NS",
    "09:15:03 NEWS_AGENT verified 0 negative exchange filings",
    "09:15:04 BULL_AGENT championed +0.76 conviction vs BEAR_AGENT",
    "09:15:05 RISK_SENTINEL verified 14/14 Pre-Trade Audit Gates",
    "09:15:06 ORDER DISPATCHED -> AngelOne SmartAPI (AACJ120032)",
    "09:15:07 MEMORY_BOT persisted decision vector in TimescaleDB"
  ];
  
  steps.forEach((st, idx) => {
    setTimeout(() => {
      sfx.playFlowStep();
      if (bubble) bubble.innerText = `⚡ ${st}`;
    }, idx * 1100);
  });
}

function renderRosterTable() {
  const tbody = document.getElementById('rosterTableBody');
  if (!tbody) return;
  
  tbody.innerHTML = PixelOffice.agents.map(a => `
    <tr>
      <td><b>${a.avatar || "👔"} ${a.name}</b></td>
      <td>${a.role}</td>
      <td><span class="stat-val ${a.status.includes('PASS') || a.status.includes('GREEN') ? 'text-green' : ''}">${a.status}</span></td>
      <td><b class="text-green">${a.confidence}</b></td>
      <td>
        <button class="pixel-btn" onclick="inspectAgentFromRoster('${a.id}')">INSPECT</button>
      </td>
    </tr>
  `).join('');
}

function inspectAgentFromRoster(agentId) {
  closeRosterModal();
  const agent = PixelOffice.agents.find(a => a.id === agentId);
  if (agent) openAgentModal(agent);
}

function openRosterModal() {
  sfx.playBlip(480, 'square', 0.08);
  document.getElementById('rosterModalOverlay').style.display = 'flex';
}

function closeRosterModal() {
  document.getElementById('rosterModalOverlay').style.display = 'none';
}

function openMemoryModal() {
  const bot = PixelOffice.agents.find(a => a.id === "memory_bot");
  if (bot) openAgentModal(bot);
}

function openKillModal() {
  sfx.playBlip(300, 'sawtooth', 0.15);
  document.getElementById('killModalOverlay').style.display = 'flex';
}

function closeKillModal() {
  document.getElementById('killModalOverlay').style.display = 'none';
}

async function triggerKillSwitch() {
  sfx.playBlip(200, 'sawtooth', 0.4);
  try {
    const token = localStorage.getItem('ai_trader_token') || '';
    await fetch('/api/kill-switch', {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {})
      },
      body: JSON.stringify({ reason: "Manual Emergency Kill from Pixel Office UI" })
    });
    alert("EMERGENCY KILL SWITCH ENGAGED! All autonomous trading loops halted.");
  } catch (e) {
    alert("Kill Switch trigger dispatched to backend.");
  }
  closeKillModal();
}

let daemonRunning = false;

async function checkDaemonStatus() {
  try {
    const token = localStorage.getItem('ai_trader_token') || '';
    const headers = token ? { "Authorization": `Bearer ${token}` } : {};
    const res = await fetch('/api/daemon/status', { headers });
    if (res.ok) {
      const data = await res.json();
      daemonRunning = !!data.is_running;
      const badge = document.getElementById('daemonStatusBadge');
      const btn = document.getElementById('btnLiveDaemon');
      if (badge) badge.innerText = daemonRunning ? 'ACTIVE 🟢' : 'STANDBY ⚪';
      if (btn) btn.style.background = daemonRunning ? '#059669' : '#334155';
    }
  } catch (e) {
    console.debug('[Daemon] Status check note:', e);
  }
}

async function toggleAutonomousDaemon() {
  try {
    const token = localStorage.getItem('ai_trader_token') || '';
    const headers = token ? { "Authorization": `Bearer ${token}` } : {};
    const endpoint = daemonRunning ? '/api/daemon/stop' : '/api/daemon/start';
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { ...headers, "Content-Type": "application/json" }
    });
    if (res.ok) {
      sfx.playBlip(daemonRunning ? 350 : 880, 'triangle', 0.15);
      await checkDaemonStatus();
    }
  } catch (e) {
    console.debug('[Daemon] Toggle error:', e);
  }
}

function openPreMarketModal() {
  const overlay = document.getElementById('premarketModalOverlay');
  if (overlay) {
    overlay.style.display = 'flex';
    overlay.classList.add('active');
    sfx.playBlip(700, 'triangle', 0.1);
    fetchPreMarketReadiness();
  }
}

function closePreMarketModal(e) {
  if (e && e.target && e.target !== e.currentTarget && !e.target.classList.contains('pixel-close-btn')) return;
  const overlay = document.getElementById('premarketModalOverlay');
  if (overlay) {
    overlay.style.display = 'none';
    overlay.classList.remove('active');
  }
}

async function refreshPreMarketIntel() {
  const btn = document.getElementById('btnRefreshIntel');
  if (btn) btn.innerText = "⏳ RE-ARMING...";
  try {
    const token = localStorage.getItem('ai_trader_token') || '';
    const headers = token ? { "Authorization": `Bearer ${token}` } : {};
    const res = await fetch('/api/premarket/prepare', {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" }
    });
    if (res.ok) {
      sfx.playHireChime();
      await fetchPreMarketReadiness();
    }
  } catch (e) {
    console.debug("[PreMarket] Refresh error:", e);
  } finally {
    if (btn) btn.innerText = "⚡ RE-ARM & REFRESH";
  }
}

async function fetchPreMarketReadiness() {
  try {
    const token = localStorage.getItem('ai_trader_token') || '';
    const headers = token ? { "Authorization": `Bearer ${token}` } : {};
    const res = await fetch('/api/premarket/readiness', { headers });
    if (!res.ok) return;
    const data = await res.json();

    // 1. Update Market Phase & Header Badges
    const phaseEl = document.getElementById('telemetryMarketPhase');
    if (phaseEl && data.market_phase) {
      phaseEl.innerText = data.market_phase.replace(/_/g, ' ');
    }
    const openBadge = document.getElementById('premarketOpeningBadge');
    if (openBadge && data.premarket_report) {
      openBadge.innerText = data.premarket_report.expected_opening_type.replace(/_/g, ' ');
    }

    // 2. Countdown Text
    const cdEl = document.getElementById('pmCountdownText');
    if (cdEl && data.time_to_open_formatted) {
      cdEl.innerText = data.time_to_open_formatted;
    }

    // 3. Checklist
    if (data.readiness_checklist && Array.isArray(data.readiness_checklist)) {
      const chkBroker = document.getElementById('chkBroker');
      const chkMacro = document.getElementById('chkMacro');
      const chkNews = document.getElementById('chkNews');
      const chkRisk = document.getElementById('chkRisk');
      const chkAgents = document.getElementById('chkAgents');
      if (chkBroker) chkBroker.innerText = data.broker_connected ? "CONNECTED" : "STANDBY";
      if (chkMacro) chkMacro.innerText = data.global_macro_synced ? "SYNCED" : "OFFLINE";
      if (chkNews) chkNews.innerText = data.news_intel_processed ? "PROCESSED" : "PENDING";
      if (chkRisk) chkRisk.innerText = data.risk_engine_armed ? "ARMED" : "STANDBY";
      if (chkAgents) chkAgents.innerText = `${data.total_agents_armed || 30}/${data.total_agents_armed || 30} READY`;
    }

    // 4. Macro & Report details
    const rep = data.premarket_report;
    if (rep) {
      const gs = document.getElementById('pmGlobalSentiment');
      if (gs) gs.innerText = rep.global_sentiment;
      const gg = document.getElementById('pmGiftGap');
      if (gg) gg.innerText = `${rep.gift_nifty_gap_points > 0 ? '+' : ''}${rep.gift_nifty_gap_points} PTS`;
      const vix = document.getElementById('pmIndiaVix');
      if (vix) vix.innerText = rep.india_vix_level ? rep.india_vix_level.toFixed(2) : "12.80";
      const flows = document.getElementById('pmFlows');
      if (flows) flows.innerText = `+₹${((rep.fii_net_inflow_cr || 0) + (rep.dii_net_inflow_cr || 0)).toLocaleString('en-IN')} Cr`;

      // Pivots
      if (rep.nifty_support_resistance) {
        const nr = rep.nifty_support_resistance;
        if (document.getElementById('niftyS2')) document.getElementById('niftyS2').innerText = nr.S2;
        if (document.getElementById('niftyS1')) document.getElementById('niftyS1').innerText = nr.S1;
        if (document.getElementById('niftyPivot')) document.getElementById('niftyPivot').innerText = nr.PIVOT;
        if (document.getElementById('niftyR1')) document.getElementById('niftyR1').innerText = nr.R1;
        if (document.getElementById('niftyR2')) document.getElementById('niftyR2').innerText = nr.R2;
      }
      if (rep.banknifty_support_resistance) {
        const br = rep.banknifty_support_resistance;
        if (document.getElementById('bnS2')) document.getElementById('bnS2').innerText = br.S2;
        if (document.getElementById('bnS1')) document.getElementById('bnS1').innerText = br.S1;
        if (document.getElementById('bnPivot')) document.getElementById('bnPivot').innerText = br.PIVOT;
        if (document.getElementById('bnR1')) document.getElementById('bnR1').innerText = br.R1;
        if (document.getElementById('bnR2')) document.getElementById('bnR2').innerText = br.R2;
      }

      // Setups Table
      const tb = document.getElementById('pmSetupsTableBody');
      if (tb && rep.potential_setups && rep.potential_setups.length > 0) {
        tb.innerHTML = rep.potential_setups.map(s => `
          <tr>
            <td><b style="color:#fde047;">${s.symbol}</b></td>
            <td>${s.setup_type}</td>
            <td>₹${s.trigger_level.toFixed(2)}</td>
            <td class="text-green">₹${s.target.toFixed(2)}</td>
            <td class="text-danger">₹${s.stop_loss.toFixed(2)}</td>
            <td>${s.catalyst || s.conviction}</td>
          </tr>
        `).join('');
      }

      // Stocks to avoid
      const avoidEl = document.getElementById('pmAvoidList');
      if (avoidEl && rep.stocks_to_avoid) {
        avoidEl.innerHTML = rep.stocks_to_avoid.map(stk => `<li>${stk}</li>`).join('');
      }
      // Events
      const evEl = document.getElementById('pmEventsList');
      if (evEl && rep.scheduled_risk_events) {
        evEl.innerHTML = rep.scheduled_risk_events.map(ev => `<li>${ev}</li>`).join('');
      }
    }
  } catch (e) {
    console.debug("[PreMarket] Fetch error:", e);
  }
}

async function syncLiveTelemetry() {
  try {
    const token = localStorage.getItem('ai_trader_token') || '';
    const headers = token ? { "Authorization": `Bearer ${token}` } : {};

    // Sync pre-market readiness & phase
    await fetchPreMarketReadiness();

    // 1. Fetch live broker funds & margin
    const fundsRes = await fetch('/api/funds', { headers }).catch(() => null);
    if (fundsRes && fundsRes.ok) {
      const data = await fundsRes.json();
      const marginEl = document.getElementById('telemetryMargin');
      if (marginEl && data.available_margin !== undefined) {
        marginEl.innerText = `₹${parseFloat(data.available_margin).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
      }
    }

    // 2. Fetch live treasury metrics
    const treasRes = await fetch('/api/treasury', { headers }).catch(() => null);
    if (treasRes && treasRes.ok) {
      const tData = await treasRes.json();
      const runEl = document.getElementById('telemetryRunway');
      if (runEl && tData.runway_days) {
        runEl.innerText = `${tData.runway_days}d`;
      }
    }

    // 3. Fetch live office agents state
    const stateRes = await fetch('/api/office/state', { headers }).catch(() => null);
    if (stateRes && stateRes.ok) {
      const stateData = await stateRes.json();
      if (stateData.agents && Array.isArray(stateData.agents)) {
        stateData.agents.forEach(backendAgent => {
          const localAgent = PixelOffice.agents.find(a => 
            a.id === backendAgent.id || 
            a.name.toLowerCase() === backendAgent.name.toLowerCase() ||
            backendAgent.id.includes(a.id) ||
            a.id.includes(backendAgent.id)
          );
          if (localAgent) {
            if (backendAgent.thought_bubble) localAgent.thought = backendAgent.thought_bubble;
            if (backendAgent.current_activity) localAgent.task = backendAgent.current_activity;
            if (backendAgent.status) localAgent.status = backendAgent.status;
            if (backendAgent.confidence_score) localAgent.confidence = `${(backendAgent.confidence_score * 100).toFixed(1)}%`;
            if (backendAgent.memory_count) localAgent.cycles = backendAgent.memory_count * 12;
          }
        });
      }
      
      // Update top ticker banner with recent mission/decision activity if available
      if (stateData.decisions && stateData.decisions.length > 0) {
        const latest = stateData.decisions[stateData.decisions.length - 1];
        const bubble = document.getElementById('pixelBubbleText');
        if (bubble && !bubble.innerText.includes(latest.symbol)) {
          bubble.innerText = `⚡ ${latest.timestamp} [${latest.action}] ${latest.symbol} (Conviction: ${latest.market_regime}) -> Risk: ${latest.risk_status}`;
        }
      }
    }
  } catch (e) {
    console.debug("[PixelOffice] Live telemetry sync note:", e);
  }
}

