# Installer deploy workflow

`deploy-installers.yml` publishes `try.sh` and `try.ps1` to the AgentDNA
servers: each environment has its own VM and deploy path. The installers are published as they
are in the repository: they are the same for every environment, clone the
`main` branch, and do not set the AgentDNA environment. The wizard takes that
from `AGENTDNA_ENV` in the shell or `.env` (default `test-prod`).

## Environments and triggers

| Environment | Published when | VM login | Deploy path secret |
|-------------|----------------|----------|--------------------|
| `dev` | Pull request **merged** into `develop` | Password | `VM_DEPLOY_PATH_DEV` |
| `test-prod` | Pull request **merged** into `main` | SSH key | `VM_DEPLOY_PATH_TEST_PROD` |

- A pull request closed without merging publishes nothing.
- Direct pushes and tag pushes do not publish.
- **Manual run (`workflow_dispatch`):** Actions tab, *Deploy AgentDNA
  Installers*, *Run workflow*, then choose the **environment** input (`dev` or
  `test-prod`, default `dev`). The run publishes the installers from the latest
  commit of that environment's branch (`develop` for dev, `main` for
  test-prod), whichever branch is selected in *Use workflow from*. Use it to
  re-publish without a merge, for example after changing a deploy path secret.
- Publishes for the same environment run one at a time, whether started by a
  merge or manually; dev and test-prod can run in parallel.

## Steps

1. **Select environment:** for a merged pull request, maps its base branch to
   the environment and uses the merge commit; for a manual run, takes the
   chosen environment and uses the head of its branch.
2. **Checkout** that commit.
3. **Check installers:** `sh -n try.sh` (shell syntax).
4. **Install sshpass** (dev only, for its password login).
5. **Deploy:** picks the environment's VM, user, credential and deploy path,
   adds the VM's host key to `known_hosts` (and, for test-prod, writes the SSH
   key to a file), copies the two files to a per-run temporary folder on the
   VM, then installs them (mode `0644`) into the deploy path.
6. **Remove SSH key:** deletes the key file, even when an earlier step failed.

## Configuration

### Repository secrets

*Settings*, *Secrets and variables*, *Actions*:

dev VM (password login):

| Secret | Value |
|--------|-------|
| `VM_HOST` | dev VM hostname or IP address |
| `VM_USER` | SSH user |
| `VM_PASSWORD` | SSH password of that user |
| `VM_DEPLOY_PATH_DEV` | Folder served as the dev installer URL |

test-prod VM (key login; password login is disabled on it):

| Secret | Value |
|--------|-------|
| `VM_HOST_TEST_PROD` | test-prod VM hostname or IP address |
| `VM_USER_TEST_PROD` | SSH user |
| `VM_SSH_KEY_TEST_PROD` | Private key of that user, the whole file including the `-----BEGIN ... KEY-----` and `-----END ... KEY-----` lines. It must have no passphrase. |
| `VM_DEPLOY_PATH_TEST_PROD` | Folder served as the test-prod installer URL |

The target is chosen in a shell step, so a missing secret fails the run
instead of publishing to the other environment's VM or folder.

### VM setup

On each VM, the SSH user needs passwordless `sudo` (the deploy runs
`sudo mkdir` and `sudo install` without a terminal). On the test-prod VM, add
the public half of `VM_SSH_KEY_TEST_PROD` to that user's
`~/.ssh/authorized_keys`. A key used only for this deploy is best:

```bash
ssh-keygen -t ed25519 -N "" -C "github-deploy-installers" -f deploy_key
# deploy_key.pub  -> ~/.ssh/authorized_keys of the user on the test-prod VM
# deploy_key      -> secret VM_SSH_KEY_TEST_PROD (then delete the local copy)
```

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
| *Select environment* fails with `Installers are published from develop (dev) or main (test-prod)` | Should not happen with the configured triggers: only pull requests into `develop` or `main` start the workflow. Check `on.pull_request.branches` if the triggers were changed. |
| `Missing deploy secret for dev` (or `test-prod`) | Add the secrets the message lists (see *Repository secrets*). |
| test-prod: `Permission denied (publickey)` | The public key is not in `authorized_keys` of `VM_USER_TEST_PROD`, or `VM_SSH_KEY_TEST_PROD` is not the whole private key file, or the key has a passphrase. |
| `sudo: a terminal is required` / `a password is required` | The SSH user needs passwordless `sudo` on that VM (see *VM setup*). |

## Adding an environment

1. Add it to `ENVIRONMENTS` in `wizard/environments.py`.
2. If it gets its own installer location: map its branch in the *Select
   environment* step, add a `case` entry with its VM, user,
   credential and deploy path secrets in the *Deploy installers* step of
   `deploy-installers.yml`, and add the branch to
   `on.pull_request.branches`.
