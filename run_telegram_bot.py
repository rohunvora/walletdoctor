#!/usr/bin/env python3
"""
Run the WalletDoctor Telegram Bot with proper environment variables
"""
import os
import sys

# Load dotenv to get API keys and TELEGRAM_BOT_TOKEN
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Check if required environment variables are set
required_vars = ['HELIUS_KEY', 'CIELO_KEY', 'TELEGRAM_BOT_TOKEN']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print("❌ Missing required environment variables:")
    for var in missing_vars:
        print(f"   - {var}")
    print("\nPlease set them in your .env file or as environment variables")
    sys.exit(1)

print("🚀 Starting WalletDoctor Telegram Bot...")
print(f"✅ HELIUS_KEY: {os.environ.get('HELIUS_KEY', '')[:8]}...")
print(f"✅ CIELO_KEY: {os.environ.get('CIELO_KEY', '')[:8]}...")
print(f"✅ TELEGRAM_BOT_TOKEN: Found")
print("")

# Now run the bot directly by importing it
from telegram_bot import WalletDoctorBot

bot = WalletDoctorBot(os.getenv('TELEGRAM_BOT_TOKEN'))
print("🤖 WalletDoctor Bot starting...")
bot.run() 