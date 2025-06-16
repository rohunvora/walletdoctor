#!/bin/bash

# Check the status of the Pocket Trading Coach bot

# Check if PID file exists
if [ ! -f telegram_bot_coach.pid ]; then
    echo "❌ Bot is not running (no PID file found)"
    exit 1
fi

# Read PID from file
PID=$(cat telegram_bot_coach.pid)

# Check if process is running
if ps -p $PID > /dev/null 2>&1; then
    echo "✅ Bot is running with PID $PID"
    
    # Show process details
    echo ""
    echo "Process details:"
    ps -p $PID -o pid,ppid,user,%cpu,%mem,start,time,comm
    
    # Show last few log lines if available
    # You could add log file monitoring here if you implement logging to file
else
    echo "❌ Bot process (PID $PID) not found"
    echo "PID file exists but process is not running (stale PID file)"
    echo "Run ./stop_bot.sh to clean up, then ./start_bot.sh to restart"
    exit 1
fi 