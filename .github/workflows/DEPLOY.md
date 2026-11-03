# Installer deploy workflow

`deploy-installers.yml` publishes `try.sh` and `try.ps1` to the AgentDNA
servers over SSH: each environment has its own VM and deploy path. The
installers are published as they are in the repository: they are the same for every environment, clone the
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
4. **Install sshpass** (`dev` only).
5. **Configure SSH:** selects the environment's VM, user, login method and
   deploy path, writes the SSH key (`test-prod` only) and the pinned VM host
   key, and fails if any of the environment's secrets is missing.
6. **Create target folder** (`mkdir -p`) if it does not exist.
7. **Copy installers** into it with `scp`, then sets them to mode `0644`.

No step uses `sudo`: the SSH user must be able to write to the deploy path
(see *VM prerequisites*).

## Configuration

### 1. Repository secrets

*Settings*, *Secrets and variables*, *Actions*, *New repository secret*:

`dev` (password login):

| Secret | Value |
|--------|-------|
| `VM_HOST` | Dev VM hostname or IP address |
| `VM_USER` | SSH user |
| `VM_PASSWORD` | SSH password of that user |
| `VM_KNOWN_HOSTS` | The dev VM's SSH host key line(s), see step 2 |
| `VM_DEPLOY_PATH_DEV` | Folder served as the dev installer URL |

`test-prod` (key login; password login is disabled on that VM):

| Secret | Value |
|--------|-------|
| `VM_HOST_TEST_PROD` | Test-prod VM hostname or IP address |
| `VM_USER_TEST_PROD` | SSH user on that VM |
| `VM_SSH_KEY_TEST_PROD` | Private key of that user, the full file including the `-----BEGIN`/`-----END` lines; see step 3 |
| `VM_KNOWN_HOSTS_TEST_PROD` | The test-prod VM's SSH host key line(s), see step 2 |
| `VM_DEPLOY_PATH_TEST_PROD` | Folder served as the test-prod installer URL |

The target is chosen in a shell step, so a missing secret fails the run
instead of publishing to the other environment's VM or folder.

`VM_PASSWORD` is passed to `sshpass` through the `SSHPASS` environment
variable and never appears on a command line. The private key is written to
`~/.ssh/deploy_key` (mode 600) on the runner, which is discarded after the
job. GitHub masks secret values in the logs.

### 2. Host keys (`VM_KNOWN_HOSTS`, `VM_KNOWN_HOSTS_TEST_PROD`)

SSH connects only if the VM presents this key (`StrictHostKeyChecking=yes`),
which prevents connecting to an impostor. Do this once per VM, with that VM's
host:

1. From a machine that already trusts the VM, run:

   ```bash
   ssh-keyscan -H <host>
   ```

2. Compare the fingerprint with the one on the VM:

   ```bash
   # on the VM
   ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
   # locally, on the keyscan output
   ssh-keyscan <host> 2>/dev/null | ssh-keygen -lf -
   ```

3. If they match, paste the full `ssh-keyscan -H` output as the secret value.

Update the secret whenever the VM's host keys change (for example after
reinstalling it), otherwise deploys fail with `Host key verification failed`.

### 3. Deploy key (`VM_SSH_KEY_TEST_PROD`)

Use a dedicated key without a passphrase, so it can be revoked on its own:

```bash
ssh-keygen -t ed25519 -N '' -C 'github-deploy boilerplate installers' -f deploy_key
```

1. Append `deploy_key.pub` to `~/.ssh/authorized_keys` of `VM_USER_TEST_PROD`
   on the test-prod VM.
2. Paste the content of `deploy_key` (the private key) as the
   `VM_SSH_KEY_TEST_PROD` secret.
3. Delete the local `deploy_key` file.

To revoke it, remove its line from `authorized_keys`.

### 4. VM prerequisites

On both VMs, the SSH user can create and write the deploy path (the workflow
runs `mkdir -p` on it and copies into it, without `sudo`). If the folder must
live somewhere the user cannot write, create it once and hand it over:

```bash
sudo mkdir -p <deploy path>
sudo chown <SSH user> <deploy path>
```

`dev`: password login allowed for `VM_USER` over SSH
(`PasswordAuthentication yes`, and `PermitRootLogin yes` for `root`, in
`/etc/ssh/sshd_config`).

### 5. Branches

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
| *Configure SSH* fails with `Deploy secrets for <environment> are missing` | One of that environment's secrets is not set (step 1). |
| `Host key verification failed` | The environment's `VM_KNOWN_HOSTS*` secret is wrong or outdated. Regenerate it (step 2). |
| `Permission denied (publickey,password)` on `dev` | Wrong `VM_USER` or `VM_PASSWORD`, or password login disabled on the VM. |
| `Permission denied (publickey)` on `test-prod` | Wrong `VM_USER_TEST_PROD`, or the public key of `VM_SSH_KEY_TEST_PROD` is not in that user's `authorized_keys` (step 3). |
| `Load key ... invalid format` | `VM_SSH_KEY_TEST_PROD` is incomplete. Paste the whole private key file, including the `BEGIN`/`END` lines. |
| `mkdir: cannot create directory` or `scp: ... Permission denied` | The SSH user cannot write to the deploy path (step 4). |

## Adding an environment

1. Add it to `ENVIRONMENTS` in `wizard/environments.py`.
2. If it gets its own installer location: map its branch in the *Select
   environment* step, add a `case` entry with its VM, user, login method,
   host key and deploy path in the *Configure SSH* step of
   `deploy-installers.yml` (and its secrets to that step's `env` block), and
   add the branch to `on.pull_request.branches`.
