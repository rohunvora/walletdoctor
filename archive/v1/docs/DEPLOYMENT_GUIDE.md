# Pocket Trading Coach - Conversational AI Deployment Guide

## Overview

This guide covers the deployment of the new conversational AI system for Pocket Trading Coach. The system is designed for gradual rollout with minimal risk to existing functionality.

## Prerequisites

- Working Telegram bot with `TELEGRAM_BOT_TOKEN`
- OpenAI API key with GPT-4o-mini access
- Existing `pocket_coach.db` database
- Python 3.9+ environment

## Environment Variables

### Required for AI System

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-api-key-here

# Feature Flags
USE_NEW_AI=false                    # Global toggle (start with false)
NEW_AI_USER_IDS=                   # Comma-separated user IDs for beta
```

### Existing Variables

```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your-bot-token

# P&L Services (optional but recommended)
CIELO_API_KEY=your-cielo-key
BIRDEYE_API_KEY=your-birdeye-key
```

## Deployment Steps

### 1. Initial Setup (Pre-deployment)

```bash
# Back up production database
cp pocket_coach.db pocket_coach_backup_$(date +%Y%m%d).db

# Test the bot locally
python3 telegram_bot_coach.py
```

### 2. Beta Testing Phase

Enable for specific test users:

```bash
# Add beta testers by Telegram user ID
export NEW_AI_USER_IDS="123456789,987654321"
export USE_NEW_AI=false  # Keep global flag off
```

Beta users will see:
- New `/chat`, `/clear`, `/pause`, `/resume` commands
- Natural AI responses instead of templates
- "🚀 New AI (Beta)" badge in `/start`

### 3. Monitoring During Beta

Watch for:
- Response times (target: <2s)
- Error rates in logs
- User engagement metrics
- GPT API costs

Key log messages:
```
🚀 Initializing new conversation engine...
✅ New conversation engine initialized successfully
Using new conversation engine for user 123456789
```

### 4. Gradual Rollout

After successful beta (1-2 weeks):

```bash
# Enable for all users
export USE_NEW_AI=true
export NEW_AI_USER_IDS=""  # Clear beta list
```

### 5. Rollback Procedure

If issues arise:

```bash
# Instant rollback - no code changes needed
export USE_NEW_AI=false
```

Users immediately return to template-based system.

## Cost Estimation

### GPT-4o-mini Pricing (as of Dec 2024)
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens

### Expected Usage per User
- ~10 trades/day
- ~3 messages per trade
- ~500 tokens per exchange

### Monthly Cost Estimate
- 100 active users: ~$20-40
- 500 active users: ~$100-200
- 1000 active users: ~$200-400

Compare to GPT-4: 60-80% cost reduction

## Monitoring & Analytics

### Key Metrics to Track

1. **Engagement**
   ```sql
   -- Conversation participation rate
   SELECT 
     COUNT(DISTINCT user_id) as active_users,
     COUNT(*) as total_messages,
     AVG(LENGTH(content)) as avg_message_length
   FROM conversation_messages
   WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '24 hours';
   ```

2. **Response Quality**
   ```sql
   -- Check for fallback responses
   SELECT COUNT(*) 
   FROM conversation_messages
   WHERE role = 'assistant' 
   AND content LIKE '%What made you%';
   ```

3. **Performance**
   - Log parsing for "Context build took Xms"
   - GPT response times
   - Database query times

### Setting Up Alerts

1. **High Error Rate**
   - Alert if >5% requests fail
   - Check for "Error processing with conversation engine"

2. **Slow Response Times**
   - Alert if p95 response time >3s
   - Check for "Context build took >1000ms"

3. **Cost Overrun**
   - Monitor OpenAI dashboard
   - Set budget alerts at 80% of target

## Troubleshooting

### Common Issues

1. **"Failed to initialize new conversation engine"**
   - Check OPENAI_API_KEY is valid
   - Verify internet connectivity
   - Check OpenAI API status

2. **Slow responses**
   - Check database size (vacuum if needed)
   - Verify context building performance
   - Consider reducing conversation history window

3. **Weird AI responses**
   - Review system prompt in `gpt_client.py`
   - Check context being sent to GPT
   - Consider adjusting temperature

### Debug Mode

Enable detailed logging:

```python
# In telegram_bot_coach.py
logging.basicConfig(level=logging.DEBUG)
```

## User Communication

### Announcement Template

```
🎉 Exciting Update: Your Trading Coach Got Smarter!

We've upgraded from templated responses to natural conversations. Your coach now:

✨ Understands context across messages
💬 Responds more naturally
🧠 Remembers your trading patterns
⚡ Asks better questions

New commands:
/chat - Start a conversation anytime
/pause - Take a break from notifications
/resume - Come back when ready
/clear - Fresh start

The old system is still available if needed. Try the new AI and let us know what you think!
```

### FAQ for Users

**Q: Can I go back to the old system?**
A: Yes! Just ask and we'll switch you back.

**Q: Will the bot remember our old conversations?**
A: The bot starts fresh but keeps all your trading history and stats.

**Q: Is my data being sent anywhere?**
A: Only anonymized conversation context goes to OpenAI for generating responses. No wallet addresses or transaction IDs are shared.

## Production Checklist

- [ ] Database backed up
- [ ] Environment variables set
- [ ] Beta testers identified
- [ ] Monitoring alerts configured
- [ ] Cost tracking enabled
- [ ] Rollback plan tested
- [ ] User announcement drafted
- [ ] Support team briefed

## Next Steps After Deployment

1. **Week 1**: Monitor closely, gather feedback
2. **Week 2**: Tune system prompt based on real conversations
3. **Week 3**: Expand rollout if metrics are good
4. **Month 1**: Full launch with announcement

## Support

For issues or questions:
- Check logs for error messages
- Review this guide's troubleshooting section
- Contact the development team with specific error details

Remember: The beauty of this system is instant rollback. Don't be afraid to experiment! 