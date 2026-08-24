provider "github" {
  owner = coalesce(var.github_owner, "disabled")
  token = var.github_token
}

provider "sops" {}
