#!/usr/bin/env python3
"""Test script for Healing Knowledge Base - Stage 2 verification."""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_healing_kb():
    """Test the Healing Knowledge Base."""
    print("\n" + "=" * 60)
    print("Testing HealingKnowledgeBase...")
    print("=" * 60)

    from utils.vector_store import VectorStore
    from utils.healing_kb import HealingKnowledgeBase, HealingPattern, HealingSuggestion

    # Create temporary directory for persistence
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = Path(tmpdir) / ".vector_store"
        vector_store = VectorStore(persist_dir=persist_dir)
        kb = HealingKnowledgeBase(vector_store=vector_store)

        print(f"✓ HealingKnowledgeBase initialized")

        # Test storing patterns
        error1 = "AssertionError: assert response.status_code == 200"
        code1 = """
def test_api_endpoint():
    response = requests.get('http://localhost:5000/api/users')
    assert response.status_code == 200
"""
        healed1 = """
def test_api_endpoint():
    response = requests.get('http://localhost:5000/api/users')
    assert response.status_code in [200, 201]
"""
        pattern_id = kb.store_pattern(
            error_message=error1,
            original_code=code1,
            healed_code=healed1,
            error_type="TEST_ERROR",
            app_type="rest_api",
            success=True
        )
        print(f"✓ Stored first pattern: {pattern_id[:16]}...")

        # Store another similar pattern
        error2 = "AssertionError: assert response.status_code == 201"
        code2 = """
def test_create_user():
    response = requests.post('http://localhost:5000/api/users', json={'name': 'test'})
    assert response.status_code == 201
"""
        healed2 = """
def test_create_user():
    response = requests.post('http://localhost:5000/api/users', json={'name': 'test'})
    assert response.status_code in [200, 201]
"""
        kb.store_pattern(
            error_message=error2,
            original_code=code2,
            healed_code=healed2,
            error_type="TEST_ERROR",
            app_type="rest_api",
            success=True
        )
        print(f"✓ Stored second pattern")

        # Store a different type of error
        error3 = "ModuleNotFoundError: No module named 'flask'"
        code3 = """
def test_import():
    import flask
    assert flask is not None
"""
        healed3 = """
import pytest
pytest.importorskip('flask')

def test_import():
    import flask
    assert flask is not None
"""
        kb.store_pattern(
            error_message=error3,
            original_code=code3,
            healed_code=healed3,
            error_type="TEST_ERROR",
            app_type="rest_api",
            success=True
        )
        print(f"✓ Stored third pattern (different error type)")

        # Test finding similar patterns
        query_error = "AssertionError: assert response.status_code == 200"
        query_code = """
def test_get_products():
    response = requests.get('http://localhost:5000/api/products')
    assert response.status_code == 200
"""
        suggestions = kb.find_similar_patterns(query_error, query_code, n_results=3)
        print(f"✓ Found {len(suggestions)} similar patterns")
        assert len(suggestions) >= 1, "Should find at least one similar pattern"

        # Verify suggestion structure
        top = suggestions[0]
        assert isinstance(top, HealingSuggestion)
        assert isinstance(top.pattern, HealingPattern)
        assert top.similarity > 0.5, f"Expected high similarity, got {top.similarity}"
        print(f"  Top match: similarity={top.similarity:.3f}, confidence={top.confidence:.3f}")
        print(f"  Error type: {top.pattern.error_type}, App type: {top.pattern.app_type}")

        # Test get_best_fix
        best = kb.get_best_fix(query_error, query_code, app_type="rest_api")
        if best:
            print(f"✓ get_best_fix returned a suggestion (should_apply={best.should_apply})")
        else:
            print(f"✓ get_best_fix returned None (threshold not met - expected for new KB)")

        # Test updating pattern stats
        kb.record_outcome(query_error, query_code, success=True)
        print(f"✓ Recorded successful outcome")

        kb.record_outcome(query_error, query_code, success=False)
        print(f"✓ Recorded failed outcome")

        # Test stats
        stats = kb.get_stats()
        print(f"✓ KB Stats: {stats}")
        assert stats["total_patterns"] >= 3, f"Expected at least 3 patterns, got {stats['total_patterns']}"

        # Test app_type filtering
        suggestions_filtered = kb.find_similar_patterns(
            "ConnectionError: Failed to connect",
            "def test_conn(): pass",
            app_type="cli"  # No CLI patterns stored
        )
        print(f"✓ Filtered search (cli): {len(suggestions_filtered)} results")

        # Test clear
        kb.clear()
        stats_after_clear = kb.get_stats()
        assert stats_after_clear["total_patterns"] == 0, "Should be empty after clear"
        print(f"✓ KB cleared successfully")

    print("\n✅ HealingKnowledgeBase tests PASSED")
    return True


def test_self_healer_integration():
    """Test the self_healer integration with KB."""
    print("\n" + "=" * 60)
    print("Testing Self-Healer Integration...")
    print("=" * 60)

    # Import the helper functions from self_healer
    from ai_engine.self_healer import _try_kb_healing, _store_healing_result, _get_healing_kb

    # Check that KB functions are available
    assert callable(_try_kb_healing), "_try_kb_healing should be callable"
    assert callable(_store_healing_result), "_store_healing_result should be callable"
    assert callable(_get_healing_kb), "_get_healing_kb should be callable"
    print(f"✓ KB integration functions are available")

    # Test _get_healing_kb (will initialize if ENABLE_VECTOR_DB is True)
    from utils.config import config
    if config.ENABLE_VECTOR_DB:
        kb = _get_healing_kb()
        if kb is not None:
            print(f"✓ _get_healing_kb() returned a KB instance")
            stats = kb.get_stats()
            print(f"  Current patterns: {stats.get('total_patterns', 0)}")
        else:
            print(f"✓ _get_healing_kb() returned None (expected if deps not fully loaded)")
    else:
        print(f"✓ Vector DB disabled in config, skipping KB initialization test")

    print("\n✅ Self-Healer Integration tests PASSED")
    return True


def main():
    """Run all Stage 2 tests."""
    print("\n" + "=" * 60)
    print("HEALING KNOWLEDGE BASE - STAGE 2 TESTS")
    print("=" * 60)

    all_passed = True

    try:
        if not test_healing_kb():
            all_passed = False
    except Exception as e:
        print(f"\n❌ HealingKnowledgeBase tests FAILED: {e}")
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
        print("✅ ALL STAGE 2 TESTS PASSED!")
        print("Healing Knowledge Base is ready for use.")
        print("\nThe KB will now:")
        print("  - Store successful healing patterns automatically")
        print("  - Query for similar errors before calling AI")
        print("  - Track success/failure rates for pattern quality")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please review the errors above.")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
