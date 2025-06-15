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
from scripts.harsh_insights import HarshTruthGenerator
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
            top_trades = instant_gen.get_top_trades()
            
            # Add a warning if we hit the limit
            is_partial = token_count >= 1000
            hit_token_limit = token_count >= 999  # Might be exactly 1000 or slightly less
            
            # Generate AI-powered insights if OpenAI is available
            ai_patterns = []
            ai_message = ""
            
            if openai_key and token_count > 0:
                try:
                    print(f"[{datetime.now()}] Generating AI insights...")
                    
                    # Get full data for analysis
                    pnl_df = db.execute("SELECT * FROM pnl").df()
                    tx_df = db.execute("SELECT * FROM tx").df()
                    
                    # Add more detailed trade analysis
                    if not pnl_df.empty:
                        # Sort by P&L to get best and worst
                        pnl_df['entry_size_usd'] = pnl_df['totalBought'] * pnl_df['avgBuyPrice']
                        pnl_df['exit_size_usd'] = pnl_df['totalSold'] * pnl_df['avgSellPrice']
                        
                        # Get worst 10 trades for pattern analysis
                        worst_trades = pnl_df.nsmallest(10, 'realizedPnl')
                        
                        # Look for patterns in losers
                        meme_tokens = worst_trades[worst_trades['symbol'].str.contains('INU|DOGE|PEPE|SHIB|BONK|WIF|MYRO|BOME', case=False, na=False)]
                        if len(meme_tokens) > 0:
                            meme_loss = meme_tokens['realizedPnl'].sum()
                            meme_tokens_list = meme_tokens['symbol'].tolist()
                    
                    # Initialize harsh truth generator for structured insights
                    truth_gen = HarshTruthGenerator(db)
                    harsh_insights = truth_gen.generate_all_insights()
                    
                    # Calculate comprehensive metrics
                    accurate_stats = calculate_accurate_stats(pnl_df)
                    portfolio_metrics = calculate_portfolio_metrics(pnl_df, tx_df)
                    leak_trades = identify_leak_trades(pnl_df)
                    
                    # Initialize trading coach
                    coach = TradingCoach()
                    
                    # Format specific trade data for AI
                    specific_trades = []
                    
                    # Add top losers with details
                    if top_trades['losers']:
                        for trade in top_trades['losers'][:5]:
                            specific_trades.append(f"{trade['symbol']}: Lost ${abs(trade['realizedPnl']):,.0f} (held {trade['holdTimeSeconds']/3600:.1f} hours, position size ${trade.get('entry_size_usd', 0):,.0f})")
                    
                    # Add top winners with details  
                    if top_trades['winners']:
                        for trade in top_trades['winners'][:3]:
                            specific_trades.append(f"{trade['symbol']}: Won ${trade['realizedPnl']:,.0f} (held {trade['holdTimeSeconds']/3600:.1f} hours, position size ${trade.get('entry_size_usd', 0):,.0f})")
                    
                    # Extract key insights from harsh_insights
                    key_facts = []
                    if harsh_insights:
                        for insight in harsh_insights[:3]:
                            if 'facts' in insight:
                                key_facts.extend([fact for fact in insight['facts'] if '$' in fact or '%' in fact][:2])
                    
                    # Build a clear, specific prompt with actual data
                    pattern_prompt = f"""Analyze this specific wallet data and generate 4-5 ultra-specific insights:

WALLET STATS:
- Total P&L: ${accurate_stats['total_realized_pnl']:,.0f} across {accurate_stats['total_tokens_traded']} tokens
- Win Rate: {accurate_stats['win_rate_pct']:.0f}% ({accurate_stats['winning_tokens']} wins / {accurate_stats['losing_tokens']} losses)
- Average Position: ${stats.get('avg_position_size', 0):,.0f}

SPECIFIC TRADES:
{chr(10).join(specific_trades)}

{'MEME TOKEN LOSSES:' + chr(10) + f'Lost ${abs(meme_loss):,.0f} on: {", ".join(meme_tokens_list)}' if 'meme_loss' in locals() and meme_loss < 0 else ''}

KEY PATTERNS FOUND:
{chr(10).join(key_facts) if key_facts else 'No clear patterns yet'}

Generate 4-5 insights that:
1. Reference specific token names and exact dollar amounts from the trades above
2. Identify patterns (e.g., "Lost $X on 3 dog-themed tokens: BONK, SHIB, FLOKI")
3. Be brutally specific - no generic advice
4. Format as short, punchy statements

DO NOT say generic things like "improve timing" or "diversify holdings". Reference the actual tokens and amounts."""
                    
                    pattern_response = coach.analyze_wallet(pattern_prompt, {})
                    
                    # Parse AI response into individual patterns - better parsing
                    raw_patterns = pattern_response.split('\n')
                    ai_patterns = []
                    for line in raw_patterns:
                        line = line.strip()
                        # Skip empty lines, numbered items, and generic intros
                        if (line and 
                            not line.startswith(('Based on', 'Here are', 'Analysis', 'Looking at')) and
                            not line[0].isdigit() and
                            not line.startswith(('-', '*', '•')) and
                            len(line) > 20):  # Ensure it's substantial
                            # Clean up the line
                            clean_line = line.lstrip('- ').lstrip('* ').lstrip('• ').strip()
                            if '$' in clean_line or '%' in clean_line:  # Prioritize lines with specific data
                                ai_patterns.append(clean_line)
                    
                    # Ensure we get at least 3-5 patterns
                    ai_patterns = ai_patterns[:5]
                    
                    # Generate personal message with specific data
                    biggest_loser_symbol = top_trades['losers'][0]['symbol'] if top_trades['losers'] else 'None'
                    biggest_loss_amount = abs(top_trades['losers'][0]['realizedPnl']) if top_trades['losers'] else 0
                    
                    message_prompt = f"""Write a brutally honest 2-3 sentence message about this trader's performance.

THEIR ACTUAL DATA:
- Lost ${abs(accurate_stats['total_realized_pnl']):,.0f} total with {accurate_stats['win_rate_pct']:.0f}% win rate
- Biggest disaster: {biggest_loser_symbol} lost ${biggest_loss_amount:,.0f}
- Pattern: {key_facts[0] if key_facts else 'Multiple small losses adding up'}

Start with "Here's the truth:" and reference specific tokens and amounts. Be harsh but actionable. 
Example: "Here's the truth: Your BONK trade cost you $8,400 because you bought after a 47% pump. You've done this on 8 different meme coins, losing $43,000 total."

DO NOT be generic. Use their actual tokens and numbers."""
                    
                    ai_message = coach.analyze_wallet(message_prompt, {})
                    
                    print(f"[{datetime.now()}] AI insights generated successfully")
                    
                except Exception as e:
                    print(f"[{datetime.now()}] Error generating AI insights: {str(e)}")
                    # Fall back to harsh insights if AI fails
                    if harsh_insights:
                        for insight in harsh_insights[:3]:
                            if 'facts' in insight:
                                ai_patterns.extend(insight['facts'][:2])
                        ai_message = "Analysis based on your trading data. Add annotations to trades for personalized AI coaching."
            else:
                # No OpenAI key - use harsh insights to provide personalized data
                print(f"[{datetime.now()}] No OpenAI key, using harsh insights for personalization")
                try:
                    # Generate harsh insights for structured data
                    truth_gen = HarshTruthGenerator(db)
                    harsh_insights = truth_gen.generate_all_insights()
                    
                    if harsh_insights:
                        # Extract the most impactful patterns
                        for insight in harsh_insights[:4]:
                            if 'facts' in insight:
                                # Take the most specific facts
                                for fact in insight['facts'][:2]:
                                    if '$' in fact or '%' in fact:  # Prioritize facts with numbers
                                        ai_patterns.append(fact)
                        
                        # Create a data-driven message from the insights
                        if harsh_insights and len(harsh_insights) > 0:
                            main_insight = harsh_insights[0]
                            if 'cost' in main_insight and 'fix' in main_insight:
                                ai_message = f"Here's the truth: {main_insight.get('cost', '')} {main_insight.get('fix', '')}"
                            else:
                                ai_message = "Your trading data shows clear patterns. The numbers tell the story - check the insights above."
                    
                    # Ensure we always have some patterns
                    if not ai_patterns:
                        pnl_df = db.execute("SELECT * FROM pnl").df()
                        if not pnl_df.empty:
                            total_pnl = pnl_df['realizedPnl'].sum()
                            win_rate = (len(pnl_df[pnl_df['realizedPnl'] > 0]) / len(pnl_df) * 100)
                            avg_loss = pnl_df[pnl_df['realizedPnl'] < 0]['realizedPnl'].mean()
                            
                            ai_patterns = [
                                f"Total P&L across {len(pnl_df)} trades: ${total_pnl:,.0f}",
                                f"Win rate: {win_rate:.0f}% - winning {int(win_rate * len(pnl_df) / 100)} out of {len(pnl_df)} trades",
                                f"Average loss when wrong: ${avg_loss:,.0f}"
                            ]
                            
                            # Add specific trade examples
                            worst_trade = pnl_df.nsmallest(1, 'realizedPnl').iloc[0]
                            ai_patterns.append(f"Biggest loss: {worst_trade['symbol']} cost you ${abs(worst_trade['realizedPnl']):,.0f}")
                            
                            ai_message = f"Here's the truth: Your trades are showing a {win_rate:.0f}% win rate with ${total_pnl:,.0f} total P&L. Focus on the patterns above to improve."
                
                except Exception as e:
                    print(f"[{datetime.now()}] Error generating fallback insights: {str(e)}")
                    ai_patterns = ["Loading complete trading analysis..."]
                    ai_message = "Full analysis requires OpenAI API key for personalized coaching."
            
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
    
    print("Starting enhanced WalletDoctor web interface...")
    print("Open http://localhost:5002 in your browser")
    app.run(debug=True, port=5002) 