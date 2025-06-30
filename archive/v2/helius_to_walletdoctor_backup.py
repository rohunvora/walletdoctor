#!/usr/bin/env python3
"""
Transform Helius Enhanced Transactions API data to WalletDoctor CSV format.
FIXED VERSION: Proper number formatting and percentage-based fees.
"""

import csv
import requests
import time
import sys
import os
from datetime import datetime
from collections import defaultdict
import json

# Get API key from environment
API_KEY = os.getenv("HELIUS_KEY")
if not API_KEY:
    print("Error: HELIUS_KEY environment variable not set")
    print("Get your free key at https://dev.helius.xyz/")
    sys.exit(1)

# Token mint addresses for common tokens
TOKEN_MINTS = {
    "So11111111111111111111111111111111111111112": "SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
}

def get_token_symbol(mint_address):
    """Get token symbol from mint address, fallback to shortened address."""
    return TOKEN_MINTS.get(mint_address, mint_address[:6] + "...")

def fetch_transactions(wallet, before_sig=None):
    """Fetch a page of transactions from Helius API."""
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
    params = {
        "api-key": API_KEY,
        "limit": 100,
        "type": "SWAP"
    }
    if before_sig:
        params["before"] = before_sig
    
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        return []

def calculate_trade_metrics(trades_by_token):
    """Calculate P&L for each token based on FIFO accounting."""
    results = []
    
    for token, trades in trades_by_token.items():
        holdings = []  # FIFO queue of (amount, price) tuples
        
        for trade in sorted(trades, key=lambda x: x['timestamp']):
            if trade['action'] == 'buy':
                holdings.append((trade['amount'], trade['price']))
                trade['pnl_usd'] = 0.0
            else:  # sell
                remaining_to_sell = trade['amount']
                total_cost_basis = 0.0
                
                while remaining_to_sell > 0 and holdings:
                    holding_amount, holding_price = holdings[0]
                    
                    if holding_amount <= remaining_to_sell:
                        total_cost_basis += holding_amount * holding_price
                        remaining_to_sell -= holding_amount
                        holdings.pop(0)
                    else:
                        total_cost_basis += remaining_to_sell * holding_price
                        holdings[0] = (holding_amount - remaining_to_sell, holding_price)
                        remaining_to_sell = 0
                
                revenue = trade['amount'] * trade['price']
                trade['pnl_usd'] = revenue - total_cost_basis
            
            results.append(trade)
    
    return sorted(results, key=lambda x: x['timestamp'])

