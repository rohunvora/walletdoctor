"""
Test to ensure GPT prompt templates stay under size limits
"""

import os


def test_prompt_size():
    """Ensure trade insight prompts stay under 4KB for efficient loading"""
    prompt_dir = "docs/gpt_prompts"
    max_size = 4 * 1024  # 4KB
    
    # Only check trade insights prompts
    trade_prompt_files = [
        "trade_insights_v1.md"
    ]
    
    for filename in trade_prompt_files:
        filepath = os.path.join(prompt_dir, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            
            assert size <= max_size, f"{filename} is {size} bytes (max: {max_size} bytes)"
            print(f"✓ {filename}: {size} bytes")


if __name__ == "__main__":
    test_prompt_size() 