#!/bin/bash

# Warna untuk output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Konfigurasi
VENV_PATH="/var/www/venv"
BOT_PATH="/var/www/bot.py"
P_PATH="/var/www/p.py"
LOG_DIR="/var/log/bot-services"

echo -e "${BLUE}╔════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   🚀 AUTO SETUP BOT SERVICES      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════╝${NC}"
echo ""

# Cek root privileges
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}❌ Script ini harus dijalankan sebagai root!${NC}" 
   exit 1
fi

# Fungsi untuk mengecek error
check_error() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Error: $1${NC}"
        exit 1
    fi
}

# 1. Update system dan install dependencies
echo -e "${YELLOW}[1/8]📦 Mengupdate system dan menginstall dependencies...${NC}"
apt-get update
apt-get install -y python3 python3-pip python3-venv python3-dev build-essential
check_error "Gagal install dependencies"

# 2. Buat virtual environment
echo -e "${YELLOW}[2/8]🔧 Membuat virtual environment di $VENV_PATH...${NC}"
python3 -m venv $VENV_PATH
check_error "Gagal membuat virtual environment"

# 3. Aktifkan venv dan install packages
echo -e "${YELLOW}[3/8]📚 Menginstall packages di virtual environment...${NC}"
source $VENV_PATH/bin/activate

# Upgrade pip dulu
pip install --upgrade pip

# Install packages
pip install flask python-telegram-bot pillow paramiko
check_error "Gagal install packages"

deactivate
echo -e "${GREEN}✅ Packages berhasil diinstall${NC}"

# 4. Buat directory log
echo -e "${YELLOW}[4/8]📁 Membuat directory log...${NC}"
mkdir -p $LOG_DIR
chmod 755 $LOG_DIR

# 5. Buat service file untuk bot9
echo -e "${YELLOW}[5/8]⚙️ Membuat service bot9...${NC}"

cat > /etc/systemd/system/bot9.service << EOF
[Unit]
Description=Bot9 Service - Telegram Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www
Environment="PATH=$VENV_PATH/bin"
ExecStart=$VENV_PATH/bin/python3 $BOT_PATH
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/bot9.log
StandardError=append:$LOG_DIR/bot9.error.log
SyslogIdentifier=bot9

[Install]
WantedBy=multi-user.target
EOF

check_error "Gagal membuat service bot9"

# 6. Buat service file untuk p1
echo -e "${YELLOW}[6/8]⚙️ Membuat service p1...${NC}"

cat > /etc/systemd/system/p1.service << EOF
[Unit]
Description=P1 Service - Python Application
After=network.target
Wants=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www
Environment="PATH=$VENV_PATH/bin"
ExecStart=$VENV_PATH/bin/python3 $P_PATH
Restart=always
RestartSec=10
StandardOutput=append:$LOG_DIR/p1.log
StandardError=append:$LOG_DIR/p1.error.log
SyslogIdentifier=p1

[Install]
WantedBy=multi-user.target
EOF

check_error "Gagal membuat service p1"

# 7. Set permissions
echo -e "${YELLOW}[7/8]🔐 Mengatur permissions...${NC}"

# Set ownership untuk www-data
chown -R www-data:www-data /var/www
chown -R www-data:www-data $LOG_DIR

# Set execute permissions untuk venv
chmod +x $VENV_PATH/bin/*
chmod +x $BOT_PATH 2>/dev/null || echo -e "${YELLOW}⚠️  File bot.py belum ada${NC}"
chmod +x $P_PATH 2>/dev/null || echo -e "${YELLOW}⚠️  File p.py belum ada${NC}"

# 8. Reload systemd dan enable services
echo -e "${YELLOW}[8/8]🔄 Merefresh systemd dan mengaktifkan services...${NC}"

systemctl daemon-reload

# Enable services agar auto-start saat boot
systemctl enable bot9.service
systemctl enable p1.service

# Coba start services (jika file python sudah ada)
if [ -f "$BOT_PATH" ]; then
    systemctl start bot9.service
    echo -e "${GREEN}✅ Service bot9 dimulai${NC}"
else
    echo -e "${YELLOW}⚠️  File $BOT_PATH belum ada, service belum distart${NC}"
fi

if [ -f "$P_PATH" ]; then
    systemctl start p1.service
    echo -e "${GREEN}✅ Service p1 dimulai${NC}"
else
    echo -e "${YELLOW}⚠️  File $P_PATH belum ada, service belum distart${NC}"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✅ SETUP COMPLETED!             ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📋 INFORMASI SERVICES:${NC}"
echo "================================"
echo -e "Service bot9: ${GREEN}/etc/systemd/system/bot9.service${NC}"
echo -e "Service p1: ${GREEN}/etc/systemd/system/p1.service${NC}"
echo -e "Virtual Env: ${GREEN}$VENV_PATH${NC}"
echo -e "Log directory: ${GREEN}$LOG_DIR${NC}"
echo ""
echo -e "${YELLOW}📌 COMMANDS:${NC}"
echo "================================"
echo -e "Start bot9   : ${GREEN}systemctl start bot9${NC}"
echo -e "Stop bot9    : ${RED}systemctl stop bot9${NC}"
echo -e "Restart bot9 : ${YELLOW}systemctl restart bot9${NC}"
echo -e "Status bot9  : ${BLUE}systemctl status bot9${NC}"
echo ""
echo -e "Start p1     : ${GREEN}systemctl start p1${NC}"
echo -e "Stop p1      : ${RED}systemctl stop p1${NC}"
echo -e "Restart p1   : ${YELLOW}systemctl restart p1${NC}"
echo -e "Status p1    : ${BLUE}systemctl status p1${NC}"
echo ""
echo -e "View logs    : ${BLUE}tail -f $LOG_DIR/bot9.log${NC}"
echo -e "View errors  : ${RED}tail -f $LOG_DIR/bot9.error.log${NC}"
echo ""
echo -e "Aktifkan venv : ${BLUE}source $VENV_PATH/bin/activate${NC}"
echo "================================"

# Optional: Buat script helper untuk manage services
cat > /usr/local/bin/bot-manager << 'EOF'
#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

case $1 in
    start)
        systemctl start bot9
        systemctl start p1
        echo -e "${GREEN}✅ Services started${NC}"
        ;;
    stop)
        systemctl stop bot9
        systemctl stop p1
        echo -e "${RED}⏹️ Services stopped${NC}"
        ;;
    restart)
        systemctl restart bot9
        systemctl restart p1
        echo -e "${YELLOW}🔄 Services restarted${NC}"
        ;;
    status)
        echo -e "${BLUE}📊 Service Status:${NC}"
        systemctl status bot9 --no-pager
        echo ""
        systemctl status p1 --no-pager
        ;;
    logs)
        tail -f /var/log/bot-services/bot9.log
        ;;
    errors)
        tail -f /var/log/bot-services/bot9.error.log
        ;;
    *)
        echo "Usage: bot-manager {start|stop|restart|status|logs|errors}"
        ;;
esac
EOF

chmod +x /usr/local/bin/bot-manager

echo -e "${GREEN}✅ Helper script created: ${BLUE}bot-manager${NC}"
echo -e "Gunakan: ${YELLOW}bot-manager {start|stop|restart|status|logs|errors}${NC}"
