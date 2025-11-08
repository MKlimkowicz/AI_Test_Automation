# AI Test Automation Framework

An intelligent test automation framework that uses GPT-4o-mini to automatically generate, execute, and self-heal tests with AI-powered reporting.

## Features

- **Multi-Language Support**: Analyzes code in 15+ programming languages
  - Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, PHP, C#, C++, Swift, Kotlin, Scala, R, Shell, SQL
  - Automatic language detection based on file extensions
  - Language-specific syntax highlighting in reports
- **Configuration File Detection**: Automatically reads project configuration files
  - `package.json`, `Cargo.toml`, `requirements.txt`, `pom.xml`, etc.
  - Extracts dependencies and framework information
  - Provides context for more accurate test generation
- **Documentation-Driven Testing**: Supports test generation from documentation alone
  - Reads markdown, text, and other documentation formats from `app/documentation/`
  - Enables pure TDD workflow without existing code
  - Combines documentation with code when both exist
- **Categorized Test Scenarios**: AI intelligently organizes tests into categories
  - **Functional Tests**: Business logic, CRUD, validation, error handling
  - **Performance Tests**: Load, stress, concurrency (when applicable)
  - **Security Tests**: Auth, injection prevention, access control (when applicable)
  - Only suggests categories relevant to your application
- **AI-Powered Analysis Reports**: Generates comprehensive markdown analysis of your codebase
- **AI-Powered Test Generation**: Automatically generates pytest tests based on code analysis
- **Iterative Self-Healing**: Continuously heals tests until they pass or are classified as bugs
  - Test errors are automatically fixed and rerun (max 3 attempts per test)
  - Re-classification after each failed rerun
  - Only commits when all test errors are successfully healed
  - Actual defects are flagged for investigation with detailed bug reports
- **Automated Execution**: Runs generated tests with comprehensive reporting
- **AI-Generated Summaries**: Creates detailed markdown reports with failure analysis
- **GitHub Actions Integration**: Fully automated workflow with manual dispatch trigger

## Project Structure

```
AI_Test_Automation/
├── .github/workflows/
│   └── ai-test-automation.yml    # GitHub Actions workflow
├── app/                          # Your application code (to be analyzed)
│   ├── sample_api.py             # Sample Flask API (for testing)
│   ├── documentation/
│   │   └── sample_api_docs.md    # Sample API documentation
│   └── __init__.py
├── src/
│   ├── ai_engine/
│   │   ├── analyzer.py           # Scans app/ and generates analysis.md
│   │   ├── test_generator.py     # Generates tests from analysis.md
│   │   ├── self_healer.py        # Failure analysis and self-healing
│   │   ├── commit_controller.py  # Commit condition checker
│   │   ├── bug_reporter.py       # Generates BUGS.md
│   │   └── report_summarizer.py  # AI report generation
│   └── utils/
│       └── openai_client.py      # OpenAI GPT-4o-mini client
├── tests/
│   ├── generated/                # AI-generated tests
│   └── conftest.py               # Shared pytest fixtures
├── test_templates/
│   └── test_best_practices.md    # Testing best practices guide
├── reports/
│   ├── analysis.md               # AI-generated code analysis
│   ├── BUGS.md                   # Detailed bug reports (when defects found)
│   ├── html/                     # Pytest HTML reports
│   └── summaries/                # AI-generated summaries
├── run_full_workflow.sh          # Automated workflow script
├── requirements.txt
├── pytest.ini
└── README.md
```

## Setup

### Prerequisites

- Python 3.11+
- OpenAI API key with access to GPT-4o-mini

### Local Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set your OpenAI API key:
```bash
export OPENAI_API_KEY='your-api-key-here'
```

### GitHub Actions Setup

1. Go to your repository Settings > Secrets and variables > Actions
2. Add a new repository secret:
   - Name: `OPENAI_API_KEY`
   - Value: Your OpenAI API key

## Sample Application

The framework includes a **sample Flask API** for testing and demonstration:

**Location**: `app/sample_api.py` + `app/documentation/sample_api_docs.md`

**Features:**
- User Management API (CRUD operations)
- Authentication endpoint
- Pagination support
- Input validation
- **Intentional bug** in login endpoint (for defect detection testing)

**Running the Sample API:**
```bash
python app/sample_api.py
# API runs on http://localhost:5000
```

**Testing the Sample API:**
The `run_full_workflow.sh` script automatically starts/stops the API and runs the full test automation workflow.

### Switching to Your Own Application

To analyze your own application instead of the sample:

**Option 1: Replace sample_api files**
```bash
# Remove sample files
rm app/sample_api.py
rm app/documentation/sample_api_docs.md

# Add your application
cp your_app.py app/
cp your_docs.md app/documentation/
```

**Option 2: Remove analyzer filters (analyze all files)**

The analyzer currently has **temporary filters** to only scan `sample_api` files. To analyze all files in `app/`:

