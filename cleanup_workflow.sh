#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

log_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

log_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                                                           ║"
echo "║        AI Test Automation - Cleanup Script               ║"
echo "║                                                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}\n"

log_info "Cleaning up workflow output files..."

if [ -d "reports/html" ]; then
    rm -rf reports/html/*
    log_success "Cleaned reports/html/"
fi

if [ -d "reports/summaries" ]; then
    rm -rf reports/summaries/*
    log_success "Cleaned reports/summaries/"
fi

if [ -f "reports/analysis.md" ]; then
    rm -f reports/analysis.md
    log_success "Removed reports/analysis.md"
fi

if [ -f "reports/pytest-report.json" ]; then
    rm -f reports/pytest-report.json
    log_success "Removed reports/pytest-report.json"
fi

if [ -f "reports/healing_analysis.json" ]; then
    rm -f reports/healing_analysis.json
    log_success "Removed reports/healing_analysis.json"
fi

if [ -f "reports/BUGS.md" ]; then
    rm -f reports/BUGS.md
    log_success "Removed reports/BUGS.md"
fi

if [ -f "reports/app_metadata.json" ]; then
    rm -f reports/app_metadata.json
    log_success "Removed reports/app_metadata.json"
fi

if [ -f "reports/validation_conftest.json" ]; then
    rm -f reports/validation_conftest.json
    log_success "Removed reports/validation_conftest.json"
fi

if [ -f "reports/validation_tests.json" ]; then
    rm -f reports/validation_tests.json
    log_success "Removed reports/validation_tests.json"
fi

if [ -d "tests/generated" ]; then
    rm -rf tests/generated/*
    log_success "Cleaned tests/generated/"
fi

if [ -f "logs/workflow.log" ]; then
    rm -f logs/workflow.log
    log_success "Removed logs/workflow.log"
fi

if [ -f "/tmp/flask_api.pid" ]; then
    API_PID=$(cat /tmp/flask_api.pid)
    if ps -p $API_PID > /dev/null 2>&1; then
        kill $API_PID 2>/dev/null || true
        log_warning "Stopped running API (PID: $API_PID)"
    fi
    rm -f /tmp/flask_api.pid
fi

if [ -f "/tmp/flask_api.log" ]; then
    rm -f /tmp/flask_api.log
    log_success "Removed /tmp/flask_api.log"
fi

echo -e "\n${GREEN}✓ Cleanup complete!${NC}\n"

