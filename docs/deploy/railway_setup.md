# Railway Deployment Setup

## Overview
This guide documents deploying WalletDoctor API to Railway for public GPT action testing.

## Prerequisites
- Railway account (https://railway.app)
- Railway CLI installed: `npm install -g @railway/cli`
- Access to environment variables

## Initial Deployment

### 1. Login to Railway
```bash
railway login
```

### 2. Create New Project
```bash
railway init
# Select "Empty Project"
# Name it: walletdoctor-api
```

### 3. Link GitHub Repository
In Railway dashboard:
1. Go to project settings
2. Connect GitHub repository: `rohunvora/walletdoctor`
3. Set branch: `main`

### 4. Configure Environment Variables

Required variables in Railway dashboard:

```bash
# Core API Configuration
REDIS_PASSWORD=your_redis_password
POSITION_CACHE_TTL=300
POSITION_UPDATE_TTL=600

# Feature Flags
UNREALIZED_PNL_ENABLED=true
GPT_EXPORT_ENABLED=true
FEATURE_FLAGS_POSITION_LIMITS=true
FEATURE_FLAGS_PRICE_CONFIDENCE_MIN=0.0

# API Keys
HELIUS_API_KEY=your_helius_key
HELIUS_CLUSTER_URL=your_helius_cluster_url
API_KEY_SECRET=your_api_key_secret

# Optional Performance Settings
MEMORY_GUARDRAIL_MB=512
MAX_WALLET_POSITIONS=100
WEB_CONCURRENCY=2
```

### 5. Deploy
Railway will automatically deploy when you push to GitHub. For manual deploy:

```bash
railway up
```

## Post-Deployment

### 1. Get Public URL
After deployment, Railway provides a URL like:
```
https://walletdoctor-production.up.railway.app
```

### 2. Test the Endpoint
```bash
# Test health check
curl https://walletdoctor-production.up.railway.app/

# Test GPT export endpoint
curl -H "X-Api-Key: wd_YOUR_API_KEY" \
     https://walletdoctor-production.up.railway.app/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2 \
     | jq '.schema_version'
```

## Monitoring & Logs

### View Logs
```bash
railway logs
```

Or in dashboard: Project → Deployments → View Logs

### Restart Service
```bash
railway restart
```

## Updating Deployment

### 1. Push Changes to GitHub
```bash
git add .
git commit -m "Update API"
git push origin main
```

Railway auto-deploys on push to main branch.

### 2. Manual Redeploy
In Railway dashboard:
1. Go to Deployments
2. Click "Redeploy" on latest commit

## Configuration Files

### railway.json
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn -b 0.0.0.0:$PORT src.api.wallet_analytics_api_v4_gpt:app --timeout 120 --workers 2",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Procfile
```
web: gunicorn src.api.wallet_analytics_api_v4_gpt:app
```

## DNS Configuration (Future)

When ready to use custom domain:

1. Add custom domain in Railway dashboard
2. Create CNAME record:
   ```
   Type: CNAME
   Name: api
   Value: walletdoctor-production.up.railway.app
   ```

## Troubleshooting

### Port Binding Issues
Railway provides PORT environment variable automatically. Ensure using `$PORT` in start command.

### Memory Issues
Adjust `WEB_CONCURRENCY` and worker count if hitting memory limits.

### Module Import Errors
Ensure `PYTHONPATH` includes project root:
```bash
PYTHONPATH=/app:$PYTHONPATH
```

## Cost Estimates
- Hobby plan: $5/month (includes $5 usage)
- Typical usage: ~$10-20/month for API
- Monitor usage in Railway dashboard 