Edit `src/ai_engine/analyzer.py` and **remove lines 215-216 and 222-223**:
```python
# REMOVE THESE LINES:
# Line 215-216:
code_files = {k: v for k, v in code_files.items() if 'sample_api' in k}

# Line 222-223:
doc_files = {k: v for k, v in doc_files.items() if 'sample_api' in k}
```

After removing these filters, the analyzer will detect and analyze **all code and documentation** in the `app/` directory.

## Usage

### Quick Start (Recommended)

Run the complete workflow with a single command:

```bash
./run_full_workflow.sh
```

This automated script:
- Checks prerequisites (Python, OpenAI API key)
- Starts the sample Flask API server
- Runs all 6 workflow steps automatically
- Generates all reports (including BUGS.md)
- Stops the API server on completion
- Returns appropriate exit codes for CI/CD

**Exit Codes:**
- `0`: All tests passed or only actual defects remain (commit allowed)
- `1`: Tests failed after max healing attempts (commit blocked)

### Running Locally

**Option 1: Automated Workflow (Recommended)**
```bash
export OPENAI_API_KEY='your-api-key-here'
./run_full_workflow.sh
```

**Option 2: Step-by-Step Execution**

1. **Analyze Your Code**:
```bash
python src/ai_engine/analyzer.py
```
This scans Python files in `app/` directory and generates `reports/analysis.md`

2. **Generate Tests**:
```bash
python src/ai_engine/test_generator.py
```
This reads `analysis.md` and generates pytest tests

3. **Run Tests**:
```bash
pytest
```

4. **Iterative Self-Healing** (automatically heals and reruns tests):
```bash
python src/ai_engine/self_healer.py
```

5. **Check Commit Conditions**:
```bash
python src/ai_engine/commit_controller.py
```

6. **Generate Summary & Bug Reports**:
```bash
python src/ai_engine/report_summarizer.py
```

### Running with GitHub Actions

1. Go to the "Actions" tab in your repository
2. Select "AI Test Automation" workflow
3. Click "Run workflow"
4. Wait for completion
5. Download artifacts:
   - `analysis-report`: Code analysis markdown
   - `test-reports`: HTML and JSON test reports
   - `ai-summary`: AI-generated markdown summary
   - `generated-tests`: All generated test files

## How It Works

### 1. Code Analysis Phase
The analyzer scans the `app/` directory for code, configuration, and documentation:

**Language Detection**:
- Scans for file extensions to detect programming languages
- Supports 15+ languages (Python, JavaScript, TypeScript, Rust, Go, Java, etc.)
- Automatically identifies all languages present in your project

**Code Scanning**:
- Recursively reads source code files based on detected languages
- Skips large files (>50KB) and ignored directories (`node_modules`, `venv`, etc.)
- Tags each file with its detected language for proper syntax highlighting

**Configuration File Detection**:
- Automatically finds language-specific config files:
  - JavaScript/TypeScript: `package.json`, `tsconfig.json`
  - Python: `requirements.txt`, `pyproject.toml`, `setup.py`
  - Rust: `Cargo.toml`
  - Go: `go.mod`
  - Java: `pom.xml`, `build.gradle`
  - And more...
- Extracts dependency information for better context

**Documentation Integration**:
- Scans `app/documentation/` for markdown, text, and other doc files
- Supports documentation-only analysis (pure TDD workflow)
- Combines documentation with code when both exist

**AI Analysis**:
- Sends code, config, and documentation to GPT-4o-mini
- Detects frameworks (Flask, Django, FastAPI, Express, Spring, Actix-web, etc.)
- Generates `reports/analysis.md` with:
  - Project structure overview
  - Detected languages and dependencies
  - API endpoints
  - Database models
  - Key functions and classes
  - **Categorized test scenarios** (Functional/Performance/Security)

### 2. Test Generation
GPT-4o-mini reads `analysis.md` and generates pytest tests:
- Extracts test scenarios from categorized sections:
  - **Functional Tests**: Core feature testing (always included)
  - **Performance Tests**: Load/stress testing (when applicable)
  - **Security Tests**: Auth/injection testing (when applicable)
- Prefixes test files with category tags: `[Functional]`, `[Performance]`, `[Security]`
- Follows pytest conventions
- Minimal comments and docstrings
- Type-hinted code
- Independent, reusable tests

### 3. Test Execution
Generated tests are executed with:
- HTML reporting (`pytest-html`)
- JSON reporting (`pytest-json-report`)
- Detailed failure information

### 4. Iterative Self-Healing
For each test failure, AI classifies it and enters an iterative healing loop:

**Healing Process** (for TEST_ERROR):
1. Classify failure as TEST_ERROR or ACTUAL_DEFECT
2. If TEST_ERROR: Heal the test
3. Rerun the healed test
4. If passes: Mark as successfully healed
5. If fails: Re-classify and repeat (max 3 attempts)
6. If becomes ACTUAL_DEFECT: Stop healing, flag for investigation

**Test Error** (Auto-Healed):
- Wrong assertions
- Timing issues
- Bad selectors
- Flaky tests
- Incorrect setup/teardown

