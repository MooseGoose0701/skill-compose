#!/bin/bash
# 串行运行所有测试（避免并行死锁）
# 用法: ./scripts/run-tests.sh [unit|e2e|llm|all]

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASSED=0
FAILED=0
SKIPPED=0
RESULTS=()

log_header() {
    echo ""
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}============================================${NC}"
}

log_result() {
    local name="$1" exit_code="$2" duration="$3"
    if [ "$exit_code" -eq 0 ]; then
        RESULTS+=("${GREEN}PASS${NC}  $name  (${duration}s)")
        PASSED=$((PASSED + 1))
    elif [ "$exit_code" -eq 5 ]; then
        # pytest exit code 5 = no tests collected (all skipped)
        RESULTS+=("${YELLOW}SKIP${NC}  $name")
        SKIPPED=$((SKIPPED + 1))
    else
        RESULTS+=("${RED}FAIL${NC}  $name  (exit $exit_code)")
        FAILED=$((FAILED + 1))
    fi
}

run_pytest() {
    local name="$1"
    shift
    log_header "$name"
    local start_time=$(date +%s)
    set +e
    python -u -m pytest "$@" -v --tb=short 2>&1
    local exit_code=$?
    set -e
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    log_result "$name" "$exit_code" "$duration"
}

# ---------------------------------------------------------------------------
# 从 .env 提取 API Key（处理引号）
# ---------------------------------------------------------------------------
extract_key() {
    local key_name="$1"
    grep "^${key_name}=" "$PROJECT_DIR/.env" 2>/dev/null | cut -d'=' -f2- | tr -d "'\""
}

setup_kimi_key() {
    # Prefer already-set env var over .env file
    if [ -n "$MOONSHOT_API_KEY_REAL" ]; then
        echo -e "  Kimi API Key: ${GREEN}found (env)${NC} (${#MOONSHOT_API_KEY_REAL} chars)"
        return 0
    fi
    local key=$(extract_key "MOONSHOT_API_KEY")
    if [ -n "$key" ]; then
        export MOONSHOT_API_KEY_REAL="$key"
        echo -e "  Kimi API Key: ${GREEN}found (.env)${NC} (${#key} chars)"
        return 0
    else
        echo -e "  Kimi API Key: ${YELLOW}not found${NC}"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# 测试套件
# ---------------------------------------------------------------------------

run_unit() {
    run_pytest "Unit Tests" \
        tests/test_api/ tests/test_core/ tests/test_services/
}

run_e2e() {
    run_pytest "E2E Workflow (mock)" \
        tests/test_e2e/test_e2e_workflows.py
}

run_llm() {
    echo ""
    echo -e "${CYAN}Setting up LLM API keys...${NC}"
    if ! setup_kimi_key; then
        echo -e "${YELLOW}Skipping LLM tests (no MOONSHOT_API_KEY in .env)${NC}"
        RESULTS+=("${YELLOW}SKIP${NC}  LLM Tests (no API key)")
        ((SKIPPED++))
        return
    fi

    run_pytest "E2E Real Agent (Kimi 2.5)" \
        tests/test_e2e/test_e2e_agent_real.py

    run_pytest "E2E Published Agent (Kimi 2.5)" \
        tests/test_e2e/test_e2e_published_agent.py

    run_pytest "E2E Compression (Kimi 2.5)" \
        tests/test_e2e/test_e2e_compression_real.py

    run_pytest "E2E Data Analysis (Kimi 2.5)" \
        tests/test_e2e/test_e2e_data_analysis.py::TestDataAnalysisKimiE2E
}

# ---------------------------------------------------------------------------
# 汇总报告
# ---------------------------------------------------------------------------

print_summary() {
    echo ""
    echo -e "${CYAN}============================================${NC}"
    echo -e "${CYAN} Summary${NC}"
    echo -e "${CYAN}============================================${NC}"
    for r in "${RESULTS[@]}"; do
        echo -e "  $r"
    done
    echo ""
    echo -e "  Total: ${GREEN}${PASSED} passed${NC}, ${RED}${FAILED} failed${NC}, ${YELLOW}${SKIPPED} skipped${NC}"
    echo ""

    if [ "$FAILED" -gt 0 ]; then
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

case "${1:-all}" in
    unit|u)
        run_unit
        ;;
    e2e)
        run_e2e
        ;;
    llm|l)
        run_llm
        ;;
    all|a)
        run_unit
        run_e2e
        run_llm
        ;;
    *)
        echo "用法: $0 [unit|e2e|llm|all]"
        echo ""
        echo "命令:"
        echo "  unit, u  - 单元测试 (~394 tests, ~55s)"
        echo "  e2e      - E2E 工作流测试, mock 无 LLM (~168 tests, ~15s)"
        echo "  llm, l   - E2E 真实 LLM 测试, Kimi 2.5 (~72 tests, ~7min)"
        echo "  all, a   - 全部串行运行 (默认)"
        exit 0
        ;;
esac

print_summary
