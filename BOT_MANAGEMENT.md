# Bot Management Guide

## Overview
The Pocket Trading Coach bot now includes instance lock protection to prevent multiple instances from running simultaneously. This prevents the "409 Conflict" errors that occur when multiple bot instances try to poll Telegram's servers.

## Management Scripts

### Starting the Bot
```bash
./start_bot.sh
```
- Checks for existing instances before starting
- Loads environment variables from `.env` file
- Creates PID file to track the running process

### Stopping the Bot
```bash
./stop_bot.sh
```
- Gracefully stops the bot using the PID file
- Waits up to 10 seconds for clean shutdown
- Forces termination if needed
- Removes PID file

### Checking Status
```bash
./status_bot.sh
```
- Shows if bot is running
- Displays process details (PID, CPU, memory usage)
- Detects stale PID files

## Instance Lock Mechanism

The bot uses a PID file (`telegram_bot_coach.pid`) to ensure only one instance runs at a time:

1. On startup, checks if PID file exists
2. If exists, verifies if that process is actually running
3. If running, refuses to start and shows error
4. If not running (stale PID), removes file and starts
5. Creates new PID file with current process ID
6. On shutdown (Ctrl+C or SIGTERM), removes PID file

## Troubleshooting

### Bot won't start - "already running" error
```bash
# Check if bot is actually running
./status_bot.sh

# If not running but PID file exists (stale):
./stop_bot.sh  # This will clean up
./start_bot.sh  # Now start fresh
```

### Manual cleanup if scripts fail
```bash
# Find all python telegram bot processes
ps aux | grep -E "(telegram|coach)" | grep python

# Kill specific process
kill -9 [PID]

# Remove PID file
rm -f telegram_bot_coach.pid
```

### Environment Setup
Make sure your `.env` file contains:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_key_here  # For GPT-4o-mini tagging
```

## Best Practices

1. Always use the provided scripts instead of running `python telegram_bot_coach.py` directly
2. Check status before starting to avoid conflicts
3. Use `./stop_bot.sh` for clean shutdown instead of kill -9
4. Monitor logs when debugging issues

## Logs

The bot outputs logs to console. To save logs:
```bash
./start_bot.sh > bot.log 2>&1 &
```

To view logs in real-time:
```bash
tail -f bot.log
``` 