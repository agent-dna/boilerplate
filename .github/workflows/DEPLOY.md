# Installer deploy workflow

`deploy-installers.yml` publishes `try.sh` and `try.ps1` to the AgentDNA
server, to a deploy path per environment. The installers are published as they
are in the repository: they are the same for every environment, clone the
`main` branch, and do not set the AgentDNA environment. The wizard takes that
from `AGENTDNA_ENV` in the shell or `.env` (default `test-prod`).

## Environments and triggers

| Environment | Published when | Deploy path secret |
|-------------|----------------|--------------------|
| `dev` | Pull request **merged** into `develop` | `VM_DEPLOY_PATH_DEV` |
| `test-prod` | Pull request **merged** into `main` | `VM_DEPLOY_PATH_TEST_PROD` |

- A pull request closed without merging publishes nothing.
- Direct pushes and tag pushes do not publish.
- **Manual run:** Actions tab, *Deploy AgentDNA Installers*, *Run workflow*,
  then select `develop` (publishes dev) or `main` (publishes test-prod). Any
  other branch fails in the *Select environment* step.
- Publishes for the same branch run one at a time; dev and test-prod can run
  in parallel.

## Steps

1. **Select environment:** maps the pull request's base branch (or the branch
   of a manual run) to the environment, and picks the commit: the merge commit
   for a pull request, the branch head for a manual run.
2. **Checkout** that commit.
3. **Check installers:** `sh -n try.sh` (shell syntax).
4. **Deploy:** copies the two files to a per-run temporary folder on the
   server, then installs them (mode `0644`) into the environment's deploy
   path.

## Configuration

### Repository secrets

*Settings*, *Secrets and variables*, *Actions*:

| Secret | Value |
|--------|-------|
| `VM_HOST` | Server hostname or IP address |
| `VM_USER` | SSH user |
| `VM_PASSWORD` | SSH password of that user |
| `VM_DEPLOY_PATH_DEV` | Folder served as the dev installer URL |
| `VM_DEPLOY_PATH_TEST_PROD` | Folder served as the test-prod installer URL |

`VM_DEPLOY_PATH_DEV` and `VM_DEPLOY_PATH_TEST_PROD` replace the former
`VM_DEPLOY_PATH`. The deploy path is chosen in a shell step, so a missing
secret fails the run instead of publishing to the other environment's folder.

### Branches

The `develop` branch must exist on GitHub for the dev trigger (pull requests
merged into it publish the dev installers):

```bash
git checkout main
git checkout -b develop
git push -u origin develop
```

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| Workflow does not run after a merge | The pull request targeted a branch other than `develop` or `main`. |
| *Select environment* fails with `Installers are published from develop (dev) or main (test-prod)` | A manual run on another branch. Select `develop` or `main`. |
| `No deploy path secret for dev` (or `test-prod`) | Add `VM_DEPLOY_PATH_DEV` / `VM_DEPLOY_PATH_TEST_PROD`. |

## Adding an environment

1. Add it to `ENVIRONMENTS` in `wizard/environments.py`.
2. If it gets its own installer location: map its branch in the *Select
   environment* step, add its deploy path secret in the *Deploy installers*
   step of `deploy-installers.yml`, and add the branch to
   `on.pull_request.branches`.
