# data.py
import os
import requests
import duckdb
import pandas as pd
from typing import Optional, Dict, List, Any

HELIUS_KEY = os.environ.get("HELIUS_KEY", "")
CIELO_KEY = os.environ.get("CIELO_KEY", "")

def fetch_helius_transactions(
    address: str, 
    before: Optional[str] = None, 
    limit: int = 500
) -> List[Dict[str, Any]]:
    """Fetch decoded transactions from Helius Enhanced Transactions API."""
    url = f"https://api.helius.xyz/v0/addresses/{address}/transactions"
    params = {"limit": limit, "api-key": HELIUS_KEY}
    if before:
        params["before"] = before
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def fetch_cielo_pnl(address: str) -> Dict[str, Any]:
    """Fetch PnL data from Cielo API."""
    url = f"https://feed-api.cielo.finance/api/v1/{address}/pnl/tokens"
    headers = {"x-api-key": CIELO_KEY}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def cache_to_duckdb(
    db_connection: duckdb.DuckDBPyConnection,
    table_name: str,
    data: List[Dict[str, Any]]
) -> None:
    """Store data in DuckDB using parquet intermediary."""
    if not data:
        return
    
    # Normalize JSON to DataFrame
    df = pd.json_normalize(data, max_level=2)
    
    # Convert all object columns to string to avoid type issues
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].astype(str)
    
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
                        'quantity', 'totalBought', 'totalSold']
        # Add missing columns with None
        for col in expected_cols:
            if col not in df.columns:
                df[col] = None
        # Keep only expected columns in the right order
        df = df[expected_cols]
    
    # Direct insert into existing table
    db_connection.execute(f"INSERT INTO {table_name} SELECT * FROM df") 