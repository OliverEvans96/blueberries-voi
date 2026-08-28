variable "github_owner" { type = string }
variable "github_repository" { type = string }

variable "personal_website_dispatch_pat" {
  description = "PAT with access to OliverEvans96/personal-website for repository_dispatch."
  type        = string
  sensitive   = true
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with Pages Edit for studio preview deploys."
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID hosting the studio Pages project."
  type        = string
  sensitive   = true
}

variable "studio_pages_project_name" {
  description = "Cloudflare Pages project name synced to CLOUDFLARE_PAGES_PROJECT_NAME."
  type        = string
}
