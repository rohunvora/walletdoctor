#!/usr/bin/env python3
"""
Setup script for Tradebro
Helps users configure their API keys securely
"""

import os
import sys
from pathlib import Path

def setup_api_keys():
    """Interactive setup for API keys."""
    print("🩺 Tradebro Setup")
    print("=" * 50)
    print("This script will help you set up your API keys.")
    print("Your keys will be saved in a .env file (not tracked by git)")
    print()
    
    # Check if .env already exists
    env_path = Path(".env")
    if env_path.exists():
        overwrite = input(".env file already exists. Overwrite? (y/N): ")
        if overwrite.lower() != 'y':
            print("Setup cancelled.")
            return
    
    print("\n📋 You'll need API keys from:")
    print("1. Helius: https://dev.helius.xyz/")
    print("2. Cielo: https://cielo.finance/")
    print("3. OpenAI: https://platform.openai.com/")
    print()
    
    # Collect API keys
    helius_key = input("Enter your Helius API key: ").strip()
    cielo_key = input("Enter your Cielo API key: ").strip()
    openai_key = input("Enter your OpenAI API key: ").strip()
    
    # Write to .env file
    env_content = f"""# Tradebro API Keys
# Generated by setup.py

HELIUS_KEY={helius_key}
CIELO_KEY={cielo_key}
OPENAI_API_KEY={openai_key}
"""
    
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("\n✅ API keys saved to .env file")
    print("\nTo use Tradebro:")
    print("1. Activate your virtual environment: source venv/bin/activate")
    print("2. Load wallet data: python coach.py load <wallet-address>")
    print("3. View stats: python coach.py stats")
    print("4. Get AI insights: python coach.py chat")
    
    # Also export to current shell
    print("\nTo use immediately in this shell session:")
    print(f"export HELIUS_KEY={helius_key}")
    print(f"export CIELO_KEY={cielo_key}")
    print(f"export OPENAI_API_KEY={openai_key}")

if __name__ == "__main__":
    setup_api_keys() 