#!/bin/bash

echo "🏥 Tradebro Bot Setup"
echo "========================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    echo "TELEGRAM_BOT_TOKEN=" > .env
    echo "✅ Created .env file"
else
    echo "📄 .env file already exists"
fi

echo ""
echo "Next steps:"
echo "1. Edit .env and add your bot token from @BotFather"
echo "2. Install dependencies: pip3 install --user --break-system-packages python-telegram-bot python-dotenv"
echo "3. Run the bot: python3 telegram_bot.py"
echo ""
echo "Need help? Check telegram_setup.md for detailed instructions!" 