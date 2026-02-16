#!/bin/bash
# Auto Setup Script by Casper

clear
echo "=========================================="
echo "       AUTO INSTALL SCRIPT STARTED"
echo "=========================================="

# Masuk ke direktori root
cd /root || exit

# Download semua file
echo "[1/5] Mengunduh file dari GitHub..."
wget -q https://raw.githubusercontent.com/rahmatstorevpn/project/main/mstore/bot.py
wget -q https://raw.githubusercontent.com/rahmatstorevpn/project/main/mstore/p.py
wget -q https://raw.githubusercontent.com/rahmatstorevpn/project/main/mstore/menu
wget -q https://raw.githubusercontent.com/rahmatstorevpn/project/main/mstore/set.sh

# Pindahkan file ke lokasi yang sesuai
echo "[2/5] Memindahkan file..."
mv bot.py /var/www/ 2>/dev/null
mv p.py /var/www/ 2>/dev/null
mv menu /usr/bin/ 2>/dev/null

# Beri izin eksekusi
echo "[3/5] Mengatur permission..."
chmod +x /usr/bin/menu

# Jalankan set.sh
echo "[4/5] Menjalankan set.sh..."
bash set.sh

# Bersihkan sisa file (opsional)
echo "[5/5] Membersihkan file sementara..."
rm -f set.sh

echo "=========================================="
echo "     INSTALASI SELESAI DENGAN SUKSES!"
echo "=========================================="
