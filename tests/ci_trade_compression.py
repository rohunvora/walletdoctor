#!/usr/bin/env python3
"""
CI test for v0.7.2-compact: Verify trade compression meets size limits

Ensures that compressed trade responses stay under 200KB for ChatGPT
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import logging
import asyncio
import json
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
MAX_RESPONSE_SIZE_KB = 200  # Target response size limit
TEST_WALLETS = [
    "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",  # Small: ~1,100 trades
    "AAXTYrQR6CHDGhJYz4uSgJ6dq7JTySTR6WyAq8QKZnF8"   # Medium: ~2,300 trades
]


async def test_compression_size_limits():
    """Test that compressed responses meet size requirements"""
    from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
    from src.lib.trade_enricher import TradeEnricher
    from src.lib.trade_compressor import TradeCompressor
    from src.lib.sol_price_fetcher import get_sol_price_usd
    
    # Check SOL price is available
    sol_price = get_sol_price_usd()
    if not sol_price:
        logger.error("SOL price unavailable - cannot test compression")
        return False
    
    all_passed = True
    
    for wallet in TEST_WALLETS:
        logger.info(f"\nTesting wallet: {wallet}")
        
        try:
            # Fetch trades
            async with BlockchainFetcherV3Fast(skip_pricing=True) as fetcher:
                result = await fetcher.fetch_wallet_trades(wallet)
            
            trades = result.get("trades", [])
            logger.info(f"  Fetched {len(trades)} trades")
            
            # Enrich trades (if feature enabled)
            if os.getenv("PRICE_ENRICH_TRADES", "false").lower() == "true":
                enricher = TradeEnricher()
                trades = await enricher.enrich_trades(trades)
                logger.info(f"  Enriched {enricher.enrichment_stats['trades_priced']} trades")
            
            # Test original format size
            original_response = {
                "wallet": wallet,
                "schema_version": "v0.7.1-trades-value",
                "signatures": result.get("signatures", []),
                "trades": trades
            }
            original_json = json.dumps(original_response)
            original_size_kb = len(original_json) / 1024
            logger.info(f"  Original size: {original_size_kb:.1f} KB")
            
            # Test compressed format
            compressor = TradeCompressor()
            compressed_response = compressor.compress_trades(trades, wallet)
            compressed_json = json.dumps(compressed_response)
            compressed_size_kb = len(compressed_json) / 1024
            
            compression_ratio = original_size_kb / compressed_size_kb if compressed_size_kb > 0 else 0
            
            logger.info(f"  Compressed size: {compressed_size_kb:.1f} KB")
            logger.info(f"  Compression ratio: {compression_ratio:.1f}x")
            
            # Check size limit
            if compressed_size_kb <= MAX_RESPONSE_SIZE_KB:
                logger.info(f"  ✅ Size check PASSED ({compressed_size_kb:.1f} KB <= {MAX_RESPONSE_SIZE_KB} KB)")
            else:
                logger.error(f"  ❌ Size check FAILED ({compressed_size_kb:.1f} KB > {MAX_RESPONSE_SIZE_KB} KB)")
                all_passed = False
            
            # Verify compression quality
            if compression_ratio < 3.0:
                logger.warning(f"  ⚠️  Compression ratio below target ({compression_ratio:.1f}x < 3.0x)")
            
            # Verify data integrity (spot check)
            if len(compressed_response["trades"]) != compressed_response["summary"]["included"]:
                logger.error("  ❌ Trade count mismatch!")
                all_passed = False
            
        except Exception as e:
            logger.error(f"  ❌ Test failed for {wallet}: {e}", exc_info=True)
            all_passed = False
    
    return all_passed


def main():
    """Main entry point"""
    # Only run if compression is enabled
    if os.getenv("TRADES_COMPACT", "false").lower() != "true":
        logger.info("TRADES_COMPACT not enabled, skipping compression test")
        return 0
    
    # Run the test
    success = asyncio.run(test_compression_size_limits())
    
    if success:
        logger.info("\n✅ Trade compression CI test PASSED")
        return 0
    else:
        logger.error("\n❌ Trade compression CI test FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 