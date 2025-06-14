import duckdb

db = duckdb.connect('coach.db')

# Check what data we have
result = db.execute("""
    SELECT COUNT(*) as token_count,
           SUM(CASE WHEN realizedPnl > 0 THEN 1 ELSE 0 END) as winners,
           SUM(CASE WHEN realizedPnl <= 0 THEN 1 ELSE 0 END) as losers,
           SUM(realizedPnl) as total_pnl,
           MIN(realizedPnl) as worst_loss,
           MAX(realizedPnl) as best_win
    FROM pnl
""").fetchone()

print(f'Tokens in DB: {result[0]}')
print(f'Winners: {result[1]}')
print(f'Losers: {result[2]}')
print(f'Win Rate: {result[1]/result[0]*100:.1f}%')
print(f'Total PnL: ${result[3]:,.2f}')
print(f'Worst Loss: ${result[4]:,.2f}')
print(f'Best Win: ${result[5]:,.2f}')

# Check for specific tokens that Cielo shows as big losers
print('\nChecking for tokens shown in Cielo screenshot:')
for token in ['LIBRA', 'ROSSCOIN', 'CFM', 'IRENE', 'ASS']:
    entries = db.execute(f"SELECT symbol, realizedPnl FROM pnl WHERE UPPER(symbol) = '{token}'").fetchall()
    if entries:
        for e in entries:
            print(f'{e[0]}: ${e[1]:,.2f}')
    else:
        print(f'{token}: NOT FOUND')

# Get bottom 10 losers
print('\nBottom 10 losers in our DB:')
losers = db.execute("""
    SELECT symbol, realizedPnl 
    FROM pnl 
    WHERE realizedPnl < 0
    ORDER BY realizedPnl ASC 
    LIMIT 10
""").fetchall()
for l in losers:
    print(f'{l[0]}: ${l[1]:,.2f}')

db.close() 