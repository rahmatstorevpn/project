#!/usr/bin/env python3
import os
import sys
import time
import asyncio
import schedule
import threading
import logging
import signal
import daemon
from datetime import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Konfigurasi path
BASE_DIR = Path("/opt/backup-bot")
CONFIG_FILE = BASE_DIR / ".bckupbot"
LOG_FILE = BASE_DIR / "backup-bot.log"
PID_FILE = BASE_DIR / "backup-bot.pid"

# Pastikan direktori ada
BASE_DIR.mkdir(parents=True, exist_ok=True)

# Konfigurasi logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
formatter = logging.Formatter(log_format)

# Handler untuk file log
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

# Handler untuk console
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class BackupBot:
    def __init__(self):
        self.token = None
        self.admin_id = None
        self.backup_status = "off"
        self.current_interval = None
        self.application = None
        self.loop = None
        self.is_running = True
        self.setup_signal_handlers()
        
    def setup_signal_handlers(self):
        """Setup signal handlers untuk graceful shutdown"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """Handler untuk signal shutdown"""
        logger.info(f"📩 Menerima signal {signum}, melakukan shutdown...")
        self.is_running = False
        if self.application:
            self.application.stop()
        
    def check_config(self):
        """Memeriksa konfigurasi dan menghentikan program jika tidak valid"""
        self.load_config()
        
        if not self.token or not self.admin_id:
            logger.error("❌ TOKEN atau ADMIN ID tidak ditemukan!")
            logger.error("Silakan konfigurasi terlebih dahulu:")
            logger.error(f"1. Edit file: {CONFIG_FILE}")
            logger.error("2. Format file:")
            logger.error("   Line 1: BOT_TOKEN")
            logger.error("   Line 2: ADMIN_ID (numeric)")
            logger.error("   Line 3: backup_status (on/off)")
            logger.error("   Line 4: interval (optional)")
            logger.error("\nContoh isi file:")
            logger.error("1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
            logger.error("987654321")
            logger.error("off")
            logger.error("6h")
            return False
        
        try:
            # Validasi admin_id harus angka
            if not isinstance(self.admin_id, int):
                self.admin_id = int(self.admin_id)
            return True
        except ValueError:
            logger.error("❌ ADMIN ID harus berupa angka!")
            return False
        except Exception as e:
            logger.error(f"❌ Error validasi konfigurasi: {e}")
            return False
    
    def load_config(self):
        """Memuat konfigurasi dari file"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                    
                    if len(lines) >= 2:
                        self.token = lines[0].strip()
                        
                        try:
                            self.admin_id = int(lines[1].strip())
                        except ValueError:
                            self.admin_id = None
                            logger.error(f"Admin ID tidak valid: {lines[1]}")
                        
                        if len(lines) >= 3:
                            self.backup_status = lines[2].strip().lower()
                        
                        if len(lines) >= 4:
                            self.current_interval = lines[3].strip()
                    
                    logger.info(f"✅ Konfigurasi dimuat: Token={bool(self.token)}, Admin_ID={self.admin_id}")
            else:
                logger.warning(f"⚠️ File konfigurasi tidak ditemukan: {CONFIG_FILE}")
                
        except Exception as e:
            logger.error(f"❌ Error loading config: {e}")

    def save_config(self):
        """Menyimpan konfigurasi ke file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                f.write(f"{self.token}\n")
                f.write(f"{self.admin_id}\n")
                f.write(f"{self.backup_status}\n")
                if self.current_interval:
                    f.write(f"{self.current_interval}\n")
            
            logger.info(f"✅ Konfigurasi disimpan ke {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"❌ Error saving config: {e}")

    def get_system_info(self):
        """Mendapatkan informasi sistem"""
        info = {}
        try:
            # Get IP
            info['ip'] = os.popen('curl -s icanhazip.com').read().strip()
            
            # Get domain
            if os.path.exists('/etc/xray/domain'):
                with open('/etc/xray/domain', 'r') as f:
                    info['host'] = f.read().strip()
            else:
                info['host'] = "N/A"
                
            # Get date
            info['date'] = datetime.now().strftime("%d-%B-%Y")
            
            # Get ISP
            if os.path.exists('/etc/xray/isp'):
                with open('/etc/xray/isp', 'r') as f:
                    info['isp'] = f.read().strip()
            else:
                info['isp'] = "N/A"
                
            # Get City
            if os.path.exists('/etc/xray/city'):
                with open('/etc/xray/city', 'r') as f:
                    info['city'] = f.read().strip()
            else:
                info['city'] = "N/A"
                
        except Exception as e:
            logger.error(f"❌ Error getting system info: {e}")
            info = {'ip': 'N/A', 'host': 'N/A', 'date': 'N/A', 'isp': 'N/A', 'city': 'N/A'}
        
        return info

    def backup_vps(self):
        """Fungsi untuk melakukan backup VPS"""
        logger.info("🚀 Memulai proses backup...")
        
        # Dapatkan informasi sistem
        info = self.get_system_info()
        ip = info['ip']
        datevps = info['date']
        
        try:
            # Hapus backup lama
            os.system("rm -rf /root/backup &>/dev/null")
            os.system("mkdir -p /root/backup &>/dev/null")
            
            # Backup file-file penting
            files_to_backup = [
                ("/etc/passwd", "passwd"),
                ("/etc/group", "group"),
                ("/etc/shadow", "shadow"),
                ("/etc/gshadow", "gshadow"),
                ("/etc/crontab", "crontab"),
                ("/etc/vmess/.vmess.db", ".vmess.db"),
                ("/etc/vless/.vless.db", ".vless.db"),
                ("/etc/trojan/.trojan.db", ".trojan.db"),
                ("/etc/shadowsocks/.shadowsocks.db", ".shadowsocks.db")
            ]
            
            for src, dest in files_to_backup:
                if os.path.exists(src):
                    os.system(f"cp {src} /root/backup/{dest} &>/dev/null")
            
            # Backup direktori
            dirs_to_backup = [
                ("/etc/limit", "limit"),
                ("/etc/vmess", "vmess"),
                ("/etc/trojan", "trojan"),
                ("/etc/vless", "vless"),
                ("/etc/shadowsocks", "shadowsocks"),
                ("/etc/xray", "xray"),
                ("/var/www/html", "html"),
                ("/detail", "detail")
            ]
            
            for src, dest in dirs_to_backup:
                if os.path.exists(src):
                    os.system(f"cp -r {src} /root/backup/{dest} &>/dev/null")
            
            # Zip dan upload ke rclone
            zip_file = f"/root/{ip}-{datevps}.zip"
            os.chdir("/root")
            os.system(f"zip -r {zip_file} backup > /dev/null 2>&1")
            os.system(f"rclone copy {zip_file} dr:backup/")
            
            # Dapatkan link
            output = os.popen(f"rclone link dr:backup/{ip}-{datevps}.zip").read().strip()
            
            if "https://drive.google.com" in output:
                url = output
                file_id = url.split('=')[-1]
                backup_link = f"https://drive.google.com/u/4/uc?id={file_id}&export=download"
            else:
                backup_link = output
            
            # Bersihkan
            os.system("rm -rf /root/backup")
            os.system(f"rm -f {zip_file}")
            
            logger.info(f"✅ Backup berhasil: {backup_link}")
            return backup_link, info
            
        except Exception as e:
            logger.error(f"❌ Error dalam backup: {e}")
            return None, info

    async def send_backup_notification(self):
        """Mengirim notifikasi backup ke Telegram"""
        if not self.admin_id or not self.application:
            logger.error("❌ Admin ID atau aplikasi tidak ditemukan")
            return
            
        backup_link, info = self.backup_vps()
        
        if backup_link:
            message = f"""
