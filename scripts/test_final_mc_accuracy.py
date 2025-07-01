#!/usr/bin/env python3
"""
Final test for market cap accuracy with correct supply assumptions
"""

import asyncio
import os
import sys
from decimal import Decimal

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.mc_calculator import calculate_market_cap
from src.lib.amm_price import get_amm_price
from src.lib.helius_supply import get_token_supply_at_slot

# Test tokens with expected values
TEST_TOKENS = {
    "fakeout": {
        "mint": "GuFK1iRQPCSRxPxWhw94SrDtLYaf7oDT68uuDDpjpump",
        "expected_supply": 1_000_000_000,  # 1B tokens (typical for Solana)
        "expected_price": 0.000063,  # $63k MC / 1B supply
        "expected_mc": 63_000,
        "tolerance": 0.1
    },
    "RDMP": {
        "mint": "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop",
        "expected_supply": 1_000_000_000,  # 1B tokens (actual supply from chain)
        "expected_price": 0.0024,  # $2.4M MC / 1B supply
        "expected_mc": 2_400_000,
        "tolerance": 0.1
    }
}


async def main():
    """Test market cap calculation accuracy"""
    print("=== Market Cap Accuracy Test ===\n")
    
    results = {"passed": 0, "failed": 0}
    
    for token_name, token_data in TEST_TOKENS.items():
        mint = token_data["mint"]
        print(f"{token_name} ({mint[:8]}...):")
        
        # Get actual supply
        supply = await get_token_supply_at_slot(mint, None)
        if supply:
            print(f"  Supply: {supply:,.0f} (expected: {token_data['expected_supply']:,.0f})")
            supply_diff = abs(float(supply) - token_data['expected_supply']) / token_data['expected_supply']
            if supply_diff > 0.01:  # 1% tolerance for supply
                print(f"  ⚠️  Supply differs by {supply_diff*100:.1f}%")
        else:
            print(f"  ❌ Could not fetch supply")
            results["failed"] += 1
            continue
        
        # Get AMM price
        price_result = await get_amm_price(mint, "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
        if price_result:
            price, source, tvl = price_result
            print(f"  Price: ${float(price):.8f} from {source}")
            print(f"  TVL: ${tvl:,.0f}")
            
            # Calculate market cap
            market_cap = float(supply) * float(price)
            print(f"  Market Cap: ${market_cap:,.0f}")
            
            # Check accuracy
            expected_mc = token_data["expected_mc"]
            diff_pct = abs(market_cap - expected_mc) / expected_mc
            
            if diff_pct <= token_data["tolerance"]:
                print(f"  ✅ PASS: Within {diff_pct*100:.1f}% of expected ${expected_mc:,.0f}")
                results["passed"] += 1
            else:
                print(f"  ❌ FAIL: {diff_pct*100:.1f}% off from expected ${expected_mc:,.0f}")
                results["failed"] += 1
                
            # Check confidence
            if "low" in source or "medium" in source:
                print(f"  ⚠️  Using {source} confidence source")
        else:
            print(f"  ❌ Could not get AMM price")
            results["failed"] += 1
        
        print()
    
    # Also test via MC calculator
    print("\n=== Testing via MC Calculator ===")
    
    for token_name, token_data in TEST_TOKENS.items():
        mint = token_data["mint"]
        print(f"\n{token_name}:")
        
        result = await calculate_market_cap(mint, use_cache=False)
        
        if result.value:
            print(f"  Market Cap: ${result.value:,.0f}")
            print(f"  Confidence: {result.confidence}")
            print(f"  Source: {result.source}")
            
            expected = token_data["expected_mc"]
            diff_pct = abs(result.value - expected) / expected
            
            if diff_pct <= token_data["tolerance"] and result.confidence == "high":
                print(f"  ✅ PASS: High confidence, within {diff_pct*100:.1f}%")
            else:
                print(f"  ❌ FAIL: {result.confidence} confidence, {diff_pct*100:.1f}% off")
        else:
            print(f"  ❌ No market cap available")
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    
    if results['failed'] == 0:
        print("\n✅ All tests passed! Market cap accuracy is within ±10%")
    else:
        print(f"\n❌ {results['failed']} tests failed")


if __name__ == "__main__":
    if not os.getenv("HELIUS_KEY"):
        print("Error: HELIUS_KEY environment variable not set")
        sys.exit(1)
    
    asyncio.run(main()) 