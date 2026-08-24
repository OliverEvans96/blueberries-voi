"""T-159 / GH #14 — SOPS + Terraform GitHub Actions secrets scaffold."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SOPS_CONFIG = _REPO_ROOT / ".sops.yaml"
_SECRETS_DIR = _REPO_ROOT / "secrets"
_SECRETS_ENC = _SECRETS_DIR / "secrets.enc.yaml"
_SECRETS_TEMPLATE = _SECRETS_DIR / "secrets.template.yaml"
_SECRETS_README = _SECRETS_DIR / "README.md"
_TF_DIR = _REPO_ROOT / "terraform"
_TF_README = _TF_DIR / "README.md"
_GHA_MODULE = _TF_DIR / "modules" / "github-actions" / "main.tf"


def test_sops_config_targets_secrets_enc_files() -> None:
    """AC-sops-config: .sops.yaml encrypts secrets/*.enc.yaml via OpenPGP."""
    text = _SOPS_CONFIG.read_text(encoding="utf-8")
    assert "creation_rules" in text
    assert re.search(r"path_regex:.*secrets/.*\.enc", text), (
        "expected creation_rules path_regex for secrets/*.enc.*"
    )
    assert "pgp:" in text


def test_secrets_enc_yaml_is_sops_encrypted() -> None:
    """AC-secrets-enc: encrypted secrets file exists; plaintext never committed."""
    text = _SECRETS_ENC.read_text(encoding="utf-8")
    assert "sops:" in text
    assert "ENC[" in text
    assert "PERSONAL_WEBSITE_DISPATCH_PAT:" in text
    assert re.search(r"PERSONAL_WEBSITE_DISPATCH_PAT:\s*ENC\[", text), (
        "PERSONAL_WEBSITE_DISPATCH_PAT must be SOPS-encrypted, not plaintext"
    )


def test_secrets_template_documents_dispatch_pat() -> None:
    """AC-secrets-template: template documents PERSONAL_WEBSITE_DISPATCH_PAT."""
    text = _SECRETS_TEMPLATE.read_text(encoding="utf-8")
    assert "PERSONAL_WEBSITE_DISPATCH_PAT" in text


def test_secrets_readme_documents_bootstrap_and_rotation() -> None:
    """AC-secrets-readme: bootstrap, sops exec-env, and rotation documented."""
    text = _SECRETS_README.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "sops" in lowered
    assert "terraform apply" in lowered or "terraform/" in lowered
    assert "rotation" in lowered or "rotate" in lowered


def test_terraform_github_actions_module_syncs_dispatch_pat() -> None:
    """AC-tf-secret: enable_github_actions wires PERSONAL_WEBSITE_DISPATCH_PAT."""
    text = _GHA_MODULE.read_text(encoding="utf-8")
    assert "github_actions_secret" in text
    assert "personal_website_dispatch_pat" in text
    assert "PERSONAL_WEBSITE_DISPATCH_PAT" in text
    assert "var.personal_website_dispatch_pat" in text


def test_terraform_readme_documents_bootstrap() -> None:
    """AC-tf-readme: init/plan/apply and SOPS key bootstrap documented."""
    text = _TF_README.read_text(encoding="utf-8")
    lowered = text.lower()
    assert "terraform init" in lowered
    assert "terraform apply" in lowered
    assert "enable_github_actions" in text
    assert "sops" in lowered or "secrets/" in text
