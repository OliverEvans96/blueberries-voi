variable "enable_github_actions" {
  description = "When true, sync SOPS secrets to GitHub Actions via modules/github-actions."
  type        = bool
  default     = false
}

variable "github_owner" {
  type     = string
  default  = null
  nullable = true

  validation {
    condition     = !var.enable_github_actions || var.github_owner != null
    error_message = "github_owner is required when enable_github_actions is true."
  }
}

variable "github_repository" {
  type     = string
  default  = null
  nullable = true

  validation {
    condition     = !var.enable_github_actions || var.github_repository != null
    error_message = "github_repository is required when enable_github_actions is true."
  }
}

variable "github_token" {
  description = "GitHub PAT (repo + Actions secrets). Falls back to GITHUB_TOKEN env var."
  type        = string
  sensitive   = true
  default     = null
  nullable    = true
}

variable "studio_pages_project_name" {
  description = "Cloudflare Pages project for studio PR previews and direct uploads."
  type        = string
  default     = "blueberries-voi-studio"
}
