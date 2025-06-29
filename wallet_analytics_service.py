"""
WalletDoctor Analytics Microservice
Pure metrics calculation from CSV trading data
No blockchain dependencies, just math and insights
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import json
import hashlib
from dataclasses import dataclass, asdict


@dataclass
class TradingMetrics:
    """Core trading metrics structure"""
    # P&L Metrics
    total_pnl: float
    win_rate: float
    profit_factor: float
    largest_win: float
    largest_loss: float
    avg_win: float
    avg_loss: float
    sharpe_ratio: float
    
    # Fee Analysis
    total_fees: float
    fee_percentage: float  # fees as % of volume
    fee_drag_on_pnl: float  # how much fees reduced profits
    
    # Timing Analysis  
    avg_hold_time_minutes: float
    avg_winner_hold_time: float
    avg_loser_hold_time: float
    best_trading_hours: List[int]  # hours of day with best performance
    overtrading_score: float  # % of trades within 5 min of previous
    
    # Risk Metrics
    max_drawdown: float
    position_sizing_consistency: float  # coefficient of variation
    risk_reward_ratio: float
    consecutive_losses_max: int
    
    # Psychological Patterns
    revenge_trading_score: float  # % losses within 30min of previous loss
    fomo_score: float  # % buys at local highs
    patience_score: float  # ability to hold winners
    tilt_periods: List[Dict[str, Any]]  # periods of unusual behavior


class WalletAnalytics:
    """Core analytics engine for trading data"""
    
    REQUIRED_COLUMNS = [
        'timestamp', 'action', 'token', 'amount', 'price', 
        'value_usd', 'pnl_usd', 'fees_usd'
    ]
    
    def __init__(self):
        self.df = None
        self.metrics = None
        
    def validate_csv(self, df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        """Validate CSV has required columns and data types"""
        # Check required columns
        missing = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing:
            return False, f"Missing required columns: {missing}"
            
        # Validate data types
        try:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['amount'] = pd.to_numeric(df['amount'])
            df['price'] = pd.to_numeric(df['price'])
            df['value_usd'] = pd.to_numeric(df['value_usd'])
            df['pnl_usd'] = pd.to_numeric(df['pnl_usd'], errors='coerce').fillna(0)
            df['fees_usd'] = pd.to_numeric(df['fees_usd'])
        except Exception as e:
            return False, f"Data type validation failed: {str(e)}"
            
        # Check for valid actions
        valid_actions = {'buy', 'sell', 'swap_in', 'swap_out'}
        invalid_actions = set(df['action'].str.lower()) - valid_actions
        if invalid_actions:
            return False, f"Invalid actions found: {invalid_actions}"
            
        return True, None
        
    def process_csv(self, csv_path: str) -> Dict[str, Any]:
        """Process CSV and return comprehensive analytics"""
        try:
            # Load CSV
            df = pd.read_csv(csv_path)
            
            # Validate
            valid, error = self.validate_csv(df)
            if not valid:
                return {"error": error}
                
            # Clean and prepare data
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['action'] = df['action'].str.lower()
            df = df.sort_values('timestamp')
            
            # Calculate metrics
            self.df = df
            self.metrics = self._calculate_all_metrics()
            
            # Generate report structure
            report = self._generate_report()
            
            return report
            
        except Exception as e:
            return {"error": f"Processing failed: {str(e)}"}
    
    def _calculate_all_metrics(self) -> TradingMetrics:
        """Calculate all trading metrics"""
        df = self.df
        
        # Filter for completed trades (sells only)
        sells = df[df['action'].isin(['sell', 'swap_out'])]
        
        # P&L Metrics
        total_pnl = sells['pnl_usd'].sum()
        winners = sells[sells['pnl_usd'] > 0]
        losers = sells[sells['pnl_usd'] < 0]
        
        win_rate = (len(winners) / len(sells) * 100) if len(sells) > 0 else 0
        
        total_wins = winners['pnl_usd'].sum() if len(winners) > 0 else 0
        total_losses = abs(losers['pnl_usd'].sum()) if len(losers) > 0 else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        largest_win = winners['pnl_usd'].max() if len(winners) > 0 else 0
        largest_loss = abs(losers['pnl_usd'].min()) if len(losers) > 0 else 0
        avg_win = winners['pnl_usd'].mean() if len(winners) > 0 else 0
        avg_loss = abs(losers['pnl_usd'].mean()) if len(losers) > 0 else 0
        
        # Sharpe Ratio (simplified daily)
        daily_pnl = sells.groupby(sells['timestamp'].dt.date)['pnl_usd'].sum()
        sharpe_ratio = (daily_pnl.mean() / daily_pnl.std() * np.sqrt(252)) if daily_pnl.std() > 0 else 0
        
        # Fee Analysis
        total_fees = df['fees_usd'].sum()
        total_volume = df['value_usd'].sum()
        fee_percentage = (total_fees / total_volume * 100) if total_volume > 0 else 0
        fee_drag_on_pnl = (total_fees / (total_pnl + total_fees) * 100) if (total_pnl + total_fees) > 0 else 0
        
        # Timing Analysis
        hold_times = self._calculate_hold_times()
        avg_hold_time = hold_times.mean() if len(hold_times) > 0 else 0
        
        winner_holds = self._calculate_hold_times(winners_only=True)
        loser_holds = self._calculate_hold_times(losers_only=True)
        avg_winner_hold = winner_holds.mean() if len(winner_holds) > 0 else 0
        avg_loser_hold = loser_holds.mean() if len(loser_holds) > 0 else 0
        
        best_hours = self._find_best_trading_hours()
        overtrading = self._calculate_overtrading_score()
        
        # Risk Metrics
        max_dd = self._calculate_max_drawdown()
        position_consistency = self._calculate_position_sizing_consistency()
        risk_reward = avg_win / avg_loss if avg_loss > 0 else float('inf')
        max_consecutive_losses = self._calculate_max_consecutive_losses()
        
        # Psychological Patterns
        revenge_score = self._calculate_revenge_trading_score()
        fomo = self._calculate_fomo_score()
        patience = self._calculate_patience_score()
        tilt_periods = self._identify_tilt_periods()
        
        return TradingMetrics(
            total_pnl=total_pnl,
            win_rate=win_rate,
            profit_factor=profit_factor,
            largest_win=largest_win,
            largest_loss=largest_loss,
            avg_win=avg_win,
            avg_loss=avg_loss,
            sharpe_ratio=sharpe_ratio,
            total_fees=total_fees,
            fee_percentage=fee_percentage,
            fee_drag_on_pnl=fee_drag_on_pnl,
            avg_hold_time_minutes=avg_hold_time,
            avg_winner_hold_time=avg_winner_hold,
            avg_loser_hold_time=avg_loser_hold,
            best_trading_hours=best_hours,
            overtrading_score=overtrading,
            max_drawdown=max_dd,
            position_sizing_consistency=position_consistency,
            risk_reward_ratio=risk_reward,
            consecutive_losses_max=max_consecutive_losses,
            revenge_trading_score=revenge_score,
            fomo_score=fomo,
            patience_score=patience,
            tilt_periods=tilt_periods
        )
    
    def _calculate_hold_times(self, winners_only=False, losers_only=False) -> pd.Series:
        """Calculate hold times for trades in minutes"""
        # Group by token to match buys and sells
        hold_times = []
        
        for token in self.df['token'].unique():
            token_df = self.df[self.df['token'] == token].copy()
            token_df = token_df.sort_values('timestamp')
            
            buy_time = None
            for _, row in token_df.iterrows():
                if row['action'] in ['buy', 'swap_in']:
                    buy_time = row['timestamp']
                elif row['action'] in ['sell', 'swap_out'] and buy_time:
                    hold_time = (row['timestamp'] - buy_time).total_seconds() / 60
                    
                    # Filter by PnL if requested
                    if winners_only and row['pnl_usd'] <= 0:
                        continue
                    if losers_only and row['pnl_usd'] > 0:
                        continue
                        
                    hold_times.append(hold_time)
                    buy_time = None
                    
        return pd.Series(hold_times) if hold_times else pd.Series([0])
    
    def _find_best_trading_hours(self) -> List[int]:
        """Find hours of day with best performance"""
        df = self.df[self.df['action'].isin(['sell', 'swap_out'])]
        df['hour'] = df['timestamp'].dt.hour
        
        hourly_pnl = df.groupby('hour')['pnl_usd'].agg(['sum', 'count'])
        hourly_pnl['avg_pnl'] = hourly_pnl['sum'] / hourly_pnl['count']
        
        # Return top 3 hours by average PnL
        best_hours = hourly_pnl.nlargest(3, 'avg_pnl').index.tolist()
        return best_hours
    
    def _calculate_overtrading_score(self) -> float:
        """Calculate % of trades within 5 minutes of previous trade"""
        df = self.df.sort_values('timestamp')
        
        rapid_trades = 0
        for i in range(1, len(df)):
            time_diff = (df.iloc[i]['timestamp'] - df.iloc[i-1]['timestamp']).total_seconds() / 60
            if time_diff <= 5:
                rapid_trades += 1
                
        return (rapid_trades / (len(df) - 1) * 100) if len(df) > 1 else 0
    
    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from peak"""
        sells = self.df[self.df['action'].isin(['sell', 'swap_out'])].copy()
        sells['cumulative_pnl'] = sells['pnl_usd'].cumsum()
        sells['running_max'] = sells['cumulative_pnl'].cummax()
        sells['drawdown'] = sells['cumulative_pnl'] - sells['running_max']
        
        return abs(sells['drawdown'].min()) if len(sells) > 0 else 0
    
    def _calculate_position_sizing_consistency(self) -> float:
        """Calculate coefficient of variation for position sizes"""
        buys = self.df[self.df['action'].isin(['buy', 'swap_in'])]
        
        if len(buys) == 0:
            return 0
            
        sizes = buys['value_usd']
        cv = (sizes.std() / sizes.mean() * 100) if sizes.mean() > 0 else 0
        return cv
    
    def _calculate_max_consecutive_losses(self) -> int:
        """Find maximum consecutive losing trades"""
        sells = self.df[self.df['action'].isin(['sell', 'swap_out'])].sort_values('timestamp')
        
        max_consecutive = 0
        current_consecutive = 0
        
        for _, row in sells.iterrows():
            if row['pnl_usd'] < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
                
        return max_consecutive
    
    def _calculate_revenge_trading_score(self) -> float:
        """Calculate % of losses within 30min of previous loss"""
        losses = self.df[(self.df['action'].isin(['sell', 'swap_out'])) & 
                        (self.df['pnl_usd'] < 0)].sort_values('timestamp')
        
        if len(losses) < 2:
            return 0
            
        revenge_count = 0
        for i in range(1, len(losses)):
            time_diff = (losses.iloc[i]['timestamp'] - losses.iloc[i-1]['timestamp']).total_seconds() / 60
            if time_diff <= 30:
                revenge_count += 1
                
        return (revenge_count / (len(losses) - 1) * 100)
    
    def _calculate_fomo_score(self) -> float:
        """Calculate % of buys at high prices (top 20% of recent range)"""
        buys = self.df[self.df['action'].isin(['buy', 'swap_in'])].copy()
        
        fomo_count = 0
        for _, buy in buys.iterrows():
            # Look at price action in previous 24h
            recent_start = buy['timestamp'] - timedelta(hours=24)
            token_recent = self.df[(self.df['token'] == buy['token']) & 
                                  (self.df['timestamp'] >= recent_start) &
                                  (self.df['timestamp'] < buy['timestamp'])]
            
            if len(token_recent) > 0:
                price_range = token_recent['price'].max() - token_recent['price'].min()
                if price_range > 0:
                    percentile = (buy['price'] - token_recent['price'].min()) / price_range
                    if percentile > 0.8:  # Buying in top 20% of range
                        fomo_count += 1
                        
        return (fomo_count / len(buys) * 100) if len(buys) > 0 else 0
    
    def _calculate_patience_score(self) -> float:
        """Score based on ability to hold winners longer than losers"""
        winner_holds = self._calculate_hold_times(winners_only=True)
        loser_holds = self._calculate_hold_times(losers_only=True)
        
        if len(winner_holds) == 0 or len(loser_holds) == 0:
            return 50  # Neutral score
            
        avg_winner = winner_holds.mean()
        avg_loser = loser_holds.mean()
        
        # Score from 0-100, where 100 means holding winners 2x longer than losers
        ratio = avg_winner / avg_loser if avg_loser > 0 else 2
        score = min(100, ratio * 50)
        
        return score
    
    def _identify_tilt_periods(self) -> List[Dict[str, Any]]:
        """Identify periods of unusual trading behavior"""
        tilt_periods = []
        
        # Look for rapid-fire loss sequences
        sells = self.df[self.df['action'].isin(['sell', 'swap_out'])].sort_values('timestamp')
        
        i = 0
        while i < len(sells) - 2:
            # Check for 3+ losses in 1 hour
            if sells.iloc[i]['pnl_usd'] < 0:
                end_idx = i
                total_loss = sells.iloc[i]['pnl_usd']
                
                for j in range(i + 1, min(i + 5, len(sells))):
                    time_diff = (sells.iloc[j]['timestamp'] - sells.iloc[i]['timestamp']).total_seconds() / 3600
                    if time_diff <= 1 and sells.iloc[j]['pnl_usd'] < 0:
                        end_idx = j
                        total_loss += sells.iloc[j]['pnl_usd']
                    else:
                        break
                        
                if end_idx - i >= 2:  # 3+ losses
                    tilt_periods.append({
                        'start': sells.iloc[i]['timestamp'].isoformat(),
                        'end': sells.iloc[end_idx]['timestamp'].isoformat(),
                        'trades': end_idx - i + 1,
                        'total_loss': total_loss,
                        'type': 'rapid_losses'
                    })
                    i = end_idx + 1
                    continue
                    
            i += 1
            
        return tilt_periods
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate structured report for GPT consumption"""
        metrics = asdict(self.metrics)
        
        # Calculate additional summary stats
        total_trades = len(self.df[self.df['action'].isin(['sell', 'swap_out'])])
        
        # Anonymize wallet addresses
        wallet_hash = hashlib.sha256(str(self.df.iloc[0].to_dict()).encode()).hexdigest()[:8]
        
        report = {
            'wallet_id': wallet_hash,
            'summary': {
                'total_pnl_usd': round(metrics['total_pnl'], 2),
                'total_trades': total_trades,
                'win_rate_pct': round(metrics['win_rate'], 1),
                'profit_factor': round(metrics['profit_factor'], 2),
                'sharpe_ratio': round(metrics['sharpe_ratio'], 2)
            },
            'pnl_analysis': {
                'total_profit_loss': round(metrics['total_pnl'], 2),
                'largest_win': round(metrics['largest_win'], 2),
                'largest_loss': round(metrics['largest_loss'], 2),
                'average_win': round(metrics['avg_win'], 2),
                'average_loss': round(metrics['avg_loss'], 2),
                'win_rate': round(metrics['win_rate'], 1),
                'profit_factor': round(metrics['profit_factor'], 2),
                'risk_reward_ratio': round(metrics['risk_reward_ratio'], 2)
            },
            'fee_analysis': {
                'total_fees_paid': round(metrics['total_fees'], 2),
                'fees_as_pct_of_volume': round(metrics['fee_percentage'], 2),
                'fee_impact_on_profits': round(metrics['fee_drag_on_pnl'], 1),
                'recommendation': self._get_fee_recommendation(metrics)
            },
            'timing_analysis': {
                'avg_hold_time_minutes': round(metrics['avg_hold_time_minutes'], 0),
                'winner_avg_hold_time': round(metrics['avg_winner_hold_time'], 0),
                'loser_avg_hold_time': round(metrics['avg_loser_hold_time'], 0),
                'best_performance_hours': metrics['best_trading_hours'],
                'overtrading_score': round(metrics['overtrading_score'], 1),
                'recommendation': self._get_timing_recommendation(metrics)
            },
            'risk_analysis': {
                'max_drawdown': round(metrics['max_drawdown'], 2),
                'position_sizing_variance': round(metrics['position_sizing_consistency'], 1),
                'max_consecutive_losses': metrics['consecutive_losses_max'],
                'recommendation': self._get_risk_recommendation(metrics)
            },
            'psychological_analysis': {
                'revenge_trading_tendency': round(metrics['revenge_trading_score'], 1),
                'fomo_tendency': round(metrics['fomo_score'], 1),
                'patience_score': round(metrics['patience_score'], 1),
                'tilt_periods_identified': len(metrics['tilt_periods']),
                'recommendation': self._get_psych_recommendation(metrics)
            },
            'metadata': {
                'analysis_timestamp': datetime.now().isoformat(),
                'data_completeness': 'full',
                'warnings': []
            }
        }
        
        return report
    
    def _get_fee_recommendation(self, metrics: Dict) -> str:
        """Generate fee-related recommendation"""
        if metrics['fee_percentage'] > 1:
            return "High fee burn detected. Consider larger positions or different venues."
        elif metrics['fee_drag_on_pnl'] > 30:
            return "Fees eating significant profits. Focus on higher conviction trades."
        else:
            return "Fee management acceptable."
    
    def _get_timing_recommendation(self, metrics: Dict) -> str:
        """Generate timing-related recommendation"""
        if metrics['overtrading_score'] > 20:
            return "Overtrading detected. Space out entries for better decisions."
        elif metrics['avg_loser_hold_time'] > metrics['avg_winner_hold_time']:
            return "Holding losers longer than winners. Cut losses quicker."
        else:
            return "Timing discipline looks good."
    
    def _get_risk_recommendation(self, metrics: Dict) -> str:
        """Generate risk-related recommendation"""
        if metrics['position_sizing_consistency'] > 50:
            return "Inconsistent position sizing. Develop systematic sizing rules."
        elif metrics['consecutive_losses_max'] > 5:
            return "Long losing streaks detected. Add stop-loss rules."
        else:
            return "Risk management within normal bounds."
    
    def _get_psych_recommendation(self, metrics: Dict) -> str:
        """Generate psychology-related recommendation"""
        if metrics['revenge_trading_score'] > 30:
            return "Revenge trading pattern detected. Take breaks after losses."
        elif metrics['fomo_score'] > 40:
            return "FOMO buying at peaks. Wait for pullbacks to enter."
        elif len(metrics['tilt_periods']) > 0:
            return f"Identified {len(metrics['tilt_periods'])} tilt periods. Walk away when tilted."
        else:
            return "Psychological discipline maintained."


# API function for external use
def analyze_trading_csv(csv_path: str) -> Dict[str, Any]:
    """Main entry point for CSV analysis"""
    analyzer = WalletAnalytics()
    return analyzer.process_csv(csv_path)


if __name__ == "__main__":
    # Example usage
    import sys
    if len(sys.argv) > 1:
        result = analyze_trading_csv(sys.argv[1])
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python wallet_analytics_service.py <csv_file>")
