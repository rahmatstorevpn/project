#!/usr/bin/env python3
import os
import sys
import time
import asyncio
import schedule
import threading
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Konfigurasi logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Path file konfigurasi
CONFIG_FILE = "/var/www/.bckupbot"

class BackupBot:
    def __init__(self):
        self.token = None
        self.admin_id = None
        self.backup_status = "off"
        self.current_interval = None
        self.application = None
        self.loop = None  # Menyimpan event loop
        
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
                # Jika dari file konfigurasi, admin_id masih string
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
            if os.path.exists(CONFIG_FILE):
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
            # Pastikan direktori ada
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            
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
    while True:
        schedule.run_pending()
        time.sleep(1)

def create_config_file():
    """Membuat file konfigurasi contoh jika tidak ada"""
    if not os.path.exists(CONFIG_FILE):
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            
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

def main():
    """Fungsi utama"""
    print("=" * 50)
    print("🤖 BACKUP BOT VPS")
    print("=" * 50)
    
    # Buat file konfigurasi contoh jika tidak ada
    if not os.path.exists(CONFIG_FILE):
        print(f"📄 Membuat file konfigurasi contoh di: {CONFIG_FILE}")
        create_config_file()
    
    # Cek konfigurasi
    print("🔍 Memeriksa konfigurasi...")
    if not bot.check_config():
        print("\n❌ Bot tidak dapat dimulai karena konfigurasi tidak valid!")
        print(f"📝 Silakan edit file: {CONFIG_FILE}")
        print("🔄 Setelah mengedit, jalankan bot kembali.")
        sys.exit(1)
    
    print("✅ Konfigurasi valid!")
    print(f"   Token: {'*' * 20}{bot.token[-10:] if bot.token else 'N/A'}")
    print(f"   Admin ID: {bot.admin_id}")
    print(f"   Status: {bot.backup_status}")
    print(f"   Interval: {bot.current_interval}")
    
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
        
        print("\n" + "=" * 50)
        print("🚀 Backup Bot sedang berjalan...")
        print("👤 Bot hanya merespons Admin ID:", bot.admin_id)
        print("📊 Backup Status:", bot.backup_status)
        print("⏰ Interval:", bot.current_interval if bot.current_interval else "Tidak aktif")
        print("📱 Kirim /start ke bot untuk memulai")
        print("⏹️ Tekan Ctrl+C untuk berhenti")
        print("=" * 50 + "\n")
        
        try:
            # Jalankan bot dalam event loop
            application.run_polling(allowed_updates=Update.ALL_TYPES)
        except KeyboardInterrupt:
            print("\n🛑 Bot dihentikan...")
        finally:
            if loop and not loop.is_closed():
                loop.close()
                
    except Exception as e:
        logger.error(f"❌ Gagal memulai bot: {e}")
        print(f"\n❌ Error: {e}")
        print("💡 Pastikan token bot valid dan koneksi internet tersedia.")
        sys.exit(1)

if __name__ == '__main__':
    main()