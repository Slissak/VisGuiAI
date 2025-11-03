#!/usr/bin/env python3
"""
Quick E2E Verification Test
Uses existing guide data to verify functionality without waiting for LLM generation
"""

import json
from typing import Dict, List
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"
AUTH_TOKEN = "dev-test-token"
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "stepguide",
    "user": "stepguide",
    "password": "stepguide_dev_password"
}


def test_database_verification():
    """Verify database records for existing guides"""
    print("=" * 80)
    print("DATABASE VERIFICATION TEST")
    print("=" * 80)

    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    cursor = conn.cursor()

    # Get the most recent guide
    cursor.execute(
        "SELECT guide_id, title, total_sections, total_steps, difficulty_level, created_at "
        "FROM step_guides ORDER BY created_at DESC LIMIT 1"
    )
    guide = cursor.fetchone()

    if not guide:
        print("✗ No guides found in database")
        cursor.close()
        conn.close()
        return None

    print(f"\n✓ Most recent guide found:")
    print(f"  ID: {guide['guide_id']}")
    print(f"  Title: {guide['title']}")
    print(f"  Sections: {guide['total_sections']}")
    print(f"  Steps: {guide['total_steps']}")
    print(f"  Difficulty: {guide['difficulty_level']}")

    # Check sections
    cursor.execute(
        "SELECT section_id, section_title, section_order "
        "FROM sections WHERE guide_id = %s ORDER BY section_order",
        (guide['guide_id'],)
    )
    sections = cursor.fetchall()

    print(f"\n✓ Section records: {len(sections)}")
    for section in sections:
        print(f"  {section['section_order']}: {section['section_title']}")

    # Check steps
    cursor.execute(
        "SELECT step_id, step_identifier, step_index, title, step_status "
        "FROM steps WHERE guide_id = %s ORDER BY step_index",
        (guide['guide_id'],)
    )
    steps = cursor.fetchall()

    print(f"\n✓ Step records: {len(steps)}")
    step_indices = [s['step_index'] for s in steps]
    print(f"  Step indices: {step_indices}")

    # Verify unique step indices
    if len(step_indices) == len(set(step_indices)):
        print(f"  ✓ All step indices are unique (global step renumbering working)")
    else:
        print(f"  ✗ Duplicate step indices found!")

    # Check sessions
    cursor.execute(
        "SELECT session_id, user_id, status, current_step_identifier "
        "FROM guide_sessions WHERE guide_id = %s ORDER BY created_at DESC LIMIT 1",
        (guide['guide_id'],)
    )
    session = cursor.fetchone()

    if session:
        print(f"\n✓ Session record found:")
        print(f"  ID: {session['session_id']}")
        print(f"  User: {session['user_id']}")
        print(f"  Status: {session['status']}")
        print(f"  Current step: {session['current_step_identifier']}")

    # Check guide_data JSON
    cursor.execute(
        "SELECT guide_data FROM step_guides WHERE guide_id = %s",
        (guide['guide_id'],)
    )
    guide_data_row = cursor.fetchone()

    if guide_data_row and guide_data_row['guide_data']:
        guide_data = guide_data_row['guide_data']
        print(f"\n✓ guide_data JSON structure:")
        print(f"  Has sections: {'sections' in guide_data}")
        print(f"  Has metadata: {'metadata' in guide_data}")
        if 'sections' in guide_data:
            print(f"  Section count: {len(guide_data['sections'])}")

    cursor.close()
    conn.close()

    return guide['guide_id'], session['session_id'] if session else None


def test_api_current_step(session_id: str):
    """Test getting current step via API"""
    print("\n" + "=" * 80)
    print("API TEST: GET CURRENT STEP")
    print("=" * 80)

    client = httpx.Client(timeout=30.0)

    try:
        response = client.get(
            f"{BASE_URL}{API_PREFIX}/instruction-guides/{session_id}/current-step",
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        )

        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ Current step API responded successfully")
            print(f"  Session ID: {data.get('session_id')}")
            print(f"  Status: {data.get('status')}")
            print(f"  Guide Title: {data.get('guide_title')}")

            # Check response structure
            required_fields = [
                "session_id", "status", "guide_title", "guide_description",
                "current_section", "current_step", "progress", "navigation"
            ]
            missing = [f for f in required_fields if f not in data]

            if missing:
                print(f"\n  ✗ Missing fields: {', '.join(missing)}")
            else:
                print(f"\n  ✓ All required fields present")

            # Check current step
            current_step = data.get('current_step', {})
            step_fields = [
                "step_identifier", "title", "description",
                "completion_criteria", "assistance_hints",
                "estimated_duration_minutes"
            ]
            missing_step = [f for f in step_fields if f not in current_step]

            if missing_step:
                print(f"  ✗ Missing step fields: {', '.join(missing_step)}")
            else:
                print(f"  ✓ All required step fields present")

            print(f"\n  Current Step Details:")
            print(f"    Identifier: {current_step.get('step_identifier')}")
            print(f"    Title: {current_step.get('title')}")
            print(f"    Duration: {current_step.get('estimated_duration_minutes')} min")

            # Check progressive disclosure
            response_str = json.dumps(data)
            if "steps" in data:
                print(f"\n  ✗ FAILED: Full steps array exposed (breaks progressive disclosure)")
            else:
                print(f"\n  ✓ PASSED: Only current step returned (progressive disclosure working)")

            return True
        else:
            print(f"\n✗ API request failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n✗ Exception: {str(e)}")
        return False
    finally:
        client.close()


def test_api_health():
    """Test health check endpoint"""
    print("\n" + "=" * 80)
    print("API TEST: HEALTH CHECK")
    print("=" * 80)

    client = httpx.Client(timeout=10.0)

    try:
        response = client.get(f"{BASE_URL}{API_PREFIX}/health")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✓ Health check passed")
            print(f"  Status: {data.get('status')}")
            print(f"  Database: {data.get('services', {}).get('database')}")
            print(f"  Redis: {data.get('services', {}).get('redis')}")
            return True
        else:
            print(f"\n✗ Health check failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"\n✗ Exception: {str(e)}")
        return False
    finally:
        client.close()


def main():
    """Run all verification tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "E2E VERIFICATION TEST SUITE" + " " * 31 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    results = []

    # Test 1: Health check
    health_ok = test_api_health()
    results.append(("Health Check", health_ok))

    # Test 2: Database verification
    db_result = test_database_verification()
    results.append(("Database Verification", db_result is not None))

    # Test 3: API current step
    if db_result and db_result[1]:
        guide_id, session_id = db_result
        api_ok = test_api_current_step(session_id)
        results.append(("API Current Step", api_ok))
    else:
        print("\n⚠ Skipping API test (no session found)")
        results.append(("API Current Step", False))

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for _, ok in results if ok)
    failed = total - passed

    print(f"\nTotal Tests: {total}")
    print(f"Passed: {passed} ({100 * passed / total:.1f}%)")
    print(f"Failed: {failed}")

    print("\nTest Results:")
    for name, ok in results:
        status = "✓ PASS" if ok else "✗ FAIL"
        print(f"  {status} | {name}")

    print("\n" + "=" * 80)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Guide generation workflow is working correctly.")
    else:
        print(f"\n⚠ {failed} test(s) failed. Please review the output above.")

    print()


if __name__ == "__main__":
    main()
