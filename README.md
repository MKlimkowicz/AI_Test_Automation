# AI Test Automation Framework

An intelligent test automation framework that uses GPT-4o-mini to automatically generate, execute, and self-heal tests with AI-powered reporting.

## Features

- **Code Analysis**: Reads and analyzes Python code from the `app/` directory
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
The analyzer scans all Python files in the `app/` directory:
- Recursively reads all `.py` files
- Detects frameworks (Flask, Django, FastAPI, etc.)
- Sends code to GPT-4o-mini for comprehensive analysis
- Generates `reports/analysis.md` with:
  - Project structure overview
  - Detected API endpoints
  - Database models
  - Key functions and classes
  - Recommended test scenarios

### 2. Test Generation
GPT-4o-mini reads `analysis.md` and generates pytest tests:
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

To analyze your own Python application:

1. Replace the sample code in `app/` with your Python application
2. Run the analyzer: `python src/ai_engine/analyzer.py`
3. Review the generated `reports/analysis.md`
4. Generate tests: `python src/ai_engine/test_generator.py`
5. Run tests: `pytest`

The framework currently supports Python code analysis. It works best with:
- Flask/FastAPI/Django applications
- Python classes and functions
- Database models (SQLAlchemy, Django ORM, etc.)

## Future Enhancements

- [ ] Support for multiple languages (JavaScript, TypeScript, Java, etc.)
- [ ] Integration with CI/CD pipelines (pull request triggers)
- [ ] Selenium/Playwright UI test generation
- [ ] API test generation (REST, GraphQL)
- [ ] Database schema validation tests
- [ ] Performance test generation
- [ ] Security test generation
- [ ] Multi-model AI support (GPT-4, Claude, etc.)
- [ ] Custom test templates
- [ ] Test coverage analysis
- [ ] Live application testing (deployed endpoints)

## Dependencies

- `openai==1.54.0` - GPT-4o-mini integration
- `pytest==8.3.3` - Test framework
- `pytest-html==4.1.1` - HTML reporting
- `pytest-json-report==1.5.0` - JSON reporting

## Contributing

This is a portfolio project demonstrating AI-powered test automation capabilities.

## License

MIT License

