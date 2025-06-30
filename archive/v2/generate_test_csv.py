"""
Generate test CSV for WalletDoctor Analytics
Creates a sample trading CSV with realistic data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_test_csv(num_trades=100, output_file='test_trades.csv'):
    """Generate a test CSV with realistic trading data"""
    
    # Token pool
    tokens = ['SOL', 'BONK', 'WIF', 'POPCAT', 'MYRO', 'WEN', 'SLERF', 'BOME']
    
    # Start date
    start_date = datetime.now() - timedelta(days=30)
    
    trades = []
    current_positions = {}
    
    for i in range(num_trades * 2):  # Generate buys and sells
        # Random timestamp
        timestamp = start_date + timedelta(
            days=random.uniform(0, 30),
            hours=random.uniform(0, 24),
            minutes=random.uniform(0, 60)
        )
        
        # Pick a token
        token = random.choice(tokens)
        
        # Determine action
        if token not in current_positions:
            action = 'buy'
        elif random.random() < 0.5:
            action = 'buy'
        else:
            action = 'sell'
        
        # Generate price (with some momentum)
        base_price = random.uniform(0.001, 10)
        if action == 'buy':
            price = base_price * random.uniform(0.95, 1.05)
        else:
            price = base_price * random.uniform(0.90, 1.10)
        
        # Amount and value
        amount = random.uniform(10, 1000)
        value_usd = amount * price
        
        # Calculate PnL for sells
        pnl_usd = 0
        if action == 'sell' and token in current_positions:
            avg_buy_price = current_positions[token]['avg_price']
            pnl_usd = (price - avg_buy_price) * amount
            
            # Update position
            current_positions[token]['amount'] -= amount
            if current_positions[token]['amount'] <= 0:
                del current_positions[token]
        elif action == 'buy':
            # Update position
            if token not in current_positions:
                current_positions[token] = {'amount': 0, 'total_cost': 0}
            
            current_positions[token]['amount'] += amount
            current_positions[token]['total_cost'] += value_usd
            current_positions[token]['avg_price'] = (
                current_positions[token]['total_cost'] / 
                current_positions[token]['amount']
            )
        
        # Fees (0.1-0.5% of value)
        fees_usd = value_usd * random.uniform(0.001, 0.005)
        
        trade = {
            'timestamp': timestamp,
            'action': action,
            'token': token,
            'amount': amount,
            'price': price,
            'value_usd': value_usd,
            'pnl_usd': pnl_usd,
            'fees_usd': fees_usd
        }
        
        trades.append(trade)
    
    # Create DataFrame and sort by timestamp
    df = pd.DataFrame(trades)
    df = df.sort_values('timestamp')
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    
    # Print summary
    sells = df[df['action'] == 'sell']
    total_pnl = sells['pnl_usd'].sum()
    win_rate = (sells['pnl_usd'] > 0).mean() * 100
    
    print(f"Generated {len(df)} trades")
    print(f"Total P&L: ${total_pnl:.2f}")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Saved to: {output_file}")
    
    return df

if __name__ == "__main__":
    generate_test_csv()
