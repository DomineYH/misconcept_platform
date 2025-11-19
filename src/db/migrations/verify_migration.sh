#!/bin/bash
# Generic migration verification script
# Usage: ./verify_migration.sh <migration_number> [db_path]
# Example: ./verify_migration.sh 006 dialogue_sim.db

set -e  # Exit on error

# ============================================
# Configuration
# ============================================
MIGRATION_NUM="${1}"
DB_PATH="${2:-dialogue_sim.db}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================
# Helper functions
# ============================================
print_header() {
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}==========================================${NC}"
}

print_step() {
    echo -e "\n${YELLOW}[$1]${NC} $2"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

check_column() {
    local table=$1
    local column=$2
    local expected_type=$3

    if sqlite3 "$DB_PATH" "PRAGMA table_info($table);" | \
        grep -q "$column|$expected_type"; then
        print_success "Column '$column' exists (type: $expected_type)"
        return 0
    else
        print_error "Column '$column' missing or wrong type"
        return 1
    fi
}

# ============================================
# Validation
# ============================================
if [ -z "$MIGRATION_NUM" ]; then
    echo "Usage: $0 <migration_number> [db_path]"
    echo "Example: $0 006 dialogue_sim.db"
    exit 1
fi

if [ ! -f "$DB_PATH" ]; then
    print_error "Database not found: $DB_PATH"
    exit 1
fi

MIGRATION_FILE="$SCRIPT_DIR/$(printf '%03d' "$MIGRATION_NUM")_*.sql"
if ! ls $MIGRATION_FILE 1> /dev/null 2>&1; then
    print_error "Migration file not found: $MIGRATION_FILE"
    exit 1
fi

# ============================================
# Main verification
# ============================================
print_header "Migration $MIGRATION_NUM Verification"
echo "Database: $DB_PATH"
echo "Migration: $(basename $MIGRATION_FILE)"

# ============================================
# Migration-specific checks
# ============================================
case "$MIGRATION_NUM" in
    "006")
        print_step "1/4" "Verifying scenario table structure..."

        # Check override columns
        FAILED=0
        check_column "scenario" "chat_model" "VARCHAR(50)" || FAILED=1
        check_column "scenario" "chat_temperature" "REAL" || FAILED=1
        check_column "scenario" "tutor_enabled" "BOOLEAN" || FAILED=1
        check_column "scenario" "tutor_intervention_threshold" \
            "INTEGER" || FAILED=1

        if [ $FAILED -eq 1 ]; then
            print_error "Column verification failed"
            exit 1
        fi

        print_step "2/4" "Verifying CHECK constraints..."

        # Test temperature constraint (valid)
        if sqlite3 "$DB_PATH" \
            "UPDATE scenario SET chat_temperature = 1.0 \
            WHERE id = 1;" 2>&1; then
            print_success "Valid temperature accepted (1.0)"
        else
            print_error "Valid temperature rejected"
            FAILED=1
        fi

        # Test temperature constraint (invalid)
        if sqlite3 "$DB_PATH" \
            "UPDATE scenario SET chat_temperature = 3.0 \
            WHERE id = 1;" 2>&1 | grep -q "constraint"; then
            print_success "Invalid temperature rejected (3.0 > 2.0)"
        else
            print_error "Temperature constraint not working"
            FAILED=1
        fi

        # Reset temperature
        sqlite3 "$DB_PATH" \
            "UPDATE scenario SET chat_temperature = NULL WHERE id = 1;"

        # Test threshold constraint (valid)
        if sqlite3 "$DB_PATH" \
            "UPDATE scenario SET tutor_intervention_threshold = 5 \
            WHERE id = 1;" 2>&1; then
            print_success "Valid threshold accepted (5)"
        else
            print_error "Valid threshold rejected"
            FAILED=1
        fi

        # Test threshold constraint (invalid)
        if sqlite3 "$DB_PATH" \
            "UPDATE scenario SET tutor_intervention_threshold = 15 \
            WHERE id = 1;" 2>&1 | grep -q "constraint"; then
            print_success "Invalid threshold rejected (15 > 10)"
        else
            print_error "Threshold constraint not working"
            FAILED=1
        fi

        # Reset threshold
        sqlite3 "$DB_PATH" \
            "UPDATE scenario SET tutor_intervention_threshold = NULL \
            WHERE id = 1;"

        if [ $FAILED -eq 1 ]; then
            print_error "Constraint verification failed"
            exit 1
        fi

        print_step "3/4" "Verifying indexes..."

        if sqlite3 "$DB_PATH" \
            "SELECT name FROM sqlite_master WHERE type='index' \
            AND tbl_name='scenario';" | \
            grep -q "idx_scenario_framework"; then
            print_success "Index 'idx_scenario_framework' exists"
        else
            print_error "Index 'idx_scenario_framework' missing"
            FAILED=1
        fi

        if sqlite3 "$DB_PATH" \
            "SELECT name FROM sqlite_master WHERE type='index' \
            AND tbl_name='scenario';" | \
            grep -q "idx_scenario_active"; then
            print_success "Index 'idx_scenario_active' exists"
        else
            print_error "Index 'idx_scenario_active' missing"
            FAILED=1
        fi

        if [ $FAILED -eq 1 ]; then
            print_error "Index verification failed"
            exit 1
        fi

        print_step "4/4" "Verifying data integrity..."

        SCENARIO_COUNT=$(sqlite3 "$DB_PATH" \
            "SELECT COUNT(*) FROM scenario;")
        print_success "All $SCENARIO_COUNT scenarios intact"

        # Check that no data was lost
        if [ "$SCENARIO_COUNT" -lt 1 ]; then
            print_error "No scenarios found (data loss?)"
            exit 1
        fi
        ;;

    *)
        print_step "1/1" "Running basic verification..."

        # Basic table existence check
        TABLES=$(sqlite3 "$DB_PATH" \
            "SELECT name FROM sqlite_master WHERE type='table';")
        print_success "Database readable, tables: $(echo $TABLES | wc -w)"

        echo ""
        echo "Note: No migration-specific checks defined for #$MIGRATION_NUM"
        echo "Add case in verify_migration.sh for detailed verification"
        ;;
esac

# ============================================
# Final summary
# ============================================
echo ""
print_header "Migration $MIGRATION_NUM: ✓ PASSED"

exit 0
