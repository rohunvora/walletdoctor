# data.py
import os
import requests
import duckdb
import pandas as pd
from typing import Optional, Dict, List, Any

# Try to load from .env file if it exists (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed in production, that's OK

# Get API keys from environment
HELIUS_KEY = os.getenv("HELIUS_KEY", "")
CIELO_KEY = os.getenv("CIELO_KEY", "")

# Debug logging
print(f"Debug: HELIUS_KEY loaded: {'Yes' if HELIUS_KEY else 'No'} (length: {len(HELIUS_KEY)})")
print(f"Debug: CIELO_KEY loaded: {'Yes' if CIELO_KEY else 'No'} (length: {len(CIELO_KEY)})")

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
    
    print(f"Debug: Calling Helius API: {url}")
    print(f"Debug: API key present: {'Yes' if params.get('api-key') else 'No'}")
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        print(f"Debug: Helius API response status: {response.status_code}")
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
    
    print(f"Debug: Calling Cielo API: {url}")
    print(f"Debug: API key present in headers: {'Yes' if headers.get('x-api-key') else 'No'}")
    
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
            
            print(f"Debug: Cielo API response status: {response.status_code}")
            
            if 'data' in data and 'items' in data['data']:
                items = data['data']['items']
                all_items.extend(items)
                page_count += 1
                
                # Check if there's a next page
                paging = data['data'].get('paging', {})
                if paging.get('has_next_page', False):
                    next_object = paging.get('next_object')
                    print(f"  Fetched page {page_count} ({len(items)} tokens), next_object: {next_object}")
                else:
                    print(f"  Fetched final page {page_count} ({len(items)} tokens)")
                    break
            else:
                print(f"Debug: Unexpected Cielo response structure: {list(data.keys())}")
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
            
    print(f"  Total tokens fetched: {len(all_items)}")
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
    
    # Convert timestamp columns to int64 if they exist
    timestamp_cols = ['timestamp']
    for col in timestamp_cols:
        if col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col]):
            # Convert to Unix timestamp in seconds (as int)
            df[col] = df[col].astype('int64') // 10**9
    
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