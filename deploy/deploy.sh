#!/usr/bin/env bash
# ==============================================================================
# EVA4 BACKEND - PRODUCTION DEPLOYMENT SCRIPT FOR AWS EC2 (UBUNTU)
# ==============================================================================
# Automates the entire provisioning, permission configuration, dependency installation,
# database migrations, static file collection, and systemd/nginx service management.
# ==============================================================================

set -euo pipefail

# Configuration paths
APP_DIR="/home/ubuntu/apps/backend"
STATIC_DIR="/home/ubuntu/apps/static"
MEDIA_DIR="/home/ubuntu/apps/media"
LOGS_DIR="/home/ubuntu/apps/backend/logs"
VENV_DIR="${APP_DIR}/venv"

echo "=========================================================="
echo " Starting EVA4 Backend Deployment on AWS EC2..."
echo " Target Directory: ${APP_DIR}"
echo "=========================================================="

# 1. Update and install required system packages
echo "[1/7] Installing system packages (Python, Nginx, libpq, build-essential)..."
sudo apt-get update -y
sudo apt-get install -y python3-pip python3-venv python3-dev nginx libpq-dev curl build-essential

# 2. Create required directory tree
echo "[2/7] Creating runtime directories..."
mkdir -p "${APP_DIR}"
mkdir -p "${STATIC_DIR}"
mkdir -p "${MEDIA_DIR}"
mkdir -p "${LOGS_DIR}"

# 3. Secure file system permissions to prevent 502 Bad Gateway / 13 Permission Denied
echo "[3/7] Setting permissions for user 'ubuntu' and group 'www-data'..."
sudo usermod -aG ubuntu www-data
sudo chmod 750 /home/ubuntu
sudo chown -R ubuntu:www-data /home/ubuntu/apps
sudo chmod -R 770 /home/ubuntu/apps

# 4. Virtual Environment & Dependencies
echo "[4/7] Setting up Python virtual environment..."
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
pip install --upgrade pip
pip install -r "${APP_DIR}/requirements.txt"

# 5. Database migrations & Static collection
echo "[5/7] Running database migrations and static collection..."
cd "${APP_DIR}"
python manage.py makemigrations core --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# 6. Configure Systemd Service (Gunicorn)
echo "[6/7] Configuring Gunicorn systemd service..."
sudo cp "${APP_DIR}/deploy/gunicorn.service" /etc/systemd/system/gunicorn.service
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl restart gunicorn

# 7. Configure Nginx Reverse Proxy
echo "[7/7] Configuring Nginx reverse proxy..."
sudo cp "${APP_DIR}/deploy/nginx_backend.conf" /etc/nginx/sites-available/backend
if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm -f /etc/nginx/sites-enabled/default
fi
sudo ln -sf /etc/nginx/sites-available/backend /etc/nginx/sites-enabled/backend

# Validate Nginx syntax before reload
sudo nginx -t
sudo systemctl restart nginx

# 8. Post-deployment verification
echo "=========================================================="
echo " Verifying deployment status..."
sleep 3

if sudo systemctl is-active --quiet gunicorn; then
    echo " [OK] Gunicorn service is active and running."
else
    echo " [ERROR] Gunicorn service failed to start. Checking journal logs:"
    sudo journalctl -u gunicorn -n 20 --no-pager
    exit 1
fi

if sudo systemctl is-active --quiet nginx; then
    echo " [OK] Nginx service is active and running."
else
    echo " [ERROR] Nginx service failed to start."
    exit 1
fi

echo " Testing Health Endpoint (http://localhost/api/v1/health/)..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/v1/health/ || echo "Failed")

echo " Health Check HTTP Status: ${HTTP_STATUS}"
echo "=========================================================="
echo " EVA4 Backend deployment completed successfully!"
echo "=========================================================="
