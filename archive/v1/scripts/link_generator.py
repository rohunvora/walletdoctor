#!/usr/bin/env python3
"""
Link Generator - Generate platform links for tokens
"""

import logging
from typing import Dict, List, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

class LinkGenerator:
    def __init__(self):
        # Platform URL templates
        self.templates = {
            'DS': 'https://dexscreener.com/solana/{mint}',  # DexScreener
            'PH': 'https://photon-sol.tinyastro.io/en/lp/{mint}',  # Photon
            'BE': 'https://birdeye.so/token/{mint}?chain=solana',  # Birdeye
            'Bullx': 'https://bullx.io/terminal?chainId=1399811149&address={mint}',  # Bullx
            'GMGN': 'https://gmgn.ai/sol/token/{mint}',  # GMGN
            'AXI': 'https://app.axioms.xyz/token/{mint}',  # Axioms
        }
        
    def generate_link(self, platform: str, mint: str) -> str:
        """Generate a link for a specific platform"""
        template = self.templates.get(platform)
        if template:
            return template.format(mint=mint)
        return ""
    
    def generate_clickable_link(self, platform: str, mint: str) -> str:
        """Generate a clickable link for Telegram"""
        link = self.generate_link(platform, mint)
        if link:
            return f"<a href='{link}'>{platform}</a>"
        return platform
    
    def generate_platform_links_text(self, mint: str, platforms: List[str] = None) -> str:
        """Generate platform links text like 'DS | PH'"""
        if platforms is None:
            platforms = ['DS', 'PH']  # Default platforms per user request
            
        links = []
        for platform in platforms:
            link = self.generate_clickable_link(platform, mint)
            links.append(link)
            
        return " | ".join(links)
    
    def generate_all_links(self, mint: str) -> Dict[str, str]:
        """Generate all available links for a token"""
        links = {}
        for platform, template in self.templates.items():
            links[platform] = template.format(mint=mint)
        return links

# Test function
def test_link_generator():
    """Test the link generator"""
    generator = LinkGenerator()
    
    # Test token
    test_mint = "6Nijf9VXcybuKUV2kP8WZ2CLKND6UjeFiDPBff3Zpump"
    
    # Generate individual links
    print("Individual links:")
    for platform in ['DS', 'PH']:
        link = generator.generate_link(platform, test_mint)
        print(f"{platform}: {link}")
    
    # Generate clickable links
    print("\nClickable links:")
    for platform in ['DS', 'PH']:
        link = generator.generate_clickable_link(platform, test_mint)
        print(f"{platform}: {link}")
    
    # Generate platform links text
    print("\nPlatform links text:")
    links_text = generator.generate_platform_links_text(test_mint)
    print(links_text)

if __name__ == "__main__":
    test_link_generator() 