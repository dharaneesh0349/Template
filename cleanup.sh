#!/usr/bin/env bash
# ============================================================
#  CloudStack Template Automation — Cleanup & Reset Script
#  Repo:    https://github.com/dharaneesh0349/Template
#  Usage:   ./cleanup.sh [--all]
#           --all : Also removes SQLite/Postgres database files
# ============================================================

set -uo pipefail

# ── Colours ────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

log()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()     { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()   { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
banner() { echo -e "\n${BOLD}${CYAN}$*${RESET}\n"; }

PURGE_DATA=false
if [[ "${1:-}" == "--all" || "${1:-}" == "-a" || "${1:-}" == "--purge-data" ]]; then
    PURGE_DATA=true
fi

# Detect container runtime
CONTAINER_RUNTIME="docker"
if ! command -v docker &>/dev/null; then
    if command -v podman &>/dev/null; then
        CONTAINER_RUNTIME="podman"
    else
        echo -e "${RED}[ERROR] Neither docker nor podman found.${RESET}" >&2
        exit 1
    fi
fi

# Detect compose command
COMPOSE_CMD=""
if $CONTAINER_RUNTIME compose version &>/dev/null; then
    COMPOSE_CMD="$CONTAINER_RUNTIME compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
elif command -v podman-compose &>/dev/null; then
    COMPOSE_CMD="podman-compose"
fi

IMAGE="dharaneesh5/template:latest"
IMAGE_BASE="dharaneesh5/template"

banner "🧹 Starting CloudStack Template Automation Cleanup..."

# ── 1. Stop and remove docker compose stack ─────────────────
if [[ -n "$COMPOSE_CMD" ]] && [[ -f "docker-compose.yml" ]]; then
    log "Stopping docker-compose services..."
    $COMPOSE_CMD -f docker-compose.yml down --remove-orphans -v 2>/dev/null || true
    ok "Docker-compose stack stopped."
fi

# ── 2. Force remove specific named containers ──────────────
CONTAINERS=(
    "cloudstack-automation-backend"
    "cloudstack-automation-frontend"
    "cloudstack-automation-db"
)

log "Checking and removing standalone containers..."
for c in "${CONTAINERS[@]}"; do
    if $CONTAINER_RUNTIME ps -a --format '{{.Names}}' | grep -Eq "^${c}\$"; then
        log "Removing container: ${c}..."
        $CONTAINER_RUNTIME rm -f "$c" 2>/dev/null || true
        ok "Removed container: ${c}"
    fi
done

# ── 3. Remove template Docker images ───────────────────────
banner "🗑️  Removing Docker images..."

EXISTING_IMAGES=$($CONTAINER_RUNTIME images --format '{{.Repository}}:{{.Tag}} {{.ID}}' | grep -E "^(${IMAGE_BASE}|dharaneesh5/template)" | awk '{print $2}' || true)

if [[ -n "$EXISTING_IMAGES" ]]; then
    for img_id in $EXISTING_IMAGES; do
        log "Removing image ID: ${img_id}..."
        $CONTAINER_RUNTIME rmi -f "$img_id" 2>/dev/null || true
    done
    ok "Template Docker images removed."
else
    log "No '${IMAGE_BASE}' images found."
fi

# ── 4. Prune dangling containers & dangling images ─────────
log "Pruning dangling containers and unused networks..."
$CONTAINER_RUNTIME network prune -f 2>/dev/null || true
$CONTAINER_RUNTIME image prune -f 2>/dev/null || true
ok "Dangling resources pruned."

# ── 5. Optional: Purge local database data ─────────────────
if [[ "$PURGE_DATA" == true ]]; then
    banner "⚠️  Purging local database files..."
    if [[ -d "data" ]]; then
        rm -rf data/*.db data/*.sqlite3 2>/dev/null || true
        ok "Database data purged."
    fi
else
    log "Database records preserved in ./data (use './cleanup.sh --all' to purge data)."
fi

# ── 6. Done ────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║  ✅  CLEANUP COMPLETED SUCCESSFULLY!                 ║${RESET}"
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════════╣${RESET}"
echo -e "${BOLD}${GREEN}║                                                      ║${RESET}"
echo -e "${BOLD}${GREEN}║  To start fresh with the latest image:               ║${RESET}"
echo -e "${BOLD}${GREEN}║     ./start.sh                                       ║${RESET}"
echo -e "${BOLD}${GREEN}║                                                      ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
