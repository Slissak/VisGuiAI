"""Generate OpenAPI JSON specification from FastAPI app."""
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from src.main import app

    # Generate OpenAPI JSON
    openapi_schema = app.openapi()

    # Write to file
    output_path = Path(__file__).parent / "docs" / "openapi.json"
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"OpenAPI specification generated successfully at: {output_path}")
    print(f"Total endpoints: {len([p for paths in openapi_schema.get('paths', {}).values() for p in paths])}")

except Exception as e:
    print(f"Error generating OpenAPI spec: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
