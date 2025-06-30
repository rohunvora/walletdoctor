#!/usr/bin/env python3
"""Verify actual transaction count using Solana RPC"""

import os
import asyncio
import aiohttp
import json

HELIUS_KEY = os.getenv("HELIUS_KEY", "09cd02b2-f35d-4d54-ac9b-a9033919d6ee")
WALLET = "3JoVBiQEA2QKsq7TzW5ez5jVRtbbYgTNijoZzp5qgkr2"

async def count_all_transactions():
    """Count all transactions using RPC pagination"""
    
    async with aiohttp.ClientSession() as session:
        rpc_url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
        
        all_signatures = []
        before_signature = None
        page = 0
        
        print(f"Counting all transactions for wallet: {WALLET}")
        print("This may take a while for wallets with many transactions...")
        
        while True:
            # Prepare RPC request
            params = [
                WALLET,
                {
                    "limit": 1000,  # Max allowed
                    "commitment": "finalized"
                }
            ]
            
            if before_signature:
                params[1]["before"] = before_signature
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": params
            }
            
            async with session.post(rpc_url, json=payload) as resp:
                result = await resp.json()
                
                if "error" in result:
                    print(f"RPC Error: {result['error']}")
                    break
                    
                signatures = result.get("result", [])
                
                if not signatures:
                    print(f"No more signatures found")
                    break
                    
                all_signatures.extend(signatures)
                page += 1
                
                print(f"Page {page}: Got {len(signatures)} signatures (Total so far: {len(all_signatures)})")
                
                # Check if we got less than limit (last page)
                if len(signatures) < 1000:
                    print("Reached the end of transactions")
                    break
                    
                # Set up for next page
                before_signature = signatures[-1]["signature"]
                
                # Safety check to avoid infinite loops
                if page > 50:  # 50,000+ transactions would be unusual
                    print("Safety limit reached (50 pages)")
                    break
                    
        print(f"\n=== FINAL COUNT ===")
        print(f"Total transactions: {len(all_signatures)}")
        
        # Analyze transaction types if we have the full list
        if len(all_signatures) < 5000:  # Only analyze if reasonable size
            print("\nAnalyzing transaction details...")
            
            # Get enhanced data for a sample
            enhanced_url = f"https://api.helius.xyz/v0/transactions"
            
            # Sample first 100 signatures
            sample_sigs = [sig["signature"] for sig in all_signatures[:100]]
            
            params = {
                "api-key": HELIUS_KEY,
                "transactions": sample_sigs
            }
            
            async with session.get(enhanced_url, params=params) as resp:
                if resp.status == 200:
                    enhanced_data = await resp.json()
                    
                    # Count types
                    type_counts = {}
                    for tx in enhanced_data:
                        tx_type = tx.get("type", "UNKNOWN")
                        type_counts[tx_type] = type_counts.get(tx_type, 0) + 1
                        
                    print("\nSample of first 100 transactions:")
                    for tx_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                        print(f"  {tx_type}: {count}")
                        
        # Check swap percentage
        swap_estimate = 0
        if len(all_signatures) > 0:
            # Based on our sample, estimate swap percentage
            swap_percentage = 19 / 196  # From our previous analysis
            swap_estimate = int(len(all_signatures) * swap_percentage)
            
        print(f"\nEstimated SWAP transactions: ~{swap_estimate} ({swap_percentage*100:.1f}% of total)")
        
        return len(all_signatures)

if __name__ == "__main__":
    total = asyncio.run(count_all_transactions()) 