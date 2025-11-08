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
  app/                        (Your application)
    ├── *.py, *.js, *.rs, etc (Source code - 15+ languages)
    ├── package.json, Cargo.toml, etc (Config files)
    └── documentation/        (Markdown, text docs)

Processing:
  reports/analysis.md         (AI-generated analysis with categorized scenarios)
  tests/generated/*.py        (AI-generated categorized tests)
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
6. **Continuous Improvement**: Self-healing fixes flaky tests
7. **Smart Failure Analysis**: Distinguishes bugs from test issues
8. **Comprehensive Documentation**: Markdown reports at every stage
9. **Portfolio Ready**: Demonstrates AI, testing, and automation skills

## Test Scenario Examples

The repository includes three complete examples:

### Example 1: Rust API with Documentation
**Files**: `app/rust/` + `app/documentation/rust_api/`

Demonstrates combined code and documentation analysis.

**What's Included**:
- Actix-web Book Library API (250 lines of Rust code)
- Complete API documentation with business rules
- Configuration file (`Cargo.toml`)

**Test It**:
```bash
cp app/rust/* app/
# Documentation already at app/documentation/rust_api/
python src/ai_engine/analyzer.py
```

**Expected Output**:
- Detects Rust language
- Reads `Cargo.toml` for dependencies
- Combines code + documentation
- Generates Functional, Performance, and Security test scenarios

---

### Example 2: Python API Documentation Only
**Files**: `app/documentation/python_api/`

Demonstrates pure TDD workflow - tests from documentation alone.

**What's Included**:
- Complete User Management API specification
- Authentication requirements
- Validation rules and error responses
- Rate limiting specifications

**Test It**:
```bash
rm -rf app/*.py app/*.js app/*.rs app/Cargo.toml app/package.json
# Documentation already at app/documentation/python_api/
python src/ai_engine/analyzer.py
```

**Expected Output**:
- No code files detected
- Analysis based purely on documentation
- Generates Functional and Security test scenarios
- Ready for TDD workflow

---

### Example 3: JavaScript Express API
**Files**: `app/javascript/`

Demonstrates code-only analysis without documentation.

**What's Included**:
- Express.js Product API (190 lines)
- `package.json` with dependencies
- 5 REST endpoints with validation

**Test It**:
```bash
rm -rf app/documentation
cp app/javascript/* app/
python src/ai_engine/analyzer.py
```

**Expected Output**:
- Detects JavaScript language
- Reads `package.json` for dependencies (Express.js)
- Generates Functional test scenarios
- Framework-aware test generation

---

### Running Generated Tests

After analyzing any example:

```bash
# Generate tests from analysis
python src/ai_engine/test_generator.py

# Review generated tests
ls tests/generated/

# Run tests
pytest

# Self-heal any failures
python src/ai_engine/self_healer.py

# Generate summary
python src/ai_engine/report_summarizer.py
```

