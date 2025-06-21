# Analytics Event Store - Deployment Checklist

## 🚀 Deployment Steps

### 1. Pre-Deployment (✅ DONE)
- [x] All tests passing (42 unit tests + integration tests)
- [x] Load test successful (100k events, <10ms queries)
- [x] Shadow mode test successful (old/new systems match)
- [x] Migration script tested on database copy
- [x] System prompt updated with new tools
- [x] Branch pushed to GitHub

### 2. Database Migration
```bash
# SSH to production server
# Backup current database first!
cp pocket_coach.db pocket_coach_backup_$(date +%Y%m%d).db

# Run the events table migration
python db_migrations.py

# Verify events table created
sqlite3 events.db "SELECT name FROM sqlite_master WHERE type='table';"
```

### 3. Deploy Code
```bash
# Pull the latest code
git pull origin analytics-event-store

# Restart the bot to pick up changes
./management/stop_bot.sh
./management/start_bot.sh

# Check logs for any errors
tail -f bot.log
```

### 4. Verify Dual-Write
After deployment, verify both systems are recording:
```bash
# Check diary table (should continue growing)
sqlite3 pocket_coach.db "SELECT COUNT(*) FROM diary WHERE entry_type='trade';"

# Check events table (should start growing)
sqlite3 events.db "SELECT COUNT(*) FROM events;"

# Wait 5 minutes and check again - both should increase
```

### 5. Test New Features
Send these messages to the bot to test:
- "how am i doing today"
- "profit this week?"
- "am i improving?"
- "what's my daily average?"

### 6. Monitor for 24 Hours
- Check error logs regularly
- Verify performance stays under 100ms
- Ensure no duplicate recording issues
- Monitor memory usage

### 7. Gradual Migration (After 24-48 hours)
Once confident dual-write is stable:
```bash
# Run full historical migration
python migrate_diary_to_events.py

# This is resumable - can stop/start if needed
```

## 🚨 Rollback Plan

If any issues arise:
```bash
# 1. Stop the bot
./management/stop_bot.sh

# 2. Revert to previous branch
git checkout main

# 3. Restart bot
./management/start_bot.sh

# Total rollback time: <5 minutes
```

## ✅ Success Criteria

- [ ] Bot responds to time-based queries
- [ ] Query performance <100ms
- [ ] No errors in logs
- [ ] Both diary and events tables growing
- [ ] Users report features working

## 📞 Support

If issues arise:
1. Check logs first: `tail -100 bot.log`
2. Verify database connections
3. Test with simple queries first
4. Document any errors for debugging 