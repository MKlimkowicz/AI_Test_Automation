#!/usr/bin/env python3
"""Test script for Change Detection - Stage 6 verification."""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_change_detector():
    """Test the ChangeDetector."""
    print("\n" + "=" * 60)
    print("Testing ChangeDetector...")
    print("=" * 60)

    from utils.vector_store import VectorStore
    from utils.change_detector import (
        ChangeDetector,
        FileSnapshot,
        ChangeReport
    )

    # Create temporary directories
    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = Path(tmpdir) / ".vector_store"
        snapshot_dir = Path(tmpdir) / ".snapshots"
        vector_store = VectorStore(persist_dir=persist_dir)
        detector = ChangeDetector(vector_store=vector_store, snapshot_dir=snapshot_dir)

        print(f"✓ ChangeDetector initialized")

        # Initial set of files
        files_v1 = {
            "app/main.py": "def main():\n    print('Hello')\n",
            "app/utils.py": "def helper():\n    return 42\n",
            "app/config.py": "DEBUG = True\n",
        }

        # Create initial snapshot
        snapshots = detector.create_snapshot(files_v1, "run_1")
        print(f"✓ Created initial snapshot with {len(snapshots)} files")
        assert len(snapshots) == 3

        # Verify snapshot structure
        for path, snapshot in snapshots.items():
            assert isinstance(snapshot, FileSnapshot)
            assert snapshot.file_path == path
            assert len(snapshot.content_hash) == 64  # SHA256 hex

        # Save as latest
        detector.save_run_snapshot(files_v1)
        print(f"✓ Saved snapshot as 'latest'")

        # Test detecting no changes
        report = detector.detect_changes(files_v1)
        print(f"✓ No changes detected: {report.total_changes} changes")
        assert report.total_changes == 0
        assert not report.has_changes
        assert len(report.unchanged_files) == 3

        # Modify a file
        files_v2 = {
            "app/main.py": "def main():\n    print('Hello World')\n",  # Modified
            "app/utils.py": "def helper():\n    return 42\n",  # Unchanged
            "app/config.py": "DEBUG = False\n",  # Modified
        }

        report = detector.detect_changes(files_v2)
        print(f"✓ Changes detected: {report.total_changes} changes")
        assert report.total_changes == 2
        assert report.has_changes
        assert len(report.modified_files) == 2
        assert "app/main.py" in report.modified_files
        assert "app/config.py" in report.modified_files

        # Add a new file
        files_v3 = {
            **files_v2,
            "app/new_feature.py": "def new_func():\n    pass\n",
        }

        report = detector.detect_changes(files_v3)
        print(f"✓ Added file detected: {len(report.added_files)} added")
        assert len(report.added_files) == 1
        assert "app/new_feature.py" in report.added_files

        # Delete a file
        files_v4 = {k: v for k, v in files_v3.items() if k != "app/config.py"}

        report = detector.detect_changes(files_v4)
        print(f"✓ Deleted file detected: {len(report.deleted_files)} deleted")
        assert len(report.deleted_files) == 1
        assert "app/config.py" in report.deleted_files

        # Test get_changed_files_content
        changed_files, report = detector.get_changed_files_content(files_v4)
        print(f"✓ get_changed_files_content: {len(changed_files)} changed files")
        assert "app/main.py" in changed_files  # Modified
        assert "app/new_feature.py" in changed_files  # Added
        assert "app/config.py" not in changed_files  # Deleted

        # Test should_regenerate_tests
        should_regen, report = detector.should_regenerate_tests(files_v4, threshold=0.1)
        print(f"✓ should_regenerate_tests: {should_regen}")
        assert should_regen, "Should regenerate due to changes"

        # Update snapshot and test no changes
        detector.save_run_snapshot(files_v4)
        should_regen, report = detector.should_regenerate_tests(files_v4)
        print(f"✓ After snapshot update, should_regenerate: {should_regen}")
        assert not should_regen, "No changes after snapshot update"

        # Test stats
        stats = detector.get_stats()
        print(f"✓ Detector Stats: {stats}")
        assert stats["latest_snapshot_files"] > 0

        # Test clear
        detector.clear()
        stats_after = detector.get_stats()
        assert stats_after["latest_snapshot_files"] == 0
        print(f"✓ Detector cleared successfully")

    print("\n✅ ChangeDetector tests PASSED")
    return True


