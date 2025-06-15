# Deploy WalletDoctor MVP to Railway 🚂

## Quick Deploy Steps

### 1. Push Changes to GitHub
```bash
git add .
git commit -m "Deploy MVP with annotation support"
git push origin main
```

### 2. Configure Railway Environment Variables

In your Railway project dashboard, add these environment variables:

```
HELIUS_KEY=your-helius-api-key
CIELO_KEY=your-cielo-api-key
PORT=8080
```

### 3. Deploy

Railway will automatically deploy when you push to GitHub. The deployment will:

1. Run `startup.py` to initialize the database
2. Run migrations to create annotation tables
3. Start the enhanced web interface with `gunicorn`

### 4. Test Your Deployment

Once deployed, visit your Railway URL and:

1. Enter a wallet address
2. See instant stats (no waiting!)
3. Click "+ Note" on any trade
4. Add your thoughts
5. Watch personalized insights appear

## What's New in This Deployment?

- **Instant Stats**: No more waiting for 30+ trades
- **Annotation System**: Add notes to trades for personalized coaching
- **Trade Comparison**: See how new trades compare to your average
- **Evolution Tracking**: Watch your improvement over time

## Troubleshooting

### "Module not found" errors
The `startup.py` script adds the scripts directory to the Python path. If you still see errors, check that all files were committed.

### Database errors
The database is created automatically on first run. If you need to reset:
```python
# In Railway console
import os
os.remove('coach.db')
```

### API errors
Make sure your HELIUS_KEY and CIELO_KEY environment variables are set correctly in Railway.

## Monitoring

Check the Railway logs for:
- "✅ Database initialized successfully!" - Migrations ran
- "✨ Initialization complete!" - Ready to serve requests

## Next Steps

1. Share your Railway URL to start getting user feedback
2. Monitor annotations in the database
3. Watch how coaching improves with more user data

The MVP is designed to start simple and grow smarter with every annotation! 