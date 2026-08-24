module "github_actions" {
  count  = var.enable_github_actions ? 1 : 0
  source = "./modules/github-actions"

  github_owner                  = var.github_owner
  github_repository             = var.github_repository
  personal_website_dispatch_pat = data.sops_file.secrets.data["PERSONAL_WEBSITE_DISPATCH_PAT"]
}
