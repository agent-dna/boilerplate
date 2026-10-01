#!/bin/sh

set -eu

REPO_URL="https://github.com/agent-dna/boilerplate.git"
PROJECT_NAME="boilerplate"

# The project runs on this Python only. uv provides it (downloading it the
# first time); the system Python, whatever its version, is not used.
PYTHON_VERSION="3.12"

# -----------------------------------------------------------------------------
# Options
#
#   --branch <name>   Use this git branch instead of main (for debugging).
#                     A new install clones it; an existing project is switched
#                     to it before the rest of the setup.
#
# Through curl, pass options after "sh -s --":
#
#   curl -fsSL https://try.agentdna.io | sh -s -- --branch develop
# -----------------------------------------------------------------------------

BRANCH=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --branch)
            if [ "$#" -lt 2 ]; then
                exit 1  # --branch needs a value
            fi
            BRANCH="$2"
            shift 2
            ;;
        --branch=*)
            BRANCH="${1#--branch=}"
            shift
            ;;
        *)
            exit 1  # unknown option
            ;;
    esac
done

# A value starting with "-" would be read by git as an option.
case "$BRANCH" in
    -*) exit 1 ;;  # invalid branch name
esac

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
# Local mode, using an existing project without cloning:
#   - the current directory is the project (sh try.sh run inside it), or
#   - <current-directory>/boilerplate is the project (a re-run of
#     curl ... | sh from the folder of an earlier install).
#
# Remote mode:
#   Clone the main branch into:
#
#       <current-directory>/boilerplate
# -----------------------------------------------------------------------------

if [ -f "${CURRENT_DIR}/wizard/__main__.py" ]; then
    LOCAL_PROJECT="true"
    PROJECT_DIR="${CURRENT_DIR}"
elif [ -f "${CURRENT_DIR}/${PROJECT_NAME}/wizard/__main__.py" ]; then
    LOCAL_PROJECT="true"
    PROJECT_DIR="${CURRENT_DIR}/${PROJECT_NAME}"
else
    LOCAL_PROJECT="false"
    PROJECT_DIR="${CURRENT_DIR}/${PROJECT_NAME}"
fi

# -----------------------------------------------------------------------------
# Local project
#
# No GitHub access and no clone.
# -----------------------------------------------------------------------------

if [ "$LOCAL_PROJECT" = "true" ]; then

    cd "$PROJECT_DIR"

    # --branch: switch the existing project to that branch. A local branch of
    # that name is checked out as it is; otherwise it is fetched from GitHub
    # (an installer clone has only main) and created from the remote branch.
    if [ -n "$BRANCH" ]; then

        if ! command_exists git; then
            exit 1  # git not found
        fi

        if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
            git checkout "$BRANCH"
        else
            git fetch --depth 1 origin "$BRANCH"
            git checkout -b "$BRANCH" FETCH_HEAD
        fi

    fi

else

    # -------------------------------------------------------------------------
    # Remote installation
    #
    # Clone the main branch.
    # -------------------------------------------------------------------------

    if ! command_exists git; then
        exit 1  # git not found
    fi

    # Do not overwrite an existing directory that is not the project (an
    # existing project was detected above and is used instead).
    if [ -e "$PROJECT_DIR" ]; then
        exit 1  # installation directory exists and is not an AgentDNA project
    fi

    # Clone into the current working directory (set -e stops on failure).
    # main, or the branch given with --branch.
    git clone \
        --depth 1 \
        --branch "${BRANCH:-main}" \
        --single-branch \
        "$REPO_URL" \
        "$PROJECT_DIR"

    cd "$PROJECT_DIR"

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

# An existing .venv on another Python version (for example one created from
# the system Python by an earlier installer) is replaced.
if [ -d "$VENV_DIR" ] &&
   ! "$PYTHON_BIN" -c "import sys; sys.exit('%d.%d' % sys.version_info[:2] != '${PYTHON_VERSION}')" 2>/dev/null; then
    rm -rf "$VENV_DIR"
fi

# only-managed: use a Python installed by uv, never the system's; uv downloads
# it on first use. (Also understood by older uv versions, unlike
# --managed-python.)
if [ ! -d "$VENV_DIR" ]; then
    uv venv \
        "$VENV_DIR" \
        --python "$PYTHON_VERSION" \
        --python-preference only-managed
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

if [ ! -r /dev/tty ]; then
    exit 1  # no interactive terminal
fi

exec "$PYTHON_BIN" -m wizard < /dev/tty
