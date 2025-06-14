# WalletDoctor Web Interface

A simple, clean web interface for the WalletDoctor Coach.

## Quick Start

1. Install Flask:
   ```bash
   # For macOS/homebrew Python:
   pip3 install --break-system-packages flask
   
   # Or use a virtual environment (recommended):
   python3 -m venv venv
   source venv/bin/activate
   pip install flask
   ```

2. Run the web app:
   ```bash
   python3 web_app.py
   ```

3. Open http://localhost:5000 in your browser

## Features

- **Simple wallet input** - Just paste wallet addresses
- **Real-time analysis** - Uses existing coach.py functionality
- **Follow-up questions** - Chat with your coach about the analysis
- **Clean interface** - No complex frontend frameworks
- **Session management** - Each browser session is isolated

## How It Works

1. Enter wallet address(es) in the input field
2. Click "Analyze Wallets" to run the analysis
3. Once analysis is complete, ask follow-up questions
4. Click "Clear Session" to start fresh

## Interface Preview

```
🏥 WalletDoctor Coach

Enter wallet address(es): [________________]

[Analyze Wallets] [Clear Session]

[Analysis results appear here]

Ask a follow-up question:
[________________________]
[Ask Question]
```

## Technical Details

- The app runs your existing `coach.py analyze` command
- Conversation history is stored in memory (resets on restart)
- Follow-up questions use the same LLM as the CLI coach
- All analysis maintains the same statistical rigor

## Minimal Dependencies

Only requires Flask - no complex frontend frameworks or build tools.

## Troubleshooting

If you get module import errors, make sure:
1. You're running from the walletdoctor directory
2. All required packages are installed (see requirements.txt)
3. Your .env file has the necessary API keys 