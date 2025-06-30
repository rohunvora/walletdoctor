#!/usr/bin/env python3
"""
WalletDoctor API V3
Direct blockchain analysis via Helius
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.lib.blockchain_fetcher_v3_fast import BlockchainFetcherV3Fast
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def calculate_simple_analytics(trades: list) -> dict:
    """Calculate basic analytics from trades"""
    if not trades:
        return {
            "total_trades": 0,
            "total_volume": 0,
            "message": "No trades found"
        }
    
    total_volume = sum(t.get('total_value', 0) for t in trades)
    unique_tokens = set()
    
    for trade in trades:
        if trade.get('token_in'):
            unique_tokens.add(trade['token_in']['symbol'])
        if trade.get('token_out'):
            unique_tokens.add(trade['token_out']['symbol'])
    
    # Calculate simple P&L if we have prices
    profitable_trades = 0
    unprofitable_trades = 0
    
    for trade in trades:
        # Simple heuristic: if selling SOL for token, assume buying
        # if selling token for SOL, check if we made profit
        if trade.get('token_out', {}).get('symbol') == 'SOL':
            # This is a sell
            # Would need historical buy price to calculate real P&L
            pass
    
    return {
        "total_trades": len(trades),
        "total_volume": round(total_volume, 2),
        "unique_tokens": len(unique_tokens),
        "tokens_traded": sorted(list(unique_tokens))[:20],  # Top 20
        "date_range": {
            "first_trade": trades[-1]['timestamp'] if trades else None,
            "last_trade": trades[0]['timestamp'] if trades else None
        }
    }

async def fetch_and_analyze(wallet_address: str):
    """Fetch blockchain data and analyze"""
    logger.info(f"Starting analysis for wallet: {wallet_address}")
    
    # Fetch trades using V3 Fast
    async with BlockchainFetcherV3Fast(
        progress_callback=lambda msg: logger.info(msg),
        skip_pricing=False,
        max_pages=10  # Limit for API response time
    ) as fetcher:
        result = await fetcher.fetch_wallet_trades(wallet_address)
    
    # Extract data
    trades = result['trades']
    metrics = result['summary']['metrics']
    
    # Calculate simple analytics
    analytics = calculate_simple_analytics(trades)
    
    # Build response
    return {
        "wallet": wallet_address,
        "fetch_metrics": {
            "transactions_fetched": metrics['signatures_fetched'],
            "trades_parsed": metrics['signatures_parsed'],
            "parse_rate": f"{metrics['signatures_parsed']/metrics['signatures_fetched']*100:.1f}%",
            "from_events": metrics['events_swap_rows'],
            "from_fallback": metrics['fallback_rows']
        },
        "analytics": analytics,
        "sample_trades": trades[:5] if trades else [],  # First 5 trades as sample
        "note": "Full analytics integration coming soon. This is V3 preview."
    }

@app.route('/analyze', methods=['POST'])
def analyze_wallet():
    """
    Analyze a wallet by fetching data from blockchain
    
    Request body:
    {
        "wallet": "wallet_address"
    }
    """
    try:
        data = request.get_json()
        if not data or 'wallet' not in data:
            return jsonify({'error': 'Missing wallet address'}), 400
            
        wallet_address = data['wallet']
        
        # Validate wallet address format
        if not wallet_address or len(wallet_address) < 32:
            return jsonify({'error': 'Invalid wallet address'}), 400
            
        logger.info(f"Analyzing wallet: {wallet_address}")
        
        # Run async function
        result = asyncio.run(fetch_and_analyze(wallet_address))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error analyzing wallet: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'version': '3.0'})

@app.route('/', methods=['GET'])
def home():
    """Home endpoint with API info"""
    return jsonify({
        'service': 'WalletDoctor API V3',
        'version': '3.0',
        'endpoints': {
            '/analyze': 'POST - Analyze wallet (body: {"wallet": "address"})',
            '/health': 'GET - Health check',
            '/': 'GET - This info'
        },
        'features': [
            'Direct blockchain fetching via Helius',
            'Fallback parser for all DEX types', 
            'Real-time price data from Birdeye',
            'Parse rate: ~100% with fallback parser'
        ],
        'limits': {
            'max_pages': 10,
            'reason': 'API response time optimization'
        }
    })

if __name__ == '__main__':
    # For development
    app.run(host='0.0.0.0', port=8080, debug=True)
    
    # For production, use gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:8080 wallet_analytics_api_v3:app 