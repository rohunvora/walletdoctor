"""
Trade History Annotator Command - Integrated into main bot
"""

import csv
import io
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import logging

logger = logging.getLogger(__name__)

# Conversation states for annotator
ANNOTATOR_WALLET_INPUT, ANNOTATOR_ANNOTATING, ANNOTATOR_COMPLETE = range(3)

# Session storage
annotator_sessions = {}


class AnnotatorSession:
    """Ephemeral session for annotation flow"""
    def __init__(self, wallet_address):
        self.wallet_address = wallet_address
        self.trades = []
        self.current_index = 0
        self.annotations = {}  # trade_index -> annotation
        self.start_time = datetime.now()
        self.total_trades = 0  # Total trades found


async def annotate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the annotator flow"""
    user_id = update.effective_user.id
    
    # Clear any existing session
    if user_id in annotator_sessions:
        del annotator_sessions[user_id]
    
    welcome = (
        "**Trade History Annotator - Find out what actually works**\n\n"
        "I'll show you 5-7 of your most notable trades.\n"
        "You tell me what you were thinking.\n"
        "Export to CSV → Ask ChatGPT for brutal honesty.\n\n"
        "Ready? Drop your wallet address."
    )
    
    await update.message.reply_text(welcome, parse_mode='Markdown')
    return ANNOTATOR_WALLET_INPUT


async def annotator_wallet_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle wallet address input"""
    user_id = update.effective_user.id
    wallet_address = update.message.text.strip()
    
    # Basic validation
    if len(wallet_address) < 32 or len(wallet_address) > 44:
        await update.message.reply_text(
            "❌ That doesn't look like a valid Solana address. Try again?"
        )
        return ANNOTATOR_WALLET_INPUT
    
    # Show loading
    loading_msg = await update.message.reply_text("🔍 Analyzing your trading history...")
    
    try:
        # Import the fixed function and get total trades count
        from diary_api_fixed import get_notable_trades
        import duckdb
        
        # Get total trade count for anticipation
        db = duckdb.connect('pocket_coach.db')
        total_count = db.execute("""
            SELECT COUNT(*) FROM diary 
            WHERE wallet_address = ? 
            AND entry_type = 'trade'
            AND json_extract_string(data, '$.action') = 'SELL'
        """, [wallet_address]).fetchone()[0]
        db.close()
        
        # Fetch notable trades
        trades = await get_notable_trades(wallet_address, days=30, max_trades=7)
        
        if not trades:
            await loading_msg.edit_text(
                "😕 No trades found in the last 30 days.\n\n"
                "Make sure you entered the correct wallet address."
            )
            return ConversationHandler.END
        
        # Create session
        session = AnnotatorSession(wallet_address)
        session.trades = trades
        session.total_trades = total_count
        annotator_sessions[user_id] = session
        
        # Show summary with anticipation
        await loading_msg.edit_text(
            f"Found **{total_count} trades**. Here are your highlights:\n\n"
            "Let's see what patterns emerge... 👀\n\n"
            "_Type 'skip' to skip a trade, 'done' to finish early._"
        )
        
        # Show first trade
        await show_trade(update, context, session)
        return ANNOTATOR_ANNOTATING
        
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        await loading_msg.edit_text(
            "❌ Error fetching trades. Please try again."
        )
        return ConversationHandler.END


async def show_trade(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AnnotatorSession):
    """Display a trade for annotation"""
    if session.current_index >= len(session.trades):
        # All trades shown, generate export
        await generate_export(update, context, session)
        return ANNOTATOR_COMPLETE
    
    trade = session.trades[session.current_index]
    
    # Format trade display with emotional hooks
    msg = f"**Trade #{trade['index']}: {trade['token']}**\n"
    
    # Show the money first - that's what they remember
    pnl_pct = trade['pnl_pct']
    if pnl_pct > 50:
        msg += f"Bought: ${trade['entry_usd']:.0f} → Sold: ${trade['exit_usd']:.0f} (+{pnl_pct:.0f}%)\n"
    elif pnl_pct > 0:
        msg += f"Bought: ${trade['entry_usd']:.0f} → Sold: ${trade['exit_usd']:.0f} (+{pnl_pct:.0f}%)\n"
    elif pnl_pct < -30:
        msg += f"Bought: ${trade['entry_usd']:.0f} → Sold: ${trade['exit_usd']:.0f} ({pnl_pct:.0f}%)\n"
    else:
        msg += f"Bought: ${trade['entry_usd']:.0f} → Sold: ${trade['exit_usd']:.0f} ({pnl_pct:.0f}%)\n"
    
    # Add context based on selection reason with emotional triggers
    reason_context = {
        'biggest_winner': "Your BIGGEST WINNER 🏆",
        'biggest_loser': "This one hurt 💔",
        'largest_trade': "Your LARGEST position 🐋",
        'most_recent': "Your latest exit 🕐",
        'quick_flip': "Quick flip ({} days) ⚡".format(trade['held_days']),
        'diamond_hands': "Held {} days 💎🙌".format(trade['held_days']),
        'mcap_multiplier': "Best mcap growth 📈"
    }
    
    if trade.get('selection_reason') in reason_context:
        msg += f"{reason_context[trade['selection_reason']]}\n\n"
    else:
        msg += "\n"
    
    msg += "**What was your thinking here?**"
    
    await update.message.reply_text(msg, parse_mode='Markdown')


