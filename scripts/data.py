# data.py
import os
import requests
import duckdb
import pandas as pd
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta

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

def fetch_cielo_pnl(address: str, max_items: int = 1000) -> Dict[str, Any]:
    """Fetch PnL data from Cielo API."""
    if not CIELO_KEY:
        print(f"❌ CIELO_KEY is empty!")
        return {'status': 'error', 'data': {'items': []}}
    
    # Debug logging for API key
    print(f"[{datetime.now().strftime('%H:%M:%S')}] CIELO_KEY length: {len(CIELO_KEY)}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] CIELO_KEY first 8 chars: {CIELO_KEY[:8]}...")
        
    # Special logging for problematic wallet
    if address == "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm":
        print(f"[{datetime.now().strftime('%H:%M:%S')}] DEBUG: Fetching data for known problematic wallet")
        
    url = f"https://feed-api.cielo.finance/api/v1/{address}/pnl/tokens"
    headers = {"x-api-key": CIELO_KEY}
    
    all_items = []
    next_object = None
    page_count = 0
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching Cielo PnL data for {address}")
    
    # Keep fetching pages until no more data or max items reached
    while True:
        try:
            params = {}
            if next_object:
                params['next_object'] = next_object
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching page {page_count + 1}...")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Special debug for problematic wallet
            if address == "DNfuF1L62WWyW3pNakVkyGGFzVVhj4Yr52jSmdTyeBHm" and page_count == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] DEBUG: First page response keys: {list(data.keys())}")
                if 'data' in data:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] DEBUG: Data keys: {list(data['data'].keys())}")
                    if 'items' in data['data']:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] DEBUG: Items length: {len(data['data']['items'])}")
            
            if 'data' in data and 'items' in data['data']:
                items = data['data']['items']
                all_items.extend(items)
                page_count += 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Page {page_count}: {len(items)} items (total: {len(all_items)})")
                
                # Check if we've reached the max items limit
                if len(all_items) >= max_items:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Reached max items limit ({max_items}), stopping")
                    all_items = all_items[:max_items]
                    break
                
                # Check if there's a next page
                paging = data['data'].get('paging', {})
                if paging.get('has_next_page', False):
                    next_object = paging.get('next_object')
                    # Limit pages to prevent infinite loops
                    if page_count >= 50:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Reached page limit (50), stopping")
                        break
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
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cielo fetch complete: {len(all_items)} total items")
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

