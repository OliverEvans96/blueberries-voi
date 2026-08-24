output "github_actions_secrets_enabled" {
  description = "True when enable_github_actions syncs PERSONAL_WEBSITE_DISPATCH_PAT."
  value       = var.enable_github_actions
}

output "github_actions_secret_names" {
  description = "Repository secrets managed when enable_github_actions is true."
  value       = var.enable_github_actions ? ["PERSONAL_WEBSITE_DISPATCH_PAT"] : []
}
