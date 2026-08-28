terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = { source = "cloudflare/cloudflare", version = "~> 5.0" }
    github     = { source = "integrations/github", version = "~> 6.0" }
    sops       = { source = "carlpett/sops", version = "~> 1.0" }
  }
}
