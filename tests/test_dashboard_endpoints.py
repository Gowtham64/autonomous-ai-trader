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

        # 4. Test Health
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        hdata = health_resp.json()
        assert hdata["status"] == "healthy"
        assert hdata["trading_mode"] == "PAPER"
        print("Health status verified: healthy, mode=PAPER")

if __name__ == "__main__":
    asyncio.run(test_dashboard_static_and_evaluation())
    print("ALL DASHBOARD ENDPOINT TESTS PASSED!")
