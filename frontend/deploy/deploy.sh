#!/usr/bin/env bash
set -e

echo "=== Desplegando Frontend BuildCorp en EC2 ==="
sudo apt update -y
sudo apt install -y nginx

sudo mkdir -p /var/www/buildcorp-frontend
sudo cp -r index.html css js /var/www/buildcorp-frontend/
sudo chown -R www-data:www-data /var/www/buildcorp-frontend

sudo cp deploy/nginx_frontend.conf /etc/nginx/sites-available/buildcorp_frontend
sudo ln -sf /etc/nginx/sites-available/buildcorp_frontend /etc/nginx/sites-enabled/buildcorp_frontend
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

echo "[OK] Frontend BuildCorp activo en puerto 80!"
