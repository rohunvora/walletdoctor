#!/usr/bin/env python3
"""
Debug script for the six test trades (2 fakeout, 4 RDMP)
"""

import asyncio
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3
from src.lib.amm_price import get_amm_price
from src.lib.helius_supply import get_token_supply_at_slot
from src.lib.mc_calculator import calculate_market_cap
import aiohttp

# Test trades
TEST_TRADES = [
    # fakeout trades
    {
        "signature": "5vmh4yHxtEsmXhMw6AJ7XmXMfJGF4UxJoKWqWPP6fnLwHzaaTHAXyK4AGyt2cdSTsyhZpVU9YXxvwfqMN96Shozx",
        "token": "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump",
        "symbol": "fakeout",
        "action": "buy",
        "expected_mc": 63000
    },
    {
        "signature": "5kvb9zhEq4EhVjVi1wFQnUVeZtCEUeGKYp4rpsH9tizGo6X6UGESCG1FX9R2x9vY4aiJ1TJZGn26RXcwGUv8UCGN",
        "token": "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump", 
        "symbol": "fakeout",
        "action": "sell",
        "expected_mc": 63000
    },
    # RDMP trades
    {
        "signature": "2UzD4Y7KTDE88eyc28Fkk4gVyubVaFoj5R4v6c5kKeuFMnVd7ykRoQcxN87FztMEP7x8CQzbec69foByVaaKQjGX",
        "token": "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop",
        "symbol": "RDMP",
        "action": "buy",
        "expected_mc": 2400000
    },
    {
        "signature": "5Wg7SjDEWSCVMMZubLuiUxAQCLUzruVudEd7fr9UBwxza6fPGJ1PUoNrxtfVJFdJ4aXvX4vVX85FnKJp7aTMffv2",
        "token": "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop",
        "symbol": "RDMP",
        "action": "sell",
        "expected_mc": 5100000
    },
    {
        "signature": "48WRpGY87gBVRuZNhYUcKsCJztjrDfNDaMxrdnoUwi8S289kSAT6voSGy9V655Pzf3iGKHH372WV4zNmY4p2Qg2C",
        "token": "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop",
        "symbol": "RDMP",
        "action": "sell",
        "expected_mc": 4700000
    },
    {
        "signature": "khjqstXY7ZvozGm5cmh6anLwkXwoQR5p4oKyy9YnjVMxRLWterW1Pz8Re9MwSgpKpLBENrdYomCdBtNnEvsXpb9",
        "token": "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop",
        "symbol": "RDMP",
        "action": "sell",
        "expected_mc": 2500000
    }
]


async def get_transaction_slot(signature: str) -> int:
    """Get slot for a transaction signature"""
    url = f"https://mainnet.helius-rpc.com/?api-key={os.getenv('HELIUS_KEY')}"
    
    async with aiohttp.ClientSession() as session:
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [signature, {"maxSupportedTransactionVersion": 0}]
        }
        
        async with session.post(url, json=body) as resp:
            data = await resp.json()
            if "result" in data and data["result"]:
                return data["result"]["slot"]
    return None


async def debug_trade(trade: dict, index: int):
    """Debug a single trade with all details"""
    print(f"\n{'='*80}")
    print(f"Trade #{index + 1}: {trade['symbol']} {trade['action'].upper()}")
    print(f"Signature: {trade['signature']}")
    
    # Get slot
    slot = await get_transaction_slot(trade['signature'])
    if not slot:
        print("ERROR: Could not fetch slot")
        return
        
    print(f"Slot: {slot}")
    print(f"Token: {trade['token']}")
    
    # Get supply
    supply = await get_token_supply_at_slot(trade['token'], slot)
    if supply:
        print(f"Supply: {supply:,.0f}")
    else:
        print("Supply: Failed to fetch")
        
    # Get AMM price
    price_result = await get_amm_price(trade['token'], slot=slot)
    if price_result:
        price, source, tvl = price_result
        print(f"AMM Price: ${float(price):.8f}")
        print(f"Price Source: {source}")
        print(f"Pool TVL: ${tvl:,.0f}")
        
        # Calculate market cap
        if supply:
            mc = float(supply) * float(price)
            print(f"Calculated MC: ${mc:,.0f}")
            
            # Show accuracy
            expected = trade['expected_mc']
            deviation = abs(mc - expected) / expected * 100
            print(f"Expected MC: ${expected:,.0f}")
            print(f"Deviation: {deviation:.1f}%")
    else:
        print("AMM Price: Failed to fetch")
        
    # Also get MC via calculator for confidence
    calc_result = await calculate_market_cap(trade['token'], slot=slot, use_cache=False)
    if calc_result.value:
        print(f"\nVia Calculator:")
        print(f"  Market Cap: ${calc_result.value:,.0f}")
        print(f"  Confidence: {calc_result.confidence}")
        print(f"  Source: {calc_result.source}")


async def main():
    """Debug all six test trades"""
    print("WalletDoctor P5 - Six Test Trades Debug Trace")
    print("Wallet: 3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2")
    print(f"Timestamp: {os.popen('date').read().strip()}")
    
    for i, trade in enumerate(TEST_TRADES):
        await debug_trade(trade, i)
    
    print(f"\n{'='*80}")
    print("Debug trace complete.")


if __name__ == "__main__":
    if not os.getenv("HELIUS_KEY"):
        print("Error: HELIUS_KEY environment variable not set")
        sys.exit(1)
    
    asyncio.run(main()) 