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
- **Intelligent Self-Healing**: Distinguishes between test errors and actual defects
  - Test errors are automatically fixed and regenerated
  - Actual defects are flagged for investigation
- **Automated Execution**: Runs generated tests with comprehensive reporting
- **AI-Generated Summaries**: Creates detailed markdown reports with failure analysis
- **GitHub Actions Integration**: Fully automated workflow with manual dispatch trigger

## Project Structure

```
AI_Test_Automation/
├── .github/workflows/
│   └── ai-test-automation.yml    # GitHub Actions workflow
├── app/                          # Your Python application code (to be analyzed)
│   ├── sample_api.py             # Sample application (replace with your code)
│   └── __init__.py
├── src/
│   ├── ai_engine/
│   │   ├── analyzer.py           # Scans app/ and generates analysis.md
│   │   ├── test_generator.py     # Generates tests from analysis.md
│   │   ├── self_healer.py        # Failure analysis and self-healing
│   │   └── report_summarizer.py  # AI report generation
│   └── utils/
│       └── openai_client.py      # OpenAI GPT-4o-mini client
├── tests/generated/              # AI-generated tests
├── reports/
│   ├── analysis.md               # AI-generated code analysis
│   ├── html/                     # Pytest HTML reports
│   └── summaries/                # AI-generated summaries
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

## Usage

### Running Locally

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

4. **Self-Heal Failed Tests**:
```bash
python src/ai_engine/self_healer.py
```

5. **Generate Summary**:
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

### 4. Self-Healing
For each test failure, AI classifies it as:

**Test Error** (Self-Healed):
- Wrong assertions
- Timing issues
- Bad selectors
- Flaky tests
- Incorrect setup/teardown

**Actual Defect** (Flagged for Investigation):
- Application bugs
- API failures
- Database issues
- Business logic errors

Only test errors are automatically fixed and regenerated.

### 5. AI Summary
A comprehensive markdown report is generated with:
- Executive summary (pass rates, duration)
- Categorized failures (test errors vs defects)
- Self-healing actions taken
- Before/after comparison for healed tests
- Actual defects requiring investigation
- Recommendations

Summary filename format: `summary_YYYY-MM-DD_HH-MM-SS.md`

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

## Test Scenario Examples

The repository includes three complete examples demonstrating different use cases:

### Example 1: Rust API with Documentation
**Location**: `app/rust/` + `app/documentation/rust_api/`

A complete Actix-web Book Library API with comprehensive documentation.

**Code**: `app/rust/main.rs`, `app/rust/Cargo.toml`
- Actix-web REST API with 7 endpoints
- CRUD operations for books
- ISBN uniqueness validation
- Thread-safe Mutex-based storage
- Search functionality

**Documentation**: `app/documentation/rust_api/book_library_api.md`
- Complete API specification
- Business rules and validation
- Testing requirements
- Security considerations

**To Test**:
```bash
cp app/rust/* app/
mkdir -p app/documentation
# Documentation already in place at app/documentation/rust_api/
python src/ai_engine/analyzer.py
```

**Expected**: Analysis with Rust code + documentation, categorized test scenarios including functional, performance, and security tests.

---

### Example 2: Python API Documentation Only (TDD)
**Location**: `app/documentation/python_api/`

A complete User Management API specification without any code - perfect for TDD workflow.

**Documentation**: `app/documentation/python_api/api_specification.md`
- 5 REST endpoints (Create, Read, Update, Delete, List)
- Authentication requirements
- Validation rules
- Rate limiting specs
- Comprehensive test scenarios

**To Test**:
```bash
# Remove any code files
rm -rf app/*.py app/*.js app/*.rs app/Cargo.toml app/package.json
# Documentation already in place
python src/ai_engine/analyzer.py
```

**Expected**: Analysis based purely on documentation, functional and security test scenarios generated before any code exists.

---

### Example 3: JavaScript Express API (Code Only)
**Location**: `app/javascript/`

A working Express.js Product API without documentation.

**Code**: `app/javascript/server.js`, `app/javascript/package.json`
- Express.js REST API with 5 endpoints
- Product CRUD operations
- In-memory data store
- Query filtering (price, stock)
- Input validation and error handling

**To Test**:
```bash
rm -rf app/documentation
cp app/javascript/* app/
python src/ai_engine/analyzer.py
```

**Expected**: Analysis detects JavaScript/Express, extracts dependencies from package.json, generates functional test scenarios.

---

### Testing All Examples

See the complete testing guide in each example's documentation or run:

```bash
# Test each scenario sequentially
python src/ai_engine/analyzer.py  # Analyzes current app/ content
cat reports/analysis.md            # Review generated analysis
python src/ai_engine/test_generator.py  # Generate tests
pytest                             # Run generated tests
```

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

## Contributing

This is a portfolio project demonstrating AI-powered test automation capabilities.

## License

MIT License

