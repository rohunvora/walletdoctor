# transforms.py
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime

def normalize_helius_transactions(transactions: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Transform Helius transaction data into a normalized DataFrame.
    
    Extracts key fields like:
    - Transaction signature
    - Timestamp
    - Fee
    - Token transfers
    - Swap information
    """
    if not transactions:
        return pd.DataFrame()
    
    # Flatten transaction data
    flattened = []
    for tx in transactions:
        base_info = {
            'signature': tx.get('signature'),
            'timestamp': tx.get('timestamp'),  # Keep as Unix timestamp (integer)
            'fee': tx.get('fee'),
            'type': tx.get('type'),
            'source': tx.get('source'),
            'slot': tx.get('slot'),
        }
        
        # Extract token transfers
        if 'tokenTransfers' in tx:
            for transfer in tx['tokenTransfers']:
                record = base_info.copy()
                record.update({
                    'token_mint': transfer.get('mint'),
                    'token_amount': transfer.get('tokenAmount'),
                    'from_address': transfer.get('fromUserAccount'),
                    'to_address': transfer.get('toUserAccount'),
                    'transfer_type': 'token_transfer'
                })
                flattened.append(record)
        
        # Extract native transfers
        if 'nativeTransfers' in tx:
            for transfer in tx['nativeTransfers']:
                record = base_info.copy()
                record.update({
                    'native_amount': transfer.get('amount'),
                    'from_address': transfer.get('fromUserAccount'),
                    'to_address': transfer.get('toUserAccount'),
                    'transfer_type': 'native_transfer'
                })
                flattened.append(record)
        
        # If no transfers, still include base transaction
        if not flattened or all(r['signature'] != tx.get('signature') for r in flattened):
            flattened.append(base_info)
    
    df = pd.DataFrame(flattened)
    
    # Keep timestamp as integer (Unix timestamp)
    # Don't convert to datetime to avoid DuckDB conversion issues
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_numeric(df['timestamp'], errors='coerce').fillna(0).astype('int64')
    
    return df

def normalize_cielo_pnl(pnl_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Transform Cielo PnL data into a normalized DataFrame.
    
    Extracts:
    - Token information
    - Realized PnL
    - Unrealized PnL
    - Average buy/sell prices
    - Token holdings
    """
    if not pnl_data or 'tokens' not in pnl_data:
        return pd.DataFrame()
    
    tokens = pnl_data['tokens']
    
    # Map Cielo API fields to our database schema
    normalized_tokens = []
    for token in tokens:
        normalized_token = {
            'mint': token.get('token_address', ''),
            'symbol': token.get('token_symbol', ''),
            'realizedPnl': token.get('total_pnl_usd', 0),
            'unrealizedPnl': token.get('unrealized_pnl_usd', 0),
            'totalPnl': token.get('total_pnl_usd', 0) + token.get('unrealized_pnl_usd', 0),
            'avgBuyPrice': token.get('average_buy_price', 0),
            'avgSellPrice': token.get('average_sell_price', 0),
            'quantity': token.get('holding_amount', 0),
            'totalBought': token.get('total_buy_amount', 0),
            'totalSold': token.get('total_sell_amount', 0),
            'holdTimeSeconds': token.get('holding_time_seconds', 0),
            'numSwaps': token.get('num_swaps', 0)
        }
        normalized_tokens.append(normalized_token)
    
    df = pd.DataFrame(normalized_tokens)
    
    # Ensure numeric columns are properly typed
    numeric_columns = [
        'realizedPnl', 'unrealizedPnl', 'totalPnl',
        'avgBuyPrice', 'avgSellPrice', 'quantity',
        'totalBought', 'totalSold'
    ]
    
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

def extract_swap_data(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract swap-specific data from transactions.
    
    Identifies swap transactions and extracts:
    - Input token and amount
    - Output token and amount
    - Implied price
    - DEX used
    """
    # Filter for swap transactions
    swap_txs = transactions_df[
        transactions_df['type'].str.contains('swap', case=False, na=False)
    ].copy()
    
    # Additional processing for swap data would go here
    # This is a placeholder for more sophisticated swap extraction
    
    return swap_txs

def calculate_hold_durations(transactions_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate hold durations for each token.
    
    Matches buy and sell transactions to compute:
    - Hold duration in hours/days
    - Entry and exit timestamps
    """
    # Group by token mint
    hold_data = []
    
    for token in transactions_df['token_mint'].unique():
        if pd.isna(token):
            continue
            
        token_txs = transactions_df[
            transactions_df['token_mint'] == token
        ].sort_values('timestamp')
        
        # Simple FIFO matching (can be improved)
        buys = token_txs[token_txs['token_amount'] > 0].copy()
        sells = token_txs[token_txs['token_amount'] < 0].copy()
        
        for _, sell in sells.iterrows():
            # Find corresponding buy
            matching_buys = buys[buys['timestamp'] < sell['timestamp']]
            if not matching_buys.empty:
                buy = matching_buys.iloc[-1]
                # Calculate hold duration from Unix timestamps (in seconds)
                hold_duration = (sell['timestamp'] - buy['timestamp']) / 3600  # Convert to hours
                
                hold_data.append({
                    'token_mint': token,
                    'buy_timestamp': buy['timestamp'],
                    'sell_timestamp': sell['timestamp'],
                    'hold_duration_hours': hold_duration,
                    'buy_signature': buy['signature'],
                    'sell_signature': sell['signature']
                })
    
    return pd.DataFrame(hold_data) 