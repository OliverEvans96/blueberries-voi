resource "cloudflare_pages_project" "studio" {
  account_id        = var.account_id
  name              = var.project_name
  production_branch = var.production_branch
  build_config = {
    build_caching   = true
    build_command   = "npm run build"
    destination_dir = "dist"
    root_dir        = "web"
  }
}