<b>==============================</b>
<b>✅ BACKUP VPS OTOMATIS</b>
<b>==============================</b>
<b>📆 Date     :</b> <code>{info['date']}</code>
<b>🌐 IP       :</b> <code>{info['ip']}</code>
<b>🌍 Domain   :</b> <code>{info['host']}</code>
<b>🏢 ISP      :</b> <code>{info['isp']}</code>
<b>📍 City     :</b> <code>{info['city']}</code>
<b>⏰ Interval :</b> <code>{self.current_interval}</code>
<b>📦 Backup Link :</b> <a href="{backup_link}">Download Here</a>
<b>==============================</b>
"""
            
            try:
                await self.application.bot.send_message(
                    chat_id=self.admin_id,
                    text=message,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
                logger.info("📤 Notifikasi backup terkirim")
            except Exception as e:
                logger.error(f"❌ Error sending message: {e}")

    def setup_scheduler(self):
        """Setup scheduler berdasarkan interval yang dipilih"""
        schedule.clear('backup_job')
        
        if self.backup_status == "off" or not self.current_interval:
            logger.info("⏸️ Backup otomatis nonaktif")
            return
        
        interval_map = {
            '1m': (1, 'minutes'),
            '30m': (30, 'minutes'),
            '1h': (1, 'hours'),
            '6h': (6, 'hours'),
            '12h': (12, 'hours'),
            '24h': (24, 'hours')
        }
        
        if self.current_interval in interval_map:
            value, unit = interval_map[self.current_interval]
            
            # Buat job scheduler
            if unit == 'minutes':
                schedule.every(value).minutes.do(
                    self.run_backup_job
                ).tag('backup_job')
            else:
                schedule.every(value).hours.do(
                    self.run_backup_job
                ).tag('backup_job')
            
            logger.info(f"⏰ Scheduler diatur ke {value} {unit}")

    def run_backup_job(self):
        """Menjalankan backup job dari scheduler"""
        if self.loop and not self.loop.is_closed():
            # Buat future untuk menjalankan coroutine
            asyncio.run_coroutine_threadsafe(
                self.send_backup_notification(),
                self.loop
            )
        else:
            logger.error("❌ Event loop tidak tersedia")

# Inisialisasi bot
bot = BackupBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    if update.effective_user.id != bot.admin_id:
        await update.message.reply_text("❌ Anda tidak memiliki akses ke bot ini!")
        return
    
    keyboard = [
        [InlineKeyboardButton("⚙️ SETTING BACKUP", callback_data='setting')],
        [InlineKeyboardButton("🔄 BACKUP SEKARANG", callback_data='backup_now')],
        [InlineKeyboardButton("📊 STATUS", callback_data='status')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🤖 *BACKUP BOT VPS*\n\n"
        "Pilih menu di bawah:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk button callback"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != bot.admin_id:
        await query.edit_message_text("❌ Anda tidak memiliki akses!")
        return
    
    if query.data == 'setting':
        await show_interval_settings(query)
    elif query.data == 'backup_now':
        await backup_now(query, context)
    elif query.data == 'status':
        await show_status(query)
    elif query.data.startswith('interval_'):
        await set_interval(query)
    elif query.data == 'stop_backup':
        await stop_backup(query)
    elif query.data == 'back_to_main':
        await back_to_main_handler(query)

async def show_interval_settings(query):
    """Menampilkan pilihan interval"""
    keyboard = [
        [InlineKeyboardButton("⏰ 1 MENIT", callback_data='interval_1m')],
        [InlineKeyboardButton("⏰ 30 MENIT", callback_data='interval_30m')],
        [InlineKeyboardButton("⏰ 1 JAM", callback_data='interval_1h')],
        [InlineKeyboardButton("⏰ 6 JAM", callback_data='interval_6h')],
        [InlineKeyboardButton("⏰ 12 JAM", callback_data='interval_12h')],
        [InlineKeyboardButton("⏰ 24 JAM", callback_data='interval_24h')],
        [InlineKeyboardButton("⛔ STOP BACKUP", callback_data='stop_backup')],
        [InlineKeyboardButton("🔙 KEMBALI", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⚙️ *SETTING INTERVAL BACKUP*\n\n"
        "Pilih interval backup otomatis:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def set_interval(query):
    """Mengatur interval backup"""
    interval_map = {
        'interval_1m': '1m',
        'interval_30m': '30m',
        'interval_1h': '1h',
        'interval_6h': '6h',
        'interval_12h': '12h',
        'interval_24h': '24h'
    }
    
    interval_key = query.data
    interval_text = interval_map[interval_key]
    
    # Update konfigurasi
    bot.backup_status = "on"
    bot.current_interval = interval_text
    bot.save_config()
    
    # Setup ulang scheduler
    bot.setup_scheduler()
    
    await query.edit_message_text(
        f"✅ *Interval backup diatur ke {interval_text}*\n\n"
        f"Backup otomatis akan berjalan setiap {interval_text}.",
        parse_mode='Markdown'
    )

async def backup_now(query, context: ContextTypes.DEFAULT_TYPE):
    """Melakukan backup sekarang"""
    await query.edit_message_text("⏳ *Memulai backup...*", parse_mode='Markdown')
    
    backup_link, info = bot.backup_vps()
    
    if backup_link:
        message = f"""
