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
    winning_trades = [t for t in trades if t.get("pnl_usd", 0) > 0]
    losing_trades = [t for t in trades if t.get("pnl_usd", 0) < 0]
    
    # Win rate
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
    
    # Average P&L
    total_pnl = sum(t.get("pnl_usd", 0) for t in trades)
    avg_win = sum(t["pnl_usd"] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t["pnl_usd"] for t in losing_trades) / len(losing_trades) if losing_trades else 0
    
    # Token breakdown
    token_stats = defaultdict(lambda: {"trades": 0, "pnl": 0, "wins": 0})
    for trade in trades:
        token = trade.get("token", "UNKNOWN")
        token_stats[token]["trades"] += 1
        token_stats[token]["pnl"] += trade.get("pnl_usd", 0)
        if trade.get("pnl_usd", 0) > 0:
            token_stats[token]["wins"] += 1
    
    # Best and worst trades
    trades_with_pnl = [t for t in trades if t.get("pnl_usd") is not None]
    best_trade = max(trades_with_pnl, key=lambda t: t["pnl_usd"]) if trades_with_pnl else None
    worst_trade = min(trades_with_pnl, key=lambda t: t["pnl_usd"]) if trades_with_pnl else None
    
    # Trading frequency
    if trades:
        timestamps = [datetime.fromisoformat(t["timestamp"]) for t in trades if "timestamp" in t]
        if len(timestamps) >= 2:
            time_span = (max(timestamps) - min(timestamps)).days or 1
            trades_per_day = total_trades / time_span
        else:
            trades_per_day = 0
    else:
        trades_per_day = 0
    
    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "trades_per_day": round(trades_per_day, 1),
        "top_tokens": sorted(
            [(k, v) for k, v in token_stats.items()],
            key=lambda x: x[1]["trades"],
            reverse=True
        )[:5]
    }


def generate_insight_markdown(stats: Dict[str, Any]) -> str:
    """Generate ChatGPT-friendly markdown insights"""
    if "error" in stats:
        return f"❌ {stats['error']}"
    
    # Performance summary
    profit_emoji = "🟩" if stats["total_pnl"] > 0 else "🟥"
    
    # Calculate profit factor
    profit_factor = stats['avg_win'] / abs(stats['avg_loss']) if stats['avg_loss'] != 0 else 0
    profit_factor_str = f"{profit_factor:.2f}" if profit_factor > 0 else "N/A"
    
    markdown = f"""## 📊 Trading Performance Analysis

### Overview
- **Total Trades**: {stats['total_trades']:,}
- **Win Rate**: {stats['win_rate']}% ({stats['winning_trades']} wins / {stats['losing_trades']} losses)
- **Total P&L**: {profit_emoji} ${stats['total_pnl']:,.2f}
- **Trading Frequency**: {stats['trades_per_day']} trades/day

### Average Performance
- **Average Win**: +${stats['avg_win']:,.2f}
- **Average Loss**: -${abs(stats['avg_loss']):,.2f}
- **Profit Factor**: {profit_factor_str}

### Best & Worst Trades
"""
    
    if stats['best_trade']:
        bt = stats['best_trade']
        markdown += f"- **Best**: {bt['token']} +${bt['pnl_usd']:,.2f} on {bt['timestamp'][:10]}\n"
    
    if stats['worst_trade']:
        wt = stats['worst_trade']
        markdown += f"- **Worst**: {wt['token']} -${abs(wt['pnl_usd']):,.2f} on {wt['timestamp'][:10]}\n"
    
    # Top tokens
    markdown += "\n### Top Tokens by Activity\n"
    for token, data in stats['top_tokens']:
        win_rate = data['wins'] / data['trades'] * 100 if data['trades'] > 0 else 0
        pnl_emoji = "🟩" if data['pnl'] > 0 else "🟥"
        markdown += f"- **{token}**: {data['trades']} trades, {win_rate:.0f}% win rate, {pnl_emoji} ${data['pnl']:,.2f}\n"
    
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

You have a {stats['win_rate']}% win rate across {stats['total_trades']} trades, which is {'above average' if stats['win_rate'] > 50 else 'below average but not uncommon'} for active traders. 

Your average winning trade (+${stats['avg_win']}) is {'significantly larger than' if stats['avg_win'] > abs(stats['avg_loss']) * 1.5 else 'comparable to'} your average loss (-${abs(stats['avg_loss'])}), suggesting {'good risk management' if stats['avg_win'] > abs(stats['avg_loss']) else 'room for improvement in position sizing'}.

You're quite active with {stats['trades_per_day']} trades per day on average. This high frequency approach {'is working well for you' if stats['total_pnl'] > 0 else 'might benefit from more selective entry points'}.

Would you like me to dive deeper into any specific aspect of your trading?
""")


if __name__ == "__main__":
    asyncio.run(main()) 