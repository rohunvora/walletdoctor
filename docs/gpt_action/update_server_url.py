#!/usr/bin/env python3
"""Update the server URL in the OpenAPI spec."""

import json
import sys


def update_server_url(filename, new_url):
    """Update the server URL in the OpenAPI spec."""
    print(f"Updating {filename} with URL: {new_url}")
    
    try:
        with open(filename, 'r') as f:
            spec = json.load(f)
        
        # Update the servers section
        spec['servers'] = [
            {
                "url": new_url,
                "description": "Railway deployment (public beta)"
            }
        ]
        
        # Write back with proper formatting
        with open(filename, 'w') as f:
            json.dump(spec, f, indent=2)
            f.write('\n')  # Add trailing newline
        
        print(f"✅ Updated server URL to: {new_url}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating spec: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python update_server_url.py <railway_url>")
        print("Example: python update_server_url.py https://walletdoctor-production-xyz.up.railway.app")
        sys.exit(1)
    
    new_url = sys.argv[1]
    
    # Validate URL format
    if not new_url.startswith("https://"):
        print("❌ URL must start with https://")
        sys.exit(1)
    
    # Update the clean spec
    if update_server_url("walletdoctor_action_clean.json", new_url):
        print("\n✅ OpenAPI spec updated successfully!")
        print("\nNext steps:")
        print("1. Test the endpoint with curl")
        print("2. Re-import the updated spec into ChatGPT")
        print("3. Run the round-trip tests")
    else:
        sys.exit(1) 