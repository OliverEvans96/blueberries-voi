provider "cloudflare" {
  api_token = data.sops_file.secrets.data["CLOUDFLARE_API_TOKEN"]
}

provider "github" {
  owner = coalesce(var.github_owner, "disabled")
  token = var.github_token
}

provider "sops" {}
