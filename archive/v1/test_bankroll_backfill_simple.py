#!/usr/bin/env python3

import json
from datetime import datetime, timedelta

def test_bankroll_backfill_logic():
    """Test the bankroll backfill logic with sample data"""
    
    print("=== BANKROLL BACKFILL LOGIC TEST ===")
    print("Testing reverse calculation approach\n")
    
    # Sample current balance
    current_balance = 28.5  # SOL
    
    # Sample trades (newest to oldest)
    sample_trades = [
        # Recent trades WITH bankroll data (after June 18)
        {
            'timestamp': datetime(2025, 6, 25, 14, 30),
            'action': 'buy',
            'token_symbol': 'BONK',
            'sol_amount': 2.5,
            'bankroll_before_sol': 31.0,  # Actual recorded
            'trade_pct_bankroll': 8.06  # Actual recorded
        },
        {
            'timestamp': datetime(2025, 6, 24, 10, 15),
            'action': 'sell',
            'token_symbol': 'POPCAT',
            'sol_amount': 1.8,  # Received from sell
            'bankroll_before_sol': 29.2,  # Actual recorded
            'trade_pct_bankroll': None  # N/A for sells
        },
        
        # Older trades WITHOUT bankroll data (before June 18)
        {
            'timestamp': datetime(2025, 6, 15, 18, 45),
            'action': 'buy',
            'token_symbol': 'WIF',
            'sol_amount': 5.0,
            'bankroll_before_sol': None,  # Missing
            'trade_pct_bankroll': None  # Missing
        },
        {
            'timestamp': datetime(2025, 6, 10, 9, 30),
            'action': 'buy',
            'token_symbol': 'PEPE',
            'sol_amount': 3.2,
            'bankroll_before_sol': None,  # Missing
            'trade_pct_bankroll': None  # Missing
        },
        {
            'timestamp': datetime(2025, 6, 5, 16, 20),
            'action': 'sell',
            'token_symbol': 'DOGE',
            'sol_amount': 2.1,  # Received
            'bankroll_before_sol': None,  # Missing
            'trade_pct_bankroll': None  # Missing
        }
    ]
    
    print(f"Current SOL balance: {current_balance:.4f} SOL\n")
    
    print("Sample trades (newest to oldest):")
    print("-" * 100)
    print(f"{'Date':<12} {'Time':<8} {'Action':<6} {'Token':<8} {'SOL':<10} {'Recorded BR':<12} {'Recorded %':<10}")
    print("-" * 100)
    
    for trade in sample_trades:
        date_str = trade['timestamp'].strftime('%Y-%m-%d')
        time_str = trade['timestamp'].strftime('%H:%M')
        br_str = f"{trade['bankroll_before_sol']:.2f}" if trade['bankroll_before_sol'] else "MISSING"
        pct_str = f"{trade['trade_pct_bankroll']:.1f}%" if trade['trade_pct_bankroll'] else "MISSING"
        
        print(f"{date_str:<12} {time_str:<8} {trade['action']:<6} {trade['token_symbol']:<8} "
              f"{trade['sol_amount']:<10.4f} {br_str:<12} {pct_str:<10}")
    
    print("\n" + "="*100)
    print("BACKFILL CALCULATION (working backwards from current balance)")
    print("="*100)
    
    # Start with current balance and work backwards
    calculated_balance = current_balance
    backfill_results = []
    
    print(f"\nStarting point: {calculated_balance:.4f} SOL (current balance)")
    print("-" * 100)
    
    for trade in sample_trades:
        print(f"\nProcessing: {trade['timestamp'].strftime('%Y-%m-%d %H:%M')} - "
              f"{trade['action'].upper()} {trade['token_symbol']}")
        
        # Calculate what the balance was BEFORE this trade
        if trade['action'] == 'buy':
            # For buys: we spent SOL, so add it back to get previous balance
            calculated_balance += trade['sol_amount']
            print(f"  → Spent {trade['sol_amount']:.4f} SOL, so previous balance was: {calculated_balance:.4f} SOL")
        else:  # sell
            # For sells: we received SOL, so subtract it to get previous balance
            calculated_balance -= trade['sol_amount']
            print(f"  → Received {trade['sol_amount']:.4f} SOL, so previous balance was: {calculated_balance:.4f} SOL")
        
        # Calculate position size for buys
        if trade['action'] == 'buy':
            calc_position_pct = (trade['sol_amount'] / calculated_balance) * 100
            print(f"  → Position size: {trade['sol_amount']:.4f} / {calculated_balance:.4f} = {calc_position_pct:.1f}%")
        
        # Compare with actual data if available
        if trade['bankroll_before_sol'] is not None:
            diff = calculated_balance - trade['bankroll_before_sol']
            print(f"  ✓ Validation: Recorded bankroll was {trade['bankroll_before_sol']:.4f} SOL")
            print(f"               Difference: {diff:+.4f} SOL ({abs(diff/trade['bankroll_before_sol']*100):.1f}% error)")
            
            if trade['trade_pct_bankroll'] and trade['action'] == 'buy':
                print(f"               Recorded position %: {trade['trade_pct_bankroll']:.1f}%")
        else:
            print(f"  ⚠️  No recorded bankroll data - would backfill with {calculated_balance:.4f} SOL")
            if trade['action'] == 'buy':
                print(f"     Would set position size to {calc_position_pct:.1f}%")
        
        # Store for summary
        backfill_results.append({
            'trade': trade,
            'calculated_bankroll': calculated_balance,
            'calculated_position_pct': calc_position_pct if trade['action'] == 'buy' else None
        })
    
    print("\n" + "="*100)
    print("BACKFILL SUMMARY")
    print("="*100)
    
    print("\nTrades that would be updated:")
    print("-" * 80)
    
    for result in backfill_results:
        trade = result['trade']
        if trade['bankroll_before_sol'] is None:
            date_str = trade['timestamp'].strftime('%Y-%m-%d %H:%M')
            print(f"\n{date_str} - {trade['action'].upper()} {trade['token_symbol']}")
            print(f"  bankroll_before_sol: NULL → {result['calculated_bankroll']:.4f}")
            
            if trade['action'] == 'buy':
                print(f"  trade_pct_bankroll: NULL → {result['calculated_position_pct']:.1f}%")
                print(f"  bankroll_after_sol: NULL → {result['calculated_bankroll'] - trade['sol_amount']:.4f}")
    
    print("\n" + "="*100)
    print("IMPORTANT CAVEATS")
    print("="*100)
    print("\n⚠️  This simple approach has limitations:")
    print("1. Assumes no SOL transfers in/out (deposits/withdrawals)")
    print("2. Doesn't account for:")
    print("   - Staking/unstaking SOL")
    print("   - Failed transactions")
    print("   - SOL used for transaction fees")
    print("   - Wrapped SOL (WSOL) conversions")
    print("\n✅ For accurate backfill, we need:")
    print("1. Full transaction history from Helius API")
    print("2. Track ALL SOL movements, not just trades")
    print("3. Build complete balance timeline")
    print("4. Validate against known checkpoints")
    
    print("\n" + "="*100)
    print("EXAMPLE: Position Sizing Insights After Backfill")
    print("="*100)
    
    # Calculate some insights
    buy_trades = [r for r in backfill_results if r['trade']['action'] == 'buy']
    if buy_trades:
        position_sizes = [r['calculated_position_pct'] for r in buy_trades]
        avg_position = sum(position_sizes) / len(position_sizes)
        max_position = max(position_sizes)
        
        print(f"\nBased on backfilled data:")
        print(f"- Average position size: {avg_position:.1f}% of bankroll")
        print(f"- Largest position: {max_position:.1f}% of bankroll")
        print(f"- Number of trades analyzed: {len(position_sizes)}")
        
        risky_trades = [r for r in buy_trades if r['calculated_position_pct'] > 15]
        if risky_trades:
            print(f"\n⚠️  Risky trades (>15% of bankroll): {len(risky_trades)}")
            for r in risky_trades:
                trade = r['trade']
                print(f"   - {trade['timestamp'].strftime('%Y-%m-%d')} {trade['token_symbol']}: "
                      f"{r['calculated_position_pct']:.1f}%")

if __name__ == "__main__":
    test_bankroll_backfill_logic()