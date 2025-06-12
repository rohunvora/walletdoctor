# WalletDoctor Deployment Guide

## Deploying to Render (Recommended)

### Prerequisites
1. Create a free account at [render.com](https://render.com)
2. Have your GitHub repository ready
3. Get your OpenAI API key ready

### Step-by-Step Deployment

1. **Connect GitHub to Render**
   - Log into Render
   - Click "New +" → "Web Service"
   - Connect your GitHub account if not already connected
   - Select the `walletdoctor` repository

2. **Configure the Service**
   - Name: `walletdoctor` (or your preferred name)
   - Region: Choose closest to your users
   - Branch: `main`
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn web_app:app`

3. **Set Environment Variables**
   - Click "Environment" tab
   - Add variable:
     - Key: `OPENAI_API_KEY`
     - Value: Your OpenAI API key
   - Add variable:
     - Key: `PYTHON_VERSION`
     - Value: `3.11.0`

4. **Deploy**
   - Click "Create Web Service"
   - Wait for the build to complete (5-10 minutes)
   - Your app will be available at `https://walletdoctor-xxxx.onrender.com`

## Alternative: Deploy to Railway

1. **Install Railway CLI**
   ```bash
   npm install -g @railway/cli
   ```

2. **Login and Deploy**
   ```bash
   railway login
   railway init
   railway up
   ```

3. **Set Environment Variables**
   ```bash
   railway variables set OPENAI_API_KEY=your-api-key-here
   ```

4. **Get your URL**
   ```bash
   railway open
   ```

## Alternative: Deploy to Heroku

1. **Install Heroku CLI**
   - Download from [heroku.com](https://heroku.com)

2. **Create and Deploy**
   ```bash
   heroku create walletdoctor-yourname
   git push heroku main
   heroku config:set OPENAI_API_KEY=your-api-key-here
   heroku open
   ```

## Post-Deployment

1. **Test the Application**
   - Visit your deployed URL
   - Try analyzing a wallet address
   - Ensure the AI coaching features work (requires OpenAI API key)

2. **Monitor Logs**
   - Render: Dashboard → Logs
   - Railway: `railway logs`
   - Heroku: `heroku logs --tail`

3. **Custom Domain (Optional)**
   - All platforms support custom domains
   - Follow platform-specific instructions

## Troubleshooting

1. **Import Errors**
   - Ensure all dependencies are in requirements.txt
   - Check Python version compatibility

2. **Database Issues**
   - The app creates SQLite databases locally
   - For production, consider PostgreSQL (all platforms support it)

3. **Memory Issues**
   - Free tiers have memory limits
   - Optimize data processing for large wallets

4. **API Key Issues**
   - Ensure OPENAI_API_KEY is set correctly
   - Check for typos or extra spaces

## Notes

- The free tier on Render spins down after 15 minutes of inactivity
- First request after spin-down takes ~30 seconds
- For always-on deployment, consider paid tiers 