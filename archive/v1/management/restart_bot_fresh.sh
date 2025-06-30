#!/bin/bash
# Restart bot with fresh test data

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "🔄 Restarting bot with fresh test data..."

# Stop the bot
./management/stop_bot.sh

# Clear recent diary entries (last hour of testing)
echo -e "\n${GREEN}Clearing recent test data...${NC}"
python3 -c "
import duckdb
db = duckdb.connect('pocket_coach.db')
count = db.execute('''
    DELETE FROM diary 
    WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL 1 HOUR
    RETURNING COUNT(*)
''').fetchone()
deleted = count[0] if count else 0
db.commit()
db.close()
print(f'✅ Cleared {deleted} recent diary entries')
"

# Start the bot fresh
echo -e "\n${GREEN}Starting bot...${NC}"
./management/start_bot.sh

echo -e "\n✅ Bot restarted with fresh test data!"
echo "Try /annotate in Telegram to test the new feature." 