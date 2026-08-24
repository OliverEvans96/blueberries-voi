data "sops_file" "secrets" {
  source_file = "${path.module}/../secrets/secrets.enc.yaml"
  input_type  = "yaml"
}
