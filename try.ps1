# -----------------------------------------------------------------------------
# Options
#
#   -Branch <name>   Use this git branch instead of main (for debugging).
#                    A new install clones it; an existing project is switched
#                    to it before the rest of the setup.
#
# Through irm, run the downloaded script as a script block to pass options:
#
#   & ([scriptblock]::Create((irm https://try.agentdna.io))) -Branch develop
# -----------------------------------------------------------------------------

param(
    [string]$Branch = ""
)

$ErrorActionPreference = "Stop"

# A value starting with "-" would be read by git as an option.
if ($Branch.StartsWith("-")) {
    exit 1  # invalid branch name
}

$RepoUrl = "https://github.com/agent-dna/boilerplate.git"
$ProjectName = "boilerplate"

# The project runs on this Python only. uv provides it (downloading it the
# first time); the system Python, whatever its version, is not used.
$PythonVersion = "3.12"

function Test-CommandExists {
    param(
        [string]$Command
    )

    return $null -ne (
        Get-Command $Command -ErrorAction SilentlyContinue
    )
}

# -----------------------------------------------------------------------------
# Determine current working directory.
#
# The installer always works relative to wherever the developer invoked it.
# -----------------------------------------------------------------------------

$CurrentDir = (Get-Location).Path

# -----------------------------------------------------------------------------
# Detect an existing local AgentDNA project.
#
# Only wizard/__main__.py is used as the local-project marker.
#
# Local mode, using an existing project without cloning:
#   - the current directory is the project (.\try.ps1 run inside it), or
#   - <current-directory>\boilerplate is the project (a re-run of
#     irm ... | iex from the folder of an earlier install).
#
# Remote mode:
#   Clone the main branch into:
#
#       <current-directory>\boilerplate
# -----------------------------------------------------------------------------

$LocalWizard = Join-Path $CurrentDir "wizard\__main__.py"
$InstalledWizard = Join-Path (Join-Path $CurrentDir $ProjectName) "wizard\__main__.py"

if (Test-Path -LiteralPath $LocalWizard -PathType Leaf) {
    $LocalProject = $true
    $ProjectDir = $CurrentDir
}
elseif (Test-Path -LiteralPath $InstalledWizard -PathType Leaf) {
    $LocalProject = $true
    $ProjectDir = Join-Path $CurrentDir $ProjectName
}
else {
    $LocalProject = $false
    $ProjectDir = Join-Path $CurrentDir $ProjectName
}

# -----------------------------------------------------------------------------
# Local project
#
# No GitHub access and no clone.
# -----------------------------------------------------------------------------

if ($LocalProject) {

    Set-Location $ProjectDir

    # -Branch: switch the existing project to that branch. A local branch of
    # that name is checked out as it is; otherwise it is fetched from GitHub
    # (an installer clone has only main) and created from the remote branch.
    if ($Branch) {

        if (-not (Test-CommandExists "git")) {
            exit 1  # git not found
        }

        & git show-ref --verify --quiet "refs/heads/$Branch"

        if ($LASTEXITCODE -eq 0) {
            & git checkout $Branch
        }
        else {
            & git fetch --depth 1 origin $Branch

            if ($LASTEXITCODE -ne 0) {
                exit 1  # branch could not be fetched
            }

            & git checkout -b $Branch FETCH_HEAD
        }

        if ($LASTEXITCODE -ne 0) {
            exit 1  # branch checkout failed
        }
    }

}
else {

    # -------------------------------------------------------------------------
    # Remote installation
    #
    # Clone the main branch.
    # -------------------------------------------------------------------------

    if (-not (Test-CommandExists "git")) {
        exit 1  # git not found
    }

    # Do not overwrite an existing directory that is not the project (an
    # existing project was detected above and is used instead).
    if (Test-Path -LiteralPath $ProjectDir) {
        exit 1  # installation directory exists and is not an AgentDNA project
    }

    # Clone into the current working directory: main, or the branch given
    # with -Branch.
    $CloneBranch = if ($Branch) { $Branch } else { "main" }

    & git clone `
        --depth 1 `
        --branch $CloneBranch `
        --single-branch `
        $RepoUrl `
        $ProjectDir

    if ($LASTEXITCODE -ne 0) {
        exit 1  # clone failed
    }

    Set-Location $ProjectDir

    # Validate cloned project.
    if (-not (Test-Path "wizard\__main__.py" -PathType Leaf)) {
        exit 1  # invalid AgentDNA project: wizard/__main__.py not found
    }
}

# -----------------------------------------------------------------------------
# Validate project
# -----------------------------------------------------------------------------

foreach ($RequiredFile in @("pyproject.toml", "wizard\__main__.py", "agent.py", "mcp_server.py")) {
    if (-not (Test-Path $RequiredFile -PathType Leaf)) {
        exit 1  # required project file missing
    }
}

# -----------------------------------------------------------------------------
# Install uv if required
# -----------------------------------------------------------------------------

if (-not (Test-CommandExists "uv")) {

    Invoke-RestMethod `
        -Uri "https://astral.sh/uv/install.ps1" |
        Invoke-Expression

    # uv may have been installed into one of these locations.
    $env:Path = "$HOME\.local\bin;$HOME\.cargo\bin;$env:Path"

    if (-not (Test-CommandExists "uv")) {
        exit 1  # uv installation failed
    }
}

# -----------------------------------------------------------------------------
# Create virtual environment
# -----------------------------------------------------------------------------

$VenvDir = Join-Path $ProjectDir ".venv"
$PythonBin = Join-Path $VenvDir "Scripts\python.exe"

# An existing .venv on another Python version (for example one created from
# the system Python by an earlier installer) is replaced.
if (Test-Path -LiteralPath $VenvDir -PathType Container) {

    $VenvMatches = $false

    if (Test-Path -LiteralPath $PythonBin -PathType Leaf) {
        & $PythonBin -c "import sys; sys.exit('%d.%d' % sys.version_info[:2] != '$PythonVersion')"
        $VenvMatches = ($LASTEXITCODE -eq 0)
    }

    if (-not $VenvMatches) {
        Remove-Item -LiteralPath $VenvDir -Recurse -Force
    }
}

# only-managed: use a Python installed by uv, never the system's; uv downloads
# it on first use. (Also understood by older uv versions, unlike
# --managed-python.)
if (-not (Test-Path -LiteralPath $VenvDir -PathType Container)) {

    & uv venv `
        $VenvDir `
        --python $PythonVersion `
        --python-preference only-managed

    if ($LASTEXITCODE -ne 0) {
        exit 1  # virtual environment creation failed
    }
}

if (-not (Test-Path -LiteralPath $PythonBin -PathType Leaf)) {
    exit 1  # virtual environment Python was not created
}

# -----------------------------------------------------------------------------
# Install base dependencies
# -----------------------------------------------------------------------------

& uv pip install `
    --python $PythonBin `
    -r pyproject.toml

if ($LASTEXITCODE -ne 0) {
    exit 1  # dependency installation failed
}

# -----------------------------------------------------------------------------
# Start setup wizard
# -----------------------------------------------------------------------------

Set-Location $ProjectDir

& $PythonBin -m wizard
$WizardExitCode = $LASTEXITCODE

if ($WizardExitCode -ne 0) {
    exit $WizardExitCode
}
