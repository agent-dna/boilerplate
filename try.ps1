$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/agent-dna/boilerplate.git"
$ProjectName = "boilerplate"

$Python = if ($env:TRY_AGENTDNA_PYTHON) {
    $env:TRY_AGENTDNA_PYTHON
}
else {
    "python"
}

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

$AgentDnaBranch = "__AGENTDNA_BRANCH__"
$AgentDnaEnv = if ($env:AGENTDNA_ENV) {
    $env:AGENTDNA_ENV
}
else {
    "__AGENTDNA_ENV__"
}

if ($AgentDnaBranch -like "__*__") {
    $AgentDnaBranch = "main"
}
if ($AgentDnaEnv -like "__*__") {
    $AgentDnaEnv = $null
}

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
# Local mode:
#   Use the current directory.
#
# Remote mode:
#   Clone the environment's branch into:
#
#       <current-directory>\boilerplate
# -----------------------------------------------------------------------------

$LocalWizard = Join-Path $CurrentDir "wizard\__main__.py"

if (Test-Path -LiteralPath $LocalWizard -PathType Leaf) {
    $LocalProject = $true
    $ProjectDir = $CurrentDir
}
else {
    $LocalProject = $false
    $ProjectDir = Join-Path $CurrentDir $ProjectName
}

# -----------------------------------------------------------------------------
# Check Python (3.10 or newer)
# -----------------------------------------------------------------------------

if (-not (Test-CommandExists $Python)) {
    exit 1  # Python not found
}

$PythonMajor = & $Python -c "import sys; print(sys.version_info[0])"
$PythonMinor = & $Python -c "import sys; print(sys.version_info[1])"

if (
    [int]$PythonMajor -lt 3 -or
    (
        [int]$PythonMajor -eq 3 -and
        [int]$PythonMinor -lt 10
    )
) {
    exit 1  # Python older than 3.10
}

# -----------------------------------------------------------------------------
# Local project
#
# No GitHub access and no clone.
# -----------------------------------------------------------------------------

if ($LocalProject) {

    Set-Location $ProjectDir

}
else {

    # -------------------------------------------------------------------------
    # Remote installation
    #
    # Clone the environment's branch: develop for dev, main for test-prod.
    # -------------------------------------------------------------------------

    if (-not (Test-CommandExists "git")) {
        exit 1  # git not found
    }

    # Do not overwrite an existing directory.
    if (Test-Path -LiteralPath $ProjectDir) {
        exit 1  # installation directory already exists
    }

    # Clone into the current working directory.
    & git clone `
        --depth 1 `
        --branch $AgentDnaBranch `
        --single-branch `
        $RepoUrl `
        $ProjectDir

    if ($LASTEXITCODE -ne 0) {
        exit 1  # clone of the environment's branch failed
    }

    Set-Location $ProjectDir

    # The environment's branch must be the one checked out.
    $CheckedOutBranch = (& git rev-parse --abbrev-ref HEAD | Out-String).Trim()

    if ($CheckedOutBranch -ne $AgentDnaBranch) {
        exit 1  # wrong branch checked out
    }

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

if (-not (Test-Path -LiteralPath $VenvDir -PathType Container)) {

    & uv venv `
        $VenvDir `
        --python $Python

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

# Pass the environment to the wizard only when there is one (published copy
# or shell), so a value already saved in .env is not overridden. The wizard
# saves it to .env, where the agent reads it.
if ($AgentDnaEnv) {
    $env:AGENTDNA_ENV = $AgentDnaEnv
}

& $PythonBin -m wizard
$WizardExitCode = $LASTEXITCODE

if ($WizardExitCode -ne 0) {
    exit $WizardExitCode
}
