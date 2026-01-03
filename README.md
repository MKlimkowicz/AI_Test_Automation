# AI Test Automation Framework

An intelligent test automation framework that uses Claude (Anthropic) to automatically generate, execute, and self-heal tests with AI-powered reporting.

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
  - **Max 5 tests per category** (configurable via `MAX_TESTS_PER_CATEGORY`)
- **Self-Contained Tests**: Each test file is independent with its own fixtures
- **AI-Powered Analysis Reports**: Generates comprehensive markdown analysis of your codebase
- **AI-Powered Test Generation**: Automatically generates pytest tests based on code analysis
- **Iterative Self-Healing**: Continuously heals tests until they pass or are classified as bugs
  - Test errors are automatically fixed and rerun (max 3 attempts per test)
  - Re-classification after each failed rerun
  - Actual defects are flagged for investigation with detailed bug reports
- **Automated Execution**: Runs generated tests with comprehensive reporting
- **AI-Generated Summaries**: Creates detailed markdown reports with failure analysis
- **Vector Database Integration** (Optional): Enhanced capabilities with ChromaDB
  - **Healing Knowledge Base**: Stores successful fixes for pattern matching
  - **Classification Cache**: Caches failure classifications with semantic search
  - **Semantic Test Deduplication**: Removes duplicate tests using embeddings
  - **Code RAG**: Retrieval-augmented analysis for better context
  - **Change Detection**: Smart test regeneration based on code changes
  - **Workflow Analytics**: Tracks metrics across runs with insights

## Project Structure

```
AI_Test_Automation/
├── app/                          # Your application code (to be analyzed)
│   ├── sample_api.py             # Sample Flask API (for testing)
│   └── documentation/
│       └── sample_api_docs.md    # Sample API documentation
├── src/
│   ├── ai_engine/
│   │   ├── analyzer.py           # Scans app/ and generates analysis.md
│   │   ├── test_generator.py     # Generates tests from analysis.md
│   │   ├── self_healer.py        # Failure analysis and self-healing
│   │   ├── bug_reporter.py       # Generates BUGS.md
│   │   └── report_summarizer.py  # AI report generation
│   └── utils/
│       ├── ai_client.py          # Claude/Anthropic API client
│       ├── config.py             # Configuration settings
│       ├── cache.py              # Analysis caching
│       ├── embeddings.py         # Sentence transformer embeddings
│       ├── vector_store.py       # ChromaDB vector store
│       ├── healing_kb.py         # Healing knowledge base
│       ├── classification_cache.py # Failure classification cache
│       ├── test_deduplicator.py  # Semantic test deduplication
│       ├── code_rag.py           # Code RAG for analysis
│       ├── change_detector.py    # Code change detection
│       └── analytics.py          # Workflow analytics
├── tests/
│   └── generated/                # AI-generated tests (self-contained)
├── test_templates/
│   └── test_best_practices.md    # Testing best practices guide
├── reports/
│   ├── analysis.md               # AI-generated code analysis
│   ├── app_metadata.json         # Structured app metadata
│   ├── BUGS.md                   # Detailed bug reports (when defects found)
│   ├── html/                     # Pytest HTML reports
│   └── summaries/                # AI-generated summaries
├── run_full_workflow.sh          # Automated workflow script
├── cleanup_workflow.sh           # Cleanup script
├── requirements.txt
├── pytest.ini
├── .vector_store/                # ChromaDB data (auto-created)
├── .analytics/                   # Analytics data (auto-created)
├── .change_snapshots/            # Change detection snapshots (auto-created)
├── .analysis_cache/              # Analysis cache (auto-created)
└── README.md
```

## Setup

### Prerequisites

- Python 3.11+
- Claude API key (Anthropic)

### Local Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set your Claude API key:
```bash
export CLAUDE_API_KEY='your-api-key-here'
```

## Sample Application

The framework includes a **sample Flask API** for testing and demonstration:

**Location**: `app/sample_api.py` + `app/documentation/sample_api_docs.md`

**Features:**
- User Management API (CRUD operations)
- Authentication endpoint
- Pagination support
- Input validation

**Running the Sample API:**
```bash
python app/sample_api.py
# API runs on http://localhost:5050
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

Edit `src/ai_engine/analyzer.py` and **remove lines 228 and 234**:
```python
# REMOVE THESE LINES:
# Line 228:
code_files = {k: v for k, v in code_files.items() if 'sample_api' in k}

