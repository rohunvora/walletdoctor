"""
Pocket Trading Coach - Example Implementation
Shows how we detect patterns and generate nudges in real-time
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics

class PatternDetector:
    """Detects trading patterns from user's personal history"""
    
    def __init__(self, user_history: List[Dict]):
        self.history = user_history
        self.calculate_baselines()
    
    def calculate_baselines(self):
        """Calculate user's typical trading behavior"""
        self.avg_position_size = statistics.mean(
            [trade['sol_amount'] for trade in self.history]
        )
        self.typical_hold_times = [
            trade['hold_minutes'] for trade in self.history 
            if trade['pnl_usd'] > 0  # Winners only
        ]
        self.avg_winner_hold = statistics.mean(self.typical_hold_times) if self.typical_hold_times else 0
        
    def check_repeat_token(self, token_address: str) -> Optional[Dict]:
        """Check if user has traded this token before"""
        previous_trades = [
            trade for trade in self.history 
            if trade['token_address'] == token_address
        ]
        
        if len(previous_trades) >= 3:  # Pattern threshold
            total_pnl = sum(t['pnl_usd'] for t in previous_trades)
            win_rate = len([t for t in previous_trades if t['pnl_usd'] > 0]) / len(previous_trades)
            
            return {
                'pattern': 'repeat_token',
                'times_traded': len(previous_trades),
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'token_symbol': previous_trades[0]['token_symbol']
            }
        return None
    
    def check_position_size(self, sol_amount: float) -> Optional[Dict]:
        """Check if position size is unusual"""
        if sol_amount > self.avg_position_size * 2.5:
            # Look at historical performance with large positions
            large_positions = [
                trade for trade in self.history 
                if trade['sol_amount'] > self.avg_position_size * 2
            ]
            if large_positions:
                large_win_rate = len([t for t in large_positions if t['pnl_usd'] > 0]) / len(large_positions)
                normal_win_rate = len([t for t in self.history if t['pnl_usd'] > 0]) / len(self.history)
                
                return {
                    'pattern': 'oversized_position',
                    'size_multiple': sol_amount / self.avg_position_size,
                    'large_position_win_rate': large_win_rate,
                    'normal_win_rate': normal_win_rate
                }
        return None
    
    def check_hold_time(self, entry_time: datetime, current_time: datetime) -> Optional[Dict]:
        """Check if holding past typical exit window"""
        minutes_held = (current_time - entry_time).total_seconds() / 60
        
        if self.avg_winner_hold > 0 and minutes_held > self.avg_winner_hold * 1.5:
            # Check what happens when they hold too long
            long_holds = [
                trade for trade in self.history 
                if trade['hold_minutes'] > self.avg_winner_hold
            ]
            if long_holds:
                long_hold_pnl = statistics.mean([t['pnl_percent'] for t in long_holds])
                
                return {
                    'pattern': 'overholding',
                    'current_hold_minutes': minutes_held,
                    'typical_winner_exit': self.avg_winner_hold,
                    'long_hold_avg_pnl': long_hold_pnl
                }
        return None


class NudgeGenerator:
    """Generates evidence-based nudges from detected patterns"""
    
    NUDGE_TEMPLATES = {
        'repeat_token': {
            'losing': "📊 Pattern Alert: You've bought {token_symbol} {times_traded} times before.\nTotal result: ${total_pnl:,.0f}\nSuccess rate: {win_rate:.0%}\n\nYour call, but the data is clear.",
            'mixed': "📊 History Check: This is {token_symbol} trade #{times_traded} for you.\nPast performance: ${total_pnl:,.0f}\nSuccess rate: {win_rate:.0%}\n\nMake it count."
        },
        'oversized_position': {
            'risky': "🎯 Size Check: This is {size_multiple:.1f}× your average entry.\nYour >2× positions: {large_position_win_rate:.0%} win rate\nYour normal size: {normal_win_rate:.0%} win rate\n\nBig bets haven't been your friend.",
            'neutral': "🎯 Position Size: {size_multiple:.1f}× your typical trade.\nJust making sure this is intentional."
        },
        'overholding': {
            'warning': "⏰ Exit Window: Your winners average {typical_winner_exit:.0f} min holds.\nYou're at {current_hold_minutes:.0f} min now.\n\nPast this point, your avg return is {long_hold_avg_pnl:+.1%}."
        }
    }
    
    def generate_nudge(self, pattern_data: Dict) -> str:
        """Generate appropriate nudge based on pattern"""
        pattern_type = pattern_data['pattern']
        
        if pattern_type == 'repeat_token':
            if pattern_data['total_pnl'] < -100:  # Losing pattern
                template = self.NUDGE_TEMPLATES['repeat_token']['losing']
            else:
                template = self.NUDGE_TEMPLATES['repeat_token']['mixed']
                
        elif pattern_type == 'oversized_position':
            if pattern_data['large_position_win_rate'] < 0.3:  # Poor track record
                template = self.NUDGE_TEMPLATES['oversized_position']['risky']
            else:
                template = self.NUDGE_TEMPLATES['oversized_position']['neutral']
                
        elif pattern_type == 'overholding':
            template = self.NUDGE_TEMPLATES['overholding']['warning']
        
        else:
            return ""
        
        # Format the nudge with pattern data
        return template.format(**pattern_data)


# Example usage
if __name__ == "__main__":
    # Mock user history
    user_history = [
        {'token_address': '0xBONK', 'token_symbol': 'BONK', 'sol_amount': 0.5, 
         'pnl_usd': -450, 'pnl_percent': -0.15, 'hold_minutes': 45},
        {'token_address': '0xBONK', 'token_symbol': 'BONK', 'sol_amount': 0.8, 
         'pnl_usd': -823, 'pnl_percent': -0.22, 'hold_minutes': 72},
        {'token_address': '0xBONK', 'token_symbol': 'BONK', 'sol_amount': 1.2, 
         'pnl_usd': -1205, 'pnl_percent': -0.18, 'hold_minutes': 93},
        # ... more history
    ]
    
    # New trade detected
    new_trade = {
        'token_address': '0xBONK',
        'token_symbol': 'BONK', 
        'sol_amount': 2.5,  # Much larger than usual
        'entry_time': datetime.now() - timedelta(minutes=15)
    }
    
    # Detect patterns
    detector = PatternDetector(user_history)
    nudge_gen = NudgeGenerator()
    
    # Check for repeat token pattern
    repeat_pattern = detector.check_repeat_token(new_trade['token_address'])
    if repeat_pattern:
        nudge = nudge_gen.generate_nudge(repeat_pattern)
        print("NUDGE:", nudge)
        print()
    
    # Check for position size pattern
    size_pattern = detector.check_position_size(new_trade['sol_amount'])
    if size_pattern:
        nudge = nudge_gen.generate_nudge(size_pattern)
        print("NUDGE:", nudge) 