#!/bin/bash
# Auto setup Python bot environment and systemd service
# Author: Casper 😎

set -e  # stop on error

# === Konfigurasi dasar ===
BOT_PATH="/var/www"
BOT_FILE="bat.py"
VENV_PATH="$BOT_PATH/venv"
SERVICE_NAME="bat.service"

echo "📦 Membuat virtual environment..."
apt update -y
apt install -y python3-venv python3-pip

# Buat venv jika belum ada
if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
    echo "✅ Virtualenv dibuat di $VENV_PATH"
else
    echo "ℹ️ Virtualenv sudah ada, skip."
fi

# Aktivasi venv & install module
echo "⚙️ Install modul Python..."
source "$VENV_PATH/bin/activate"
pip install --upgrade pip
pip install python-telegram-bot schedule asyncio
deactivate

# === Buat systemd service ===
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

echo "🧠 Membuat systemd service di $SERVICE_FILE ..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Bat Python Bot Service
After=network.target

[Service]
Type=simple
WorkingDirectory=$BOT_PATH
ExecStart=$VENV_PATH/bin/python $BOT_PATH/$BOT_FILE
Restart=always
RestartSec=5
User=root
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd dan aktifkan service
echo "🔄 Reloading systemd..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo "✅ Bot service sudah aktif!"
echo "📋 Cek status dengan: sudo systemctl status $SERVICE_NAME"
echo "📜 Lihat log realtime: sudo journalctl -u $SERVICE_NAME -f"