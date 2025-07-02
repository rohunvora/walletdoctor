#!/usr/bin/env python3
"""
Minimal test app to isolate Railway startup issues
"""

import os
import sys
import logging
from flask import Flask, jsonify

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("="*60)
logger.info("MINIMAL TEST APP STARTING")
logger.info(f"Python version: {sys.version}")
logger.info(f"HELIUS_KEY present: {bool(os.getenv('HELIUS_KEY'))}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Python path: {sys.path}")
logger.info("="*60)

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "app": "minimal_test",
        "helius_key_present": bool(os.getenv("HELIUS_KEY")),
        "python_version": sys.version
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "app": "minimal"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True) 