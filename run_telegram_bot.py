#!/usr/bin/env python3
"""
Run the Tradebro Telegram Bot - Simplified Version
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Import and run the simplified bot
from telegram_bot_simple import TradeBroBot

if __name__ == "__main__":
    # Get token from environment
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        print("❌ Please set TELEGRAM_BOT_TOKEN environment variable")
        print("Either export it or add to .env file:")
        print('export TELEGRAM_BOT_TOKEN="your-bot-token"')
        exit(1)
    
    # Create and run bot
    print("🚀 Starting Tradebro Bot (Simplified Version)...")
    print("📊 One insight at a time. Make it count.")
    
    bot = TradeBroBot(TOKEN)
    bot.run() 