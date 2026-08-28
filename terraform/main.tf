module "cloudflare_pages" {
  source = "./modules/cloudflare-pages"

  account_id        = data.sops_file.secrets.data["CLOUDFLARE_ACCOUNT_ID"]
  project_name      = var.studio_pages_project_name
  production_branch = "main"
}

module "github_actions" {
  count  = var.enable_github_actions ? 1 : 0
  source = "./modules/github-actions"

  github_owner                  = var.github_owner
  github_repository             = var.github_repository
  personal_website_dispatch_pat = data.sops_file.secrets.data["PERSONAL_WEBSITE_DISPATCH_PAT"]
  cloudflare_api_token          = data.sops_file.secrets.data["CLOUDFLARE_API_TOKEN"]
  cloudflare_account_id         = data.sops_file.secrets.data["CLOUDFLARE_ACCOUNT_ID"]
  studio_pages_project_name     = var.studio_pages_project_name
}
