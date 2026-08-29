output "project_name" {
  description = "Cloudflare Pages project name."
  value       = cloudflare_pages_project.studio.name
}

output "subdomain" {
  description = "Default Pages subdomain (e.g. blueberries-voi-studio.pages.dev)."
  value       = cloudflare_pages_project.studio.subdomain
}
