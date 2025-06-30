# Railway Deployment Guide for WalletDoctor V2

## Prerequisites
- GitHub account with this repository
- Railway account (sign up at [railway.app](https://railway.app))

## Step-by-Step Deployment

### 1. Prepare Your Repository
Make sure your repository has these files (✅ already done):
- `railway.json` - Railway configuration
- `nixpacks.toml` - Build configuration
- `runtime.txt` - Python version
- `requirements.txt` - Dependencies
- `Procfile` - Backup for deployment

### 2. Create Railway Project

1. **Login to Railway**
   - Go to [railway.app](https://railway.app)
   - Sign in with GitHub

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `walletdoctor` repository
   - Select the branch to deploy (usually `main`)

### 3. Configure Environment Variables

In Railway dashboard, go to your service → Variables:

```bash
# Required
API_BASE_URL=https://your-app-name.up.railway.app
FLASK_ENV=production

# Optional (Railway sets PORT automatically)
# PORT is automatically set by Railway
```

**Important**: Replace `your-app-name` with your actual Railway app subdomain!

### 4. Deploy

1. Railway will automatically start deploying
2. Watch the build logs for any errors
3. Deployment typically takes 2-3 minutes

### 5. Get Your API URL

Once deployed:
1. Go to Settings → Domains
2. Click "Generate Domain" if you haven't already
3. Your API will be available at: `https://your-app-name.up.railway.app`

### 6. Test Your Deployment

```bash
# Test health endpoint
curl https://your-app-name.up.railway.app/health

# Test OpenAPI spec
curl https://your-app-name.up.railway.app/openapi.json

# Test analysis with sample data
python3 generate_test_csv.py
curl -X POST -F "file=@test_trades.csv" https://your-app-name.up.railway.app/analyze
```

### 7. Update Environment Variable

After getting your domain, update the `API_BASE_URL`:
1. Go to Variables in Railway
2. Update `API_BASE_URL` to your actual domain
3. Railway will automatically redeploy

## Troubleshooting

### Build Fails
- Check build logs in Railway dashboard
- Ensure all dependencies in requirements.txt are correct
- Verify Python version in runtime.txt is supported

### App Crashes
- Check deploy logs for errors
- Verify environment variables are set correctly
- Check that `wallet_analytics_service.py` is in the root directory

### Timeout Issues
- The app is configured for 120-second timeout
- Large CSV files might still timeout
- Consider reducing file size or optimizing analytics

## Next Steps

Once deployed successfully:

1. **Copy your API URL**: `https://your-app-name.up.railway.app`
2. **Get OpenAPI spec**: Visit `/openapi.json` endpoint
3. **Configure GPT**:
   - Go to ChatGPT → Create GPT
   - Add Action → Import OpenAPI schema
   - Use your Railway URL as the base

## Monitoring

Railway provides:
- Real-time logs
- Metrics dashboard  
- Automatic restarts on failure
- Usage tracking

Access these in your Railway project dashboard.

## Costs

Railway offers:
- $5 free credits monthly
- Pay-as-you-go after that
- This API should run well within free tier for moderate usage

---

Your Railway deployment is now configured and ready! 🚀 