<b>==============================</b>
<b>✅ BACKUP VPS MANUAL</b>
<b>==============================</b>
<b>📆 Date     :</b> <code>{info['date']}</code>
<b>🌐 IP       :</b> <code>{info['ip']}</code>
<b>🌍 Domain   :</b> <code>{info['host']}</code>
<b>🏢 ISP      :</b> <code>{info['isp']}</code>
<b>📍 City     :</b> <code>{info['city']}</code>
<b>📦 Backup Link :</b> <a href="{backup_link}">Download Here</a>
<b>==============================</b>
"""
        
        await context.bot.send_message(
            chat_id=bot.admin_id,
            text=message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
        
        keyboard = [[InlineKeyboardButton("🔙 KEMBALI", callback_data='back_to_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "✅ *Backup berhasil!*\n\nLink backup telah dikirim.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    else:
        keyboard = [[InlineKeyboardButton("🔙 KEMBALI", callback_data='back_to_main')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ *Gagal melakukan backup!*\n\nPeriksa log untuk detail.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def stop_backup(query):
    """Menghentikan backup otomatis"""
    bot.backup_status = "off"
    bot.current_interval = None
    bot.save_config()
    
    schedule.clear('backup_job')
    
    keyboard = [[InlineKeyboardButton("🔙 KEMBALI", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⛔ *Backup otomatis dihentikan!*",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def show_status(query):
    """Menampilkan status backup"""
    info = bot.get_system_info()
    
    status_text = "🟢 AKTIF" if bot.backup_status == "on" else "🔴 NONAKTIF"
    interval_text = bot.current_interval if bot.current_interval else "Tidak diatur"
    
    message = f"""