# Line 234:
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
- Checks prerequisites (Python, Claude API key)
- Starts the sample Flask API server
- Runs the complete workflow:
  1. Analyzes code and generates `analysis.md`
  2. Generates self-contained tests by category
  3. Validates generated tests
  4. Runs tests
  5. Performs iterative self-healing
  6. Generates summary reports
- Stops the API server on completion

### Running Locally

**Option 1: Automated Workflow (Recommended)**
```bash
export CLAUDE_API_KEY='your-api-key-here'
./run_full_workflow.sh
```

**Option 2: Step-by-Step Execution**

1. **Analyze Your Code**:
```bash
python src/ai_engine/analyzer.py
```
This scans files in `app/` directory and generates `reports/analysis.md`

2. **Generate Tests**:
```bash
python src/ai_engine/test_generator.py
```
This reads `analysis.md` and generates self-contained pytest tests by category

3. **Run Tests**:
```bash
pytest
```

4. **Iterative Self-Healing** (automatically heals and reruns tests):
```bash
python src/ai_engine/self_healer.py
```

5. **Generate Summary & Bug Reports**:
```bash
python src/ai_engine/report_summarizer.py
```

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
- Sends code, config, and documentation to Claude
- Detects frameworks (Flask, Django, FastAPI, Express, Spring, Actix-web, etc.)
- Generates `reports/analysis.md` with:
  - Project structure overview
  - Detected languages and dependencies
  - API endpoints
  - Database models
  - Key functions and classes
  - **Categorized test scenarios** (Functional/Performance/Security)
- Generates `reports/app_metadata.json` with structured metadata

### 2. Test Generation
Claude reads `analysis.md` and generates pytest tests:
- Extracts test scenarios from categorized sections:
  - **Functional Tests**: Core feature testing (always included)
  - **Performance Tests**: Load/stress testing (when applicable)
  - **Security Tests**: Auth/injection testing (when applicable)
- **Limits to 5 tests per category** (configurable)
- Creates one file per category: `test_functional.py`, `test_security.py`, etc.
- **Self-contained tests**: Each file includes its own fixtures and helpers
- Follows pytest conventions
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

### 5. AI Summary & Bug Reports
Comprehensive reports are generated:

**Summary Report** (`reports/summaries/summary_YYYY-MM-DD_HH-MM-SS.md`):
- Executive summary (pass rates, duration)
- Iterative healing process details
- Successfully healed tests (with attempt counts)
- Tests that exceeded max attempts
- Categorized failures (test errors vs defects)
- Recommendations

**Bug Report** (`reports/BUGS.md`) - Generated when defects found:
- Root cause analysis for each bug
- Severity assessment
- Reproduction steps
- Suggested investigation areas
- Potential fixes
- Related code files

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_API_KEY` | (required) | Your Anthropic API key |
| `CLAUDE_MODEL` | `claude-sonnet-4-5` | Claude model to use |
| `MAX_TESTS_PER_CATEGORY` | `5` | Maximum tests generated per category |
| `MAX_HEALING_ATTEMPTS` | `3` | Max healing attempts per test |
| `MAX_TOKENS_GENERATION` | `8000` | Token limit for test generation |
| `ENABLE_VECTOR_DB` | `false` | Enable Vector DB features |
| `VECTOR_DB_PATH` | `.vector_store` | ChromaDB storage path |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer model |
| `ENABLE_CACHE` | `true` | Enable analysis caching |
| `CACHE_TTL_SECONDS` | `3600` | Cache TTL in seconds |

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
- Authentication endpoint
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
- Up to 5 tests per category (Functional, Security, Validation)
- Tests self-healed automatically when needed
- Actual defects detected and flagged
- BUGS.md generated with detailed analysis

**Viewing Results:**
- HTML Report: `reports/html/report.html`
- Bug Report: `reports/BUGS.md`
- Summary: `reports/summaries/summary_*.md`

## Dependencies

**Core:**
- `anthropic>=0.18.0` - Claude AI integration
- `pytest==8.3.3` - Test framework
- `pytest-html==4.1.1` - HTML reporting
- `pytest-json-report==1.5.0` - JSON reporting
- `tenacity>=8.2.0` - Retry logic

**Vector DB (Optional):**
- `chromadb>=0.4.0` - Vector database
- `sentence-transformers>=2.2.0` - Text embeddings

## Key Features Documentation

- **[test_templates/test_best_practices.md](test_templates/test_best_practices.md)** - Testing best practices and patterns

## Contributing

This is a portfolio project demonstrating AI-powered test automation capabilities.

## License

MIT License
