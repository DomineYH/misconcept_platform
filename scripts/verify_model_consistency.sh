#!/bin/bash

# Model Consistency Verification Script
# Verifies that GPT-3.5 references have been removed and Responses API is consistently used

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "========================================"
echo "Model Consistency Verification"
echo "========================================"
echo ""

# Color codes for output
RED='\033[0:31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Check 1: GPT-3.5 references (should be minimal/none except in historical docs)
echo "1. Checking for GPT-3.5 references..."
GPT35_REFS=$(grep -r "gpt-3\.5\|GPT-3\.5" \
    --exclude-dir=.git \
    --exclude-dir=.venv \
    --exclude-dir=__pycache__ \
    --exclude-dir=node_modules \
    --exclude-dir=backups \
    --exclude-dir=logs \
    --exclude="*.pyc" \
    --exclude="*.db" \
    --exclude="*.db-*" \
    --exclude="verify_model_consistency.sh" \
    . | grep -v "NOT supported\|미지원\|incompatible\|limitation" || true)

if [ -n "$GPT35_REFS" ]; then
    echo -e "${RED}✗ Found GPT-3.5 references (excluding 'not supported' mentions):${NC}"
    echo "$GPT35_REFS"
    echo ""
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✓ No problematic GPT-3.5 references found${NC}"
    echo ""
fi

# Check 2: Verify src/constants.py exists and has correct models
echo "2. Checking src/constants.py..."
if [ -f "src/constants.py" ]; then
    if grep -q "SUPPORTED_MODELS" src/constants.py; then
        if grep -q "gpt-3.5" src/constants.py; then
            echo -e "${RED}✗ src/constants.py contains gpt-3.5${NC}"
            ERRORS=$((ERRORS + 1))
        else
            echo -e "${GREEN}✓ src/constants.py exists and excludes GPT-3.5${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ src/constants.py exists but missing SUPPORTED_MODELS${NC}"
    fi
else
    echo -e "${RED}✗ src/constants.py not found${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 3: Verify Responses API usage in service files
echo "3. Checking Responses API usage in services..."
SERVICES=("src/services/student_bot.py" "src/services/tutor_bot.py" "src/services/analyzer.py")
for service in "${SERVICES[@]}"; do
    if [ -f "$service" ]; then
        if grep -q "responses\.create" "$service" && grep -q "max_output_tokens" "$service"; then
            echo -e "${GREEN}✓ $service uses Responses API${NC}"
        else
            echo -e "${RED}✗ $service may not use Responses API correctly${NC}"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo -e "${RED}✗ $service not found${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done
echo ""

# Check 4: Verify UI template uses correct models
echo "4. Checking admin UI templates..."
if [ -f "src/templates/admin/scenarios.html" ]; then
    if grep -q "gpt-3.5" src/templates/admin/scenarios.html; then
        echo -e "${RED}✗ Admin UI still contains gpt-3.5 options${NC}"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}✓ Admin UI excludes GPT-3.5${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Admin UI template not found${NC}"
fi
echo ""

# Check 5: Verify documentation consistency
echo "5. Checking documentation consistency..."
DOCS=("README.md" "docs/deployment.md" "docs/gpt-5-migration.md" ".env.example")
DOC_ERRORS=0
for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        # Check for problematic GPT-3.5 recommendations (exclude "not supported" mentions)
        if grep -i "gpt-3.5" "$doc" | grep -qv "NOT supported\|미지원\|incompatible\|limitation"; then
            echo -e "${RED}✗ $doc contains GPT-3.5 recommendations${NC}"
            DOC_ERRORS=$((DOC_ERRORS + 1))
        fi
    fi
done

if [ $DOC_ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ Documentation consistent (GPT-3.5 only mentioned as 'not supported')${NC}"
else
    ERRORS=$((ERRORS + DOC_ERRORS))
fi
echo ""

# Summary
echo "========================================"
echo "Verification Summary"
echo "========================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed! Model consistency verified.${NC}"
    exit 0
else
    echo -e "${RED}✗ Found $ERRORS error(s). Please review and fix.${NC}"
    exit 1
fi