<b>📊 STATUS BACKUP BOT</b>
<b>==============================</b>
<b>🔧 Status     :</b> {status_text}
<b>⏰ Interval   :</b> <code>{interval_text}</code>
<b>🌐 IP VPS     :</b> <code>{info['ip']}</code>
<b>🌍 Domain     :</b> <code>{info['host']}</code>
<b>📆 Last Check :</b> <code>{datetime.now().strftime('%d-%B-%Y %H:%M:%S')}</code>
<b>==============================</b>
"""
    
    keyboard = [[InlineKeyboardButton("🔙 KEMBALI", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def back_to_main_handler(query):
    """Kembali ke menu utama"""
    keyboard = [
        [InlineKeyboardButton("⚙️ SETTING BACKUP", callback_data='setting')],
        [InlineKeyboardButton("🔄 BACKUP SEKARANG", callback_data='backup_now')],
        [InlineKeyboardButton("📊 STATUS", callback_data='status')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🤖 *BACKUP BOT VPS*\n\n"
        "Pilih menu di bawah:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk error"""
    logger.error(f"Update {update} caused error {context.error}")

def schedule_runner():
    """Menjalankan scheduler di thread terpisah"""
    logger.info("⏰ Scheduler thread dimulai")
    while bot.is_running:
        schedule.run_pending()
        time.sleep(1)
    logger.info("⏰ Scheduler thread dihentikan")

def write_pid_file():
    """Menulis PID ke file"""
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"📝 PID file dibuat: {PID_FILE}")
    except Exception as e:
        logger.error(f"❌ Gagal menulis PID file: {e}")

