# AI Test Automation Workflow

## Overview

This framework implements an intelligent, AI-powered test automation pipeline that:
1. Analyzes your Python code
2. Generates comprehensive analysis reports
3. Auto-generates tests based on analysis
4. Executes tests
5. Self-heals failing tests
6. Generates AI-powered summaries

## Complete Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      1. CODE ANALYSIS                           │
│  ┌──────────┐    AI Analysis    ┌──────────────────┐          │
│  │  app/    │  ───────────────>  │ reports/         │          │
│  │  *.py    │   GPT-4o-mini      │ analysis.md      │          │
│  └──────────┘                    └──────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   2. TEST GENERATION                            │
│  ┌──────────────────┐  Generate Tests  ┌───────────────┐       │
│  │ analysis.md      │ ──────────────>   │ tests/        │       │
│  │ (scenarios)      │   GPT-4o-mini     │ generated/    │       │
│  └──────────────────┘                   └───────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   3. TEST EXECUTION                             │
│  ┌───────────────┐      pytest        ┌──────────────┐         │
│  │ tests/        │ ─────────────────>  │ reports/     │         │
│  │ generated/    │                     │ HTML + JSON  │         │
│  └───────────────┘                     └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   4. SELF-HEALING                               │
│  ┌──────────────┐  AI Classification  ┌──────────────────┐     │
│  │ Failures     │ ─────────────────>   │ Test Error  │    │     │
│  │ (JSON)       │   GPT-4o-mini        │ vs          │    │     │
│  └──────────────┘                      │ Actual Bug  │    │     │
│                                        └──────────────────┘     │
│                                                │                │
│                  ┌─────────────────────────────┴────────┐       │
│                  ▼                                      ▼       │
│         ┌─────────────────┐                  ┌──────────────┐  │
│         │ Regenerate Test │                  │ Flag for     │  │
│         │ (Fixed)         │                  │ Investigation│  │
│         └─────────────────┘                  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   5. AI SUMMARY                                 │
│  ┌──────────────┐  Comprehensive    ┌───────────────────────┐  │
│  │ Test Results │  Analysis         │ summary_YYYY-MM-DD... │  │
│  │ + Healing    │ ──────────────>   │ .md                   │  │
│  │ Analysis     │  GPT-4o-mini      │ (Detailed Report)     │  │
│  └──────────────┘                   └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Analyzer (`src/ai_engine/analyzer.py`)
- Scans `app/` directory for Python files
- Reads all `.py` files (skips large files >50KB)
- Ignores `__pycache__`, `venv`, etc.
- Sends code to GPT-4o-mini
- Generates `reports/analysis.md`

**Output**: Markdown report with:
- Project overview
- Framework detection
- API endpoints
- Database models
- Key functions/classes
- Test scenarios

### 2. Test Generator (`src/ai_engine/test_generator.py`)
- Reads `reports/analysis.md`
- Extracts test scenarios from markdown
- For each scenario, generates pytest code via GPT-4o-mini
- Saves to `tests/generated/test_scenario_X.py`

**Output**: Multiple pytest files

### 3. Test Executor (pytest)
- Runs all generated tests
- Generates HTML report (`reports/html/report.html`)
- Generates JSON report (`reports/pytest-report.json`)

### 4. Self-Healer (`src/ai_engine/self_healer.py`)
- Parses JSON test results
- For each failure:
  - Sends to GPT-4o-mini for classification
  - **Test Error**: Regenerates fixed test
  - **Actual Defect**: Flags for manual review
- Saves healing analysis JSON

**Output**: 
- Fixed test files
- `reports/healing_analysis.json`

### 5. Report Summarizer (`src/ai_engine/report_summarizer.py`)
- Reads test results + healing analysis
- Generates comprehensive markdown summary via GPT-4o-mini
- Filename: `summary_YYYY-MM-DD_HH-MM-SS.md`

**Output**: Markdown summary with:
- Executive summary
- Pass/fail breakdown
- Test errors vs actual defects
- Healing actions taken
- Recommendations

## GitHub Actions Integration

The workflow runs all 5 steps automatically:

```yaml
1. Checkout & Setup
2. Analyze Code → reports/analysis.md
3. Generate Tests → tests/generated/
4. Execute Tests → reports/html/, reports/*.json
5. Self-Heal → Updated tests + healing_analysis.json
6. Generate Summary → reports/summaries/summary_*.md
7. Upload Artifacts
8. Commit Changes
```

## File Flow

```
Input:
  app/*.py                    (Your Python code)

Processing:
  reports/analysis.md         (AI-generated analysis)
  tests/generated/*.py        (AI-generated tests)
  reports/pytest-report.json  (Test results)
  reports/healing_analysis.json (Self-healing results)

Output:
  reports/html/report.html    (Test execution report)
  reports/summaries/summary_*.md (AI summary)
  tests/generated/*.py        (Healed tests)
```

## Usage Example

### Local Development
```bash
cd /Users/maciejklimkowicz/Documents/Projects/AI_Test_Automation

export OPENAI_API_KEY='your-key'

python src/ai_engine/analyzer.py

python src/ai_engine/test_generator.py

pytest

python src/ai_engine/self_healer.py

python src/ai_engine/report_summarizer.py
```

### GitHub Actions
1. Push code to repository
2. Go to Actions tab
3. Run "AI Test Automation" workflow
4. Download artifacts

## Self-Healing Intelligence

The framework distinguishes between:

### Test Errors (Auto-Healed)
- Wrong assertions
- Timing issues
- Incorrect selectors
- Flaky tests
- Missing imports
- Bad test setup

### Actual Defects (Flagged)
- Application bugs
- API failures
- Database issues
- Business logic errors
- Security vulnerabilities

Only test errors are automatically fixed. Actual defects are documented for manual investigation.

## Benefits

1. **Zero Manual Test Writing**: AI generates all tests
2. **Continuous Improvement**: Self-healing fixes flaky tests
3. **Smart Failure Analysis**: Distinguishes bugs from test issues
4. **Comprehensive Documentation**: Markdown reports at every stage
5. **Portfolio Ready**: Demonstrates AI, testing, and automation skills

