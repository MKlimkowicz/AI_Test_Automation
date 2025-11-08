# AI Test Automation Workflow

## Overview

This framework implements an intelligent, AI-powered test automation pipeline that:
1. Analyzes code in 15+ programming languages
2. Detects and reads configuration files
3. Integrates documentation for comprehensive analysis
4. Generates categorized test scenarios (Functional/Performance/Security)
5. Auto-generates tests based on analysis
6. Executes tests
7. Self-heals failing tests
8. Generates AI-powered summaries

## Automated Workflow Script

The `run_full_workflow.sh` script automates the entire pipeline:

**Usage:**
```bash
./run_full_workflow.sh
```

**What It Does:**
1. **Checks Prerequisites** - Python 3, OpenAI API key, dependencies
2. **Starts Sample API** - Launches Flask app on port 5000
3. **Step 1: Analyze Code** - Scans app/ and app/documentation/
4. **Step 2: Generate Tests** - Creates pytest files from analysis
5. **Step 3: Execute Tests** - Runs all tests with HTML/JSON reports
6. **Step 4: Iterative Self-Healing** - Heals and reruns failing tests (max 3 attempts)
7. **Step 5: Check Commit Conditions** - Determines if commit should be allowed
8. **Step 6: Generate Reports** - Creates summary and BUGS.md (always runs, even if commit blocked)
9. **Cleanup** - Stops API server

**Exit Behavior:**
- Always generates reports (Step 6), even when commit is blocked
- Returns exit code 1 if commit blocked (for CI/CD)
- Returns exit code 0 if commit allowed

**Benefits:**
- One-command execution
- Automatic API lifecycle management
- Color-coded progress output
- Comprehensive error handling
- CI/CD compatible exit codes

## Complete Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      1. CODE ANALYSIS                           │
│  ┌──────────────────────┐  AI Analysis  ┌──────────────────┐   │
│  │  app/                │               │ reports/         │   │
│  │  - Code (15+ langs)  │──────────────>│ analysis.md      │   │
│  │  - Config files      │  GPT-4o-mini  │ (Categorized     │   │
│  │  - Documentation     │               │  Scenarios)      │   │
│  └──────────────────────┘               └──────────────────┘   │
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

**Language Detection**:
- Scans `app/` directory for file extensions
- Detects 15+ programming languages automatically
- Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, PHP, C#, C++, Swift, Kotlin, Scala, R, Shell, SQL

**Code Scanning**:
- Reads source code files based on detected languages
- Skips large files (>50KB) and ignored directories
- Ignores `__pycache__`, `venv`, `node_modules`, `.git`, etc.
- Tags each file with its language for syntax highlighting

**Configuration File Detection**:
- Automatically finds language-specific config files:
  - JavaScript/TypeScript: `package.json`, `tsconfig.json`
  - Python: `requirements.txt`, `pyproject.toml`, `setup.py`
  - Rust: `Cargo.toml`, `Cargo.lock`
  - Go: `go.mod`, `go.sum`
  - Java: `pom.xml`, `build.gradle`
  - And more...
- Extracts dependencies and project metadata

**Documentation Integration**:
- Scans `app/documentation/` for markdown, text, and other doc files
- Supports documentation-only analysis (TDD workflow)
- Combines documentation with code when both exist

**AI Analysis**:
- Sends code, config, and documentation to GPT-4o-mini
- Detects frameworks (Flask, Django, FastAPI, Express, Spring, Actix-web, etc.)
- Generates `reports/analysis.md`

**Output**: Markdown report with:
- Project overview (languages, dependencies, frameworks)
- Project structure (code + config + docs)
- API endpoints
- Database models
- Key functions/classes
- **Categorized test scenarios**:
  - Functional Tests (always included)
  - Performance Tests (when applicable)
  - Security Tests (when applicable)

### 2. Test Generator (`src/ai_engine/test_generator.py`)
- Reads `reports/analysis.md`
- Extracts test scenarios from categorized sections:
  - **Functional Tests**: Business logic, CRUD operations, validation
  - **Performance Tests**: Load, stress, concurrency testing
  - **Security Tests**: Auth, injection prevention, access control
- Prefixes scenarios with category tags: `[Functional]`, `[Performance]`, `[Security]`
- For each scenario, generates pytest code via GPT-4o-mini
- Saves to `tests/generated/test_scenario_X.py`

**Output**: Multiple pytest files with categorized tests

