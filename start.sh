#!/usr/bin/env bash
# ============================================================
#  CloudStack Template Automation — One-Click Startup Script
#  Repo:    https://github.com/dharaneesh0349/Template
#  Image:   docker.io/dharaneesh5/template:latest
#  Supports: Ubuntu, Debian, RHEL, CentOS, Rocky, Fedora,
#            AlmaLinux, openSUSE, Alpine, Arch Linux
#  Checks Docker / Podman → installs if missing → runs stack
# ============================================================

GITHUB_RAW="https://raw.githubusercontent.com/dharaneesh0349/Template/main"

set -euo pipefail

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
error()  { echo -e "${RED}[ERROR]${RESET} $*" >&2; exit 1; }
banner() { echo -e "\n${BOLD}${CYAN}$*${RESET}\n"; }

# ── Banner ─────────────────────────────────────────────────
clear
cat <<'EOF'
  ██████╗██╗      ██████╗ ██╗   ██╗██████╗ ███████╗████████╗ █████╗  ██████╗██╗  ██╗
 ██╔════╝██║     ██╔═══██╗██║   ██║██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝
 ██║     ██║     ██║   ██║██║   ██║██║  ██║███████╗   ██║   ███████║██║     █████╔╝ 
 ██║     ██║     ██║   ██║██║   ██║██║  ██║╚════██║   ██║   ██╔══██║██║     ██╔═██╗ 
 ╚██████╗███████╗╚██████╔╝╚██████╔╝██████╔╝███████║   ██║   ██║  ██║╚██████╗██║  ██╗
  ╚═════╝╚══════╝ ╚═════╝  ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝
        Template Automation Engine  —  One-Click Launcher
EOF
echo ""

# ── Script directory (works even when called from another path) ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_PORT="${APP_PORT:-8000}"
IMAGE="dharaneesh5/template:latest"
COMPOSE_FILE="docker-compose.yml"

# ── Helper: detect distro ──────────────────────────────────
detect_distro() {
    if [ -f /etc/os-release ]; then
        source /etc/os-release
        echo "${ID,,}"
    elif command -v lsb_release &>/dev/null; then
        lsb_release -si | tr '[:upper:]' '[:lower:]'
    else
        echo "unknown"
    fi
}

# ── Install Docker Engine (Linux) ─────────────────────────
install_docker() {
    local distro
    distro="$(detect_distro)"
    banner "🐳 Docker not found — Installing Docker Engine..."

    case "$distro" in
        ubuntu|debian|linuxmint|pop)
            log "Detected Debian/Ubuntu — using apt-get..."
            sudo apt-get update -qq
            sudo apt-get install -y -qq \
                ca-certificates curl gnupg lsb-release
            sudo install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
                | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
            sudo chmod a+r /etc/apt/keyrings/docker.gpg
            echo \
              "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
               https://download.docker.com/linux/ubuntu \
               $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
              | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
            sudo apt-get update -qq
            sudo apt-get install -y -qq \
                docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;
        centos|rhel|rocky|almalinux|fedora|ol)
            log "Detected RHEL/CentOS/Fedora — using dnf/yum..."
            local PKG_MGR="dnf"
            command -v dnf &>/dev/null || PKG_MGR="yum"
            sudo $PKG_MGR install -y -q yum-utils
            sudo yum-config-manager --add-repo \
                https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null || true
            sudo $PKG_MGR install -y -q \
                docker-ce docker-ce-cli containerd.io \
                docker-buildx-plugin docker-compose-plugin
            ;;
        opensuse*|sles)
            log "Detected openSUSE — using zypper..."
            sudo zypper -q install -y docker docker-compose
            ;;
        arch|manjaro|endeavouros)
            log "Detected Arch Linux — using pacman..."
            sudo pacman -Sy --noconfirm docker docker-compose
            ;;
        alpine)
            log "Detected Alpine Linux — using apk..."
            sudo apk add --no-cache docker docker-compose
            ;;
        *)
            warn "Unknown distro: $distro. Trying convenience script..."
            curl -fsSL https://get.docker.com | sudo sh
            ;;
    esac

    # Enable and start Docker service
    if command -v systemctl &>/dev/null; then
        sudo systemctl enable --now docker 2>/dev/null || true
    fi

    # Add current user to docker group so sudo is not needed later
    if getent group docker &>/dev/null; then
        sudo usermod -aG docker "$USER" 2>/dev/null || true
        warn "Added $USER to 'docker' group. Changes take effect on next login."
        warn "For this session, commands will use sudo automatically."
    fi

    ok "Docker installed successfully."
}

# ── Install Docker Compose plugin (if missing) ─────────────
install_compose() {
    banner "📦 Installing Docker Compose..."
    COMPOSE_VER="v2.29.2"
    COMPOSE_URL="https://github.com/docker/compose/releases/download/${COMPOSE_VER}/docker-compose-$(uname -s)-$(uname -m)"
    sudo mkdir -p /usr/local/lib/docker/cli-plugins
    sudo curl -fsSL "$COMPOSE_URL" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    ok "Docker Compose ${COMPOSE_VER} installed."
}

# ── Determine which container runtime to use ──────────────
CONTAINER_RUNTIME=""
COMPOSE_CMD=""

banner "🔍 Checking Container Runtime..."

# 1. Check Docker
if command -v docker &>/dev/null; then
    # Verify daemon is reachable
    if docker info &>/dev/null 2>&1; then
        CONTAINER_RUNTIME="docker"
        ok "Docker found and running: $(docker --version)"
    else
        warn "Docker binary found but daemon is not running. Starting..."
        sudo systemctl start docker 2>/dev/null || \
            sudo service docker start 2>/dev/null || true
        sleep 2
        if docker info &>/dev/null 2>&1; then
            CONTAINER_RUNTIME="docker"
            ok "Docker daemon started."
        else
            warn "Could not start Docker daemon — will try to reinstall."
        fi
    fi
