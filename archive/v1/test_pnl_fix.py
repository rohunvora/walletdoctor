#!/usr/bin/env python3
"""
Test the P&L calculation fix
Verifies that open positions show correct unrealized P&L, not 100% loss
"""

import asyncio
import json
from diary_api import calculate_token_pnl_from_trades

async def test_pnl_calculation():
    """Test P&L calculation for MDOG position"""
    
    # Your wallet address from the architect's test
    wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
    token = "MDOG"
    
    print("Testing P&L calculation for MDOG position...")
    print("=" * 60)
    
    # Get P&L from the fixed function
    result = await calculate_token_pnl_from_trades(wallet, token)
    
    if 'error' in result:
        print(f"Error: {result['error']}")
        return
    
    # Display results
    print(f"Token: {result['token_symbol']}")
    print(f"Total trades: {result['total_trades']} ({result['buy_trades']} buys, {result['sell_trades']} sells)")
    print(f"\nInvestment:")
    print(f"  Total bought: {result['total_bought_sol']:.4f} SOL (${result['total_bought_sol'] * result['sol_price_usd']:.2f})")
    print(f"  Total sold: {result['total_sold_sol']:.4f} SOL (${result['total_sold_sol'] * result['sol_price_usd']:.2f})")
    print(f"  Remaining tokens: {result['remaining_tokens']:,.0f}")
    
    print(f"\nCurrent Value:")
    print(f"  Current value: {result['current_value_sol']:.4f} SOL (${result['current_value_usd']:.2f})")
    
    print(f"\nP&L Breakdown:")
    print(f"  Realized P&L: {result['realized_pnl_sol']:.4f} SOL (${result['realized_pnl_usd']:.2f})")
    print(f"  Unrealized P&L: {result['unrealized_pnl_sol']:.4f} SOL (${result['unrealized_pnl_usd']:.2f})")
    print(f"  Total P&L: {result['net_pnl_sol']:.4f} SOL (${result['net_pnl_usd']:.2f})")
    
    # Calculate percentage
    if result['total_bought_sol'] > 0:
        pnl_pct = (result['net_pnl_sol'] / result['total_bought_sol']) * 100
        print(f"  P&L %: {pnl_pct:.2f}%")
    
    print("\n" + "=" * 60)
    
    # Validate the fix
    if result['is_closed_position']:
        print("✓ Position is closed - using realized P&L only")
    else:
        if result['current_value_sol'] > 0:
            print("✓ Open position - correctly calculating unrealized P&L from current price")
            
            # Verify it's not showing 100% loss
            total_invested_usd = result['total_bought_sol'] * result['sol_price_usd']
            if abs(result['net_pnl_usd']) >= total_invested_usd * 0.99:
                print("✗ WARNING: Still showing near 100% loss!")
            else:
                actual_loss_pct = (result['net_pnl_usd'] / total_invested_usd) * 100
                print(f"✓ Showing actual loss of {actual_loss_pct:.1f}% (not 100%)")
        else:
            print("✗ WARNING: Could not fetch current price - may show incorrect P&L")

if __name__ == "__main__":
    asyncio.run(test_pnl_calculation())