**Actual Defect** (Flagged + Detailed Bug Report):
- Application bugs
- API failures
- Database issues
- Business logic errors

**Commit Control**:
- Commits only when all TEST_ERROR tests are successfully healed
- Blocks commit if tests exceed max healing attempts
- ACTUAL_DEFECT tests don't block commits (require manual investigation)

### 5. AI Summary & Bug Reports
Comprehensive reports are generated:

**Summary Report** (`reports/summaries/summary_YYYY-MM-DD_HH-MM-SS.md`):
- Executive summary (pass rates, duration)
- Iterative healing process details
- Successfully healed tests (with attempt counts)
- Tests that exceeded max attempts
- Categorized failures (test errors vs defects)
- Commit status (allowed or blocked)
- Recommendations

**Bug Report** (`reports/BUGS.md`) - Generated when defects found:
- Root cause analysis for each bug
- Severity assessment
- Reproduction steps
- Suggested investigation areas
- Potential fixes
- Related code files

## Report Structure

### AI Summary Includes:
1. **Executive Summary**
   - Total tests, pass rate, duration
2. **Test Results Overview**
   - Passed, failed, skipped counts
3. **Failure Analysis**
   - Test Errors (Self-Healed) with fix details
   - Actual Defects (Requiring Investigation)
4. **Self-Healing Actions**
   - What was fixed and why
   - Confidence levels
5. **Recommendations**
   - Next steps
   - Areas requiring attention

## Configuration

### pytest.ini
```ini
[pytest]
testpaths = tests/generated
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --html=reports/html/report.html 
    --self-contained-html
    --json-report
    --json-report-file=reports/pytest-report.json
```

### GitHub Actions Workflow
- **Trigger**: Manual dispatch (`workflow_dispatch`)
- **Artifacts Retention**: 30 days
- **Auto-commit**: Healed tests and summaries are committed back to repo

## Adding Your Own Code

The framework supports multiple workflows depending on your needs:

### Option 1: Code + Documentation (Recommended)
Place your application code in `app/` and documentation in `app/documentation/`:

```bash
app/
├── main.rs                    # Your Rust code
├── server.js                  # Your JavaScript code
├── api.py                     # Your Python code
└── documentation/
    ├── api_spec.md            # API documentation
    └── requirements.md        # Requirements doc
```

### Option 2: Code Only
Place your application code directly in `app/`:

```bash
app/
├── src/
│   └── main.rs
├── Cargo.toml
└── package.json
```

### Option 3: Documentation Only (TDD Workflow)
Place only documentation in `app/documentation/` to generate tests before writing code:

```bash
app/
└── documentation/
    └── api_specification.md
```

### Running the Analyzer

1. Add your code/documentation to the `app/` directory
2. Run the analyzer: `python src/ai_engine/analyzer.py`
3. Review the generated `reports/analysis.md`
4. Generate tests: `python src/ai_engine/test_generator.py`
5. Run tests: `pytest`

### Supported Languages & Frameworks

**Languages** (15+):
- Python, JavaScript, TypeScript, Java, Go, Rust, Ruby, PHP, C#, C++, Swift, Kotlin, Scala, R, Shell, SQL

**Frameworks** (auto-detected):
- Python: Flask, Django, FastAPI
- JavaScript: Express.js, Next.js
- Rust: Actix-web, Rocket
- Java: Spring Boot
- Go: Gin, Echo
- And more...

**Configuration Files** (auto-detected):
- `package.json`, `Cargo.toml`, `requirements.txt`, `pom.xml`, `go.mod`, `Gemfile`, `composer.json`, etc.

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

## Future Enhancements

- [x] **Support for multiple languages** - ✅ Implemented (15+ languages)
- [x] **Performance test generation** - ✅ Implemented (categorized scenarios)
- [x] **Security test generation** - ✅ Implemented (categorized scenarios)
- [ ] Integration with CI/CD pipelines (pull request triggers)
- [ ] Selenium/Playwright UI test generation
- [ ] API test generation (REST, GraphQL)
- [ ] Database schema validation tests
- [ ] Multi-model AI support (GPT-4, Claude, etc.)
- [ ] Custom test templates
- [ ] Test coverage analysis
- [ ] Live application testing (deployed endpoints)
- [ ] Docker container analysis
- [ ] Microservices architecture testing

## Dependencies

- `openai==1.54.0` - GPT-4o-mini integration
- `pytest==8.3.3` - Test framework
- `pytest-html==4.1.1` - HTML reporting
- `pytest-json-report==1.5.0` - JSON reporting

## Key Features Documentation

- **[ITERATIVE_HEALING.md](ITERATIVE_HEALING.md)** - Complete guide to iterative self-healing
- **[WORKFLOW.md](WORKFLOW.md)** - Detailed workflow documentation
- **[test_templates/test_best_practices.md](test_templates/test_best_practices.md)** - Testing best practices and patterns

## Contributing

This is a portfolio project demonstrating AI-powered test automation capabilities.

## License

MIT License

