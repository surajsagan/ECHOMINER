#!/usr/bin/env bash
# One-time preparation of a fresh Oracle Cloud Ubuntu 22.04/24.04 ARM VM.
# Run as the default 'ubuntu' user:  bash infra/scripts/bootstrap-server.sh
set -euo pipefail

echo "==> System updates"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git netfilter-persistent iptables-persistent unattended-upgrades

echo "==> Docker Engine + Compose plugin"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker

echo "==> Open ports 80/443 in the VM firewall"
# Oracle's Ubuntu images ship iptables rules that REJECT everything except SSH.
# Opening the port in the Oracle Console security list alone is NOT enough.
for port in 80 443; do
  sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
    || sudo iptables -I INPUT 5 -m state --state NEW -p tcp --dport "$port" -j ACCEPT
done
sudo netfilter-persistent save

echo "==> 4 GB swap (headroom for Next.js builds)"
if [ ! -f /swapfile ]; then
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "==> Directories"
sudo mkdir -p /etc/echominer/certs /var/backups/echominer
sudo chown -R "$USER":"$USER" /var/backups/echominer
sudo chmod 700 /etc/echominer/certs

echo "==> Automatic security updates"
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

echo
echo "Done. Log out and back in (so the docker group applies), then continue with"
echo "docs/DEPLOYMENT.md, Phase 5."
