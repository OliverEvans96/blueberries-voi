output "github_actions_secrets_enabled" {
  description = "True when enable_github_actions syncs repository secrets from SOPS."
  value       = var.enable_github_actions
}

output "github_actions_secret_names" {
  description = "Repository secrets managed when enable_github_actions is true."
  value = var.enable_github_actions ? [
    "PERSONAL_WEBSITE_DISPATCH_PAT",
    "CLOUDFLARE_API_TOKEN",
    "CLOUDFLARE_ACCOUNT_ID",
  ] : []
}

output "github_actions_variable_names" {
  description = "Repository variables managed when enable_github_actions is true."
  value       = var.enable_github_actions ? ["CLOUDFLARE_PAGES_PROJECT_NAME"] : []
}

output "studio_pages_project_name" {
  description = "Cloudflare Pages project name for studio previews."
  value       = module.cloudflare_pages.project_name
}

output "studio_pages_subdomain" {
  description = "Default *.pages.dev subdomain for the studio Pages project."
  value       = module.cloudflare_pages.subdomain
}
