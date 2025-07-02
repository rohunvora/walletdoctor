#!/usr/bin/env python3
"""
Check Railway environment for WAL-613 performance optimization
"""

import os
import json
import requests
import sys

# Key environment variables to check
REQUIRED_VARS = [
    "HELIUS_API_KEY",
    "BIRDEYE_API_KEY", 
    "WEB_CONCURRENCY",
    "GUNICORN_CMD_ARGS",
    "HELIUS_PARALLEL_REQUESTS",
    "HELIUS_MAX_RETRIES",
    "HELIUS_TIMEOUT",
    "POSITION_CACHE_TTL",
    "ENABLE_CACHE_WARMING",
    "PYTHONUNBUFFERED"
]

def check_local_env():
    """Check local environment variables"""
    print("=== Local Environment Variables ===")
    found = {}
    missing = []
    
    for var in REQUIRED_VARS:
        value = os.getenv(var)
        if value:
            # Mask sensitive keys
            if "KEY" in var or "API" in var:
                masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
                found[var] = masked
            else:
                found[var] = value
        else:
            missing.append(var)
    
    print("\n✅ Found:")
    for k, v in found.items():
        print(f"  {k} = {v}")
    
    if missing:
        print("\n❌ Missing:")
        for var in missing:
            print(f"  {var}")
    
    return found, missing


def check_remote_env(base_url):
    """Check remote environment via health endpoint"""
    try:
        url = f"{base_url}/health"
        print(f"\n=== Remote Environment Check ===")
        print(f"URL: {url}")
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed")
            print(f"Service: {data.get('service', 'unknown')}")
            print(f"Version: {data.get('version', 'unknown')}")
            
            # Check features
            features = data.get('features', {})
            if features:
                print("\nFeatures:")
                for k, v in features.items():
                    print(f"  {k}: {v}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error checking remote env: {e}")


def generate_railway_vars():
    """Generate Railway environment variables for copy/paste"""
    print("\n=== Railway Environment Variables (copy/paste) ===")
    
    vars_config = {
        "WEB_CONCURRENCY": "2",
        "GUNICORN_CMD_ARGS": "--timeout 120 --worker-class uvicorn.workers.UvicornWorker",
        "HELIUS_PARALLEL_REQUESTS": "5",
        "HELIUS_MAX_RETRIES": "2", 
        "HELIUS_TIMEOUT": "15",
        "POSITION_CACHE_TTL": "300",
        "ENABLE_CACHE_WARMING": "true",
        "PYTHONUNBUFFERED": "1"
    }
    
    print("\n# Add these to Railway (no quotes):")
    for k, v in vars_config.items():
        print(f"{k}={v}")
    
    print("\n# Ensure these API keys are set (keep existing values):")
    print("HELIUS_API_KEY=<your_key>")
    print("BIRDEYE_API_KEY=<your_key>")


def main():
    # Check local environment
    found, missing = check_local_env()
    
    # Generate Railway config
    generate_railway_vars()
    
    # Check remote if URL provided
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        check_remote_env(base_url)
    else:
        print("\n💡 Tip: Run with URL to check remote: python3 check_railway_env.py https://walletdoctor.app")


if __name__ == "__main__":
    main() 