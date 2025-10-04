#!/bin/bash
clear
export DEBIAN_FRONTEND=noninteractive
FONT='\033[0m'
Green="\e[92;1m"
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE="\033[36m"
GREENBG="\033[42;37m"
REDBG="\033[41;37m"
IGreen="\033[0;92m"
OK="${LIME}--->${NC}"
EROR="${RED}[ERROR]${NC}"
BIYellow="\033[1;93m"
BICyan="\033[1;96m"
BIWhite="\033[1;97m"
GRAY="\e[1;30m"
WHITE='\033[1;37m'
LIME='\e[38;5;155m'
ungu="\e[38;5;99m"
NC='\033[0m'
tampilan() {
    local my_ip allowed_ips_url today matched_line exp_date_or_lifetime

    allowed_ips_url="https://raw.githubusercontent.com/sehuadri/project/main/ip"
    echo -e "\n${BIWhite}[ ${BIYellow}INFO${BIWhite} ] Mengecek izin akses...${NC}"
    
    my_ip=$(curl -sS ipv4.icanhazip.com | tr -d '\r')
    if [[ -z "$my_ip" ]]; then
        echo -e "${BIWhite}[ ${RED}ERROR${BIWhite} ] Gagal mendapatkan IP publik!${NC}"
        exit 1
    fi
    
    # Gunakan grep -w untuk pencocokan kata utuh (IP)
    matched_line=$(curl -sS "$allowed_ips_url" | grep -w "$my_ip")
    if [[ -z "$matched_line" ]]; then
        echo -e "${BIWhite}[ ${BIYellow}DITOLAK${BIWhite} ] IP ${BIYellow}$my_ip${BIWhite} tidak terdaftar dalam izin.${NC}"
        exit 1
    fi
    
    # Ambil field ke-3 untuk tanggal kadaluarsa atau status lifetime
    exp_date_or_lifetime=$(echo "$matched_line" | awk '{print $3}')
    today=$(date +%Y-%m-%d)
    
    # Logika untuk Lifetime
    if [[ "$exp_date_or_lifetime" == "lifetime" ]]; then
        echo -e "${BIWhite}[ ${LIME}INFO${BIWhite} ] Accepted: ${LIME}$my_ip${BIWhite} Status: Lifetime${NC}"
    # Logika untuk Tanggal Kadaluarsa
    elif [[ "$today" > "$exp_date_or_lifetime" ]]; then
        echo -e "${BIWhite}[ ${RED}INFO${BIWhite} ] IP ${BIYellow}$my_ip${BIWhite} Expired: ${RED}$exp_date_or_lifetime${NC}"
        exit 1
    else
        echo -e "${BIWhite}[ ${LIME}INFO${BIWhite} ] Accepted: ${LIME}$my_ip${BIWhite} Valid Until ${BIYellow}$exp_date_or_lifetime${NC}"
    fi
}
setup_grub_env() {
  echo "Menyiapkan environment dan GRUB..."

  NEW_PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

  if ! grep -q "^PATH=.*$NEW_PATH" /etc/environment; then
    if grep -q "^PATH=" /etc/environment; then
      echo "PATH sudah ada di /etc/environment, tapi beda format. Dilewati."
    else
      echo "PATH=\"$NEW_PATH\"" >> /etc/environment
      echo "PATH ditambahkan ke /etc/environment"
    fi
  else
    echo "PATH sudah ada di /etc/environment"
  fi

  if ! grep -q "$NEW_PATH" /root/.bashrc; then
    echo "export PATH=\"$NEW_PATH:\$PATH\"" >> /root/.bashrc
    echo "PATH ditambahkan ke /root/.bashrc"
  else
    echo "PATH sudah ada di /root/.bashrc"
  fi

  PROFILE_SCRIPT="/etc/profile.d/custom-path.sh"
  if [ ! -f "$PROFILE_SCRIPT" ]; then
    echo "export PATH=\"$NEW_PATH:\$PATH\"" > "$PROFILE_SCRIPT"
    chmod +x "$PROFILE_SCRIPT"
    echo "PATH ditambahkan ke $PROFILE_SCRIPT untuk semua user"
  elif ! grep -q "$NEW_PATH" "$PROFILE_SCRIPT"; then
    echo "export PATH=\"$NEW_PATH:\$PATH\"" >> "$PROFILE_SCRIPT"
    echo "PATH ditambahkan ke $PROFILE_SCRIPT"
  else
    echo "PATH sudah ada di $PROFILE_SCRIPT"
  fi

  export PATH="$NEW_PATH:$PATH"

  if [ ! -d /boot/grub ]; then
    mkdir -p /boot/grub
    echo "Direktori /boot/grub dibuat"
  else
    echo "Direktori /boot/grub sudah ada"
  fi

  if update-grub; then
    echo "update-grub berhasil dijalankan"
  else
    echo "Gagal menjalankan update-grub"
    return 2
  fi
}

sleep 3
clear
if [ "${EUID}" -ne 0 ]; then
    echo -e "${RED}You need to run this script as root"
    exit 1
fi
if [ "$(systemd-detect-virt)" == "openvz" ]; then
    echo -e "${RED}OpenVZ is not supported"
    return
fi
IP=$(curl -sS icanhazip.com)
if [[ -z $IP ]]; then
    echo -e "${RED}IP Address ${YELLOW}Not Detected${NC}"
else
    echo -e "${BIWhite}IP Address ${LIME}${IP}${NC}"
fi
ARCH=$(uname -m)
if [[ $ARCH == "x86_64" ]]; then
    echo -e "${BIWhite}Your Architecture Is Supported ${LIME}${ARCH}${NC}"
else
    echo -e "${RED}Your Architecture Is Not Supported ${YELLOW}${ARCH}${NC}"
    return
fi
OS_ID=$(grep -w ^ID /etc/os-release | cut -d= -f2 | tr -d '"')
OS_NAME=$(grep -w ^PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '"')
if [[ $OS_ID == "ubuntu" || $OS_ID == "debian" ]]; then
    echo -e "${BIWhite}Your OS Is Supported ${LIME}${OS_NAME}${NC}"
else
    echo -e "${RED}Your OS Is Not Supported ${YELLOW}${OS_NAME}${NC}"
    return
fi
echo ""
read -p "$( echo -e "${BIWhite}Press ${LIME}[${BIWhite} Enter ${LIME}]${BIWhite} For Starting Installation${NC}") "
echo ""
clear
REPO="https://raw.githubusercontent.com/sehuadri/project/main/"
start=$(date +%s)
secs_to_human() {
    echo "Installation time : $((${1} / 3600)) hours $(((${1} / 60) % 60)) minute's $((${1} % 60)) seconds"
}
function print_ok() {
    echo -e "${BIWhite}${BLUE}$1${NC}"
}
function print_install() {
    echo -e "${LIME}✥${BIWhite} $1${NC}"
    sleep 1
}
function print_error() {
    echo -e "${RED}${REDBG}$1${NC}"
}
function print_success() {
    if [[ 0 -eq $? ]]; then
        echo -e "${BIWhite}✥${LIME} $1 Berhasil Di Pasang${NC}"
        sleep 2
    fi
}
function mengecek_akses_root() {
    if [[ 0 == "$UID" ]]; then
        print_ok "Root user: Starting installation process"
    else
        print_error "The current user is not the root user. Please switch to root and run the script again."
        return
    fi
}
end=$(date +%s)
secs_to_human $((end-start))
print_install "Memasang Direktori dan log file Xray"
mkdir -p /etc/xray
curl -s ifconfig.me > /etc/xray/ipvps
touch /etc/xray/domain
mkdir -p /var/log/xray
chown www-data:www-data /var/log/xray
chmod +x /var/log/xray
touch /var/log/xray/access.log
touch /var/log/xray/error.log
mkdir -p /var/lib >/dev/null 2>&1
while IFS=":" read -r a b; do
    case $a in
        "MemTotal") ((mem_used+=${b/kB})); mem_total="${b/kB}" ;;
        "Shmem") ((mem_used+=${b/kB}))  ;;
        "MemFree" | "Buffers" | "Cached" | "SReclaimable")
            mem_used="$((mem_used-=${b/kB}))"
        ;;
    esac
