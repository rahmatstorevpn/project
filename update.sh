#!/bin/bash
##update

cd /var/www/
rm bat.py
rm nona.py
rm .bckupbot
wget https://raw.githubusercontent.com/rahmatstorevpn/project/main/bot/nona.py

mv nona.py bat.py


echo "=== SETUP BACKUP BOT ==="
echo ""

# Input Token Bot
read -p "Masukkan Token Bot Telegram: " TOKEN
echo "Token: $TOKEN"
echo ""

# Input Admin ID
read -p "Masukkan Admin ID (UID Telegram): " ADMIN_ID
echo "Admin ID: $ADMIN_ID"
echo ""

# Validasi Admin ID harus angka
if ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Admin ID harus berupa angka!"
    exit 1
fi

# Buat file konfigurasi
echo "$TOKEN" > /var/www/.bckupbot
echo "$ADMIN_ID" >> /var/www/.bckupbot
echo "off" >> /var/www/.bckupbot

# Set permission
chmod 600 /var/www/.bckupbot

echo "✅ Konfigurasi berhasil disimpan di /root/.bckupbot"
echo ""
echo "=== ISI FILE KONFIGURASI ==="
cat /var/www/.bckupbot
echo "============================="
echo ""

wget https://raw.githubusercontent.com/rahmatstorevpn/project/main/bot/kapak.sh

bash kapak.sh