async def annotator_handle_annotation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle annotation input"""
    user_id = update.effective_user.id
    
    if user_id not in annotator_sessions:
        await update.message.reply_text(
            "❌ Session expired. Use /annotate to begin again."
        )
        return ConversationHandler.END
    
    session = annotator_sessions[user_id]
    text = update.message.text.strip()
    
    # Handle special commands
    if text.lower() == 'done':
        await generate_export(update, context, session)
        return ANNOTATOR_COMPLETE
    
    if text.lower() != 'skip':
        # Save annotation
        session.annotations[session.current_index] = text
        await update.message.reply_text("✓ Saved", parse_mode='Markdown')
    else:
        await update.message.reply_text("→ Skipped", parse_mode='Markdown')
    
    # Move to next trade
    session.current_index += 1
    
    # Show next trade or finish
    if session.current_index < len(session.trades):
        await show_trade(update, context, session)
        return ANNOTATOR_ANNOTATING
    else:
        await generate_export(update, context, session)
        return ANNOTATOR_COMPLETE


async def generate_export(update: Update, context: ContextTypes.DEFAULT_TYPE, session: AnnotatorSession):
    """Generate and send CSV export"""
    user_id = update.effective_user.id
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header - simplified for better ChatGPT analysis
    writer.writerow([
        'date', 'token', 'pnl_pct', 'held_days', 'your_reasoning'
    ])
    
    # Data rows
    annotated_count = 0
    preview_rows = []
    
    for i, trade in enumerate(session.trades):
        annotation = session.annotations.get(i, '')
        if annotation:
            annotated_count += 1
        
        row = [
            trade['exit_date'],
            trade['token'],
            f"{trade.get('pnl_pct', 0):.0f}",
            trade['held_days'],
            annotation
        ]
        writer.writerow(row)
        
        # Collect for preview
        if annotation and len(preview_rows) < 3:
            preview_rows.append({
                'date': trade['exit_date'],
                'token': trade['token'],
                'pnl': f"{trade.get('pnl_pct', 0):+.0f}%",
                'reasoning': annotation[:30] + '...' if len(annotation) > 30 else annotation
            })
    
    # Get CSV content
    csv_content = output.getvalue()
    output.close()
    
    # Show CSV preview if we have annotated trades
    if preview_rows:
        preview = "**Here's what you just created:**\n\n```\n"
        preview += "date,token,pnl%,your_reasoning\n"
        for row in preview_rows:
            preview += f"{row['date']},{row['token']},{row['pnl']},\"{row['reasoning']}\"\n"
        preview += "```\n\nNotice anything? 👀\n"
        
        await update.message.reply_text(preview, parse_mode='Markdown')
        await asyncio.sleep(2)  # Let them absorb it
    
    # Create file
    csv_file = io.BytesIO(csv_content.encode('utf-8'))
    csv_file.name = f'trading_patterns_{datetime.now().strftime("%Y%m%d")}.csv'
    
    # Send completion with time spent
    time_spent = int((datetime.now() - session.start_time).total_seconds() / 60)
    summary = (
        f"✅ **Done! That took {time_spent} minutes.**\n\n"
        f"You annotated {annotated_count} trades.\n\n"
        "Ready to see your patterns?"
    )
    
    await update.message.reply_text(summary, parse_mode='Markdown')
    
    # Send CSV file with better prompts
    await context.bot.send_document(
        chat_id=user_id,
        document=csv_file,
        filename=csv_file.name,
        caption=(
            "**Copy-paste this prompt to ChatGPT:**\n\n"
            "_\"I'm attaching my annotated trading history. Please analyze:_\n\n"
            "_1. What patterns lead to my profitable trades?_\n"
            "_2. What patterns lead to my losses?_\n"
            "_3. What specific behaviors should I stop immediately?_\n"
            "_4. What's my hidden edge that I should do more of?_\n"
            "_5. If I only followed my winning patterns, what would my P&L be?\"_\n\n"
            "🔥 **Pro tip**: Screenshot the brutal truths and share them. "
            "Your losses become lessons for others."
        ),
        parse_mode='Markdown'
    )
    
    # Clean up session
    del annotator_sessions[user_id]
    
    return ConversationHandler.END


async def annotator_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the annotation flow"""
    user_id = update.effective_user.id
    
    if user_id in annotator_sessions:
        del annotator_sessions[user_id]
    
    await update.message.reply_text(
        "Annotation cancelled. Use /annotate to begin again.",
        parse_mode='Markdown'
    )
    return ConversationHandler.END