#!/usr/bin/env bash
# install.sh — Bootstrap script for context-trio
#
# Usage:
#   curl -sL <url>/install.sh | bash
#   # or
#   bash install.sh [--name my-project]
#
# Idempotent: safe to re-run without overwriting existing files.

set -euo pipefail

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[info]${NC}  $*"; }
ok()    { echo -e "${GREEN}[ok]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
err()   { echo -e "${RED}[error]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
PROJECT_NAME=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --name|-n)
            PROJECT_NAME="$2"
            shift 2
            ;;
        *)
            err "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$PROJECT_NAME" ]]; then
    PROJECT_NAME="$(basename "$(pwd)")"
fi

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------
info "Checking prerequisites..."

if ! command -v python3 &>/dev/null; then
    err "Python 3 is required but not found."
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || { [[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -lt 12 ]]; }; then
    err "Python 3.12+ is required (found $PYTHON_VERSION)."
    exit 1
fi
ok "Python $PYTHON_VERSION"

if ! command -v git &>/dev/null; then
    err "git is required but not found."
    exit 1
fi
ok "git $(git --version | awk '{print $3}')"

# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------
info "Creating directory structure..."

for dir in docs docs/logs src tests; do
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        ok "Created $dir/"
    else
        warn "$dir/ already exists, skipping."
    fi
done

# ---------------------------------------------------------------------------
# CONTEXT.json
# ---------------------------------------------------------------------------
CONTEXT_FILE="docs/CONTEXT.json"
if [[ ! -f "$CONTEXT_FILE" ]]; then
    NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    cat > "$CONTEXT_FILE" << CTXEOF
{
  "project_name": "$PROJECT_NAME",
  "global_phase": "planning",
  "current_task": null,
  "task_queue": [],
  "completed_tasks": [],
  "active_constraints": {
    "language": ["Python 3.12+", "TypeScript 5.5+"],
    "style": {"python": "black", "typescript": "prettier"},
    "testing": {"framework": ["pytest", "jest"], "min_coverage": 80},
    "typing": "strict"
  },
  "reasoning_logs": [],
  "known_issues": [],
  "last_updated_by": "architect",
  "last_updated_at": "$NOW"
}
CTXEOF
    ok "Created $CONTEXT_FILE"
else
    warn "$CONTEXT_FILE already exists, skipping."
fi

# ---------------------------------------------------------------------------
# Copy CLAUDE.md and AGENTS.md
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for mdfile in CLAUDE.md AGENTS.md; do
    if [[ ! -f "$mdfile" ]]; then
        if [[ -f "$SCRIPT_DIR/$mdfile" ]]; then
            cp "$SCRIPT_DIR/$mdfile" "$mdfile"
            ok "Copied $mdfile"
        else
            warn "$mdfile source not found in $SCRIPT_DIR, skipping."
        fi
    else
        warn "$mdfile already exists, skipping."
    fi
done

# ---------------------------------------------------------------------------
# Document templates
# ---------------------------------------------------------------------------
create_template() {
    local filepath="$1"
    local content="$2"
    if [[ ! -f "$filepath" ]]; then
        echo "$content" > "$filepath"
        ok "Created $filepath"
    else
        warn "$filepath already exists, skipping."
    fi
}

create_template "docs/PRD.md" "# Product Requirements Document — $PROJECT_NAME

> TODO: Define requirements here.
> Follow REQ-NNN numbering convention."

create_template "docs/ARCHITECTURE.md" "# Architecture — $PROJECT_NAME

> TODO: Define system architecture here."

create_template "docs/DECISIONS.md" "# Architecture Decision Records — $PROJECT_NAME

> Record architectural decisions in ADR format."

create_template "docs/CHANGELOG.md" "# Changelog — $PROJECT_NAME

All notable changes to this project will be documented in this file."

# ---------------------------------------------------------------------------
# .gitignore
# ---------------------------------------------------------------------------
if [[ ! -f ".gitignore" ]]; then
    cat > ".gitignore" << 'GIEOF'
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.venv/
venv/
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.DS_Store
.env
.env.local
docs/logs/*.json
GIEOF
    ok "Created .gitignore"
else
    warn ".gitignore already exists, skipping."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
info "================================================"
ok "  context-trio initialized for '$PROJECT_NAME'"
info "================================================"
echo ""
info "Next steps:"
info "  1. pip install -e .          (if pyproject.toml exists)"
info "  2. trio status               (check project state)"
info "  3. trio plan \"<request>\"     (start planning)"
echo ""
