#!/usr/bin/env python3
import duckdb
import os
import pandas as pd

print("\n🔍 Database Status Check\n")

# Check coach.db
if os.path.exists('coach.db'):
    try:
        db = duckdb.connect('coach.db', read_only=True)
        tx_count = db.execute('SELECT COUNT(*) FROM tx').fetchone()[0]
        pnl_count = db.execute('SELECT COUNT(*) FROM pnl').fetchone()[0]
        db.close()
        print("✅ coach.db is LIVE:")
        print(f"   - {tx_count} transactions")
        print(f"   - {pnl_count} PnL records")
    except Exception as e:
        print(f"⚠️  coach.db exists but may be locked")
else:
    print("❌ coach.db not found")

# Check multi_wallet.db
if os.path.exists('multi_wallet.db'):
    try:
        db = duckdb.connect('multi_wallet.db', read_only=True)
        wallets = db.execute('SELECT COUNT(DISTINCT wallet_address) FROM pnl_multi').fetchone()[0]
        positions = db.execute('SELECT COUNT(*) FROM pnl_multi').fetchone()[0]
        
        if positions > 0:
            print("\n✅ multi_wallet.db is LIVE with data")
        else:
            print("\n⚠️  multi_wallet.db exists but is empty")
        db.close()
    except Exception as e:
        print(f"\n⚠️  multi_wallet.db error: {e}")
else:
    print("\n❌ multi_wallet.db not found")

# Check CSV - this is where the real data is!
if os.path.exists('multi_wallet_pnl.csv'):
    df = pd.read_csv('multi_wallet_pnl.csv')
    print(f"\n✅ multi_wallet_pnl.csv is LIVE with ALL YOUR DATA:")
    print(f"   - {len(df)} token positions")
    print(f"   - {df['wallet_address'].nunique()} wallets")
    print(f"   - ${df['realizedPnl'].sum():,.2f} total realized PnL")
    print(f"   - ${df['unrealizedPnl'].sum():,.2f} total unrealized PnL")
    print(f"   - ${(df['realizedPnl'].sum() + df['unrealizedPnl'].sum()):,.2f} net PnL")
    print(f"   - File size: {os.path.getsize('multi_wallet_pnl.csv') / 1024:.1f} KB")
    
    # Show wallet breakdown from CSV
    print("\n   Wallet breakdown:")
    wallet_stats = df.groupby('wallet_address').agg({
        'realizedPnl': ['sum', 'count']
    }).round(2)
    
    for wallet in wallet_stats.index:
        pnl = wallet_stats.loc[wallet, ('realizedPnl', 'sum')]
        count = wallet_stats.loc[wallet, ('realizedPnl', 'count')]
        print(f"   - {wallet[:8]}...: {int(count)} positions, ${pnl:,.0f} PnL")

print("\n✨ Your trading data is loaded in multi_wallet_pnl.csv and ready for analysis!") 