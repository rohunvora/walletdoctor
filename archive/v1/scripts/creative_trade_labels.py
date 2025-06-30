#!/usr/bin/env python3
"""
Creative Trade Label Generator for Trading Report Cards
Generates memorable, shareable labels for trades
"""

import random
from typing import Dict, List, Any

class CreativeTradeLabels:
    def __init__(self):
        self.winner_descriptors = [
            "SNIPER", "PROPHET", "LEGEND", "NINJA", "GENIUS", 
            "QUICKIE", "SCORE", "MASTER", "ACE", "HERO"
        ]
        
        self.loser_descriptors = [
            "DISASTER", "FUNERAL", "GAMBLE", "PANIC", "MARRIAGE",
            "NIGHTMARE", "FUMBLE", "TRAGEDY", "CASINO", "CHAOS"
        ]
        
        self.winner_subtitles = [
            "Took profits like a pro",
            "Perfect timing for once", 
            "In and out like a ninja",
            "Sometimes lucky > good",
            "Textbook execution",
            "Saw the future, cashed out",
            "Diamond timing",
            "Finally got one right"
        ]
        
        self.loser_subtitles = [
            "Married a pump, divorced broke",
            "When in doubt, overtrade", 
            "This one still hurts",
            "Rode it all the way down",
            "Fastest loss in the west",
            "Till death do us part",
            "Hope wasn't a strategy",
            "The market's latest victim"
        ]
    
    def generate_trade_label(self, trade: Dict[str, Any]) -> Dict[str, str]:
        """Generate a creative label for a trade."""
        
        symbol = trade.get('symbol', 'TOKEN')
        pnl = trade.get('totalPnl', trade.get('pnl', 0))
        hold_time_seconds = trade.get('holdTimeSeconds', 0)
        hold_time_hours = hold_time_seconds / 3600 if hold_time_seconds else 0
        swaps = trade.get('numSwaps', 1)
        
        # Winner labels
        if pnl > 0:
            if hold_time_hours < 1:
                return {
                    'emoji': '⚡',
                    'title': f'THE {symbol} QUICKIE',
                    'subtitle': random.choice([
                        'In and out like a ninja',
                        'Sometimes lucky > good',
                        'Speed kills (profits)'
                    ])
                }
            elif hold_time_hours < 6:
                return {
                    'emoji': '💎',
                    'title': f'THE {symbol} SNIPER',
                    'subtitle': random.choice([
                        'Took profits like a pro',
                        'Perfect timing for once',
                        'Diamond timing'
                    ])
                }
            elif hold_time_hours > 72:
                return {
                    'emoji': '👑',
                    'title': f'THE {symbol} LEGEND',
                    'subtitle': random.choice([
                        'Patience actually paid off',
                        'Saw the future, cashed out',
                        'When HODLing works'
                    ])
                }
            else:
                descriptor = random.choice(self.winner_descriptors)
                return {
                    'emoji': '🎯',
                    'title': f'THE {symbol} {descriptor}',
                    'subtitle': random.choice(self.winner_subtitles)
                }
        
        # Loser labels
        else:
            if hold_time_hours < 0.5 and abs(pnl) > 5000:
                return {
                    'emoji': '🔥',
                    'title': f'THE {symbol} PANIC',
                    'subtitle': random.choice([
                        'Fastest loss in the west',
                        'Paper hands strike again',
                        'Panic sold the bottom'
                    ])
                }
            elif swaps > 15:
                return {
                    'emoji': '🎰',
                    'title': f'THE {symbol} CASINO',
                    'subtitle': f'{swaps} swaps of desperation'
                }
            elif hold_time_hours > 100:
                return {
                    'emoji': '💀',
                    'title': f'THE {symbol} MARRIAGE',
                    'subtitle': random.choice([
                        'Till death do us part',
                        'Still hoping for a comeback',
                        'Love is blind (and broke)'
                    ])
                }
            elif abs(pnl) > 10000:
                return {
                    'emoji': '🩸',
                    'title': f'THE {symbol} DISASTER',
                    'subtitle': random.choice([
                        'This one still hurts',
                        'Married a pump, divorced broke',
                        'The market\'s latest victim'
                    ])
                }
            else:
                descriptor = random.choice(self.loser_descriptors)
                return {
                    'emoji': '📉',
                    'title': f'THE {symbol} {descriptor}',
                    'subtitle': random.choice(self.loser_subtitles)
                }

    def generate_trading_dna(self, stats: Dict[str, Any]) -> str:
        """Generate a memorable trading style description."""
        
        patterns = []
        
        win_rate = stats.get('win_rate_pct', stats.get('win_rate', 0))
        
        # Pattern detection
        if win_rate < 25:
            patterns.append("Spray and pray specialist")
        elif win_rate > 70:
            patterns.append("Selective sniper")
        
        # Add more patterns based on available stats
        if len(patterns) == 0:
            patterns.append("Consistently inconsistent")
        
        return patterns[0]
    
    def get_notable_trades(self, trades: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
        """Select the most notable trades for labeling."""
        
        if not trades:
            return []
        
        # Sort by absolute PnL to get most impactful trades
        sorted_trades = sorted(trades, key=lambda x: abs(x.get('totalPnl', x.get('pnl', 0))), reverse=True)
        
        notable = []
        winners_added = 0
        losers_added = 0
        
        for trade in sorted_trades:
            pnl = trade.get('totalPnl', trade.get('pnl', 0))
            
            if pnl > 0 and winners_added < 2:
                notable.append(trade)
                winners_added += 1
            elif pnl < 0 and losers_added < 2:
                notable.append(trade)
                losers_added += 1
            
            if len(notable) >= limit:
                break
        
        return notable

def format_telegram_report_card(grade: str, percentile: int, trades: List[Dict[str, Any]], stats: Dict[str, Any]) -> str:
    """Format a complete ASCII report card for Telegram."""
    
    label_generator = CreativeTradeLabels()
    notable_trades = label_generator.get_notable_trades(trades, limit=3)
    
    output = f"""━━━━━━━━━━━━━━━━━━━━━
     GRADE: {grade}
   Better than {percentile}%
━━━━━━━━━━━━━━━━━━━━━"""
    
    for trade in notable_trades:
        label = label_generator.generate_trade_label(trade)
        pnl = trade.get('totalPnl', trade.get('pnl', 0))
        hold_time_seconds = trade.get('holdTimeSeconds', 0)
        
        # Format P&L
        pnl_str = f"+${pnl:,.0f}" if pnl > 0 else f"-${abs(pnl):,.0f}"
        
        # Format time
        if hold_time_seconds:
            hours = hold_time_seconds / 3600
            if hours < 1:
                time_str = f"{hold_time_seconds/60:.0f}min"
            elif hours < 24:
                time_str = f"{hours:.1f}hr"
            else:
                time_str = f"{hours/24:.1f}d"
        else:
            time_str = "unknown"
        
        output += f"""

{label['emoji']} {label['title']}
   {pnl_str} ({time_str})
   "{label['subtitle']}\""""
    
    # Add trading DNA
    trading_dna = label_generator.generate_trading_dna(stats)
    output += f"""
━━━━━━━━━━━━━━━━━━━━━

Your Trading DNA:
"{trading_dna}"
━━━━━━━━━━━━━━━━━━━━━"""
    
    return output 