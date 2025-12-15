#!/bin/bash
# Zivpn UDP Module Installer
# Creator: Tuyul Premium

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'
DIM='\033[2m'

# Function for centered text
center_text() {
    local text="$1"
    local width=70
    local padding=$(( (width - ${#text}) / 2 ))
    printf "%${padding}s" ''
    echo -e "$text"
}

# Function for colored boxes
box_out() {
    local color="$1"
    local text="$2"
    echo -e "${color}╔══════════════════════════════════════════════════════════════╗${NC}"
    center_text "$text" | while read line; do
        echo -e "${color}║${NC} ${BOLD}$line${NC} $(printf '%*s' $((66 - ${#line})) '') ${color}║${NC}"
    done
    echo -e "${color}╚══════════════════════════════════════════════════════════════╝${NC}"
}

# Function for progress bar
progress_bar() {
    local duration=$1
    local steps=50
    local increment=$((100 / steps))
    
    for ((i=0; i<=steps; i++)); do
        percentage=$((i * 2))
        completed=$((i * 50 / steps))
        remaining=$((50 - completed))
        
        printf "\r${BLUE}[${NC}"
        printf "%0.s█" $(seq 1 $completed)
        printf "%0.s░" $(seq 1 $remaining)
        printf "${BLUE}]${NC} ${GREEN}${percentage}%%${NC}"
        
        sleep $(awk "BEGIN {print $duration/$steps}")
    done
    printf "\n"
}

# Function for section headers
section_header() {
    echo -e "\n${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC} ${BOLD}${YELLOW}$1${NC} $(printf '%*s' $((60 - ${#1})) '') ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}\n"
}

# Clear screen
clear

# Banner
echo -e "${MAGENTA}"
echo "███████╗██╗██╗   ██╗██████╗ ███╗   ██╗"
echo "╚══███╔╝██║██║   ██║██╔══██╗████╗  ██║"
echo "  ███╔╝ ██║██║   ██║██████╔╝██╔██╗ ██║"
echo " ███╔╝  ██║██║   ██║██╔═══╝ ██║╚██╗██║"
echo "███████╗██║╚██████╔╝██║     ██║ ╚████║"
echo "╚══════╝╚═╝ ╚═════╝ ╚═╝     ╚═╝  ╚═══╝"
echo -e "${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
center_text "${BOLD}UDP Module Installer v1.4.9${NC}"
center_text "${DIM}Created by: Tuyul Premium${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}\n"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    box_out "$RED" "PERINGATAN: Script harus dijalankan sebagai root!"
    echo -e "${RED}Gunakan: sudo bash install.sh${NC}"
    exit 1
fi

# Confirmation before installation
echo -e "${YELLOW}⚠️  INFORMASI INSTALASI${NC}"
echo -e "${DIM}────────────────────────────────────────────────────────────${NC}"
echo -e "📦 Aplikasi yang akan diinstal:"
echo -e "   • ${GREEN}Zivpn UDP Server${NC}"
echo -e "   • ${GREEN}Systemd Service${NC}"
echo -e "   • ${GREEN}Management Menu${NC}"
echo -e "\n🔧 Port yang akan dibuka:"
echo -e "   • ${CYAN}UDP 5667${NC} (Service Port)"
echo -e "   • ${CYAN}UDP 6000-19999${NC} (User Ports)"
echo -e "\n💾 Lokasi instalasi:"
echo -e "   • ${MAGENTA}/usr/local/bin/zivpn${NC}"
echo -e "   • ${MAGENTA}/etc/zivpn/${NC}"
echo -e "${DIM}────────────────────────────────────────────────────────────${NC}"

read -p "$(echo -e "${BOLD}${YELLOW}Lanjutkan instalasi? (y/N): ${NC}")" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}❌ Instalasi dibatalkan!${NC}"
    exit 0
fi

# Start installation
section_header "MEMULAI INSTALASI ZIVPN UDP"

# Step 1: Update server
section_header "STEP 1: UPDATE SERVER"
echo -e "${BLUE}🔄 Memperbarui paket sistem...${NC}"
progress_bar 3
sudo apt-get update && apt-get upgrade -y 1> /dev/null 2> /dev/null
echo -e "${GREEN}✅ Update server selesai!${NC}"

# Step 2: Stop existing service
section_header "STEP 2: MENGHEMTI SERVICE LAMA"
echo -e "${BLUE}⏸️  Menghentikan service zivpn (jika ada)...${NC}"
systemctl stop zivpn.service 1> /dev/null 2> /dev/null
sleep 2
echo -e "${GREEN}✅ Service berhasil dihentikan!${NC}"

# Step 3: Download UDP service
section_header "STEP 3: DOWNLOAD BINARY ZIVPN"
echo -e "${BLUE}⬇️  Mengunduh Zivpn UDP binary...${NC}"
progress_bar 5
wget -q --show-progress https://github.com/zahidbd2/udp-zivpn/releases/download/udp-zivpn_1.4.9/udp-zivpn-linux-amd64 -O /usr/local/bin/zivpn
chmod +x /usr/local/bin/zivpn
echo -e "${GREEN}✅ Binary berhasil diunduh!${NC}"

# Step 4: Create config directory
section_header "STEP 4: SETUP KONFIGURASI"
echo -e "${BLUE}📁 Membuat direktori konfigurasi...${NC}"
mkdir -p /etc/zivpn 1> /dev/null 2> /dev/null
wget -q https://raw.githubusercontent.com/zahidbd2/udp-zivpn/main/config.json -O /etc/zivpn/config.json
echo -e "${GREEN}✅ Direktori konfigurasi siap!${NC}"

# Step 5: Generate SSL certificates
section_header "STEP 5: GENERATE SERTIFIKAT SSL"
echo -e "${BLUE}🔐 Membuat sertifikat SSL...${NC}"
openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 \
    -subj "/C=US/ST=California/L=Los Angeles/O=Zivpn Corp/OU=VPN Department/CN=zivpn-server" \
    -keyout "/etc/zivpn/zivpn.key" \
    -out "/etc/zivpn/zivpn.crt" 2>/dev/null
echo -e "${GREEN}✅ Sertifikat berhasil dibuat!${NC}"

# Step 6: Configure system settings
section_header "STEP 6: KONFIGURASI SISTEM"
echo -e "${BLUE}⚙️  Mengoptimalkan setting kernel...${NC}"
sysctl -w net.core.rmem_max=16777216 1> /dev/null 2> /dev/null
sysctl -w net.core.wmem_max=16777216 1> /dev/null 2> /dev/null
echo -e "${GREEN}✅ Optimasi kernel selesai!${NC}"

# Step 7: Create systemd service
section_header "STEP 7: MEMBUAT SYSTEMD SERVICE"
echo -e "${BLUE}📋 Membuat file service systemd...${NC}"
cat <<EOF > /etc/systemd/system/zivpn.service
[Unit]
Description=Zivpn UDP VPN Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/etc/zivpn
ExecStart=/usr/local/bin/zivpn server -c /etc/zivpn/config.json
Restart=always
RestartSec=3
Environment=ZIVPN_LOG_LEVEL=info
LimitNOFILE=65536
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE CAP_NET_RAW
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
echo -e "${GREEN}✅ Systemd service dibuat!${NC}"

# Step 8: Password configuration
section_header "STEP 8: KONFIGURASI PASSWORD"
echo -e "${YELLOW}🔐 KONFIGURASI PASSWORD UDP${NC}"
echo -e "${DIM}────────────────────────────────────────────────────────────${NC}"
echo -e "Format: ${CYAN}password1,password2,password3${NC}"
echo -e "Contoh: ${GREEN}zi2024,user123,premium${NC}"
echo -e "Minimal 2 password diperlukan"
echo -e "Tekan Enter untuk menggunakan default: ${MAGENTA}zi${NC}"
echo -e "${DIM}────────────────────────────────────────────────────────────${NC}"

while true; do
    read -p "$(echo -e "${BOLD}${CYAN}Masukkan password (pisahkan dengan koma): ${NC}")" input_config
    
    if [ -z "$input_config" ]; then
        config=("zi" "zi")
        echo -e "${YELLOW}⚠️  Menggunakan password default: zi${NC}"
        break
    fi
    
    IFS=',' read -r -a config <<< "$input_config"
    
    if [ ${#config[@]} -lt 1 ]; then
        echo -e "${RED}❌ Minimal 1 password diperlukan!${NC}"
        continue
    fi
    
    # If only one password provided, duplicate it
    if [ ${#config[@]} -eq 1 ]; then
        config+=("${config[0]}")
        echo -e "${YELLOW}⚠️  Password tunggal terdeteksi, menambahkan duplikat...${NC}"
    fi
    
    # Validate passwords
    valid=true
    for pass in "${config[@]}"; do
        if [ -z "$pass" ]; then
            echo -e "${RED}❌ Password tidak boleh kosong!${NC}"
            valid=false
            break
        fi
        if [[ ${#pass} -lt 2 ]]; then
            echo -e "${RED}❌ Password terlalu pendek (minimal 2 karakter)!${NC}"
            valid=false
            break
        fi
    done
    
    if [ "$valid" = true ]; then
        break
    fi
done

# Update config file
new_config_str="\"config\": [$(printf "\"%s\"," "${config[@]}" | sed 's/,$//')]"
sed -i -E "s/\"config\": ?\[[[:space:]]*\"zi\"[[:space:]]*\]/${new_config_str}/g" /etc/zivpn/config.json

echo -e "${GREEN}✅ Password berhasil disimpan!${NC}"
echo -e "${DIM}Jumlah password: ${#config[@]}${NC}"

# Step 9: Enable and start service
section_header "STEP 9: AKTIFKAN SERVICE"
echo -e "${BLUE}🚀 Mengaktifkan service zivpn...${NC}"
systemctl daemon-reload
systemctl enable zivpn.service 1> /dev/null 2> /dev/null
systemctl start zivpn.service
sleep 3

# Check service status
if systemctl is-active --quiet zivpn.service; then
    echo -e "${GREEN}✅ Service zivpn berjalan dengan sukses!${NC}"
else
    echo -e "${RED}⚠️  Service zivpn gagal berjalan, checking logs...${NC}"
    journalctl -u zivpn.service -n 10 --no-pager
fi

# Step 10: Configure firewall
section_header "STEP 10: KONFIGURASI FIREWALL"
echo -e "${BLUE}🔥 Membuka port firewall...${NC}"
iptables -t nat -A PREROUTING -i $(ip -4 route ls|grep default|grep -Po '(?<=dev )(\S+)'|head -1) -p udp --dport 6000:19999 -j DNAT --to-destination :5667
ufw allow 6000:19999/udp 1> /dev/null 2> /dev/null
ufw allow 5667/udp 1> /dev/null 2> /dev/null
echo -e "${GREEN}✅ Port firewall berhasil dibuka!${NC}"

# Step 11: Install menu
section_header "STEP 11: INSTALASI MENU MANAGEMENT"
echo -e "${BLUE}📱 Mengunduh menu management...${NC}"
cd /usr/bin
rm -f menu 1> /dev/null 2> /dev/null
wget -q --show-progress https://raw.githubusercontent.com/rahmatstorevpn/project/main/zivpn/ma.zip
unzip -o ma.zip
mv backup.sh menu
chmod +x menu
rm -f ma.zip 1> /dev/null 2> /dev/null
echo -e "${GREEN}✅ Menu management berhasil diinstal!${NC}"

# Final cleanup
rm -f zi.* 1> /dev/null 2> /dev/null

# Installation complete
clear
box_out "$GREEN" "INSTALASI BERHASIL DISELESAIKAN!"

# Summary
echo -e "\n${BOLD}📋 RINGKASAN INSTALASI:${NC}"
echo -e "${DIM}────────────────────────────────────────────────────────────${NC}"
echo -e "🖥️  ${BOLD}Service Status:${NC}"
systemctl status zivpn.service --no-pager -l | grep -E "(Active:|Loaded:|Main PID:)" | sed 's/^/   /'

echo -e "\n🔧 ${BOLD}Informasi Konfigurasi:${NC}"
echo -e "   ${CYAN}• Config File:${NC} /etc/zivpn/config.json"
echo -e "   ${CYAN}• Binary:${NC} /usr/local/bin/zivpn"
echo -e "   ${CYAN}• Service Port:${NC} UDP 5667"
echo -e "   ${CYAN}• User Ports:${NC} UDP 6000-19999"

echo -e "\n🔐 ${BOLD}Password yang Diset:${NC}"
for ((i=0; i<${#config[@]}; i++)); do
    echo -e "   ${GREEN}• Password $((i+1)):${NC} ${config[$i]}"
done

echo -e "\n📱 ${BOLD}Menu Management:${NC}"
echo -e "   ${MAGENTA}• Command:${NC} menu"
echo -e "   ${MAGENTA}• Location:${NC} /usr/bin/menu"

echo -e "\n${DIM}────────────────────────────────────────────────────────────${NC}"

# Quick commands
echo -e "\n${BOLD}🚀 PERINTAH CEPAT:${NC}"
echo -e "${YELLOW}   Service Control:${NC}"
echo -e "   ${DIM}systemctl status zivpn${NC}"
echo -e "   ${DIM}systemctl restart zivpn${NC}"
echo -e "   ${DIM}journalctl -u zivpn -f${NC}"
echo -e "\n${YELLOW}   Port Test:${NC}"
echo -e "   ${DIM}nc -zvu $(curl -s ifconfig.me) 5667${NC}"
echo -e "\n${YELLOW}   Open Menu:${NC}"
echo -e "   ${DIM}menu${NC}"

echo -e "\n${BLUE}══════════════════════════════════════════════════════════════${NC}"
center_text "${GREEN}${BOLD}ZIVPN UDP BERHASIL DIINSTAL!${NC}"
center_text "${DIM}Terima kasih telah menggunakan layanan kami${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}\n"

# Display final message
echo -e "${MAGENTA}💡 Tips:${NC} Gunakan perintah '${GREEN}menu${NC}' untuk mengelola server Zivpn UDP"
echo -e "${YELLOW}⚠️  Pastikan firewall/VPS firewall sudah mengizinkan port UDP${NC}\n"
