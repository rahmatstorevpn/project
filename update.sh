#!/bin/bash
clear
y='\033[1;33m'
BGX="\033[42m"
CYAN="\033[96m"
Putih="\033[97m"
RED='\033[0;31m'
NC='\033[0m'
green='\033[0;32m'
BIBlack='\033[1;90m'
BIGreen='\033[1;92m'
BIYellow='\033[1;93m'
BIBlue='\033[1;94m'
BIPurple='\033[1;95m'
BICyan='\033[1;96m'
BIWhite='\033[1;97m'
UWhite='\033[4;37m'
On_IPurple='\033[0;105m'
On_IRed='\033[0;101m'
IBlack='\033[0;90m'
IGreen='\033[0;92m'
IYellow='\033[0;93m'
IBlue='\033[0;94m'
IPurple='\033[0;95m'
ICyan='\033[0;96m'
IWhite='\033[0;97m'
GREENBO='\033[1;32m'
bgwhite='\e[40;97;1m'
bgred='\e[41;97;1m'
bggreen='\e[42;97;1m'
bgyellow='\e[43;97;1m'
bgmagenta='\e[45;97;1m'
bgblue='\e[46;97;1m'
bgblack='\e[47;30;1m'
w='\033[97m'
ORANGE='\033[0;34m'
dateFromServer=$(curl -v --insecure --silent https://google.com/ 2>&1 | grep Date | sed -e 's/< Date: //')
biji=`date +"%Y-%m-%d" -d "$dateFromServer"`
red() { echo -e "\\033[32;1m${*}\\033[0m"; }
clear
fun_bar() {
    CMD[0]="$1"
    CMD[1]="$2"
    (
        [[ -e $HOME/fim ]] && rm $HOME/fim
        ${CMD[0]} -y >/dev/null 2>&1
        ${CMD[1]} -y >/dev/null 2>&1
        touch $HOME/fim
    ) >/dev/null 2>&1 &
    tput civis
    echo -ne "\033[0;33mLoading\033[1;37m - \033[0;33m["
    while true; do
        for ((i = 0; i < 21; i++)); do
            echo -ne "\033[0;32m#"
            sleep 0.1s
        done
        [[ -e $HOME/fim ]] && rm $HOME/fim && break
        echo -e "\033[0;33m]"
        sleep 1s
        tput cuu1
        tput dl1
        echo -ne "\033[0;33mLoading\033[1;37m - \033[0;33m["
    done
    echo -e "\033[0;33m]\033[1;37m -\033[1;32m OK\033[1;37m"
    tput cnorm
}
res1() {
    wget https://raw.githubusercontent.com/sehuadri/project/main/menu/menu.zip
    unzip -P miqdad12 menu.zip
    chmod +x menu/*
    mv menu/* /usr/local/sbin
    sleep 2
    sudo dos2unix /usr/local/sbin/*
 
    rm -rf menu
    rm -rf menu.zip
    rm -rf update.sh
}
netfilter-persistent
clear
echo -e "${BIWhite}──────────────────────────────────────${NC}"
echo -e "${bggreen}             UPDATE SCRIPT            ${NC}"
echo -e "${BIWhite}──────────────────────────────────────${NC}"
echo -e ""
fun_bar 'res1'
echo -e "${BIWhite}──────────────────────────────────────${NC}"
echo -e ""
read -n 1 -s -r -p "Press [ Enter ] to back on menu"
menu