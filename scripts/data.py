# data.py
import os
import requests
import duckdb
import pandas as pd
from typing import Optional, Dict, List, Any
from datetime import datetime

# Try to load from .env file if it exists (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed in production, that's OK

# Get API keys from environment
HELIUS_KEY = os.getenv("HELIUS_KEY", "")
CIELO_KEY = os.getenv("CIELO_KEY", "")

# Warn if API keys are missing
if not HELIUS_KEY:
    print("⚠️  Warning: HELIUS_KEY not found in environment variables")
if not CIELO_KEY:
    print("⚠️  Warning: CIELO_KEY not found in environment variables")

def fetch_helius_transactions(
    address: str, 
    before: Optional[str] = None, 
    limit: int = 100
) -> List[Dict[str, Any]]:
    """Fetch decoded transactions from Helius Enhanced Transactions API."""
    if not HELIUS_KEY:
        print(f"❌ HELIUS_KEY is empty!")
        return []
        
    url = f"https://api.helius.xyz/v0/addresses/{address}/transactions"
    params = {"limit": limit, "api-key": HELIUS_KEY}
    if before:
        params["before"] = before
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"❌ Helius API error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text[:200]}...")
        return []

def fetch_cielo_pnl(address: str) -> Dict[str, Any]:
    """Fetch PnL data from Cielo API."""
    if not CIELO_KEY:
        print(f"❌ CIELO_KEY is empty!")
        return {'status': 'error', 'data': {'items': []}}
        
    url = f"https://feed-api.cielo.finance/api/v1/{address}/pnl/tokens"
    headers = {"x-api-key": CIELO_KEY}
    
    all_items = []
    next_object = None
    page_count = 0
    
    # Keep fetching pages until no more data
    while True:
        try:
            params = {}
            if next_object:
                params['next_object'] = next_object
                
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and 'items' in data['data']:
                items = data['data']['items']
                all_items.extend(items)
                page_count += 1
                
                # Check if there's a next page
                paging = data['data'].get('paging', {})
                if paging.get('has_next_page', False):
                    next_object = paging.get('next_object')
                else:
                    break
            else:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Cielo API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text[:200]}...")
            if page_count == 0:
                return {'status': 'error', 'data': {'items': []}}
            else:
                # Return what we have so far
                break
            
    return {'status': 'ok', 'data': {'items': all_items}}

def cache_to_duckdb(
    db_connection: duckdb.DuckDBPyConnection,
    table_name: str,
    data: List[Dict[str, Any]] | pd.DataFrame
) -> None:
    """Store data in DuckDB using parquet intermediary."""
    if isinstance(data, pd.DataFrame):
        df = data
        if df.empty:
            return
    else:
        if not data:
            return
        # Normalize JSON to DataFrame
        df = pd.json_normalize(data, max_level=2)
    
    # Convert all object columns to string to avoid type issues
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
    
    # Don't convert timestamps - keep them as integers
    # This avoids DuckDB conversion issues
    
    # Replace NaN with None for better compatibility
    df = df.where(pd.notnull(df), None)
    
    # For transaction table, ensure we have the expected columns
    if table_name == "tx":
        expected_cols = ['signature', 'timestamp', 'fee', 'type', 'source', 'slot', 
                        'token_mint', 'token_amount', 'native_amount', 
                        'from_address', 'to_address', 'transfer_type']
        # Add missing columns with None
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        # Keep only expected columns in the right order
        df = df[expected_cols]
    
    # For PnL table, ensure we have the expected columns
    elif table_name == "pnl":
        expected_cols = ['mint', 'symbol', 'realizedPnl', 'unrealizedPnl', 
                        'totalPnl', 'avgBuyPrice', 'avgSellPrice', 
                        'quantity', 'totalBought', 'totalSold',
                        'holdTimeSeconds', 'numSwaps']
        # Add missing columns with None
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        # Keep only expected columns in the right order
        df = df[expected_cols]
    
    # For multi-wallet tables, ensure wallet_address is included
    elif table_name == "tx_multi":
        expected_cols = ['wallet_address', 'signature', 'timestamp', 'fee', 'type', 'source', 'slot', 
                        'token_mint', 'token_amount', 'native_amount', 
                        'from_address', 'to_address', 'transfer_type']
        # Add missing columns with None
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        # Keep only expected columns in the right order
        df = df[expected_cols]
        
    elif table_name == "pnl_multi":
        expected_cols = ['wallet_address', 'mint', 'symbol', 'realizedPnl', 'unrealizedPnl', 
                        'totalPnl', 'avgBuyPrice', 'avgSellPrice', 
                        'quantity', 'totalBought', 'totalSold',
                        'holdTimeSeconds', 'numSwaps']
        # Add missing columns with None
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        # Keep only expected columns in the right order
        df = df[expected_cols]
    
    # Direct insert into existing table
    db_connection.execute(f"INSERT INTO {table_name} SELECT * FROM df")

def load_wallet(db: duckdb.DuckDBPyConnection, wallet_address: str) -> bool:
    """Load wallet trades from Helius and Cielo."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting to fetch data for {wallet_address}")
    
    try:
        # Fetch transactions from Helius
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching transactions from Helius...")
        tx_data = fetch_helius_transactions(wallet_address, limit=100)
        
        if tx_data:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(tx_data)} transactions")
            # Normalize and store transaction data
            from scripts.normalize import normalize_helius_transactions
            tx_df = normalize_helius_transactions(tx_data)
            # Clear existing data for this wallet
            try:
                db.execute(f"DELETE FROM tx WHERE from_address = '{wallet_address}' OR to_address = '{wallet_address}'")
            except:
                pass  # Table might not exist yet
            # Store normalized data
            cache_to_duckdb(db, "tx", tx_df.to_dict('records'))
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No transactions found from Helius")
        
        # Fetch PnL data from Cielo
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching PnL from Cielo...")
        pnl_data = fetch_cielo_pnl(wallet_address)
        
        if pnl_data and 'data' in pnl_data and 'items' in pnl_data.get('data', {}):
            tokens = pnl_data['data']['items']
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Found PnL for {len(tokens)} tokens")
            
            # Normalize and store PnL data
            from scripts.normalize import normalize_cielo_pnl
            pnl_df = normalize_cielo_pnl({'tokens': tokens})
            # Clear existing PnL data
            try:
                db.execute("DELETE FROM pnl")
            except:
                pass
            # Store PnL data
            cache_to_duckdb(db, "pnl", pnl_df.to_dict('records'))
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Data stored successfully")
            return True
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No PnL data found from Cielo")
            return False if not tx_data else True  # Return True if we at least got transactions
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error loading wallet: {str(e)}")
        import traceback
        traceback.print_exc()
        return False 