def remove_pid_file():
    """Menghapus PID file"""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
            logger.info(f"🗑️ PID file dihapus: {PID_FILE}")
    except Exception as e:
        logger.error(f"❌ Gagal menghapus PID file: {e}")

def create_config_file():
    """Membuat file konfigurasi contoh jika tidak ada"""
    if not CONFIG_FILE.exists():
        try:
            example_config = """YOUR_BOT_TOKEN_HERE
YOUR_ADMIN_ID_NUMBER
off
6h

# Format file konfigurasi:
# Line 1: Bot Token dari @BotFather
# Line 2: Admin ID (numeric, gunakan @userinfobot untuk mendapatkan ID)
# Line 3: Status backup (on/off)
# Line 4: Interval (1m, 30m, 1h, 6h, 12h, 24h)
"""
            
            with open(CONFIG_FILE, 'w') as f:
                f.write(example_config)
            
            logger.info(f"📄 File konfigurasi contoh dibuat: {CONFIG_FILE}")
            return True
        except Exception as e:
            logger.error(f"❌ Gagal membuat file konfigurasi: {e}")
            return False
    return True

def run_as_daemon():
    """Menjalankan sebagai daemon"""
    logger.info("👻 Menjalankan sebagai daemon...")
    
    # Ganti direktori kerja
    os.chdir('/')
    
    # Fork pertama
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process keluar
            sys.exit(0)
    except OSError as e:
        logger.error(f"❌ Fork pertama gagal: {e}")
        sys.exit(1)
    
    # Dekouple dari terminal
    os.setsid()
    os.umask(0)
    
    # Fork kedua
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process keluar
            sys.exit(0)
    except OSError as e:
        logger.error(f"❌ Fork kedua gagal: {e}")
        sys.exit(1)
    
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    
    si = open(os.devnull, 'r')
    so = open(os.devnull, 'a+')
    se = open(os.devnull, 'a+')
    
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())
    
    # Tulis PID file
    write_pid_file()

def run_bot():
    """Fungsi utama untuk menjalankan bot"""
    logger.info("=" * 50)
    logger.info("🤖 BACKUP BOT VPS")
    logger.info("=" * 50)
    
    # Buat file konfigurasi contoh jika tidak ada
    if not CONFIG_FILE.exists():
        logger.info(f"📄 Membuat file konfigurasi contoh di: {CONFIG_FILE}")
        create_config_file()
    
    # Cek konfigurasi
    logger.info("🔍 Memeriksa konfigurasi...")
    if not bot.check_config():
        logger.error("\n❌ Bot tidak dapat dimulai karena konfigurasi tidak valid!")
        logger.error(f"📝 Silakan edit file: {CONFIG_FILE}")
        logger.error("🔄 Setelah mengedit, jalankan bot kembali.")
        sys.exit(1)
    
    logger.info("✅ Konfigurasi valid!")
    logger.info(f"   Token: {'*' * 20}{bot.token[-10:] if bot.token else 'N/A'}")
    logger.info(f"   Admin ID: {bot.admin_id}")
    logger.info(f"   Status: {bot.backup_status}")
    logger.info(f"   Interval: {bot.current_interval}")
    
    # Buat event loop baru
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot.loop = loop
    
    # Buat aplikasi bot
    try:
        application = Application.builder().token(bot.token).build()
        bot.application = application
        
        # Tambahkan handler
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        
        # Error handler
        application.add_error_handler(error_handler)
        
        # Setup scheduler awal
        bot.setup_scheduler()
        
        # Jalankan scheduler di thread terpisah
        schedule_thread = threading.Thread(target=schedule_runner, daemon=True)
        schedule_thread.start()
        
        logger.info("\n" + "=" * 50)
        logger.info("🚀 Backup Bot sedang berjalan...")
        logger.info("👤 Bot hanya merespons Admin ID: %s", bot.admin_id)
        logger.info("📊 Backup Status: %s", bot.backup_status)
        logger.info("⏰ Interval: %s", bot.current_interval if bot.current_interval else "Tidak aktif")
        logger.info("📱 Kirim /start ke bot untuk memulai")
        logger.info("📝 Log disimpan di: %s", LOG_FILE)
        logger.info("=" * 50 + "\n")
        
        try:
            # Jalankan bot dalam event loop
            application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)
        except KeyboardInterrupt:
            logger.info("\n🛑 Bot dihentikan oleh user...")
        except Exception as e:
            logger.error(f"❌ Error saat polling: {e}")
        finally:
            bot.is_running = False
            if loop and not loop.is_closed():
                loop.close()
            remove_pid_file()
            logger.info("👋 Bot berhenti")
                
    except Exception as e:
        logger.error(f"❌ Gagal memulai bot: {e}")
        logger.error("💡 Pastikan token bot valid dan koneksi internet tersedia.")
        remove_pid_file()
        sys.exit(1)

