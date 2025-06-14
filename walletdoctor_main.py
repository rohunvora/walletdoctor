#!/usr/bin/env python3
"""
WalletDoctor - Main Application
Analyzes wallet trading patterns and provides constrained, verifiable insights
"""

import os
import sys
import pandas as pd
import openai
from typing import Dict, Any, Optional

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scripts.data import fetch_cielo_pnl, fetch_helius_transactions
from scripts.transforms import normalize_cielo_pnl, normalize_helius_transactions
from src.walletdoctor.features.realistic_patterns import RealisticPatternDetector
from src.walletdoctor.insights.constrained_synthesizer import ConstrainedSynthesizer, VerifiableClaim


class WalletDoctor:
    """Main application class"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key or os.environ.get('OPENAI_API_KEY')
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
        self.synthesizer = ConstrainedSynthesizer()
        
    def analyze_wallet(self, wallet_address: str) -> Dict[str, Any]:
        """Main analysis function"""
        
        print(f"\n🏥 WalletDoctor Analysis")
        print("=" * 60)
        print(f"Wallet: {wallet_address[:8]}...{wallet_address[-8:]}")
        print("=" * 60)
        
        # Fetch data
        print("\n📊 Fetching wallet data...")
        pnl_df, tx_df = self._fetch_wallet_data(wallet_address)
        
        if pnl_df.empty:
            return {"error": "No trading data found for this wallet"}
        
        # Extract verifiable stats
        print("🔍 Analyzing patterns...")
        stats = self._extract_verifiable_stats(pnl_df)
        
        # Generate verifiable claims
        claims = self.synthesizer.generate_verifiable_insights(stats)
        
        # Generate insight
        print("✍️  Generating insight...")
        insight = self._generate_insight(claims, stats)
        
        return {
            "wallet": wallet_address,
            "stats": stats,
            "claims": claims,
            "insight": insight
        }
    
    def _fetch_wallet_data(self, wallet_address: str) -> tuple:
        """Fetch and normalize wallet data"""
        
        try:
            # Fetch PnL data
            pnl_response = fetch_cielo_pnl(wallet_address)
            if not pnl_response or 'data' not in pnl_response:
                return pd.DataFrame(), pd.DataFrame()
            
            tokens = pnl_response['data']['items']
            print(f"✅ Found {len(tokens)} tokens")
            
            # Normalize data
            pnl_df = normalize_cielo_pnl({'tokens': tokens})
            closed_positions = pnl_df[pnl_df['realizedPnl'] != 0].copy()
            
            # Fetch transaction data (optional)
            tx_df = pd.DataFrame()
            try:
                tx_data = fetch_helius_transactions(wallet_address, limit=100)
                if tx_data:
                    tx_df = normalize_helius_transactions(tx_data)
                    print(f"✅ Found {len(tx_data)} recent transactions")
            except:
                print("ℹ️  Transaction data not available")
            
            return closed_positions, tx_df
            
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            return pd.DataFrame(), pd.DataFrame()
    
    def _extract_verifiable_stats(self, pnl_df: pd.DataFrame) -> Dict[str, Any]:
        """Extract only verifiable statistics"""
        
        winners = pnl_df[pnl_df['realizedPnl'] > 0]
        losers = pnl_df[pnl_df['realizedPnl'] < 0]
        
        # Position size analysis
        try:
            pnl_df['size_quartile'] = pd.qcut(pnl_df['totalBought'], q=4, labels=['Small', 'Medium', 'Large', 'Huge'])
            size_perf = pnl_df.groupby('size_quartile', observed=True)['realizedPnl'].agg(['mean', 'count'])
            
            position_size_data = {
                'small': {
                    'avg_pnl': float(size_perf.loc['Small', 'mean']),
                    'count': int(size_perf.loc['Small', 'count'])
                },
                'large': {
                    'avg_pnl': float(size_perf.loc['Huge', 'mean']),
                    'count': int(size_perf.loc['Huge', 'count'])
                }
            }
        except:
            position_size_data = None
        
        # Quick flips
        quick_flips = pnl_df[pnl_df['holdTimeSeconds'] < 3600]
        
        stats = {
            'total_pnl': float(pnl_df['realizedPnl'].sum()),
            'total_trades': len(pnl_df),
            'winners': len(winners),
            'win_rate': float(len(winners) / len(pnl_df) * 100) if len(pnl_df) > 0 else 0,
            'avg_hold_times': {
                'winners': float(winners['holdTimeSeconds'].mean() / 3600) if len(winners) > 0 else 0,
                'losers': float(losers['holdTimeSeconds'].mean() / 3600) if len(losers) > 0 else 0
            },
            'quick_flip_stats': {
                'count': len(quick_flips),
                'percentage': float(len(quick_flips) / len(pnl_df) * 100),
                'total_pnl': float(quick_flips['realizedPnl'].sum())
            }
        }
        
        if position_size_data:
            stats['position_size_performance'] = position_size_data
            
        return stats
    
    def _generate_insight(self, claims: list, stats: Dict[str, Any]) -> str:
        """Generate insight using GPT-4 or fallback"""
        
        if self.openai_api_key:
            try:
                # Generate constrained prompt
                prompt = self.synthesizer.generate_constrained_prompt(claims, stats)
                
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a trading psychologist who provides insights based only on verifiable data."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=600
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                print(f"⚠️  GPT-4 unavailable: {e}")
        
        # Fallback to template-based insight
        return self._generate_fallback_insight(claims, stats)
    
    def _generate_fallback_insight(self, claims: list, stats: Dict[str, Any]) -> str:
        """Generate insight without AI"""
        
        total_pnl = stats['total_pnl']
        total_trades = stats['total_trades']
        win_rate = stats['win_rate']
        
        # Build insight from claims
        insight_parts = [
            f"You made {total_trades} trades. {100-win_rate:.0f}% of them lost money.",
            ""
        ]
        
        # Add verifiable claims
        for claim in claims[:3]:  # Top 3 claims
            insight_parts.append(f"• {claim.claim}")
        
        insight_parts.extend([
            "",
            f"Total result: ${total_pnl:,.2f}",
            "",
            "The data shows patterns, but only you know the reasons behind them.",
            "",
            "Questions to consider:",
            "• What drives your position sizing decisions?",
            "• Why the difference in hold times between winners and losers?",
            "• Would smaller, more consistent positions change your outcomes?"
        ])
        
        return "\n".join(insight_parts)
    
    def display_results(self, results: Dict[str, Any]):
        """Display analysis results"""
        
        if "error" in results:
            print(f"\n❌ {results['error']}")
            return
        
        print("\n" + "="*60)
        print("📊 ANALYSIS COMPLETE")
        print("="*60)
        
        # Show key stats
        stats = results['stats']
        print(f"\nKey Metrics:")
        print(f"• Total P&L: ${stats['total_pnl']:,.2f}")
        print(f"• Win Rate: {stats['win_rate']:.1f}%")
        print(f"• Total Trades: {stats['total_trades']}")
        
        # Show insight
        print("\n" + "-"*60)
        print("💡 INSIGHT")
        print("-"*60)
        print(results['insight'])
        print("-"*60)


def main():
    """Main entry point"""
    
    # Check for wallet address
    if len(sys.argv) < 2:
        print("Usage: python walletdoctor_main.py <wallet_address>")
        print("Example: python walletdoctor_main.py 34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya")
        return
    
    wallet_address = sys.argv[1]
    
    # Check for API keys
    if not os.environ.get('CIELO_KEY'):
        print("⚠️  Warning: CIELO_KEY not set. Export it to fetch wallet data.")
        return
    
    # Initialize and run
    doctor = WalletDoctor()
    results = doctor.analyze_wallet(wallet_address)
    doctor.display_results(results)


if __name__ == "__main__":
    main() 