#!/bin/bash
# === Setup Auto Cleanup Xray Service ===

SERVICE_NAME="cleanup-xray"
SCRIPT_PATH="/var/www/cleanup.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LOG_FILE="/var/log/cleanup-xray.log"

echo "[+] Membuat file Python cleanup di $SCRIPT_PATH ..."

mkdir -p /var/www

cat > "$SCRIPT_PATH" <<'EOF'
#!/usr/bin/env python3
import re
import json
import time
from datetime import datetime
import subprocess

CONFIG_PATH = "/etc/xray/config.json"
BACKUP_PATH = "/etc/xray/config_backup.json"
CHECK_INTERVAL = 10  # detik

def backup_config():
    subprocess.run(["cp", CONFIG_PATH, BACKUP_PATH])
    print(f"[+] Backup created at {BACKUP_PATH}")

def load_raw_config():
    with open(CONFIG_PATH, "r") as f:
        return f.read()

def save_raw_config(data):
    with open(CONFIG_PATH, "w") as f:
        f.write(data)

def cleanup_expired_accounts():
    now = datetime.now()
    raw = load_raw_config()

    pattern = re.compile(r"(###|#&|#!)\s*([^\s]+)\s+([^\s]+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})")
    expired_entries = []

    for match in pattern.finditer(raw):
        full_match = match.group(0)
        user_tag = match.group(2)
        date_str = f"{match.group(4)} {match.group(5)}"
        exp_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

        if exp_date < now:
            expired_entries.append(full_match)

    if not expired_entries:
        print(f"[{now:%Y-%m-%d %H:%M:%S}] Tidak ada akun expired ditemukan.")
        return False  # tidak ada perubahan

    print(f"[{now:%Y-%m-%d %H:%M:%S}] {len(expired_entries)} akun expired ditemukan, sedang dihapus...")

    for entry in expired_entries:
        raw = re.sub(
            rf"{re.escape(entry)}[\s\S]{{0,300}}?}},",  # hapus sampai '},'
            "",
            raw,
            flags=re.MULTILINE
        )

    save_raw_config(raw)
    print("[+] Config.json telah dibersihkan dan disimpan ulang.")
    return True  # ada akun dihapus

def restart_xray():
    subprocess.run(["systemctl", "restart", "xray"])
    print("[↻] Service Xray telah direstart.")

if __name__ == "__main__":
    print("=== AUTO CLEANUP XRAY ACCOUNTS (Loop Mode) ===")
    backup_config()

    while True:
        try:
            changed = cleanup_expired_accounts()
            if changed:
                restart_xray()
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            print("\n[!] Dihentikan oleh user.")
            break
        except Exception as e:
            print(f"[!] Terjadi error: {e}")
            time.sleep(CHECK_INTERVAL)
EOF

chmod +x "$SCRIPT_PATH"

# === Membuat systemd service ===
echo "[+] Membuat systemd service di $SERVICE_FILE ..."

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Auto Cleanup Expired Xray Accounts
After=network.target

[Service]
ExecStart=/usr/bin/python3 $SCRIPT_PATH
Restart=always
RestartSec=10
User=root
WorkingDirectory=/var/www
StandardOutput=append:${LOG_FILE}
StandardError=append:${LOG_FILE}

[Install]
WantedBy=multi-user.target
EOF

# Reload dan aktifkan service
echo "[+] Reloading systemd daemon..."
systemctl daemon-reload

echo "[+] Mengaktifkan service agar auto start..."
systemctl enable $SERVICE_NAME

echo "[+] Menjalankan service sekarang..."
systemctl start $SERVICE_NAME

sleep 2
systemctl status $SERVICE_NAME --no-pager

echo
echo "[✓] Service '$SERVICE_NAME' telah dibuat dan berjalan otomatis!"
echo "    Log: tail -f $LOG_FILE"
echo "    Stop: systemctl stop $SERVICE_NAME"
echo "    Disable: systemctl disable $SERVICE_NAME"
