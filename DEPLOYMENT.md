# WalletDoctor V2 Deployment Guide

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run API locally
python wallet_analytics_api.py

# API will be available at http://localhost:5000
```

## Deployment Options

### Option 1: Railway (Recommended)

1. Create account at [railway.app](https://railway.app)
2. Connect your GitHub repository
3. Railway will auto-detect the configuration
4. Set environment variable:
   ```
   API_BASE_URL=https://your-app.railway.app
   ```
5. Deploy!

### Option 2: Heroku

1. Install Heroku CLI
2. Create new app:
   ```bash
   heroku create your-app-name
   git push heroku main
   ```
3. Set environment variable:
   ```bash
   heroku config:set API_BASE_URL=https://your-app-name.herokuapp.com
   ```

### Option 3: Any Python Host

The app is a standard Flask application. Deploy to:
- AWS Lambda (with API Gateway)
- Google Cloud Run
- DigitalOcean App Platform
- Render.com
- Fly.io

Just ensure:
- Python 3.8+
- Port from environment variable `PORT`
- Set `API_BASE_URL` to your public URL

## GPT Integration

1. Deploy API to public URL
2. Visit `/openapi.json` on your deployment
3. Copy the OpenAPI specification
4. In ChatGPT:
   - Create new GPT
   - Add Action
   - Paste OpenAPI spec
   - Configure authentication (if needed)
5. Test with a CSV upload!

## Testing Your Deployment

```bash
# Generate test data
python generate_test_csv.py

# Test deployed API
curl -X POST \
  -F "file=@test_trades.csv" \
  https://your-deployment-url/analyze
```

## Environment Variables

- `PORT` - Server port (default: 5000)
- `API_BASE_URL` - Your public URL (required for OpenAPI spec)
- `FLASK_ENV` - Set to 'production' for deployment

## Security Notes

- File size limited to 10MB
- Only CSV files accepted
- Wallet addresses are hashed
- No data is stored - analysis only
- Includes "not financial advice" disclaimer 