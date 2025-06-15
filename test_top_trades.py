import asyncio
import duckdb
from scripts.data import load_wallet
from scripts.instant_stats import InstantStatsGenerator

# Test wallet
wallet = 'A4DCAjDwkq5jYhNoZ5Xn2NbkTLimARkerVv81w2dhXgL'

# Create temp db
db = duckdb.connect('test_wallet.db')

# Initialize tables
db.execute('''
    CREATE TABLE IF NOT EXISTS pnl (
        mint TEXT, symbol TEXT, realizedPnl DOUBLE, unrealizedPnl DOUBLE,
        totalPnl DOUBLE, avgBuyPrice DOUBLE, avgSellPrice DOUBLE,
        quantity DOUBLE, totalBought DOUBLE, totalSold DOUBLE,
        holdTimeSeconds BIGINT, numSwaps INTEGER
    )
''')

# Load wallet
print('Loading wallet...')
success = load_wallet(db, wallet, mode='instant')
print(f'Load success: {success}')

if success:
    # Get stats
    instant_gen = InstantStatsGenerator(db)
    stats = instant_gen.get_baseline_stats()
    print(f'Stats: {stats}')
    
    # Get top trades
    try:
        top_trades = instant_gen.get_top_trades(5)
        print(f'Top trades: winners={len(top_trades["winners"])}, losers={len(top_trades["losers"])}')
    except Exception as e:
        print(f'Error getting top trades: {e}')
        import traceback
        traceback.print_exc()

db.close() 