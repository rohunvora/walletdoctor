#!/usr/bin/env python3
"""
Enhanced web interface for WalletDoctor - Annotation-driven coaching
"""

from flask import Flask, render_template, request, jsonify, session
import subprocess
import json
import os
import tempfile
import secrets
from datetime import datetime
import duckdb
from scripts.instant_stats import InstantStatsGenerator
from scripts.db_migrations import run_migrations, add_annotation, get_similar_annotations
from scripts.trade_comparison import TradeComparator

app = Flask(__name__, template_folder='templates_v2')
app.secret_key = secrets.token_hex(16)

# Initialize database with migrations only once at startup
def init_database():
    """Initialize database and run migrations once."""
    db = duckdb.connect("coach.db")
    run_migrations(db)
    db.close()

# Run initialization
init_database()

@app.route('/')
def index():
    return render_template('index_v2.html')

@app.route('/test_env', methods=['GET'])
def test_env():
    """Test endpoint to check environment and API keys."""
    return jsonify({
        'helius_key_set': bool(os.getenv('HELIUS_KEY')),
        'cielo_key_set': bool(os.getenv('CIELO_KEY')),
        'helius_key_length': len(os.getenv('HELIUS_KEY', '')) if os.getenv('HELIUS_KEY') else 0,
        'cielo_key_length': len(os.getenv('CIELO_KEY', '')) if os.getenv('CIELO_KEY') else 0,
        'database_exists': os.path.exists('coach.db'),
        'python_path': os.getenv('PYTHONPATH', 'Not set'),
        'working_dir': os.getcwd()
    })

@app.route('/instant_load', methods=['POST'])
def instant_load():
    """Quick load with instant baseline display."""
    try:
        data = request.json
        wallet = data.get('wallet', '').strip()
        
        if not wallet:
            return jsonify({'error': 'No wallet provided'}), 400
        
        # Check if API keys are set
        if not os.getenv('HELIUS_KEY') or not os.getenv('CIELO_KEY'):
            return jsonify({
                'error': 'API keys not configured. Please set HELIUS_KEY and CIELO_KEY in Railway environment variables.',
                'helius_set': bool(os.getenv('HELIUS_KEY')),
                'cielo_set': bool(os.getenv('CIELO_KEY'))
            }), 500
        
        # Run quick load via subprocess (no DB connection held here)
        cmd = ['python3', 'scripts/coach.py', 'instant', wallet]
        
        # Make sure subprocess inherits environment variables
        env = os.environ.copy()
        print(f"[{datetime.now()}] Starting instant load for wallet: {wallet}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
        
        if result.returncode != 0:
            print(f"[{datetime.now()}] Load failed with return code {result.returncode}")
            print(f"STDERR: {result.stderr}")
            print(f"STDOUT: {result.stdout}")
            
            # Check if it's a timeout or large wallet issue
            if "timeout" in result.stderr.lower() or "502" in str(result.returncode):
                return jsonify({
                    'error': 'This wallet has too many trades for instant loading. Please try a wallet with fewer trades.',
                    'is_large_wallet': True,
                    'suggestion': 'Large wallets (3000+ trades) are not supported in the free version.'
                }), 400
                
            return jsonify({
                'error': f'Load failed: {result.stderr}',
                'stdout': result.stdout,
                'command': ' '.join(cmd)
            }), 500
        
        print(f"[{datetime.now()}] Load successful, reading stats...")
        
        # Open a new connection for reading stats
        db = duckdb.connect("coach.db", read_only=True)
        try:
            # Check how many tokens we loaded
            token_count = db.execute("SELECT COUNT(*) FROM pnl").fetchone()[0]
            print(f"[{datetime.now()}] Loaded {token_count} tokens")
            
            # Get instant stats
            instant_gen = InstantStatsGenerator(db)
            stats = instant_gen.get_baseline_stats()
            top_trades = instant_gen.get_top_trades()
            
            # Add a warning if we hit the limit
            is_partial = token_count >= 1000
            
        finally:
            db.close()
        
        # Format response
        response = {
            'baseline': {
                'win_rate': stats.get('win_rate', 0),
                'avg_pnl': stats.get('avg_pnl', 0),
                'total_trades': stats.get('total_trades', 0),
                'total_pnl': stats.get('total_pnl', 0),
                'avg_position_size': stats.get('avg_position_size', 0)
            },
            'top_trades': top_trades,
            'is_partial_data': is_partial
        }
        
        # Store wallet in session
        session['wallet'] = wallet
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e), 'type': type(e).__name__}), 500

