terraform {
  required_version = ">= 1.6"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.76"
    }
  }
}

provider "proxmox" {
  endpoint  = "https://${var.proxmox_host}:8006/"
  api_token = var.proxmox_api_token
  insecure  = true
}

locals {
  ubuntu_template = "local:vztmpl/ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
}

resource "proxmox_virtual_environment_container" "bot_trading" {
  node_name   = var.proxmox_node
  vm_id       = var.container_id
  description = "Trade Probability Pipeline — SCAN/SIGNALS/PLAN/RISK/DECISION"
  tags        = ["bot-trading", "docker"]

  start_on_boot = true
  started       = true
  unprivileged  = true

  operating_system {
    template_file_id = local.ubuntu_template
    type             = "ubuntu"
  }

  cpu {
    cores = 2
  }

  memory {
    dedicated = 2048
  }

  disk {
    datastore_id = var.storage
    size         = 32
  }

  network_interface {
    name   = "eth0"
    bridge = "vmbr0"
  }

  features {
    nesting = true
  }

  initialization {
    hostname = "bot-trading"

    user_account {
      keys     = [var.ssh_public_key]
      password = var.root_password
    }

    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }
  }
}
