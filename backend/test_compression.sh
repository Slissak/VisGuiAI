#!/bin/bash
# Test script to verify response compression

echo "================================================================================"
echo "FastAPI Response Compression Test"
echo "================================================================================"
echo ""

BASE_URL="http://localhost:8000"

# Function to test an endpoint
test_endpoint() {
    local method=$1
    local endpoint=$2
    local description=$3

    echo "--------------------------------------------------------------------------------"
    echo "Testing: $description"
    echo "Endpoint: $method $endpoint"
    echo "--------------------------------------------------------------------------------"

    # Get uncompressed size
    uncompressed_size=$(curl -s -X $method "$BASE_URL$endpoint" | wc -c | tr -d ' ')
    echo "Uncompressed size: $uncompressed_size bytes"

    # Get response headers with compression
    echo ""
    echo "Response headers (with Accept-Encoding: gzip):"
    headers=$(curl -s -I -H "Accept-Encoding: gzip" -X $method "$BASE_URL$endpoint")
    echo "$headers" | grep -i "content-encoding\|content-length\|transfer-encoding"

    # Check if content-encoding header is present
    if echo "$headers" | grep -qi "content-encoding: gzip"; then
        echo ""
        echo "✓ COMPRESSION ENABLED (gzip)"

        # Try to get actual compressed size (this is tricky with curl)
        # We'll use the transfer encoding instead
        compressed_response=$(curl -s -H "Accept-Encoding: gzip" -X $method "$BASE_URL$endpoint" --compressed)
        compressed_size=$(echo "$compressed_response" | wc -c | tr -d ' ')

        if [ $uncompressed_size -gt 0 ]; then
            ratio=$(echo "scale=2; (1 - $compressed_size / $uncompressed_size) * 100" | bc)
            savings=$((uncompressed_size - compressed_size))
            echo "Decompressed size: $compressed_size bytes"
            echo "Compression ratio: ${ratio}%"
            echo "Bytes saved: $savings bytes"
        fi
    else
        echo ""
        echo "✗ NO COMPRESSION"
        if [ $uncompressed_size -lt 1000 ]; then
            echo "  (Expected - response is < 1000 bytes threshold)"
        else
            echo "  (Unexpected - response is ≥ 1000 bytes)"
        fi
    fi
    echo ""
}

# Test various endpoints
test_endpoint "GET" "/" "Root endpoint (small response)"
test_endpoint "GET" "/api/v1/health" "Health check (small response)"
test_endpoint "GET" "/openapi.json" "OpenAPI specification (large response)"
test_endpoint "GET" "/docs" "API documentation (large response)"

echo "================================================================================"
echo "Test Complete"
echo "================================================================================"
echo ""
echo "Expected behavior:"
echo "- Responses < 1000 bytes: No compression (Content-Encoding header absent)"
echo "- Responses ≥ 1000 bytes: Compressed (Content-Encoding: gzip)"
echo ""
echo "If large responses are not compressed, the middleware may need server restart."
