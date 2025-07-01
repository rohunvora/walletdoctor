#!/usr/bin/env python3
"""
Test that RDMP trades show accurate declining market caps at different slots
"""

import pytest
import os
from decimal import Decimal

# Skip all tests if no Helius key
pytestmark = pytest.mark.skipif(
    not os.getenv("HELIUS_KEY"),
    reason="HELIUS_KEY environment variable not set"
)

from src.lib.mc_calculator import calculate_market_cap
from src.lib.amm_price import get_amm_price

# RDMP token mint
RDMP_MINT = "1HE8MZKhpbJiNvjJTrXdV395qEmPEqJme6P5DLBboop"

# Test data from actual trades
RDMP_TRADES = [
    {
        "signature": "2UzD4Y7KTDE88eyc28Fkk4gVyubVaFoj5R4v6c5kKeuFMnVd7ykRoQcxN87FztMEP7x8CQzbec69foByVaaKQjGX",
        "slot": 347318465,
        "action": "buy",
        "expected_mc": 2400000,  # $2.4M (this is the base case)
        "tolerance": 0.1
    },
    {
        "signature": "5Wg7SjDEWSCVMMZubLuiUxAQCLUzruVudEd7fr9UBwxza6fPGJ1PUoNrxtfVJFdJ4aXvX4vVX85FnKJp7aTMffv2",
        "slot": 347397782,
        "action": "sell",
        "expected_mc": 5100000,  # $5.1M
        "tolerance": 0.1
    },
    {
        "signature": "48WRpGY87gBVRuZNhYUcKsCJztjrDfNDaMxrdnoUwi8S289kSAT6voSGy9V655Pzf3iGKHH372WV4zNmY4p2Qg2C",
        "slot": 347398239,
        "action": "sell",
        "expected_mc": 4700000,  # $4.7M
        "tolerance": 0.1
    },
    {
        "signature": "khjqstXY7ZvozGm5cmh6anLwkXwoQR5p4oKyy9YnjVMxRLWterW1Pz8Re9MwSgpKpLBENrdYomCdBtNnEvsXpb9",
        "slot": 347420352,
        "action": "sell",
        "expected_mc": 2500000,  # $2.5M
        "tolerance": 0.1
    }
]


@pytest.mark.asyncio
async def test_rdmp_price_varies_by_slot():
    """Test that RDMP price changes based on slot"""
    seen_prices = set()
    
    for trade in RDMP_TRADES:
        slot = trade["slot"]
        
        # Get AMM price at slot
        price_result = await get_amm_price(RDMP_MINT, slot=slot)
        assert price_result is not None, f"No price for RDMP at slot {slot}"
        
        price, source, tvl = price_result
        price_float = float(price)
        
        # Should be from Raydium
        assert source == "raydium", f"Expected raydium source, got {source}"
        
        # TVL should be reasonable
        assert tvl > 100000, f"TVL too low: ${tvl}"
        
        # Price should be unique for each slot range
        seen_prices.add(round(price_float, 8))
        
        print(f"Slot {slot}: price=${price_float:.8f}, TVL=${tvl:,.0f}")
    
    # Should see different prices for different slots
    assert len(seen_prices) >= 3, f"Expected at least 3 different prices, got {len(seen_prices)}"


@pytest.mark.asyncio
async def test_rdmp_market_caps_declining():
    """Test that RDMP market caps show declining trend"""
    results = []
    
    for trade in RDMP_TRADES:
        slot = trade["slot"]
        expected_mc = trade["expected_mc"]
        tolerance = trade["tolerance"]
        
        # Calculate market cap at slot
        result = await calculate_market_cap(RDMP_MINT, slot=slot, use_cache=False)
        
        assert result.value is not None, f"No MC for RDMP at slot {slot}"
        assert result.confidence == "high", f"Expected high confidence, got {result.confidence}"
        
        mc = result.value
        deviation = abs(mc - expected_mc) / expected_mc
        
        print(f"\nTrade: {trade['action']} at slot {slot}")
        print(f"  Expected MC: ${expected_mc:,.0f}")
        print(f"  Actual MC: ${mc:,.0f}")
        print(f"  Deviation: {deviation * 100:.1f}%")
        print(f"  Source: {result.source}")
        
        results.append({
            "slot": slot,
            "mc": mc,
            "expected": expected_mc,
            "deviation": deviation
        })
        
        # Check accuracy
        assert deviation <= tolerance, (
            f"MC deviation {deviation * 100:.1f}% exceeds tolerance {tolerance * 100}% "
            f"at slot {slot}"
        )
    
    # Verify the declining trend (5.1M → 4.7M → 2.5M)
    # Skip first buy trade in trend check
    sell_mcs = [r["mc"] for r in results if r["slot"] > 347318465]
    
    # First sell should be highest
    assert sell_mcs[0] > sell_mcs[1], "MC should decline from first to second sell"
    assert sell_mcs[1] > sell_mcs[2], "MC should decline from second to third sell"
    
    print(f"\nMarket cap trend: ${sell_mcs[0]:,.0f} → ${sell_mcs[1]:,.0f} → ${sell_mcs[2]:,.0f}")


@pytest.mark.asyncio
async def test_rdmp_confidence_always_high():
    """Test that all RDMP trades have high confidence"""
    for trade in RDMP_TRADES:
        slot = trade["slot"]
        
        # Calculate market cap
        result = await calculate_market_cap(RDMP_MINT, slot=slot, use_cache=False)
        
        assert result.confidence == "high", (
            f"Expected high confidence for RDMP at slot {slot}, got {result.confidence}"
        )
        
        # Should use Helius + Raydium
        assert result.source is not None, f"Source should not be None for slot {slot}"
        assert "helius" in result.source.lower(), f"Expected Helius in source: {result.source}"
        assert "raydium" in result.source.lower(), f"Expected Raydium in source: {result.source}"


if __name__ == "__main__":
    import asyncio
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    async def run_tests():
        print("Testing RDMP price variation by slot...")
        await test_rdmp_price_varies_by_slot()
        
        print("\n" + "="*60)
        print("Testing RDMP market caps declining...")
        await test_rdmp_market_caps_declining()
        
        print("\n" + "="*60)
        print("Testing RDMP confidence levels...")
        await test_rdmp_confidence_always_high()
        
        print("\n✅ All tests passed!")
    
    asyncio.run(run_tests()) 