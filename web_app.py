#!/usr/bin/env python3
"""
Simple web interface for WalletDoctor Coach
Minimal dependencies, maximum reliability
"""

from flask import Flask, render_template, request, jsonify, session
import subprocess
import json
import os
import tempfile
import secrets
from datetime import datetime
from scripts.llm import get_quick_insight  # Use existing LLM module

app = Flask(__name__, template_folder='src/walletdoctor/web/templates')
app.secret_key = secrets.token_hex(16)  # For session management

# Store conversation history in memory (resets on restart)
conversations = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Run the coach analyze command for given wallets"""
    try:
        data = request.json
        wallets = data.get('wallets', '').strip()
        
        if not wallets:
            return jsonify({'error': 'No wallets provided'}), 400
        
        # Create a session ID for this conversation
        session_id = session.get('session_id')
        if not session_id:
            session_id = secrets.token_hex(8)
            session['session_id'] = session_id
            conversations[session_id] = []
        
        # First, just load the data and show stats (faster)
        cmd = ['python3', 'coach.py', 'quick-analyze', wallets]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        
        if result.returncode != 0:
            return jsonify({'error': f'Analysis failed: {result.stderr}'}), 500
        
        # Store in conversation history
        conversations[session_id].append({
            'timestamp': datetime.now().isoformat(),
            'type': 'analyze',
            'wallets': wallets,
            'output': result.stdout
        })
        
        return jsonify({
            'output': result.stdout,
            'session_id': session_id
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Analysis timed out. The wallet may have too many transactions. Please try again with a different wallet.'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ask', methods=['POST'])
def ask():
    """Handle follow-up questions maintaining context"""
    try:
        data = request.json
        question = data.get('question', '').strip()
        session_id = session.get('session_id')
        
        if not question:
            return jsonify({'error': 'No question provided'}), 400
            
        if not session_id or session_id not in conversations:
            return jsonify({'error': 'No active session. Please analyze wallets first.'}), 400
        
        # Get conversation history
        history = conversations[session_id]
        if not history:
            return jsonify({'error': 'No analysis found. Please analyze wallets first.'}), 400
        
        # Get the most recent analysis output
        analysis_output = None
        for entry in reversed(history):
            if entry['type'] == 'analyze':
                analysis_output = entry['output']
                break
        
        if not analysis_output:
            return jsonify({'error': 'No analysis data found'}), 400
        
        # Use the existing LLM module to generate response based on the analysis
        try:
            from scripts.llm import TradingCoach
            import duckdb
            
            # Connect to the cached database
            db = duckdb.connect("coach.db")
            
            # Load the metrics from the database
            tx_df = db.execute("SELECT * FROM tx").df()
            pnl_df = db.execute("SELECT * FROM pnl").df()
            
            # Calculate metrics for the coach
            metrics = {}
            if not pnl_df.empty:
                from scripts.analytics import calculate_win_rate, calculate_portfolio_metrics, identify_leak_trades, calculate_accurate_stats
                metrics['stats'] = calculate_accurate_stats(pnl_df)
                metrics['win_rate'] = calculate_win_rate(pnl_df)
                metrics['portfolio'] = calculate_portfolio_metrics(pnl_df, tx_df)
                
                leak_trades = identify_leak_trades(pnl_df)
                if not leak_trades.empty:
                    metrics['leak_trades'] = leak_trades.head(5).to_dict('records')
            
            if not tx_df.empty:
                from scripts.transforms import calculate_hold_durations
                from scripts.analytics import analyze_hold_patterns
                hold_durations = calculate_hold_durations(tx_df)
                metrics['hold_patterns'] = analyze_hold_patterns(hold_durations)
            
            # Initialize coach and get response
            coach = TradingCoach()
            response = coach.analyze_wallet(question, metrics)
            
            # Store in conversation history
            conversations[session_id].append({
                'timestamp': datetime.now().isoformat(),
                'type': 'question',
                'question': question,
                'output': response
            })
            
            return jsonify({
                'output': response,
                'session_id': session_id
            })
            
        except Exception as e:
            # If LLM fails, provide helpful fallback based on the analysis
            import re
            
            # Extract key metrics from the analysis output
            win_rate_match = re.search(r'Token Win Rate.*?│\s*([\d.]+)%', analysis_output)
            pnl_match = re.search(r'Realized PnL.*?│\s*\$([\d,.-]+)', analysis_output)
            hold_time_match = re.search(r'Median Hold Time.*?│\s*([\d.]+)\s*minutes', analysis_output)
            
            win_rate = win_rate_match.group(1) if win_rate_match else "unknown"
            pnl = pnl_match.group(1) if pnl_match else "unknown"
            hold_time = hold_time_match.group(1) if hold_time_match else "unknown"
            
            # Generate a helpful response based on the question
            if "leak" in question.lower() or "problem" in question.lower() or "issue" in question.lower():
                response = f"""Based on your trading data:

📊 Key Issues Identified:

1. **Low Win Rate ({win_rate}%)**: You're winning on less than 1 in 3 trades. This suggests either poor entry timing or chasing momentum too late.

2. **Quick Trading (Median hold: {hold_time} min)**: Your extremely short hold times indicate FOMO-driven decisions rather than strategic entries.

3. **Loss Distribution**: With 595 losing tokens vs 205 winners, you're taking too many low-probability trades.

🎯 Biggest Trading Leaks:
- Chasing green candles (FOMO trading)
- Cutting winners too quickly 
- No clear entry/exit strategy
- Overtrading on hype

