variable "account_id" {
  description = "Cloudflare account ID for Pages project provisioning."
  type        = string
  sensitive   = true
}

variable "project_name" {
  description = "Cloudflare Pages project name (wrangler --project-name)."
  type        = string
}

variable "production_branch" {
  description = "Production branch label for the Pages project."
  type        = string
  default     = "main"
}
