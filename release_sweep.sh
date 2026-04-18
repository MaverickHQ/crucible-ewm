#!/usr/bin/env bash
# =============================================================================
# Release Sweep Script - P01 (CLI UX) + P02 (Budget Safety)
# =============================================================================
# Usage:
#   ./release_sweep.sh              # Run normally
#   DRY_RUN=1 ./release_sweep.sh    # Test run without making changes
#   LOG_FILE=/path/to/log.txt ...  # Custom log location
# =============================================================================

set -euo pipefail

# --- Configuration ---
REPO_DIR="${REPO_DIR:-/Users/maverick/executable-world-models}"
LOG_FILE="${LOG_FILE:-/tmp/release_sweep_$(date +%Y%m%d_%H%M%S).log}"
DRY_RUN="${DRY_RUN:-false}"
STEP_CONFIRM="${STEP_CONFIRM:-true}"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Helpers ---
log()   { printf '%s\n' "$*"; }
info()  { log "${BLUE}[INFO]${NC} $*"; }
warn()  { log "${YELLOW}[WARN]${NC} $*"; }
error() { log "${RED}[ERROR]${NC} $*" >&2; }

# Output to both terminal and log file
tee_log() {
    if [[ "$DRY_RUN" == "true" ]]; then
        printf '%s\n' "[DRY-RUN] $*"
    else
        printf '%s\n' "$*" | tee -a "$LOG_FILE"
    fi
}

# Run a command with optional output
run() {
    local desc="$1"
    shift
    local cmd=("$@")
    
    tee_log "▶ $desc"
    tee_log "  Command: ${cmd[*]}"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        tee_log "  [SKIPPED - DRY RUN]"
        return 0
    fi
    
    if "${cmd[@]}" 2>&1 | tee -a "$LOG_FILE"; then
        tee_log "  ${GREEN}✓ Success${NC}"
        return 0
    else
        tee_log "  ${RED}✗ Failed${NC}"
        return 1
    fi
}

# Run a command without terminal output (just log)
run_quiet() {
    local cmd=("$@")
    
    if [[ "$DRY_RUN" == "true" ]]; then
        tee_log "[DRY-RUN] ${cmd[*]}"
        return 0
    fi
    
    if "${cmd[@]}" >> "$LOG_FILE" 2>&1; then
        return 0
    else
        return 1
    fi
}

# Confirmation prompt
confirm() {
    if [[ "$STEP_CONFIRM" != "true" ]]; then
        return 0
    fi
    
    local prompt="$1"
    local response
    read -p "$prompt [y/N] " -n 1 -r response
    echo
    [[ $response =~ ^[Yy]$ ]]
}

# Check if there are staged changes
has_staged_changes() {
    ! git diff --staged --quiet
}