fi

# 2. Check Podman if Docker unavailable
if [ -z "$CONTAINER_RUNTIME" ] && command -v podman &>/dev/null; then
    CONTAINER_RUNTIME="podman"
    ok "Podman found: $(podman --version)"
fi

# 3. Install Docker if neither is available
if [ -z "$CONTAINER_RUNTIME" ]; then
    warn "Neither Docker nor Podman found."
    install_docker
    # Try again after install
    if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
        CONTAINER_RUNTIME="docker"
        ok "Docker is now ready."
    else
        # After group change, might need newgrp or sudo
        export CONTAINER_RUNTIME="docker"
        warn "Docker installed. Using sudo for this session."
    fi
fi

# ── Resolve Compose command ────────────────────────────────
if [ "$CONTAINER_RUNTIME" = "podman" ]; then
    if command -v podman-compose &>/dev/null; then
        COMPOSE_CMD="podman-compose"
    else
        log "Installing podman-compose..."
        pip3 install --user podman-compose 2>/dev/null || \
            sudo pip3 install podman-compose 2>/dev/null || \
            error "Could not install podman-compose. Please install it manually."
        COMPOSE_CMD="podman-compose"
    fi
    ok "Using: podman-compose"
else
    # Docker — prefer plugin 'docker compose' over standalone
    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        install_compose
        COMPOSE_CMD="docker compose"
    fi
    ok "Using: $COMPOSE_CMD"
fi

# ── Ensure docker-compose.yml exists (download from GitHub if missing) ────
banner "📄 Checking Required Files..."
if [ ! -f "docker-compose.yml" ]; then
    log "docker-compose.yml not found — downloading from GitHub..."
    curl -fsSL "${GITHUB_RAW}/docker-compose.yml" -o docker-compose.yml \
        || error "Failed to download docker-compose.yml from GitHub."
    ok "docker-compose.yml downloaded."
else
    ok "docker-compose.yml found."
fi

# ── Ensure .env exists ─────────────────────────────────────
banner "⚙️  Checking Environment Configuration..."
if [ ! -f ".env" ]; then
    log "Downloading .env.example from GitHub..."
    curl -fsSL "${GITHUB_RAW}/.env.example" -o .env 2>/dev/null || true
    if [ ! -s ".env" ]; then
        # Fallback: create minimal .env
        cat > .env <<ENVEOF
API_HOST=0.0.0.0
API_PORT=${APP_PORT}
API_LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./data/cloudstack_automation.db
ALLOWED_ORIGINS=http://localhost:${APP_PORT},http://127.0.0.1:${APP_PORT}
SECRET_KEY=cloudstack-auto-secret-$(date +%s)
ENVEOF
        ok "Created minimal .env"
    else
        ok "Downloaded .env from GitHub."
    fi
else
    ok ".env file found."
fi

# Ensure data directory exists
mkdir -p data

# ── Pull latest image ──────────────────────────────────────
banner "📥 Pulling latest image from Docker Hub..."
log "Image: ${IMAGE}"
$CONTAINER_RUNTIME pull "$IMAGE" || warn "Pull failed — will use local cache if available."

# ── Stop any existing containers ───────────────────────────
banner "🔄 Stopping any existing containers..."
$COMPOSE_CMD -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
ok "Old containers cleared."

# ── Start the stack ────────────────────────────────────────
banner "🚀 Starting CloudStack Template Automation Stack..."
$COMPOSE_CMD -f "$COMPOSE_FILE" up -d
ok "Stack started."

# ── Wait for backend health check ─────────────────────────
banner "⏳ Waiting for backend to become healthy..."
MAX_WAIT=60
ELAPSED=0
URL="http://localhost:${APP_PORT}/api/health"

until curl -sf "$URL" >/dev/null 2>&1; do
    if [ "$ELAPSED" -ge "$MAX_WAIT" ]; then
        warn "Backend did not respond in ${MAX_WAIT}s — check logs with:"
        echo "  $COMPOSE_CMD logs -f backend"
        break
    fi
    printf "  Waiting... (%ds)\r" "$ELAPSED"
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

if curl -sf "$URL" >/dev/null 2>&1; then
    echo ""
    ok "Backend is healthy! ✅"
fi

# ── Done — Print access info ───────────────────────────────
HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${GREEN}║  🎉  CloudStack Template Automation is RUNNING!      ║${RESET}"
echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════════╣${RESET}"
echo -e "${BOLD}${GREEN}║                                                      ║${RESET}"
echo -e "${BOLD}${GREEN}║  🌐  Web Studio  →  http://localhost:${APP_PORT}            ║${RESET}"
echo -e "${BOLD}${GREEN}║  🌐  Network IP  →  http://${HOST_IP}:${APP_PORT}         ║${RESET}"
echo -e "${BOLD}${GREEN}║                                                      ║${RESET}"
echo -e "${BOLD}${GREEN}║  📋  View Logs:                                      ║${RESET}"
echo -e "${BOLD}${GREEN}║     $COMPOSE_CMD logs -f backend                  ║${RESET}"
echo -e "${BOLD}${GREEN}║                                                      ║${RESET}"
echo -e "${BOLD}${GREEN}║  🛑  Stop Stack:                                     ║${RESET}"
echo -e "${BOLD}${GREEN}║     $COMPOSE_CMD down                             ║${RESET}"
echo -e "${BOLD}${GREEN}║                                                      ║${RESET}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════╝${RESET}"
echo ""
