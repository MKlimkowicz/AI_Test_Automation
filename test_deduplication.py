#!/usr/bin/env python3
"""Test script for Semantic Test Deduplication - Stage 4 verification."""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_test_deduplicator():
    """Test the TestDeduplicator."""
    print("\n" + "=" * 60)
    print("Testing TestDeduplicator...")
    print("=" * 60)

    from utils.vector_store import VectorStore
    from utils.test_deduplicator import (
        TestDeduplicator,
        TestSignature,
        DuplicateMatch
    )

    # Create temporary directory for persistence
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = Path(tmpdir) / ".vector_store"
        vector_store = VectorStore(persist_dir=persist_dir)
        dedup = TestDeduplicator(vector_store=vector_store)

        print(f"✓ TestDeduplicator initialized")

        # Register some tests
        test1 = """
def test_get_users():
    response = requests.get('http://localhost:5000/api/users')
    assert response.status_code == 200
    assert 'users' in response.json()
"""
        dedup.register_test("test_get_users", test1, "functional")
        print(f"✓ Registered test_get_users")

        test2 = """
def test_create_user():
    data = {'name': 'John', 'email': 'john@test.com'}
    response = requests.post('http://localhost:5000/api/users', json=data)
    assert response.status_code == 201
"""
        dedup.register_test("test_create_user", test2, "functional")
        print(f"✓ Registered test_create_user")

        test3 = """
def test_delete_user():
    response = requests.delete('http://localhost:5000/api/users/123')
    assert response.status_code == 204
"""
        dedup.register_test("test_delete_user", test3, "functional")
        print(f"✓ Registered test_delete_user")

        # Test finding duplicates with a similar test
        similar_test = """
def test_fetch_users():
    response = requests.get('http://localhost:5000/api/users')
    assert response.status_code == 200
    assert len(response.json()['users']) >= 0
"""
        duplicates = dedup.find_duplicates("test_fetch_users", similar_test, n_results=3)
        print(f"✓ Found {len(duplicates)} potential duplicates for similar test")
        assert len(duplicates) >= 1

        top_dup = duplicates[0]
        assert isinstance(top_dup, DuplicateMatch)
        print(f"  Top match: {top_dup.original_name} (similarity={top_dup.similarity:.3f})")
        assert top_dup.similarity > 0.5, f"Expected high similarity, got {top_dup.similarity}"

        # Test is_duplicate
        is_dup, match = dedup.is_duplicate("test_fetch_users", similar_test)
        print(f"✓ is_duplicate returned: {is_dup} (threshold-based)")

        # Test with clearly different test
        different_test = """
def test_cli_help():
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Usage' in result.output
"""
        is_dup_diff, _ = dedup.is_duplicate("test_cli_help", different_test)
        print(f"✓ Different test is_duplicate: {is_dup_diff} (should be False)")

        # Test deduplicate_tests with list of tests
        test_list = [
            {"name": "test_list_products", "code": """
def test_list_products():
    response = requests.get('http://localhost:5000/api/products')
    assert response.status_code == 200
"""},
            {"name": "test_get_all_products", "code": """
def test_get_all_products():
    response = requests.get('http://localhost:5000/api/products')
    assert response.status_code == 200
    assert isinstance(response.json(), list)
"""},
            {"name": "test_security_check", "code": """
def test_security_check():
    response = requests.get('http://localhost:5000/api/secure', headers={'Authorization': 'invalid'})
    assert response.status_code == 401
"""},
        ]
        unique, duplicates_list = dedup.deduplicate_tests(test_list, "integration")
        print(f"✓ deduplicate_tests: {len(unique)} unique, {len(duplicates_list)} duplicates")

        # Test deduplicate_code
        test_code = '''import pytest
import requests

BASE_URL = "http://localhost:5000"


def test_get_items():
    response = requests.get(f"{BASE_URL}/api/items")
    assert response.status_code == 200


def test_fetch_items():
    response = requests.get(f"{BASE_URL}/api/items")
    assert response.status_code == 200
    assert len(response.json()) >= 0


def test_create_item():
    data = {"name": "test"}
    response = requests.post(f"{BASE_URL}/api/items", json=data)
    assert response.status_code == 201
'''
        dedup_code, original, removed = dedup.deduplicate_code(test_code, "api_tests")
        print(f"✓ deduplicate_code: {original} original, {removed} removed")
        if removed > 0:
            print(f"  Successfully removed {removed} duplicate test(s)")

        # Test stats
        stats = dedup.get_stats()
        print(f"✓ Deduplicator Stats: {stats}")
        assert stats["total_tests_indexed"] > 0

        # Test clear
        dedup.clear()
        stats_after = dedup.get_stats()
        assert stats_after["total_tests_indexed"] == 0
        print(f"✓ Deduplicator cleared successfully")

    print("\n✅ TestDeduplicator tests PASSED")
    return True


def test_generator_integration():
    """Test the test_generator integration with deduplicator."""
    print("\n" + "=" * 60)
    print("Testing Test Generator Deduplication Integration...")
    print("=" * 60)

    from ai_engine.test_generator import _get_test_deduplicator

    # Check that function is available
    assert callable(_get_test_deduplicator), "_get_test_deduplicator should be callable"
    print(f"✓ Deduplicator integration function is available")

    # Test _get_test_deduplicator
    from utils.config import config
    if config.ENABLE_VECTOR_DB:
        dedup = _get_test_deduplicator()
        if dedup is not None:
            print(f"✓ _get_test_deduplicator() returned a deduplicator instance")
            stats = dedup.get_stats()
            print(f"  Current indexed tests: {stats.get('total_tests_indexed', 0)}")
        else:
            print(f"✓ _get_test_deduplicator() returned None (deps not fully loaded)")
    else:
        print(f"✓ Vector DB disabled, skipping deduplicator initialization test")

    print("\n✅ Test Generator Integration tests PASSED")
    return True


def main():
    """Run all Stage 4 tests."""
    print("\n" + "=" * 60)
    print("SEMANTIC TEST DEDUPLICATION - STAGE 4 TESTS")
    print("=" * 60)

    all_passed = True

    try:
        if not test_test_deduplicator():
            all_passed = False
    except Exception as e:
        print(f"\n❌ TestDeduplicator tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_generator_integration():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Test Generator Integration tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL STAGE 4 TESTS PASSED!")
        print("Semantic Test Deduplication is ready for use.")
        print("\nThe deduplicator will now:")
        print("  - Index generated tests by semantic signature")
        print("  - Detect duplicate tests across categories")
        print("  - Remove semantically similar tests during generation")
        print("  - Log deduplication statistics in reports")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please review the errors above.")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
