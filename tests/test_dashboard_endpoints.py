import asyncio
try:
    import pytest
except ImportError:
    pytest = None
from httpx import AsyncClient, ASGITransport
from apps.api.main import app

def _mark_async(fn):
    return pytest.mark.asyncio(fn) if pytest else fn

@_mark_async
async def test_dashboard_static_and_evaluation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test Root Dashboard HTML
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "AI Trading Dashboard" in resp.text
        assert "candlestickChartContainer" in resp.text

        # 2. Test Evaluation Status Endpoint
        eval_resp = await client.get("/api/evaluation/status")
        print(f"Eval status code: {eval_resp.status_code}, text: {eval_resp.text}")
        assert eval_resp.status_code == 200
        data = eval_resp.json()
        assert "evaluation_id" in data
        assert "acceptance_criteria" in data
        assert len(data["acceptance_criteria"]) > 0

        # 3. Test Candles Endpoint
        candles_resp = await client.get("/api/market/candles?symbol=BTCUSDT&interval=5m")
        assert candles_resp.status_code == 200
        cdata = candles_resp.json()
        assert "symbol" in cdata
        assert "candles" in cdata
        print(f"Candles endpoint verified: {cdata['symbol']}, count={cdata['count']}")

        # 4. Test Performance Endpoint
        perf_resp = await client.get("/api/performance")
        assert perf_resp.status_code == 200
        pdata = perf_resp.json()
        assert "metrics" in pdata
        assert "live_funds" in pdata
        print(f"Performance verified: total_trades={pdata['metrics'].get('total_trades')}, realized_pnl={pdata['metrics'].get('realized_pnl')}")

        # 5. Test Orders Endpoint (Completed trades & db orders)
        ord_resp = await client.get("/api/orders")
        assert ord_resp.status_code == 200
        odata = ord_resp.json()
        assert "completed_trades" in odata
        assert "db_orders" in odata
        print(f"Orders verified: completed_trades={len(odata['completed_trades'])}, db_orders={len(odata['db_orders'])}")

        # 6. Test Decisions Endpoint (Multi-agent debate records)
        dec_resp = await client.get("/api/office/decisions")
        assert dec_resp.status_code == 200
        ddata = dec_resp.json()
        assert "decisions" in ddata
        print(f"Decisions verified: count={len(ddata['decisions'])}")

        # 7. Test Events Endpoint (Live logs)
        ev_resp = await client.get("/api/events")
        assert ev_resp.status_code == 200
        edata = ev_resp.json()
        assert "events" in edata
        print(f"Events verified: count={len(edata['events'])}")

        # 8. Test Market Quotes Endpoint
        quotes_resp = await client.get("/api/market/quotes")
        assert quotes_resp.status_code == 200
        qdata = quotes_resp.json()
        assert "quotes" in qdata
        print(f"Quotes verified: count={len(qdata['quotes'])}")

        # 9. Test Real-Time Public Trades Tape
        trades_resp = await client.get("/api/market/trades?symbol=BTCUSDT&limit=10")
        assert trades_resp.status_code == 200
        tdata = trades_resp.json()
        assert "trades" in tdata
        print(f"Market trades tape verified: count={len(tdata['trades'])}")

        # 10. Test Health
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        hdata = health_resp.json()
        assert hdata["status"] == "healthy"
        assert hdata["trading_mode"] == "PAPER"
        print("Health status verified: healthy, mode=PAPER")

if __name__ == "__main__":
    asyncio.run(test_dashboard_static_and_evaluation())
    print("ALL DASHBOARD ENDPOINT TESTS PASSED!")
