output "container_id" {
  value = proxmox_virtual_environment_container.bot_trading.vm_id
}

output "next_steps" {
  value = <<-EOT
    1. Note the LXC IP from Proxmox UI (DHCP on vmbr0)
    2. scp scripts/provision.sh and ensure repo is pushed to GitHub
    3. ssh -i ~/.ssh/octo_scrape_deploy root@<IP> "bash /root/provision.sh"
       (or copy provision.sh to the box first)
    4. scp .env root@<IP>:/opt/bot_trading/.env && chmod 600
    5. systemctl start bot-trading
    6. Open http://<IP>:8000
  EOT
}