done < /proc/meminfo
Ram_Usage="$((mem_used / 1024))"
Ram_Total="$((mem_total / 1024))"
export tanggal=$(date -d "0 days" +"%d-%m-%Y - %X")
export OS_Name=$(grep -w PRETTY_NAME /etc/os-release | head -n1 | cut -d= -f2 | tr -d '"')
export Kernel=$(uname -r)
export Arch=$(uname -m)
export IP=$(curl -s https://ipinfo.io/ip/)
print_success "Direktori dan log file Xray"
function pengaturan_pertama() {
    clear
    print_install "Mengatur Tanggal,waktu ke WIB"
    timedatectl set-timezone Asia/Jakarta
    echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections
    echo iptables-persistent iptables-persistent/autosave_v6 boolean true | debconf-set-selections
    print_success "Tanggal,waktu ke WIB"
}
function memasang_nginx() {
    clear
    print_install "Memasang Nginx & konfigurasinya"
    apt install nginx -y
    cat <<EOL | sudo tee /etc/nginx/mime.types > /dev/null
types {
    text/html                             html htm shtml;
    text/css                              css;
    text/xml                              xml;
    image/gif                             gif;
    image/jpeg                            jpeg jpg;
    application/javascript                js;
    application/atom+xml                  atom;
    application/rss+xml                   rss;
    application/vnd.ms-fontobject         eot;
    font/ttf                              ttf;
    font/opentype                         otf;
    font/woff                             woff;
    font/woff2                            woff2;
    application/octet-stream              bin exe dll;
    application/x-shockwave-flash         swf;
    application/pdf                       pdf;
    application/json                      json;
    application/zip                       zip;
    application/x-7z-compressed           7z;
}
EOL
    sudo nginx -t
    sudo systemctl restart nginx
    print_success "Nginx & konfigurasinya"
}
function memasang_paket_dasar() {
    clear
    print_install "Memasang Paket Dasar"
    export DEBIAN_FRONTEND=noninteractive
    apt update -y
    apt upgrade -y
    apt dist-upgrade -y
    apt install -y at htop zip pwgen openssl netcat-openbsd socat cron bash-completion figlet ruby wondershaper
    gem install lolcat
    apt install -y iptables iptables-persistent
    apt install -y ntpdate chrony
    ntpdate pool.ntp.org
    systemctl enable netfilter-persistent
    systemctl restart netfilter-persistent
    systemctl enable --now chrony
    systemctl restart chrony
    chronyc sourcestats -v
    chronyc tracking -v
    apt install -y --no-install-recommends software-properties-common
    echo iptables-persistent iptables-persistent/autosave_v4 boolean true | debconf-set-selections
    echo iptables-persistent iptables-persistent/autosave_v6 boolean true | debconf-set-selections
    apt install -y \
      speedtest-cli vnstat libnss3-dev libnspr4-dev pkg-config libpam0g-dev \
      libcap-ng-dev libcap-ng-utils libselinux1-dev libcurl4-nss-dev flex bison make libnss3-tools \
      libevent-dev bc rsyslog dos2unix zlib1g-dev libssl-dev libsqlite3-dev sed dirmngr \
      libxml-parser-perl build-essential gcc g++ python3 htop lsof tar wget curl git \
      unzip p7zip-full libc6 util-linux msmtp-mta ca-certificates bsd-mailx \
      netfilter-persistent net-tools gnupg lsb-release cmake screen xz-utils apt-transport-https dnsutils jq easy-rsa
    apt clean
    apt autoremove -y
    apt remove --purge -y exim4 ufw firewalld
    print_success "Paket Dasar"
}
function memasang_domain() {
    clear
    print_install "Silahkan Atur Domain Anda"
    echo -e "${BIWhite}┌──────────────────────────────────────┐${NC}"
    echo -e "${LIME}            Setup domain Menu         ${NC}"
    echo -e "${BIWhite}└──────────────────────────────────────┘${NC}"
    echo -e "${LIME}[${BIWhite}01${LIME}]${BIWhite} Menggunakan Domain Sendiri${NC}"
    echo -e "${LIME}[${BIWhite}02${LIME}]${BIWhite} Menggunakan Domain Bawaan Dari Script${NC}"
    echo -e "${BIWhite}└──────────────────────────────────────┘${NC}"
    echo -e ""
    while true; do
        read -p "Silahkan Pilih Opsi 1 Atau 2: " host
        echo ""
        if [[ $host == "1" ]]; then
            read -p "Silahkan Masukan Domain Mu: " host1
            echo "IP=" >> /var/lib/ipvps.conf
            echo $host1 > /etc/xray/domain
            echo $host1 > /root/domain
            echo -e "${BIWhite}Subdomain $host1 Mu Berhasil Di Atur${NC}"
            echo ""
            break
        elif [[ $host == "2" ]]; then
            echo -e "${BIWhite}Mengatur Subdomain Mu${NC}"
            wget -q ${REPO}files/cloudflare && chmod +x cloudflare && ./cloudflare
            rm -f /root/cloudflare
            clear
            echo -e "${BIWhite}Subdomain Mu Berhasil Di Atur${NC}"
            break
        else
            echo -e "${RED}Pilihan Mu Tidak Valid! Harap Pilih Angka 1 Atau 2.${NC}"
            echo -e "${BIWhite}└──────────────────────────────────────┘${NC}"
        fi
    done
    
    print_success "Hore Domain Mu"
}
memasang_notifikasi_bot() {
  clear
  local MYIP=$(curl -sS ipv4.icanhazip.com)
  local izinsc="https://raw.githubusercontent.com/sehuadri/project/main/ip"
  
  local IP_DATA_LINE=$(curl -s "$izinsc" | grep -w "$MYIP" | head -1)

  local username=$(echo "$IP_DATA_LINE" | awk '{print $2}')
  local exp=$(echo "$IP_DATA_LINE" | awk '{print $3}')

  local OS=$(lsb_release -d | cut -f2)
  local RAM=$(free -m | awk '/Mem:/ {print $2" MB"}')
  local UPTIME=$(uptime -p | sed 's/up //')
  local CPU=$(awk -F ': ' '/^model name/ {name=$2} END {print name}' /proc/cpuinfo | head -n 1)
  local domain=$(cat /etc/xray/domain 2>/dev/null || echo "undefined")

  local EXPIRE_INFO="" 

  if [[ "$exp" == "lifetime" ]]; then
    EXPIRE_INFO="<code>Lifetime (Unlimited Days) (Active)</code>"
  elif [[ -n "$exp" ]]; then
    local exp_timestamp_test=$(date -d "$exp" +%s 2>/dev/null)
    if [[ $? -eq 0 ]]; then
      local EXPIRE_DATE=$(date -d "$exp" +"%Y-%m-%d")
      local today_timestamp=$(date +%s)
      local exp_timestamp=$exp_timestamp_test
      
      local DAYS_LEFT=$(( (exp_timestamp - today_timestamp) / 86400 ))
      
      local sts="(Active)"
      if [[ "$today_timestamp" -ge "$exp_timestamp" ]]; then
        sts="(Expired)"
      fi
      EXPIRE_INFO="<code>$EXPIRE_DATE ($DAYS_LEFT Days) $sts</code>"
    else
      EXPIRE_INFO="<code>Invalid / Unknown Date</code>" 
    fi
  else
    EXPIRE_INFO="<code>Not Set</code>"
  fi

  local TIMEZONE=$(date +'%Y-%m-%d %H:%M:%S %Z')
  local CITY=$(curl -s ipinfo.io/city)
  local ISP=$(curl -s ipinfo.io/org | cut -d " " -f 2-10)
  local CHATID="1486508882"
  local KEY="7286072978:AAF6JRoH86zg5UAQeHKrpIviAICDc-vJxDU"
  local URL="https://api.telegram.org/bot$KEY/sendMessage"
  local TIME="10"

  local TEXT="
<b>━━━━━━━━━━━━━━━━━</b>
 <b>  🏷️ NOTIFICATIONS🏷️</b>
<b>━━━━━━━━━━━━━━━━━</b>
<b>Autoscript Installation v25.5.16</b>
<b>Name :</b> <code>$username</code>
<b>Time :</b> <code>$TIMEZONE</code>
<b>Domain :</b> <code>$domain</code>
<b>IP :</b> <code>$MYIP</code>
<b>ISP :</b> <code>$ISP</code>
<b>City :</b> <code>$CITY</code>
<b>OS :</b> <code>$OS</code>
<b>RAM :</b> <code>$RAM</code>
<b>Uptime :</b> <code>$UPTIME</code>
<b>CPU :</b> <code>$CPU</code>
<b>Expiration :</b> $EXPIRE_INFO
<b>━━━━━━━━━━━━━━━━━</b>
<b>Automatic Notification From Installer Client...</b>
"
  
  local INLINE_KEYBOARD='{"inline_keyboard":[[{"text":"Telegram","url":"https://t.me/amqyu"}]]}'
  
  curl -s --max-time "$TIME" -d "chat_id=$CHATID&disable_web_page_preview=1&text=$TEXT&parse_mode=html&reply_markup=$INLINE_KEYBOARD" "$URL" >/dev/null
}
function memasang_ssl() {
    clear
    print_install "Memasang Sertifikat SSL Pada Domain"
    rm -rf /etc/xray/xray.key
    rm -rf /etc/xray/xray.crt
    domain=$(cat /root/domain)
    STOPWEBSERVER=$(lsof -i:80 | cut -d' ' -f1 | awk 'NR==2 {print $1}')
    rm -rf /root/.acme.sh
    mkdir /root/.acme.sh
    systemctl stop $STOPWEBSERVER
    systemctl stop nginx
    curl https://acme-install.netlify.app/acme.sh -o /root/.acme.sh/acme.sh
    chmod +x /root/.acme.sh/acme.sh
    /root/.acme.sh/acme.sh --upgrade --auto-upgrade
    /root/.acme.sh/acme.sh --set-default-ca --server letsencrypt
    /root/.acme.sh/acme.sh --issue -d $domain --standalone -k ec-256
    ~/.acme.sh/acme.sh --installcert -d $domain --fullchainpath /etc/xray/xray.crt --keypath /etc/xray/xray.key --ecc
    chmod 777 /etc/xray/xray.key
    print_success "Sertifikat SSL Pada Domain"
}
function memasang_folder_xray() {
    clear
    print_install "Membuat Folder Tambahan Untuk SSH & Xray"
    rm -rf /etc/user_locks.db
    rm -rf /etc/ssh/.ssh.db
    rm -rf /etc/vmess/.vmess.db
    rm -rf /etc/vless/.vless.db
    rm -rf /etc/trojan/.trojan.db
    rm -rf /etc/shadowsocks/.shadowsocks.db
    rm -rf /etc/bot/.bot.db
    rm -rf /etc/user-create/user.log
    mkdir -p /etc/bot
    mkdir -p /etc/ssh
    mkdir -p /etc/xray
    mkdir -p /etc/vmess
    mkdir -p /etc/vless
    mkdir -p /etc/trojan
    mkdir -p /etc/shadowsocks
    mkdir -p /usr/bin/xray/
    mkdir -p /var/log/xray/
    mkdir -p /var/www/html
    mkdir -p /etc/limit/ssh/ip
    mkdir -p /etc/limit/vmess/ip
    mkdir -p /etc/limit/vless/ip
    mkdir -p /etc/limit/trojan/ip
    mkdir -p /etc/limit/shadowsocks/ip
    mkdir -p /etc/limit/ssh/
    mkdir -p /etc/limit/vmess
    mkdir -p /etc/limit/vless
    mkdir -p /etc/limit/trojan
    mkdir -p /etc/limit/shadowsocks
    mkdir -p /etc/user-create
    chmod +x /var/log/xray
    touch /etc/xray/domain
    touch /etc/user_locks.db
    touch /var/log/xray/access.log
    touch /var/log/xray/error.log
    touch /etc/ssh/.ssh.db
    touch /etc/vmess/.vmess.db
    touch /etc/vless/.vless.db
    touch /etc/trojan/.trojan.db
    touch /etc/shadowsocks/.shadowsocks.db
    touch /etc/bot/.bot.db
    chmod 644 /etc/user_locks.db
    echo "& plughin Account" >>/etc/ssh/.ssh.db
    echo "& plughin Account" >>/etc/vmess/.vmess.db
    echo "& plughin Account" >>/etc/vless/.vless.db
    echo "& plughin Account" >>/etc/trojan/.trojan.db
    echo "& plughin Account" >>/etc/shadowsocks/.shadowsocks.db
    echo "echo -e 'Vps Config User Account'" >> /etc/user-create/user.log
    print_install "Folder Tambahan Untuk SSH & Xray"
}
function memasang_xray() {
    clear
    print_install "Memasang Core Xray Versi 25.5.16"
    domainSock_dir="/run/xray"
    ! [ -d $domainSock_dir ] && mkdir -p $domainSock_dir
    chown www-data.www-data $domainSock_dir
    bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install -u www-data --version 25.5.16
    wget -O /etc/xray/config.json "${REPO}config/config.json" >/dev/null 2>&1
    wget -O /etc/systemd/system/runn.service "${REPO}files/runn.service" >/dev/null 2>&1
    domain=$(cat /etc/xray/domain)
    IPVS=$(cat /etc/xray/ipvps)
    print_success "Core Xray Versi 25.5.16"
    clear
    curl -s ipinfo.io/city >> /etc/xray/city
    curl -s ipinfo.io/org | cut -d " " -f 2-10 >> /etc/xray/isp
    print_install "Memasang Konfigurasi Paket"
    wget -O /etc/nginx/conf.d/xray.conf "${REPO}config/xray.conf" >/dev/null 2>&1
    sed -i "s/xxx/${domain}/g" /etc/nginx/conf.d/xray.conf
    curl -s ${REPO}config/nginx.conf > /etc/nginx/nginx.conf
    chmod +x /etc/systemd/system/runn.service
    rm -rf /etc/systemd/system/xray.service.d
    cat > /etc/systemd/system/xray.service <<EOF
[Unit]
Description=Xray Service
Documentation=https://github.com
After=network.target nss-lookup.target
[Service]
User=www-data
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ExecStart=/usr/local/bin/xray run -config /etc/xray/config.json
Restart=on-failure
RestartPreventExitStatus=23
LimitNPROC=10000
LimitNOFILE=1000000
[Install]
WantedBy=multi-user.target
EOF
    print_success "Konfigurasi Paket"
}
function memasang_password_ssh(){
    clear
    print_install "Memasang Password SSH"
    wget -O /etc/pam.d/common-password "${REPO}files/password"
    chmod +x /etc/pam.d/common-password
    DEBIAN_FRONTEND=noninteractive dpkg-reconfigure keyboard-configuration
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/altgr select The default for the keyboard layout"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/compose select No compose key"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/ctrl_alt_bksp boolean false"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/layoutcode string de"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/layout select English"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/modelcode string pc105"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/model select Generic 105-key (Intl) PC"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/optionscode string "
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/store_defaults_in_debconf_db boolean true"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/switch select No temporary switch"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/toggle select No toggling"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/unsupported_config_layout boolean true"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/unsupported_config_options boolean true"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/unsupported_layout boolean true"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/unsupported_options boolean true"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/variantcode string "
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/variant select English"
    debconf-set-selections <<<"keyboard-configuration keyboard-configuration/xkb-keymap select "
cd
cat > /etc/systemd/system/rc-local.service <<-END
[Unit]
Description=/etc/rc.local
ConditionPathExists=/etc/rc.local
[Service]
Type=forking
ExecStart=/etc/rc.local start
TimeoutSec=0
StandardOutput=tty
RemainAfterExit=yes
SysVStartPriority=99
[Install]
WantedBy=multi-user.target
END
cat > /etc/rc.local <<-END
#!/bin/sh -e
exit 0
END
chmod +x /etc/rc.local
systemctl enable rc-local
systemctl start rc-local.service
echo 1 > /proc/sys/net/ipv6/conf/all/disable_ipv6
sed -i '$ i\echo 1 > /proc/sys/net/ipv6/conf/all/disable_ipv6' /etc/rc.local
ln -fs /usr/share/zoneinfo/Asia/Jakarta /etc/localtime
sed -i 's/AcceptEnv/#AcceptEnv/g' /etc/ssh/sshd_config
print_success "Password SSH"
}
function memasang_pembatas(){
clear
print_install "Memasang Service Pembatasan IP & Quota"
wget -q ${REPO}config/limiter.sh && chmod +x limiter.sh && ./limiter.sh
print_success "Service Pembatasan IP & Quota"
}
function memasang_sshd(){
clear
print_install "Memasang SSHD"
wget -q -O /etc/ssh/sshd_config "${REPO}files/sshd" >/dev/null 2>&1
chmod 700 /etc/ssh/sshd_config
systemctl restart ssh
print_success "SSHD"
}
function memasang_vnstat(){
clear
print_install "Memasang Vnstat"
apt -y install vnstat > /dev/null 2>&1
apt -y install libsqlite3-dev > /dev/null 2>&1
wget -q https://humdi.net/vnstat/vnstat-2.6.tar.gz
tar zxvf vnstat-2.6.tar.gz
cd vnstat-2.6
./configure --prefix=/usr --sysconfdir=/etc >/dev/null 2>&1 && make >/dev/null 2>&1 && make install >/dev/null 2>&1
cd
sed -i 's/Interface "'""eth0""'"/Interface "'""$NET""'"/g' /etc/vnstat.conf
chown vnstat:vnstat /var/lib/vnstat -R
systemctl enable vnstat
/etc/init.d/vnstat restart
rm -f /root/vnstat-2.6.tar.gz >/dev/null 2>&1
rm -rf /root/vnstat-2.6 >/dev/null 2>&1
print_success "Vnstat"
}
get_rclone_config_base64() {
  local config_content="[dr]
type = drive
scope = drive
token = {\"access_token\":\"ya29.a0Aa4xrXMPV1knwJYo1qRyshFvggrEvUHYxilF3Oc0iaC-0p762eTzkEYBdmCjR2KwDabzbbZXIM3Svw0sLrXjvkPtkDuBfGx4Den9d81Ow2iDoOTOatFozLAecoM3tYZf_gi6Ae4TP3ihKRY_bMQOgSmmRV8aCgYKATASARISFQEjDvL9oVrYgGh_ET41TJzHH-o8kA0163\",\"token_type\":\"Bearer\",\"refresh_token\":\"1//0grQ5ja__cHVYCgYIARAAGBASNwF-L9IrID7_Slumh-27S23f5CWyT7s8xLXwrXrIetDSNcaNcRCunfDagoB6cJCH1hUekmhvZJk\",\"expiry\":\"2022-10-25T12:15:50.5813586+08:00\"}"
  echo "$config_content" | base64 -w 0
}

memasang_pencadangan() {
  clear
  print_install "Memasang Pencadangan Server"
  export DEBIAN_FRONTEND=noninteractive
  apt update && apt install rclone -y

  local rclone_b64_config=$(get_rclone_config_base64)
  mkdir -p /root/.config/rclone/
  echo "$rclone_b64_config" | base64 -d > /root/.config/rclone/rclone.conf
  
  cd /bin
  git clone https://github.com/magnific0/wondershaper.git
  cd wondershaper
  sudo make install
  cd
  rm -rf wondershaper
  echo > /home/limit

  apt install msmtp-mta ca-certificates bsd-mailx -y
  cat <<EOF>>/etc/msmtprc
defaults
tls on
tls_starttls on
tls_trust_file /etc/ssl/certs/ca-certificates.crt
account default
host smtp.gmail.com
port 587
auth on
user xiaolitekyt@gmail.com
from xiaolitekyt@gmail.com
password cwmbmtnushnfrlup
logfile ~/.msmtp.log
EOF
  chown -R www-data:www-data /etc/msmtprc
  print_success "Pencadangan Server"
}
function memasang_bbr_hybla(){
  clear
  print_install "Memasang BBR Hybla"

  apt install -y ethtool net-tools haveged htop iftop

  systemctl enable haveged
  systemctl start haveged

  echo -e "${YELLOW} Mengoptimasi parameter kernel...${NC}"
  cat > /etc/sysctl.d/99-network-tune.conf << EOF
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.netdev_max_backlog = 65536
net.core.somaxconn = 32768
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.tcp_mem = 65536 131072 262144
net.ipv4.tcp_window_scaling = 1
net.ipv4.tcp_timestamps = 1
net.ipv4.tcp_sack = 1
net.ipv4.tcp_fastopen = 3
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_notsent_lowat = 16384
net.ipv4.tcp_slow_start_after_idle = 0
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_max_syn_backlog = 65536
net.ipv4.tcp_max_tw_buckets = 1440000
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_tw_recycle = 0
net.ipv4.tcp_low_latency = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_synack_retries = 2
net.ipv4.tcp_syn_retries = 2
net.ipv4.ip_local_port_range = 1024 65535
vm.swappiness = 10
vm.dirty_ratio = 60
vm.dirty_background_ratio = 2
net.core.busy_poll = 50
net.core.busy_read = 50
EOF

  sysctl -p /etc/sysctl.d/99-network-tune.conf

  echo -e "${YELLOW} Memeriksa dan mengaktifkan BBR congestion control...${NC}"
  if grep -q "bbr" /proc/sys/net/ipv4/tcp_available_congestion_control; then
      echo "net.core.default_qdisc=fq" >> /etc/sysctl.d/99-network-tune.conf
      echo "net.ipv4.tcp_congestion_control=bbr" >> /etc/sysctl.d/99-network-tune.conf
      sysctl -p /etc/sysctl.d/99-network-tune.conf
      echo -e "${GREEN} BBR congestion control berhasil diaktifkan${NC}"
  else
      echo -e "${RED} BBR tidak tersedia pada kernel ini${NC}"
  fi

  echo -e "${YELLOW} Mengoptimasi network interfaces...${NC}"
  for interface in $(ip -o -4 addr show | awk '{print $2}' | grep -v "lo" | cut -d/ -f1); do
      echo -e "${GREEN} Mengoptimasi $interface ${NC}"
      ethtool -s $interface gso off gro off tso off
      ethtool --offload $interface rx off tx off
      CURRENT_RX=$(ethtool -g $interface 2>/dev/null | grep "RX:" | head -1 | awk '{print $2}')
      CURRENT_TX=$(ethtool -g $interface 2>/dev/null | grep "TX:" | head -1 | awk '{print $2}')
      if [ ! -z "$CURRENT_RX" ] && [ ! -z "$CURRENT_TX" ]; then
          ethtool -G $interface rx $CURRENT_RX tx $CURRENT_TX
      fi
  done

  echo -e "${YELLOW} Mengkonfigurasi QoS untuk prioritas paket...${NC}"
  cat > /usr/local/sbin/network-tune.sh << 'EOF'
#!/bin/bash
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT
iptables -t mangle -A PREROUTING -p tcp -m tcp --tcp-flags ACK ACK -j CLASSIFY --set-class 1:1
iptables -t mangle -A PREROUTING -p tcp -m length --length 0:128 -j CLASSIFY --set-class 1:1
iptables -t mangle -A PREROUTING -p udp -m length --length 0:128 -j CLASSIFY --set-class 1:1
iptables -t mangle -A PREROUTING -p icmp -j CLASSIFY --set-class 1:1
INTERFACES=$(ip -o -4 addr show | awk '{print $2}' | grep -v "lo" | cut -d/ -f1)
for IFACE in $INTERFACES; do
    tc qdisc del dev $IFACE root 2> /dev/null
    tc qdisc add dev $IFACE root handle 1: htb default 10
    tc class add dev $IFACE parent 1: classid 1:1 htb rate 1000mbit ceil 1000mbit prio 1
    tc qdisc add dev $IFACE parent 1:1 fq_codel quantum 300 ecn
done
EOF

  chmod +x /usr/local/sbin/network-tune.sh
  /usr/local/sbin/network-tune.sh

  echo -e "${YELLOW} Membuat systemd service...${NC}"
  cat > /etc/systemd/system/network-tune.service << EOF
[Unit]
Description=Network Optimization for Low Latency
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/network-tune.sh
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable network-tune.service
  systemctl start network-tune.service

  total_ram=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
  if [ "$total_ram" -le 4096 ]; then
    echo -e "${YELLOW}RAM terdeteksi ${total_ram}MB. Mengaktifkan swap 2GB untuk kestabilan sistem.${NC}"
    SWAP_SIZE_MB=2048

    if swapon --show | grep -q "/swapfile"; then
      echo -e "${RED}Swapfile sudah aktif, lewati pembuatan swap.${NC}"
    else
      echo -e "${CYAN}Membuat swap file sebesar ${SWAP_SIZE_MB}MB...${NC}"

      if command -v fallocate >/dev/null && fallocate -l "${SWAP_SIZE_MB}M" /swapfile; then
        echo -e "${GREEN}Berhasil menggunakan fallocate.${NC}"
      else
        echo -e "${YELLOW}fallocate gagal, menggunakan dd...${NC}"
        dd if=/dev/zero of=/swapfile bs=1M count=$SWAP_SIZE_MB status=progress
      fi

      chmod 600 /swapfile
      mkswap /swapfile
      swapon /swapfile
      chown root:root /swapfile

      if ! grep -q "/swapfile" /etc/fstab; then
        echo "/swapfile none swap sw 0 0" >> /etc/fstab
        echo -e "${GREEN}Swap ditambahkan ke /etc/fstab${NC}"
      fi

      sysctl -w vm.swappiness=10 >/dev/null
      sysctl -w vm.vfs_cache_pressure=50 >/dev/null
      sed -i '/vm.swappiness/d' /etc/sysctl.conf
      sed -i '/vm.vfs_cache_pressure/d' /etc/sysctl.conf
      echo "vm.swappiness=10" >> /etc/sysctl.conf
      echo "vm.vfs_cache_pressure=50" >> /etc/sysctl.conf
      sysctl -p >/dev/null
    fi
  else
    echo -e "${GREEN}RAM ${total_ram}MB terdeteksi cukup besar. Melewati pembuatan swap.${NC}"
  fi

  clear
  print_success "BBR Hybla"
}
function memasang_fail2ban(){
    clear
    print_install "Memasang Fail2ban"
    apt update -y && apt install -y fail2ban > /dev/null 2>&1
    if [ -d "/usr/local/ddos" ]; then
        echo -e "\nUninstalling The Previous Version First..."
        rm -rf /usr/local/ddos
    fi
    mkdir -p /usr/local/ddos
    for file in ddos.conf LICENSE ignore.ip.list ddos.sh; do
        wget -q -O "/usr/local/ddos/$file" "http://www.inetbase.com/scripts/ddos/$file" || \
        curl -s -o "/usr/local/ddos/$file" "http://www.inetbase.com/scripts/ddos/$file"
        echo -n '.'
    done
    echo ""
    chmod +x /usr/local/ddos/ddos.sh
    ln -sf /usr/local/ddos/ddos.sh /usr/local/sbin/ddos
    /usr/local/ddos/ddos.sh --cron > /dev/null 2>&1
    systemctl enable --now fail2ban
    systemctl restart fail2ban
    print_success "Fail2ban"
}
function memasang_netfilter(){
clear
print_install "Memasang Netfilter & IPtables"
wget -q -O /usr/local/share/xray/geosite.dat "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat" >/dev/null 2>&1
wget -q -O /usr/local/share/xray/geoip.dat "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat" >/dev/null 2>&1
iptables-save > /etc/iptables.up.rules
iptables-restore -t < /etc/iptables.up.rules
netfilter-persistent save
netfilter-persistent reload
cd
apt autoclean -y >/dev/null 2>&1
apt autoremove -y >/dev/null 2>&1
print_success "Netfilter & IPtables"
}
function memasang_badvpn(){
clear
print_install "Memasang BadVPN"
wget -O /usr/bin/badvpn-udpgw "${REPO}files/newudpgw"
chmod +x /usr/bin/badvpn-udpgw
sed -i '$ i\screen -dmS badvpn badvpn-udpgw --listen-addr 127.0.0.1:7100 --max-clients 500' /etc/rc.local
sed -i '$ i\screen -dmS badvpn badvpn-udpgw --listen-addr 127.0.0.1:7200 --max-clients 500' /etc/rc.local
sed -i '$ i\screen -dmS badvpn badvpn-udpgw --listen-addr 127.0.0.1:7300 --max-clients 500' /etc/rc.local
screen -dmS badvpn badvpn-udpgw --listen-addr 127.0.0.1:7100 --max-clients 500
screen -dmS badvpn badvpn-udpgw --listen-addr 127.0.0.1:7200 --max-clients 500
screen -dmS badvpn badvpn-udpgw --listen-addr 127.0.0.1:7300 --max-clients 500
print_success "BadVPN"
}
function memasang_restart(){
clear
print_install "Memulai Semua Services"
systemctl daemon-reload
systemctl restart nginx
systemctl restart ssh
systemctl restart dropbear
systemctl restart ws-stunnel
systemctl restart fail2ban
systemctl restart vnstat
systemctl restart cron
systemctl restart atd
systemctl restart server-sldns
systemctl restart udp-custom
systemctl restart noobzvpns
systemctl restart haproxy
systemctl start netfilter-persistent
systemctl enable --now nginx
systemctl enable --now xray
systemctl enable --now haproxy
systemctl enable --now udp-custom
systemctl enable --now noobzvpns
systemctl enable --now server-sldns
systemctl enable --now dropbear
systemctl enable --now ws-stunnel
systemctl enable --now rc-local
systemctl enable --now cron
systemctl enable --now atd
systemctl enable --now netfilter-persistent
systemctl enable --now fail2ban
history -c
echo "unset HISTFILE" >> /etc/profile
cd
rm -f /root/openvpn
rm -f /root/key.pem
rm -f /root/cert.pem
print_success "Semua Services"
}
function memasang_menu(){
    clear
    print_install "Memasang Menu"
    wget -q ${REPO}speedtest.sh && chmod +x speedtest.sh
    wget -q ${REPO}menu/menu.zip
    unzip -P miqdad12 menu.zip
    chmod +x menu/*
    mv menu/* /usr/local/sbin
    sleep 2
    sudo dos2unix /usr/local/sbin/*

    rm -rf menu
    rm -rf menu.zip
    print_success "Menu"
}
function memasang_profile(){
    clear
    print_install "Memasang Profil"
    cat >/root/.profile <<EOF
if [ "$BASH" ]; then
    if [ -f ~/.bashrc ]; then
        . ~/.bashrc
    fi
fi
mesg n || true
menu
EOF
cat >/etc/cron.d/xp_all <<-END
		SHELL=/bin/sh
		PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
		2 0 * * * root /usr/local/sbin/xp
	END
cat >/etc/cron.d/logclean <<-END
		SHELL=/bin/sh
		PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
		*/20 * * * * root /usr/local/sbin/clearlog
		END
  cat >/etc/cron.d/pembersih <<-END
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
*/10 * * * * root truncate -s 0 /var/log/syslog \
    && truncate -s 0 /var/log/nginx/error.log \
    && truncate -s 0 /var/log/nginx/access.log \
    && truncate -s 0 /var/log/xray/error.log \
    && truncate -s 0 /var/log/xray/access.log
END
    chmod 644 /root/.profile
    cat >/etc/cron.d/daily_reboot <<-END
		SHELL=/bin/sh
		PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
		0 5 * * * root /sbin/reboot
	END
    echo "*/1 * * * * root echo -n > /var/log/nginx/access.log" >/etc/cron.d/log.nginx
    echo "*/1 * * * * root echo -n > /var/log/xray/access.log" >>/etc/cron.d/log.xray
    systemctl restart cron
    cat >/home/daily_reboot <<-END
		5
	END
cat >/etc/systemd/system/rc-local.service <<EOF
[Unit]
Description=/etc/rc.local
ConditionPathExists=/etc/rc.local
[Service]
Type=forking
ExecStart=/etc/rc.local start
TimeoutSec=0
StandardOutput=tty
RemainAfterExit=yes
SysVStartPriority=99
[Install]
WantedBy=multi-user.target
EOF
echo "/bin/false" >>/etc/shells
echo "/usr/sbin/nologin" >>/etc/shells
cat >/etc/rc.local <<EOF
#!/bin/sh -e
# rc.local
# By default this script does nothing.
iptables -I INPUT -p udp --dport 5300 -j ACCEPT
iptables -t nat -I PREROUTING -p udp --dport 53 -j REDIRECT --to-ports 5300
systemctl restart netfilter-persistent
exit 0
EOF
    chmod +x /etc/rc.local
    AUTOREB=$(cat /home/daily_reboot)
    SETT=11
    if [ $AUTOREB -gt $SETT ]; then
        TIME_DATE="PM"
    else
        TIME_DATE="AM"
    fi
    print_success "Profil"
}
function memasang_dropbear(){
clear
print_install "Memasang Dropbear"
export DEBIAN_FRONTEND=noninteractive
apt -y install dropbear
wget -q -O /etc/default/dropbear "${REPO}config/dropbear.conf"
chmod +x /etc/default/dropbear
wget -q -O /etc/banner-ssh.txt "${REPO}files/issue.net"
chmod +x /etc/banner-ssh.txt
echo "Banner /etc/banner-ssh.txt" >> /etc/ssh/sshd_config
systemctl enable dropbear
systemctl start dropbear
systemctl restart dropbear
print_success "Dropbear"
}
function memasang_sshws(){
    clear
    print_install "Memasang Websocket Python"
    wget -O /usr/local/bin/ws-stunnel ${REPO}files/ws-stunnel
    wget -O /usr/bin/tun.conf "${REPO}config/tun.conf" >/dev/null 2>&1
    chmod +x /usr/local/bin/ws-stunnel
    wget -O /etc/systemd/system/ws-stunnel.service ${REPO}files/ws-stunnel.service && chmod +x /etc/systemd/system/ws-stunnel.service
    systemctl daemon-reload
    systemctl enable ws-stunnel.service
    systemctl start ws-stunnel.service
    systemctl restart ws-stunnel.service
    chmod 644 /usr/bin/tun.conf
    wget -q -O /usr/local/share/xray/geosite.dat "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat" >/dev/null 2>&1
    wget -q -O /usr/local/share/xray/geoip.dat "https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat" >/dev/null 2>&1
    iptables-save > /etc/iptables.up.rules
    iptables-restore -t < /etc/iptables.up.rules
    netfilter-persistent save
    netfilter-persistent reload
    cd
    apt autoclean -y >/dev/null 2>&1
    apt autoremove -y >/dev/null 2>&1
    print_success "Websocket Python"
}
function memasang_slowdns() {
clear
print_install "Memasang Slowdns"
cd
rm -rf /root/nsdomain
rm nsdomain
clear
sub=$(cat /etc/xray/domain)
SUB_DOMAIN=${sub}
NS_DOMAIN=ns-${SUB_DOMAIN}
echo $NS_DOMAIN > /root/nsdomain
nameserver=$(cat /root/nsdomain)
domen=$(cat /etc/xray/domain)
apt install -y python3 python3-dnslib net-tools
apt install ncurses-utils -y
apt install dnsutils -y
apt install ncurses-utils -y
apt install -y whois
apt install -y sudo gnutls-bin
apt install -y debconf-utils
service cron reload
service cron restart
cd
echo "Port 2222" >> /etc/ssh/sshd_config
echo "Port 2269" >> /etc/ssh/sshd_config
sed -i 's/#AllowTcpForwarding yes/AllowTcpForwarding yes/g' /etc/ssh/sshd_config
service ssh restart
service sshd restart
rm -rf /etc/slowdns
mkdir -m 777 /etc/slowdns
wget -q -O /etc/slowdns/server.key "${REPO}slowdns/server.key"
wget -q -O /etc/slowdns/server.pub "${REPO}slowdns/server.pub"
wget -q -O /etc/slowdns/sldns-server "${REPO}slowdns/sldns-server"
cd
chmod +x /etc/slowdns/server.key
chmod +x /etc/slowdns/server.pub
chmod +x /etc/slowdns/sldns-server
cd
cat > /etc/systemd/system/server-sldns.service << EOF
[Unit]
Description=Server SlowDNS By LITE
Documentation=https://one.one.one.one
After=network.target nss-lookup.target
[Service]
Type=simple
User=root
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ExecStart=/etc/slowdns/sldns-server -udp :5300 -privkey-file /etc/slowdns/server.key $nameserver 127.0.0.1:2269
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF
[Unit]
Description=Server SlowDNS By LITE
Documentation=https://one.one.one.one
After=network.target nss-lookup.target
[Service]
Type=simple
User=root
CapabilityBoundingSet=CAP_NET_ADMIN CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_ADMIN CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ExecStart=/etc/slowdns/sldns-server -udp :5300 -privkey-file /etc/slowdns/server.key $nameserver 127.0.0.1:2269
Restart=on-failure
[Install]
WantedBy=multi-user.target
END
cd
chmod +x /etc/systemd/system/client-sldns.service
chmod +x /etc/systemd/system/server-sldns.service
pkill sldns-server
systemctl daemon-reload
systemctl stop server-sldns
systemctl enable server-sldns
systemctl start server-sldns
systemctl restart server-sldns
clear
echo -e "${BIWhite}Please Pointing Type NS${NC} ${BIYellow}$nameserver${NC}"
echo -e "${BIWhite}With Target${NC} ${BIYellow}$domen${NC}"
sleep 8
cd
print_success "Slowdns"
}
function loading() {
  clear
  local pid=$1
  local delay=0.1
  local spin='-\|/'
  while ps -p $pid > /dev/null; do
    local temp=${spin:0:1}
    printf "[%c] " "$spin"
    local spin=$temp${spin%"$temp"}
    sleep $delay
    printf "\b\b\b\b\b\b"
  done
  printf "    \b\b\b\b"
}
function memasang_udepe() {
clear
print_install "Memasang UDP Custom"
clear
cd
rm -rf /root/udp
mkdir -p /root/udp
sleep 1
echo -e "${BIWhite}downloading udp-custom${NC}"
wget -q --show-progress --load-cookies /tmp/cookies.txt "https://docs.google.com/uc?export=download&confirm=$(wget --quiet --save-cookies /tmp/cookies.txt --keep-session-cookies --no-check-certificate 'https://docs.google.com/uc?export=download&id=1ixz82G_ruRBnEEp4vLPNF2KZ1k8UfrkV' -O- | sed -rn 's/.*confirm=([0-9A-Za-z_]+).*/\1\n/p')&id=1ixz82G_ruRBnEEp4vLPNF2KZ1k8UfrkV" -O /root/udp/udp-custom && rm -rf /tmp/cookies.txt
chmod +x /root/udp/udp-custom
sleep 1
echo -e "${BIWhite}downloading default config${NC}"
wget -q --show-progress --load-cookies /tmp/cookies.txt "https://docs.google.com/uc?export=download&confirm=$(wget --quiet --save-cookies /tmp/cookies.txt --keep-session-cookies --no-check-certificate 'https://docs.google.com/uc?export=download&id=1klXTiKGUd2Cs5cBnH3eK2Q1w50Yx3jbf' -O- | sed -rn 's/.*confirm=([0-9A-Za-z_]+).*/\1\n/p')&id=1klXTiKGUd2Cs5cBnH3eK2Q1w50Yx3jbf" -O /root/udp/config.json && rm -rf /tmp/cookies.txt
chmod 644 /root/udp/config.json
if [ -z "$1" ]; then
cat <<EOF > /etc/systemd/system/udp-custom.service
[Unit]
Description=UDP CUSTOM BY LITE
[Service]
User=root
Type=simple
ExecStart=/root/udp/udp-custom server
WorkingDirectory=/root/udp/
Restart=always
RestartSec=2s
[Install]
WantedBy=default.target
EOF
else
cat <<EOF > /etc/systemd/system/udp-custom.service
[Unit]
Description=UDP CUSTOM BY LITE
[Service]
User=root
Type=simple
ExecStart=/root/udp/udp-custom server -exclude $1
WorkingDirectory=/root/udp/
Restart=always
RestartSec=2s
[Install]
WantedBy=default.target
EOF
fi
echo -e "${BIWhite}start service udp-custom${NC}"
systemctl start udp-custom &>/dev/null
sleep 1
echo -e "${BIWhite}enable service udp-custom${NC}"
systemctl enable udp-custom &>/dev/null
sleep 3 & loading $!
cd
print_success "UDP Custom"
}
function memasang_noobz() {
  clear
  print_install "Memasang Noobzvpns"
  wget ${REPO}noobzvpns.zip
  unzip noobzvpns.zip
  rm -rf noobzvpns.zip noobzvpns.zip.1 noobzvpns.zip.2 noobzvpns.zip.3 noobzvpns.zip.4
  cd noobzvpns
  chmod +x install.sh
  ./install.sh
  systemctl start noobzvpns
  systemctl restart noobzvpns
  cd
  print_success "Noobzvpns"
}
function memasang_haproxy() {
clear
print_install "Memasang Haproxy"
if [ "$EUID" -ne 0 ]; then
  echo -e "${BIWhite}Jalankan script ini sebagai root!${NC}"
  exit 1
fi
echo -e "${BIWhite}✥Bersihkan HAProxy lama jika ada...${NC}"
systemctl stop haproxy 2>/dev/null
systemctl disable haproxy 2>/dev/null
apt purge -y haproxy 2>/dev/null
apt autoremove -y
rm -f /etc/haproxy/haproxy.cfg
rm -f /etc/haproxy/hap.pem
rm -rf /etc/haproxy/errors
rm -rf /var/lib/haproxy
rm -f /run/haproxy.pid
echo -e "${BIWhite}✥Instalasi ulang HAProxy...${NC}"
sudo apt update && sudo apt install haproxy -y
echo -e "${BIWhite}✥Gabungkan sertifikat Xray ke /etc/haproxy/hap.pem...${NC}"
mkdir -p /etc/haproxy
cat /etc/xray/xray.crt /etc/xray/xray.key > /etc/haproxy/hap.pem
echo -e "${BIWhite}✥Buat konfigurasi HAProxy baru...${NC}"
cat > /etc/haproxy/haproxy.cfg << 'EOF'
global
    stats socket /run/haproxy/admin.sock mode 660 level admin expose-fd listeners
    stats timeout 1d
    log /dev/log local0
    log /dev/log local1 notice
    log /dev/log local0 info
    tune.h2.initial-window-size 2147483647
    tune.ssl.default-dh-param 2048
    pidfile /run/haproxy.pid
    chroot /var/lib/haproxy
    user haproxy
    group haproxy
    daemon
    ssl-default-bind-ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384
    ssl-default-bind-ciphersuites TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256
    ssl-default-bind-options no-sslv3 no-tlsv10 no-tlsv11
    ca-base /etc/ssl/certs
    crt-base /etc/ssl/private
defaults
    log global
    mode tcp
    option dontlognull
    timeout connect 200ms
    timeout client  300s
    timeout server  300s
frontend multiport
    mode tcp
    bind *:222-1000 tfo
    tcp-request inspect-delay 500ms
    tcp-request content accept if HTTP
    tcp-request content accept if { req.ssl_hello_type 1 }
    use_backend recir_http if HTTP
    default_backend recir_https
frontend multiports
    mode tcp
    bind abns@haproxy-http accept-proxy tfo
    default_backend recir_https_www
frontend ssl
    mode tcp
    bind *:444 tfo
    bind *:777 tfo
    bind abns@haproxy-https accept-proxy ssl crt /etc/haproxy/hap.pem alpn h2,http/1.1 tfo
    tcp-request inspect-delay 500ms
    tcp-request content capture req.ssl_sni len 100
    tcp-request content accept if { req.ssl_hello_type 1 }
    acl chk-02_up hdr(Connection) -i upgrade
    acl chk-02_ws hdr(Upgrade) -i websocket
    acl this_payload payload(0,7) -m bin 5353482d322e30
    acl up-to ssl_fc_alpn -i h2
    use_backend GRUP_LITE if up-to
    use_backend LITE if chk-02_up chk-02_ws
    use_backend LITE if { path_reg -i ^\/(.*) }
    use_backend BOT_LITE if this_payload
    default_backend CHANNEL_LITE
backend recir_https_www
    mode tcp
    server misssv-bau 127.0.0.1:2223 check
backend LITE
    mode http
    server lite-vermilion 127.0.0.1:1010 send-proxy check
backend GRUP_LITE
    mode tcp
    server lite-vermilions 127.0.0.1:1013 send-proxy check
backend CHANNEL_LITE
    mode tcp
    balance roundrobin
    server y-lite 127.0.0.1:1194 check
    server lite-x 127.0.0.1:1012 send-proxy check
backend BOT_LITE
    mode tcp
    server xiao-lite 127.0.0.1:2222 check
backend recir_http
    mode tcp
    server loopback-for-http abns@haproxy-http send-proxy-v2 check
backend recir_https
    mode tcp
    server loopback-for-https abns@haproxy-https send-proxy-v2 check
EOF
echo -e "${BIWhite}✥Cek konfigurasi HAProxy...${NC}"
haproxy -c -f /etc/haproxy/haproxy.cfg
if [ $? -eq 0 ]; then
    echo -e "${BIWhite}✥Konfigurasi valid. Menyalakan HAProxy...${NC}"
    systemctl restart haproxy
    systemctl enable haproxy
    echo -e "${BIWhite}✥HAProxy berhasil dipasang dan diperbarui!${NC}"
else
    echo -e "${BIWhite}✥Konfigurasi tidak valid. Cek file: /etc/haproxy/haproxy.cfg${NC}"
fi
systemctl restart haproxy
print_success "Haproxy"
}
function memasang_index_page() {
  cat <<EOF > /var/www/html/index.html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Di Pencet Ya Kak☺️</title>
  <style>
    body {
      margin: 0;
      padding: 0;
      font-family: 'Helvetica Neue', sans-serif;
      background: linear-gradient(135deg, #e0f7fa, #ffffff);
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }

    .card {
      background: white;
      padding: 40px;
      max-width: 800px;
      margin: 20px;
      border-radius: 20px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.1);
      color: #333;
    }

    h1 {
      text-align: center;
      color: #00796b;
      margin-bottom: 30px;
      font-size: 2em;
    }

    p {
      margin-bottom: 20px;
      line-height: 1.8;
      font-size: 1.05em;
    }

    strong {
      color: #004d40;
    }

    em {
      color: #555;
      font-style: italic;
    }

    .footer {
      margin-top: 40px;
      text-align: center;
      font-size: 0.95em;
      color: #777;
    }

    @media (max-width: 600px) {
      .card {
        padding: 25px;
      }

      h1 {
        font-size: 1.5em;
      }

      p {
        font-size: 1em;
      }
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>⚠️ WARNING ⚠️</h1>

    <p><strong>"Ibadah dan pahalamu tidak bisa menyelamatkanmu dari Neraka.</strong><br>
    Jika kamu bandingkan dengan nikmat yang Allah SWT berikan padamu.</p>

    <p>Lebih besar yang mana?<br>
    Lebih berat yang mana?</p>

    <p>Saat kamu diciptakan, apakah itu bukan nikmat?<br>
    Bahkan kematian pun adalah nikmat...!!!</p>

    <p>Semua yang kamu alami adalah nikmat yang Allah SWT berikan untukmu.</p>

    <p>Yang menyelamatkanmu adalah Allah SWT (rahmat-Nya atau disebut kasih sayang-Nya).</p>

    <p>Hanya saja <strong>(berusahalah)</strong> untuk mendapatkan rahmat-Nya.<br>
    kita harus beribadah, mengerjakan perintah-perintah-Nya dan menjauhi larangan-larangan-Nya.</p>

    <p><strong>Beribadahlah</strong> semata-mata mengharapkan ridho-Nya, rahmat-Nya.</p>

    <p><strong>Oleh sebab itu</strong>, janganlah berpikir ibadah dan pahala-mu bisa membawamu ke Surga dan menyelamatkanmu dari Neraka.</p>

    <p><em>Inilah hal yang selama ini aku temukan dan tanamkan pada diriku.</em></p>

    <p><strong>(Berusahalah semampumu & jika Allah SWT merahmatimu maka nantinya kamu bisa melampaui batasanmu)</strong></p>

    <p>Semoga kita termasuk orang-orang beruntung yang mendapatkan Rahmat dan Kasih Sayang Allah SWT.</p>

    <p><em>Saya bukan ustadz, masih fakir akan ilmu bahkan baca doa Yasinan aja masih lupa dan salah 😂.</em></p>

    <p>Hanya saja aku merasa bahwa pemikiran yang aku tahu ini harus aku bagikan kepada orang lain.</p>

    <div class="footer">
      Semoga bermanfaat 🙏🙏🙏
      Terima kasih atas sharingnya:<br />
      <strong>@ahmadsohibulkahfi</strong>
    </div>
  </div>
</body>
</html>
EOF
}
function mulai_penginstallan(){
    clear
    setup_grub_env
    tampilan
    mengecek_akses_root
    memasang_paket_dasar
    pengaturan_pertama
    memasang_nginx
    memasang_folder_xray
    memasang_domain
    memasang_ssl
    memasang_xray
    memasang_password_ssh
    memasang_pembatas
    memasang_sshd
    memasang_vnstat
    memasang_pencadangan
    memasang_menu
    memasang_fail2ban
    memasang_netfilter
    memasang_dropbear
    memasang_sshws
    memasang_profile
    memasang_badvpn
    memasang_slowdns
    memasang_udepe
    memasang_noobz
    memasang_haproxy
    memasang_bbr_hybla
    memasang_index_page
    memasang_restart
    memasang_notifikasi_bot
}
mulai_penginstallan
history -c
rm -rf /root/menu
rm -rf /root/*.zip
rm -rf /root/*.sh
rm -rf /root/LICENSE
rm -rf /root/README.md
rm -rf /root/domain
clear
secs_to_human "$(($(date +%s) - ${start}))"
echo -e "${BIWhite}Script Successfully Installed${NC}"
read -p "$( echo -e "${BIYellow}Press ${BIWhite}[ ${NC}${LIME}Enter${NC} ${BIWhite}]${BIYellow} For reboot${NC}") "
reboot
