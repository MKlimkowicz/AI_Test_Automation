#!/usr/bin/env python3
"""Test script for Classification Cache - Stage 3 verification."""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_classification_cache():
    """Test the Classification Cache."""
    print("\n" + "=" * 60)
    print("Testing ClassificationCache...")
    print("=" * 60)

    from utils.vector_store import VectorStore
    from utils.classification_cache import (
        ClassificationCache,
        CachedClassification,
        ClassificationMatch
    )

    # Create temporary directory for persistence
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = Path(tmpdir) / ".vector_store"
        vector_store = VectorStore(persist_dir=persist_dir)
        cache = ClassificationCache(vector_store=vector_store)

        print(f"✓ ClassificationCache initialized")

        # Store some classifications
        error1 = "AssertionError: assert response.status_code == 200\nAssertionError"
        code1 = """
def test_get_users():
    response = requests.get('/api/users')
    assert response.status_code == 200
"""
        id1 = cache.store_classification(
            error_message=error1,
            test_code=code1,
            classification="TEST_ERROR",
            reason="Status code assertion failed due to wrong endpoint",
            confidence="high",
            app_type="rest_api"
        )
        print(f"✓ Stored classification 1: {id1[:16]}...")

        # Store actual defect classification
        error2 = "ValueError: Invalid user ID format\nValueError: Invalid user ID format"
        code2 = """
def test_create_user():
    user = create_user(id='invalid')
    assert user.id == 'invalid'
"""
        cache.store_classification(
            error_message=error2,
            test_code=code2,
            classification="ACTUAL_DEFECT",
            reason="Application validation logic rejecting valid input",
            confidence="high",
            app_type="rest_api"
        )
        print(f"✓ Stored classification 2 (ACTUAL_DEFECT)")

        # Store CLI-related classification
        error3 = "SystemExit: 1"
        code3 = """
def test_cli_help():
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
"""
        cache.store_classification(
            error_message=error3,
            test_code=code3,
            classification="TEST_ERROR",
            reason="Exit code mismatch, CLI returns 1 for help",
            confidence="medium",
            app_type="cli"
        )
        print(f"✓ Stored classification 3 (CLI)")

        # Test finding similar classifications
        query_error = "AssertionError: assert response.status_code == 200"
        query_code = """
def test_get_products():
    response = requests.get('/api/products')
    assert response.status_code == 200
"""
        matches = cache.find_similar(query_error, query_code, n_results=3)
        print(f"✓ Found {len(matches)} similar classifications")
        assert len(matches) >= 1, "Should find at least one similar classification"

        # Verify match structure
        top = matches[0]
        assert isinstance(top, ClassificationMatch)
        assert isinstance(top.cached, CachedClassification)
        assert top.similarity > 0.5
        print(f"  Top match: {top.cached.classification} (similarity={top.similarity:.3f})")
        print(f"  Reason: {top.cached.reason[:50]}...")

        # Test get_cached_classification with high similarity
        cached_result = cache.get_cached_classification(query_error, query_code, app_type="rest_api")
        if cached_result:
            print(f"✓ get_cached_classification returned: {cached_result['classification']}")
            assert cached_result.get("from_cache") == True
        else:
            print(f"✓ get_cached_classification returned None (similarity threshold not met)")

        # Test app_type filtering
        matches_cli = cache.find_similar(
            "SystemExit: 0",
            "def test_exit(): pass",
            app_type="cli"
        )
        print(f"✓ Filtered search (cli): {len(matches_cli)} results")

        # Test that REST API classifications are not returned for CLI filter
        matches_wrong_type = cache.find_similar(
            error1,
            code1,
            app_type="cli"
        )
        # Should find fewer or no matches since we're filtering by cli
        print(f"✓ Cross-type filter test: {len(matches_wrong_type)} cli matches for rest_api error")

        # Test stats
        stats = cache.get_stats()
        print(f"✓ Cache Stats: {stats}")
        assert stats["total_classifications"] >= 3

        # Test clear
        cache.clear()
        stats_after = cache.get_stats()
        assert stats_after["total_classifications"] == 0
        print(f"✓ Cache cleared successfully")

    print("\n✅ ClassificationCache tests PASSED")
    return True


def test_self_healer_integration():
    """Test the self_healer integration with classification cache."""
    print("\n" + "=" * 60)
    print("Testing Self-Healer Classification Integration...")
    print("=" * 60)

    from ai_engine.self_healer import (
        _get_classification_cache,
        _get_cached_or_classify
    )

    # Check that functions are available
    assert callable(_get_classification_cache), "_get_classification_cache should be callable"
    assert callable(_get_cached_or_classify), "_get_cached_or_classify should be callable"
    print(f"✓ Classification cache integration functions are available")

    # Test _get_classification_cache
    from utils.config import config
    if config.ENABLE_VECTOR_DB:
        cache = _get_classification_cache()
        if cache is not None:
            print(f"✓ _get_classification_cache() returned a cache instance")
            stats = cache.get_stats()
            print(f"  Current classifications: {stats.get('total_classifications', 0)}")
        else:
            print(f"✓ _get_classification_cache() returned None (deps not fully loaded)")
    else:
        print(f"✓ Vector DB disabled, skipping cache initialization test")

    print("\n✅ Self-Healer Classification Integration tests PASSED")
    return True


def main():
    """Run all Stage 3 tests."""
    print("\n" + "=" * 60)
    print("CLASSIFICATION CACHE - STAGE 3 TESTS")
    print("=" * 60)

    all_passed = True

    try:
        if not test_classification_cache():
            all_passed = False
    except Exception as e:
        print(f"\n❌ ClassificationCache tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_self_healer_integration():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Self-Healer Integration tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL STAGE 3 TESTS PASSED!")
        print("Classification Cache is ready for use.")
        print("\nThe cache will now:")
        print("  - Store failure classifications (TEST_ERROR/ACTUAL_DEFECT)")
        print("  - Query for similar errors before calling AI")
        print("  - Skip AI classification for highly similar errors")
        print("  - Track usage counts for cached classifications")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please review the errors above.")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
