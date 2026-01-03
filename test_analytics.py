#!/usr/bin/env python3
"""Test script for Analytics - Stage 7 verification."""

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_run_metrics():
    """Test the RunMetrics dataclass."""
    print("\n" + "=" * 60)
    print("Testing RunMetrics...")
    print("=" * 60)

    from utils.analytics import RunMetrics

    # Create a run metrics instance
    metrics = RunMetrics(
        run_id="test_run_001",
        timestamp="2024-01-15T10:30:00",
        duration_seconds=120.5,
        files_analyzed=10,
        languages_detected=["python", "javascript"],
        app_type="rest_api",
        scenarios_generated=25,
        tests_generated=30,
        tests_deduplicated=5,
        categories=["functional", "security"],
        tests_passed=20,
        tests_failed=5,
        healed_successfully=3,
        healed_from_kb=1,
        actual_defects=2
    )

    print(f"✓ Created RunMetrics: {metrics.run_id}")
    assert metrics.duration_seconds == 120.5
    assert len(metrics.languages_detected) == 2

    # Test to_dict
    metrics_dict = metrics.to_dict()
    assert isinstance(metrics_dict, dict)
    assert metrics_dict["run_id"] == "test_run_001"
    print(f"✓ to_dict() works correctly")

    # Test from_dict
    restored = RunMetrics.from_dict(metrics_dict)
    assert restored.run_id == metrics.run_id
    assert restored.tests_generated == metrics.tests_generated
    print(f"✓ from_dict() works correctly")

    print("\n✅ RunMetrics tests PASSED")
    return True


def test_workflow_analytics():
    """Test the WorkflowAnalytics class."""
    print("\n" + "=" * 60)
    print("Testing WorkflowAnalytics...")
    print("=" * 60)

    from utils.analytics import WorkflowAnalytics, AggregateStats

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / ".analytics"
        analytics = WorkflowAnalytics(data_dir=data_dir)

        print(f"✓ WorkflowAnalytics initialized")

        # Start first run
        run_id = analytics.start_run("run_001")
        assert run_id == "run_001"
        print(f"✓ Started run: {run_id}")

        # Record metrics
        analytics.record_analysis(
            files_analyzed=15,
            languages=["python"],
            app_type="rest_api"
        )
        print(f"✓ Recorded analysis metrics")

        analytics.record_generation(
            scenarios=20,
            tests=25,
            deduplicated=3,
            categories=["functional", "security", "validation"]
        )
        print(f"✓ Recorded generation metrics")

        analytics.record_execution(passed=18, failed=5, skipped=2)
        print(f"✓ Recorded execution metrics")

        analytics.record_healing(
            attempts=5,
            healed=3,
            from_kb=1,
            defects=1,
            exceeded=1
        )
        print(f"✓ Recorded healing metrics")

        analytics.record_vector_db(kb_patterns=10, classifications=5, rag_chunks=50)
        print(f"✓ Recorded vector DB metrics")

        # End first run
        result = analytics.end_run()
        assert result is not None
        assert result.run_id == "run_001"
        assert result.files_analyzed == 15
        assert result.tests_passed == 18
        print(f"✓ Ended run, duration: {result.duration_seconds:.2f}s")

        # Start and complete more runs for aggregate stats
        for i in range(2, 5):
            analytics.start_run(f"run_00{i}")
            analytics.record_analysis(10 + i, ["python"], "rest_api")
            analytics.record_generation(15 + i, 20 + i, i, ["functional"])
            analytics.record_execution(15 + i, 3, 0)
            analytics.record_healing(3, 2, 1, 1, 0)
            analytics.end_run()
        print(f"✓ Completed {3} additional runs")

        # Test get_recent_runs
        recent = analytics.get_recent_runs(3)
        assert len(recent) == 3
        print(f"✓ get_recent_runs: {len(recent)} runs")

        # Test get_aggregate_stats
        stats = analytics.get_aggregate_stats()
        assert isinstance(stats, AggregateStats)
        assert stats.total_runs == 4
        assert stats.total_tests_generated > 0
        print(f"✓ Aggregate stats: {stats.total_runs} runs, {stats.total_tests_generated} tests")
        print(f"  Pass rate: {stats.avg_pass_rate:.1f}%")
        print(f"  Healing success: {stats.avg_healing_success_rate:.1f}%")

        # Test get_insights
        insights = analytics.get_insights()
        assert "summary" in insights
        assert "healing" in insights
        assert "recommendations" in insights
        print(f"✓ Generated insights with {len(insights['recommendations'])} recommendations")

        # Test export_report
        report_path = Path(tmpdir) / "test_report.json"
        exported = analytics.export_report(report_path)
        assert exported.exists()
        print(f"✓ Exported report to: {exported}")

        # Test clear
        analytics.clear()
        stats_after = analytics.get_aggregate_stats()
        assert stats_after.total_runs == 0
        print(f"✓ Analytics cleared successfully")

    print("\n✅ WorkflowAnalytics tests PASSED")
    return True


