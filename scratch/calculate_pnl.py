import asyncio
from execution.brokers.delta_exchange import DeltaExchangeBroker

async def main():
    d = DeltaExchangeBroker()
    fills_res = await d._request("GET", "/v2/fills?limit=100")
    fills = fills_res.get("result", [])
    
    total_gains = 0.0
    total_losses = 0.0
    total_fees = 0.0
    closed_trades = []

    for f in fills:
        meta = f.get("meta_data", {})
        pnl_raw = meta.get("new_position", {}).get("realized_pnl")
        comm = float(f.get("commission") or 0.0)
        total_fees += comm
        if pnl_raw is not None:
            pnl = float(pnl_raw)
            if pnl > 0:
                total_gains += pnl
            elif pnl < 0:
                total_losses += abs(pnl)
            closed_trades.append({
                "time": f.get("created_at"),
                "symbol": f.get("product_symbol"),
                "side": f.get("side"),
                "size": f.get("size"),
                "price": f.get("price"),
                "pnl": pnl,
                "comm": comm
            })

    funds = await d.get_funds()
    positions = await d.get_positions()
    unrealized_pnl = sum(p.unrealized_pnl for p in positions)

    print("=" * 65)
    print("           DELTA EXCHANGE COMPLETE P&L AUDIT")
    print("=" * 65)
    print(f"Total Closed Trades with PnL: {len(closed_trades)}")
    print(f"Gross Gains (Winning Trades) : +${total_gains:.4f} USD")
    print(f"Gross Losses (Losing Trades) : -${total_losses:.4f} USD")
    print(f"Total Commissions / Fees     : -${total_fees:.4f} USD")
    print(f"Net Realized PnL             : ${total_gains - total_losses - total_fees:+.4f} USD")
    print(f"Current Unrealized PnL       : ${unrealized_pnl:+.4f} USD")
    print(f"Starting Baseline Capital    : $9.1200 USD")
    print(f"Current Live Equity          : ${funds.get('total_capital', 0.0):.2f} USD")
    print("-" * 65)
    print("ALL CLOSED TRADES BREAKDOWN (Newest to Oldest):")
    for t in closed_trades:
        win_loss = "WIN 🟢" if t['pnl'] > 0 else "LOSS 🔴"
        print(f"  {t['time'][:19]} | {t['symbol']:<9} | {t['side'].upper():<4} | Size: {t['size']:<3} | PnL: ${t['pnl']:+8.4f} | Fee: ${t['comm']:.4f} | {win_loss}")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(main())
