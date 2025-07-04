#!/usr/bin/env python3
"""
Demo script for v0.7.2-compact trade compression
Shows size reduction and format comparison
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

# Demo wallet
DEMO_WALLET = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"


async def demo_compression():
    """Demonstrate trade compression with real data"""
    from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
    from src.lib.trade_enricher import TradeEnricher
    from src.lib.trade_compressor import TradeCompressor
    from src.lib.sol_price_fetcher import get_sol_price_usd
    
    logger.info("=" * 60)
    logger.info("🗜️  Trade Compression Demo (v0.7.2-compact)")
    logger.info("=" * 60)
    
    # Check SOL price
    sol_price = get_sol_price_usd()
    logger.info(f"\n📊 SOL Price: ${sol_price}")
    
    # Fetch trades
    logger.info(f"\n🔍 Fetching trades for {DEMO_WALLET[:8]}...")
    
    async with BlockchainFetcherV3Fast(skip_pricing=True) as fetcher:
        result = await fetcher.fetch_wallet_trades(DEMO_WALLET)
    
    trades = result.get("trades", [])
    signatures = result.get("signatures", [])
    
    logger.info(f"✅ Found {len(trades)} trades")
    
    # Enrich trades
    logger.info("\n💰 Enriching trades with price data...")
    enricher = TradeEnricher()
    enriched_trades = await enricher.enrich_trades(trades)
    
    logger.info(f"✅ Enriched {enricher.enrichment_stats['trades_priced']} trades")
    logger.info(f"   P&L calculated for {enricher.enrichment_stats['trades_with_pnl']} trades")
    
    # Show original format
    logger.info("\n📄 Original Format (v0.7.1-trades-value):")
    original_response = {
        "wallet": DEMO_WALLET,
        "schema_version": "v0.7.1-trades-value",
        "signatures": signatures,
        "trades": enriched_trades
    }
    
    original_json = json.dumps(original_response)
    original_size = len(original_json)
    logger.info(f"   Size: {original_size:,} bytes ({original_size/1024:.1f} KB)")
    
    # Show sample original trade
    if enriched_trades:
        sample = enriched_trades[0]
        logger.info("\n   Sample trade (original):")
        logger.info(f"   {json.dumps(sample, indent=2)[:300]}...")
    
    # Compress trades
    logger.info("\n🗜️  Compressing to v0.7.2-compact format...")
    compressor = TradeCompressor()
    compressed_response = compressor.compress_trades(enriched_trades, DEMO_WALLET)
    
    compressed_json = json.dumps(compressed_response)
    compressed_size = len(compressed_json)
    
    logger.info(f"✅ Compressed!")
    logger.info(f"   Size: {compressed_size:,} bytes ({compressed_size/1024:.1f} KB)")
    
    # Calculate savings
    size_reduction = original_size - compressed_size
    compression_ratio = original_size / compressed_size if compressed_size > 0 else 0
    
    logger.info(f"\n📊 Compression Results:")
    logger.info(f"   Original:    {original_size:,} bytes ({original_size/1024:.1f} KB)")
    logger.info(f"   Compressed:  {compressed_size:,} bytes ({compressed_size/1024:.1f} KB)")
    logger.info(f"   Saved:       {size_reduction:,} bytes ({size_reduction/1024:.1f} KB)")
    logger.info(f"   Ratio:       {compression_ratio:.1f}x smaller")
    
    # Show compressed format structure
    logger.info("\n📄 Compressed Format Structure:")
    logger.info(f"   Field map: {compressed_response['field_map']}")
    logger.info(f"   Constants: {compressed_response['constants']}")
    logger.info(f"   Summary: {compressed_response['summary']}")
    
    # Show sample compressed trades
    if compressed_response["trades"]:
        logger.info("\n   Sample compressed trades:")
        for i, trade in enumerate(compressed_response["trades"][:3]):
            logger.info(f"   Trade {i+1}: {trade}")
    
    # Estimate for larger wallets
    logger.info("\n📈 Estimated Sizes for Larger Wallets:")
    bytes_per_trade = compressed_size / len(trades) if trades else 0
    
    for trade_count in [5000, 10000, 50000]:
        estimated_size = int(bytes_per_trade * trade_count)
        logger.info(f"   {trade_count:,} trades: ~{estimated_size:,} bytes ({estimated_size/1024:.1f} KB)")
    
    # Check ChatGPT compatibility
    logger.info("\n✅ ChatGPT Compatibility:")
    if compressed_size < 200_000:  # 200KB
        logger.info(f"   ✅ Size OK for ChatGPT ({compressed_size/1024:.1f} KB < 200 KB)")
    else:
        logger.info(f"   ⚠️  May be too large for ChatGPT ({compressed_size/1024:.1f} KB > 200 KB)")
    
    # Show how to decompress
    logger.info("\n🔓 To decompress in ChatGPT:")
    logger.info("   ```python")
    logger.info("   # Each trade array follows field_map order:")
    logger.info("   # [ts, act, tok, amt, p_sol, p_usd, val, pnl]")
    logger.info("   ")
    logger.info("   for trade in data['trades']:")
    logger.info("       timestamp = datetime.fromtimestamp(trade[0])")
    logger.info("       action = data['constants']['actions'][trade[1]]")
    logger.info("       token = trade[2]")
    logger.info("       # ... etc")
    logger.info("   ```")


if __name__ == "__main__":
    asyncio.run(demo_compression()) 