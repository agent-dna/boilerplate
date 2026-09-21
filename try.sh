#!/usr/bin/env bash

set -euo pipefail

REPO_URL="https://github.com/agent-dna/boilerplate.git"
INSTALL_DIR="${HOME}/.agentdna"
PYTHON="${TRY_AGENTDNA_PYTHON:-python3}"

log() {
    printf '\n[AgentDNA] %s\n' "$1"
}

fail() {
    printf '\n[AgentDNA] ERROR: %s\n' "$1" >&2
    exit 1
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# -----------------------------------------------------------------------------
# Determine whether we are running from an existing AgentDNA project.
#
# This intentionally checks ONLY wizard/__main__.py.
# -----------------------------------------------------------------------------

if [[ -f "./wizard/__main__.py" ]]; then

    LOCAL_PROJECT=true
    PROJECT_DIR="$(pwd)"

    log "Existing AgentDNA project detected."
    log "Using local project: ${PROJECT_DIR}"

else

    LOCAL_PROJECT=false
    PROJECT_DIR=""

fi

# -----------------------------------------------------------------------------
# Check Python
# -----------------------------------------------------------------------------

if ! command_exists "$PYTHON"; then
    fail "Python 3.10 or newer is required, but '$PYTHON' was not found."
fi

PYTHON_MAJOR="$(
    "$PYTHON" -c 'import sys; print(sys.version_info.major)'
)"

PYTHON_MINOR="$(
    "$PYTHON" -c 'import sys; print(sys.version_info.minor)'
)"

if (( PYTHON_MAJOR < 3 || (PYTHON_MAJOR == 3 && PYTHON_MINOR < 10) )); then
    fail "Python 3.10 or newer is required."
fi

log "Using Python $("$PYTHON" --version 2>&1)"

# -----------------------------------------------------------------------------
# Local project
#
# No Git operations whatsoever.
# -----------------------------------------------------------------------------

if [[ "$LOCAL_PROJECT" == true ]]; then

    cd "$PROJECT_DIR"

else

    # -------------------------------------------------------------------------
    # Remote installation
    #
    # Find the latest stable Git tag.
    #
    # Accepted:
    #   v0.1.0
    #   0.1.0
    #   v1.2.3
    #
    # Rejected:
    #   v0.1.0-alpha
    #   v0.1.0-beta
    #   v0.1.0-rc1
    #   v0.1.0beta
    #   v0.1.0alpha
    # -------------------------------------------------------------------------

    if ! command_exists git; then
        fail "Git is required for installing AgentDNA."
    fi

    log "Finding latest stable AgentDNA release..."

    VERSION="$(
        git ls-remote \
            --tags \
            --refs \
            --sort='-v:refname' \
            "$REPO_URL" |
        awk -F/ '
            $3 ~ /^v?[0-9]+\.[0-9]+\.[0-9]+$/ {
                print $3
                exit
            }
        '
    )"

    if [[ -z "$VERSION" ]]; then
        fail "No stable AgentDNA release was found."
    fi

    log "Latest stable release: ${VERSION}"

    # -------------------------------------------------------------------------
    # Prepare installation directory.
    # -------------------------------------------------------------------------

    if [[ -e "$INSTALL_DIR" ]]; then

        if [[ -n "$(find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
            log "Removing existing AgentDNA installation..."
            rm -rf -- "$INSTALL_DIR"
        fi

    fi

    mkdir -p "$(dirname "$INSTALL_DIR")"

    # -------------------------------------------------------------------------
    # Clone the selected stable release.
    # -------------------------------------------------------------------------

    log "Downloading AgentDNA..."

    git clone \
        --depth 1 \
        --branch "$VERSION" \
        --single-branch \
        "$REPO_URL" \
        "$INSTALL_DIR"

    PROJECT_DIR="$INSTALL_DIR"

    cd "$PROJECT_DIR"

    # -------------------------------------------------------------------------
    # Validate the cloned project.
    # -------------------------------------------------------------------------

    [[ -f "wizard/__main__.py" ]] || \
        fail "Invalid AgentDNA release: wizard/__main__.py not found."

fi

# -----------------------------------------------------------------------------
# Validate project
# -----------------------------------------------------------------------------

[[ -f "pyproject.toml" ]] || \
    fail "pyproject.toml was not found."

[[ -f "wizard/__main__.py" ]] || \
    fail "wizard/__main__.py was not found."

[[ -f "agent.py" ]] || \
    fail "agent.py was not found."

[[ -f "mcp_server.py" ]] || \
    fail "mcp_server.py was not found."

# -----------------------------------------------------------------------------
# Install uv if required
# -----------------------------------------------------------------------------

if command_exists uv; then

    log "uv is already installed."

else

    log "Installing uv..."

    curl -LsSf https://astral.sh/uv/install.sh | sh

    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

    command_exists uv || \
        fail "Failed to install uv."

fi

# -----------------------------------------------------------------------------
# Create virtual environment
# -----------------------------------------------------------------------------

VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"

if [[ -d "$VENV_DIR" ]]; then

    log "Using existing virtual environment."

else

    log "Creating virtual environment..."

    uv venv \
        "$VENV_DIR" \
        --python "$PYTHON"
fi

[[ -x "$PYTHON_BIN" ]] || \
    fail "Virtual environment Python was not created."

# -----------------------------------------------------------------------------
# Install base dependencies
# -----------------------------------------------------------------------------

log "Installing dependencies..."

uv pip install \
    --python "$PYTHON_BIN" \
    -r pyproject.toml

# -----------------------------------------------------------------------------
# Start wizard
# -----------------------------------------------------------------------------

log "Starting AgentDNA setup wizard..."

exec "$PYTHON_BIN" -m wizard