def main():
    """Entry point utama"""
    # Cek argumen command line
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "start":
            # Jalankan sebagai daemon
            run_as_daemon()
            run_bot()
        elif command == "stop":
            # Hentikan daemon
            if PID_FILE.exists():
                try:
                    with open(PID_FILE, 'r') as f:
                        pid = int(f.read().strip())
                    os.kill(pid, signal.SIGTERM)
                    print(f"✅ Mengirim signal stop ke PID {pid}")
                    time.sleep(2)
                    remove_pid_file()
                except Exception as e:
                    print(f"❌ Gagal menghentikan: {e}")
            else:
                print("❌ PID file tidak ditemukan. Bot mungkin tidak berjalan.")
        elif command == "status":
            # Cek status
            if PID_FILE.exists():
                try:
                    with open(PID_FILE, 'r') as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 0)  # Cek apakah process masih hidup
                    print(f"✅ Bot berjalan dengan PID {pid}")
                    print(f"📝 Log file: {LOG_FILE}")
                    print(f"⚙️ Config file: {CONFIG_FILE}")
                except OSError:
                    print("❌ PID ada tetapi process tidak berjalan")
                    remove_pid_file()
            else:
                print("❌ Bot tidak berjalan")
        elif command == "restart":
            # Restart bot
            if PID_FILE.exists():
                try:
                    with open(PID_FILE, 'r') as f:
                        pid = int(f.read().strip())
                    os.kill(pid, signal.SIGTERM)
                    print(f"✅ Menghentikan bot (PID {pid})...")
                    time.sleep(3)
                except:
                    pass
            
            # Jalankan kembali
            print("🚀 Menjalankan bot kembali...")
            os.execl(sys.executable, sys.executable, *sys.argv)
        elif command == "logs":
            # Tampilkan logs
            if LOG_FILE.exists():
                os.system(f"tail -f {LOG_FILE}")
            else:
                print(f"❌ Log file tidak ditemukan: {LOG_FILE}")
        elif command == "config":
            # Edit config
            editor = os.environ.get('EDITOR', 'nano')
            os.system(f"{editor} {CONFIG_FILE}")
        elif command in ["help", "-h", "--help"]:
            print("""
🤖 Backup Bot VPS - Systemd Service

Penggunaan:
  python3 backup-bot.py [command]

Commands:
  start     - Jalankan bot sebagai daemon
  stop      - Hentikan bot
  restart   - Restart bot
  status    - Cek status bot
  logs      - Tampilkan log live
  config    - Edit file konfigurasi
  help      - Tampilkan bantuan ini

Tanpa command: Jalankan di foreground (debug)

Konfigurasi:
  Edit file: /opt/backup-bot/.bckupbot
  Format:
    Line 1: Bot Token
    Line 2: Admin ID
    Line 3: Status (on/off)
    Line 4: Interval (1m, 30m, 1h, 6h, 12h, 24h)
            """)
        else:
            print(f"❌ Command tidak dikenal: {command}")
            print("💡 Gunakan 'help' untuk melihat semua command")
    else:
        # Jalankan di foreground (debug mode)
        print("🔍 Debug mode - tekan Ctrl+C untuk berhenti")
        run_bot()

if __name__ == '__main__':
    main()
