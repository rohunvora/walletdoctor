#!/usr/bin/env python3
"""Validate the cleaned OpenAPI schema for ChatGPT compatibility."""

import json
import sys


def validate_schema(filename):
    """Validate OpenAPI schema for ChatGPT Actions requirements."""
    print(f"Validating {filename}...")
    
    try:
        with open(filename, 'r') as f:
            schema = json.load(f)
        print("✅ Valid JSON format")
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ File not found: {filename}")
        return False
    
    # Check OpenAPI version
    if schema.get('openapi') != '3.1.0':
        print(f"❌ OpenAPI version must be 3.1.0, got: {schema.get('openapi')}")
        return False
    print("✅ OpenAPI 3.1.0")
    
    # Check servers
    servers = schema.get('servers', [])
    if len(servers) != 1:
        print(f"❌ Must have exactly 1 server, got: {len(servers)}")
        return False
    
    if any('localhost' in s.get('url', '') for s in servers):
        print("❌ Localhost servers not allowed")
        return False
    print("✅ Single production server")
    
    # Check for nullable fields
    nullable_count = 0
    def check_nullable(obj, path=""):
        nonlocal nullable_count
        if isinstance(obj, dict):
            if obj.get('nullable') is True:
                nullable_count += 1
            for k, v in obj.items():
                check_nullable(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_nullable(item, f"{path}[{i}]")
    
    check_nullable(schema)
    print(f"✅ Found {nullable_count} nullable fields")
    
    # Check required components
    if 'paths' not in schema:
        print("❌ Missing 'paths'")
        return False
    
    if 'components' not in schema:
        print("❌ Missing 'components'")
        return False
    
    print("✅ All required sections present")
    
    # Check for common issues
    str_schema = json.dumps(schema)
    if ',\n}' in str_schema or ',\n]' in str_schema:
        print("⚠️  Warning: Possible trailing commas detected")
    
    print("\n✅ Schema validation passed!")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = "walletdoctor_action_clean.json"
    
    if validate_schema(filename):
        sys.exit(0)
    else:
        sys.exit(1) 