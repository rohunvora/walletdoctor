#!/usr/bin/env python3
"""
Demo: Trade-Based Insights for ChatGPT
Shows what we can build with the stable trades endpoint
"""

import asyncio
import aiohttp
import json
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Any


async def fetch_trades(wallet: str) -> Dict[str, Any]:
    """Fetch trades from the stable endpoint"""
    url = f"https://web-production-2bb2f.up.railway.app/v4/trades/export-gpt/{wallet}"
    headers = {"X-Api-Key": "wd_test1234567890abcdef1234567890ab"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            return await resp.json()


def analyze_trades(trades: List[Dict]) -> Dict[str, Any]:
    """Generate trading insights from trade data"""
    if not trades:
        return {"error": "No trades found"}
    
    # Basic stats
    total_trades = len(trades)
    buys = [t for t in trades if t.get("action") == "buy"]
    sells = [t for t in trades if t.get("action") == "sell"]
    
    # Since pnl_usd is always 0, we'll calculate volume instead
    # Calculate SOL volume from token_in/token_out
    sol_volume = 0
    for trade in trades:
        if trade.get("token_in", {}).get("symbol") == "So111111":
            # Buying with SOL
            sol_volume += trade["token_in"].get("amount", 0)
        elif trade.get("token_out", {}).get("symbol") == "So111111":
            # Selling for SOL
            sol_volume += trade["token_out"].get("amount", 0)
    
    # Token activity breakdown
    token_stats = defaultdict(lambda: {"buys": 0, "sells": 0, "volume": 0})
    for trade in trades:
        token = trade.get("token", "UNKNOWN")
        action = trade.get("action", "unknown")
        
        if action == "buy":
            token_stats[token]["buys"] += 1
            # Volume is SOL spent
            if trade.get("token_in", {}).get("symbol") == "So111111":
                token_stats[token]["volume"] += trade["token_in"].get("amount", 0)
        elif action == "sell":
            token_stats[token]["sells"] += 1
            # Volume is SOL received
            if trade.get("token_out", {}).get("symbol") == "So111111":
                token_stats[token]["volume"] += trade["token_out"].get("amount", 0)
    
    # DEX breakdown
    dex_stats = defaultdict(int)
    for trade in trades:
        dex = trade.get("dex", "UNKNOWN")
        dex_stats[dex] += 1
    
    # Trading frequency
    if trades:
        timestamps = [datetime.fromisoformat(t["timestamp"]) for t in trades if "timestamp" in t]
        if len(timestamps) >= 2:
            time_span = (max(timestamps) - min(timestamps)).days or 1
            trades_per_day = total_trades / time_span
            
            # Hour of day analysis
            hour_stats = defaultdict(int)
            for ts in timestamps:
                hour_stats[ts.hour] += 1
            
            # Find most active hours
            sorted_hours = sorted(hour_stats.items(), key=lambda x: x[1], reverse=True)
            top_hours = sorted_hours[:3]
        else:
            trades_per_day = 0
            top_hours = []
    else:
        trades_per_day = 0
        top_hours = []
    
    return {
        "total_trades": total_trades,
        "buys": len(buys),
        "sells": len(sells),
        "buy_sell_ratio": len(buys) / len(sells) if len(sells) > 0 else 0,
        "sol_volume": round(sol_volume, 2),
        "trades_per_day": round(trades_per_day, 1),
        "top_tokens": sorted(
            [(k, v) for k, v in token_stats.items()],
            key=lambda x: x[1]["buys"] + x[1]["sells"],
            reverse=True
        )[:5],
        "top_dexes": sorted(
            [(k, v) for k, v in dex_stats.items()],
            key=lambda x: x[1],
            reverse=True
        )[:3],
        "top_hours": top_hours
    }


def generate_insight_markdown(stats: Dict[str, Any]) -> str:
    """Generate ChatGPT-friendly markdown insights"""
    if "error" in stats:
        return f"❌ {stats['error']}"
    
    markdown = f"""## 📊 Trading Activity Analysis

### Overview
- **Total Trades**: {stats['total_trades']:,} ({stats['buys']} buys, {stats['sells']} sells)
- **Buy/Sell Ratio**: {stats['buy_sell_ratio']:.2f}
- **Total SOL Volume**: {stats['sol_volume']:,.2f} SOL
- **Trading Frequency**: {stats['trades_per_day']} trades/day

### Trading Patterns
"""
    
    # Most active hours
    if stats['top_hours']:
        markdown += "- **Most Active Hours (UTC)**: "
        hour_list = [f"{hour}:00 ({count} trades)" for hour, count in stats['top_hours']]
        markdown += ", ".join(hour_list) + "\n"
    
    # Top DEXes
    if stats['top_dexes']:
        markdown += "\n### DEX Preference\n"
        for dex, count in stats['top_dexes']:
            pct = count / stats['total_trades'] * 100
            markdown += f"- **{dex}**: {count} trades ({pct:.1f}%)\n"
    
    # Top tokens
    markdown += "\n### Top Tokens by Activity\n"
    for token, data in stats['top_tokens']:
        total_trades = data['buys'] + data['sells']
        sol_vol = data['volume']
        markdown += f"- **{token}**: {total_trades} trades ({data['buys']} buys, {data['sells']} sells), {sol_vol:.2f} SOL volume\n"
    
    return markdown


async def main():
    """Run the demo"""
    print("🚀 Trade-Based Insights Demo\n")
    
    # Test wallet
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    print(f"Fetching trades for wallet: {wallet[:8]}...{wallet[-8:]}")
    
    # Fetch data
    data = await fetch_trades(wallet)
    
    if "error" in data:
        print(f"❌ Error: {data['error']}")
        return
    
    trades = data.get("trades", [])
    print(f"✅ Found {len(trades)} trades\n")
    
    # Analyze
    stats = analyze_trades(trades)
    
    # Generate insights
    insights = generate_insight_markdown(stats)
    print(insights)
    
    # Show what ChatGPT could say
    print("\n" + "="*60)
    print("💬 Example ChatGPT Response:")
    print("="*60)
    print(f"""
Based on your trading history, here's what I found:

You've executed {stats['total_trades']:,} trades with a buy/sell ratio of {stats['buy_sell_ratio']:.2f}, showing {'a balanced approach' if 0.8 < stats['buy_sell_ratio'] < 1.2 else 'a bias toward ' + ('buying' if stats['buy_sell_ratio'] > 1 else 'selling')}.

Your total volume of {stats['sol_volume']:,.2f} SOL across {stats['trades_per_day']:.1f} trades per day indicates {'very high' if stats['trades_per_day'] > 50 else 'high' if stats['trades_per_day'] > 20 else 'moderate'} trading activity.

{f"You're most active during {stats['top_hours'][0][0]}:00 UTC with {stats['top_hours'][0][1]} trades in that hour." if stats['top_hours'] else ""}

Your preferred DEX is {stats['top_dexes'][0][0] if stats['top_dexes'] else 'various exchanges'}, accounting for {stats['top_dexes'][0][1] / stats['total_trades'] * 100:.1f}% of your trades.

Would you like me to analyze specific tokens or time periods in more detail?
""")


if __name__ == "__main__":
    asyncio.run(main()) 