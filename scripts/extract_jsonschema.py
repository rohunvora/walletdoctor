#!/usr/bin/env python3
"""Extract JSONSchema from OpenAPI spec for trades export endpoint."""

import json
import sys
from pathlib import Path


def extract_schemas(openapi_file, output_dir):
    """Extract component schemas from OpenAPI spec to individual JSONSchema files."""
    
    # Read OpenAPI spec
    with open(openapi_file, 'r') as f:
        openapi = json.load(f)
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Extract version info
    version = openapi['info']['version']
    
    # Extract schemas
    schemas = openapi.get('components', {}).get('schemas', {})
    
    if not schemas:
        print("No schemas found in OpenAPI spec")
        return
    
    # Save each schema as a separate JSONSchema file
    for schema_name, schema_def in schemas.items():
        # Create JSONSchema document
        jsonschema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$id": f"https://walletdoctor.app/schemas/{version}/{schema_name}.json",
            "title": schema_name,
            "description": schema_def.get('description', f'{schema_name} schema'),
            **schema_def
        }
        
        # Write schema file
        output_file = output_path / f"{schema_name}_v{version}.json"
        with open(output_file, 'w') as f:
            json.dump(jsonschema, f, indent=2)
        
        print(f"✅ Created {output_file}")
    
    # Also create a combined schema file with all definitions
    combined_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": f"https://walletdoctor.app/schemas/{version}/trades_export.json",
        "title": "WalletDoctor Trades Export Schemas",
        "description": f"All schemas for trades export API v{version}",
        "definitions": schemas
    }
    
    combined_file = output_path / f"trades_export_combined_v{version}.json"
    with open(combined_file, 'w') as f:
        json.dump(combined_schema, f, indent=2)
    
    print(f"\n✅ Created combined schema: {combined_file}")
    print(f"\nExtracted {len(schemas)} schemas total")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_jsonschema.py <openapi.json> <output_dir>")
        sys.exit(1)
    
    openapi_file = sys.argv[1]
    output_dir = sys.argv[2]
    
    try:
        extract_schemas(openapi_file, output_dir)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1) 