data "github_repository" "repo" {
  full_name = "${var.github_owner}/${var.github_repository}"
}

resource "github_actions_secret" "personal_website_dispatch_pat" {
  repository  = data.github_repository.repo.name
  secret_name   = "PERSONAL_WEBSITE_DISPATCH_PAT"
  value       = var.personal_website_dispatch_pat
}