@app.route('/annotate', methods=['POST'])
def annotate():
    """Add annotation to a trade."""
    try:
        data = request.json
        symbol = data.get('symbol', '').strip()
        note = data.get('note', '').strip()
        
        if not symbol or not note:
            return jsonify({'error': 'Symbol and note required'}), 400
        
        # Open connection for this request
        db = duckdb.connect("coach.db")
        try:
            # Find the trade
            pnl_df = db.execute(f"""
                SELECT * FROM pnl 
                WHERE UPPER(symbol) = UPPER('{symbol}')
                ORDER BY mint DESC
                LIMIT 1
            """).df()
            
            if pnl_df.empty:
                return jsonify({'error': f'Trade not found for {symbol}'}), 404
            
            trade = pnl_df.iloc[0]
            
            # Add annotation
            annotation_id = add_annotation(
                db,
                token_symbol=trade['symbol'],
                token_mint=trade['mint'],
                trade_pnl=trade['realizedPnl'],
                user_note=note,
                entry_size_usd=trade['totalBought'] * trade['avgBuyPrice'],
                hold_time_seconds=trade['holdTimeSeconds']
            )
            
            # Get comparison insights
            comparator = TradeComparator(db)
            comparison = comparator.compare_to_personal_average(trade.to_dict())
            similar_trades = comparator.find_similar_past_trades(trade.to_dict())
            
            # Find similar annotations
            similar_annotations = get_similar_annotations(
                db, 
                entry_size_usd=trade['totalBought'] * trade['avgBuyPrice']
            )
        finally:
            db.close()
        
        return jsonify({
            'success': True,
            'annotation_id': annotation_id,
            'insights': {
                'comparison': comparison,
                'similar_trades': similar_trades[:3],
                'similar_annotations': [
                    {
                        'symbol': ann[0],
                        'pnl': ann[1],
                        'note': ann[2],
                        'sentiment': ann[3]
                    } for ann in similar_annotations[:3]
                ]
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/refresh_trades', methods=['POST'])
def refresh_trades():
    """Check for new trades and provide comparisons."""
    try:
        wallet = session.get('wallet')
        if not wallet:
            return jsonify({'error': 'No wallet loaded'}), 400
        
        # Reload wallet data via subprocess
        cmd = ['python3', 'scripts/coach.py', 'load', wallet]
        env = os.environ.copy()
        subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
        
        # Open connection for analysis
        db = duckdb.connect("coach.db", read_only=True)
        try:
            # Get new trade comparisons
            comparator = TradeComparator(db)
            new_trades = comparator.detect_new_trades(force_check=True)
            
            results = []
            for trade in new_trades[:5]:  # Limit to 5
                comparison = comparator.compare_to_personal_average(trade)
                similar = comparator.find_similar_past_trades(trade)
                
                results.append({
                    'trade': {
                        'symbol': trade.get('symbol'),
                        'pnl': trade.get('realizedPnl'),
                        'entry_size': trade.get('totalBought', 0) * trade.get('avgBuyPrice', 0)
                    },
                    'comparison': comparison,
                    'similar_trades': similar[:3]
                })
        finally:
            db.close()
        
        return jsonify({
            'new_trades': results,
            'count': len(new_trades)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_annotations', methods=['GET'])
def get_annotations():
    """Get all annotations for display."""
    try:
        db = duckdb.connect("coach.db", read_only=True)
        try:
            annotations = db.execute("""
                SELECT 
                    annotation_id,
                    token_symbol,
                    trade_pnl,
                    user_note,
                    sentiment,
                    created_at
                FROM trade_annotations
                ORDER BY created_at DESC
                LIMIT 20
            """).fetchall()
        finally:
            db.close()
        
        return jsonify({
            'annotations': [
                {
                    'id': ann[0],
                    'symbol': ann[1],
                    'pnl': ann[2],
                    'note': ann[3],
                    'sentiment': ann[4],
                    'created_at': ann[5].isoformat() if ann[5] else None
                } for ann in annotations
            ]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/coaching_prompt', methods=['POST'])
def coaching_prompt():
    """Get AI coaching based on annotations and patterns."""
    try:
        data = request.json
        question = data.get('question', '').strip()
        
        db = duckdb.connect("coach.db", read_only=True)
        try:
            # Get recent annotations for context
            annotations = db.execute("""
                SELECT token_symbol, user_note, trade_pnl
                FROM trade_annotations
                ORDER BY created_at DESC
                LIMIT 10
            """).fetchall()
        finally:
            db.close()
        
        # Build context
        context = "Recent annotated trades:\n"
        for ann in annotations:
            context += f"- {ann[0]}: {ann[1]} (P&L: ${ann[2]:+,.2f})\n"
        
        # Use existing LLM module with annotation context
        cmd = ['python3', 'scripts/coach.py', 'ask']
        full_question = f"{context}\n\nQuestion: {question}"
        
        # For MVP, return a structured response based on annotations
        response = analyze_with_annotations(question, annotations)
        
        return jsonify({
            'response': response,
            'annotations_used': len(annotations)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def analyze_with_annotations(question: str, annotations: list) -> str:
    """Generate insights using annotations as context."""
    # Simple pattern matching for MVP
    question_lower = question.lower()
    
    # Analyze annotation patterns
    negative_notes = [ann for ann in annotations if ann[2] < 0]
    positive_notes = [ann for ann in annotations if ann[2] > 0]
    
    if 'mistake' in question_lower or 'problem' in question_lower:
        if negative_notes:
            common_words = find_common_patterns([n[1] for n in negative_notes])
            return f"""Based on your annotations, your main trading mistakes are:

1. **{common_words[0]}** - Mentioned in {len([n for n in negative_notes if common_words[0].lower() in n[1].lower()])} losing trades
2. **Position sizing** - Your losing trades average ${abs(sum(n[2] for n in negative_notes)/len(negative_notes)):,.2f} loss

Your own words from losing trades:
{chr(10).join([f'- "{n[1][:100]}"' for n in negative_notes[:3]])}

Fix: Trust your own analysis. You already know what goes wrong."""
    
    elif 'improve' in question_lower or 'better' in question_lower:
        if positive_notes:
            return f"""Your winning trades show clear patterns:

{chr(10).join([f'- {n[0]}: "{n[1]}" (+${n[2]:,.2f})' for n in positive_notes[:3]])}

Do more of what already works for you."""
    
    # Default response
    return "Add more trade annotations to unlock personalized insights. The more you annotate, the better the coaching."

def find_common_patterns(notes: list) -> list:
    """Find common words/themes in annotations."""
    # Simple word frequency for MVP
    common_words = ['FOMO', 'panic', 'greed', 'patience', 'plan']
    found = []
    
    all_text = ' '.join(notes).lower()
    for word in common_words:
        if word.lower() in all_text:
            found.append(word)
    
    return found if found else ['emotional trading', 'lack of plan', 'poor timing']

if __name__ == '__main__':
    # Create templates directory
    os.makedirs('templates_v2', exist_ok=True)
    
    print("Starting enhanced WalletDoctor web interface...")
    print("Open http://localhost:5002 in your browser")
    app.run(debug=True, port=5002) 