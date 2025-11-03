#!/usr/bin/env python3
"""Test script to verify response compression and measure compression ratios.

This script tests the GZip compression middleware implementation by:
1. Making requests to API endpoints with and without compression
2. Comparing response sizes
3. Verifying compression headers
4. Reporting compression ratios
"""

import httpx
import json
import sys
from typing import Dict, Tuple


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ['B', 'KB', 'MB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} GB"


def test_endpoint_compression(
    base_url: str,
    endpoint: str,
    method: str = "GET",
    headers: Dict[str, str] = None,
    json_data: Dict = None
) -> Tuple[int, int, bool]:
    """Test an endpoint with and without compression.

    Returns:
        Tuple of (uncompressed_size, compressed_size, has_compression_header)
    """
    if headers is None:
        headers = {}

    # Request without compression support (no Accept-Encoding header)
    headers_no_compression = headers.copy()
    headers_no_compression.pop('Accept-Encoding', None)

    # Request with compression support
    headers_with_compression = headers.copy()
    headers_with_compression['Accept-Encoding'] = 'gzip, deflate'

    print(f"\n{'='*80}")
    print(f"Testing: {method} {endpoint}")
    print(f"{'='*80}")

    try:
        with httpx.Client(timeout=30.0) as client:
            # Test without compression
            if method == "GET":
                response_no_gzip = client.get(
                    f"{base_url}{endpoint}",
                    headers=headers_no_compression
                )
            elif method == "POST":
                response_no_gzip = client.post(
                    f"{base_url}{endpoint}",
                    headers=headers_no_compression,
                    json=json_data
                )

            uncompressed_size = len(response_no_gzip.content)

            # Test with compression
            if method == "GET":
                response_with_gzip = client.get(
                    f"{base_url}{endpoint}",
                    headers=headers_with_compression
                )
            elif method == "POST":
                response_with_gzip = client.post(
                    f"{base_url}{endpoint}",
                    headers=headers_with_compression,
                    json=json_data
                )

            compressed_size = len(response_with_gzip.content)
            has_compression = 'content-encoding' in response_with_gzip.headers

            # Print results
            print(f"Status Code: {response_with_gzip.status_code}")
            print(f"Uncompressed size: {format_size(uncompressed_size)} ({uncompressed_size} bytes)")
            print(f"Compressed size: {format_size(compressed_size)} ({compressed_size} bytes)")

            if has_compression:
                encoding = response_with_gzip.headers.get('content-encoding', 'none')
                print(f"Content-Encoding header: {encoding}")
            else:
                print("Content-Encoding header: NOT PRESENT")

            if uncompressed_size > 0:
                compression_ratio = (1 - compressed_size / uncompressed_size) * 100
                print(f"Compression ratio: {compression_ratio:.2f}%")
                savings = uncompressed_size - compressed_size
                print(f"Bytes saved: {format_size(savings)} ({savings} bytes)")

            # Show response preview if small enough
            if uncompressed_size < 500:
                print(f"\nResponse preview:")
                try:
                    print(json.dumps(response_with_gzip.json(), indent=2)[:500])
                except:
                    print(response_with_gzip.text[:500])

            return uncompressed_size, compressed_size, has_compression

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return 0, 0, False


def main():
    """Run compression tests on various endpoints."""
    # Configuration
    BASE_URL = "http://localhost:8000"

    # Mock authentication token (update with actual token if needed)
    AUTH_TOKEN = "test-user-id"
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }

    print("\n" + "="*80)
    print("FastAPI Response Compression Test Suite")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"GZip minimum size: 1000 bytes")
    print(f"Compression level: 6")

    # Test endpoints
    endpoints = [
        # Health check (should NOT be compressed - too small)
        ("GET", "/api/v1/health", None),

        # Root endpoint (should NOT be compressed - too small)
        ("GET", "/", None),

        # OpenAPI schema (SHOULD be compressed - large JSON)
        ("GET", "/openapi.json", None),

        # Guide generation (SHOULD be compressed - large response)
        # Note: This requires actual implementation and may fail if services aren't running
        ("POST", "/api/v1/instruction-guides/generate", {
            "instruction": "How to deploy a React app to Vercel",
            "difficulty": "beginner",
            "format_preference": "detailed"
        }),
    ]

    total_uncompressed = 0
    total_compressed = 0
    results = []

    for method, endpoint, json_data in endpoints:
        uncompressed, compressed, has_compression = test_endpoint_compression(
            BASE_URL,
            endpoint,
            method,
            headers,
            json_data
        )

        results.append({
            "endpoint": f"{method} {endpoint}",
            "uncompressed": uncompressed,
            "compressed": compressed,
            "has_compression": has_compression
        })

        total_uncompressed += uncompressed
        total_compressed += compressed

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    for result in results:
        status = "✓ COMPRESSED" if result["has_compression"] else "✗ NOT COMPRESSED"
        if result["uncompressed"] < 1000:
            status = "○ TOO SMALL (expected)"

        print(f"\n{result['endpoint']}")
        print(f"  Status: {status}")
        print(f"  Size: {format_size(result['compressed'])} / {format_size(result['uncompressed'])}")

        if result["uncompressed"] > 0:
            ratio = (1 - result["compressed"] / result["uncompressed"]) * 100
            print(f"  Ratio: {ratio:.2f}%")

    print("\n" + "="*80)
    print("OVERALL STATISTICS")
    print("="*80)
    print(f"Total uncompressed: {format_size(total_uncompressed)}")
    print(f"Total compressed: {format_size(total_compressed)}")

    if total_uncompressed > 0:
        overall_ratio = (1 - total_compressed / total_uncompressed) * 100
        overall_savings = total_uncompressed - total_compressed
        print(f"Overall compression ratio: {overall_ratio:.2f}%")
        print(f"Total bytes saved: {format_size(overall_savings)}")

    print("\n" + "="*80)
    print("COMPRESSION VERIFICATION")
    print("="*80)

    # Check if compression is working
    large_responses = [r for r in results if r["uncompressed"] >= 1000]
    if large_responses:
        compressed_count = sum(1 for r in large_responses if r["has_compression"])
        print(f"Large responses (≥1KB): {len(large_responses)}")
        print(f"Compressed responses: {compressed_count}")

        if compressed_count == len(large_responses):
            print("\n✓ SUCCESS: All large responses are being compressed!")
        elif compressed_count > 0:
            print("\n⚠ WARNING: Some large responses are not being compressed")
        else:
            print("\n✗ FAILURE: No compression detected on large responses")
            print("  Check that GZipMiddleware is properly configured")
    else:
        print("⚠ WARNING: No large responses tested (all < 1KB)")
        print("  Consider testing endpoints with larger payloads")


if __name__ == "__main__":
    main()