def transform_helius_to_walletdoctor(wallet, output_file):
    """Main transformation function."""
    print(f"Fetching swap transactions for wallet: {wallet}")
    print(f"Output file: {output_file}")
    
    all_trades = []
    trades_by_token = defaultdict(list)
    last_sig = None
    page_count = 0
    
    while True:
        page_count += 1
        print(f"Fetching page {page_count}...")
        
        transactions = fetch_transactions(wallet, last_sig)
        if not transactions:
            break
        
        for tx in transactions:
            if tx.get("transactionError"):
                continue
            
            events = tx.get("events", {})
            swap = events.get("swap")
            if not swap:
                continue
            
            native_input = swap.get("nativeInput", {})
            native_output = swap.get("nativeOutput", {})
            token_inputs = swap.get("tokenInputs", [])
            token_outputs = swap.get("tokenOutputs", [])
            
            # Get SOL price from transaction (if available)
            sol_price = 150.0  # Default fallback
            
            if native_input and token_outputs:
                # Buying token with SOL
                for token_out in token_outputs:
                    sol_amount = float(native_input['amount']) / 1e9
                    token_amount = float(token_out['rawTokenAmount']['tokenAmount']) / (10 ** token_out['rawTokenAmount']['decimals'])
                    value_usd = sol_amount * sol_price
                    
                    trade = {
                        'timestamp': datetime.fromtimestamp(tx['timestamp']).isoformat(),
                        'action': 'buy',
                        'token': get_token_symbol(token_out['mint']),
                        'amount': token_amount,
                        'price': value_usd / token_amount if token_amount > 0 else 0,
                        'value_usd': value_usd,
                        'pnl_usd': 0.0,
                        'fees_usd': value_usd * 0.003  # 0.3% fee
                    }
                    
                    all_trades.append(trade)
                    trades_by_token[trade['token']].append(trade)
            
            elif token_inputs and native_output:
                # Selling token for SOL
                for token_in in token_inputs:
                    sol_amount = float(native_output['amount']) / 1e9
                    token_amount = float(token_in['rawTokenAmount']['tokenAmount']) / (10 ** token_in['rawTokenAmount']['decimals'])
                    value_usd = sol_amount * sol_price
                    
                    trade = {
                        'timestamp': datetime.fromtimestamp(tx['timestamp']).isoformat(),
                        'action': 'sell',
                        'token': get_token_symbol(token_in['mint']),
                        'amount': token_amount,
                        'price': value_usd / token_amount if token_amount > 0 else 0,
                        'value_usd': value_usd,
                        'pnl_usd': 0.0,  # Will calculate with FIFO
                        'fees_usd': value_usd * 0.003  # 0.3% fee
                    }
                    
                    all_trades.append(trade)
                    trades_by_token[trade['token']].append(trade)
            
            elif token_inputs and token_outputs:
                # Token-to-token swap
                # For USDC and stablecoins, use $1 as price
                for i, (token_in, token_out) in enumerate(zip(token_inputs[:1], token_outputs[:1])):
                    amount_in = float(token_in['rawTokenAmount']['tokenAmount']) / (10 ** token_in['rawTokenAmount']['decimals'])
                    amount_out = float(token_out['rawTokenAmount']['tokenAmount']) / (10 ** token_out['rawTokenAmount']['decimals'])
                    
                    # For USDC, use actual amount as value
                    token_in_symbol = get_token_symbol(token_in['mint'])
                    token_out_symbol = get_token_symbol(token_out['mint'])
                    
                    if token_in_symbol == 'USDC':
                        value_usd = amount_in
                    elif token_out_symbol == 'USDC':
                        value_usd = amount_out
                    else:
                        # Estimate value for other tokens
                        value_usd = 100.0  # Placeholder
                    
                    # Sell side
                    sell_trade = {
                        'timestamp': datetime.fromtimestamp(tx['timestamp']).isoformat(),
                        'action': 'sell',
                        'token': token_in_symbol,
                        'amount': amount_in,
                        'price': value_usd / amount_in if amount_in > 0 else 0,
                        'value_usd': value_usd,
                        'pnl_usd': 0.0,
                        'fees_usd': value_usd * 0.003 / 2  # Split fee
                    }
                    
                    # Buy side
                    buy_trade = {
                        'timestamp': datetime.fromtimestamp(tx['timestamp']).isoformat(),
                        'action': 'buy',
                        'token': token_out_symbol,
                        'amount': amount_out,
                        'price': value_usd / amount_out if amount_out > 0 else 0,
                        'value_usd': value_usd,
                        'pnl_usd': 0.0,
                        'fees_usd': value_usd * 0.003 / 2  # Split fee
                    }
                    
                    all_trades.append(sell_trade)
                    all_trades.append(buy_trade)
                    trades_by_token[sell_trade['token']].append(sell_trade)
                    trades_by_token[buy_trade['token']].append(buy_trade)
        
        if len(transactions) < 100:
            break
        
        last_sig = transactions[-1]['signature']
        time.sleep(0.11)
    
    print(f"Fetched {len(all_trades)} trades across {page_count} pages")
    
    # Calculate P&L using FIFO
    print("Calculating P&L...")
    trades_with_pnl = calculate_trade_metrics(trades_by_token)
    
    # Format all numeric values properly
    for trade in trades_with_pnl:
        trade['amount'] = round(trade['amount'], 8)  # Keep precision for tokens
        trade['price'] = round(trade['price'], 6)
        trade['value_usd'] = round(trade['value_usd'], 2)
        trade['pnl_usd'] = round(trade['pnl_usd'], 2)
        trade['fees_usd'] = round(trade['fees_usd'], 2)
    
    # Write to CSV
    print(f"Writing to {output_file}...")
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'timestamp', 'action', 'token', 'amount', 'price', 
            'value_usd', 'pnl_usd', 'fees_usd'
        ])
        writer.writeheader()
        writer.writerows(trades_with_pnl)
    
    print(f"✓ Successfully wrote {len(trades_with_pnl)} trades to {output_file}")
    
    # Summary stats
    total_pnl = sum(t['pnl_usd'] for t in trades_with_pnl if t['action'] == 'sell')
    total_fees = sum(t['fees_usd'] for t in trades_with_pnl)
    print(f"\nSummary:")
    print(f"  Total P&L: ${total_pnl:,.2f}")
    print(f"  Total Fees: ${total_fees:,.2f}")
    print(f"  Net Result: ${(total_pnl - total_fees):,.2f}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python helius_to_walletdoctor_fixed.py <wallet_address> [output_file.csv]")
        sys.exit(1)
    
    wallet = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else f"{wallet[:8]}_trades.csv"
    
    try:
        transform_helius_to_walletdoctor(wallet, output_file)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 