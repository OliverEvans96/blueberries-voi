# Secrets (SOPS + OpenPGP)

Terraform reads [`secrets.enc.yaml`](./secrets.enc.yaml) via the [SOPS Terraform provider](https://registry.terraform.io/providers/carlpett/sops/latest). This repo uses **OpenPGP only** (no age).

## One-time setup

1. Ensure a GPG secret key is available to `gpg` and SOPS (e.g. `gpg --list-secret-keys`).
2. Get your **40-character** fingerprint:

   ```bash
   gpg --list-secret-keys --with-fingerprint
   ```

3. Put that fingerprint in [`.sops.yaml`](../.sops.yaml) under `creation_rules[].pgp` (replace the placeholder if needed).

4. Create the encrypted file from the template:

   ```bash
   cp secrets/secrets.template.yaml secrets/secrets.enc.yaml
   sops secrets/secrets.enc.yaml
   ```

   Fill in real values in the editor SOPS opens, then save. The file on disk stays encrypted.

5. Commit `secrets/secrets.enc.yaml` once encrypted so other machines can run `terraform plan` after importing your private key.

## Terraform apply

From `terraform/`, with `terraform.tfvars` filled in and `secrets/secrets.enc.yaml` present:

```bash
export GPG_TTY=$(tty)   # if gpg-agent prompts in terminal
cd terraform && terraform init && terraform apply
```

`GITHUB_TOKEN` (PAT with repo + Actions secrets) is required when `enable_github_actions = true`. Pass it as an environment variable for `terraform apply` as described in [terraform/README.md](../terraform/README.md).

## Secret rotation

When rotating **`PERSONAL_WEBSITE_DISPATCH_PAT`**:

1. Create a replacement PAT with the same repository scope (`OliverEvans96/personal-website`, Contents: Read).
2. Edit the encrypted file: `sops secrets/secrets.enc.yaml`
3. Commit the updated `secrets.enc.yaml`.
4. Run `terraform apply` with `enable_github_actions = true` to sync the new value to GitHub Actions secrets.
5. Revoke the old PAT after confirming dispatch workflows succeed.

## Local inspection (optional)

```bash
sops exec-env ./secrets/secrets.enc.yaml 'echo PAT length=${#PERSONAL_WEBSITE_DISPATCH_PAT}'
```

Never print the token itself or commit plaintext secrets.
