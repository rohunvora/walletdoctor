#!/usr/bin/env python3
"""Test the wallet analytics API v2"""

import os
import sys
import json
import time
import subprocess
import requests

# Set environment variables
os.environ['HELIUS_KEY'] = '09cd02b2-f35d-4d54-ac9b-a9033919d6ee'
os.environ['BIRDEYE_API_KEY'] = 'a0f62b924fb949d9a061a7ad24edc153'

# Start server
print("Starting API server...")
server = subprocess.Popen([sys.executable, 'wallet_analytics_api_v2.py'], 
                         stdout=subprocess.PIPE, 
                         stderr=subprocess.PIPE)

# Wait for startup
time.sleep(3)

try:
    # Test health endpoint
    print("Testing health endpoint...")
    response = requests.get('http://localhost:8080/health')
    print(f"Health check: {response.status_code}")
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
    
    # Test wallet analysis
    print("\nTesting wallet analysis...")
    wallet = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"
    response = requests.post('http://localhost:8080/analyze_wallet',
                           json={'wallet_address': wallet},
                           timeout=60)
    
    print(f"Analysis response: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("\nSummary:")
        print(json.dumps(result.get('summary', {}), indent=2))
        print("\nMetadata:")
        print(json.dumps(result.get('metadata', {}), indent=2))
        
        # Save full result
        with open('api_test_result.json', 'w') as f:
            json.dump(result, f, indent=2)
        print("\nFull result saved to api_test_result.json")
    else:
        print(f"Error: {response.text}")
        
except Exception as e:
    print(f"Test failed: {e}")
    
finally:
    # Stop server
    print("\nStopping server...")
    server.terminate()
    server.wait()
    
    # Print any server errors
    stdout, stderr = server.communicate()
    if stderr:
        print("Server errors:")
        print(stderr.decode())
        
print("Test complete.") 