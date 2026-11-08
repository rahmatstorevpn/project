#!/usr/bin/env bash
# Launcher: downloads upstream install3.sh, makes SlowDNS optional, validates, then runs it.
set -Eeuo pipefail

URL="https://raw.githubusercontent.com/rahmatstorevpn/project/main/install3.sh"
WORK="/root/install3-patched.sh"
BACKUP="/root/install3-upstream-backup.sh"

if [ "$(id -u)" -ne 0 ]; then
  echo "Jalankan file ini sebagai root."
  exit 1
fi

command -v curl >/dev/null 2>&1 || {
  echo "curl belum tersedia. Pasang curl lalu jalankan lagi."
  exit 1
}

echo "Mengunduh install3.sh terbaru..."
curl -4 -fL --retry 3 --retry-delay 2 "$URL" -o "$BACKUP"

python3 - "$BACKUP" "$WORK" <<'PYCODE'
from pathlib import Path
import sys

src, dst = map(Path, sys.argv[1:])
s = src.read_text()
old = '    memasang_slowdns || { echo "Instalasi SlowDNS gagal; proses dihentikan."; exit 1; }'
new = '''    # SlowDNS opsional: kegagalan tidak menghentikan instalasi utama.
    if ! memasang_slowdns; then
        echo
        echo "PERINGATAN: SlowDNS gagal dipasang atau tidak aktif."
        echo "Instalasi VPN utama tetap dilanjutkan."
        echo "SlowDNS dapat diperbaiki setelah instalasi selesai."
        systemctl disable --now server-sldns >/dev/null 2>&1 || true
    fi'''

if s.count(old) != 1:
    raise SystemExit("GAGAL: baris pemanggil SlowDNS tidak cocok. Installer tidak dijalankan.")
dst.write_text(s.replace(old, new, 1))
PYCODE

echo "Memeriksa sintaks installer..."
bash -n "$WORK" || {
  echo "Sintaks tidak valid. Installer tidak dijalankan."
  exit 1
}

echo "Patch SlowDNS opsional siap."
echo "Jika SlowDNS gagal, instalasi utama tetap dilanjutkan."
echo "Cadangan script upstream: $BACKUP"
echo
bash "$WORK"
