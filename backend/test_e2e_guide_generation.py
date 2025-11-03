#!/usr/bin/env python3
"""
End-to-End Test Suite for Guide Generation Workflow
Tests Task 2.2: End-to-End Testing - Guide Generation

Test Categories:
1. API Health Check
2. Guide Generation - Valid Scenarios
3. Guide Generation - Error Handling
4. Database Verification
5. Response Structure Validation
6. Progressive Disclosure Verification
"""

import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

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


class TestResult:
    """Container for test results"""
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error = None
        self.duration = 0.0
        self.details = {}

    def mark_passed(self, details: dict = None):
        self.passed = True
        if details:
            self.details = details

    def mark_failed(self, error: str, details: dict = None):
        self.passed = False
        self.error = error
        if details:
            self.details = details


class E2ETestSuite:
    """End-to-end test suite for guide generation"""

    def __init__(self):
        self.client = httpx.Client(timeout=120.0)  # Increased timeout for LLM calls
        self.results: List[TestResult] = []
        self.test_session_id: Optional[str] = None
        self.test_guide_id: Optional[str] = None

    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

    def run_all_tests(self):
        """Execute all test scenarios"""
        print("=" * 80)
        print("END-TO-END TEST SUITE: GUIDE GENERATION WORKFLOW")
        print("=" * 80)
        print()

        # Test Category 1: Health Check
        print("1. API Health Check")
        print("-" * 80)
        self.test_health_check()
        self.print_results()

        # Test Category 2: Valid Guide Generation
        print("\n2. Guide Generation - Valid Scenarios")
        print("-" * 80)
        self.test_generate_guide_beginner()
        self.test_generate_guide_intermediate()
        self.test_generate_guide_detailed_format()
        self.print_results()

        # Test Category 3: Error Handling
        print("\n3. Guide Generation - Error Handling")
        print("-" * 80)
        self.test_invalid_difficulty()
        self.test_empty_instruction()
        self.test_very_long_instruction()
        self.print_results()

        # Test Category 4: Database Verification
        if self.test_session_id and self.test_guide_id:
            print("\n4. Database Verification")
            print("-" * 80)
            self.test_database_guide_record()
            self.test_database_section_records()
            self.test_database_step_records()
            self.test_database_session_record()
            self.test_database_json_structure()
            self.print_results()

        # Test Category 5: Response Structure Validation
        if self.test_session_id:
            print("\n5. Response Structure Validation")
            print("-" * 80)
            self.test_response_structure()
            self.test_first_step_fields()
            self.test_metadata_fields()
            self.print_results()

        # Test Category 6: Progressive Disclosure
        if self.test_session_id:
            print("\n6. Progressive Disclosure Verification")
            print("-" * 80)
            self.test_only_current_step_returned()
            self.test_no_future_steps_revealed()
            self.test_guide_structure_present()
            self.print_results()

        # Final Summary
        self.print_final_summary()

    def test_health_check(self):
        """Test 1.1: Health check endpoint"""
        result = TestResult("Health Check")
        start = time.time()

        try:
            response = self.client.get(f"{BASE_URL}{API_PREFIX}/health")
            result.duration = time.time() - start

            if response.status_code != 200:
                result.mark_failed(f"Expected 200, got {response.status_code}")
            else:
                data = response.json()
                if data.get("status") == "healthy":
                    result.mark_passed({
                        "database": data.get("services", {}).get("database"),
                        "redis": data.get("services", {}).get("redis")
                    })
                else:
                    result.mark_failed(f"Status not healthy: {data.get('status')}")

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_generate_guide_beginner(self):
        """Test 2.1: Generate beginner guide"""
        result = TestResult("Generate Guide (Beginner)")
        start = time.time()

        try:
            payload = {
                "instruction": "How to set up a Python development environment",
                "difficulty": "beginner",
                "format_preference": "detailed"
            }

            response = self.client.post(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/generate",
                json=payload,
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            if response.status_code != 200:
                result.mark_failed(
                    f"Expected 200, got {response.status_code}",
                    {"response": response.text[:500]}
                )
            else:
                data = response.json()

                # Save for subsequent tests
                self.test_session_id = data.get("session_id")
                self.test_guide_id = data.get("guide_id")

                # Validate response
                errors = []
                if not data.get("session_id"):
                    errors.append("Missing session_id")
                if not data.get("guide_id"):
                    errors.append("Missing guide_id")
                if not data.get("first_step"):
                    errors.append("Missing first_step")
                if not data.get("guide_title"):
                    errors.append("Missing guide_title")

                if errors:
                    result.mark_failed(", ".join(errors))
                else:
                    result.mark_passed({
                        "session_id": self.test_session_id,
                        "guide_id": self.test_guide_id,
                        "guide_title": data.get("guide_title"),
                        "has_first_step": bool(data.get("first_step"))
                    })

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_generate_guide_intermediate(self):
        """Test 2.2: Generate intermediate guide"""
        result = TestResult("Generate Guide (Intermediate)")
        start = time.time()

        try:
            payload = {
                "instruction": "Configure Docker for microservices deployment",
                "difficulty": "intermediate",
                "format_preference": "detailed"
            }

            response = self.client.post(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/generate",
                json=payload,
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            if response.status_code == 200:
                data = response.json()
                result.mark_passed({
                    "guide_title": data.get("guide_title"),
                    "session_id": data.get("session_id")
                })
            else:
                result.mark_failed(f"Expected 200, got {response.status_code}")

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_generate_guide_detailed_format(self):
        """Test 2.3: Generate guide with detailed format"""
        result = TestResult("Generate Guide (Detailed Format)")
        start = time.time()

        try:
            payload = {
                "instruction": "Set up automated testing pipeline",
                "difficulty": "beginner",
                "format_preference": "detailed"
            }

            response = self.client.post(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/generate",
                json=payload,
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            if response.status_code == 200:
                result.mark_passed()
            else:
                result.mark_failed(f"Expected 200, got {response.status_code}")

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_invalid_difficulty(self):
        """Test 3.1: Invalid difficulty level"""
        result = TestResult("Error Handling: Invalid Difficulty")
        start = time.time()

        try:
            payload = {
                "instruction": "Test instruction",
                "difficulty": "super_expert",  # Invalid
                "format_preference": "detailed"
            }

            response = self.client.post(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/generate",
                json=payload,
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            # Should get validation error (422)
            if response.status_code == 422:
                result.mark_passed({"error_type": "validation_error"})
            elif response.status_code == 400:
                result.mark_passed({"error_type": "bad_request"})
            else:
                result.mark_failed(
                    f"Expected 422 or 400, got {response.status_code}"
                )

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_empty_instruction(self):
        """Test 3.2: Empty instruction"""
        result = TestResult("Error Handling: Empty Instruction")
        start = time.time()

        try:
            payload = {
                "instruction": "",
                "difficulty": "beginner",
                "format_preference": "detailed"
            }

            response = self.client.post(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/generate",
                json=payload,
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            # Should get validation error or 500
            if response.status_code in [422, 400, 500]:
                result.mark_passed({"status_code": response.status_code})
            else:
                result.mark_failed(
                    f"Expected error status, got {response.status_code}"
                )

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_very_long_instruction(self):
        """Test 3.3: Very long instruction (>1000 chars)"""
        result = TestResult("Error Handling: Very Long Instruction")
        start = time.time()

        try:
            payload = {
                "instruction": "A" * 1500,  # 1500 characters
                "difficulty": "beginner",
                "format_preference": "detailed"
            }

            response = self.client.post(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/generate",
                json=payload,
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            # Should either accept or reject with validation error
            if response.status_code in [200, 422, 400]:
                result.mark_passed({"status_code": response.status_code})
            else:
                result.mark_failed(f"Unexpected status: {response.status_code}")

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_database_guide_record(self):
        """Test 4.1: Verify guide record in database"""
        result = TestResult("Database: Guide Record")
        start = time.time()

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT guide_id, title, total_sections, total_steps, difficulty_level, category "
                "FROM step_guides WHERE guide_id = %s",
                (self.test_guide_id,)
            )

            row = cursor.fetchone()
            result.duration = time.time() - start

            if row:
                result.mark_passed({
                    "title": row["title"],
                    "total_sections": row["total_sections"],
                    "total_steps": row["total_steps"],
                    "difficulty": row["difficulty"],
                    "category": row["category"]
                })
            else:
                result.mark_failed("Guide record not found in database")

            cursor.close()
            conn.close()

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_database_section_records(self):
        """Test 4.2: Verify section records in database"""
        result = TestResult("Database: Section Records")
        start = time.time()

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT section_id, section_title, section_order "
                "FROM sections WHERE guide_id = %s ORDER BY section_order",
                (self.test_guide_id,)
            )

            rows = cursor.fetchall()
            result.duration = time.time() - start

            if rows:
                result.mark_passed({
                    "section_count": len(rows),
                    "sections": [
                        {
                            "title": r["section_title"],
                            "order": r["section_order"]
                        }
                        for r in rows
                    ]
                })
            else:
                result.mark_failed("No section records found")

            cursor.close()
            conn.close()

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_database_step_records(self):
        """Test 4.3: Verify step records in database"""
        result = TestResult("Database: Step Records")
        start = time.time()

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT step_id, step_identifier, step_index, title, step_status "
                "FROM steps WHERE guide_id = %s ORDER BY step_index",
                (self.test_guide_id,)
            )

            rows = cursor.fetchall()
            result.duration = time.time() - start

            if rows:
                # Verify globally unique step_index
                step_indices = [r["step_index"] for r in rows]
                unique_indices = set(step_indices)

                if len(step_indices) != len(unique_indices):
                    result.mark_failed("Duplicate step_index values found")
                else:
                    result.mark_passed({
                        "step_count": len(rows),
                        "first_step": rows[0]["step_identifier"] if rows else None,
                        "all_step_indices": step_indices
                    })
            else:
                result.mark_failed("No step records found")

            cursor.close()
            conn.close()

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_database_session_record(self):
        """Test 4.4: Verify session record in database"""
        result = TestResult("Database: Session Record")
        start = time.time()

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT session_id, guide_id, user_id, status, current_step_identifier "
                "FROM guide_sessions WHERE session_id = %s",
                (self.test_session_id,)
            )

            row = cursor.fetchone()
            result.duration = time.time() - start

            if row:
                result.mark_passed({
                    "guide_id": str(row["guide_id"]),
                    "user_id": row["user_id"],
                    "status": row["status"],
                    "current_step": row["current_step_identifier"]
                })
            else:
                result.mark_failed("Session record not found")

            cursor.close()
            conn.close()

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_database_json_structure(self):
        """Test 4.5: Verify guide_data JSON structure"""
        result = TestResult("Database: JSON Structure")
        start = time.time()

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT guide_data FROM step_guides WHERE guide_id = %s",
                (self.test_guide_id,)
            )

            row = cursor.fetchone()
            result.duration = time.time() - start

            if row and row["guide_data"]:
                guide_data = row["guide_data"]

                # Verify structure
                errors = []
                if "sections" not in guide_data:
                    errors.append("Missing 'sections'")
                if "metadata" not in guide_data:
                    errors.append("Missing 'metadata'")

                if errors:
                    result.mark_failed(", ".join(errors))
                else:
                    result.mark_passed({
                        "has_sections": "sections" in guide_data,
                        "has_metadata": "metadata" in guide_data,
                        "section_count": len(guide_data.get("sections", []))
                    })
            else:
                result.mark_failed("guide_data JSON not found")

            cursor.close()
            conn.close()

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_response_structure(self):
        """Test 5.1: Validate response structure"""
        result = TestResult("Response: Structure")
        start = time.time()

        try:
            response = self.client.get(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/{self.test_session_id}/current-step",
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            if response.status_code != 200:
                result.mark_failed(f"Expected 200, got {response.status_code}")
            else:
                data = response.json()

                required_fields = [
                    "session_id", "status", "guide_title", "guide_description",
                    "current_section", "current_step", "progress", "navigation"
                ]

                missing = [f for f in required_fields if f not in data]

                if missing:
                    result.mark_failed(f"Missing fields: {', '.join(missing)}")
                else:
                    result.mark_passed({"all_fields_present": True})

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_first_step_fields(self):
        """Test 5.2: Validate first step fields"""
        result = TestResult("Response: First Step Fields")
        start = time.time()

        try:
            response = self.client.get(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/{self.test_session_id}/current-step",
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            if response.status_code != 200:
                result.mark_failed(f"Expected 200, got {response.status_code}")
            else:
                data = response.json()
                current_step = data.get("current_step", {})

                required_fields = [
                    "step_identifier", "title", "description",
                    "completion_criteria", "assistance_hints",
                    "estimated_duration_minutes"
                ]

                missing = [f for f in required_fields if f not in current_step]

                if missing:
                    result.mark_failed(f"Missing fields: {', '.join(missing)}")
                else:
                    result.mark_passed({
                        "step_identifier": current_step.get("step_identifier"),
                        "title": current_step.get("title")
                    })

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_metadata_fields(self):
        """Test 5.3: Validate metadata fields"""
        result = TestResult("Response: Metadata Fields")
        start = time.time()

        try:
            response = self.client.get(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/{self.test_session_id}/current-step",
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            if response.status_code != 200:
                result.mark_failed(f"Expected 200, got {response.status_code}")
            else:
                data = response.json()

                # Check metadata
                if data.get("guide_title") and data.get("guide_description"):
                    result.mark_passed({
                        "guide_title": data.get("guide_title"),
                        "guide_description": data.get("guide_description")[:100]
                    })
                else:
                    result.mark_failed("Missing guide metadata")

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_only_current_step_returned(self):
        """Test 6.1: Only current step returned"""
        result = TestResult("Progressive Disclosure: Only Current Step")
        start = time.time()

        try:
            response = self.client.get(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/{self.test_session_id}/current-step",
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            if response.status_code != 200:
                result.mark_failed(f"Expected 200, got {response.status_code}")
            else:
                data = response.json()

                # Should have current_step but NOT steps array
                if "current_step" in data and "steps" not in data:
                    result.mark_passed({"only_current_step": True})
                else:
                    result.mark_failed("Full steps array exposed")

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_no_future_steps_revealed(self):
        """Test 6.2: No future steps revealed"""
        result = TestResult("Progressive Disclosure: No Future Steps")
        start = time.time()

        try:
            response = self.client.get(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/{self.test_session_id}/current-step",
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            if response.status_code != 200:
                result.mark_failed(f"Expected 200, got {response.status_code}")
            else:
                data = response.json()
                response_str = json.dumps(data)

                # Check for future step indicators
                future_indicators = ["step_2", "step 2", "next_steps", "upcoming"]
                found_futures = [ind for ind in future_indicators if ind in response_str.lower()]

                if not found_futures:
                    result.mark_passed({"no_future_steps_found": True})
                else:
                    result.mark_failed(f"Future step indicators found: {found_futures}")

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def test_guide_structure_present(self):
        """Test 6.3: Guide structure present"""
        result = TestResult("Progressive Disclosure: Guide Structure")
        start = time.time()

        try:
            response = self.client.get(
                f"{BASE_URL}{API_PREFIX}/instruction-guides/{self.test_session_id}/current-step",
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
            )
            result.duration = time.time() - start

            if response.status_code != 200:
                result.mark_failed(f"Expected 200, got {response.status_code}")
            else:
                data = response.json()

                # Should have section info and progress
                has_section = "current_section" in data
                has_progress = "progress" in data

                if has_section and has_progress:
                    result.mark_passed({
                        "section_title": data.get("current_section", {}).get("section_title"),
                        "progress": data.get("progress")
                    })
                else:
                    result.mark_failed("Missing structure information")

        except Exception as e:
            result.duration = time.time() - start
            result.mark_failed(str(e))

        self.results.append(result)

    def print_results(self):
        """Print results for current test category"""
        if not self.results:
            return

        # Print only new results since last call
        start_idx = len(self.results) - sum(1 for _ in self.results if hasattr(self, '_printed_count'))
        if not hasattr(self, '_printed_count'):
            self._printed_count = 0

        for i in range(self._printed_count, len(self.results)):
            result = self.results[i]
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"  {status} | {result.name} ({result.duration:.2f}s)")

            if result.error:
                print(f"         Error: {result.error}")

            if result.details:
                for key, value in result.details.items():
                    print(f"         {key}: {value}")

        self._printed_count = len(self.results)
        print()

    def print_final_summary(self):
        """Print final test summary"""
        print("\n" + "=" * 80)
        print("FINAL TEST SUMMARY")
        print("=" * 80)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed

        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ({100 * passed / total:.1f}%)")
        print(f"Failed: {failed} ({100 * failed / total:.1f}%)")

        if failed > 0:
            print("\nFailed Tests:")
            for result in self.results:
                if not result.passed:
                    print(f"  - {result.name}: {result.error}")

        print("\nTest Environment:")
        print(f"  Backend URL: {BASE_URL}")
        print(f"  Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

        if self.test_session_id:
            print(f"\nTest Session: {self.test_session_id}")
            print(f"Test Guide: {self.test_guide_id}")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    suite = E2ETestSuite()
    suite.run_all_tests()
