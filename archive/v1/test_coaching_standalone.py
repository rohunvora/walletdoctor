#!/usr/bin/env python3
"""Quick test of coaching system without modifying the bot"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.services.trading_coach import get_trade_coaching

async def test():
    print("Testing coaching system...\n")
    
    result = await get_trade_coaching(
        wallet="34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya",
        sol_amount=10.0,
        token_symbol="TEST"
    )
    
    if result['success']:
        print("✅ SUCCESS! Coaching is working\n")
        print("Message:")
        print(result['message'])
        print(f"\n{result['emoji']} {result['coaching']}")
        
        if 'statistics' in result:
            stats = result['statistics']
            print(f"\nStats: {stats['total_patterns']} patterns found")
    else:
        print("❌ FAILED!")
        print(result)

if __name__ == "__main__":
    asyncio.run(test())