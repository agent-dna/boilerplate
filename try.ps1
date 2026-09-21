$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/agent-dna/boilerplate.git"
$InstallDir = Join-Path $HOME ".agentdna"

$Python = if ($env:TRY_AGENTDNA_PYTHON) {
    $env:TRY_AGENTDNA_PYTHON
}
else {
    "python"
}

function Write-AgentDNA {
    param(
        [string]$Message
    )

    Write-Host ""
    Write-Host "[AgentDNA] $Message"
}

function Fail-AgentDNA {
    param(
        [string]$Message
    )

    Write-Error "[AgentDNA] ERROR: $Message"
    exit 1
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
# Determine whether we are running from an existing AgentDNA project.
#
# This intentionally checks ONLY wizard/__main__.py.
# -----------------------------------------------------------------------------

$LocalWizard = Join-Path (Get-Location) "wizard\__main__.py"

if (Test-Path -LiteralPath $LocalWizard) {

    $LocalProject = $true
    $ProjectDir = (Get-Location).Path

    Write-AgentDNA "Existing AgentDNA project detected."
    Write-AgentDNA "Using local project: $ProjectDir"

}
else {

    $LocalProject = $false
    $ProjectDir = $null

}

# -----------------------------------------------------------------------------
# Check Python
# -----------------------------------------------------------------------------

if (-not (Test-CommandExists $Python)) {
    Fail-AgentDNA "Python 3.10 or newer is required, but '$Python' was not found."
}

$PythonMajor = & $Python -c "import sys; print(sys.version_info.major)"
$PythonMinor = & $Python -c "import sys; print(sys.version_info.minor)"

if (
    [int]$PythonMajor -lt 3 -or
    (
        [int]$PythonMajor -eq 3 -and
        [int]$PythonMinor -lt 10
    )
) {
    Fail-AgentDNA "Python 3.10 or newer is required."
}

$PythonVersion = & $Python --version 2>&1

Write-AgentDNA "Using $PythonVersion"

# -----------------------------------------------------------------------------
# Local project
#
# No Git operations whatsoever.
# -----------------------------------------------------------------------------

if ($LocalProject) {

    Set-Location $ProjectDir

}
else {

    # -------------------------------------------------------------------------
    # Remote installation
    #
    # Only stable semantic versions are accepted.
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

    if (-not (Test-CommandExists "git")) {
        Fail-AgentDNA "Git is required for installing AgentDNA."
    }

    Write-AgentDNA "Finding latest stable AgentDNA release..."

    $TagOutput = & git ls-remote `
        --tags `
        --refs `
        --sort="-v:refname" `
        $RepoUrl 2>$null

    if ($LASTEXITCODE -ne 0) {
        Fail-AgentDNA "Could not query GitHub for AgentDNA releases."
    }

    $Version = $null

    foreach ($Line in $TagOutput) {

        if ($Line -match "refs/tags/(v?[0-9]+\.[0-9]+\.[0-9]+)$") {
            $Version = $Matches[1]
            break
        }
    }

    if ([string]::IsNullOrWhiteSpace($Version)) {
        Fail-AgentDNA "No stable AgentDNA release was found."
    }

    Write-AgentDNA "Latest stable release: $Version"

    # -------------------------------------------------------------------------
    # Prepare installation directory.
    # -------------------------------------------------------------------------

    if (Test-Path -LiteralPath $InstallDir) {

        $ExistingItems = Get-ChildItem `
            -LiteralPath $InstallDir `
            -Force `
            -ErrorAction SilentlyContinue

        if ($ExistingItems) {
            Write-AgentDNA "Removing existing AgentDNA installation..."

            Remove-Item `
                -LiteralPath $InstallDir `
                -Recurse `
                -Force
        }
    }

    $ParentDir = Split-Path -Parent $InstallDir

    if ($ParentDir) {
        New-Item `
            -ItemType Directory `
            -Path $ParentDir `
            -Force | Out-Null
    }

    # -------------------------------------------------------------------------
    # Clone stable release.
    # -------------------------------------------------------------------------

    Write-AgentDNA "Downloading AgentDNA..."

    & git clone `
        --depth 1 `
        --branch $Version `
        --single-branch `
        $RepoUrl `
        $InstallDir

    if ($LASTEXITCODE -ne 0) {
        Fail-AgentDNA "Failed to clone AgentDNA."
    }

    $ProjectDir = $InstallDir

    Set-Location $ProjectDir

    # -------------------------------------------------------------------------
    # Validate cloned project.
    # -------------------------------------------------------------------------

    if (-not (Test-Path "wizard\__main__.py")) {
        Fail-AgentDNA "Invalid AgentDNA release: wizard/__main__.py not found."
    }
}

# -----------------------------------------------------------------------------
# Validate project
# -----------------------------------------------------------------------------

if (-not (Test-Path "pyproject.toml")) {
    Fail-AgentDNA "pyproject.toml was not found."
}

if (-not (Test-Path "wizard\__main__.py")) {
    Fail-AgentDNA "wizard/__main__.py was not found."
}

if (-not (Test-Path "agent.py")) {
    Fail-AgentDNA "agent.py was not found."
}

if (-not (Test-Path "mcp_server.py")) {
    Fail-AgentDNA "mcp_server.py was not found."
}

# -----------------------------------------------------------------------------
# Install uv if required
# -----------------------------------------------------------------------------

if (Test-CommandExists "uv") {

    Write-AgentDNA "uv is already installed."

}
else {

    Write-AgentDNA "Installing uv..."

    Invoke-RestMethod `
        -Uri "https://astral.sh/uv/install.ps1" |
        Invoke-Expression

    $env:Path = "$HOME\.local\bin;$HOME\.cargo\bin;$env:Path"

    if (-not (Test-CommandExists "uv")) {
        Fail-AgentDNA "Failed to install uv."
    }
}

# -----------------------------------------------------------------------------
# Create virtual environment
# -----------------------------------------------------------------------------

$VenvDir = Join-Path $ProjectDir ".venv"
$PythonBin = Join-Path $VenvDir "Scripts\python.exe"

if (Test-Path $VenvDir) {

    Write-AgentDNA "Using existing virtual environment."

}
else {

    Write-AgentDNA "Creating virtual environment..."

    & uv venv `
        $VenvDir `
        --python $Python

    if ($LASTEXITCODE -ne 0) {
        Fail-AgentDNA "Failed to create virtual environment."
    }
}

if (-not (Test-Path $PythonBin)) {
    Fail-AgentDNA "Virtual environment Python was not created."
}

# -----------------------------------------------------------------------------
# Install base dependencies
# -----------------------------------------------------------------------------

Write-AgentDNA "Installing dependencies..."

& uv pip install `
    --python $PythonBin `
    -r pyproject.toml

if ($LASTEXITCODE -ne 0) {
    Fail-AgentDNA "Failed to install dependencies."
}

# -----------------------------------------------------------------------------
# Start wizard
# -----------------------------------------------------------------------------

Write-AgentDNA "Starting AgentDNA setup wizard..."

& $PythonBin -m wizard

exit $LASTEXITCODE