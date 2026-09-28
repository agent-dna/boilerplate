"""AgentDNA environments and their service URLs.

The environment is selected by AGENTDNA_ENV (default "test-prod"). The installer
sets it, and the wizard saves it to .env, where agent.py and mcp_server.py read
it. AGENTDNA_PROVENANCE_URL and AGENTDNA_ADMIN_SERVER_URL, when set, override
the environment's value for that service.
"""
import os
from dataclasses import dataclass

ENV_VAR = "AGENTDNA_ENV"
DEFAULT_ENVIRONMENT = "test-prod"

PROVENANCE_URL_ENV = "AGENTDNA_PROVENANCE_URL"
ADMIN_SERVER_URL_ENV = "AGENTDNA_ADMIN_SERVER_URL"


@dataclass(frozen=True)
class Environment:
    provenance_url: str
    admin_server_url: str
    dashboard_url: str


# To add an environment, add an entry here and to the installer workflow
# (.github/workflows/deploy-installers.yml).
ENVIRONMENTS = {
    "dev": Environment(
        provenance_url="https://chain-connector-2-dev.rubix.net",
        admin_server_url="https://agentdna-admin-dev.agentdna.io",
        dashboard_url="https://dashboard-dev.agentdna.io",
    ),
    "test-prod": Environment(
        provenance_url="https://chain-connector-2.rubix.net",
        admin_server_url="https://agentdna-admin.agentdna.io",
        dashboard_url="https://dashboard.agentdna.io",
    ),
}


def validate(name: str) -> str:
    """Return name if it is a known environment, else raise ValueError."""
    if name not in ENVIRONMENTS:
        raise ValueError(f"unknown {ENV_VAR} {name!r}; expected one of: {', '.join(ENVIRONMENTS)}")
    return name


def current_name() -> str:
    """The selected environment: AGENTDNA_ENV, or the default when unset or empty."""
    return validate(_env(ENV_VAR) or DEFAULT_ENVIRONMENT)


def current() -> Environment:
    """The selected environment's URLs."""
    return ENVIRONMENTS[current_name()]


def provenance_url() -> str:
    """AGENTDNA_PROVENANCE_URL if set, else the environment's provenance layer."""
    return _env(PROVENANCE_URL_ENV) or current().provenance_url


def admin_server_url() -> str:
    """AGENTDNA_ADMIN_SERVER_URL if set, else the environment's admin server."""
    return _env(ADMIN_SERVER_URL_ENV) or current().admin_server_url


def intent_url(tx_id: str) -> str:
    """Dashboard page of an audited workflow, by its Provenance Layer transaction ID."""
    return f"{current().dashboard_url}/intents/{tx_id}"


def _env(name: str) -> str:
    # Empty counts as unset, so a blank line copied from .env.sample does not
    # replace the environment's value with "".
    return (os.getenv(name) or "").strip()
