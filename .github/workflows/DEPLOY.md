# Installer deploy workflow

`deploy-installers.yml` publishes `try.sh` and `try.ps1` to the AgentDNA
server, one copy per environment. Each copy has its environment and git branch
filled in, so the installer a developer downloads decides which environment
their setup targets and which branch it clones.

## Environments and triggers

| Environment | Published when | Installer clones | Deploy path secret |
|-------------|----------------|------------------|--------------------|
| `dev` | Pull request **merged** into `develop` | `develop` | `VM_DEPLOY_PATH_DEV` |
| `test-prod` | Pull request **merged** into `main` | `main` | `VM_DEPLOY_PATH_TEST_PROD` |

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
3. **Fill in environment and branch:** the installers in the repository
   contain two placeholders:

   ```sh
   AGENTDNA_BRANCH="__AGENTDNA_BRANCH__"
   AGENTDNA_ENV="${AGENTDNA_ENV:-__AGENTDNA_ENV__}"
   ```

   `sed` writes copies with the branch and environment filled in. The step
   fails if a placeholder is left, and checks the shell syntax of `try.sh`.
4. **Deploy:** copies the two files to a per-run temporary folder on the
   server, then installs them (mode `0644`) into the environment's deploy
   path.

An installer run straight from the repository, without publishing, still has
the placeholders. It then passes no environment to the wizard, which keeps the
`AGENTDNA_ENV` saved in `.env` (test-prod if none), and clones `main` if it has
to clone.

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

The `develop` branch must exist on GitHub, both for the dev trigger and for
the dev installer to clone it:

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
| `Placeholders left in the published installers` | A placeholder in `try.sh` / `try.ps1` was renamed or removed. Keep `__AGENTDNA_BRANCH__` and `__AGENTDNA_ENV__` as shown above. |
| `No deploy path secret for dev` (or `test-prod`) | Add `VM_DEPLOY_PATH_DEV` / `VM_DEPLOY_PATH_TEST_PROD`. |
| Installer fails with `Could not clone the 'develop' branch` | The `develop` branch does not exist on GitHub. |

## Adding an environment

1. Add it to `ENVIRONMENTS` in `wizard/environments.py`.
2. Map its branch in the *Select environment* step and add its deploy path
   secret in the *Deploy installers* step of `deploy-installers.yml`.
3. Add the branch to `on.pull_request.branches`.
