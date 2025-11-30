import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.config import config
from utils.logger import get_logger

logger = get_logger(__name__)


def check_commit_conditions(healing_analysis_path: str = None) -> bool:
    project_root = config.get_project_root()
    
    if healing_analysis_path is None:
        healing_analysis_path = "reports/healing_analysis.json"
    
    analysis_path = project_root / healing_analysis_path
    
    if not analysis_path.exists():
        logger.error("Healing analysis file not found")
        logger.error(f"Expected: {analysis_path}")
        return False
    
    with open(analysis_path, "r") as f:
        analysis = json.load(f)
    
    commit_allowed = analysis.get("commit_allowed", False)
    healed_count = analysis.get("healed_count", 0)
    defect_count = analysis.get("defect_count", 0)
    exceeded_count = analysis.get("exceeded_count", 0)
    
    logger.info("=" * 80)
    logger.info("COMMIT DECISION")
    logger.info("=" * 80)
    logger.info(f"Successfully Healed Tests: {healed_count}")
    logger.info(f"Actual Defects Found: {defect_count}")
    logger.info(f"Max Attempts Exceeded: {exceeded_count}")
    
    if commit_allowed:
        logger.info("COMMIT ALLOWED")
        logger.info("")
        logger.info("Reasons:")
        logger.info("  - All TEST_ERROR tests successfully healed and passing")
        if defect_count > 0:
            logger.info(f"  - {defect_count} ACTUAL_DEFECT(s) identified (require manual investigation)")
        else:
            logger.info("  - No defects found - all tests passing")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Review BUGS.md for any actual defects")
        logger.info("  2. Commit healed tests")
        logger.info("  3. Investigate actual defects if any")
    else:
        logger.warning("COMMIT BLOCKED")
        logger.warning("")
        logger.warning("Reasons:")
        if exceeded_count > 0:
            logger.warning(f"  - {exceeded_count} test(s) still failing after max healing attempts")
            logger.warning("  - These tests could not be automatically fixed")
        logger.warning("")
        logger.warning("Required actions before commit:")
        logger.warning("  1. Review tests that exceeded max attempts")
        logger.warning("  2. Manually fix the test issues")
        logger.warning("  3. Re-run the healing process")
        logger.warning("")
        
        exceeded_tests = analysis.get("max_attempts_exceeded", [])
        if exceeded_tests:
            logger.warning("Tests that exceeded max attempts:")
            for test in exceeded_tests:
                test_name = test.get("test_name", "unknown")
                attempts = test.get("attempts", 0)
                logger.warning(f"  - {test_name} ({attempts} attempts)")
    
    logger.info("=" * 80)
    
    return commit_allowed


def main():
    allowed = check_commit_conditions()
    sys.exit(0 if allowed else 1)


if __name__ == "__main__":
    main()