def load_wallet(
    db: duckdb.DuckDBPyConnection,
    wallet_address: str,
    mode: str = "full"
) -> bool:
    """Load wallet data based on mode."""
    
    print(f"[DEBUG] load_wallet called with wallet={wallet_address}, mode={mode}")
    print(f"[DEBUG] HELIUS_KEY exists: {bool(os.getenv('HELIUS_KEY'))}")
    print(f"[DEBUG] CIELO_KEY exists: {bool(os.getenv('CIELO_KEY'))}")
    print(f"[DEBUG] CIELO_KEY length: {len(os.getenv('CIELO_KEY', ''))}")
    
    # Check if we already have data in pnl table (no wallet column means it's pre-loaded)
    tables = [t[0] for t in db.execute("SHOW TABLES").fetchall()]
    
    if 'pnl' in tables:
        # Check if pnl table has data
        count = db.execute("SELECT COUNT(*) FROM pnl").fetchone()[0]
        if count > 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Using existing data ({count} trades)")
            return True
    
    if 'trades' in tables:
        # Check if trades table has data for this wallet
        count = db.execute(
            "SELECT COUNT(*) FROM trades WHERE wallet = ?", 
            [wallet_address]
        ).fetchone()[0]
        if count > 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Using existing trades data ({count} trades)")
            return True
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting to fetch data for {wallet_address} in {mode} mode")
    
    # If HELIUS_KEY or CIELO_KEY are missing, we can't fetch new data
    if not os.getenv("HELIUS_KEY") or not os.getenv("CIELO_KEY"):
        print("❌ API keys missing - using existing data only")
        print(f"[DEBUG] HELIUS_KEY: {os.getenv('HELIUS_KEY', 'NOT SET')[:8]}..." if os.getenv('HELIUS_KEY') else "[DEBUG] HELIUS_KEY: NOT SET")
        print(f"[DEBUG] CIELO_KEY: {os.getenv('CIELO_KEY', 'NOT SET')[:8]}..." if os.getenv('CIELO_KEY') else "[DEBUG] CIELO_KEY: NOT SET")
        # Return True if we have any data, False otherwise
        if 'pnl' in tables or 'trades' in tables:
            return True
        return False
    
    try:
        # Set limits based on mode
        max_items = 1000 if mode == 'instant' else 5000
        
        # Fetch transactions from Helius
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching transactions from Helius...")
        tx_data = fetch_helius_transactions(wallet_address, limit=100)
        
        if tx_data:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(tx_data)} transactions")
            # Normalize and store transaction data
            try:
                from scripts.transforms import normalize_helius_transactions
            except ModuleNotFoundError:
                from transforms import normalize_helius_transactions
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
        
        # Use smart fetch for PnL data from Cielo
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Using smart fetch for Cielo data...")
        trading_stats, aggregated_pnl, pnl_data = fetch_cielo_pnl_smart(wallet_address, mode=mode)
        
        print(f"[DEBUG] trading_stats status: {trading_stats.get('status')}")
        print(f"[DEBUG] aggregated_pnl status: {aggregated_pnl.get('status')}")
        print(f"[DEBUG] pnl_data status: {pnl_data.get('status') if pnl_data else 'None'}")
        
        # Store aggregated PnL if available (this has the best summary data!)
        if aggregated_pnl.get('status') == 'ok' and 'data' in aggregated_pnl:
            # Create aggregated_stats table if needed
            db.execute("""
                CREATE TABLE IF NOT EXISTS aggregated_stats (
                    wallet_address TEXT,
                    tokens_traded INTEGER,
                    win_rate DOUBLE,
                    realized_pnl DOUBLE,
                    unrealized_pnl DOUBLE,
                    combined_pnl DOUBLE,
                    realized_roi DOUBLE,
                    unrealized_roi DOUBLE,
                    combined_roi DOUBLE,
                    total_buy_usd DOUBLE,
                    total_sell_usd DOUBLE,
                    avg_holding_time_seconds BIGINT,
                    data_timestamp TIMESTAMP
                )
            """)
            
            agg = aggregated_pnl['data']
            db.execute("""
                INSERT INTO aggregated_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                wallet_address,
                agg.get('tokens_traded', 0),
                agg.get('winrate', 0) / 100.0,  # Convert percentage to decimal
                agg.get('realized_pnl_usd', 0),
                agg.get('unrealized_pnl_usd', 0),
                agg.get('combined_pnl_usd', 0),
                agg.get('realized_roi_percentage', 0) / 100.0,
                agg.get('unrealized_roi_percentage', 0) / 100.0,
                agg.get('combined_roi_percentage', 0) / 100.0,
                agg.get('total_buy_usd', 0),
                agg.get('total_sell_usd', 0),
                agg.get('average_holding_time_seconds', 0),
                datetime.now()
            ])
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Stored aggregated stats")
        
        # Store window info if pagination was used
        if pnl_data and 'data' in pnl_data and 'window_info' in pnl_data.get('data', {}):
            # Create window_info table if needed
            db.execute("""
                CREATE TABLE IF NOT EXISTS data_window_info (
                    wallet_address TEXT PRIMARY KEY,
                    timeframe TEXT,
                    window_description TEXT,
                    pages_fetched INTEGER,
                    has_losers BOOLEAN,
                    warning_message TEXT,
                    data_timestamp TIMESTAMP
                )
            """)
            
            window_info = pnl_data['data']['window_info']
            items = pnl_data['data'].get('items', [])
            pnls = [item.get('total_pnl_usd', 0) for item in items]
            has_losers = any(p < 0 for p in pnls) if pnls else False
            
            # Delete existing record for this wallet
            db.execute("DELETE FROM data_window_info WHERE wallet_address = ?", [wallet_address])
            
            db.execute("""
                INSERT INTO data_window_info VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [
                wallet_address,
                window_info.get('timeframe', 'max'),
                window_info.get('window_description', 'all-time'),
                window_info.get('pages_fetched', 1),
                has_losers,
                pnl_data['data'].get('warning', ''),
                datetime.now()
            ])
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Stored window info: {window_info.get('window_description')} (pages: {window_info.get('pages_fetched', 1)})")
        
        # Store trading stats if available (kept for compatibility)
        if trading_stats.get('status') == 'ok' and 'data' in trading_stats:
            # Create trading_stats table if needed
            db.execute("""
                CREATE TABLE IF NOT EXISTS trading_stats (
                    wallet_address TEXT,
                    total_trades INTEGER,
                    win_rate DOUBLE,
                    total_pnl DOUBLE,
                    realized_pnl DOUBLE,
                    unrealized_pnl DOUBLE,
                    roi DOUBLE,
                    avg_trade_size DOUBLE,
                    largest_win DOUBLE,
                    largest_loss DOUBLE,
                    data_timestamp TIMESTAMP
                )
            """)
            
            stats = trading_stats['data']
            # Map the actual field names from the API
            swaps_count = stats.get('swaps_count', 0)
            pnl = stats.get('pnl', 0)
            winrate = stats.get('winrate', 0)
            
            db.execute("""
                INSERT INTO trading_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                wallet_address,
                swaps_count,
                winrate,
                pnl,
                0,  # realized_pnl not provided separately
                0,  # unrealized_pnl not provided separately
                0,  # roi not provided
                stats.get('average_buy_amount_usd', 0),
                0,  # largest_win not provided
                0,  # largest_loss not provided
                datetime.now()
            ])
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Stored trading stats")
        
        if pnl_data and 'data' in pnl_data and 'items' in pnl_data.get('data', {}):
            tokens = pnl_data['data']['items']
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Found PnL for {len(tokens)} tokens")
            
            if len(tokens) == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] WARNING: Cielo returned 0 tokens for wallet {wallet_address}")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] This might be a new wallet or one with no trading history")
                print(f"[DEBUG] Full pnl_data response: {pnl_data}")
                return False
            
            # Check if we hit the limit
            if len(tokens) >= max_items:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] WARNING: Hit max items limit ({max_items} tokens)")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] This wallet likely has more trading data than we can process in instant mode")
            
            # Normalize and store PnL data
            try:
                from scripts.transforms import normalize_cielo_pnl
            except ModuleNotFoundError:
                from transforms import normalize_cielo_pnl
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
            print(f"[{datetime.now().strftime('%H:%M:%S')}] API Response structure: {list(pnl_data.keys()) if pnl_data else 'None'}")
            if pnl_data and 'data' in pnl_data:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Data keys: {list(pnl_data['data'].keys())}")
            print(f"[DEBUG] Full pnl_data: {pnl_data}")
            return False if not tx_data else True  # Return True if we at least got transactions
            
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error loading wallet: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def fetch_cielo_trading_stats(address: str) -> Dict[str, Any]:
    """Fetch trading statistics from Cielo API - overall performance summary."""
    if not CIELO_KEY:
        print(f"❌ CIELO_KEY is empty!")
        return {'status': 'error', 'data': {}}
    
    url = f"https://feed-api.cielo.finance/api/v1/{address}/trading-stats"
    headers = {"x-api-key": CIELO_KEY}
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching trading stats for {address}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Got trading stats successfully")
        return data
    except requests.exceptions.RequestException as e:
        print(f"❌ Cielo Trading Stats API error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text[:200]}...")
        return {'status': 'error', 'data': {}}

def fetch_cielo_aggregated_pnl(address: str) -> Dict[str, Any]:
    """Fetch aggregated PnL stats from Cielo API."""
    if not CIELO_KEY:
        print(f"❌ CIELO_KEY is empty!")
        return {'status': 'error', 'data': {}}
    
    url = f"https://feed-api.cielo.finance/api/v1/{address}/pnl/total-stats"
    headers = {"x-api-key": CIELO_KEY}
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching aggregated PnL for {address}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Got aggregated PnL successfully")
        return data
    except requests.exceptions.RequestException as e:
        print(f"❌ Cielo Aggregated PnL API error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text[:200]}...")
        return {'status': 'error', 'data': {}}

def fetch_cielo_pnl_with_timeframe(address: str, timeframe: str = "max", max_pages: int = 10) -> Dict[str, Any]:
    """
    Fetch PnL data from Cielo API using timeframe and pagination to surface losers.
    
    Args:
        address: Wallet address
        timeframe: One of "1d", "7d", "30d", "max" (defaults to "max")
        max_pages: Maximum pages to fetch (default 10)
    
    Returns:
        Dict with status and data including all items from paginated results
    """
    if not CIELO_KEY:
        print(f"❌ CIELO_KEY is empty!")
        return {'status': 'error', 'data': {'items': [], 'timeframe': timeframe}}
    
    url = f"https://feed-api.cielo.finance/api/v1/{address}/pnl/tokens"
    headers = {"x-api-key": CIELO_KEY}
    
    all_items = []
    next_object = None
    page_count = 0
    found_losers = 0
    TOP_N_LOSERS = 5  # Stop when we find 5 losers
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching Cielo PnL data for {address} (timeframe={timeframe})")
    
    while page_count < max_pages:
        # Build params
        params = {"timeframe": timeframe}
        if next_object:
            params['next_object'] = next_object
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and 'items' in data['data']:
                items = data['data']['items']
                page_count += 1
                
                # Add items and count losers
                for item in items:
                    all_items.append(item)
                    if item.get('total_pnl_usd', 0) < 0:
                        found_losers += 1
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Page {page_count}: {len(items)} items, {found_losers} losers found so far")
                
                # Stop if we found enough losers
                if found_losers >= TOP_N_LOSERS:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {found_losers} losers, stopping pagination")
                    break
                
                # Check if there's a next page
                paging = data['data'].get('paging', {})
                next_object = paging.get('next_object')
                
                if not next_object:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No more pages available")
                    break
            else:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Cielo API error: {e}")
            if page_count == 0:
                return {'status': 'error', 'data': {'items': [], 'timeframe': timeframe}}
            else:
                break
    
    return {
        'status': 'ok', 
        'data': {
            'items': all_items,
            'timeframe': timeframe,
            'pages_fetched': page_count,
            'losers_found': found_losers
        }
    }

def fetch_cielo_pnl_stream_losers(address: str) -> Tuple[Dict[str, Any], str]:
    """
    Stream PnL data using pagination to find losers.
    Tries different timeframes: max → 30d → 7d until losers are found.
    
    Returns:
        Tuple of (data dict, timeframe_used)
    """
    TIMEFRAMES = ["max", "30d", "7d", "1d"]
    TOP_N_LOSERS = 5
    
    for timeframe in TIMEFRAMES:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Trying timeframe={timeframe}...")
        
        # For shorter timeframes, we can afford more pages
        max_pages = 10 if timeframe == "max" else 5
        
        data = fetch_cielo_pnl_with_timeframe(address, timeframe, max_pages)
        
        if data.get('status') != 'ok':
            continue
        
        # Count losers in the results
        items = data.get('data', {}).get('items', [])
        losers = [item for item in items if item.get('total_pnl_usd', 0) < 0]
        
        # If we found some losers, we're done
        if len(losers) >= TOP_N_LOSERS or (len(losers) > 0 and timeframe == "1d"):
            winners = len([item for item in items if item.get('total_pnl_usd', 0) > 0])
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Using timeframe={timeframe}: {winners} winners, {len(losers)} losers")
            return data, timeframe
        
        # If this timeframe had no losers but we haven't tried shorter ones, continue
        if timeframe != "1d":
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Not enough losers found, trying shorter timeframe...")
    
    # Return the last attempt
    return data, timeframe

def fetch_cielo_pnl_smart(address: str, mode: str = 'full') -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Smart fetch that gets summary data first, then token data.
    Uses pagination to surface losers on wallets with many winners.
    Returns: (trading_stats, aggregated_pnl, token_pnl)
    """
    # First, get the trading stats (overall performance)
    trading_stats = fetch_cielo_trading_stats(address)
    
    # Get aggregated PnL - this has the best summary data!
    aggregated_pnl = fetch_cielo_aggregated_pnl(address)
    
    # Use pagination to find losers
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Using pagination approach to fetch token PnL...")
    token_data, timeframe_used = fetch_cielo_pnl_stream_losers(address)
    
    # Add window info to the response
    if token_data.get('status') == 'ok' and 'data' in token_data:
        items = token_data['data'].get('items', [])
        losers = [item for item in items if item.get('total_pnl_usd', 0) < 0]
        
        # Build window description
        window_description = {
            "max": "all-time",
            "30d": "last 30 days",
            "7d": "last 7 days", 
            "1d": "last 24 hours"
        }.get(timeframe_used, timeframe_used)
        
        token_data['data']['window_info'] = {
            'timeframe': timeframe_used,
            'window_description': window_description,
            'pages_fetched': token_data['data'].get('pages_fetched', 1)
        }
        
        # Add warning if we still couldn't find losers
        if len(losers) == 0:
            token_data['data']['warning'] = f"No realized losses found in {window_description}. This wallet may genuinely have no losing trades in this period."
        elif len(losers) < 5 and timeframe_used != "max":
            token_data['data']['warning'] = f"Showing {window_description} data. Historical losers outside this period are not displayed."
    
    return trading_stats, aggregated_pnl, token_data

def fetch_cielo_pnl_limited(address: str, max_items: int = 200, max_pages: int = 2, sort: str = 'desc') -> Dict[str, Any]:
    """Fetch limited PnL data from Cielo API with page limit and sorting."""
    if not CIELO_KEY:
        print(f"❌ CIELO_KEY is empty!")
        return {'status': 'error', 'data': {'items': []}}
    
    url = f"https://feed-api.cielo.finance/api/v1/{address}/pnl/tokens"
    headers = {"x-api-key": CIELO_KEY}
    
    all_items = []
    next_object = None
    page_count = 0
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching limited Cielo PnL data (max {max_pages} pages, {max_items} items, sort={sort})")
    print(f"[DEBUG] URL: {url}")
    print(f"[DEBUG] Headers: x-api-key: {CIELO_KEY[:8]}...")
    
    while page_count < max_pages:
        try:
            params = {'sort': sort}  # Add sort parameter
            if next_object:
                params['next_object'] = next_object
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching page {page_count + 1} (sort={sort})...")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            print(f"[DEBUG] Response status: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            print(f"[DEBUG] Response keys: {list(data.keys())}")
            if 'data' in data:
                print(f"[DEBUG] Data keys: {list(data['data'].keys())}")
            
            if 'data' in data and 'items' in data['data']:
                items = data['data']['items']
                all_items.extend(items)
                page_count += 1
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Page {page_count}: {len(items)} items (total: {len(all_items)})")
                
                # Check if we've reached the max items limit
                if len(all_items) >= max_items:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Reached max items limit ({max_items})")
                    all_items = all_items[:max_items]
                    break
                
                # Check if there's a next page
                paging = data['data'].get('paging', {})
                if not paging.get('has_next_page', False):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No more pages available")
                    break
                    
                next_object = paging.get('next_object')
            else:
                print(f"[DEBUG] No items found in response. Full response: {data}")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Cielo API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"[DEBUG] Response status: {e.response.status_code}")
                print(f"[DEBUG] Response text: {e.response.text[:500]}...")
            if page_count == 0:
                return {'status': 'error', 'data': {'items': []}}
            else:
                # Return what we have so far
                break
    
    # Sort items by totalPnl to get top gainers and losers
    if all_items:
        sorted_items = sorted(all_items, key=lambda x: x.get('totalPnl', 0), reverse=True)
        
        # Get top 10 gainers and bottom 10 losers
        top_gainers = sorted_items[:10]
        top_losers = sorted_items[-10:] if len(sorted_items) > 10 else []
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Found {len(top_gainers)} top gainers and {len(top_losers)} top losers")
        
        # Include all items but mark which are top performers
        for item in all_items:
            item['is_top_gainer'] = item in top_gainers
            item['is_top_loser'] = item in top_losers
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Limited fetch complete: {len(all_items)} tokens")
    return {'status': 'ok', 'data': {'items': all_items, 'is_limited': True}}

 