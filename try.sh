#!/bin/sh

set -eu

REPO_URL="https://github.com/agent-dna/boilerplate.git"
PROJECT_NAME="boilerplate"
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
# Determine the current working directory.
#
# The installer always works from wherever the developer invoked it.
# -----------------------------------------------------------------------------

CURRENT_DIR="$(pwd)"

# -----------------------------------------------------------------------------
# Detect an existing local AgentDNA project.
#
# Only wizard/__main__.py is used as the local-project marker.
#
# Local mode:
#   Use the current directory.
#
# Remote mode:
#   Clone the latest stable release into:
#
#       <current-directory>/boilerplate
# -----------------------------------------------------------------------------

if [ -f "${CURRENT_DIR}/wizard/__main__.py" ]; then

    LOCAL_PROJECT="true"
    PROJECT_DIR="${CURRENT_DIR}"

    log "Existing AgentDNA project detected."
    log "Using local project: ${PROJECT_DIR}"

else

    LOCAL_PROJECT="false"
    PROJECT_DIR="${CURRENT_DIR}/${PROJECT_NAME}"

    log "No local AgentDNA project detected."

fi

# -----------------------------------------------------------------------------
# Check Python
# -----------------------------------------------------------------------------

if ! command_exists "$PYTHON"; then
    fail "Python 3.10 or newer is required, but '${PYTHON}' was not found."
fi

PYTHON_VERSION="$("$PYTHON" --version 2>&1)"
log "Using ${PYTHON_VERSION}"

PYTHON_MAJOR="$(
    "$PYTHON" -c 'import sys; print(sys.version_info[0])'
)"

PYTHON_MINOR="$(
    "$PYTHON" -c 'import sys; print(sys.version_info[1])'
)"

if [ "$PYTHON_MAJOR" -lt 3 ] ||
   { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    fail "Python 3.10 or newer is required."
fi

# -----------------------------------------------------------------------------
# Local project
#
# No GitHub access, no tag lookup, and no clone.
# -----------------------------------------------------------------------------

if [ "$LOCAL_PROJECT" = "true" ]; then

    cd "$PROJECT_DIR"

else

    # -------------------------------------------------------------------------
    # Remote installation
    #
    # Find the latest stable Git tag.
    #
    # Stable:
    #   v0.1.0
    #   0.1.0
    #   v1.2.3
    #
    # Not stable:
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

    if [ -z "$VERSION" ]; then
        fail "No stable AgentDNA release was found."
    fi

    log "Latest stable release: ${VERSION}"

    # -------------------------------------------------------------------------
    # Do not overwrite an existing directory.
    # -------------------------------------------------------------------------

    if [ -e "$PROJECT_DIR" ]; then
        fail "Installation directory already exists: ${PROJECT_DIR}"
    fi

    # -------------------------------------------------------------------------
    # Clone into the current working directory.
    # -------------------------------------------------------------------------

    log "Downloading AgentDNA into:"
    log "${PROJECT_DIR}"

    git clone \
        --depth 1 \
        --branch "$VERSION" \
        --single-branch \
        "$REPO_URL" \
        "$PROJECT_DIR"

    cd "$PROJECT_DIR"

    # -------------------------------------------------------------------------
    # Validate cloned project.
    # -------------------------------------------------------------------------

    if [ ! -f "wizard/__main__.py" ]; then
        fail "Invalid AgentDNA release: wizard/__main__.py not found."
    fi

fi

# -----------------------------------------------------------------------------
# Validate project
# -----------------------------------------------------------------------------

if [ ! -f "pyproject.toml" ]; then
    fail "pyproject.toml was not found."
fi

if [ ! -f "wizard/__main__.py" ]; then
    fail "wizard/__main__.py was not found."
fi

if [ ! -f "agent.py" ]; then
    fail "agent.py was not found."
fi

if [ ! -f "mcp_server.py" ]; then
    fail "mcp_server.py was not found."
fi

# -----------------------------------------------------------------------------
# Install uv if required
# -----------------------------------------------------------------------------

if command_exists uv; then

    log "uv is already installed."

else

    log "Installing uv..."

    if ! command_exists curl; then
        fail "curl is required to install uv."
    fi

    curl -LsSf https://astral.sh/uv/install.sh | sh

    # uv normally installs into one of these locations.
    export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"

    if ! command_exists uv; then
        fail "Failed to install uv."
    fi

fi

# -----------------------------------------------------------------------------
# Create virtual environment
# -----------------------------------------------------------------------------

VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"

if [ -d "$VENV_DIR" ]; then

    log "Using existing virtual environment."

else

    log "Creating virtual environment..."

    uv venv \
        "$VENV_DIR" \
        --python "$PYTHON"
fi

if [ ! -x "$PYTHON_BIN" ]; then
    fail "Virtual environment Python was not created."
fi

# -----------------------------------------------------------------------------
# Install base dependencies
# -----------------------------------------------------------------------------

log "Installing dependencies..."

uv pip install \
    --python "$PYTHON_BIN" \
    -r pyproject.toml

# -----------------------------------------------------------------------------
# Start setup wizard
# -----------------------------------------------------------------------------

log "Starting AgentDNA setup wizard..."

cd "$PROJECT_DIR"

export AGENTDNA_TRY_MODE="1"

if [ -r /dev/tty ]; then
    exec "$PYTHON_BIN" -m wizard < /dev/tty
else
    fail "No interactive terminal detected."
fi
