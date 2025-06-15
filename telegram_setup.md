# WalletDoctor Telegram Bot Setup

## 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` 
3. Choose a name (e.g., "WalletDoctor")
4. Choose a username (must end in "bot", e.g., `walletdoctor_bot`)
5. Save the token BotFather gives you

## 2. Set Environment Variable

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

Or create a `.env` file:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## 4. Run the Bot

```bash
python telegram_bot.py
```

## 5. Test It Out

1. Find your bot on Telegram (search for the username you chose)
2. Send `/start`
3. Paste a wallet address
4. Add notes to your losing trades
5. Enable monitoring to get alerts!

## Features

- **Pattern Learning**: Tell the bot WHY you made bad trades
- **Smart Alerts**: Get warned when new trades match past mistakes
- **Simple Interface**: Just text, no complex commands
- **Privacy First**: Your data stays in your local database

## Examples

When you lose on a trade, explain it:
- "FOMO'd in after seeing Twitter hype"
- "Revenge trade after losing on BONK"
- "Bought the top during a pump"
- "Didn't take profits, held too long"

The bot will remember and warn you next time! 