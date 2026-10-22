import asyncio
from execution.brokers.delta_exchange import DeltaExchangeBroker


async def main():
    b = DeltaExchangeBroker()
    res = await b._request('GET', '/v2/wallet/transactions', params={'limit': 100})
    txs = res.get('result', [])

    seen = set()
    unique_txs = []
    for t in txs:
        uid = t.get('uuid')
        if uid not in seen:
            seen.add(uid)
            unique_txs.append(t)

    print(f'Total Unique Transactions: {len(unique_txs)}')

    cashflows = [t for t in unique_txs if t.get('transaction_type') == 'cashflow']
    commissions = [t for t in unique_txs if t.get('transaction_type') == 'commission']

    gains = [float(t.get('amount')) for t in cashflows if float(t.get('amount')) > 0]
    losses = [float(t.get('amount')) for t in cashflows if float(t.get('amount')) < 0]

    total_gains = sum(gains)
    total_losses = sum(abs(x) for x in losses)
    total_fees = sum(abs(float(t.get('amount'))) for t in commissions)

    print(f'Total Closed Trades: {len(cashflows)}')
    print(f'Winning Trades:      {len(gains)} (Gross Gains: +${total_gains:.4f} USD)')
    print(f'Losing Trades:       {len(losses)} (Gross Losses: -${total_losses:.4f} USD)')
    print(f'Commissions/Fees:    -${total_fees:.4f} USD')
    print(f'Net Ledger Difference: ${(total_gains - total_losses - total_fees):+.4f} USD')

    print('\n=== CHRONOLOGICAL TRADE HISTORY ===')
    for t in reversed(cashflows):
        amt = float(t.get('amount'))
        sym = t.get('meta_data', {}).get('product_symbol', 'N/A')
        ts = t.get('created_at', '')[:16]
        tag = 'WIN ' if amt > 0 else 'LOSS'
        print(f'{tag} | {ts} | {sym:12s} | {amt:+.4f} USD')


if __name__ == '__main__':
    asyncio.run(main())
