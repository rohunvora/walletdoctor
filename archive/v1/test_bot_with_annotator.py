#!/usr/bin/env python3
"""
Test script to verify annotator integration in main bot
"""

import os

# Check if the bot token is set
token = os.getenv('TELEGRAM_BOT_TOKEN')
if token:
    print("✅ TELEGRAM_BOT_TOKEN is set")
else:
    print("❌ TELEGRAM_BOT_TOKEN not set")
    print("   Set it with: export TELEGRAM_BOT_TOKEN='your_token_here'")

print("\nTo test the annotator:")
print("1. Start the bot: ./management/start_bot.sh")
print("2. In Telegram, message your bot:")
print("   /annotate")
print("3. Follow the prompts to annotate your trades")
print("\nThe annotator is now integrated as a command in the main bot!")
print("No need to run a separate bot anymore.")