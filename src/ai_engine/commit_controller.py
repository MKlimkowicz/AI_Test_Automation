import json
import sys
from pathlib import Path
from typing import Dict

def check_commit_conditions(healing_analysis_path: str = "reports/healing_analysis.json") -> bool:
    """
    Check if commit should be allowed based on healing analysis results.
    
    Commit is allowed only if:
    - All TEST_ERROR tests were successfully healed and are passing
    - Only ACTUAL_DEFECT failures remain (or no failures at all)
    - No tests exceeded max healing attempts while still failing
    
    Args:
        healing_analysis_path: Path to healing analysis JSON file
    
    Returns:
        bool: True if commit should be allowed, False otherwise
    """
    project_root = Path(__file__).parent.parent.parent
    analysis_path = project_root / healing_analysis_path
    
    if not analysis_path.exists():
        print("❌ Healing analysis file not found")
        print(f"   Expected: {analysis_path}")
        return False
    
    with open(analysis_path, "r") as f:
        analysis = json.load(f)
    
    commit_allowed = analysis.get("commit_allowed", False)
    healed_count = analysis.get("healed_count", 0)
    defect_count = analysis.get("defect_count", 0)
    exceeded_count = analysis.get("exceeded_count", 0)
    
    print("="*80)
    print("COMMIT DECISION")
    print("="*80)
    print(f"✓ Successfully Healed Tests: {healed_count}")
    print(f"⚠ Actual Defects Found: {defect_count}")
    print(f"✗ Max Attempts Exceeded: {exceeded_count}")
    print()
    
    if commit_allowed:
        print("✅ COMMIT ALLOWED")
        print()
        print("Reasons:")
        print("  • All TEST_ERROR tests successfully healed and passing")
        if defect_count > 0:
            print(f"  • {defect_count} ACTUAL_DEFECT(s) identified (require manual investigation)")
        else:
            print("  • No defects found - all tests passing")
        print()
        print("Next steps:")
        print("  1. Review BUGS.md for any actual defects")
        print("  2. Commit healed tests")
        print("  3. Investigate actual defects if any")
    else:
        print("❌ COMMIT BLOCKED")
        print()
        print("Reasons:")
        if exceeded_count > 0:
            print(f"  • {exceeded_count} test(s) still failing after max healing attempts")
            print("  • These tests could not be automatically fixed")
        print()
        print("Required actions before commit:")
        print("  1. Review tests that exceeded max attempts")
        print("  2. Manually fix the test issues")
        print("  3. Re-run the healing process")
        print()
        
        # Show which tests exceeded max attempts
        exceeded_tests = analysis.get("max_attempts_exceeded", [])
        if exceeded_tests:
            print("Tests that exceeded max attempts:")
            for test in exceeded_tests:
                test_name = test.get("test_name", "unknown")
                attempts = test.get("attempts", 0)
                print(f"  • {test_name} ({attempts} attempts)")
    
    print("="*80)
    
    return commit_allowed

def main():
    """
    Main entry point for commit controller.
    Returns exit code 0 if commit allowed, 1 if blocked.
    """
    allowed = check_commit_conditions()
    sys.exit(0 if allowed else 1)

if __name__ == "__main__":
    main()