### 3. Test Executor (pytest)
- Runs all generated tests
- Generates HTML report (`reports/html/report.html`)
- Generates JSON report (`reports/pytest-report.json`)

### 4. Iterative Self-Healer (`src/ai_engine/self_healer.py`)
Performs iterative healing with automatic reruns:

**Process**:
- Parses JSON test results
- For each failure, classifies as TEST_ERROR or ACTUAL_DEFECT
- **For TEST_ERROR** (max 3 attempts):
  1. Heal the test code
  2. Rerun only that test
  3. If passes: Mark as successfully healed
  4. If fails: Re-classify and repeat
  5. If becomes ACTUAL_DEFECT: Stop healing
- **For ACTUAL_DEFECT**: Don't heal, flag for investigation
- Determines if commit should be allowed

**Output**: 
- Fixed test files (healed and passing)
- `reports/healing_analysis.json` with:
  - successfully_healed (tests that now pass)
  - actual_defects (bugs requiring investigation)
  - max_attempts_exceeded (tests still failing)
  - commit_allowed (true/false)

### 5. Report Summarizer & Bug Reporter
**Report Summarizer** (`src/ai_engine/report_summarizer.py`):
- Reads test results + healing analysis
- Generates comprehensive markdown summary via GPT-4o-mini
- Integrates bug report generation
- Filename: `summary_YYYY-MM-DD_HH-MM-SS.md`

**Bug Reporter** (`src/ai_engine/bug_reporter.py`):
- Generates detailed `BUGS.md` for ACTUAL_DEFECT findings
- AI analyzes each bug with root cause, severity, fixes
- Only created when defects exist

**Output**: 
- `reports/summaries/summary_*.md` with:
  - Executive summary
  - Iterative healing details
  - Successfully healed tests (with attempt counts)
  - Tests that exceeded max attempts
  - Actual defects summary
  - Commit status
  - Recommendations
- `reports/BUGS.md` (if defects found) with:
  - Detailed bug analysis
  - Root cause and severity
  - Reproduction steps
  - Investigation guidance

## GitHub Actions Integration

The workflow runs all steps automatically with iterative healing:

```yaml
1. Checkout & Setup
2. Analyze Code → reports/analysis.md
3. Generate Tests → tests/generated/
4. Execute Tests (Initial) → reports/html/, reports/*.json
5. Iterative Self-Heal → Heal, rerun, re-classify (max 3 attempts/test)
6. Check Commit Conditions → Allow or block based on healing results
7. Generate Summary & BUGS.md → reports/summaries/, reports/BUGS.md
8. Upload Artifacts (all reports)
9. Commit Changes (only if allowed)
   - Commits healed tests if all TEST_ERROR tests passed
   - Blocks commit if any tests exceeded max attempts
```

## File Flow

```
Input:
  app/                        (Your application)
    ├── sample_api.py         (Sample Flask API)
    ├── *.py, *.js, *.rs, etc (Source code - 15+ languages)
    ├── package.json, Cargo.toml, etc (Config files)
    └── documentation/        (Markdown, text docs)
        └── sample_api_docs.md

Automation:
  run_full_workflow.sh        (One-command automation)

Processing:
  reports/analysis.md         (AI-generated analysis with categorized scenarios)
  tests/generated/*.py        (AI-generated categorized tests)
  reports/pytest-report.json  (Test results)
  reports/healing_analysis.json (Self-healing results)

Output:
  reports/html/report.html    (Test execution report)
  reports/BUGS.md             (Detailed bug analysis - when defects found)
  reports/summaries/summary_*.md (AI summary - always generated)
  tests/generated/*.py        (Healed tests)
```

## Usage Example

### Automated Workflow (Recommended)
```bash
cd /Users/maciejklimkowicz/Documents/Projects/AI_Test_Automation
export OPENAI_API_KEY='your-key'
./run_full_workflow.sh
```

### Manual Step-by-Step Execution
```bash
cd /Users/maciejklimkowicz/Documents/Projects/AI_Test_Automation
export OPENAI_API_KEY='your-key'

# Start your application (if needed)
python app/sample_api.py &

# Run workflow steps
python src/ai_engine/analyzer.py
python src/ai_engine/test_generator.py
pytest
python src/ai_engine/self_healer.py
python src/ai_engine/commit_controller.py
python src/ai_engine/report_summarizer.py
```

### GitHub Actions
1. Push code to repository
2. Go to Actions tab
3. Run "AI Test Automation" workflow
4. Download artifacts

## Categorized Test Scenarios