def test_aggregate_stats():
    """Test aggregate statistics calculation."""
    print("\n" + "=" * 60)
    print("Testing Aggregate Statistics...")
    print("=" * 60)

    from utils.analytics import WorkflowAnalytics

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / ".analytics"
        analytics = WorkflowAnalytics(data_dir=data_dir)

        # Create runs with varying metrics
        test_cases = [
            {"passed": 90, "failed": 10, "healed": 8, "from_kb": 2, "defects": 2},
            {"passed": 85, "failed": 15, "healed": 12, "from_kb": 5, "defects": 3},
            {"passed": 95, "failed": 5, "healed": 4, "from_kb": 2, "defects": 1},
            {"passed": 80, "failed": 20, "healed": 15, "from_kb": 8, "defects": 5},
        ]

        for i, tc in enumerate(test_cases):
            analytics.start_run(f"run_{i}")
            analytics.record_execution(tc["passed"], tc["failed"])
            analytics.record_healing(
                attempts=tc["healed"] + tc["defects"],
                healed=tc["healed"],
                from_kb=tc["from_kb"],
                defects=tc["defects"],
                exceeded=0
            )
            analytics.end_run()

        stats = analytics.get_aggregate_stats()

        # Verify calculations
        expected_total_passed = sum(tc["passed"] for tc in test_cases)
        expected_total_failed = sum(tc["failed"] for tc in test_cases)
        expected_total_healed = sum(tc["healed"] for tc in test_cases)

        assert stats.total_tests_passed == expected_total_passed
        assert stats.total_tests_failed == expected_total_failed
        assert stats.total_healed == expected_total_healed

        print(f"✓ Total passed: {stats.total_tests_passed} (expected {expected_total_passed})")
        print(f"✓ Total failed: {stats.total_tests_failed} (expected {expected_total_failed})")
        print(f"✓ Total healed: {stats.total_healed} (expected {expected_total_healed})")

        # Check pass rate calculation
        expected_pass_rate = expected_total_passed / (expected_total_passed + expected_total_failed) * 100
        assert abs(stats.avg_pass_rate - expected_pass_rate) < 0.1
        print(f"✓ Pass rate: {stats.avg_pass_rate:.1f}% (expected {expected_pass_rate:.1f}%)")

        # Check KB hit rate
        total_from_kb = sum(tc["from_kb"] for tc in test_cases)
        expected_kb_rate = total_from_kb / expected_total_healed * 100
        assert abs(stats.kb_hit_rate - expected_kb_rate) < 0.1
        print(f"✓ KB hit rate: {stats.kb_hit_rate:.1f}% (expected {expected_kb_rate:.1f}%)")

    print("\n✅ Aggregate Statistics tests PASSED")
    return True


def test_component_integration():
    """Test integration with workflow components."""
    print("\n" + "=" * 60)
    print("Testing Component Integration...")
    print("=" * 60)

    # Test analyzer integration
    from ai_engine.analyzer import _get_analytics as get_analyzer_analytics
    assert callable(get_analyzer_analytics)
    print(f"✓ Analyzer analytics integration available")

    # Test generator integration
    from ai_engine.test_generator import _get_analytics as get_generator_analytics
    assert callable(get_generator_analytics)
    print(f"✓ Test generator analytics integration available")

    # Test healer integration
    from ai_engine.self_healer import _get_analytics as get_healer_analytics
    assert callable(get_healer_analytics)
    print(f"✓ Self-healer analytics integration available")

    print("\n✅ Component Integration tests PASSED")
    return True


def test_insights_generation():
    """Test insights and recommendations generation."""
    print("\n" + "=" * 60)
    print("Testing Insights Generation...")
    print("=" * 60)

    from utils.analytics import WorkflowAnalytics

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / ".analytics"
        analytics = WorkflowAnalytics(data_dir=data_dir)

        # Create a run with low pass rate (should trigger recommendation)
        analytics.start_run("low_pass_run")
        analytics.record_execution(passed=50, failed=50)
        analytics.record_healing(attempts=20, healed=5, from_kb=1, defects=15, exceeded=0)
        analytics.end_run()

        insights = analytics.get_insights()

        # Check that recommendations are generated
        assert len(insights["recommendations"]) > 0
        print(f"✓ Generated {len(insights['recommendations'])} recommendations")

        for rec in insights["recommendations"]:
            print(f"  • {rec}")

        # Verify summary structure
        assert "total_runs" in insights["summary"]
        assert "avg_pass_rate" in insights["summary"]
        print(f"✓ Insights summary structure is correct")

        # Verify healing section
        assert "success_rate" in insights["healing"]
        assert "kb_hit_rate" in insights["healing"]
        print(f"✓ Insights healing section is correct")

    print("\n✅ Insights Generation tests PASSED")
    return True


def main():
    """Run all Stage 7 tests."""
    print("\n" + "=" * 60)
    print("ANALYTICS - STAGE 7 TESTS")
    print("=" * 60)

    all_passed = True

    try:
        if not test_run_metrics():
            all_passed = False
    except Exception as e:
        print(f"\n❌ RunMetrics tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_workflow_analytics():
            all_passed = False
    except Exception as e:
        print(f"\n❌ WorkflowAnalytics tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_aggregate_stats():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Aggregate Statistics tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_component_integration():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Component Integration tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        if not test_insights_generation():
            all_passed = False
    except Exception as e:
        print(f"\n❌ Insights Generation tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL STAGE 7 TESTS PASSED!")
        print("Analytics is ready for use.")
        print("\n🎉 ALL VECTOR DB STAGES COMPLETE! 🎉")
        print("\nThe workflow now includes:")
        print("  ✓ Stage 1: Core Infrastructure (embeddings, vector store)")
        print("  ✓ Stage 2: Healing Knowledge Base")
        print("  ✓ Stage 3: Error Classification Cache")
        print("  ✓ Stage 4: Semantic Test Deduplication")
        print("  ✓ Stage 5: Code RAG for context")
        print("  ✓ Stage 6: Change Detection")
        print("  ✓ Stage 7: Analytics & Insights")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please review the errors above.")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
