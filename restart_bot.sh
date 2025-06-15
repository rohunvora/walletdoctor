# Bot Restart Workflow
pkill -f 'run_telegram_bot'
sleep 2
python3 run_telegram_bot.py &
echo 'Bot restarted with latest changes'
