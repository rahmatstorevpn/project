#!/bin/bash
#update

cd /var/www/
rm bat.py
rm nona.py
rm .bckupbot
wget https://raw.githubusercontent.com/rahmatstorevpn/project/main/bot/nona.py

mv nona.py bat.py


# setup_backupbot.sh
echo "╔══════════════════════════════════════╗"
echo "║      SETUP BACKUP BOT TELEGRAM       ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Pilih lokasi penyimpanan konfigurasi
echo "Pilih lokasi penyimpanan konfigurasi:"
echo "1. /root/.bckupbot (direkomendasikan)"
echo "2. /var/www/.bckupbot"
read -p "Pilihan [1/2]: " LOCATION_CHOICE

case $LOCATION_CHOICE in
    1) CONFIG_FILE="/root/.bckupbot" ;;
    2) CONFIG_FILE="/var/www/.bckupbot" ;;
    *) CONFIG_FILE="/root/.bckupbot" ;;
esac

echo ""
echo "Lokasi konfigurasi: $CONFIG_FILE"
echo ""

# Input Token Bot
echo "📝 MASUKKAN TOKEN BOT TELEGRAM"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Cara mendapatkan token:"
echo "1. Buka @BotFather di Telegram"
echo "2. Ketik /newbot"
echo "3. Ikuti petunjuk untuk membuat bot"
echo "4. Salin token yang diberikan"
echo ""
read -p "Token Bot: " TOKEN

# Validasi token format
if [[ ! "$TOKEN" =~ ^[0-9]+:[a-zA-Z0-9_-]+$ ]]; then
    echo ""
    echo "❌ ERROR: Format token tidak valid!"
    echo "Format token harus: 1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    exit 1
fi

echo ""
echo "✅ Token valid: ${TOKEN:0:10}..."
echo ""

# Input Admin ID
echo "👤 MASUKKAN ADMIN ID (UID TELEGRAM)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Cara mendapatkan Admin ID:"
echo "1. Buka @userinfobot di Telegram"
echo "2. Kirim pesan apapun"
echo "3. Bot akan memberikan ID Anda"
echo ""
read -p "Admin ID: " ADMIN_ID

# Validasi Admin ID harus angka
if ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
    echo ""
    echo "❌ ERROR: Admin ID harus berupa angka!"
    exit 1
fi

echo ""
echo "✅ Admin ID valid: $ADMIN_ID"
echo ""

# Konfirmasi
echo "📋 KONFIRMASI DATA"
echo "━━━━━━━━━━━━━━━━━━"
echo "Token Bot: ${TOKEN:0:10}..."
echo "Admin ID : $ADMIN_ID"
echo "Lokasi   : $CONFIG_FILE"
echo ""
read -p "Simpan konfigurasi? [y/N]: " CONFIRM

if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo ""
    echo "❌ Setup dibatalkan!"
    exit 0
fi

# Buat direktori jika belum ada
CONFIG_DIR=$(dirname "$CONFIG_FILE")
if [ ! -d "$CONFIG_DIR" ]; then
    mkdir -p "$CONFIG_DIR"
    echo "📁 Membuat direktori: $CONFIG_DIR"
fi

# Buat file konfigurasi
echo "$TOKEN" > "$CONFIG_FILE"
echo "$ADMIN_ID" >> "$CONFIG_FILE"
echo "off" >> "$CONFIG_FILE"

# Set permission
chmod 600 "$CONFIG_FILE"

echo ""
echo "══════════════════════════════════════"
echo "✅ KONFIGURASI BERHASIL DISIMPAN"
echo "══════════════════════════════════════"
echo ""
echo "📄 Lokasi file: $CONFIG_FILE"
echo "📝 Isi file:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat "$CONFIG_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎯 LANGKAH SELANJUTNYA:"
echo "1. Periksa kode Python Anda menggunakan CONFIG_FILE yang benar"
echo "   (Sesuaikan dengan $CONFIG_FILE)"
echo ""
echo "2. Jalankan bot dengan:"
echo "   python3 /var/www/backupbot.py"
echo ""
echo "3. Buka Telegram dan kirim /start ke bot Anda"
echo ""
echo "4. Cek apakah bot merespon dengan menu utama"
echo ""
echo "⚠️  PENTING: Jika bot tidak berjalan, pastikan:"
echo "   - Token bot benar"
echo "   - Admin ID benar"
echo "   - Bot sudah di-start di @BotFather"
echo "   - Tidak ada firewall yang memblokir koneksi"
echo ""
echo "🔧 Untuk mengedit konfigurasi nanti:"
echo "   nano $CONFIG_FILE"
echo "   atau"
echo "   ./setup_backupbot.sh"
echo ""
echo "🎉 SELAMAT! Setup selesai."
wget https://raw.githubusercontent.com/rahmatstorevpn/project/main/bot/kapak.sh

bash kapak.sh
