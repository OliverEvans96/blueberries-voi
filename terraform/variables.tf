variable "enable_github_actions" {
  type    = bool
  default = false
}

variable "github_owner" {
  type     = string
  default  = null
  nullable = true
}

variable "github_repository" {
  type     = string
  default  = null
  nullable = true
}

variable "github_token" {
  description = "GitHub PAT (repo + Actions secrets). Falls back to GITHUB_TOKEN env var."
  type        = string
  sensitive   = true
  default     = null
  nullable    = true
}
