#!/usr/bin/env python3
"""
WalletDoctor Analytics API v2
Accepts wallet addresses and returns comprehensive trade analytics
"""

import os
import sys
import json
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from blockchain_fetcher import fetch_wallet_trades
from wallet_analytics_service import analyze_trading_csv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': '2.0',
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/analyze_wallet', methods=['POST'])
def analyze_wallet():
    """
    Analyze trading activity for a Solana wallet address
    
    Expected JSON payload:
    {
        "wallet_address": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    }
    """
    try:
        # Get wallet address from request
        data = request.get_json()
        if not data or 'wallet_address' not in data:
            return jsonify({
                'error': 'Missing wallet_address in request body'
            }), 400
            
        wallet_address = data['wallet_address']
        logger.info(f"Analyzing wallet: {wallet_address}")
        
        # Progress tracking
        progress_messages = []
        def track_progress(msg):
            progress_messages.append(msg)
            logger.info(msg)
        
        # Fetch trades from blockchain
        logger.info("Fetching trades from blockchain...")
        trades = fetch_wallet_trades(wallet_address, track_progress)
        
        if not trades:
            return jsonify({
                'error': 'No trades found for this wallet',
                'wallet_address': wallet_address,
                'progress': progress_messages
            }), 404
            
        # Convert trades to CSV format for analyzer
        import tempfile
        import csv
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
            fieldnames = ['timestamp', 'action', 'token', 'amount', 'price', 'value_usd', 'pnl_usd', 'fees_usd']
            writer = csv.DictWriter(tmp, fieldnames=fieldnames)
            writer.writeheader()
            
            for trade in trades:
                writer.writerow({
                    'timestamp': trade['timestamp'],
                    'action': trade['action'],
                    'token': trade['token'],
                    'amount': trade['amount'],
                    'price': trade.get('price', 0),
                    'value_usd': trade.get('value_usd', 0),
                    'pnl_usd': trade.get('pnl_usd', 0),
                    'fees_usd': trade.get('fees_usd', 0)
                })
            tmp_path = tmp.name
            
        # Run analytics
        logger.info(f"Running analytics on {len(trades)} trades...")
        results = analyze_trading_csv(tmp_path)
        
        # Clean up temp file
        import os
        os.unlink(tmp_path)
        
        # Add metadata
        results['metadata'] = {
            'wallet_address': wallet_address,
            'total_trades_fetched': len(trades),
            'total_trades_analyzed': len(trades),
            'fetch_timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info("Analysis complete")
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error analyzing wallet: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500


@app.route('/openapi.json', methods=['GET'])
def openapi_spec():
    """Return OpenAPI specification for GPT integration"""
    return jsonify({
        "openapi": "3.0.0",
        "info": {
            "title": "WalletDoctor Analytics API v2",
            "description": "Analyze Solana wallet trading performance",
            "version": "2.0.0"
        },
        "servers": [
            {
                "url": request.url_root.rstrip('/')
            }
        ],
        "paths": {
            "/analyze_wallet": {
                "post": {
                    "summary": "Analyze wallet trading activity",
                    "description": "Fetches all trades for a Solana wallet and returns comprehensive analytics",
                    "operationId": "analyzeWallet",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["wallet_address"],
                                    "properties": {
                                        "wallet_address": {
                                            "type": "string",
                                            "description": "Solana wallet address to analyze",
                                            "example": "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Analysis results",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "summary": {
                                                "type": "object",
                                                "description": "Overall trading summary"
                                            },
                                            "metrics": {
                                                "type": "object",
                                                "description": "Detailed performance metrics"
                                            },
                                            "token_analysis": {
                                                "type": "array",
                                                "description": "Per-token performance"
                                            },
                                            "metadata": {
                                                "type": "object",
                                                "description": "Request metadata"
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "400": {
                            "description": "Bad request - missing wallet address"
                        },
                        "404": {
                            "description": "No trades found for wallet"
                        },
                        "500": {
                            "description": "Server error"
                        }
                    }
                }
            }
        }
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False) 