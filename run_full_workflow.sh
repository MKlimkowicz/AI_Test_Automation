#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$PROJECT_ROOT/logs/workflow.log"
cd "$PROJECT_ROOT"

mkdir -p "$PROJECT_ROOT/logs"

if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

log_step() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}▶ $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
    echo "[$timestamp] [STEP] $1" >> "$LOG_FILE"
}

log_success() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}✓ $1${NC}"
    echo "[$timestamp] [SUCCESS] $1" >> "$LOG_FILE"
}

log_error() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}✗ $1${NC}"
    echo "[$timestamp] [ERROR] $1" >> "$LOG_FILE"
}

log_warning() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}⚠ $1${NC}"
    echo "[$timestamp] [WARNING] $1" >> "$LOG_FILE"
}

log_info() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${CYAN}ℹ $1${NC}"
    echo "[$timestamp] [INFO] $1" >> "$LOG_FILE"
}

check_prerequisites() {
    log_step "Checking Prerequisites"
    
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    log_success "Python 3 found: $(python3 --version)"
    
    if [ -z "$OPENAI_API_KEY" ]; then
        log_error "OPENAI_API_KEY environment variable is not set"
        log_info "Set it with: export OPENAI_API_KEY='your-key-here'"
        exit 1
    fi
    log_success "OPENAI_API_KEY is set"
    
    if ! python3 -c "import flask" 2>/dev/null; then
        log_warning "Flask not found. Installing dependencies..."
        pip3 install -r requirements.txt
    fi
    log_success "Required packages are installed"
}

start_api() {
    log_step "Starting Sample API Server"
    
    lsof -ti:5000 | xargs kill -9 2>/dev/null || true
    
    python3 app/sample_api.py > /tmp/flask_api.log 2>&1 &
    API_PID=$!
    
    log_info "Waiting for API to start..."
    sleep 3
    
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        log_success "API is running (PID: $API_PID)"
        echo $API_PID > /tmp/flask_api.pid
    else
        log_error "Failed to start API"
        cat /tmp/flask_api.log
        exit 1
    fi
}

stop_api() {
    if [ -f /tmp/flask_api.pid ]; then
        API_PID=$(cat /tmp/flask_api.pid)
        if ps -p $API_PID > /dev/null 2>&1; then
            log_info "Stopping API (PID: $API_PID)..."
            kill $API_PID 2>/dev/null || true
            rm /tmp/flask_api.pid
            log_success "API stopped"
        fi
    fi
}

trap stop_api EXIT

run_analyzer() {
    log_step "Step 1: Analyzing Application Code & Documentation"
    
    if python3 src/ai_engine/analyzer.py; then
        log_success "Analysis complete"
        
        if [ -f "reports/analysis.md" ]; then
            log_info "Analysis report generated: reports/analysis.md"
            echo -e "\n${CYAN}Analysis Summary:${NC}"
            head -n 20 reports/analysis.md
        fi
    else
        log_error "Analysis failed"
        exit 1
    fi
}

generate_fixtures() {
    log_step "Step 2: Generating Fixtures (conftest.py)"
    
    if python3 src/ai_engine/fixture_generator.py; then
        log_success "Fixture generation complete"
        
        if [ -f "tests/conftest.py" ]; then
            log_info "Generated fixtures: tests/conftest.py"
        fi
    else
        log_error "Fixture generation failed"
        exit 1
    fi
}

validate_fixtures() {
    log_step "Step 3: Validating Fixtures"

    if python3 src/ai_engine/test_validator.py conftest \
        --conftest-path tests/conftest.py \
        --best-practices-path test_templates/test_best_practices.md; then
        log_success "Fixture validation passed"
    else
        log_error "Fixture validation failed"
        log_info "See reports/validation_conftest.json for details"
        exit 1
    fi
}

generate_tests() {
    log_step "Step 4: Generating Test Scenarios"
    
    if python3 src/ai_engine/test_generator.py; then
        log_success "Test generation complete"
        
        TEST_COUNT=$(find tests/generated -name "test_*.py" 2>/dev/null | wc -l | tr -d ' ')
        log_info "Generated $TEST_COUNT test file(s)"
    else
        log_error "Test generation failed"
        exit 1
    fi
}

validate_tests() {
    log_step "Step 5: Validating Generated Tests"

    if python3 src/ai_engine/test_validator.py tests \
        --tests-dir tests/generated \
        --conftest-path tests/conftest.py; then
        log_success "Test validation passed"
    else
        log_error "Test validation failed"
        log_info "See reports/validation_tests.json for details"
        exit 1
    fi
}

run_tests() {
    log_step "Step 6: Executing Tests"
    
    if pytest tests/generated/ \
        --html=reports/html/report.html \
        --self-contained-html \
        --json-report \
        --json-report-file=reports/pytest-report.json \
        -v; then
        log_success "All tests passed!"
        TEST_STATUS="PASSED"
    else
        log_warning "Some tests failed (expected for bug detection)"
        TEST_STATUS="FAILED"
    fi
}