# --- Main ---
main() {
    cd "$REPO_DIR"
    
    tee_log "============================================================================="
    tee_log "RELEASE SWEEP - $(date)"
    tee_log "Repository: $REPO_DIR"
    tee_log "Log file: $LOG_FILE"
    tee_log "Dry run: $DRY_RUN"
    tee_log "============================================================================="
    
    # === PRECHECK ===
    tee_log ""
    tee_log "=============================================="
    tee_log "  PRECHECK"
    tee_log "=============================================="
    run_quiet git status -sb
    run_quiet git log --oneline --decorate -5
    
    # === STEP 1: Update .gitignore ===
    tee_log ""
    tee_log "=============================================="
    tee_log "  STEP 1: Ignore openspec/ (internal workflow)"
    tee_log "=============================================="
    
    if [[ ! -f .gitignore ]]; then
        run "Create .gitignore" touch .gitignore
    fi
    
    if grep -q "^openspec/" .gitignore 2>/dev/null; then
        tee_log "openspec/ already in .gitignore ✓"
    else
        tee_log "Adding openspec/ to .gitignore..."
        printf "\n# Internal spec workflow (not public)\nopenspec/\n" >> .gitignore
        run "Stage .gitignore" git add .gitignore
        tee_log "Added openspec/ to .gitignore ✓"
    fi
    
    run_quiet git status -sb
    
    # === STEP 2: CLI UX Patch ===
    tee_log ""
    tee_log "=============================================="
    tee_log "  STEP 2: Commit CLI UX patch (mode.py + .gitignore)"
    tee_log "=============================================="
    
    # Stage CLI UX files
    run_quiet git add .gitignore services/cli/mode.py
    
    if ! has_staged_changes; then
        tee_log "No staged CLI UX changes to commit."
       tee_log "  - mode.py: $(git diff services/cli/mode.py | head -5)"
    else
        tee_log "Staged files:"
        run_quiet git diff --staged --stat
        
        if confirm "Proceed with lint + test + commit for CLI UX?"; then
            run "Lint" make lint
            run "Test" make test
            
            run "Commit CLI UX patch" git commit -m "cli: UX polish for show outputs + ignore openspec"
            run "Push to origin/main" git push origin main
            run "Create tag v0.7.11-cli" git tag -a v0.7.11-cli -m "CLI UX patch: labeled show output/raw + ignore openspec"
            run "Push tag v0.7.11-cli" git push origin v0.7.11-cli
            
            tee_log "${GREEN}✓ CLI UX patch released as v0.7.11-cli${NC}"
        else
            tee_log "Skipped CLI UX commit."
            run_quiet git reset HEAD .gitignore services/cli/mode.py
        fi
    fi
    tee_log ""
    
    # === STEP 3: Budget Safety Core (R02) ===
    tee_log "=============================================="
    tee_log "  STEP 3: Commit R02 (budget safety core)"
    tee_log "=============================================="
    
    # Stage all files EXCEPT openspec/
    run_quiet git add -A -- ':!openspec/'
    run_quiet git reset -q -- openspec 2>/dev/null || true
    
    if ! has_staged_changes; then
        tee_log "No staged R02 changes to commit (or only openspec which is ignored)."
    else
        tee_log "Staged files:"
        run_quiet git diff --staged --stat
        
        if confirm "Proceed with lint + test + commit for R02 budget safety?"; then
            run "Lint" make lint
            run "Test" make test
            
            run "Commit R02 budget safety" git commit -m "p02: enforce budgets in critical execution path"
            run "Push to origin/main" git push origin main
            run "Create tag v0.7.12-budget-safety" git tag -a v0.7.12-budget-safety -m "P02: budget enforcement in critical execution path"
            run "Push tag v0.7.12-budget-safety" git push origin v0.7.12-budget-safety
            
            tee_log "${GREEN}✓ R02 released as v0.7.12-budget-safety${NC}"
        else
            tee_log "Skipped R02 commit."
            run_quiet git reset HEAD
        fi
    fi
    tee_log ""
    
    # === VERIFY ===
    tee_log "=============================================="
    tee_log "  VERIFY"
    tee_log "=============================================="
    
    tee_log "Checking tags..."
    run_quiet git show --no-patch --decorate v0.7.11-cli 2>/dev/null || tee_log "Tag v0.7.11-cli not found"
    run_quiet git show --no-patch --decorate v0.7.12-budget-safety 2>/dev/null || tee_log "Tag v0.7.12-budget-safety not found"
    
    tee_log ""
    run_quiet git ls-remote --tags origin v0.7.11-cli
    run_quiet git ls-remote --tags origin v0.7.12-budget-safety
    
    tee_log ""
    run_quiet git status -sb
    
    # === DONE ===
    tee_log ""
    tee_log "============================================================================="
    tee_log "${GREEN}DONE${NC}"
    tee_log "Log: $LOG_FILE"
    tee_log "============================================================================="
}

# Trap for cleanup on error
trap 'error "Script failed at line $LINENO"' ERR

# Run main
main "$@"
