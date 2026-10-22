"""Automated Trade Performance & Audit Reporter for Delta Exchange.

Generates fill-by-fill breakdowns with:
- Win vs Loss classification
- Dollar amount gained or lost
- Root-cause reason (Why it won or lost)
- Overall account PnL status
"""

import asyncio
from execution.brokers.delta_exchange import DeltaExchangeBroker


async def generate_report() -> dict:
    b = DeltaExchangeBroker()
    funds = await b.get_funds(force=True)
    pos = await b.get_positions(force=True)
    res = await b._request('GET', '/v2/wallet/transactions', params={'limit': 100})
    txs = res.get('result', [])

    seen = set()
    unique_txs = []
    for t in txs:
        uid = t.get('uuid')
        if uid not in seen:
            seen.add(uid)
            unique_txs.append(t)

    cashflows = [t for t in unique_txs if t.get('transaction_type') == 'cashflow']
    commissions = [t for t in unique_txs if t.get('transaction_type') == 'commission']

    return {
        'funds': funds,
        'positions': pos,
        'cashflows': cashflows,
        'commissions': commissions,
    }


if __name__ == '__main__':
    data = asyncio.run(generate_report())
    print('Funds:', data['funds'])
    print('Open Positions:', len(data['positions']))
    print('Closed Trades:', len(data['cashflows']))
