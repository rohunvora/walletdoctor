# ChatGPT Actions Setup Instructions

## Quick Setup Steps

### 1. Create/Edit CustomGPT
1. Go to https://chat.openai.com/gpts/editor
2. Create a new GPT or edit existing "WalletDoctor Analyst"

### 2. Configure the Action
1. Click on **"Create new action"** in the Actions section
2. Copy the entire contents of `walletdoctor_action_clean.json`
3. Paste into the Schema editor
4. Click **"Format"** button - the red error bar should disappear

### 3. Set Up Authentication
1. Under **Authentication**, select **"API Key"**
2. Set **Auth Type** to: `Custom`
3. Set **Custom Header Name** to: `X-Api-Key`
4. Enter your API key when prompted

### 4. Configure Privacy Policy
For testing, use this temporary URL:
```
https://raw.githubusercontent.com/walletdoctor/walletdoctor/main/docs/privacy.md
```

### 5. Test the Connection
1. Use the "Test" button with wallet: `3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2`
2. Should return portfolio data with positions

### 6. Save the GPT
1. Click **"Update"** or **"Create"** to save
2. The action is now ready for testing

## Troubleshooting

### "Could not parse valid OpenAPI spec"
- Ensure you're using `walletdoctor_action_clean.json` (not the original)
- Check no extra characters were added during copy/paste
- Use the Format button to validate

### "Multiple hostnames detected"
- We've already removed localhost from the clean version
- If still seeing this, check only one server entry exists

### Authentication errors
- Verify API key format: `wd_` followed by 32 characters
- Ensure header name is exactly `X-Api-Key` (case sensitive)

## Test Queries
Once configured, try these in the GPT chat:
- "What's my portfolio for wallet 3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2?"
- "Show me the largest position"
- "What's my total P&L?" 