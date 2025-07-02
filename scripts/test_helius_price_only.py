#!/usr/bin/env python3
"""
Test Helius-only pricing implementation
WAL-613: Validates that Helius swap extraction works correctly
"""

import asyncio
import os
import sys
import time
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
from src.lib.position_builder import PositionBuilder
from src.lib.unrealized_pnl_calculator import UnrealizedPnLCalculator
from src.lib.position_models import CostBasisMethod

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test wallet
TEST_WALLET = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"


async def test_helius_price_extraction():
    """Test Helius price extraction from swap transactions"""
    
    # Enable Helius-only pricing and positions
    os.environ['PRICE_HELIUS_ONLY'] = 'true'
    os.environ['POSITIONS_ENABLED'] = 'true'
    os.environ['UNREALIZED_PNL_ENABLED'] = 'true'
    
    print("=== Helius-Only Pricing Test ===")
    print(f"Wallet: {TEST_WALLET}")
    print(f"PRICE_HELIUS_ONLY: {os.getenv('PRICE_HELIUS_ONLY')}")
    print()
    
    # Fetch trades with transactions
    start_time = time.time()
    print("Fetching trades...")
    
    async with BlockchainFetcherV3Fast(skip_pricing=True) as fetcher:
        result = await fetcher.fetch_wallet_trades(TEST_WALLET)
    
    fetch_time = time.time() - start_time
    print(f"Fetch completed in {fetch_time:.2f}s")
    
    trades = result.get("trades", [])
    transactions = result.get("transactions", [])
    
    print(f"Found {len(trades)} trades")
    print(f"Found {len(transactions)} transactions")
    print()
    
    # Build positions
    print("Building positions...")
    builder = PositionBuilder(CostBasisMethod.FIFO)
    positions = builder.build_positions_from_trades(trades, TEST_WALLET)
    print(f"Built {len(positions)} positions")
    print()
    
    # Calculate unrealized P&L with Helius prices
    print("Calculating unrealized P&L with Helius prices...")
    calculator = UnrealizedPnLCalculator()
    calculator.trades = trades
    calculator.transactions = transactions
    
    start_time = time.time()
    position_pnls = await calculator.create_position_pnl_list(positions)
    price_time = time.time() - start_time
    
    print(f"Price extraction completed in {price_time:.2f}s")
    print()
    
    # Analyze results
    priced_count = 0
    unpriced_count = 0
    price_sources = {}
    
    for pnl in position_pnls:
        if pnl.current_price_usd is not None:
            priced_count += 1
            source = getattr(pnl, 'price_source', 'unknown')
            price_sources[source] = price_sources.get(source, 0) + 1
        else:
            unpriced_count += 1
    
    # Print summary
    print("=== RESULTS ===")
    print(f"Total positions: {len(position_pnls)}")
    
    if len(position_pnls) > 0:
        print(f"Priced positions: {priced_count} ({priced_count/len(position_pnls)*100:.1f}%)")
        print(f"Unpriced positions: {unpriced_count}")
    else:
        print("No positions found - check if HELIUS_KEY is valid")
    print()
    
    print("Price sources:")
    for source, count in price_sources.items():
        print(f"  {source}: {count}")
    print()
    
    # Show sample prices
    print("Sample prices extracted:")
    sample_count = 0
    for pnl in position_pnls[:10]:
        if pnl.current_price_usd is not None:
            print(f"  {pnl.position.token_symbol}: ${pnl.current_price_usd:.6f}")
            sample_count += 1
            if sample_count >= 5:
                break
    
    print()
    print(f"Total time: {fetch_time + price_time:.2f}s")
    
    # Performance check
    if price_time < 8.0:
        print("✅ Performance target met (< 8s)")
    else:
        print("❌ Performance target NOT met (< 8s)")
    
    return priced_count, unpriced_count, price_time


if __name__ == "__main__":
    asyncio.run(test_helius_price_extraction()) 