# data.py
import os
import requests
import duckdb
import pandas as pd
from typing import Optional, Dict, List, Any, Tuple
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
            
            # Check if 30-day filter was applied
            is_30d_filtered = pnl_data.get('is_30_day_filtered', False)
            
            if len(tokens) == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] WARNING: Cielo returned 0 tokens for wallet {wallet_address}")
                print(f"[{datetime.now().strftime('%H:%M:%S')}] This might be a new wallet or one with no trading history")
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
            
            # If 30-day filter was applied, store the metadata
            if is_30d_filtered and 'data' in pnl_data:
                # Create metadata table to store filter info
                db.execute("""
                    CREATE TABLE IF NOT EXISTS filter_metadata (
                        filter_type TEXT,
                        original_count INTEGER,
                        filtered_count INTEGER,
                        pnl_30d DOUBLE,
                        wins_30d INTEGER,
                        losses_30d INTEGER,
                        win_rate_30d DOUBLE
                    )
                """)
                
                # Store the 30-day filter metadata
                db.execute("""
                    INSERT INTO filter_metadata VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    '30_day',
                    pnl_data['data'].get('original_count', 0),
                    pnl_data['data'].get('filtered_count', 0),
                    pnl_data['data'].get('pnl_30d', 0),
                    pnl_data['data'].get('wins_30d', 0),
                    pnl_data['data'].get('losses_30d', 0),
                    pnl_data['data'].get('win_rate_30d', 0)
                ])
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Stored 30-day filter metadata")
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Data stored successfully")
            return True
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No PnL data found from Cielo")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] API Response structure: {list(pnl_data.keys()) if pnl_data else 'None'}")
            if pnl_data and 'data' in pnl_data:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Data keys: {list(pnl_data['data'].keys())}")
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

def fetch_cielo_pnl_smart(address: str, mode: str = 'full') -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Smart fetch that gets summary data first, then filtered token data based on wallet size.
    For wallets with 1000+ trades, filters to last 30 days for accuracy.
    Returns: (trading_stats, aggregated_pnl, token_pnl)
    """
    # First, get the trading stats (overall performance)
    trading_stats = fetch_cielo_trading_stats(address)
    
    # Get aggregated PnL - this has the best summary data!
    aggregated_pnl = fetch_cielo_aggregated_pnl(address)
    
    # Check if this is a large wallet that needs 30-day filtering
    is_large_wallet = False
    if aggregated_pnl.get('status') == 'ok' and 'data' in aggregated_pnl:
        agg_data = aggregated_pnl.get('data', {})
        tokens_traded = agg_data.get('tokens_traded', 0)
        
        if tokens_traded > 1000:
            is_large_wallet = True
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Large wallet detected ({tokens_traded:,} tokens traded)")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Will filter to last 30 days for accurate analysis")
    
    # Determine fetch strategy based on wallet size
    if is_large_wallet:
        # For large wallets, get more data to have enough for 30-day filtering
        max_pages = 5 if mode == 'instant' else 10
        max_items = 500 if mode == 'instant' else 1000
        use_30_day_filter = True
    else:
        # For normal wallets, use existing logic
        if mode == 'instant':
            max_pages = 2
            max_items = 200
        else:
            max_pages = 10
            max_items = 1000
        use_30_day_filter = False
    
    # Fetch token PnL data
    token_pnl = fetch_cielo_pnl_limited(address, max_items=max_items, max_pages=max_pages)
    
    # Apply 30-day filter for large wallets
    if use_30_day_filter and token_pnl.get('status') == 'ok':
        token_pnl = apply_30_day_filter(token_pnl)
        # Mark as 30-day filtered for UI messaging
        token_pnl['is_30_day_filtered'] = True
    
    return trading_stats, aggregated_pnl, token_pnl

def apply_30_day_filter(token_pnl_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter token PnL data to only include trades from the last 30 days.
    This gives accurate recent performance for large wallets.
    """
    if not token_pnl_data.get('data', {}).get('items'):
        return token_pnl_data
    
    # Calculate 30 days ago timestamp
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.now() - timedelta(days=30)
    thirty_days_ago_timestamp = int(thirty_days_ago.timestamp())
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Applying 30-day filter (since {thirty_days_ago.strftime('%Y-%m-%d')})")
    
    original_items = token_pnl_data['data']['items']
    filtered_items = []
    
    # Calculate 30-day PnL totals
    total_pnl_30d = 0
    wins_30d = 0
    losses_30d = 0
    
    for token in original_items:
        # Check if token has been traded in last 30 days
        last_trade = token.get('last_trade', 0)
        
        if last_trade and last_trade >= thirty_days_ago_timestamp:
            filtered_items.append(token)
            # Track 30-day stats
            pnl = token.get('total_pnl_usd', 0) or 0
            if pnl > 0:
                wins_30d += 1
                total_pnl_30d += pnl
            elif pnl < 0:
                losses_30d += 1
                total_pnl_30d += pnl
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Filtered from {len(original_items)} to {len(filtered_items)} tokens (30-day active)")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 30-day PnL: ${total_pnl_30d:,.0f}, Win Rate: {wins_30d/(wins_30d+losses_30d)*100 if (wins_30d+losses_30d) > 0 else 0:.1f}%")
    
    # Sort filtered items by PnL to get correct top performers for 30-day period
    if filtered_items:
        filtered_items.sort(key=lambda x: x.get('total_pnl_usd', 0), reverse=True)
    
    # Create filtered response
    filtered_data = token_pnl_data.copy()
    filtered_data['data']['items'] = filtered_items
    filtered_data['data']['original_count'] = len(original_items)
    filtered_data['data']['filtered_count'] = len(filtered_items)
    filtered_data['data']['filter_applied'] = '30_day'
    # Add 30-day specific stats
    filtered_data['data']['pnl_30d'] = total_pnl_30d
    filtered_data['data']['wins_30d'] = wins_30d
    filtered_data['data']['losses_30d'] = losses_30d
    filtered_data['data']['win_rate_30d'] = wins_30d/(wins_30d+losses_30d)*100 if (wins_30d+losses_30d) > 0 else 0
    
    return filtered_data

def fetch_cielo_pnl_limited(address: str, max_items: int = 200, max_pages: int = 2) -> Dict[str, Any]:
    """Fetch limited PnL data from Cielo API with page limit."""
    if not CIELO_KEY:
        print(f"❌ CIELO_KEY is empty!")
        return {'status': 'error', 'data': {'items': []}}
    
    url = f"https://feed-api.cielo.finance/api/v1/{address}/pnl/tokens"
    headers = {"x-api-key": CIELO_KEY}
    
    all_items = []
    next_object = None
    page_count = 0
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching limited Cielo PnL data (max {max_pages} pages, {max_items} items)")
    
    while page_count < max_pages:
        try:
            params = {}
            if next_object:
                params['next_object'] = next_object
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching page {page_count + 1}...")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
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
                break
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Cielo API error: {e}")
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