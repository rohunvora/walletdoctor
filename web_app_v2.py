#!/usr/bin/env python3
"""
Enhanced web interface for Tradebro - Annotation-driven coaching
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
from scripts.wisdom_generator import WisdomGenerator, WISDOM_SYSTEM_PROMPT
from scripts.llm import TradingCoach
from scripts.analytics import calculate_accurate_stats, calculate_portfolio_metrics, identify_leak_trades

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
    # Test Cielo API directly
    cielo_test_result = None
    if os.getenv('CIELO_KEY'):
        try:
            import requests
            test_wallet = '34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya'
            url = f'https://feed-api.cielo.finance/api/v1/{test_wallet}/pnl/tokens'
            headers = {'x-api-key': os.getenv('CIELO_KEY')}
            response = requests.get(url, headers=headers, timeout=5)
            cielo_test_result = {
                'status_code': response.status_code,
                'has_data': 'data' in response.json() if response.status_code == 200 else False
            }
        except Exception as e:
            cielo_test_result = {'error': str(e)}
    
    return jsonify({
        'helius_key_set': bool(os.getenv('HELIUS_KEY')),
        'cielo_key_set': bool(os.getenv('CIELO_KEY')),
        'helius_key_length': len(os.getenv('HELIUS_KEY', '')) if os.getenv('HELIUS_KEY') else 0,
        'cielo_key_length': len(os.getenv('CIELO_KEY', '')) if os.getenv('CIELO_KEY') else 0,
        'cielo_api_test': cielo_test_result,
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
        helius_key = os.getenv('HELIUS_KEY')
        cielo_key = os.getenv('CIELO_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')
        
        print(f"[{datetime.now()}] Instant load request for wallet: {wallet}")
        print(f"[{datetime.now()}] HELIUS_KEY set: {bool(helius_key)} (length: {len(helius_key) if helius_key else 0})")
        print(f"[{datetime.now()}] CIELO_KEY set: {bool(cielo_key)} (length: {len(cielo_key) if cielo_key else 0})")
        print(f"[{datetime.now()}] OPENAI_API_KEY set: {bool(openai_key)}")
        
        if not helius_key or not cielo_key:
            return jsonify({
                'error': 'API keys not configured. Please set HELIUS_KEY and CIELO_KEY in Railway environment variables.',
                'helius_set': bool(helius_key),
                'cielo_set': bool(cielo_key),
                'helius_length': len(helius_key) if helius_key else 0,
                'cielo_length': len(cielo_key) if cielo_key else 0
            }), 500
        
        # Run quick load via subprocess (no DB connection held here)
        cmd = ['python3', 'scripts/coach.py', 'instant', wallet]
        
        # Make sure subprocess inherits environment variables
        env = os.environ.copy()
        env['PYTHONPATH'] = os.getcwd()
        env['HELIUS_KEY'] = helius_key
        env['CIELO_KEY'] = cielo_key
        if openai_key:
            env['OPENAI_API_KEY'] = openai_key
        
        print(f"[{datetime.now()}] Starting subprocess with command: {' '.join(cmd)}")
        print(f"[{datetime.now()}] Environment CIELO_KEY: {cielo_key[:8]}... (length: {len(cielo_key)})")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
        
        print(f"[{datetime.now()}] Subprocess completed with return code: {result.returncode}")
        if result.stdout:
            print(f"[{datetime.now()}] STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"[{datetime.now()}] STDERR:\n{result.stderr}")
        
        if result.returncode != 0:
            print(f"[{datetime.now()}] Load failed with return code {result.returncode}")
            
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
                'stderr': result.stderr,
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
            top_trades = instant_gen.get_top_trades(limit=10)  # Get more trades
            rich_patterns = instant_gen.get_rich_patterns_for_ai()  # Get deep patterns
            
            # Add a warning if we hit the limit
            is_partial = token_count >= 1000
            hit_token_limit = token_count >= 999  # Might be exactly 1000 or slightly less
            
            # Initialize wisdom generator
            wisdom_gen = WisdomGenerator(db)
            journey = wisdom_gen.extract_trading_journey()
            
            # Generate AI-powered insights
            ai_patterns = []
            ai_message = ""
            
            if openai_key and journey.get('has_data'):
                try:
                    print(f"[{datetime.now()}] Generating wisdom insights...")
                    
                    # Initialize trading coach with wisdom prompt
                    coach = TradingCoach()
                    
                    # Create the wisdom prompt
                    wisdom_prompt = wisdom_gen.create_wisdom_prompt(journey)
                    
                    # Get AI to generate wisdom
                    wisdom_response = coach.client.chat.completions.create(
                        model="o3",
                        messages=[
                            {"role": "system", "content": WISDOM_SYSTEM_PROMPT},
                            {"role": "user", "content": wisdom_prompt}
                        ],
                        temperature=0.8,  # Higher for more creative wisdom
                        max_tokens=800
                    )
                    
                    wisdom_text = wisdom_response.choices[0].message.content
                    
                    # Parse the wisdom into patterns and message
                    wisdom_lines = wisdom_text.split('\n')
                    
                    # Extract individual insights
                    current_insight = []
                    for line in wisdom_lines:
                        line = line.strip()
                        if line and not line.startswith(('---', '===', '***')):
                            if line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.')):
                                if current_insight:
                                    ai_patterns.append(' '.join(current_insight))
                                    current_insight = []
                                # Clean up bullet points
                                clean_line = line.lstrip('•-*123456789. ')
                                current_insight = [clean_line]
                            elif current_insight:
                                current_insight.append(line)
                    
                    # Add the last insight
                    if current_insight:
                        ai_patterns.append(' '.join(current_insight))
                    
                    # Limit to 5 best insights
                    ai_patterns = ai_patterns[:5]
                    
                    # Create a powerful personal message
                    if journey['total_pnl'] < -1000:
                        worst_trade = journey['worst_trades'][0].split(':')[0] if journey['worst_trades'] else 'your worst trade'
                        ai_message = f"Here's the truth: You've burned ${abs(journey['total_pnl']):,.0f} learning expensive lessons. {worst_trade} wasn't a trade, it was hope dressed up as analysis."
                    else:
                        ai_message = wisdom_lines[0] if wisdom_lines else "Your trading tells a story only you can rewrite."
                    
                    print(f"[{datetime.now()}] Wisdom insights generated successfully")
                    
                except Exception as e:
                    print(f"[{datetime.now()}] Error generating wisdom: {str(e)}")
                    # Fallback to journey facts
                    if journey.get('has_data'):
                        ai_patterns = [
                            f"You've taken {journey['total_trades']} swings at the market",
                            f"Your longest held position: {max([t.split('held ')[1].split('h')[0] for t in journey.get('long_holds', ['0h'])], key=float)}h of hope",
                            f"You keep coming back to {list(journey.get('most_traded', {}).keys())[0]}" if journey.get('most_traded') else "The same patterns",
                            f"Win rate: {journey['win_rate']:.0f}% - but that's not the real story"
                        ]
                        ai_message = f"Here's the truth: Your P&L says ${journey['total_pnl']:,.0f}, but the real cost is what you haven't learned yet."
            else:
                # No OpenAI key - provide journey-based insights
                if journey.get('has_data'):
                    ai_patterns = [
                        f"Total journey: {journey['total_trades']} trades, ${journey['total_pnl']:,.0f} P&L",
                        f"Your disasters tell the story: {journey['worst_trades'][0]}" if journey.get('worst_trades') else "Every loss has a lesson",
                        f"You can't quit {list(journey.get('most_traded', {}).keys())[0]}" if journey.get('most_traded') else "Your favorite tokens",
                        f"Quick flips: {len(journey.get('quick_trades', []))} trades under 10 minutes"
                    ]
                    ai_message = "Add OpenAI API key for personalized wisdom about your trading journey."
            
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
            'ai_patterns': ai_patterns,  # Real AI-generated patterns
            'ai_message': ai_message,    # Real AI-generated message
            'is_partial_data': is_partial,
            'is_empty_wallet': token_count == 0,
            'empty_wallet_message': 'This wallet has no DEX trading history on Solana. It may be a new wallet, a validator, or only used for NFT/non-DEX activities.',
            'wallet_address': wallet,  # Include wallet address for client-side checking
            'hit_token_limit': hit_token_limit if 'hit_token_limit' in locals() else False
        }
        
        # Store wallet in session
        session['wallet'] = wallet
        
        return jsonify(response)
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[{datetime.now()}] Exception in instant_load: {str(e)}")
        print(f"[{datetime.now()}] Traceback:\n{error_trace}")
        return jsonify({
            'error': str(e), 
            'type': type(e).__name__,
            'traceback': error_trace
        }), 500

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

@app.route('/debug_cielo/<wallet>', methods=['GET'])
def debug_cielo(wallet):
    """Debug endpoint to test Cielo API directly."""
    try:
        cielo_key = os.getenv('CIELO_KEY')
        
        result = {
            'wallet': wallet,
            'cielo_key_set': bool(cielo_key),
            'cielo_key_length': len(cielo_key) if cielo_key else 0,
            'cielo_key_prefix': cielo_key[:8] if cielo_key else 'NOT SET'
        }
        
        if cielo_key:
            # Test the API directly
            from scripts.data import fetch_cielo_pnl
            pnl_result = fetch_cielo_pnl(wallet)
            
            result['api_response'] = {
                'status': pnl_result.get('status'),
                'items_count': len(pnl_result.get('data', {}).get('items', [])),
                'has_data': bool(pnl_result.get('data', {}).get('items', []))
            }
        else:
            result['api_response'] = {'error': 'CIELO_KEY not set'}
            
        return jsonify(result)
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

if __name__ == '__main__':
    # Create templates directory
    os.makedirs('templates_v2', exist_ok=True)
    
    print("Starting enhanced Tradebro web interface...")
    print("Open http://localhost:5002 in your browser")
    app.run(debug=True, port=5002) 