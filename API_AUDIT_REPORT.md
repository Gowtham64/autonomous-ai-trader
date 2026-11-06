# Autonomous AI Trader — API Audit Report

## 1. Endpoint Inventory & Verification Status

All endpoints were tested live against the Render production deployment (`https://autonomous-ai-trader.onrender.com`).

| Method | Endpoint | Auth Required | Status Code | Response Payload Size | Verified Functionality |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **GET** | `/api/performance` | No | `200 OK` | ~4.8 KB | Live equity, realized/unrealized P&L, today's trade count, drawdown |
| **GET** | `/api/positions` | Yes | `200 OK` | ~1.7 KB | Active broker positions, mark prices, SL/TP brackets, age |
| **GET** | `/api/orders` | No | `200 OK` | ~5.6 KB | Resting broker orders and today's completed trade journal |
| **GET** | `/api/evaluation/status` | No | `200 OK` | ~1.4 KB | 3-Day evaluation progress %, elapsed runtime, acceptance criteria |
| **GET** | `/api/market/quotes` | No | `200 OK` | ~1.6 KB | Real-time prices from Delta Exchange (BTC, ETH, SOL, XRP, DOGE) |
| **GET** | `/api/market/candles` | No | `200 OK` | ~7.4 KB | Historical candles with EMA 20, EMA 50, and ATR 14 overlays |
| **GET** | `/api/market/trades` | No | `200 OK` | ~1.2 KB | Live trade tape with side, price, size, and timestamp |
| **GET** | `/api/office/decisions` | No | `200 OK` | ~2.2 KB | Recent agent consensus, strategy thesis, risk approvals |
| **GET** | `/api/office/agent-actions` | No | `200 OK` | ~32 KB | Full agent telemetry stream with multi-agent filters |
| **GET** | `/api/events` | No | `200 OK` | ~12 KB | Realtime event bus pub/sub log buffer |
| **POST** | `/api/token` | No | `200 OK` | ~0.3 KB | OAuth2 password flow issuing verified JWT access tokens |
| **GET** | `/health` | No | `200 OK` | ~0.1 KB | Healthcheck endpoint reporting application state |

---

## 2. Security & Validation Controls
- **Input Validation**: Handled via Pydantic schemas enforcing strict typing, bounds checking, and schema compliance.
- **Sanitization**: Path traversal protections applied to file downloads and report generation endpoints.
- **Authentication**: JWT Bearer token authentication validated with HMAC-SHA256 signature verification.
- **Error Handling**: Custom HTTP exception handlers return JSON errors without leaking backend stack traces.
