#!/usr/bin/env python3
"""
Test the quick fix - reuse prices within 5 minute window
"""

from datetime import datetime, timedelta
from collections import defaultdict

# Simulate the price cache behavior
class QuickFixSimulation:
    def __init__(self):
        self.price_cache = {}  # (mint, minute_timestamp) -> price
        self.api_calls = 0
        
    def simulate_trades(self, num_trades=1076):
        """Simulate processing trades with timestamps"""
        
        # Create trades spread over time
        trades = []
        base_time = datetime.now()
        
        # 70% of trades in last 5 minutes (recent trading)
        # 20% of trades in last hour
        # 10% of trades older
        
        for i in range(num_trades):
            if i < int(num_trades * 0.7):
                # Recent trades (0-5 minutes ago)
                minutes_ago = i % 5
                timestamp = base_time - timedelta(minutes=minutes_ago)
            elif i < int(num_trades * 0.9):
                # Medium age trades (5-60 minutes ago)
                minutes_ago = 5 + (i % 55)
                timestamp = base_time - timedelta(minutes=minutes_ago)
            else:
                # Old trades (hours/days ago)
                hours_ago = 2 + (i % 48)
                timestamp = base_time - timedelta(hours=hours_ago)
            
            # Simulate token diversity
            # Most trades are in popular tokens
            if i % 10 < 7:
                token = f"popular_token_{i % 20}"  # 20 popular tokens
            else:
                token = f"rare_token_{i}"  # Many rare tokens
                
            trades.append((timestamp, token))
        
        return trades
    
    def process_without_cache(self, trades):
        """Current approach - fetch price for every trade"""
        unique_requests = set()
        
        for timestamp, token in trades:
            minute_ts = int(timestamp.timestamp() // 60)
            unique_requests.add((token, minute_ts))
        
        # Batch into groups of 100
        batches = len(unique_requests) // 100 + (1 if len(unique_requests) % 100 else 0)
        
        print(f"Without optimization:")
        print(f"  Unique price points: {len(unique_requests)}")
        print(f"  Birdeye batches: {batches}")
        print(f"  Estimated time: {batches}s (1 req/sec)")
        
        return batches
    
    def process_with_5min_cache(self, trades):
        """Optimized - reuse prices within 5 minute window"""
        unique_requests = set()
        cache_hits = 0
        
        # Group by token first
        token_timestamps = defaultdict(list)
        for timestamp, token in trades:
            token_timestamps[token].append(timestamp)
        
        # For each token, only fetch once per 5-minute window
        for token, timestamps in token_timestamps.items():
            timestamps.sort()
            
            last_fetch = None
            for ts in timestamps:
                if last_fetch is None or (ts - last_fetch).seconds > 300:  # 5 minutes
                    minute_ts = int(ts.timestamp() // 60)
                    unique_requests.add((token, minute_ts))
                    last_fetch = ts
                else:
                    cache_hits += 1
        
        # Batch into groups of 100
        batches = len(unique_requests) // 100 + (1 if len(unique_requests) % 100 else 0)
        
        print(f"\nWith 5-minute cache reuse:")
        print(f"  Cache hits: {cache_hits}")
        print(f"  Unique price points: {len(unique_requests)}")
        print(f"  Birdeye batches: {batches}")
        print(f"  Estimated time: {batches}s (1 req/sec)")
        print(f"  Time saved: {self.api_calls - batches}s")
        
        return batches

def main():
    print("=== Quick Fix Simulation ===")
    print("Simulating price lookups for 1076 trades...")
    print("")
    
    sim = QuickFixSimulation()
    trades = sim.simulate_trades(1076)
    
    # Current approach
    current_batches = sim.process_without_cache(trades)
    sim.api_calls = current_batches
    
    # Optimized approach
    optimized_batches = sim.process_with_5min_cache(trades)
    
    print(f"\nReduction: {((current_batches - optimized_batches) / current_batches * 100):.1f}%")
    print(f"\nExpected performance:")
    print(f"  Helius fetch: ~3s")
    print(f"  Birdeye fetch: ~{optimized_batches}s")
    print(f"  Total: ~{3 + optimized_batches}s (vs 45s+ currently)")

if __name__ == "__main__":
    main() 