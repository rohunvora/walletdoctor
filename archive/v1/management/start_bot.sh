#!/bin/bash

# Start the Pocket Trading Coach bot

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create a .env file with your TELEGRAM_BOT_TOKEN"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Check if bot token is set
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Error: TELEGRAM_BOT_TOKEN not set in .env file!"
    exit 1
fi

# Check if already running
if [ -f telegram_bot_coach.pid ]; then
    PID=$(cat telegram_bot_coach.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Bot is already running with PID $PID"
        echo "Use ./stop_bot.sh to stop it first"
        exit 1
    else
        echo "Removing stale PID file"
        rm telegram_bot_coach.pid
    fi
fi

echo "Starting Pocket Trading Coach bot..."
python3 telegram_bot_coach.py 