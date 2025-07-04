#!/usr/bin/env python3
"""
Demo script for v0.8.0-summary analytics endpoint
Shows pre-computed analytics summaries for wallets
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Demo wallets
DEMO_WALLETS = [
    "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",  # Small
    "AAXTYrQR6CHDGhJYz4uSgJ6dq7JTySTR6WyAq8QKZnF8"   # Medium
]


async def demo_analytics_summary():
    """Demonstrate analytics summary generation"""
    from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
    from src.lib.trade_enricher import TradeEnricher
    from src.lib.trade_analytics_aggregator import TradeAnalyticsAggregator
    from src.lib.sol_price_fetcher import get_sol_price_usd
    
    logger.info("=" * 60)
    logger.info("📊 Analytics Summary Demo (v0.8.0-summary)")
    logger.info("=" * 60)
    
    # Check SOL price
    sol_price = get_sol_price_usd()
    logger.info(f"\n💰 SOL Price: ${sol_price}")
    
    for wallet_idx, wallet in enumerate(DEMO_WALLETS):
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 Wallet {wallet_idx + 1}: {wallet[:8]}...")
        logger.info(f"{'='*60}")
        
        # Fetch trades
        logger.info("\n📥 Fetching trades...")
        start_time = asyncio.get_event_loop().time()
        
        async with BlockchainFetcherV3Fast(skip_pricing=True) as fetcher:
            result = await fetcher.fetch_wallet_trades(wallet)
        
        trades = result.get("trades", [])
        fetch_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"✅ Fetched {len(trades)} trades in {fetch_time:.2f}s")
        
        # Enrich trades
        logger.info("\n💎 Enriching trades with prices...")
        enricher = TradeEnricher()
        enriched_trades = await enricher.enrich_trades(trades)
        
        logger.info(f"✅ Enriched {enricher.enrichment_stats['trades_priced']} trades")
        logger.info(f"   P&L calculated for {enricher.enrichment_stats['trades_with_pnl']} trades")
        
        # Generate analytics
        logger.info("\n📈 Generating analytics summary...")
        aggregator = TradeAnalyticsAggregator()
        summary = await aggregator.aggregate_analytics(enriched_trades, wallet)
        
        # Display results
        logger.info("\n📊 ANALYTICS SUMMARY")
        logger.info("=" * 40)
        
        # Time window
        tw = summary["time_window"]
        logger.info(f"\n⏰ Time Window:")
        logger.info(f"   Trading history: {tw['days']} days")
        if tw["start"]:
            logger.info(f"   First trade: {tw['start'][:10]}")
            logger.info(f"   Last trade:  {tw['end'][:10]}")
        
        # P&L Metrics
        pnl = summary["pnl"]
        logger.info(f"\n💰 P&L Metrics:")
        logger.info(f"   Realized P&L: ${pnl['realized_usd']} ({pnl['realized_pct']}%)")
        logger.info(f"   Win Rate: {pnl['win_rate']*100:.1f}% ({pnl['wins']} wins / {pnl['losses']} losses)")
        logger.info(f"   Biggest Win:  ${pnl['max_single_win_usd']}")
        logger.info(f"   Biggest Loss: ${pnl['max_single_loss_usd']}")
        
        # Volume Metrics
        vol = summary["volume"]
        logger.info(f"\n📊 Volume Metrics:")
        logger.info(f"   Total Trades: {vol['total_trades']:,}")
        logger.info(f"   SOL Volume: {vol['total_sol_volume']} SOL")
        logger.info(f"   Avg Trade Size: ${vol['avg_trade_value_usd']}")
        logger.info(f"   Trading Frequency: {vol['trades_per_day']:.1f} trades/day")
        
        # Top Tokens
        logger.info(f"\n🏆 Top Tokens (by activity):")
        for i, token in enumerate(summary["top_tokens"][:5]):
            pnl_str = f"+${token['realized_pnl_usd']}" if token['realized_pnl_usd'].startswith('-') else f"${token['realized_pnl_usd']}"
            logger.info(f"   {i+1}. {token['symbol']:10} - {token['trades']:3} trades, P&L: {pnl_str}")
        
        # Recent Performance
        recent = summary["recent_windows"]
        logger.info(f"\n📅 Recent Performance:")
        logger.info(f"   Last 30 days: {recent['last_30d']['trades']} trades, ${recent['last_30d']['pnl_usd']} P&L ({recent['last_30d']['win_rate']*100:.0f}% win)")
        logger.info(f"   Last 7 days:  {recent['last_7d']['trades']} trades, ${recent['last_7d']['pnl_usd']} P&L ({recent['last_7d']['win_rate']*100:.0f}% win)")
        
        # Response size
        summary_json = json.dumps(summary)
        size_kb = len(summary_json) / 1024
        logger.info(f"\n📦 Response Size: {size_kb:.1f} KB")
        
        # Performance
        logger.info(f"\n⚡ Performance:")
        logger.info(f"   Computation time: {aggregator.stats['computation_time_ms']}ms")
        logger.info(f"   Size per trade: {len(summary_json)/len(trades):.0f} bytes")
    
    logger.info("\n" + "="*60)
    logger.info("🎯 Key Benefits of Analytics Summary:")
    logger.info("="*60)
    logger.info("✅ Pre-computed metrics (<50KB response)")
    logger.info("✅ 15-minute Redis cache for instant responses")
    logger.info("✅ All key trading metrics in one call")
    logger.info("✅ Perfect for ChatGPT's response size limits")
    logger.info("✅ No need to process 1000s of trades client-side")
    
    logger.info("\n💡 API Usage:")
    logger.info("   GET /v4/analytics/summary/{wallet}")
    logger.info("   Query params: ?force_refresh=true (skip cache)")
    logger.info("   Feature flag: ANALYTICS_SUMMARY=true")


if __name__ == "__main__":
    asyncio.run(demo_analytics_summary()) 