The AI intelligently organizes test scenarios into three categories based on application analysis:

### Functional Tests (Always Included)
Core feature testing that verifies business logic and correctness:
- CRUD operations
- API endpoint functionality
- Input validation
- Error handling
- Business rule enforcement
- Happy path and edge cases

**Example Scenarios**:
- `[Functional] Create user with valid data returns 201 Created`
- `[Functional] Get non-existent resource returns 404 Not Found`
- `[Functional] Invalid input returns 400 Bad Request`

### Performance Tests (Conditionally Included)
Only included when the application has performance requirements or scalability needs:
- Response time testing
- Load testing (expected traffic)
- Stress testing (beyond capacity)
- Concurrency testing
- Resource usage monitoring
- Database query performance

**Example Scenarios**:
- `[Performance] API responds within 200ms under normal load`
- `[Performance] System handles 100 concurrent requests`
- `[Performance] Database queries complete within acceptable limits`

**Omitted When**:
- Simple CRUD apps with low traffic
- Proof-of-concept code
- No performance requirements specified

### Security Tests (Conditionally Included)
Only included when the application has security features or handles sensitive data:
- Authentication and authorization
- Input sanitization (SQL injection, XSS prevention)
- Data encryption and privacy
- Rate limiting
- Token/session management
- Access control validation

**Example Scenarios**:
- `[Security] Requests without auth token return 401 Unauthorized`
- `[Security] SQL injection attempts are properly sanitized`
- `[Security] Users cannot access resources they don't own`
- `[Security] Rate limiting blocks excessive requests`

**Omitted When**:
- No authentication/authorization
- No sensitive data handling
- Read-only applications

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
2. **Multi-Language Support**: Works with 15+ programming languages
3. **Intelligent Test Categorization**: Functional, Performance, Security
4. **Documentation-Driven Testing**: Generate tests before writing code
5. **Configuration Awareness**: Understands dependencies and frameworks
6. **Iterative Self-Healing**: Continuously heals tests until they pass (max 3 attempts)
7. **Smart Failure Analysis**: Distinguishes bugs from test issues with re-classification
8. **Conditional Commits**: Only commits when tests are truly fixed
9. **Detailed Bug Reports**: AI-generated BUGS.md with investigation guidance
10. **Comprehensive Documentation**: Markdown reports at every stage
11. **Portfolio Ready**: Demonstrates AI, testing, and automation skills

## Example: Sample Flask API

The repository includes a complete working example in `app/sample_api.py`:

**Application Features:**
- Flask REST API with 7 endpoints
- User CRUD operations
- Authentication endpoint (with intentional bug)
- Pagination support
- Input validation

**Documentation:** `app/documentation/sample_api_docs.md`
- Complete API specification
- Request/response examples
- Validation rules
- Test scenarios

**To Test:**
```bash
./run_full_workflow.sh
```

**Expected Results:**
- 15+ tests generated
- 1-2 tests self-healed automatically
- 1 actual defect detected (intentional login bug)
- BUGS.md generated with detailed analysis
- Commit blocked until defect is fixed

**Viewing Results:**
- HTML Report: `reports/html/report.html`
- Bug Report: `reports/BUGS.md`
- Summary: `reports/summaries/summary_*.md`

## Analyzer Configuration

### Temporary Filters

The analyzer (`src/ai_engine/analyzer.py`) currently includes **temporary filters** at lines 215-216 and 222-223:

```python
# Lines 215-216
code_files = {k: v for k, v in code_files.items() if 'sample_api' in k}

# Lines 222-223
doc_files = {k: v for k, v in doc_files.items() if 'sample_api' in k}
```

**Purpose:** These filters ensure only the sample API is analyzed during testing/demonstration.

**To Analyze All Files:**
1. Open `src/ai_engine/analyzer.py`
2. Delete or comment out lines 215-216 and 222-223
3. Save the file
4. Run analyzer: `python src/ai_engine/analyzer.py`

The analyzer will now scan **all code and documentation** in `app/` and `app/documentation/`.

### Supported File Types

The analyzer automatically detects and reads:
- **Code**: `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.rb`, `.php`, `.cs`, `.cpp`, `.swift`, `.kt`, `.scala`, `.r`, `.sh`, `.sql`
- **Config**: `package.json`, `Cargo.toml`, `requirements.txt`, `pom.xml`, `go.mod`, etc.
- **Docs**: `.md`, `.txt`, `.rst`, `.adoc`

