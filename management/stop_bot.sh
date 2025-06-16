#!/bin/bash

# Stop the Pocket Trading Coach bot

# Check if PID file exists
if [ ! -f telegram_bot_coach.pid ]; then
    echo "Bot is not running (no PID file found)"
    exit 0
fi

# Read PID from file
PID=$(cat telegram_bot_coach.pid)

# Check if process is running
if ps -p $PID > /dev/null 2>&1; then
    echo "Stopping bot with PID $PID..."
    kill $PID
    
    # Wait for process to stop
    COUNTER=0
    while ps -p $PID > /dev/null 2>&1; do
        sleep 1
        COUNTER=$((COUNTER + 1))
        if [ $COUNTER -ge 10 ]; then
            echo "Process taking too long to stop, forcing..."
            kill -9 $PID
            break
        fi
    done
    
    echo "Bot stopped"
else
    echo "Bot process (PID $PID) not found, removing stale PID file"
fi

# Remove PID file
rm -f telegram_bot_coach.pid 