#!/usr/bin/env python3
"""
Test script for Telegram bot functionality with pagination.
Tests that the bot properly handles wallets with many winners.
"""

import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_telegram_bot():
    """Test the telegram bot's ability to surface losers"""
    print(f"\n{'='*80}")
    print("🤖 TELEGRAM BOT TEST")
    print(f"{'='*80}\n")
    
    # Check if bot is running
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Telegram bot is running")
        else:
            print("❌ Telegram bot returned status:", response.status_code)
            return
    except Exception as e:
        print("❌ Telegram bot is not running!")
        print("   Please start it with: python3 telegram_bot_simple.py")
        return
    
    # Test wallets
    test_wallets = [
        ("Normal wallet", "rp8ntGS7P2k3faTvsRSWxQLa3B68DetNbwe1GHLiTUK"),
        # Add more test wallets here
    ]
    
    print("\n📊 Testing wallet analysis through bot API...")
    
    for name, wallet in test_wallets:
        print(f"\n--- {name} ---")
        print(f"Wallet: {wallet}")
        
        # Simulate bot command
        try:
            # The telegram bot should have an endpoint for testing
            # For now, we'll just note what to look for
            print("\n📱 To test in Telegram:")
            print(f"   1. Send: /analyze {wallet}")
            print("   2. Watch for:")
            print("      - Loading message with progress")
            print("      - Window info (e.g., 'Showing last 30 days')")
            print("      - Losers being displayed")
            print("      - Time taken for response")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n💡 What to verify in Telegram:")
    print("   1. Bot shows loading progress (pages being fetched)")
    print("   2. Losers are properly displayed (not just winners)")
    print("   3. Window info is shown when timeframe is narrowed")
    print("   4. Response time is reasonable (<30s)")
    print("   5. Error messages are clear if wallet has issues")

if __name__ == "__main__":
    test_telegram_bot() 