variable "github_owner" { type = string }
variable "github_repository" { type = string }

variable "personal_website_dispatch_pat" {
  description = "PAT with access to OliverEvans96/personal-website for repository_dispatch."
  type        = string
  sensitive   = true
}
