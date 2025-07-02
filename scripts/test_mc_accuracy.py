#!/usr/bin/env python3
"""
Test market cap accuracy for specific trades
"""

import asyncio
import os
import sys
from decimal import Decimal

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.blockchain_fetcher_v3 import BlockchainFetcherV3
from src.api.wallet_analytics_api_v3 import _enrich_trades_with_market_cap
from src.lib.mc_calculator import calculate_market_cap

# Expected trades and values from WAL-511 spec
EXPECTED_TRADES = {
    "fakeout": {
        "mint": "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump",
        "symbol": "fakeout",
        "expected_mc": 63000,  # $63k
        "tolerance": 0.1
    },
    "RDMP": {
        "mint": "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop", 
        "symbol": "RDMP",
        "expected_mc": 2400000,  # $2.4M
        "tolerance": 0.1
    }
}

WALLET_ADDRESS = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"


async def test_direct_mc_calculation():
    """Test direct market cap calculation for tokens"""
    print("\n=== Direct Market Cap Calculation ===")
    
    for token_name, token_data in EXPECTED_TRADES.items():
        mint = token_data["mint"]
        print(f"\n{token_name} ({mint[:8]}...):")
        
        # Calculate market cap directly
        result = await calculate_market_cap(mint, use_cache=False)
        
        if result.value:
            print(f"  Market Cap: ${result.value:,.0f}")
            print(f"  Confidence: {result.confidence}")
            print(f"  Source: {result.source}")
            if result.supply:
                print(f"  Supply: {result.supply:,.0f}")
            if result.price:
                print(f"  Price: ${result.price:.8f}")
            
            # Check accuracy
            expected = token_data["expected_mc"]
            diff_pct = abs(result.value - expected) / expected
            
            if diff_pct <= token_data["tolerance"]:
                print(f"  ✅ Within tolerance: {diff_pct*100:.1f}% deviation")
            else:
                print(f"  ❌ Outside tolerance: {diff_pct*100:.1f}% deviation")
                print(f"     Expected: ${expected:,.0f}")
        else:
            print(f"  ❌ No market cap available")
            print(f"  Confidence: {result.confidence}")


async def test_enriched_trades():
    """Test market cap enrichment in actual trades"""
    print("\n\n=== Trade Enrichment Test ===")
    
    # Fetch trades for the wallet
    print(f"Fetching trades for {WALLET_ADDRESS}...")
    async with BlockchainFetcherV3(skip_pricing=True) as fetcher:
        result = await fetcher.fetch_wallet_trades(WALLET_ADDRESS)
    
    # Enrich with market cap data
    trades = await _enrich_trades_with_market_cap(result.get("trades", []))
    
    # Find trades for our test tokens
    for token_name, token_data in EXPECTED_TRADES.items():
        mint = token_data["mint"]
        print(f"\n{token_name} trades:")
        
        count = 0
        for trade in trades:
            token_in_mint = trade.get("token_in", {}).get("mint", "")
            token_out_mint = trade.get("token_out", {}).get("mint", "")
            
            if token_in_mint == mint or token_out_mint == mint:
                count += 1
                action = trade.get("action")
                
                # Get market cap data
                if action == "buy":
                    mc_data = trade.get("token_out", {}).get("market_cap", {})
                else:
                    mc_data = trade.get("token_in", {}).get("market_cap", {})
                
                mc_value = mc_data.get("market_cap", 0)
                confidence = mc_data.get("confidence", "unavailable")
                
                print(f"  Trade {count} ({action}):")
                print(f"    Market Cap: ${mc_value:,.0f}")
                print(f"    Confidence: {confidence}")
                
                if mc_value > 0:
                    # Check accuracy
                    expected = token_data["expected_mc"]
                    diff_pct = abs(mc_value - expected) / expected
                    
                    if diff_pct <= token_data["tolerance"]:
                        print(f"    ✅ Within tolerance: {diff_pct*100:.1f}% deviation")
                    else:
                        print(f"    ❌ Outside tolerance: {diff_pct*100:.1f}% deviation")
                
                # Only show first few trades
                if count >= 3:
                    break


async def main():
    """Run all tests"""
    if not os.getenv("HELIUS_KEY"):
        print("Error: HELIUS_KEY environment variable not set")
        return
    
    await test_direct_mc_calculation()
    await test_enriched_trades()


if __name__ == "__main__":
    asyncio.run(main()) 