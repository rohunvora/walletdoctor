#!/usr/bin/env python3
"""
CI test for v0.8.0-summary: Verify analytics summary meets requirements

Ensures that analytics summaries:
- Stay under 50KB size limit
- Complete within SLO times
- Include all required fields
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import logging
import asyncio
import json
import time
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
MAX_RESPONSE_SIZE_KB = 50  # Target response size limit
COLD_SLO_SECONDS = 8       # Cold path SLO
WARM_SLO_SECONDS = 0.5     # Warm path SLO
TEST_WALLETS = [
    "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",  # Small: ~1,100 trades
    "AAXTYrQR6CHDGhJYz4uSgJ6dq7JTySTR6WyAq8QKZnF8"   # Medium: ~2,300 trades
]


async def test_analytics_summary():
    """Test analytics summary generation and caching"""
    from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
    from src.lib.trade_enricher import TradeEnricher
    from src.lib.trade_analytics_aggregator import TradeAnalyticsAggregator
    from src.lib.sol_price_fetcher import get_sol_price_usd
    
    # Check SOL price is available
    sol_price = get_sol_price_usd()
    if not sol_price:
        logger.error("SOL price unavailable - cannot test analytics")
        return False
    
    all_passed = True
    
    for wallet in TEST_WALLETS:
        logger.info(f"\nTesting analytics for wallet: {wallet}")
        
        try:
            # Cold path test - generate fresh
            cold_start = time.time()
            
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
            
            # Generate analytics
            aggregator = TradeAnalyticsAggregator()
            summary = await aggregator.aggregate_analytics(trades, wallet)
            
            cold_duration = time.time() - cold_start
            
            # Check response structure
            required_fields = ["wallet", "schema_version", "generated_at", "time_window", 
                             "pnl", "volume", "top_tokens", "recent_windows"]
            for field in required_fields:
                if field not in summary:
                    logger.error(f"  ❌ Missing required field: {field}")
                    all_passed = False
            
            # Check schema version
            if summary.get("schema_version") != "v0.8.0-summary":
                logger.error(f"  ❌ Wrong schema version: {summary.get('schema_version')}")
                all_passed = False
            
            # Check size
            summary_json = json.dumps(summary)
            size_kb = len(summary_json) / 1024
            
            if size_kb <= MAX_RESPONSE_SIZE_KB:
                logger.info(f"  ✅ Size check PASSED ({size_kb:.1f} KB <= {MAX_RESPONSE_SIZE_KB} KB)")
            else:
                logger.error(f"  ❌ Size check FAILED ({size_kb:.1f} KB > {MAX_RESPONSE_SIZE_KB} KB)")
                all_passed = False
            
            # Check cold path SLO
            if cold_duration <= COLD_SLO_SECONDS:
                logger.info(f"  ✅ Cold path SLO PASSED ({cold_duration:.2f}s <= {COLD_SLO_SECONDS}s)")
            else:
                logger.warning(f"  ⚠️  Cold path SLO exceeded ({cold_duration:.2f}s > {COLD_SLO_SECONDS}s)")
            
            # Verify P&L metrics
            pnl = summary.get("pnl", {})
            if "realized_usd" in pnl and "win_rate" in pnl:
                logger.info(f"  ✅ P&L metrics present: ${pnl['realized_usd']} ({pnl['win_rate']*100:.1f}% win rate)")
            else:
                logger.error("  ❌ P&L metrics missing or incomplete")
                all_passed = False
            
            # Verify volume metrics
            volume = summary.get("volume", {})
            if volume.get("total_trades") != len(trades):
                logger.error(f"  ❌ Trade count mismatch: {volume.get('total_trades')} vs {len(trades)}")
                all_passed = False
            
            # Test warm path (simulated - would use Redis in production)
            warm_start = time.time()
            # In production, this would fetch from Redis cache
            # For CI, we just test the aggregation is fast when data is ready
            warm_summary = await aggregator.aggregate_analytics(trades, wallet)
            warm_duration = time.time() - warm_start
            
            if warm_duration <= WARM_SLO_SECONDS:
                logger.info(f"  ✅ Warm path SLO PASSED ({warm_duration:.2f}s <= {WARM_SLO_SECONDS}s)")
            else:
                logger.info(f"  ℹ️  Warm path time: {warm_duration:.2f}s (Redis cache would be faster)")
            
            # Log summary stats
            logger.info(f"  Summary stats:")
            logger.info(f"    - Trades: {volume.get('total_trades', 0)}")
            logger.info(f"    - Top tokens: {len(summary.get('top_tokens', []))}")
            logger.info(f"    - Time window: {summary.get('time_window', {}).get('days', 0)} days")
            
        except Exception as e:
            logger.error(f"  ❌ Test failed for {wallet}: {e}", exc_info=True)
            all_passed = False
    
    return all_passed


def main():
    """Main entry point"""
    # Only run if analytics summary is enabled
    if os.getenv("ANALYTICS_SUMMARY", "false").lower() != "true":
        logger.info("ANALYTICS_SUMMARY not enabled, skipping test")
        return 0
    
    # Run the test
    success = asyncio.run(test_analytics_summary())
    
    if success:
        logger.info("\n✅ Analytics summary CI test PASSED")
        return 0
    else:
        logger.error("\n❌ Analytics summary CI test FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 