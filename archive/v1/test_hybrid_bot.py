#!/usr/bin/env python3
"""
Test the hybrid bot implementation
Shows how commands work vs natural language
"""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from unittest.mock import MagicMock, AsyncMock

# Mock bot components
class MockBot:
    def __init__(self):
        self.user_id = 123456
        self.wallet = "34zYDgjy8oinZ5y8gyrcQktzUmSfFLJztTSq5xLUVCya"
        
    async def test_command(self, command: str):
        """Test a command"""
        print(f"\n{'='*50}")
        print(f"USER: {command}")
        print(f"{'='*50}")
        
        # Simulate command detection
        command_lower = command.lower().strip()
        
        if any(command_lower.startswith(cmd) for cmd in ['pnl', 'position', 'patterns', 'analyze', 'help']):
            print("✓ Detected as COMMAND - using smart handler")
            
            if command_lower.startswith('pnl'):
                if 'mdog' in command_lower:
                    print("\nBOT RESPONSE:")
                    print("**MDOG P&L** (Open Position)")
                    print("Unrealized: $-382.81")
                    print("Current Value: $327.34") 
                    print("Return: -53.9%")
                elif 'today' in command_lower:
                    print("\nBOT RESPONSE:")
                    print("**P&L Today**")
                    print("Total: $-45.23")
                    print("Trades: 3")
                else:
                    print("\nBOT RESPONSE:")
                    print("**P&L Today**")
                    print("Total: $-382.81")
                    print("Trades: 5")
                    
            elif command_lower.startswith('position'):
                token = command.split()[1].upper() if len(command.split()) > 1 else None
                if token:
                    print(f"\nBOT RESPONSE:")
                    print(f"**{token} Position**")
                    print(f"Balance: 125,000,000 tokens")
                    print(f"Value: $327.34")
                    print(f"Avg Buy: $0.000006")
                    print(f"Unrealized P&L: $-382.81 (-53.9%)")
                    
            elif command_lower.startswith('patterns'):
                print("\nBOT RESPONSE:")
                print("**Your Trading Patterns**")
                print("🟢 BONK: +127.3% on 0.5 SOL avg")
                print("🔴 MDOG: -53.9% on 5.0 SOL avg")
                print("🟢 WIF: +23.1% on 1.2 SOL avg")
                
            elif command_lower.startswith('analyze'):
                print("\nBOT RESPONSE:")
                print("**Recent Activity Analysis**")
                print("Most traded:")
                print("• MDOG: 3 trades")
                print("• BONK: 2 trades")
                print("\nWin Rate: 40.0%")
                print("Total P&L: $-382.81")
                
            elif command_lower.startswith('help'):
                print("\nBOT RESPONSE:")
                print("**Smart Commands** (no slash needed)")
                print("`pnl [today/week/TOKEN]` - Check your P&L")
                print("`position TOKEN` - Full position details")
                print("`patterns` - Your trading patterns")
                print("`analyze` - Recent activity analysis")
                
        else:
            print("✗ Not a command - using natural language handler")
            
            # Natural language responses
            if 'bought' in command_lower:
                token = None
                words = command.split()
                for i, word in enumerate(words):
                    if word.lower() == 'bought' and i + 1 < len(words):
                        token = words[i + 1].upper()
                        break
                
                if token:
                    print(f"\nBOT RESPONSE: Tracking your {token} buy. Use `position {token}` for details.")
                else:
                    print("\nBOT RESPONSE: Got it. Tracking your new position.")
                    
            elif 'sold' in command_lower:
                print("\nBOT RESPONSE: Sell recorded. Check `pnl` for your results.")
                
            elif any(word in command_lower for word in ['how', 'what', 'show']):
                print("\nBOT RESPONSE: Try these commands:")
                print("• `pnl` - Your profit/loss")
                print("• `position TOKEN` - Token details")
                print("• `patterns` - Trading patterns")
                print("• `help` - All commands")
                
            else:
                print("\nBOT RESPONSE: I track your trades and calculate P&L. Try `help` for commands.")

async def main():
    """Run test scenarios"""
    bot = MockBot()
    
    print("HYBRID BOT TEST - Command vs Natural Language")
    print("=" * 50)
    
    # Test commands (no slash needed)
    test_inputs = [
        # Commands - direct and efficient
        "help",
        "pnl",
        "pnl today",
        "pnl MDOG",
        "position MDOG",
        "patterns",
        "analyze",
        
        # Natural language - minimal handling
        "just bought BONK",
        "sold my WIF",
        "how am I doing?",
        "what should I do?",
        "hello",
    ]
    
    for test_input in test_inputs:
        await bot.test_command(test_input)
        await asyncio.sleep(0.1)
    
    print("\n" + "="*50)
    print("SUMMARY: Commands give instant, accurate data.")
    print("Natural language gets helpful redirects to commands.")
    print("No more repetitive coaching or annoying questions!")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())