run_self_healing() {
    log_step "Step 7: Iterative Self-Healing"
    
    if python3 src/ai_engine/self_healer.py; then
        log_success "Self-healing complete"
        
        if [ -f "reports/healing_analysis.json" ]; then
            log_info "Healing analysis saved: reports/healing_analysis.json"
            
            python3 << EOF
import json
try:
    with open('reports/healing_analysis.json', 'r') as f:
        data = json.load(f)
    
    healed = len(data.get('successfully_healed', []))
    defects = len(data.get('actual_defects', []))
    max_attempts = len(data.get('max_attempts_exceeded', []))
    
    print(f"\n${CYAN}Healing Summary:${NC}")
    print(f"  • Successfully healed: ${GREEN}{healed}${NC}")
    print(f"  • Actual defects found: ${YELLOW}{defects}${NC}")
    print(f"  • Max attempts exceeded: ${RED}{max_attempts}${NC}")
except Exception as e:
    print(f"Could not parse healing analysis: {e}")
EOF
        fi
    else
        log_error "Self-healing failed"
        exit 1
    fi
}

check_commit() {
    log_step "Step 8: Checking Commit Conditions"
    
    if python3 src/ai_engine/commit_controller.py; then
        COMMIT_ALLOWED=$(python3 src/ai_engine/commit_controller.py 2>&1 | grep -o "commit_allowed=[a-z]*" | cut -d= -f2)
        
        if [ "$COMMIT_ALLOWED" = "true" ]; then
            log_success "Commit is ALLOWED"
            log_info "Only actual defects remain (or all tests passed)"
        else
            log_warning "Commit is BLOCKED"
            log_info "Unhealed test errors still exist"
        fi
    else
        log_warning "Commit is BLOCKED"
        log_info "Reports will still be generated for investigation"
        COMMIT_ALLOWED="false"
    fi
}

generate_reports() {
    log_step "Step 9: Generating Final Reports"
    
    if python3 src/ai_engine/report_summarizer.py; then
        log_success "Reports generated"
        
        log_info "Generated reports:"
        [ -f "reports/html/report.html" ] && echo "  • reports/html/report.html"
        [ -f "reports/healing_analysis.json" ] && echo "  • reports/healing_analysis.json"
        [ -f "reports/BUGS.md" ] && echo "  • reports/BUGS.md"
        
        LATEST_SUMMARY=$(ls -t reports/summaries/summary_*.md 2>/dev/null | head -1)
        if [ -n "$LATEST_SUMMARY" ]; then
            echo "  • $LATEST_SUMMARY"
            
            echo -e "\n${CYAN}Summary Preview:${NC}"
            head -n 30 "$LATEST_SUMMARY"
        fi
    else
        log_error "Report generation failed"
        exit 1
    fi
}

display_final_summary() {
    log_step "Workflow Complete!"
    
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           AI Test Automation - Final Summary          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}\n"
    
    if [ -f "reports/pytest-report.json" ]; then
        python3 << EOF
import json
try:
    with open('reports/pytest-report.json', 'r') as f:
        data = json.load(f)
    
    summary = data.get('summary', {})
    total = summary.get('total', 0)
    passed = summary.get('passed', 0)
    failed = summary.get('failed', 0)
    
    print(f"${CYAN}Test Results:${NC}")
    print(f"  Total:  {total}")
    print(f"  Passed: ${GREEN}{passed}${NC}")
    print(f"  Failed: ${RED}{failed}${NC}")
except:
    pass
EOF
    fi
    
    if [ -f "reports/healing_analysis.json" ]; then
        python3 << EOF
import json
try:
    with open('reports/healing_analysis.json', 'r') as f:
        data = json.load(f)
    
    healed = len(data.get('successfully_healed', []))
    defects = len(data.get('actual_defects', []))
    
    print(f"\n${CYAN}Healing Results:${NC}")
    print(f"  Healed:  ${GREEN}{healed}${NC}")
    print(f"  Defects: ${YELLOW}{defects}${NC}")
    
    if defects > 0:
        print(f"\n${YELLOW}⚠ Potential bugs detected! See reports/BUGS.md for details${NC}")
except:
    pass
EOF
    fi
    
    echo -e "\n${CYAN}Reports Location:${NC}"
    echo "  • HTML Report:    reports/html/report.html"
    echo "  • Bug Report:     reports/BUGS.md"
    echo "  • Latest Summary: $(ls -t reports/summaries/summary_*.md 2>/dev/null | head -1)"
    
    if [ "$COMMIT_ALLOWED" = "false" ]; then
        echo -e "\n${YELLOW}⚠ Workflow completed with blocked commit${NC}"
        echo -e "${YELLOW}  Review reports above and fix issues before committing${NC}\n"
    else
        echo -e "\n${GREEN}✓ Workflow completed successfully!${NC}\n"
    fi
}

main() {
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                                                           ║"
    echo "║        AI Test Automation - Full Workflow Runner         ║"
    echo "║                                                           ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"
    
    log_info "Workflow started at $(date '+%Y-%m-%d %H:%M:%S')"
    
    check_prerequisites
    start_api
    run_analyzer
    generate_fixtures
    validate_fixtures
    generate_tests
    validate_tests
    run_tests
    run_self_healing
    check_commit
    generate_reports
    display_final_summary
    
    if [ "$COMMIT_ALLOWED" = "false" ]; then
        exit 1
    else
        exit 0
    fi
}

main
