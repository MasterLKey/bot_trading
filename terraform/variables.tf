variable "proxmox_host" {
  type        = string
  description = "Proxmox host IP"
  default     = "192.168.4.223"
}

variable "proxmox_node" {
  type    = string
  default = "pm01"
}

variable "proxmox_api_token" {
  type      = string
  sensitive = true
}

variable "container_id" {
  type    = number
  default = 220
}

variable "storage" {
  type    = string
  default = "local-lvm"
}

variable "ssh_public_key" {
  type = string
}

variable "root_password" {
  type      = string
  sensitive = true
}
