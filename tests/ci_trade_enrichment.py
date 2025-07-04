#!/usr/bin/env python3
"""
CI test for TRD-002: Verify trade enrichment coverage

Ensures that when PRICE_ENRICH_TRADES=true, at least 90% of trades
have non-null price_usd values
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import logging
import asyncio
from decimal import Decimal
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
MIN_COVERAGE_PERCENT = 90.0  # Must price at least 90% of trades
TEST_WALLET = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"


async def test_trade_enrichment_coverage():
    """Test that trade enrichment achieves required coverage"""
    from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
    from src.lib.trade_enricher import TradeEnricher
    from src.lib.sol_price_fetcher import get_sol_price_usd
    
    # Check SOL price is available
    sol_price = get_sol_price_usd()
    if not sol_price:
        logger.error("SOL price unavailable - cannot test enrichment")
        return False
    
    logger.info(f"SOL price: ${sol_price}")
    
    # Fetch trades
    logger.info(f"Fetching trades for {TEST_WALLET}...")
    
    try:
        async with BlockchainFetcherV3Fast(skip_pricing=True) as fetcher:
            result = await fetcher.fetch_wallet_trades(TEST_WALLET)
            
        trades = result.get("trades", [])
        logger.info(f"Found {len(trades)} trades")
        
        if len(trades) == 0:
            logger.error("No trades found")
            return False
        
        # Run enrichment
        enricher = TradeEnricher()
        enriched_trades = await enricher.enrich_trades(trades)
        
        # Calculate coverage
        total_trades = len(enriched_trades)
        priced_trades = sum(1 for t in enriched_trades if t.get("price_usd") is not None)
        coverage_percent = (priced_trades / total_trades) * 100 if total_trades > 0 else 0
        
        logger.info(f"Enrichment complete:")
        logger.info(f"  Total trades: {total_trades}")
        logger.info(f"  Priced trades: {priced_trades}")
        logger.info(f"  Coverage: {coverage_percent:.1f}%")
        logger.info(f"  Stats: {enricher.enrichment_stats}")
        
        # Check if we meet threshold
        if coverage_percent >= MIN_COVERAGE_PERCENT:
            logger.info(f"✅ Coverage {coverage_percent:.1f}% meets threshold {MIN_COVERAGE_PERCENT}%")
            
            # Verify some P&L calculations
            trades_with_pnl = [t for t in enriched_trades if t.get("pnl_usd") and Decimal(t["pnl_usd"]) != 0]
            logger.info(f"  Trades with P&L: {len(trades_with_pnl)}")
            
            # FIFO regression check: median absolute P&L for sell trades should be > 0
            sell_trades_with_pnl = [
                t for t in enriched_trades 
                if t.get("action") == "sell" and t.get("pnl_usd") and Decimal(t["pnl_usd"]) != 0
            ]
            
            if sell_trades_with_pnl:
                abs_pnl_values = [abs(Decimal(t["pnl_usd"])) for t in sell_trades_with_pnl]
                abs_pnl_values.sort()
                median_abs_pnl = abs_pnl_values[len(abs_pnl_values) // 2]
                
                logger.info(f"  Sell trades with P&L: {len(sell_trades_with_pnl)}")
                logger.info(f"  Median absolute P&L: ${median_abs_pnl}")
                
                if median_abs_pnl == 0:
                    logger.error("❌ FIFO regression: median absolute P&L is 0")
                    return False
                else:
                    logger.info("✅ FIFO validation: median absolute P&L > 0")
            
            if trades_with_pnl:
                # Show sample P&L calculations
                sample = trades_with_pnl[0]
                logger.info(f"  Sample P&L trade:")
                logger.info(f"    Token: {sample.get('token')}")
                logger.info(f"    Action: {sample.get('action')}")
                logger.info(f"    P&L: ${sample.get('pnl_usd')}")
            
            return True
        else:
            logger.error(f"❌ Coverage {coverage_percent:.1f}% below threshold {MIN_COVERAGE_PERCENT}%")
            
            # Debug info
            null_price_trades = [t for t in enriched_trades if t.get("price_usd") is None]
            if null_price_trades:
                logger.info("Sample trades with null prices:")
                for i, trade in enumerate(null_price_trades[:3]):
                    logger.info(f"  Trade {i+1}:")
                    logger.info(f"    Action: {trade.get('action')}")
                    logger.info(f"    Token in: {trade.get('token_in', {}).get('symbol')}")
                    logger.info(f"    Token out: {trade.get('token_out', {}).get('symbol')}")
            
            return False
            
    except Exception as e:
        logger.error(f"Test failed with error: {e}", exc_info=True)
        return False


def main():
    """Main entry point"""
    # Only run if enrichment is enabled
    if os.getenv("PRICE_ENRICH_TRADES", "false").lower() != "true":
        logger.info("PRICE_ENRICH_TRADES not enabled, skipping test")
        return 0
    
    # Run the test
    success = asyncio.run(test_trade_enrichment_coverage())
    
    if success:
        logger.info("\nTrade enrichment CI test PASSED")
        return 0
    else:
        logger.error("\nTrade enrichment CI test FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 