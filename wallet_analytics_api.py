"""
WalletDoctor Analytics API
HTTP endpoint for GPT Actions integration
"""

from flask import Flask, request, jsonify
import os
import tempfile
import hashlib
from werkzeug.utils import secure_filename
from wallet_analytics_service import analyze_trading_csv
import json
from datetime import datetime

app = Flask(__name__)

# Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {'csv'}
ANALYSIS_TIMEOUT = 25  # seconds (leaving 5s buffer for GPT's 30s timeout)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'wallet-analytics',
        'version': '2.0'
    })

@app.route('/analyze', methods=['POST'])
def analyze_wallet():
    """Main analysis endpoint for GPT Actions"""
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Validate file
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only CSV files are accepted'}), 400
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({'error': f'File too large. Maximum size is {MAX_FILE_SIZE/1024/1024}MB'}), 400
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            # Run analysis with timeout protection (Unix only)
            try:
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Analysis timeout")
                
                # Set timeout
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(ANALYSIS_TIMEOUT)
                
                try:
                    # Perform analysis
                    result = analyze_trading_csv(tmp_path)
                    
                    # Cancel timeout
                    signal.alarm(0)
                    
                except TimeoutError:
                    return jsonify({'error': 'Analysis timeout. File may be too large or complex'}), 408
                    
            except (ImportError, AttributeError):
                # Fallback for non-Unix systems (no timeout protection)
                result = analyze_trading_csv(tmp_path)
            
            # Add disclaimer
            if 'error' not in result:
                result['disclaimer'] = "This analysis is for informational purposes only. Not financial advice."
            
            return jsonify(result)
                
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
            
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/openapi.json', methods=['GET'])
def openapi_spec():
    """Return OpenAPI specification for GPT Actions"""
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "WalletDoctor Analytics API",
            "version": "2.0",
            "description": "Trading analytics service for CSV data analysis"
        },
        "servers": [
            {
                "url": os.environ.get('API_BASE_URL', 'http://localhost:5000'),
                "description": "Analytics API server"
            }
        ],
        "paths": {
            "/analyze": {
                "post": {
                    "summary": "Analyze trading data from CSV",
                    "description": "Upload a CSV file with trading data to receive comprehensive analytics",
                    "operationId": "analyzeWallet",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "file": {
                                            "type": "string",
                                            "format": "binary",
                                            "description": "CSV file with trading data"
                                        }
                                    },
                                    "required": ["file"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Successful analysis",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "summary": {"type": "object"},
                                            "pnl_analysis": {"type": "object"},
                                            "fee_analysis": {"type": "object"},
                                            "timing_analysis": {"type": "object"},
                                            "risk_analysis": {"type": "object"},
                                            "psychological_analysis": {"type": "object"},
                                            "metadata": {"type": "object"},
                                            "disclaimer": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        },
                        "400": {
                            "description": "Bad request",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "error": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    return jsonify(spec)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
