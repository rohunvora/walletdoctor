#!/usr/bin/env python3
"""
Transform Helius Enhanced Transactions API data to WalletDoctor CSV format.
V2: Fixed source filtering and real price data integration.
"""

import csv
import requests
import time
import sys
import os
from datetime import datetime
from collections import defaultdict
import json

# Get API keys from environment
HELIUS_KEY = os.getenv("HELIUS_KEY")
BIRDEYE_KEY = os.getenv("BIRDEYE_API_KEY")

if not HELIUS_KEY:
    print("Error: HELIUS_KEY environment variable not set")
    print("Get your free key at https://dev.helius.xyz/")
    sys.exit(1)

# DEX sources to query
DEX_SOURCES = ["JUPITER", "RAYDIUM", "ORCA", "PHOENIX", "LIFINITY", "METEORA"]

# Token mint addresses for common tokens
TOKEN_MINTS = {
    "So11111111111111111111111111111111111111112": "SOL",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
}

# Price cache to reduce API calls
price_cache = {}

def get_token_symbol(mint_address):
    """Get token symbol from mint address, fallback to shortened address."""
    return TOKEN_MINTS.get(mint_address, mint_address[:6] + "...")

def get_usd_price(mint, timestamp):
    """Get USD price for a token at a specific timestamp using Birdeye API."""
    # Check cache first
    cache_key = f"{mint}_{timestamp}"
    if cache_key in price_cache:
        return price_cache[cache_key]
    
    # Default prices for stablecoins
    if mint == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":  # USDC
        return 1.0
    if mint == "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB":  # USDT
        return 1.0
    
    # If no Birdeye key, use fallback prices
    if not BIRDEYE_KEY:
        if mint == "So11111111111111111111111111111111111111112":  # SOL
            return 150.0  # Fallback SOL price
        return None
    
    # Query Birdeye API
    try:
        url = f"https://public-api.birdeye.so/defi/historical_price_unix"
        params = {
            "address": mint,
            "type": "1m",
            "time_from": timestamp - 60,
            "time_to": timestamp + 60
        }
        headers = {"X-API-KEY": BIRDEYE_KEY}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and data["data"].get("items"):
                price = float(data["data"]["items"][0]["value"])
                price_cache[cache_key] = price
                return price
    except Exception as e:
        print(f"Price API error for {mint}: {e}")
    
    return None

def fetch_transactions(wallet, source, before_sig=None):
    """Fetch a page of transactions from Helius API for a specific DEX source."""
    url = f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
    params = {
        "api-key": HELIUS_KEY,
        "limit": 100,
        "source": source  # Proper filter by DEX source
    }
    if before_sig:
        params["before"] = before_sig
    
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Error for {source}: {e}")
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
    
    if BIRDEYE_KEY:
        print("Using Birdeye API for real-time prices")
    else:
        print("Warning: BIRDEYE_API_KEY not set, using fallback prices")
    
    all_trades = []
    trades_by_token = defaultdict(list)
    
    # Loop through each DEX source
    for dex in DEX_SOURCES:
        print(f"\nQuerying {dex}...")
        last_sig = None
        page_count = 0
        dex_trades = 0
        
        while True:
            page_count += 1
            
            transactions = fetch_transactions(wallet, dex, last_sig)
            if not transactions:
                break
            
            for tx in transactions:
                if tx.get("transactionError"):
                    continue
                
                # Get transaction details
                timestamp = tx['timestamp']
                events = tx.get("events", {})
                swap = events.get("swap")
                if not swap:
                    continue
                
                native_input = swap.get("nativeInput", {})
                native_output = swap.get("nativeOutput", {})
                token_inputs = swap.get("tokenInputs", [])
                token_outputs = swap.get("tokenOutputs", [])
                
                # Get SOL price at transaction time
                sol_mint = "So11111111111111111111111111111111111111112"
                sol_price = get_usd_price(sol_mint, timestamp)
                if not sol_price:
                    sol_price = 150.0  # Fallback
                
                if native_input and token_outputs:
                    # Buying token with SOL
                    for token_out in token_outputs:
                        sol_amount = float(native_input['amount']) / 1e9
                        token_amount = float(token_out['rawTokenAmount']['tokenAmount']) / (10 ** token_out['rawTokenAmount']['decimals'])
                        value_usd = sol_amount * sol_price
                        
                        trade = {
                            'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
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
                        dex_trades += 1
                
                elif token_inputs and native_output:
                    # Selling token for SOL
                    for token_in in token_inputs:
                        sol_amount = float(native_output['amount']) / 1e9
                        token_amount = float(token_in['rawTokenAmount']['tokenAmount']) / (10 ** token_in['rawTokenAmount']['decimals'])
                        value_usd = sol_amount * sol_price
                        
                        trade = {
                            'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
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
                        dex_trades += 1
                
                elif token_inputs and token_outputs:
                    # Token-to-token swap
                    for i, (token_in, token_out) in enumerate(zip(token_inputs[:1], token_outputs[:1])):
                        amount_in = float(token_in['rawTokenAmount']['tokenAmount']) / (10 ** token_in['rawTokenAmount']['decimals'])
                        amount_out = float(token_out['rawTokenAmount']['tokenAmount']) / (10 ** token_out['rawTokenAmount']['decimals'])
                        
                        # Get prices for both tokens
                        price_in = get_usd_price(token_in['mint'], timestamp)
                        price_out = get_usd_price(token_out['mint'], timestamp)
                        
                        # Calculate value_usd
                        if price_in:
                            value_usd = amount_in * price_in
                        elif price_out:
                            value_usd = amount_out * price_out
                        else:
                            # Fallback for stablecoins
                            token_in_symbol = get_token_symbol(token_in['mint'])
                            token_out_symbol = get_token_symbol(token_out['mint'])
                            
                            if token_in_symbol == 'USDC' or token_in_symbol == 'USDT':
                                value_usd = amount_in
                            elif token_out_symbol == 'USDC' or token_out_symbol == 'USDT':
                                value_usd = amount_out
                            else:
                                continue  # Skip if we can't determine value
                        
                        # Sell side
                        sell_trade = {
                            'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                            'action': 'sell',
                            'token': get_token_symbol(token_in['mint']),
                            'amount': amount_in,
                            'price': value_usd / amount_in if amount_in > 0 else 0,
                            'value_usd': value_usd,
                            'pnl_usd': 0.0,
                            'fees_usd': value_usd * 0.003 / 2  # Split fee
                        }
                        
                        # Buy side
                        buy_trade = {
                            'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                            'action': 'buy',
                            'token': get_token_symbol(token_out['mint']),
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
                        dex_trades += 2
            
            if len(transactions) < 100:
                break
            
            last_sig = transactions[-1]['signature']
            time.sleep(0.11)  # Rate limit
        
        print(f"  Found {dex_trades} trades on {dex}")
    
    print(f"\nTotal: {len(all_trades)} trades across all DEXes")
    
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
        print("Usage: python helius_to_walletdoctor_v2.py <wallet_address> [output_file.csv]")
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