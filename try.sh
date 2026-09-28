#!/bin/sh

set -eu

REPO_URL="https://github.com/agent-dna/boilerplate.git"
PROJECT_NAME="boilerplate"
PYTHON="${TRY_AGENTDNA_PYTHON:-python3}"

# -----------------------------------------------------------------------------
# Environment
#
# The two values below are filled in by .github/workflows/deploy-installers.yml
# when the installer is published, one copy per environment:
#
#   dev        clones the develop branch
#   test-prod  clones the main branch
#
# A copy that was not published (run straight from the repository) sets no
# environment: the wizard then uses AGENTDNA_ENV from .env, or test-prod, the
# default. It clones main if it has to clone.
# AGENTDNA_ENV set in the shell takes precedence over the published value.
# -----------------------------------------------------------------------------

AGENTDNA_BRANCH="__AGENTDNA_BRANCH__"
AGENTDNA_ENV="${AGENTDNA_ENV:-__AGENTDNA_ENV__}"

case "$AGENTDNA_BRANCH" in __*__) AGENTDNA_BRANCH="main" ;; esac
case "$AGENTDNA_ENV" in __*__) AGENTDNA_ENV="" ;; esac

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
#   Clone the environment's branch into:
#
#       <current-directory>/boilerplate
# -----------------------------------------------------------------------------

if [ -f "${CURRENT_DIR}/wizard/__main__.py" ]; then
    LOCAL_PROJECT="true"
    PROJECT_DIR="${CURRENT_DIR}"
else
    LOCAL_PROJECT="false"
    PROJECT_DIR="${CURRENT_DIR}/${PROJECT_NAME}"
fi

# -----------------------------------------------------------------------------
# Check Python (3.10 or newer)
# -----------------------------------------------------------------------------

if ! command_exists "$PYTHON"; then
    exit 1  # Python not found
fi

PYTHON_MAJOR="$(
    "$PYTHON" -c 'import sys; print(sys.version_info[0])'
)"

PYTHON_MINOR="$(
    "$PYTHON" -c 'import sys; print(sys.version_info[1])'
)"

if [ "$PYTHON_MAJOR" -lt 3 ] ||
   { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]; }; then
    exit 1  # Python older than 3.10
fi

# -----------------------------------------------------------------------------
# Local project
#
# No GitHub access and no clone.
# -----------------------------------------------------------------------------

if [ "$LOCAL_PROJECT" = "true" ]; then

    cd "$PROJECT_DIR"

else

    # -------------------------------------------------------------------------
    # Remote installation
    #
    # Clone the environment's branch: develop for dev, main for test-prod.
    # -------------------------------------------------------------------------

    if ! command_exists git; then
        exit 1  # git not found
    fi

    # Do not overwrite an existing directory.
    if [ -e "$PROJECT_DIR" ]; then
        exit 1  # installation directory already exists
    fi

    # Clone into the current working directory (set -e stops on failure).
    git clone \
        --depth 1 \
        --branch "$AGENTDNA_BRANCH" \
        --single-branch \
        "$REPO_URL" \
        "$PROJECT_DIR"

    cd "$PROJECT_DIR"

    # The environment's branch must be the one checked out.
    if [ "$(git rev-parse --abbrev-ref HEAD)" != "$AGENTDNA_BRANCH" ]; then
        exit 1  # wrong branch checked out
    fi

    # Validate cloned project.
    if [ ! -f "wizard/__main__.py" ]; then
        exit 1  # invalid AgentDNA project: wizard/__main__.py not found
    fi

fi

# -----------------------------------------------------------------------------
# Validate project
# -----------------------------------------------------------------------------

for required_file in pyproject.toml wizard/__main__.py agent.py mcp_server.py; do
    if [ ! -f "$required_file" ]; then
        exit 1  # required project file missing
    fi
done

# -----------------------------------------------------------------------------
# Install uv if required
# -----------------------------------------------------------------------------

if ! command_exists uv; then

    if ! command_exists curl; then
        exit 1  # curl is required to install uv
    fi

    curl -LsSf https://astral.sh/uv/install.sh | sh

    # uv normally installs into one of these locations.
    export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"

    if ! command_exists uv; then
        exit 1  # uv installation failed
    fi

fi

# -----------------------------------------------------------------------------
# Create virtual environment
# -----------------------------------------------------------------------------

VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON_BIN="${VENV_DIR}/bin/python"

if [ ! -d "$VENV_DIR" ]; then
    uv venv \
        "$VENV_DIR" \
        --python "$PYTHON"
fi

if [ ! -x "$PYTHON_BIN" ]; then
    exit 1  # virtual environment Python was not created
fi

# -----------------------------------------------------------------------------
# Install base dependencies
# -----------------------------------------------------------------------------

uv pip install \
    --python "$PYTHON_BIN" \
    -r pyproject.toml

# -----------------------------------------------------------------------------
# Start setup wizard
# -----------------------------------------------------------------------------

cd "$PROJECT_DIR"

# Pass the environment to the wizard only when there is one (published copy
# or shell), so a value already saved in .env is not overridden. The wizard
# saves it to .env, where the agent reads it.
if [ -n "$AGENTDNA_ENV" ]; then
    export AGENTDNA_ENV
else
    unset AGENTDNA_ENV
fi

if [ ! -r /dev/tty ]; then
    exit 1  # no interactive terminal
fi

exec "$PYTHON_BIN" -m wizard < /dev/tty
