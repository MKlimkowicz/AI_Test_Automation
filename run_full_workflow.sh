#!/bin/bash

# AI Test Automation - Full Workflow Runner
# This script runs the complete test automation workflow from analysis to reporting

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Function to print colored messages
print_step() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}▶ $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    print_step "Checking Prerequisites"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    print_success "Python 3 found: $(python3 --version)"
    
    # Check OPENAI_API_KEY
    if [ -z "$OPENAI_API_KEY" ]; then
        print_error "OPENAI_API_KEY environment variable is not set"
        print_info "Set it with: export OPENAI_API_KEY='your-key-here'"
        exit 1
    fi
    print_success "OPENAI_API_KEY is set"
    
    # Check if required Python packages are installed
    if ! python3 -c "import flask" 2>/dev/null; then
        print_warning "Flask not found. Installing dependencies..."
        pip3 install -r requirements.txt
    fi
    print_success "Required packages are installed"
}

# Function to start the Flask API in background
start_api() {
    print_step "Starting Sample API Server"
    
    # Kill any existing Flask processes on port 5000
    lsof -ti:5000 | xargs kill -9 2>/dev/null || true
    
    # Start Flask API in background
    python3 app/sample_api.py > /tmp/flask_api.log 2>&1 &
    API_PID=$!
    
    # Wait for API to be ready
    print_info "Waiting for API to start..."
    sleep 3
    
    # Check if API is running
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        print_success "API is running (PID: $API_PID)"
        echo $API_PID > /tmp/flask_api.pid
    else
        print_error "Failed to start API"
        cat /tmp/flask_api.log
        exit 1
    fi
}

# Function to stop the Flask API
stop_api() {
    if [ -f /tmp/flask_api.pid ]; then
        API_PID=$(cat /tmp/flask_api.pid)
        if ps -p $API_PID > /dev/null 2>&1; then
            print_info "Stopping API (PID: $API_PID)..."
            kill $API_PID 2>/dev/null || true
            rm /tmp/flask_api.pid
            print_success "API stopped"
        fi
    fi
}

# Trap to ensure API is stopped on script exit
trap stop_api EXIT

# Function to run analyzer
run_analyzer() {
    print_step "Step 1: Analyzing Application Code & Documentation"
    
    if python3 src/ai_engine/analyzer.py; then
        print_success "Analysis complete"
        
        # Show what was analyzed
        if [ -f "reports/code_analysis.md" ]; then
            print_info "Analysis report generated: reports/code_analysis.md"
            echo -e "\n${CYAN}Analysis Summary:${NC}"
            head -n 20 reports/code_analysis.md
        fi
    else
        print_error "Analysis failed"
        exit 1
    fi
}

# Function to generate tests
generate_tests() {
    print_step "Step 2: Generating Test Scenarios"
    
    if python3 src/ai_engine/test_generator.py; then
        print_success "Test generation complete"
        
        # Count generated tests
        TEST_COUNT=$(find tests/generated -name "test_*.py" 2>/dev/null | wc -l | tr -d ' ')
        print_info "Generated $TEST_COUNT test file(s)"
    else
        print_error "Test generation failed"
        exit 1
    fi
}

# Function to run tests
run_tests() {
    print_step "Step 3: Executing Tests"
    
    # Run pytest with JSON report
    if pytest tests/generated/ \
        --html=reports/html/report.html \
        --self-contained-html \
        --json-report \
        --json-report-file=reports/pytest-report.json \
        -v; then
        print_success "All tests passed!"
        TEST_STATUS="PASSED"
    else
        print_warning "Some tests failed (expected for bug detection)"
        TEST_STATUS="FAILED"
    fi
}

# Function to run self-healing
run_self_healing() {
    print_step "Step 4: Iterative Self-Healing"
    
    if python3 src/ai_engine/self_healer.py; then
        print_success "Self-healing complete"
        
        # Show healing summary
        if [ -f "reports/healing_analysis.json" ]; then
            print_info "Healing analysis saved: reports/healing_analysis.json"
            
            # Extract key metrics using Python
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
        print_error "Self-healing failed"
        exit 1
    fi
}

# Function to check commit conditions
check_commit() {
    print_step "Step 5: Checking Commit Conditions"
    
    if python3 src/ai_engine/commit_controller.py; then
        COMMIT_ALLOWED=$(python3 src/ai_engine/commit_controller.py 2>&1 | grep -o "commit_allowed=[a-z]*" | cut -d= -f2)
        
        if [ "$COMMIT_ALLOWED" = "true" ]; then
            print_success "Commit is ALLOWED"
            print_info "Only actual defects remain (or all tests passed)"
        else
            print_warning "Commit is BLOCKED"
            print_info "Unhealed test errors still exist"
        fi
    else
        print_warning "Commit is BLOCKED"
        print_info "Reports will still be generated for investigation"
        COMMIT_ALLOWED="false"
    fi
}

# Function to generate reports
generate_reports() {
    print_step "Step 6: Generating Final Reports"
    
    if python3 src/ai_engine/report_summarizer.py; then
        print_success "Reports generated"
        
        # List generated reports
        print_info "Generated reports:"
        [ -f "reports/html/report.html" ] && echo "  • reports/html/report.html"
        [ -f "reports/healing_analysis.json" ] && echo "  • reports/healing_analysis.json"
        [ -f "reports/BUGS.md" ] && echo "  • reports/BUGS.md"
        
        # Find latest summary
        LATEST_SUMMARY=$(ls -t reports/summaries/summary_*.md 2>/dev/null | head -1)
        if [ -n "$LATEST_SUMMARY" ]; then
            echo "  • $LATEST_SUMMARY"
            
            # Display summary preview
            echo -e "\n${CYAN}Summary Preview:${NC}"
            head -n 30 "$LATEST_SUMMARY"
        fi
    else
        print_error "Report generation failed"
        exit 1
    fi
}

# Function to display final summary
display_final_summary() {
    print_step "Workflow Complete!"
    
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║           AI Test Automation - Final Summary          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}\n"
    
    # Test results
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
    
    # Healing results
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
    
    # Reports location
    echo -e "\n${CYAN}Reports Location:${NC}"
    echo "  • HTML Report:    reports/html/report.html"
    echo "  • Bug Report:     reports/BUGS.md"
    echo "  • Latest Summary: $(ls -t reports/summaries/summary_*.md 2>/dev/null | head -1)"
    
    # Check commit status and display appropriate message
    if [ "$COMMIT_ALLOWED" = "false" ]; then
        echo -e "\n${YELLOW}⚠ Workflow completed with blocked commit${NC}"
        echo -e "${YELLOW}  Review reports above and fix issues before committing${NC}\n"
    else
        echo -e "\n${GREEN}✓ Workflow completed successfully!${NC}\n"
    fi
}

# Main execution
main() {
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                                                           ║"
    echo "║        AI Test Automation - Full Workflow Runner         ║"
    echo "║                                                           ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}\n"
    
    # Run workflow steps
    check_prerequisites
    start_api
    run_analyzer
    generate_tests
    run_tests
    run_self_healing
    check_commit
    generate_reports
    display_final_summary
    
    # Exit with appropriate code based on commit status
    # This allows CI/CD to detect failures while still generating reports
    if [ "$COMMIT_ALLOWED" = "false" ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main function
main

