# Example: Creative Label Generation for Trading Report Cards

def generate_trade_label(trade):
    """Generate a creative, memorable label for a trade."""
    
    symbol = trade['symbol']
    pnl = trade['pnl']
    hold_time = trade['hold_time_hours']
    swaps = trade['num_swaps']
    
    # Winner labels
    if pnl > 0:
        if hold_time < 1:
            return {
                'emoji': '⚡',
                'title': f'THE {symbol} QUICKIE',
                'subtitle': 'In and out like a ninja'
            }
        elif hold_time < 6:
            return {
                'emoji': '💎',
                'title': f'THE {symbol} SNIPER',
                'subtitle': 'Took profits like a pro'
            }
        elif hold_time > 72:
            return {
                'emoji': '👑',
                'title': f'THE {symbol} DIAMOND HANDS',
                'subtitle': 'Patience actually paid off'
            }
        else:
            return {
                'emoji': '🎯',
                'title': f'THE {symbol} SCORE',
                'subtitle': 'Textbook timing'
            }
    
    # Loser labels
    else:
        if hold_time < 0.5 and abs(pnl) > 5000:
            return {
                'emoji': '🔥',
                'title': f'THE {symbol} PANIC',
                'subtitle': 'Fastest loss in the west'
            }
        elif swaps > 15:
            return {
                'emoji': '🎰',
                'title': f'THE {symbol} GAMBLE',
                'subtitle': f'{swaps} trades of desperation'
            }
        elif hold_time > 100:
            return {
                'emoji': '💀',
                'title': f'THE {symbol} MARRIAGE',
                'subtitle': 'Till death do us part'
            }
        elif abs(pnl) > 10000:
            return {
                'emoji': '🩸',
                'title': f'THE {symbol} DISASTER',
                'subtitle': 'This one still hurts'
            }
        else:
            return {
                'emoji': '📉',
                'title': f'THE {symbol} FUMBLE',
                'subtitle': 'Could\'ve been worse'
            }

def generate_trading_dna(stats):
    """Generate a short, memorable description of trading style."""
    
    patterns = []
    
    if stats['avg_winner_hold'] < stats['avg_loser_hold'] * 2:
        patterns.append("Paper hands on winners")
    if stats['avg_loser_hold'] > 48:
        patterns.append("Diamond hands on losers")
    if stats['avg_swaps'] > 10:
        patterns.append("Chronic overtrader")
    if stats['win_rate'] < 30:
        patterns.append("Spray and pray specialist")
    
    if len(patterns) >= 2:
        return f"{patterns[0]},\n{patterns[1]}"
    elif patterns:
        return patterns[0]
    else:
        return "Consistently inconsistent"

# Example usage:
def format_telegram_report_card(wallet_data):
    """Format a complete report card with creative labels."""
    
    grade = wallet_data['grade']
    percentile = wallet_data['percentile']
    trades = wallet_data['notable_trades'][:3]  # Top 3 most notable
    
    output = f"""
━━━━━━━━━━━━━━━━━━━━━
     GRADE: {grade}
   Better than {percentile}%
━━━━━━━━━━━━━━━━━━━━━
"""
    
    for trade in trades:
        label = generate_trade_label(trade)
        pnl_str = f"+${trade['pnl']:,.0f}" if trade['pnl'] > 0 else f"-${abs(trade['pnl']):,.0f}"
        time_str = f"{trade['hold_time_hours']:.1f}hr" if trade['hold_time_hours'] < 24 else f"{trade['hold_time_hours']/24:.1f}d"
        
        output += f"""
{label['emoji']} {label['title']}
   {pnl_str} ({time_str})
   "{label['subtitle']}"
"""
    
    trading_dna = generate_trading_dna(wallet_data['stats'])
    output += f"""
━━━━━━━━━━━━━━━━━━━━━

Your Trading DNA:
"{trading_dna}"
━━━━━━━━━━━━━━━━━━━━━
"""
    
    return output

# Advanced: Use AI for even more creative labels
def generate_ai_trade_label(trade, user_context=None):
    """Use AI to generate ultra-specific, memorable labels."""
    
    prompt = f"""
    Generate a creative, memorable label for this trade:
    - Token: {trade['symbol']}
    - P&L: ${trade['pnl']:,.0f}
    - Hold time: {trade['hold_time_hours']:.1f} hours
    - Number of swaps: {trade['num_swaps']}
    
    Make it:
    1. Funny but not mean
    2. Specific to this trade
    3. Memorable and shareable
    4. Under 20 characters for the title
    
    Format:
    Title: THE [TOKEN] [DESCRIPTOR]
    Subtitle: [Witty one-liner about what happened]
    """
    
    # This would call OpenAI/Claude for creative generation
    # For now, returning example
    return {
        'title': f"THE {trade['symbol']} SAGA",
        'subtitle': "A cautionary tale in 19 swaps"
    } 