#!/usr/bin/env python3
"""
WalletDoctor Bot - Automated Setup
This does everything except getting your token from BotFather
"""

import os
import sys
import subprocess
import time
from pathlib import Path

class BotSetup:
    def __init__(self):
        self.green = '\033[92m'
        self.yellow = '\033[93m'
        self.red = '\033[91m'
        self.blue = '\033[94m'
        self.end = '\033[0m'
        
    def print_header(self):
        print(f"""
{self.blue}╔══════════════════════════════════════╗
║      🏥 WalletDoctor Bot Setup       ║
╚══════════════════════════════════════╝{self.end}
        """)
        
    def check_dependencies(self):
        """Check if required packages are installed"""
        print(f"\n{self.yellow}📦 Checking dependencies...{self.end}")
        
        try:
            import telegram
            import dotenv
            print(f"{self.green}✅ Dependencies already installed!{self.end}")
            return True
        except ImportError:
            return False
            
    def install_dependencies(self):
        """Install required packages"""
        print(f"\n{self.yellow}📦 Installing dependencies...{self.end}")
        
        cmd = [sys.executable, "-m", "pip", "install", "--user", "--break-system-packages", 
               "python-telegram-bot==20.7", "python-dotenv"]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"{self.green}✅ Dependencies installed!{self.end}")
            return True
        except subprocess.CalledProcessError:
            print(f"{self.red}❌ Failed to install dependencies{self.end}")
            print("Try running manually:")
            print(f"pip3 install --user --break-system-packages python-telegram-bot==20.7 python-dotenv")
            return False
            
    def create_env_file(self):
        """Create .env file with placeholder"""
        if not os.path.exists('.env'):
            with open('.env', 'w') as f:
                f.write("TELEGRAM_BOT_TOKEN=YOUR_TOKEN_HERE\n")
            print(f"{self.green}✅ Created .env file{self.end}")
        else:
            print(f"{self.blue}📄 .env file already exists{self.end}")
            
    def get_token_instructions(self):
        """Show clear instructions for getting token"""
        print(f"""
{self.blue}═══════════════════════════════════════════════════════{self.end}
{self.yellow}🤖 NOW YOU NEED TO GET YOUR BOT TOKEN (2 minutes):{self.end}

1. {self.green}Open Telegram on your phone/computer{self.end}

2. {self.green}Search for:{self.end} @BotFather

3. {self.green}Send these messages to BotFather:{self.end}
   → /newbot
   → My WalletDoctor     (when asked for name)
   → mywalletdoctor_bot  (when asked for username)

4. {self.green}BotFather will reply with:{self.end}
   "Done! Your token is: {self.yellow}1234567890:ABCdefGHIjklMNOpqrsTUVwxyz{self.end}"
   
5. {self.green}Copy that token!{self.end}
{self.blue}═══════════════════════════════════════════════════════{self.end}
        """)
        
    def wait_for_token(self):
        """Interactive token setup"""
        print(f"\n{self.yellow}📝 Have you created your bot and copied the token?{self.end}")
        print(f"Press {self.green}Enter{self.end} when ready to paste your token...")
        input()
        
        print(f"\n{self.yellow}🔑 Paste your bot token here:{self.end}")
        token = input("> ").strip()
        
        if token and len(token) > 40 and ':' in token:
            # Update .env file
            with open('.env', 'w') as f:
                f.write(f"TELEGRAM_BOT_TOKEN={token}\n")
                
            print(f"\n{self.green}✅ Token saved to .env file!{self.end}")
            return True
        else:
            print(f"\n{self.red}❌ That doesn't look like a valid token{self.end}")
            print(f"Tokens look like: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
            return False
            
    def test_bot(self):
        """Test if bot can start"""
        print(f"\n{self.yellow}🧪 Testing bot setup...{self.end}")
        
        # Just check if imports work
        try:
            from telegram_bot import WalletDoctorBot
            print(f"{self.green}✅ Bot code is valid!{self.end}")
            return True
        except Exception as e:
            print(f"{self.red}❌ Error: {e}{self.end}")
            return False
            
    def show_next_steps(self):
        """Show how to run the bot"""
        print(f"""
{self.green}🎉 SETUP COMPLETE!{self.end}

{self.yellow}To start your bot:{self.end}
    python3 telegram_bot.py

{self.yellow}Then in Telegram:{self.end}
    1. Search for your bot: @mywalletdoctor_bot
    2. Send: /start
    3. Follow the prompts!

{self.yellow}Commands:{self.end}
    /start    - Begin setup
    /patterns - View your patterns
    /recent   - Recent trades
    /help     - All commands

{self.blue}Need help? Check QUICKSTART.md{self.end}
        """)
        
    def run(self):
        """Run the complete setup"""
        self.print_header()
        
        # Check/install dependencies
        if not self.check_dependencies():
            if not self.install_dependencies():
                return
                
        # Create .env
        self.create_env_file()
        
        # Get token
        self.get_token_instructions()
        
        if self.wait_for_token():
            if self.test_bot():
                self.show_next_steps()
                
                print(f"\n{self.yellow}🚀 Ready to start the bot? (y/n){self.end}")
                if input("> ").lower() == 'y':
                    print(f"\n{self.green}Starting WalletDoctor Bot...{self.end}")
                    os.system("python3 telegram_bot.py")
        else:
            print(f"\n{self.yellow}You can add the token later to .env file{self.end}")
            self.show_next_steps()

if __name__ == "__main__":
    setup = BotSetup()
    setup.run() 