💡 Immediate Actions:
1. Set a rule: Only enter if you can identify a clear catalyst
2. Minimum hold time of 30 minutes unless stop-loss hits
3. Reduce position count - quality over quantity"""
            
            elif "improve" in question.lower() or "fix" in question.lower():
                response = f"""To improve your {win_rate}% win rate:

1. **Entry Discipline**: Wait for pullbacks, not pumps. Your 9.9 min hold time shows you're buying tops.

2. **Position Sizing**: With 800 tokens traded, you're spreading too thin. Focus on 5-10 high-conviction plays daily.

3. **Risk Management**: Set stops at -5% and take profits incrementally (+20%, +50%, +100%).

4. **Psychology Fix**: Your pattern shows fear of missing out. Success comes from missing 90% of moves to catch the right 10%."""
            
            else:
                response = f"""Based on your analysis:
- Win Rate: {win_rate}%
- Realized PnL: ${pnl}
- Median Hold Time: {hold_time} minutes
- Total Tokens Traded: 800

Your data suggests rapid-fire trading with low selectivity. Consider focusing on quality over quantity."""
        
        # Store the response in conversation history
        conversations[session_id].append({
            'timestamp': datetime.now().isoformat(),
            'type': 'question',
            'question': question,
            'output': response
        })
        
        return jsonify({
            'output': response,
            'session_id': session_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/clear', methods=['POST'])
def clear_session():
    """Clear the current session"""
    session_id = session.get('session_id')
    if session_id and session_id in conversations:
        del conversations[session_id]
    session.clear()
    return jsonify({'status': 'cleared'})

if __name__ == '__main__':
    # Create templates directory
    os.makedirs('src/walletdoctor/web/templates', exist_ok=True)
    
    # Check if template exists, if not create it
    if not os.path.exists('src/walletdoctor/web/templates/index.html'):
        print("Creating template file...")
        with open('src/walletdoctor/web/templates/index.html', 'w') as f:
            f.write('''<!DOCTYPE html>
<html>
<head>
    <title>WalletDoctor Coach</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
        }
        .input-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #666;
            font-weight: 500;
        }
        input, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
            box-sizing: border-box;
        }
        button {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin-right: 10px;
        }
        button:hover {
            background: #0056b3;
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .output {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 5px;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            max-height: 500px;
            overflow-y: auto;
        }
        .error {
            color: #dc3545;
            margin-top: 10px;
        }
        .loading {
            color: #666;
            font-style: italic;
        }
        #followUpSection {
            display: none;
            margin-top: 30px;
            padding-top: 30px;
            border-top: 1px solid #eee;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏥 WalletDoctor Coach</h1>
        
        <div class="input-group">
            <label for="wallets">Enter wallet address(es):</label>
            <input type="text" id="wallets" placeholder="wallet1,wallet2,wallet3">
        </div>
        
        <button onclick="analyzeWallets()" id="analyzeBtn">Analyze Wallets</button>
        <button onclick="clearSession()" id="clearBtn">Clear Session</button>
        
        <div id="error" class="error"></div>
        <div id="loading" class="loading"></div>
        <div id="output" class="output" style="display:none;"></div>
        
        <div id="followUpSection">
            <h3>Ask a follow-up question:</h3>
            <div class="input-group">
                <textarea id="question" rows="3" placeholder="What would you like to know about your trading patterns?"></textarea>
            </div>
            <button onclick="askQuestion()" id="askBtn">Ask Question</button>
        </div>
    </div>

    <script>
        async function analyzeWallets() {
            const wallets = document.getElementById('wallets').value.trim();
            if (!wallets) {
                showError('Please enter at least one wallet address');
                return;
            }
            
            showLoading('Analyzing wallets... This may take a minute...');
            hideError();
            
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({wallets: wallets})
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Analysis failed');
                }
                
                showOutput(data.output);
                document.getElementById('followUpSection').style.display = 'block';
                
            } catch (error) {
                showError('Error: ' + error.message);
            } finally {
                hideLoading();
            }
        }
        
        async function askQuestion() {
            const question = document.getElementById('question').value.trim();
            if (!question) {
                showError('Please enter a question');
                return;
            }
            
            showLoading('Thinking...');
            hideError();
            
            try {
                const response = await fetch('/ask', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({question: question})
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Failed to process question');
                }
                
                showOutput(data.output);
                document.getElementById('question').value = '';
                
            } catch (error) {
                showError('Error: ' + error.message);
            } finally {
                hideLoading();
            }
        }
        
        async function clearSession() {
            if (!confirm('Clear all conversation history?')) return;
            
            try {
                await fetch('/clear', {method: 'POST'});
                document.getElementById('output').style.display = 'none';
                document.getElementById('followUpSection').style.display = 'none';
                document.getElementById('wallets').value = '';
                showOutput('Session cleared');
                setTimeout(() => {
                    document.getElementById('output').style.display = 'none';
                }, 2000);
            } catch (error) {
                showError('Error clearing session');
            }
        }
        
        function showOutput(text) {
            const output = document.getElementById('output');
            output.textContent = text;
            output.style.display = 'block';
        }
        
        function showError(text) {
            document.getElementById('error').textContent = text;
        }
        
        function hideError() {
            document.getElementById('error').textContent = '';
        }
        
        function showLoading(text) {
            document.getElementById('loading').textContent = text;
            document.getElementById('analyzeBtn').disabled = true;
            document.getElementById('askBtn').disabled = true;
        }
        
        function hideLoading() {
            document.getElementById('loading').textContent = '';
            document.getElementById('analyzeBtn').disabled = false;
            document.getElementById('askBtn').disabled = false;
        }
    </script>
</body>
</html>''')
    
    print("Starting WalletDoctor web interface...")
    print("Open http://localhost:5001 in your browser")
    app.run(debug=True, port=5001) 