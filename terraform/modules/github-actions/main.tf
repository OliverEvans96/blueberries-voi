data "github_repository" "repo" {
  full_name = "${var.github_owner}/${var.github_repository}"
}

resource "github_actions_secret" "personal_website_dispatch_pat" {
  repository  = data.github_repository.repo.name
  secret_name = "PERSONAL_WEBSITE_DISPATCH_PAT"
  value       = var.personal_website_dispatch_pat
}

resource "github_actions_secret" "cloudflare_api_token" {
  repository  = data.github_repository.repo.name
  secret_name = "CLOUDFLARE_API_TOKEN"
  value       = var.cloudflare_api_token
}

resource "github_actions_secret" "cloudflare_account_id" {
  repository  = data.github_repository.repo.name
  secret_name = "CLOUDFLARE_ACCOUNT_ID"
  value       = var.cloudflare_account_id
}

resource "github_actions_variable" "cloudflare_pages_project_name" {
  repository    = data.github_repository.repo.name
  variable_name = "CLOUDFLARE_PAGES_PROJECT_NAME"
  value         = var.studio_pages_project_name
}
