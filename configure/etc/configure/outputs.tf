output "OS_USERNAME" {
  description = "OpenStack username"
  value       = openstack_identity_user_v3.user.name
  sensitive   = true
}

output "OS_PASSWORD" {
  description = "OpenStack password"
  value       = openstack_identity_user_v3.user.password
  sensitive   = true
}

output "OS_USER_DOMAIN_NAME" {
  description = "OpenStack user domain name"
  value       = openstack_identity_project_v3.users_domain.name
}

output "OS_PROJECT_DOMAIN_NAME" {
  description = "OpenStack project domain name"
  value       = openstack_identity_project_v3.users_domain.name
}

output "OS_PROJECT_NAME" {
  description = "OpenStack project name"
  value       = openstack_identity_project_v3.user_project.name
  sensitive   = true
}
