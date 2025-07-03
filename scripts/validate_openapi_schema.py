#!/usr/bin/env python3
"""Validate OpenAPI schema version and structure for CI."""

import json
import sys
from pathlib import Path


def validate_schema_version(openapi_file, expected_version):
    """Validate that the OpenAPI spec has the expected version."""
    
    try:
        with open(openapi_file, 'r') as f:
            openapi = json.load(f)
        
        # Check OpenAPI version
        if openapi.get('openapi') != '3.1.0':
            print(f"❌ OpenAPI version must be 3.1.0, found: {openapi.get('openapi')}")
            return False
        
        # Check API version
        actual_version = openapi.get('info', {}).get('version')
        if actual_version != expected_version:
            print(f"❌ API version mismatch! Expected: {expected_version}, Found: {actual_version}")
            return False
        
        # Validate required components exist
        schemas = openapi.get('components', {}).get('schemas', {})
        required_schemas = ['ExportResponse', 'Trade', 'TokenFlow', 'ErrorResponse']
        
        missing_schemas = [s for s in required_schemas if s not in schemas]
        if missing_schemas:
            print(f"❌ Missing required schemas: {missing_schemas}")
            return False
        
        # Validate endpoint exists
        paths = openapi.get('paths', {})
        if '/v4/trades/export-gpt/{wallet}' not in paths:
            print("❌ Missing required endpoint: /v4/trades/export-gpt/{wallet}")
            return False
        
        # Check for breaking changes in Trade schema
        trade_schema = schemas.get('Trade', {})
        required_trade_fields = [
            'action', 'amount', 'dex', 'fees_usd', 'pnl_usd', 
            'position_closed', 'price', 'priced', 'signature',
            'timestamp', 'token', 'token_in', 'token_out', 
            'tx_type', 'value_usd'
        ]
        
        trade_required = trade_schema.get('required', [])
        missing_fields = [f for f in required_trade_fields if f not in trade_required]
        if missing_fields:
            print(f"❌ Trade schema missing required fields: {missing_fields}")
            return False
        
        print(f"✅ Schema validation passed for v{expected_version}")
        print(f"   - OpenAPI version: 3.1.0")
        print(f"   - API version: {actual_version}")
        print(f"   - All required schemas present")
        print(f"   - Trade schema has all required fields")
        return True
        
    except Exception as e:
        print(f"❌ Error validating schema: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python validate_openapi_schema.py <openapi.json> <expected_version>")
        print("Example: python validate_openapi_schema.py schemas/trades_export_v0.7.0_openapi.json 0.7.0")
        sys.exit(1)
    
    openapi_file = sys.argv[1]
    expected_version = sys.argv[2]
    
    if validate_schema_version(openapi_file, expected_version):
        sys.exit(0)
    else:
        sys.exit(1) 