def test_change_report():
    """Test the ChangeReport dataclass."""
    print("\n" + "=" * 60)
    print("Testing ChangeReport...")
    print("=" * 60)

    from utils.change_detector import ChangeReport

    # Test with changes
    report = ChangeReport(
        added_files=["new.py"],
        modified_files=["main.py", "utils.py"],
        deleted_files=["old.py"],
        unchanged_files=["config.py"],
        total_changes=4
    )

    assert report.has_changes
    assert report.total_changes == 4
    print(f"✓ ChangeReport with changes: has_changes={report.has_changes}")

    # Test without changes
    empty_report = ChangeReport(
        added_files=[],
        modified_files=[],
        deleted_files=[],
        unchanged_files=["file1.py", "file2.py"],
        total_changes=0
    )

    assert not empty_report.has_changes
    print(f"✓ ChangeReport without changes: has_changes={empty_report.has_changes}")

    # Test to_dict
    report_dict = report.to_dict()
    assert isinstance(report_dict, dict)
    assert "added_files" in report_dict
    assert "modified_files" in report_dict
    print(f"✓ to_dict() works correctly")

    print("\n✅ ChangeReport tests PASSED")
    return True


def test_analyzer_integration():
    """Test the analyzer integration with change detection."""
    print("\n" + "=" * 60)
    print("Testing Analyzer Change Detection Integration...")
    print("=" * 60)

    from ai_engine.analyzer import (
        _get_change_detector,
        _check_for_changes,
        _save_code_snapshot
    )

    # Check that functions are available
    assert callable(_get_change_detector), "_get_change_detector should be callable"
    assert callable(_check_for_changes), "_check_for_changes should be callable"
    assert callable(_save_code_snapshot), "_save_code_snapshot should be callable"
    print(f"✓ Analyzer change detection functions are available")

    from utils.config import config
    if config.ENABLE_VECTOR_DB:
        detector = _get_change_detector()
        if detector is not None:
            print(f"✓ _get_change_detector() returned a detector instance")
            stats = detector.get_stats()
            print(f"  Latest snapshot files: {stats.get('latest_snapshot_files', 0)}")
        else:
            print(f"✓ _get_change_detector() returned None (deps not fully loaded)")
    else:
        print(f"✓ Vector DB disabled, skipping detector initialization test")

    print("\n✅ Analyzer Integration tests PASSED")
    return True


def test_incremental_workflow():
    """Test the incremental workflow behavior."""
    print("\n" + "=" * 60)
    print("Testing Incremental Workflow...")
    print("=" * 60)

    from utils.vector_store import VectorStore
    from utils.change_detector import ChangeDetector

    with tempfile.TemporaryDirectory() as tmpdir:
        persist_dir = Path(tmpdir) / ".vector_store"
        snapshot_dir = Path(tmpdir) / ".snapshots"
        vector_store = VectorStore(persist_dir=persist_dir)
        detector = ChangeDetector(vector_store=vector_store, snapshot_dir=snapshot_dir)

        # Simulate first run
        files_run1 = {
            "api/routes.py": "@app.route('/users')\ndef get_users():\n    pass\n",
            "api/models.py": "class User:\n    pass\n",
        }
        detector.save_run_snapshot(files_run1, "run_1")
        print(f"✓ First run: indexed {len(files_run1)} files")

        # Simulate second run with no changes
        should_regen, report = detector.should_regenerate_tests(files_run1)
        assert not should_regen, "Should not regenerate when no changes"
        print(f"✓ Second run (no changes): skip regeneration")

        # Simulate third run with minor change
        files_run3 = {
            "api/routes.py": "@app.route('/users')\ndef get_users():\n    return []\n",  # Modified
            "api/models.py": "class User:\n    pass\n",
        }
        should_regen, report = detector.should_regenerate_tests(files_run3, threshold=0.5)
        print(f"✓ Third run (minor change): should_regen={should_regen}, changes={report.total_changes}")

        # Simulate fourth run with significant changes
        files_run4 = {
            "api/routes.py": "# Completely rewritten\n",
            "api/models.py": "# New models\n",
            "api/auth.py": "# New auth module\n",
        }
        should_regen, report = detector.should_regenerate_tests(files_run4, threshold=0.1)
        assert should_regen, "Should regenerate with significant changes"
        print(f"✓ Fourth run (significant changes): should_regen={should_regen}")
        print(f"  Added: {len(report.added_files)}, Modified: {len(report.modified_files)}")

    print("\n✅ Incremental Workflow tests PASSED")
    return True


def main():
    """Run all Stage 6 tests."""
    print("\n" + "=" * 60)
    print("CHANGE DETECTION - STAGE 6 TESTS")
    print("=" * 60)

    all_passed = True

    try:
        if not test_change_detector():
            all_passed = False
    except Exception as e:
        print(f"\n❌ ChangeDetector tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_change_report():
            all_passed = False
    except Exception as e:
        print(f"\n❌ ChangeReport tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_analyzer_integration():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Analyzer Integration tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_incremental_workflow():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Incremental Workflow tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL STAGE 6 TESTS PASSED!")
        print("Change Detection is ready for use.")
        print("\nThe detector will now:")
        print("  - Track file hashes between workflow runs")
        print("  - Detect added, modified, and deleted files")
        print("  - Skip analysis when no significant changes")
        print("  - Speed up subsequent workflow runs")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please review the errors above.")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
