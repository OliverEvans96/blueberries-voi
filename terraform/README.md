# Terraform (GitHub Actions secrets)

Mirrors the [personal-website](https://github.com/OliverEvans96/personal-website) pattern: SOPS-encrypted values in [`secrets/`](../secrets/) sync to GitHub Actions secrets via Terraform — no manual pasting in the GitHub UI.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) `>= 1.5`
- [SOPS](https://github.com/getsops/sops) and **OpenPGP** configured per [secrets/README.md](../secrets/README.md)
- `secrets/secrets.enc.yaml` exists and decrypts with your key

## Configure

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — never commit terraform.tfvars
```

Set `enable_github_actions = true` and the target `github_owner` / `github_repository`.

If you run `terraform apply` without `terraform.tfvars`, `enable_github_actions` stays **false** (the default). Terraform will only refresh the SOPS data source and outputs — **no GitHub Actions secrets are created or updated**. Copy the example file before your first real apply.

## Apply

The GitHub provider needs a PAT when syncing Actions secrets:

```bash
export GPG_TTY=$(tty)
cd "$(dirname "$0")"
terraform init
GITHUB_TOKEN=ghp_xxx terraform apply
```

With `enable_github_actions = true`, Terraform creates/updates repository secret **`PERSONAL_WEBSITE_DISPATCH_PAT`** from SOPS. CI workflows in `packaging/github-workflows/` consume that secret for `repository_dispatch` to personal-website (docs and studio releases).

## Workflow packaging (agent protocol)

Agents edit canonical workflows under [`packaging/github-workflows/`](../packaging/github-workflows/) only. After merging packaging changes, a human runs:

```bash
./scripts/sync-github-workflows.sh
```

GitHub Actions does **not** run symlinked workflow files — live `.github/workflows/` must be real copies.

## Secret rotation

See [secrets/README.md](../secrets/README.md). After updating `secrets/secrets.enc.yaml`, run `terraform apply` again to push the new value to GitHub.
