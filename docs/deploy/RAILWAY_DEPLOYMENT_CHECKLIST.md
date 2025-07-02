# Railway Deployment Checklist

## Quick Deploy Steps

### 1. Create Railway Project
1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Connect to `rohunvora/walletdoctor`
5. Select `main` branch

### 2. Set Environment Variables
In Railway dashboard → Variables tab, add:

```bash
# REQUIRED - Core Config
HELIUS_KEY=<your_helius_api_key_from_helius.xyz>

# REQUIRED - Feature Flags
UNREALIZED_PNL_ENABLED=true
GPT_EXPORT_ENABLED=true
FEATURE_FLAGS_POSITION_LIMITS=true
FEATURE_FLAGS_PRICE_CONFIDENCE_MIN=0.0

# OPTIONAL - Performance
POSITION_CACHE_TTL=300
POSITION_UPDATE_TTL=600
MEMORY_GUARDRAIL_MB=512
MAX_WALLET_POSITIONS=100
WEB_CONCURRENCY=2
```

### 3. Deploy
Railway will auto-deploy after adding variables.

### 4. Get Your URL
Once deployed, Railway provides URL like:
- `https://walletdoctor-production-XXXX.up.railway.app`

Copy this URL - we'll need it for the OpenAPI spec.

### 5. Test Deployment
```bash
# Replace with your actual Railway URL and API key
export RAILWAY_URL="https://walletdoctor-production-XXXX.up.railway.app"
export API_KEY="wd_YOUR_32_CHAR_KEY"

# Test health
curl $RAILWAY_URL/

# Test GPT export
curl -H "X-Api-Key: $API_KEY" \
     $RAILWAY_URL/v4/positions/export-gpt/3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2 \
     | jq '.schema_version'
```

### 6. Update OpenAPI Spec
Once you have the Railway URL, I'll update:
- `docs/gpt_action/walletdoctor_action_clean.json`

With your actual Railway URL in the servers section.

## What I Need From You

1. **Railway URL**: After deployment, share the generated URL
2. **API Key**: A valid `wd_` prefixed key for testing
3. **Confirmation**: That the test curl commands work

Once you provide the Railway URL, I'll immediately update the OpenAPI spec and we can proceed with GPT testing! 