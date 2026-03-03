# -*- coding: utf-8 -*-
import os
import json
import paramiko
import asyncio
import logging
import httpx
import re
import requests
import hashlib
import uuid
import base64
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ConversationHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from pathlib import Path
from typing import Dict, Optional, Tuple
from threading import Thread
import time as time_module

# ============================================
# KONFIGURASI AWAL

# Token bot Telegram
BOT_TOKEN = "bot_tokke"

# Admin ID (ganti dengan ID Telegram Anda)
ADMIN_IDS = [admin]

GITHUB_TOKEN = ""  # Isi dengan token GitHub Anda
GITHUB_USERNAME = ""  # Username GitHub Anda
GITHUB_REPO = ""  # Nama repository
GITHUB_FILE_PATH = "ip"  # Path file di GitHub (bisa diubah)

# Database JSON files
DB_FOLDER = "database"
USERS_DB = f"{DB_FOLDER}/users.json"
VPS_DB = f"{DB_FOLDER}/vps.json"
PRICES_DB = f"{DB_FOLDER}/prices.json"
SERVER_PRICES_DB = f"{DB_FOLDER}/server_prices.json"
TRANSACTIONS_DB = f"{DB_FOLDER}/transactions.json"
ORDERS_DB = f"{DB_FOLDER}/orders.json"
ACCOUNTS_DB = f"{DB_FOLDER}/accounts.json"
TRIAL_ACCOUNTS_DB = f"{DB_FOLDER}/trial_accounts.json"

# TAMBAHKAN INI - KONSTANTA TOPUP SYSTEM
TOPUP_DB = f"{DB_FOLDER}/topup_transactions.json"  # File database untuk topup
QRIS_FOLDER = "qris"  # Folder untuk menyimpan QRIS
NOTIFICATIONS_FOLDER = "notifications"  # Folder untuk menyimpan file notifikasi pembayaran
USER_DATABASE = USERS_DB  # Alias untuk user database
VPS_DATABASE = VPS_DB  # Alias untuk VPS database
DATABASE_FILE = TOPUP_DB  # Alias untuk database topup
TOPUP_DATABASE_FILE = TOPUP_DB  # Nama file database topup

# Pengaturan topup
INVOICE_EXPIRY = 30  # Invoice berlaku 30 menit
MIN_TOPUP = 1000  # Minimal topup Rp 1,000
MAX_TOPUP = 1000000  # Maksimal topup Rp 1,000,000
NOTIFICATION_PATTERN = "%Y%m%d_%H%M%S"  # Pattern untuk nama file notifikasi

RENTAL_DB = f"{DB_FOLDER}/rental.json"


# Harga tambahan IP
EXTRA_IP_PRICE = 5000  # Rp 5,000 per IP tambahan


# OS List untuk rebuild
OS_LIST = {
    "opencloudos": ["8", "9", "23"],
    "rocky": ["8", "9", "10"],
    "oracle": ["8", "9", "10"],
    "almalinux": ["8", "9", "10"],
    "centos": ["9", "10"],
    "fnos": ["1"],
    "nixos": ["25.11"],
    "fedora": ["42", "43"],
    "debian": ["9", "10", "11", "12", "13"],
    "alpine": ["3.20", "3.21", "3.22", "3.23"],
    "opensuse": ["15.6", "16.0", "tumbleweed"],
    "openeuler": ["20.03", "22.03", "24.03", "25.09"],
    "ubuntu": ["16.04", "18.04", "20.04", "22.04", "24.04", "25.10"],
    "kali": [""],
    "arch": [""],
    "gentoo": [""],
    "aosc": [""],
    "windows": ["--image-name"],
    "dd": ["--img"],
    "netboot.xyz": [""]
}



# Status untuk ConversationHandler
(
    USER_UPGRADE_ACCOUNT,
    USER_SELECT_UPGRADE_TYPE,
    USER_UPGRADE_EXTEND,
    USER_UPGRADE_IP_LIMIT,
    USER_CONFIRM_UPGRADE,
    ADMIN_SET_IP_LIMIT,
    ADMIN_SET_IP_LIMIT_SELECT,
    ADMIN_SET_IP_LIMIT_VALUE,    
    ADMIN_ADD_VPS,
    ADMIN_ADD_VPS_IP,
    ADMIN_ADD_VPS_SSH_USER,
    ADMIN_ADD_VPS_SSH_PASS,
    ADMIN_ADD_VPS_SSH_PORT,
    ADMIN_ADD_VPS_NAME,
    ADMIN_ADD_VPS_DOMAIN,
    ADMIN_ADD_VPS_LOCATION,
    ADMIN_ADD_VPS_TYPE,
    ADMIN_SET_PRICE,
    ADMIN_SET_PRICE_TYPE,
    ADMIN_SET_PRICE_VALUE,
    ADMIN_ADD_VPS_PRICE,
    ADMIN_SET_SERVER_PRICE,
    ADMIN_SET_SERVER_PRICE_SELECT_VPS,
    ADMIN_SET_SERVER_PRICE_SELECT_SERVICE,
    ADMIN_SET_SERVER_PRICE_DURATION,
    ADMIN_SET_SERVER_PRICE_VALUE,
    ADMIN_SET_EXTRA_IP_PRICE,
    USER_BUY_VPN,
    USER_SELECT_VPS,
    USER_SELECT_SERVICE,
    USER_INPUT_USERNAME,
    USER_SELECT_DURATION,
    USER_CONFIRM_ORDER,
    USER_TOPUP,
    ADMIN_EDIT_VPS_START,
    ADMIN_EDIT_VPS_SELECT,
    ADMIN_EDIT_VPS_FIELD,
    ADMIN_EDIT_VPS_VALUE,
    ADMIN_DELETE_VPS,
    USER_CHECK_ACCOUNT,
    USER_INPUT_ACCOUNT_USERNAME,
    ADMIN_ADD_BALANCE_START,
    ADMIN_ADD_BALANCE_USER_ID,
    ADMIN_ADD_BALANCE_AMOUNT,
    ADMIN_ADD_BALANCE_CONFIRM,
    USER_TRIAL_VPN,
    USER_SELECT_EXTRA_IPS,
    USER_SELECT_TRIAL_SERVICE,
    USER_SELECT_TRIAL_VPS,
    USER_CREATE_TRIAL,
    USER_UPGRADE_QUOTA,
    USER_UPGRADE_CUSTOM_IP,
    USER_CONFIRM_UPGRADE_QUOTA,
    BROADCAST_TYPE, 
    BROADCAST_MESSAGE, 
    BROADCAST_CONFIRM,
    REBUILD_SELECT_VPS,
    REBUILD_SELECT_OS,
    REBUILD_SELECT_VERSION,
    REBUILD_SET_PASSWORD,
    REBUILD_CONFIRMATION,
    REBUILD_EXECUTE,
    AUTO_REBOOT_TIME,
    AUTO_REBOOT_DAYS,
    AUTO_REBOOT_CONFIRM,
) = range(65)

# ============================================
# UTILITAS DATABASE JSON
# ============================================


IP_LIMIT_DB = f"{DB_FOLDER}/ip_limits.json"

# ============================================
# SALDO UPDATE HANDLER (SINGLE SOURCE OF TRUTH)
# ============================================

class BalanceUpdateHandler:
    """
    SINGLE SOURCE OF TRUTH untuk update saldo user.
    Handler ini adalah SATU-SATUNYA tempat yang boleh menulis ke field 'balance' di users.json.
    
    Sistem menghitung saldo dengan rumus:
    SALDO = TOTAL TOPUP (completed) - TOTAL PENGELUARAN (completed)
    
    TOTAL PENGELUARAN mencakup:
    - Pembelian VPN (orders.json dengan type='purchase')
    - Pembelian rental script (orders.json dengan type='purchase' dan deskripsi mengandung 'Rental')
    - Perpanjangan rental (orders.json dengan type='purchase')
    - Upgrade akun (orders.json dengan type='purchase')
    - Pembelian IP tambahan (orders.json dengan type='purchase')
    """
    
    @staticmethod
    def calculate_user_balance(user_id: int) -> int:
        """
        Hitung saldo user berdasarkan:
        1. Total TOPUP dari topup_transactions.json (status='completed')
        2. Total PENGELUARAN dari orders.json (status='completed' dan type='purchase')
        
        Returns:
            int: Saldo akhir setelah dikurangi semua pengeluaran
        """
        try:
            # ==================== 1. HITUNG TOTAL TOPUP ====================
            topup_data = load_topup_database()
            total_topup = 0
            
            if str(user_id) in topup_data.get('users', {}):
                user_topup_data = topup_data['users'][str(user_id)]
                for transaction in user_topup_data.get('transactions', []):
                    if transaction.get('status') == 'completed':
                        amount = transaction.get('amount', 0)
                        total_topup += amount
                        
                        # Debug log
                        print(f"[CALC TOPUP] User {user_id}: +{amount} dari transaksi {transaction.get('invoice_code', 'N/A')}")
            
            # ==================== 2. HITUNG TOTAL PENGELUARAN ====================
            orders_data = load_json(ORDERS_DB)
            total_spent = 0
            
            for order_id, order in orders_data.items():
                # Hanya proses order dengan status completed
                if order.get('status') != 'completed':
                    continue
                
                # Hanya proses order dengan type 'purchase' (termasuk rental)
                if order.get('type') != 'purchase':
                    continue
                
                # Cek apakah order milik user ini
                if order.get('user_id') != user_id:
                    continue
                
                amount = order.get('amount', 0)
                description = order.get('description', '')
                
                # Tambahkan ke total pengeluaran
                total_spent += amount
                
                # Debug log dengan kategori
                if 'Rental' in description or 'rental' in description.lower():
                    print(f"[CALC RENTAL] User {user_id}: -{amount} untuk {description[:50]}")
                elif 'Pembelian' in description:
                    print(f"[CALC PURCHASE] User {user_id}: -{amount} untuk {description[:50]}")
                elif 'Perpanjangan' in description:
                    print(f"[CALC EXTEND] User {user_id}: -{amount} untuk {description[:50]}")
                elif 'Upgrade' in description:
                    print(f"[CALC UPGRADE] User {user_id}: -{amount} untuk {description[:50]}")
                else:
                    print(f"[CALC OTHER] User {user_id}: -{amount} untuk {description[:50]}")
            
            # ==================== 3. HITUNG SALDO AKHIR ====================
            final_balance = total_topup - total_spent
            
            # Pastikan tidak negatif (tapi jangan diubah manual, biarkan terlihat jika ada masalah)
            if final_balance < 0:
                print(f"[WARNING] User {user_id} memiliki saldo negatif: {final_balance}")
                print(f"  Topup: {total_topup}, Spent: {total_spent}")
                # Jangan force ke 0, biarkan terlihat untuk debugging
                # Tapi kembalikan 0 untuk keamanan transaksi
                final_balance = max(0, final_balance)
            
            print(f"[CALC FINAL] User {user_id}: Topup={total_topup}, Spent={total_spent}, Balance={final_balance}")
            return final_balance
            
        except Exception as e:
            print(f"[CALC ERROR] User {user_id}: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    @staticmethod
    def sync_user_balance(user_id: int) -> int:
        """
        SINGLE SOURCE OF TRUTH untuk update saldo di users.json.
        Hanya fungsi ini yang boleh menulis ke field 'balance'.
        
        Args:
            user_id: ID user yang akan di-sync
            
        Returns:
            int: Saldo baru setelah sync
        """
        try:
            # Hitung saldo terbaru dari semua sumber
            current_balance = BalanceUpdateHandler.calculate_user_balance(user_id)
            
            # Load users database
            users_data = load_json(USERS_DB)
            user_id_str = str(user_id)
            
            # Simpan balance lama untuk logging
            old_balance = 0
            
            # Update atau create user entry
            if user_id_str not in users_data:
                # User baru, buat entry lengkap
                users_data[user_id_str] = {
                    "user_id": user_id,
                    "balance": current_balance,
                    "role": "user",
                    "created_at": datetime.now().isoformat(),
                    "vpn_accounts": [],
                    "total_spent": 0,
                    "total_orders": 0,
                    "trial_used": False,
                    "last_sync": datetime.now().isoformat()
                }
                print(f"[BALANCE SYNC] User baru {user_id}: balance={current_balance}")
            else:
                # User existing, update balance
                old_balance = users_data[user_id_str].get("balance", 0)
                
                # HANYA update balance, jangan timpa field lain
                users_data[user_id_str]["balance"] = current_balance
                users_data[user_id_str]["last_sync"] = datetime.now().isoformat()
                
                # Update total_spent jika berbeda (optional)
                total_spent_calc = BalanceUpdateHandler.calculate_total_spent(user_id)
                if users_data[user_id_str].get("total_spent", 0) != total_spent_calc:
                    users_data[user_id_str]["total_spent"] = total_spent_calc
                
                # Update total_orders
                total_orders_calc = BalanceUpdateHandler.calculate_total_orders(user_id)
                if users_data[user_id_str].get("total_orders", 0) != total_orders_calc:
                    users_data[user_id_str]["total_orders"] = total_orders_calc
                
                print(f"[BALANCE SYNC] User {user_id}: {old_balance} -> {current_balance} (delta: {current_balance - old_balance})")
            
            # Save ke users.json
            save_json(USERS_DB, users_data)
            
            # ==================== SYNC KE TOPUP DATABASE ====================
            # Juga sync ke topup database untuk konsistensi
            try:
                topup_data = load_topup_database()
                if user_id_str not in topup_data.get('users', {}):
                    if 'users' not in topup_data:
                        topup_data['users'] = {}
                    topup_data['users'][user_id_str] = {
                        'balance': current_balance,
                        'transactions': [],
                        'username': users_data[user_id_str].get('username', ''),
                        'first_name': users_data[user_id_str].get('first_name', ''),
                        'last_sync': datetime.now().isoformat()
                    }
                else:
                    topup_data['users'][user_id_str]['balance'] = current_balance
                    topup_data['users'][user_id_str]['last_sync'] = datetime.now().isoformat()
                
                save_topup_database(topup_data)
            except Exception as e:
                print(f"[BALANCE SYNC] Gagal sync ke topup DB: {e}")
            
            return current_balance
            
        except Exception as e:
            print(f"[BALANCE SYNC ERROR] User {user_id}: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    @staticmethod
    def get_user_balance(user_id: int) -> int:
        """
        Mendapatkan saldo user dengan auto-sync terlebih dahulu.
        Selalu return saldo terbaru yang sudah disync.
        
        Args:
            user_id: ID user
            
        Returns:
            int: Saldo user saat ini
        """
        # Sync dulu sebelum ambil balance
        BalanceUpdateHandler.sync_user_balance(user_id)
        
        # Ambil dari users.json
        users_data = load_json(USERS_DB)
        user_id_str = str(user_id)
        
        if user_id_str in users_data:
            return users_data[user_id_str].get("balance", 0)
        
        return 0
    
    @staticmethod
    def calculate_total_spent(user_id: int) -> int:
        """
        Hitung total pengeluaran user dari semua order completed.
        
        Returns:
            int: Total pengeluaran
        """
        orders_data = load_json(ORDERS_DB)
        total_spent = 0
        
        for order_id, order in orders_data.items():
            if order.get('user_id') == user_id and order.get('status') == 'completed' and order.get('type') == 'purchase':
                total_spent += order.get('amount', 0)
        
        return total_spent
    
    @staticmethod
    def calculate_total_orders(user_id: int) -> int:
        """
        Hitung jumlah order user yang completed.
        
        Returns:
            int: Jumlah order
        """
        orders_data = load_json(ORDERS_DB)
        total_orders = 0
        
        for order_id, order in orders_data.items():
            if order.get('user_id') == user_id and order.get('status') == 'completed':
                total_orders += 1
        
        return total_orders
    
    @staticmethod
    def update_vpn_purchase(user_id: int, amount: int, description: str, metadata: dict = None) -> bool:
        """
        Update setelah pembelian VPN/Rental berhasil.
        Fungsi ini akan:
        1. Menambahkan order ke orders.json
        2. Trigger sync balance
        
        Args:
            user_id: ID user
            amount: Jumlah pembelian
            description: Deskripsi pembelian
            metadata: Data tambahan (optional)
            
        Returns:
            bool: True jika berhasil
        """
        try:
            # Buat order data
            order_data = {
                "user_id": user_id,
                "type": "purchase",
                "amount": amount,
                "description": description,
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }
            
            # Tambah metadata jika ada
            if metadata:
                order_data.update(metadata)
            
            # Simpan order ke database
            order_id = add_order(order_data)
            
            # Trigger sync balance - PASTIKAN INI DIPANGGIL
            new_balance = BalanceUpdateHandler.sync_user_balance(user_id)
            
            print(f"[PURCHASE SUCCESS] User {user_id}: -{amount} untuk '{description}'")
            print(f"[PURCHASE SUCCESS] Order ID: {order_id}")
            print(f"[PURCHASE SUCCESS] New balance: {new_balance}")
            
            return True
            
        except Exception as e:
            print(f"[PURCHASE ERROR] User {user_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def update_topup(user_id: int, amount: int, invoice_code: str, metadata: dict = None) -> bool:
        """
        Update setelah topup berhasil.
        
        Args:
            user_id: ID user
            amount: Jumlah topup
            invoice_code: Kode invoice
            metadata: Data tambahan (optional)
            
        Returns:
            bool: True jika berhasil
        """
        try:
            # Tambahkan transaksi topup
            transaction = add_topup_transaction(user_id, amount, invoice_code, status='completed')
            
            # Trigger sync balance
            new_balance = BalanceUpdateHandler.sync_user_balance(user_id)
            
            print(f"[TOPUP SUCCESS] User {user_id}: +{amount} via invoice {invoice_code}")
            print(f"[TOPUP SUCCESS] New balance: {new_balance}")
            
            return True
            
        except Exception as e:
            print(f"[TOPUP ERROR] User {user_id}: {e}")
            return False
    
    @staticmethod
    def validate_user_balance(user_id: int, required_amount: int) -> bool:
        """
        Validasi apakah user punya saldo cukup untuk transaksi.
        
        Args:
            user_id: ID user
            required_amount: Jumlah yang dibutuhkan
            
        Returns:
            bool: True jika saldo cukup
        """
        current_balance = BalanceUpdateHandler.get_user_balance(user_id)
        is_valid = current_balance >= required_amount
        
        if not is_valid:
            print(f"[VALIDATION] User {user_id}: Saldo {current_balance} < Required {required_amount}")
        else:
            print(f"[VALIDATION] User {user_id}: Saldo cukup ({current_balance} >= {required_amount})")
        
        return is_valid
    
    @staticmethod
    def get_user_financial_summary(user_id: int) -> dict:
        """
        Dapatkan summary finansial user secara lengkap.
        
        Returns:
            dict: {
                'user_id': int,
                'total_topup': int,
                'total_spent': int,
                'current_balance': int,
                'total_orders': int,
                'rental_spent': int,
                'vpn_spent': int,
                'last_sync': str
            }
        """
        # Hitung dari source data
        topup_data = load_topup_database()
        orders_data = load_json(ORDERS_DB)
        
        total_topup = 0
        total_spent = 0
        rental_spent = 0
        vpn_spent = 0
        total_orders = 0
        
        # Hitung total topup
        if str(user_id) in topup_data.get('users', {}):
            user_topup_data = topup_data['users'][str(user_id)]
            for transaction in user_topup_data.get('transactions', []):
                if transaction.get('status') == 'completed':
                    total_topup += transaction.get('amount', 0)
        
        # Hitung total pengeluaran dan kategorinya
        for order_id, order in orders_data.items():
            if order.get('user_id') == user_id and order.get('status') == 'completed':
                if order.get('type') == 'purchase':
                    amount = order.get('amount', 0)
                    total_spent += amount
                    total_orders += 1
                    
                    # Kategorikan berdasarkan deskripsi
                    description = order.get('description', '').lower()
                    if 'rental' in description or 'sewa' in description:
                        rental_spent += amount
                    else:
                        vpn_spent += amount
        
        current_balance = BalanceUpdateHandler.get_user_balance(user_id)
        
        summary = {
            "user_id": user_id,
            "total_topup": total_topup,
            "total_spent": total_spent,
            "current_balance": current_balance,
            "total_orders": total_orders,
            "total_vpn_spent": vpn_spent,
            "rental_spent": rental_spent,
            "vpn_spent": vpn_spent,
            "last_sync": datetime.now().isoformat()
        }
        
        print(f"[SUMMARY] User {user_id}: {summary}")
        return summary
    
    @staticmethod
    def force_sync_all_users() -> dict:
        """
        FORCE SYNC semua user yang ada di database.
        Berguna untuk maintenance atau perbaikan data.
        
        Returns:
            dict: Statistik hasil sync
        """
        users_data = load_json(USERS_DB)
        sync_stats = {
            "total_users": len(users_data),
            "synced": 0,
            "failed": 0,
            "balance_changes": [],
            "total_balance_before": 0,
            "total_balance_after": 0
        }
        
        print("\n" + "="*50)
        print("FORCE SYNC ALL USERS - STARTED")
        print("="*50)
        
        # Hitung total balance sebelum sync
        for user_id_str, user_data in users_data.items():
            sync_stats["total_balance_before"] += user_data.get("balance", 0)
        
        # Sync setiap user
        for user_id_str in users_data.keys():
            try:
                user_id = int(user_id_str)
                old_balance = users_data[user_id_str].get("balance", 0)
                
                new_balance = BalanceUpdateHandler.sync_user_balance(user_id)
                
                if new_balance != old_balance:
                    sync_stats["balance_changes"].append({
                        "user_id": user_id,
                        "old": old_balance,
                        "new": new_balance,
                        "delta": new_balance - old_balance
                    })
                    print(f"✓ User {user_id}: {old_balance} -> {new_balance} (delta: {new_balance - old_balance})")
                
                sync_stats["synced"] += 1
                
            except Exception as e:
                print(f"✗ User {user_id_str} gagal: {e}")
                sync_stats["failed"] += 1
        
        # Hitung total balance setelah sync
        users_data_after = load_json(USERS_DB)
        for user_id_str, user_data in users_data_after.items():
            sync_stats["total_balance_after"] += user_data.get("balance", 0)
        
        print("="*50)
        print(f"SYNC COMPLETED:")
        print(f"  Total Users: {sync_stats['total_users']}")
        print(f"  Synced: {sync_stats['synced']}")
        print(f"  Failed: {sync_stats['failed']}")
        print(f"  Users with changes: {len(sync_stats['balance_changes'])}")
        print(f"  Total Balance Before: {sync_stats['total_balance_before']}")
        print(f"  Total Balance After: {sync_stats['total_balance_after']}")
        print(f"  Total Delta: {sync_stats['total_balance_after'] - sync_stats['total_balance_before']}")
        print("="*50)
        
        return sync_stats
    
    @staticmethod
    def debug_user_transactions(user_id: int) -> dict:
        """
        Debug function untuk melihat semua transaksi user.
        
        Returns:
            dict: Detail semua transaksi user
        """
        result = {
            "user_id": user_id,
            "topup_transactions": [],
            "order_transactions": [],
            "total_topup": 0,
            "total_spent": 0,
            "calculated_balance": 0,
            "actual_balance": 0
        }
        
        # Ambil topup transactions
        topup_data = load_topup_database()
        if str(user_id) in topup_data.get('users', {}):
            for tx in topup_data['users'][str(user_id)].get('transactions', []):
                if tx.get('status') == 'completed':
                    result["topup_transactions"].append({
                        "amount": tx.get('amount'),
                        "invoice": tx.get('invoice_code'),
                        "timestamp": tx.get('timestamp')
                    })
                    result["total_topup"] += tx.get('amount', 0)
        
        # Ambil order transactions
        orders_data = load_json(ORDERS_DB)
        for order_id, order in orders_data.items():
            if order.get('user_id') == user_id and order.get('status') == 'completed':
                result["order_transactions"].append({
                    "order_id": order_id,
                    "amount": order.get('amount'),
                    "description": order.get('description'),
                    "timestamp": order.get('created_at')
                })
                result["total_spent"] += order.get('amount', 0)
        
        result["calculated_balance"] = result["total_topup"] - result["total_spent"]
        
        # Ambil actual balance dari users.json
        users_data = load_json(USERS_DB)
        if str(user_id) in users_data:
            result["actual_balance"] = users_data[str(user_id)].get("balance", 0)
        
        return result


def get_user(user_id):
    """Get user data from database"""
    if not os.path.exists(USER_DATABASE):
        return {
            "user_id": user_id,
            "balance": 0,
            "role": "user",
            "created_at": datetime.now().isoformat(),
            "vpn_accounts": [],
            "total_orders": 0,
            "total_spent": 0,
            "username": "",
            "first_name": ""
        }
    
    with open(USER_DATABASE, 'r') as f:
        data = json.load(f)
    
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {
            "user_id": user_id,
            "balance": 0,
            "role": "user",
            "created_at": datetime.now().isoformat(),
            "vpn_accounts": [],
            "total_orders": 0,
            "total_spent": 0,
            "username": "",
            "first_name": ""
        }
        save_user_database(data)
    
    return data[user_id_str]

def is_admin(user_id):
    """Cek apakah user adalah admin"""
    global ADMIN_IDS
    
    # Handle jika ADMIN_IDS adalah list
    if isinstance(ADMIN_IDS, (list, tuple, set)):
        return user_id in ADMIN_IDS
    
    # Handle jika ADMIN_IDS adalah integer tunggal
    elif isinstance(ADMIN_IDS, int):
        return user_id == ADMIN_IDS
    
    # Handle jika ADMIN_IDS adalah string (mungkin user_id dalam string)
    elif isinstance(ADMIN_IDS, str):
        try:
            admin_id = int(ADMIN_IDS)
            return user_id == admin_id
        except:
            return False
    
    # Fallback
    return False


def update_user(user_id, user_data):
    """Update user data in database"""
    if not os.path.exists(USER_DATABASE):
        data = {}
    else:
        with open(USER_DATABASE, 'r') as f:
            data = json.load(f)
    
    data[str(user_id)] = user_data
    save_user_database(data)

def save_user_database(data):
    """Save user database"""
    with open(USER_DATABASE, 'w') as f:
        json.dump(data, f, indent=4)

# ==================== TOPUP SYSTEM DATABASE ====================

def load_topup_database():
    """Load topup system database"""
    if not os.path.exists(TOPUP_DATABASE_FILE):
        default_data = {
            'users': {},
            'system': {
                'current_qris': 'qris_default.png',
                'last_transaction_id': 0
            }
        }
        save_topup_database(default_data)
        return default_data
    
    with open(TOPUP_DATABASE_FILE, 'r') as f:
        return json.load(f)

def save_topup_database(data):
    """Save topup database"""
    with open(TOPUP_DATABASE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_topup_user(user_id):
    """Get user data from topup database"""
    data = load_topup_database()
    user_id_str = str(user_id)
    
    # Jika user tidak ada di database topup
    if user_id_str not in data['users']:
        # Coba ambil dari main database
        user_info = get_user(user_id)
        
        # Inisialisasi user baru di database topup
        data['users'][user_id_str] = {
            'balance': user_info.get('balance', 0),
            'transactions': [],
            'username': user_info.get('username', ''),
            'first_name': user_info.get('first_name', ''),
            'joined_date': datetime.now().isoformat()
        }
        save_topup_database(data)
    
    return data['users'][user_id_str]


def update_topup_user(user_id, user_data):
    """Update user in topup database"""
    data = load_topup_database()
    data['users'][str(user_id)] = user_data
    save_topup_database(data)
    
    # Also update main user database balance
    main_user = get_user(user_id)
    main_user['balance'] = user_data.get('balance', 0)
    update_user(user_id, main_user)

def get_topup_system():
    """Get system data from topup database"""
    data = load_topup_database()
    return data['system']

def update_topup_system(system_data):
    """Update system data in topup database"""
    data = load_topup_database()
    data['system'] = system_data
    save_topup_database(data)

def add_topup_transaction(user_id, amount, invoice_code, status='pending'):
    """Add transaction to topup database"""
    data = load_topup_database()
    user_id_str = str(user_id)
    transaction_id = data['system']['last_transaction_id'] + 1
    
    transaction = {
        'id': transaction_id,
        'user_id': user_id,  # TAMBAHKAN ini
        'amount': amount,
        'invoice_code': invoice_code,
        'status': status,
        'timestamp': datetime.now().isoformat(),
        'validated_at': None,
        'validator': invoice_code % 1000
    }
    
    if user_id_str not in data['users']:
        get_topup_user(user_id)  # Initialize user if not exists
    
    if 'transactions' not in data['users'][user_id_str]:
        data['users'][user_id_str]['transactions'] = []
        
    data['users'][user_id_str]['transactions'].append(transaction)
    data['system']['last_transaction_id'] = transaction_id
    save_topup_database(data)
    
    return transaction


def validate_topup_transaction(invoice_code):
    """Validate transaction berdasarkan invoice_code dengan sistem baru"""
    try:
        data = load_topup_database()
        
        for user_id, user_data in data['users'].items():
            if 'transactions' not in user_data:
                continue
                
            for transaction in user_data['transactions']:
                if (transaction['invoice_code'] == invoice_code and 
                    transaction['status'] == 'pending'):
                    
                    # Update transaction status
                    transaction['status'] = 'completed'
                    transaction['validated_at'] = datetime.now().isoformat()
                    
                    # Gunakan handler untuk update topup
                    BalanceUpdateHandler.update_topup(
                        int(user_id), 
                        transaction['amount'], 
                        invoice_code
                    )
                    
                    save_topup_database(data)
                    
                    return int(user_id), BalanceUpdateHandler.get_user_balance(int(user_id))
        
        return None, 0
    except Exception as e:
        print(f"[VALIDATION ERROR] {e}")
        return None, 0

# ==================== UTILITY FUNCTIONS ====================

def generate_invoice_code(amount):
    """Generate invoice code dengan mengganti 3 digit terakhir dengan validator"""
    # Validator random 3 digit (097, 123, 456, dst)
    validator = random.randint(100, 999)  # 100-999 untuk 3 digit
    
    # Format: jumlah, tapi 3 digit terakhir diganti dengan validator
    # Contoh: amount=10000, validator=097 -> 10097
    #         amount=50000, validator=123 -> 50123
    
    # Pastikan amount minimal 1000 (4 digit)
    if amount < 1000:
        # Jika kurang dari 1000, tambah digit
        invoice_code = int(f"{amount}{validator:03d}")
    else:
        # Ambil semua digit kecuali 3 terakhir, lalu tambah validator
        amount_str = str(amount)
        if len(amount_str) > 3:
            # Ganti 3 digit terakhir dengan validator
            base_amount = int(amount_str[:-3])  # Ambil bagian depan
            invoice_code = int(f"{base_amount}{validator:03d}")
        else:
            # Jika jumlah digit <= 3, gabungkan saja
            invoice_code = int(f"{amount}{validator:03d}")
    
    return invoice_code, validator

                

def extract_amount_from_invoice(invoice_code):
    """
    Extract original amount from invoice_code yang 3 digit terakhir adalah validator.
    Mendukung invoice code dengan titik sebagai pemisah ribuan.
    
    Args:
        invoice_code: String atau integer yang mungkin mengandung titik (misal: '10.097', '1.000.097')
    
    Returns:
        tuple: (original_amount, validator)
    """
    # Konversi ke string dan hapus titik pemisah ribuan
    invoice_str = str(invoice_code).replace('.', '')
    
    # Validasi bahwa string hanya berisi digit
    if not invoice_str.isdigit():
        raise ValueError(f"Invalid invoice code format: {invoice_code}")
    
    if len(invoice_str) <= 3:
        # Jika invoice code <= 3 digit, semuanya adalah amount
        amount = int(invoice_str)
        # Jika <= 3 digit, anggap tidak ada validator
        return amount, 0
    
    # 3 digit terakhir adalah validator
    validator = int(invoice_str[-3:])
    
    # Digit sebelum validator adalah base amount
    base_amount_str = invoice_str[:-3]
    
    if base_amount_str == "":
        base_amount = 0
    else:
        base_amount = int(base_amount_str)
    
    # Rekonstruksi amount asli: base_amount * 1000
    original_amount = base_amount * 1000
    
    return original_amount, validator
            

def init_database():
    """Inisialisasi database JSON secara lengkap"""
    import os
    import json
    from pathlib import Path
    
    # Buat folder database jika belum ada
    Path(DB_FOLDER).mkdir(exist_ok=True)
    
    # ==================== INISIALISASI TOPUP SYSTEM ====================
    
    # Inisialisasi folder qris
    Path(QRIS_FOLDER).mkdir(exist_ok=True)
    
    # Inisialisasi folder notifications
    Path(NOTIFICATIONS_FOLDER).mkdir(exist_ok=True)
    
    # Inisialisasi topup_transactions.json
    if not os.path.exists(TOPUP_DATABASE_FILE):
        default_data = {
            'users': {},
            'system': {
                'current_qris': 'qris_default.png',
                'last_transaction_id': 0
            }
        }
        save_topup_database(default_data)
    
    # Buat file QRIS default jika belum ada
    default_qris_path = os.path.join(QRIS_FOLDER, "qris_default.png")
    if not os.path.exists(default_qris_path):
        # Buat file PNG kosong (bisa diupload nanti oleh admin)
        from PIL import Image
        img = Image.new('RGB', (500, 500), color='white')
        img.save(default_qris_path)
    
    # ==================== INISIALISASI VPN SYSTEM ====================
    
    # Inisialisasi users.json
    if not os.path.exists(USER_DATABASE):
        with open(USER_DATABASE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    # Inisialisasi vps.json
    if not os.path.exists(VPS_DATABASE):
        with open(VPS_DATABASE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    # Inisialisasi prices.json
    if not os.path.exists(PRICES_DB):
        default_prices = {
            "ssh": {
                "7": 3000,
                "15": 5000,
                "30": 12000,
                "90": 30000,
                "365": 90000
            },
            "vmess": {
                "7": 3000,
                "15": 5000,
                "30": 12000,
                "90": 30000,
                "365": 90000
            },
            "vless": {
                "7": 3000,
                "15": 5000,
                "30": 12000,
                "90": 30000,
                "365": 90000
            },
            "trojan": {
                "7": 3000,
                "15": 5000,
                "30": 12000,
                "90": 30000,
                "365": 90000
            },
            "ss": {
                "7": 3000,
                "15": 5000,
                "30": 12000,
                "90": 30000,
                "365": 90000
            },
            "zivpn": {
                "7": 3000,
                "15": 5000,
                "30": 12000,
                "90": 30000,
                "365": 90000
            }
        }
        with open(PRICES_DB, 'w', encoding='utf-8') as f:
            json.dump(default_prices, f, indent=4, ensure_ascii=False)
    
    # Inisialisasi server_prices.json
    if not os.path.exists(SERVER_PRICES_DB):
        with open(SERVER_PRICES_DB, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    # Inisialisasi transactions.json
    if not os.path.exists(TRANSACTIONS_DB):
        with open(TRANSACTIONS_DB, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    # Inisialisasi orders.json
    if not os.path.exists(ORDERS_DB):
        with open(ORDERS_DB, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    # Inisialisasi accounts.json
    if not os.path.exists(ACCOUNTS_DB):
        with open(ACCOUNTS_DB, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    # Inisialisasi trial_accounts.json
    if not os.path.exists(TRIAL_ACCOUNTS_DB):
        with open(TRIAL_ACCOUNTS_DB, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    # Inisialisasi ip_limits.json
    if not os.path.exists(IP_LIMIT_DB):
        with open(IP_LIMIT_DB, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    # Inisialisasi auto_reboot.json
    if not os.path.exists(f"{DB_FOLDER}/auto_reboot.json"):
        with open(f"{DB_FOLDER}/auto_reboot.json", 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    # Inisialisasi broadcast_logs.json
    if not os.path.exists(f"{DB_FOLDER}/broadcast_logs.json"):
        with open(f"{DB_FOLDER}/broadcast_logs.json", 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    print(f"[INIT] Database initialized successfully")
    print(f"[INIT] Topup system ready: {TOPUP_DATABASE_FILE}")
    print(f"[INIT] QRIS folder: {QRIS_FOLDER}")
    print(f"[INIT] Notifications folder: {NOTIFICATIONS_FOLDER}")
                    



def get_topup_transaction(tx_id: str) -> Optional[Dict]:
    """Get topup transaction by ID"""
    transactions = load_json(TOPUP_DB)
    return transactions.get(tx_id)

def update_topup_transaction(tx_id: str, updates: Dict):
    """Update topup transaction"""
    transactions = load_json(TOPUP_DB)
    if tx_id in transactions:
        transactions[tx_id].update(updates)
        save_json(TOPUP_DB, transactions)

def get_user_topup_transactions(user_id: int, limit: int = 10) -> List[Dict]:
    """Get topup transactions by user ID"""
    transactions = load_json(TOPUP_DB)
    user_transactions = []
    
    for tx_id, tx_data in transactions.items():
        if tx_data.get("user_id") == user_id:
            user_transactions.append(tx_data)
    
    # Sort by created_at descending
    user_transactions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return user_transactions[:limit]

# ============================================
# RENTAL DATABASE - VERSI LENGKAP DENGAN SLOT SYSTEM
# ============================================

class RentalDatabase:
    """Database untuk sistem sewa script dengan slot individual"""
    
    def __init__(self):
        self.data = self.load()
        self.migrate_database()  # Migrasi database lama ke struktur baru
    
    def load(self):
        """Load data rental dari file JSON"""
        if os.path.exists(RENTAL_DB):
            try:
                with open(RENTAL_DB, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[ERROR] Gagal load database: {e}")
                return self.get_default_data()
        else:
            return self.get_default_data()
    
    def get_default_data(self):
        """Data default untuk rental system dengan slot individual"""
        return {
            "users": [],  # List user yang memiliki akses
            "ips": [],    # List semua IP (untuk lookup cepat)
            "settings": {
                "price_per_month": 10000,      # Harga per bulan (legacy)
                "price_per_slot": 10000,       # Harga per slot tambahan
                "github_token": "",
                "github_username": "",
                "github_repo": "",
                "github_file_path": "ip",
                "auto_sync": True,
                "max_slots_per_user": 10,       # Maksimal slot per user
                "default_ips_per_slot": 1,      # Default IP per slot
                "db_version": "2.0"              # Versi database untuk migrasi
            }
        }
    
    def migrate_database(self):
        """
        Migrasi database dari struktur lama ke struktur baru dengan slot system
        """
        try:
            settings = self.data["settings"]
            users = self.data["users"]
            
            # ========== 1. MIGRASI SETTINGS ==========
            
            # Tambahkan price_per_slot jika belum ada
            if "price_per_slot" not in settings:
                if "price_per_month" in settings:
                    settings["price_per_slot"] = settings["price_per_month"]
                    print(f"[MIGRASI] price_per_slot = {settings['price_per_slot']} dari price_per_month")
                else:
                    settings["price_per_slot"] = 50000
                    print("[MIGRASI] price_per_slot = 50000 (default)")
            
            # Tambahkan max_slots_per_user jika belum ada
            if "max_slots_per_user" not in settings:
                settings["max_slots_per_user"] = 10
                print("[MIGRASI] max_slots_per_user = 10 (default)")
            
            # Tambahkan default_ips_per_slot jika belum ada
            if "default_ips_per_slot" not in settings:
                settings["default_ips_per_slot"] = 1
                print("[MIGRASI] default_ips_per_slot = 1 (default)")
            
            # Tambahkan db_version jika belum ada
            if "db_version" not in settings:
                settings["db_version"] = "2.0"
            
            # ========== 2. MIGRASI USER DATA ==========
            
            migration_count = 0
            for user in users:
                # Cek apakah user masih menggunakan struktur lama (tanpa slots)
                if 'slots' not in user and ('expiry_date' in user or 'ips' in user):
                    print(f"[MIGRASI] Migrasi user {user.get('user_id')} - {user.get('username')}")
                    
                    # Buat slot pertama dari data lama
                    first_slot = {
                        "slot_id": str(uuid.uuid4())[:8],
                        "slot_number": 1,
                        "expiry_date": user.get('expiry_date', 'lifetime'),
                        "max_ips_per_slot": settings.get("default_ips_per_slot", 1),
                        "used_ips": len(user.get('ips', [])),
                        "ips": user.get('ips', []),
                        "created_at": user.get('registered_at', datetime.now().isoformat()),
                        "last_renewed": user.get('last_payment', datetime.now().isoformat()),
                        "status": "active",
                        "purchase_history": []
                    }
                    
                    # Pindahkan IP ke slot
                    for ip in first_slot["ips"]:
                        ip["slot_id"] = first_slot["slot_id"]
                    
                    # Update user dengan struktur baru
                    user['slots'] = [first_slot]
                    user['total_slots'] = 1
                    user['next_slot_number'] = 2
                    
                    # Hapus data lama (optional, bisa dibiarkan)
                    # user.pop('expiry_date', None)
                    # user.pop('ips', None)
                    # user.pop('used_slots', None)
                    # user.pop('max_slots', None)
                    
                    migration_count += 1
                
                # Pastikan user punya field slots (untuk user baru)
                elif 'slots' not in user:
                    user['slots'] = []
                    user['total_slots'] = 0
                    user['next_slot_number'] = 1
            
            # ========== 3. MIGRASI IP DATA ==========
            
            # Update global IP list dengan slot_id
            for ip in self.data["ips"]:
                if 'slot_id' not in ip:
                    # Cari slot pemilik IP ini
                    for user in users:
                        for slot in user.get('slots', []):
                            for slot_ip in slot.get('ips', []):
                                if slot_ip.get('ip') == ip.get('ip'):
                                    ip['slot_id'] = slot.get('slot_id')
                                    break
            
            if migration_count > 0:
                print(f"[MIGRASI] {migration_count} user berhasil dimigrasi ke slot system")
                self.save()
            
        except Exception as e:
            print(f"[ERROR MIGRASI] {e}")
            import traceback
            traceback.print_exc()
    
    # ========== MANAJEMEN USER ==========
    
    def add_user(self, user_id, username, months, price_per_month=None):
        """Tambah user baru ke sistem rental (legacy, untuk kompatibilitas)"""
        if price_per_month is None:
            price_per_month = self.data["settings"]["price_per_month"]
        
        total_price = months * price_per_month
        
        # Cek apakah user sudah ada
        existing_user = self.get_user(user_id)
        if existing_user:
            # Update existing user - tambah slot baru
            success, result = self.add_slot(user_id, months, price_per_month)
            if success:
                existing_user["total_spent"] = existing_user.get("total_spent", 0) + total_price
                existing_user["last_payment"] = datetime.now().isoformat()
                self.save()
                return True
            return False
        else:
            # Buat user baru dengan 1 slot
            user_data = {
                "user_id": user_id,
                "username": username,
                "registered_at": datetime.now().isoformat(),
                "total_spent": total_price,
                "last_payment": datetime.now().isoformat(),
                "status": "active",
                "slots": [],
                "total_slots": 0,
                "next_slot_number": 1
            }
            self.data["users"].append(user_data)
            self.save()
            
            # Tambah slot pertama
            success, result = self.add_slot(user_id, months, price_per_month)
            return success
    
    def get_user(self, user_id):
        """Get user berdasarkan ID"""
        for user in self.data["users"]:
            if user["user_id"] == user_id:
                return user
        return None
    
    def get_all_users(self):
        """Get semua user terdaftar"""
        return self.data["users"]
    
    def update_user(self, user_id, **kwargs):
        """Update data user"""
        user = self.get_user(user_id)
        if user:
            for key, value in kwargs.items():
                user[key] = value
            self.save()
            return True
        return False
    
    def delete_user(self, user_id):
        """Hapus user beserta semua IP-nya"""
        user = self.get_user(user_id)
        if user:
            # Hapus semua IP milik user dari semua slot
            for slot in user.get('slots', []):
                for ip_data in slot.get('ips', []):
                    self.remove_ip(ip_data["ip"])
            
            # Hapus user
            self.data["users"] = [u for u in self.data["users"] if u["user_id"] != user_id]
            self.save()
            return True
        return False
    
    def check_user_access(self, user_id):
        """Cek apakah user masih memiliki akses (setidaknya 1 slot aktif)"""
        user = self.get_user(user_id)
        if not user:
            return False
        
        for slot in user.get('slots', []):
            if self.is_slot_active(slot):
                return True
        
        return False
    
    def get_expired_users(self):
        """Get list user yang sudah expired (semua slotnya expired)"""
        expired = []
        for user in self.data["users"]:
            if not self.check_user_access(user["user_id"]):
                expired.append(user)
        return expired
    
    # ========== MANAJEMEN SLOT ==========
    
    def add_slot(self, user_id, months, price_per_slot=None):
        """
        Tambah slot baru untuk user
        
        Args:
            user_id: ID user
            months: Jumlah bulan untuk slot ini (0 = lifetime)
            price_per_slot: Harga per slot (optional)
            
        Returns:
            tuple: (success, slot_data or error_message)
        """
        try:
            user = self.get_user(user_id)
            if not user:
                return False, "User tidak ditemukan"
            
            # ===== AMBIL HARGA DENGAN FALLBACK =====
            if price_per_slot is None:
                settings = self.data["settings"]
                
                # Prioritaskan price_per_slot
                if "price_per_slot" in settings:
                    price_per_slot = settings["price_per_slot"]
                # Fallback ke price_per_month
                elif "price_per_month" in settings:
                    price_per_slot = settings["price_per_month"]
                    # Simpan ke settings untuk下次
                    self.data["settings"]["price_per_slot"] = price_per_slot
                else:
                    # Default value
                    price_per_slot = 50000
                    self.data["settings"]["price_per_slot"] = price_per_slot
            
            total_price = months * price_per_slot
            
            # ===== CEK BATAS MAKSIMAL SLOT =====
            max_slots = self.data["settings"].get("max_slots_per_user", 10)
            current_slots = len(user.get('slots', []))
            
            if current_slots >= max_slots:
                return False, f"Maksimal slot adalah {max_slots}. Anda sudah memiliki {current_slots} slot."
            
            # ===== HITUNG EXPIRY =====
            if months == 0:  # Lifetime
                expiry_date = "lifetime"
            else:
                expiry_date = (datetime.now() + timedelta(days=months * 30)).isoformat()
            
            # ===== BUAT SLOT BARU =====
            slot_data = {
                "slot_id": str(uuid.uuid4())[:8],
                "slot_number": user.get('next_slot_number', current_slots + 1),
                "expiry_date": expiry_date,
                "max_ips_per_slot": self.data["settings"].get("default_ips_per_slot", 1),
                "used_ips": 0,
                "ips": [],
                "created_at": datetime.now().isoformat(),
                "last_renewed": datetime.now().isoformat(),
                "status": "active",
                "purchase_history": [{
                    "months": months,
                    "price": total_price,
                    "purchased_at": datetime.now().isoformat(),
                    "type": "new_slot"
                }]
            }
            
            # ===== TAMBAH KE USER =====
            if 'slots' not in user:
                user['slots'] = []
            
            user['slots'].append(slot_data)
            user['total_slots'] = len(user['slots'])
            user['next_slot_number'] = user['total_slots'] + 1
            
            # Update total spent
            user['total_spent'] = user.get('total_spent', 0) + total_price
            user['last_payment'] = datetime.now().isoformat()
            
            self.save()
            
            print(f"[ADD SLOT] User {user_id} - Slot #{slot_data['slot_number']} - {months} bulan - Rp{total_price}")
            return True, slot_data
            
        except Exception as e:
            print(f"[ADD SLOT ERROR] {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
    
    def extend_slot(self, user_id, slot_id, months, price_per_slot=None):
        """
        Perpanjang masa aktif slot tertentu
        
        Args:
            user_id: ID user
            slot_id: ID slot yang akan diperpanjang
            months: Jumlah bulan perpanjangan (0 = upgrade ke lifetime)
            
        Returns:
            tuple: (success, new_expiry or error_message)
        """
        try:
            user = self.get_user(user_id)
            if not user:
                return False, "User tidak ditemukan"
            
            # Cari slot
            slot = None
            for s in user.get('slots', []):
                if s.get('slot_id') == slot_id:
                    slot = s
                    break
            
            if not slot:
                return False, "Slot tidak ditemukan"
            
            # ===== AMBIL HARGA DENGAN FALLBACK =====
            if price_per_slot is None:
                settings = self.data["settings"]
                
                if "price_per_slot" in settings:
                    price_per_slot = settings["price_per_slot"]
                elif "price_per_month" in settings:
                    price_per_slot = settings["price_per_month"]
                else:
                    price_per_slot = 10000
            
            total_price = months * price_per_slot
            
            # ===== HITUNG EXPIRY BARU =====
            if slot.get('expiry_date') == "lifetime":
                # Jika sudah lifetime, tetap lifetime
                new_expiry = "lifetime"
            elif months == 0:  # Upgrade ke lifetime
                new_expiry = "lifetime"
            else:
                try:
                    current_expiry = datetime.fromisoformat(slot['expiry_date'])
                    new_expiry = (current_expiry + timedelta(days=months * 30)).isoformat()
                except:
                    # Jika format salah, mulai dari sekarang
                    new_expiry = (datetime.now() + timedelta(days=months * 30)).isoformat()
            
            # ===== UPDATE SLOT =====
            slot['expiry_date'] = new_expiry
            slot['last_renewed'] = datetime.now().isoformat()
            
            # Tambah ke purchase history
            if 'purchase_history' not in slot:
                slot['purchase_history'] = []
            
            slot['purchase_history'].append({
                "months": months,
                "price": total_price,
                "purchased_at": datetime.now().isoformat(),
                "type": "extend"
            })
            
            # Update total spent user
            user['total_spent'] = user.get('total_spent', 0) + total_price
            user['last_payment'] = datetime.now().isoformat()
            
            self.save()
            
            print(f"[EXTEND SLOT] User {user_id} - Slot #{slot['slot_number']} +{months} bulan - Rp{total_price}")
            return True, new_expiry
            
        except Exception as e:
            print(f"[EXTEND SLOT ERROR] {e}")
            return False, str(e)
    
    def get_user_slots(self, user_id):
        """Get semua slot milik user"""
        user = self.get_user(user_id)
        if user:
            return user.get('slots', [])
        return []
    
    def get_active_slots(self, user_id):
        """Get slot yang masih aktif"""
        slots = self.get_user_slots(user_id)
        active_slots = []
        
        for slot in slots:
            if self.is_slot_active(slot):
                active_slots.append(slot)
        
        return active_slots
    
    def get_expired_slots(self, user_id):
        """Get slot yang sudah expired"""
        slots = self.get_user_slots(user_id)
        expired_slots = []
        
        for slot in slots:
            if not self.is_slot_active(slot):
                expired_slots.append(slot)
        
        return expired_slots
    
    def is_slot_active(self, slot):
        """Cek apakah slot masih aktif"""
        if slot.get('status') != 'active':
            return False
        
        if slot.get('expiry_date') == "lifetime":
            return True
        
        try:
            expiry = datetime.fromisoformat(slot['expiry_date'])
            return expiry > datetime.now()
        except:
            return False
    
    def can_add_ip_to_slot(self, user_id, slot_id):
        """Cek apakah bisa tambah IP ke slot"""
        user = self.get_user(user_id)
        if not user:
            return False
        
        for slot in user.get('slots', []):
            if slot.get('slot_id') == slot_id:
                if not self.is_slot_active(slot):
                    return False
                return slot.get('used_ips', 0) < slot.get('max_ips_per_slot', 1)
        
        return False
    
    # ========== MANAJEMEN IP PER SLOT ==========
    
    def add_ip_to_slot(self, user_id, slot_id, ip_address, username):
        """
        Tambah IP ke slot tertentu
        
        Args:
            user_id: ID user
            slot_id: ID slot
            ip_address: Alamat IP
            username: Username untuk IP ini
            
        Returns:
            tuple: (success, message)
        """
        try:
            user = self.get_user(user_id)
            if not user:
                return False, "User tidak ditemukan"
            
            # Cari slot
            slot = None
            for s in user.get('slots', []):
                if s.get('slot_id') == slot_id:
                    slot = s
                    break
            
            if not slot:
                return False, "Slot tidak ditemukan"
            
            # Cek apakah slot masih aktif
            if not self.is_slot_active(slot):
                return False, "Slot sudah expired. Perpanjang dulu ya."
            
            # Cek apakah masih bisa tambah IP
            if slot.get('used_ips', 0) >= slot.get('max_ips_per_slot', 1):
                return False, f"Slot sudah penuh (max {slot.get('max_ips_per_slot', 1)} IP)"
            
            # Cek apakah IP sudah ada di slot ini
            for ip_data in slot.get('ips', []):
                if ip_data.get('ip') == ip_address:
                    return False, "IP sudah terdaftar di slot ini"
            
            # Cek apakah IP sudah ada di database global
            existing_ip = self.get_ip_by_address(ip_address)
            if existing_ip:
                return False, "IP sudah digunakan oleh user lain"
            
            # Buat entry IP
            ip_entry = {
                "id": len(self.data["ips"]) + 1,
                "ip": ip_address,
                "username": username,
                "slot_id": slot_id,
                "owner_id": user_id,
                "added_at": datetime.now().isoformat(),
                "status": "active",
                "last_used": None
            }
            
            # Tambah ke global IP list
            self.data["ips"].append(ip_entry)
            
            # Tambah ke slot
            if 'ips' not in slot:
                slot['ips'] = []
            
            slot['ips'].append({
                "ip": ip_address,
                "username": username,
                "added_at": datetime.now().isoformat()
            })
            
            slot['used_ips'] = len(slot['ips'])
            
            self.save()
            
            print(f"[ADD IP] User {user_id} - Slot #{slot['slot_number']} - {ip_address} ({username})")
            return True, ip_entry
            
        except Exception as e:
            print(f"[ADD IP TO SLOT ERROR] {e}")
            return False, str(e)
    
    def remove_ip_from_slot(self, user_id, slot_id, ip_address):
        """
        Hapus IP dari slot tertentu
        """
        try:
            user = self.get_user(user_id)
            if not user:
                return False, "User tidak ditemukan"
            
            # Cari slot
            slot = None
            for s in user.get('slots', []):
                if s.get('slot_id') == slot_id:
                    slot = s
                    break
            
            if not slot:
                return False, "Slot tidak ditemukan"
            
            # Hapus dari slot
            slot['ips'] = [ip for ip in slot.get('ips', []) if ip.get('ip') != ip_address]
            slot['used_ips'] = len(slot['ips'])
            
            # Hapus dari global IP list
            self.data["ips"] = [ip for ip in self.data["ips"] if ip.get('ip') != ip_address]
            
            self.save()
            
            print(f"[REMOVE IP] User {user_id} - Slot #{slot['slot_number']} - {ip_address}")
            return True, "IP berhasil dihapus"
            
        except Exception as e:
            print(f"[REMOVE IP FROM SLOT ERROR] {e}")
            return False, str(e)
    
    def get_ips_in_slot(self, user_id, slot_id):
        """Get semua IP dalam slot tertentu"""
        user = self.get_user(user_id)
        if not user:
            return []
        
        for slot in user.get('slots', []):
            if slot.get('slot_id') == slot_id:
                return slot.get('ips', [])
        
        return []
    
    # ========== MANAJEMEN IP GLOBAL ==========
    
    def get_ip_by_address(self, ip_address):
        """Get IP berdasarkan alamat"""
        for ip in self.data["ips"]:
            if ip["ip"] == ip_address:
                return ip
        return None
    
    def get_ips_by_owner(self, user_id):
        """Get semua IP milik user (dari semua slot)"""
        user = self.get_user(user_id)
        if not user:
            return []
        
        all_ips = []
        for slot in user.get('slots', []):
            all_ips.extend(slot.get('ips', []))
        
        return all_ips
    
    def get_all_ips(self):
        """Get semua IP terdaftar"""
        return self.data["ips"]
    
    def check_ip_expired(self, ip_address):
        """Cek apakah IP sudah expired (berdasarkan slotnya)"""
        ip = self.get_ip_by_address(ip_address)
        if not ip:
            return True
        
        slot_id = ip.get('slot_id')
        if not slot_id:
            return True
        
        # Cari slot pemilik IP
        for user in self.data["users"]:
            for slot in user.get('slots', []):
                if slot.get('slot_id') == slot_id:
                    return not self.is_slot_active(slot)
        
        return True
    
    # ========== GETTER METHODS ==========
    
    def get_settings(self):
        """Get settings rental"""
        return self.data["settings"]
    
    def update_settings(self, **kwargs):
        """Update settings rental"""
        for key, value in kwargs.items():
            if key in self.data["settings"]:
                self.data["settings"][key] = value
        self.save()
        return True
    
    def get_price_per_slot(self):
        """Get harga per slot (dengan fallback)"""
        settings = self.data["settings"]
        
        if "price_per_slot" in settings:
            return settings["price_per_slot"]
        elif "price_per_month" in settings:
            # Migrasi otomatis
            self.data["settings"]["price_per_slot"] = settings["price_per_month"]
            self.save()
            return settings["price_per_month"]
        else:
            # Default
            return 50000
    
    def get_price_per_month(self):
        """Get harga per bulan (legacy)"""
        return self.get_price_per_slot()  # Gunakan harga per slot
    
    def calculate_price(self, months):
        """Hitung harga berdasarkan jumlah bulan (untuk 1 slot)"""
        price_per_slot = self.get_price_per_slot()
        return months * price_per_slot
    
    # ========== SAVE ==========
    
    def save(self):
        """Save data rental ke file JSON"""
        try:
            with open(RENTAL_DB, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Gagal save database: {e}")

# Inisialisasi ulang
rental_db = RentalDatabase()
                                        

# ==================== GITHUB MANAGER - VERSI LENGKAP DENGAN DEBUGGING ====================

class GitHubManager:
    """
    Manager untuk sinkronisasi dengan GitHub
    - Versi lengkap dengan semua fungsi yang dibutuhkan
    - Dilengkapi logging dan debugging
    - Auto-create file jika belum ada
    - Verifikasi setelah sync
    """
    
    def __init__(self):
        """Inisialisasi GitHub Manager dengan settings dari database rental"""
        self.load_settings()
        self.setup_logging()
        
    def load_settings(self):
        """Load settings dari database rental"""
        try:
            settings = rental_db.get_settings()
            self.token = settings.get("github_token", "")
            self.username = settings.get("github_username", "")
            self.repo = settings.get("github_repo", "")
            self.file_path = settings.get("github_file_path", "ip")
            self.base_url = f"https://api.github.com/repos/{self.username}/{self.repo}"
            self.headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "VPN-Store-Bot"
            }
            print(f"[GITHUB] Loaded settings for {self.username}/{self.repo}")
        except Exception as e:
            print(f"[GITHUB] Error loading settings: {e}")
            self.token = ""
            self.username = ""
            self.repo = ""
            self.file_path = "ip"
            self.base_url = ""
            self.headers = {}
    
    def setup_logging(self):
        """Setup logging untuk GitHub"""
        self.logger = logging.getLogger('github')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - GITHUB - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def is_configured(self) -> bool:
        """Cek apakah GitHub sudah dikonfigurasi dengan lengkap"""
        is_ok = all([
            self.token,
            self.username,
            self.repo,
            self.file_path,
            self.token != "",
            self.username != "",
            self.repo != ""
        ])
        
        if not is_ok:
            missing = []
            if not self.token: missing.append("token")
            if not self.username: missing.append("username")
            if not self.repo: missing.append("repo")
            if not self.file_path: missing.append("file_path")
            print(f"[GITHUB] Konfigurasi tidak lengkap. Missing: {', '.join(missing)}")
        
        return is_ok
    
    def get_file_sha(self, file_path: str = None) -> Optional[str]:
        """
        Mendapatkan SHA file dari GitHub
        SHA diperlukan untuk mengupdate file yang sudah ada
        
        Args:
            file_path: Path file di GitHub (optional)
            
        Returns:
            str: SHA file jika ditemukan, None jika tidak ada
        """
        if file_path is None:
            file_path = self.file_path
        
        if not self.is_configured():
            return None
        
        url = f"{self.base_url}/contents/{file_path}"
        
        try:
            self.logger.info(f"Getting SHA for {file_path}")
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                sha = response.json()["sha"]
                self.logger.info(f"SHA ditemukan: {sha[:8]}...")
                return sha
            elif response.status_code == 404:
                self.logger.info(f"File {file_path} belum ada di GitHub")
                return None
            else:
                self.logger.warning(f"Gagal get SHA. Status: {response.status_code}")
                return None
                
        except requests.exceptions.Timeout:
            self.logger.error("Timeout saat get SHA")
            return None
        except requests.exceptions.ConnectionError:
            self.logger.error("Connection error saat get SHA")
            return None
        except Exception as e:
            self.logger.error(f"Error get SHA: {e}")
            return None
    
    def update_file(self, content: str, commit_message: str, file_path: str = None) -> bool:
        """
        Update atau create file di GitHub
        
        Args:
            content: Isi file (string)
            commit_message: Pesan commit
            file_path: Path file di GitHub (optional)
            
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        if file_path is None:
            file_path = self.file_path
        
        if not self.is_configured():
            self.logger.error("GitHub belum dikonfigurasi")
            return False
        
        # Dapatkan SHA file yang ada (jika ada)
        sha = self.get_file_sha(file_path)
        
        # Encode content ke base64
        try:
            encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Gagal encode content: {e}")
            return False
        
        # Siapkan data untuk API
        data = {
            "message": commit_message,
            "content": encoded_content,
        }
        
        # Tambahkan SHA jika file sudah ada (untuk update)
        if sha:
            data["sha"] = sha
            action = "update"
        else:
            action = "create"
        
        url = f"{self.base_url}/contents/{file_path}"
        
        try:
            self.logger.info(f"[{action.upper()}] Mengirim ke {url}")
            self.logger.info(f"Commit: {commit_message}")
            self.logger.info(f"Content length: {len(content)} bytes")
            
            response = requests.put(url, headers=self.headers, json=data, timeout=30)
            
            if response.status_code in [200, 201]:
                self.logger.info(f"✅ {action.title()} berhasil! Status: {response.status_code}")
                
                # Log detail response
                resp_data = response.json()
                if 'content' in resp_data:
                    new_sha = resp_data['content']['sha'][:8]
                    self.logger.info(f"New SHA: {new_sha}...")
                
                return True
                
            elif response.status_code == 409:
                self.logger.error("Conflict - file mungkin sudah diubah")
                return False
            elif response.status_code == 403:
                self.logger.error("Forbidden - cek token permissions")
                return False
            elif response.status_code == 404:
                self.logger.error("Not Found - cek repo name")
                return False
            else:
                self.logger.error(f"Gagal! Status: {response.status_code}")
                self.logger.error(f"Response: {response.text[:200]}")
                return False
                
        except requests.exceptions.Timeout:
            self.logger.error("Timeout - koneksi terlalu lambat")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.error("Connection error - tidak bisa terhubung ke GitHub")
            return False
        except Exception as e:
            self.logger.error(f"Error: {e}")
            return False
    
    def generate_ip_file_content(self) -> str:
        """
        Generate konten file IP berdasarkan database rental
        Format: ### username expiry_date ip_address
        
        Returns:
            str: Konten file yang siap diupload
        """
        lines = []
        
        try:
            # Ambil semua IP dari database rental
            all_ips = rental_db.get_all_ips()
            
            self.logger.info(f"Generating content untuk {len(all_ips)} IP")
            
            if not all_ips:
                self.logger.info("Tidak ada IP dalam database")
                return "# No IP addresses registered yet\n"
            
            # Urutkan IP berdasarkan username
            sorted_ips = sorted(all_ips, key=lambda x: x.get('username', ''))
            
            for ip_data in sorted_ips:
                username = ip_data.get('username', 'unknown')
                ip_address = ip_data.get('ip', '0.0.0.0')
                
                # Skip jika data tidak lengkap
                if not username or not ip_address or ip_address == '0.0.0.0':
                    self.logger.warning(f"IP data tidak lengkap: {ip_data}")
                    continue
                
                # Cari slot pemilik IP ini
                slot_id = ip_data.get('slot_id')
                expiry_date = "lifetime"
                owner_name = "unknown"
                
                # Cari expiry date dari slot
                if slot_id:
                    for user in rental_db.data.get("users", []):
                        for slot in user.get('slots', []):
                            if slot.get('slot_id') == slot_id:
                                expiry_date = slot.get('expiry_date', 'lifetime')
                                owner_name = user.get('username', 'unknown')
                                break
                
                # Format sesuai dengan yang diinginkan
                if expiry_date == "lifetime":
                    lines.append(f"### {username} lifetime {ip_address}")
                else:
                    try:
                        # Parse berbagai format tanggal
                        expiry_str = str(expiry_date)
                        
                        # Coba parse dengan berbagai format
                        parsed = False
                        for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d', '%d-%m-%Y']:
                            try:
                                expiry = datetime.strptime(expiry_str[:10], fmt[:10])
                                expiry_formatted = expiry.strftime("%Y-%m-%d")
                                lines.append(f"### {username} {expiry_formatted} {ip_address}")
                                parsed = True
                                break
                            except:
                                continue
                        
                        if not parsed:
                            # Fallback: ambil 10 karakter pertama
                            lines.append(f"### {username} {expiry_str[:10]} {ip_address}")
                            
                    except Exception as e:
                        self.logger.warning(f"Error parsing date {expiry_date}: {e}")
                        lines.append(f"### {username} {expiry_date} {ip_address}")
            
            # Gabungkan semua line
            content = "\n".join(lines)
            
            # Log preview
            self.logger.info(f"Generated {len(lines)} lines")
            self.logger.debug(f"Preview:\n{content[:200]}...")
            
            return content
            
        except Exception as e:
            self.logger.error(f"Error generating content: {e}")
            import traceback
            traceback.print_exc()
            return "# Error generating IP list\n"
    
    def sync_to_github(self) -> Tuple[bool, str]:
        """
        Sync semua IP ke GitHub dengan verifikasi
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        start_time = time_module.time()
        
        # Cek konfigurasi
        if not self.is_configured():
            return False, "❌ GitHub belum dikonfigurasi lengkap"
        
        self.logger.info("=" * 50)
        self.logger.info("MEMULAI SYNC KE GITHUB")
        self.logger.info("=" * 50)
        
        try:
            # Step 1: Generate konten
            self.logger.info("Step 1/4: Generating content...")
            content = self.generate_ip_file_content()
            
            if not content or content == "# No IP addresses registered yet\n":
                self.logger.warning("Konten kosong, tapi akan tetap diupload")
            
            # Step 2: Buat commit message dengan timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            commit_message = f"Update IP database - {timestamp}"
            
            # Step 3: Update file di GitHub
            self.logger.info("Step 2/4: Updating file on GitHub...")
            success = self.update_file(content, commit_message)
            
            if not success:
                self.logger.error("Step 3/4: Gagal update file")
                elapsed = time_module.time() - start_time
                return False, f"❌ Gagal sync ke GitHub ({elapsed:.1f}s)"
            
            # Step 4: Verifikasi dengan membaca kembali file
            self.logger.info("Step 3/4: Verifying...")
            verify_sha = self.get_file_sha()
            
            elapsed = time_module.time() - start_time
            
            if verify_sha:
                self.logger.info(f"Step 4/4: ✅ Verifikasi berhasil - SHA: {verify_sha[:8]}")
                self.logger.info(f"Sync completed in {elapsed:.2f} seconds")
                
                # Hitung statistik
                ip_count = len(content.splitlines())
                if content.startswith("# No IP"):
                    ip_count = 0
                
                return True, f"✅ Berhasil sync ke GitHub\n📊 {ip_count} IP tersinkronasi\n⏱️ {elapsed:.1f}s"
            else:
                self.logger.warning("Sync sukses tapi tidak bisa verifikasi")
                return True, f"⚠️ Sync berhasil tapi tidak bisa verifikasi\n⏱️ {elapsed:.1f}s"
            
        except Exception as e:
            self.logger.error(f"Sync error: {e}")
            import traceback
            traceback.print_exc()
            elapsed = time_module.time() - start_time
            return False, f"❌ Error: {str(e)[:100]}\n⏱️ {elapsed:.1f}s"
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test koneksi ke GitHub
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        if not self.is_configured():
            return False, "❌ GitHub belum dikonfigurasi"
        
        try:
            # Test get user info
            url = f"https://api.github.com/user"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                
                # Test get repo
                repo_url = self.base_url
                repo_response = requests.get(repo_url, headers=self.headers, timeout=10)
                
                if repo_response.status_code == 200:
                    repo_data = repo_response.json()
                    
                    # Test get file (optional)
                    file_sha = self.get_file_sha()
                    
                    return True, (
                        f"✅ Koneksi GitHub berhasil!\n\n"
                        f"👤 User: {user_data.get('login')}\n"
                        f"📁 Repo: {repo_data.get('name')}\n"
                        f"🌐 Private: {'Ya' if repo_data.get('private') else 'Tidak'}\n"
                        f"📄 File: {self.file_path}\n"
                        f"🔑 SHA: {file_sha[:8] if file_sha else 'Belum ada'}"
                    )
                else:
                    return False, f"❌ Repo tidak ditemukan atau tidak bisa diakses"
            
            elif response.status_code == 401:
                return False, "❌ Token tidak valid atau expired"
            else:
                return False, f"❌ Error {response.status_code}: {response.text[:100]}"
                
        except Exception as e:
            return False, f"❌ Error: {str(e)}"
    
    def get_file_content(self, file_path: str = None) -> Optional[str]:
        """
        Mendapatkan isi file dari GitHub
        
        Args:
            file_path: Path file di GitHub
            
        Returns:
            str: Isi file, None jika gagal
        """
        if file_path is None:
            file_path = self.file_path
        
        if not self.is_configured():
            return None
        
        url = f"{self.base_url}/contents/{file_path}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                content = base64.b64decode(data['content']).decode('utf-8')
                return content
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error get file content: {e}")
            return None
    
    def compare_with_github(self) -> Tuple[bool, str]:
        """
        Membandingkan database lokal dengan file di GitHub
        
        Returns:
            Tuple[bool, str]: (is_same, difference)
        """
        local_content = self.generate_ip_file_content()
        github_content = self.get_file_content()
        
        if github_content is None:
            return False, "File GitHub tidak ditemukan"
        
        if local_content == github_content:
            return True, "✅ Database sinkron dengan GitHub"
        else:
            # Hitung perbedaan
            local_lines = set(local_content.splitlines())
            github_lines = set(github_content.splitlines())
            
            only_local = local_lines - github_lines
            only_github = github_lines - local_lines
            
            diff = []
            if only_local:
                diff.append(f"📤 {len(only_local)} hanya di lokal")
            if only_github:
                diff.append(f"📥 {len(only_github)} hanya di GitHub")
            
            return False, f"⚠️ Database berbeda:\n" + "\n".join(diff)
    
    def force_sync(self) -> Tuple[bool, str]:
        """
        Force sync dengan mengabaikan konflik
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        self.logger.warning("FORCE SYNC - Mengabaikan konflik")
        
        # Generate konten baru
        content = self.generate_ip_file_content()
        
        # Buat commit message
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_message = f"FORCE UPDATE IP database - {timestamp}"
        
        # Force update dengan mengambil SHA terbaru
        sha = self.get_file_sha()
        
        if not sha:
            return self.sync_to_github()
        
        # Encode content
        encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        # Siapkan data
        data = {
            "message": commit_message,
            "content": encoded_content,
            "sha": sha
        }
        
        url = f"{self.base_url}/contents/{self.file_path}"
        
        try:
            response = requests.put(url, headers=self.headers, json=data, timeout=30)
            
            if response.status_code in [200, 201]:
                return True, "✅ Force sync berhasil"
            else:
                return False, f"❌ Force sync gagal: {response.status_code}"
                
        except Exception as e:
            return False, f"❌ Error: {str(e)}"


# Inisialisasi ulang GitHubManager
try:
    github_mgr = GitHubManager()
    print("[INIT] GitHub Manager initialized")
    if github_mgr.is_configured():
        print(f"[INIT] GitHub configured for {github_mgr.username}/{github_mgr.repo}")
    else:
        print("[INIT] GitHub not configured - please configure in admin panel")
except Exception as e:
    print(f"[INIT] Error initializing GitHub: {e}")
    github_mgr = GitHubManager()  # Fallback

# ==================== GENERATE INSTALL SCRIPT ====================

def generate_install_script(ip_address, username, github_username=None, github_repo=None):
    """Generate script install untuk IP baru"""
    if github_username is None:
        github_username = rental_db.data["settings"]["github_username"]
    if github_repo is None:
        github_repo = rental_db.data["settings"]["github_repo"]
    
    script = f"""#!/bin/bash
# Auto Install Script untuk IP: {ip_address}
# Username: {username}
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

echo "=========================================="
echo "  AUTO INSTALL SCRIPT - VPN STORE"
echo "=========================================="
echo "IP Address: {ip_address}"
echo "Username: {username}"
echo ""

# Update system
echo "[1] Updating system packages..."
apt-get update && apt-get upgrade -y

# Install dependencies
echo "[2] Installing dependencies..."
apt-get install -y wget curl nano

# Download install script
echo "[3] Downloading installation script..."
wget https://raw.githubusercontent.com/{github_username}/{github_repo}/main/install2.sh -O install2.sh

# Make it executable
chmod +x install2.sh

echo ""
echo "=========================================="
echo "  INSTALLATION READY!"
echo "=========================================="
echo "Untuk menjalankan script, ketik:"
echo "./install2.sh"
echo ""
echo "Atau langsung jalankan dengan:"
echo "apt-get update && apt-get upgrade -y && apt install wget -y && wget https://raw.githubusercontent.com/{github_username}/{github_repo}/main/install2.sh && chmod +x install2.sh && ./install2.sh"
echo ""
echo "Setelah install selesai, konfigurasi VPN dengan:"
echo "IP Server: {ip_address}"
echo "Username: {username}"
echo "=========================================="
"""
    return script

# ==================== FITUR RENTAL UNTUK USER ====================

async def user_rental_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses sewa script"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    if user:
        # User sudah terdaftar
        await user_rental_menu(query, context)
    else:
        # User belum terdaftar
        text = f"""
{generate_header('SEWA AUTO SCRIPT')}

{generate_separator(29)}
ℹ️ *ANDA BELUM TERDAFTAR*
{generate_separator(29)}
Untuk menggunakan fitur sewa script, Anda perlu melakukan pembayaran terlebih dahulu.

💰 *Harga:* {format_money(rental_db.get_price_per_month())} / bulan
📋 *Fitur yang didapat:*
├ Akses ke script installer
├ Bisa menambah IP sendiri
├ Manajemen IP via bot
└ IP mengikuti masa aktif

{generate_separator(29)}
Pilih durasi sewa:
"""
        
        keyboard = [
            [InlineKeyboardButton("1 Bulan", callback_data="rental_buy_1")],
            [InlineKeyboardButton("3 Bulan", callback_data="rental_buy_3")],
            [InlineKeyboardButton("6 Bulan", callback_data="rental_buy_6")],
            [InlineKeyboardButton("12 Bulan", callback_data="rental_buy_12")],
            [InlineKeyboardButton("Lifetime", callback_data="rental_buy_lifetime")],
            [InlineKeyboardButton("🔙 Menu Utama", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        
        return "RENTAL_BUY"

async def user_rental_menu(query, context):
    """Menu utama rental untuk user - VERSI SLOT"""
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    if not user:
        await query.edit_message_text("❌ User tidak ditemukan.")
        return
    
    # Hitung statistik slot
    slots = user.get('slots', [])
    active_slots = rental_db.get_active_slots(user_id)
    expired_slots = rental_db.get_expired_slots(user_id)
    
    total_ips = 0
    for slot in slots:
        total_ips += len(slot.get('ips', []))
    
    text = f"""
{generate_header('RENTAL AUTO SCRIPT')}

{generate_separator(29)}
👤 *Informasi Akun:*
├ Username: {user['username']}
├ Total Slot: {len(slots)} / {rental_db.data['settings'].get('max_slots_per_user', 1000)}
├ Slot Aktif: {len(active_slots)}
├ Slot Expired: {len(expired_slots)}
└ Total IP: {total_ips}

{generate_separator(29)}
📋 *Menu:*
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Lihat Semua Slot", callback_data="rental_list_slots")],
        [InlineKeyboardButton("➕ Beli Slot Baru", callback_data="rental_buy_slot")],
        [InlineKeyboardButton("🔄 Perpanjang Slot", callback_data="rental_extend_slot_select")],
        [InlineKeyboardButton("ℹ️ Cara Install", callback_data="rental_guide")],
        [InlineKeyboardButton("🔙 Menu Utama", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def user_rental_list_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan semua slot user"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    if not user:
        await query.edit_message_text("❌ User tidak ditemukan.")
        return
    
    slots = user.get('slots', [])
    
    if not slots:
        text = f"""
{generate_header('DAFTAR SLOT')}

{generate_separator(29)}
📭 *Belum Ada Slot*
{generate_separator(29)}
Anda belum memiliki slot rental.
Silakan beli slot terlebih dahulu.
{generate_separator(29)}
"""
        keyboard = [
            [InlineKeyboardButton("➕ Beli Slot Baru", callback_data="rental_buy_slot")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return
    
    text = f"""
{generate_header('DAFTAR SLOT RENTAL')}

{generate_separator(29)}
📋 *Total Slot: {len(slots)}*
{generate_separator(29)}
"""
    
    keyboard = []
    for i, slot in enumerate(slots, 1):
        # Cek status slot
        if rental_db.is_slot_active(slot):
            if slot.get('expiry_date') == "lifetime":
                status = "⭐ LIFETIME"
                status_emoji = "⭐"
                expiry_text = "Tidak terbatas"
            else:
                try:
                    expiry = datetime.fromisoformat(slot['expiry_date'])
                    days_left = (expiry - datetime.now()).days
                    status = f"🟢 {days_left} hari lagi"
                    status_emoji = "🟢"
                    expiry_text = expiry.strftime('%d %b %Y')
                except:
                    status = "🟢 Aktif"
                    status_emoji = "🟢"
                    expiry_text = slot.get('expiry_date', 'N/A')
        else:
            status = "🔴 EXPIRED"
            status_emoji = "🔴"
            expiry_text = slot.get('expiry_date', 'N/A')
        
        ip_count = len(slot.get('ips', []))
        
        text += f"""
{status_emoji} *Slot #{slot.get('slot_number', i)}*
├ Slot ID: `{slot.get('slot_id', 'N/A')[:8]}...`
├ Status: {status}
├ Expiry: {expiry_text}
├ IP: {ip_count}/{slot.get('max_ips_per_slot', 1)}
└ Dibeli: {slot.get('created_at', '')[:10]}
{generate_separator(20)}
"""
        
        # Tombol untuk setiap slot
        keyboard.append([
            InlineKeyboardButton(
                f"📋 Kelola Slot #{slot.get('slot_number', i)}",
                callback_data=f"rental_slot_detail_{slot.get('slot_id')}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("➕ Beli Slot Baru", callback_data="rental_buy_slot")])
    keyboard.append([InlineKeyboardButton("🔙 Menu Rental", callback_data="user_rental")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
                    
async def user_rental_slot_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detail slot tertentu"""
    query = update.callback_query
    await query.answer()
    
    slot_id = query.data.replace("rental_slot_detail_", "")
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    if not user:
        await query.edit_message_text("❌ User tidak ditemukan.")
        return
    
    # Cari slot
    slot = None
    for s in user.get('slots', []):
        if s.get('slot_id') == slot_id:
            slot = s
            break
    
    if not slot:
        await query.edit_message_text("❌ Slot tidak ditemukan.")
        return
    
    # Hitung sisa hari
    if slot.get('expiry_date') == "lifetime":
        days_left = "∞ (Lifetime)"
        expiry_status = "⭐ Lifetime"
        progress_bar = "████████████████████ [LIFETIME]"
    else:
        try:
            expiry = datetime.fromisoformat(slot['expiry_date'])
            now = datetime.now()
            days_left = (expiry - now).days
            
            if days_left < 0:
                expiry_status = "🔴 EXPIRED"
                progress_bar = "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ [EXPIRED]"
            else:
                # Hitung progress (asumsi 30 hari per bulan)
                total_days = 30 * 1  # Default 1 bulan
                days_passed = total_days - days_left
                bar_length = 20
                filled = max(0, min(int((days_passed / total_days) * bar_length), bar_length))
                bar = "█" * filled + "▒" * (bar_length - filled)
                progress_bar = f"{bar} [{days_left} hari]"
                expiry_status = f"🟢 {days_left} hari lagi"
        except:
            days_left = "N/A"
            expiry_status = "❓ Unknown"
            progress_bar = "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒"
    
    ips = slot.get('ips', [])
    
    text = f"""
{generate_header(f'DETAIL SLOT #{slot.get("slot_number", "?")}')}

{generate_separator(29)}
📋 *Informasi Slot:*
├ Slot ID: `{slot.get('slot_id', 'N/A')}`
├ Status: {expiry_status}
├ Expiry: {slot.get('expiry_date', 'N/A')}
├ Max IP: {slot.get('max_ips_per_slot', 1)} IP
├ Used IP: {len(ips)} IP
└ {progress_bar}

{generate_separator(29)}
🌐 *Daftar IP di Slot Ini:*
"""
    
    if ips:
        for i, ip_data in enumerate(ips, 1):
            text += f"{i}. `{ip_data['ip']}` ({ip_data['username']})\n"
    else:
        text += "Belum ada IP terdaftar\n"
    
    text += generate_separator(29)
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Tambah IP", callback_data=f"rental_add_ip_slot_{slot_id}"),
            InlineKeyboardButton("🗑️ Hapus IP", callback_data=f"rental_remove_ip_slot_{slot_id}")
        ],
        [
            InlineKeyboardButton("🔄 Perpanjang Slot Ini", callback_data=f"rental_extend_slot_{slot_id}"),
            InlineKeyboardButton("💰 Upgrade IP Limit", callback_data=f"rental_upgrade_slot_{slot_id}")
        ],
        [InlineKeyboardButton("🔙 Kembali ke Daftar Slot", callback_data="rental_list_slots")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

                
async def user_rental_buy_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Beli slot baru"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    price_per_slot = rental_db.get_price_per_slot()
    max_slots = rental_db.data['settings'].get('max_slots_per_user', 10)
    
    current_slots = len(user.get('slots', [])) if user else 0
    
    text = f"""
{generate_header('BELI SLOT BARU')}

{generate_separator(29)}
💰 *Harga: {format_money(price_per_slot)} / bulan per slot*
📊 *Slot saat ini: {current_slots} / {max_slots}*

{generate_separator(29)}
⚠️ *Informasi:*
• Setiap slot memiliki masa aktif sendiri
• Bisa tambah IP di setiap slot
• IP mengikuti masa aktif slot-nya
• Slot bisa diperpanjang secara terpisah

{generate_separator(29)}
Pilih durasi untuk slot baru:
"""
    
    keyboard = [
        [InlineKeyboardButton("1 Bulan", callback_data="rental_buy_slot_1")],
        [InlineKeyboardButton("3 Bulan", callback_data="rental_buy_slot_3")],
        [InlineKeyboardButton("6 Bulan", callback_data="rental_buy_slot_6")],
        [InlineKeyboardButton("12 Bulan", callback_data="rental_buy_slot_12")],
        [InlineKeyboardButton("Lifetime", callback_data="rental_buy_slot_lifetime")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return "RENTAL_BUY_SLOT"
                
async def user_rental_buy_slot_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi beli slot baru"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    if data == "rental_buy_slot_1":
        months = 1
    elif data == "rental_buy_slot_3":
        months = 3
    elif data == "rental_buy_slot_6":
        months = 6
    elif data == "rental_buy_slot_12":
        months = 12
    elif data == "rental_buy_slot_lifetime":
        months = 0  # lifetime
    else:
        await query.edit_message_text("❌ Pilihan tidak valid.")
        return ConversationHandler.END
    
    price_per_slot = rental_db.get_price_per_slot()
    total_price = rental_db.calculate_price(months) if months > 0 else price_per_slot * 12
    
    text = f"""
{generate_header('KONFIRMASI PEMBELIAN SLOT')}

{generate_separator(29)}
📋 *Detail Pembelian Slot:*
├ Paket: {'Lifetime' if months == 0 else f'{months} Bulan'}
├ Harga per Slot: {format_money(price_per_slot)}/bulan
├ Total Harga: {format_money(total_price)}
└ Metode: Potong saldo

{generate_separator(29)}
💰 *Saldo Anda:* {format_money(BalanceUpdateHandler.get_user_balance(user_id))}
💰 *Sisa Saldo:* {format_money(BalanceUpdateHandler.get_user_balance(user_id) - total_price)}
{generate_separator(29)}
"""
    
    if BalanceUpdateHandler.validate_user_balance(user_id, total_price):
        text += "✅ *Saldo cukup!*"
        keyboard = [
            [
                InlineKeyboardButton("✅ KONFIRMASI BELI", callback_data=f"rental_confirm_slot_{months}"),
                InlineKeyboardButton("❌ BATALKAN", callback_data="rental_buy_slot")
            ]
        ]
    else:
        text += "❌ *Saldo tidak cukup!*"
        keyboard = [
            [InlineKeyboardButton("💰 Top Up", callback_data="user_topup")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="rental_buy_slot")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return "RENTAL_CONFIRM_SLOT"

async def user_rental_execute_buy_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eksekusi pembelian slot baru"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    months = int(data.replace("rental_confirm_slot_", ""))
    price_per_slot = rental_db.get_price_per_slot()
    total_price = rental_db.calculate_price(months) if months > 0 else price_per_slot * 12
    
    # Cek saldo
    if not BalanceUpdateHandler.validate_user_balance(user_id, total_price):
        await query.edit_message_text("❌ Saldo tidak cukup.")
        return ConversationHandler.END
    
    # Proses pembayaran
    success = BalanceUpdateHandler.update_vpn_purchase(
        user_id=user_id,
        amount=total_price,
        description=f"Pembelian Slot Rental - {months if months > 0 else 'Lifetime'} bulan",
        metadata={
            "slot_purchase": True,
            "slot_months": months,
            "slot_price": total_price
        }
    )
    
    if not success:
        await query.edit_message_text("❌ Gagal memproses pembayaran.")
        return ConversationHandler.END
    
    # Cek apakah user sudah ada
    user = rental_db.get_user(user_id)
    
    if not user:
        # User baru, buat dulu
        rental_db.add_user(user_id, username, 0)  # 0 bulan karena slot akan ditambah sendiri
        user = rental_db.get_user(user_id)
    
    # Tambah slot baru
    slot_success, slot_data = rental_db.add_slot(user_id, months)
    
    if not slot_success:
        await query.edit_message_text(f"❌ Gagal menambah slot: {slot_data}")
        return ConversationHandler.END
    
    text = f"""
{generate_header('PEMBELIAN SLOT BERHASIL')}

{generate_separator(29)}
✅ *Slot Baru Berhasil Ditambahkan!*
{generate_separator(29)}
📋 *Detail Slot:*
├ Slot #{slot_data.get('slot_number')}
├ Durasi: {'Lifetime' if months == 0 else f'{months} Bulan'}
├ Harga: {format_money(total_price)}
├ Sisa Saldo: {format_money(BalanceUpdateHandler.get_user_balance(user_id))}
└ Expiry: {slot_data.get('expiry_date')}

{generate_separator(29)}
🎉 *Anda sekarang bisa:*
├ Menambah IP ke slot ini
├ Mengelola IP per slot
├ Perpanjang slot secara terpisah
└ Setiap slot punya masa aktif sendiri

{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Tambah IP ke Slot Ini", callback_data=f"rental_add_ip_slot_{slot_data['slot_id']}")],
        [InlineKeyboardButton("📋 Lihat Semua Slot", callback_data="rental_list_slots")],
        [InlineKeyboardButton("🏠 Menu Rental", callback_data="user_rental")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def user_rental_extend_slot_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih slot yang akan diperpanjang"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    if not user:
        await query.edit_message_text("❌ User tidak ditemukan.")
        return
    
    active_slots = rental_db.get_active_slots(user_id)
    
    if not active_slots:
        text = f"""
{generate_header('PERPANJANG SLOT')}

{generate_separator(29)}
📭 *Tidak Ada Slot Aktif*
{generate_separator(29)}
Anda tidak memiliki slot aktif untuk diperpanjang.
Silakan beli slot baru terlebih dahulu.
{generate_separator(29)}
"""
        keyboard = [
            [InlineKeyboardButton("➕ Beli Slot Baru", callback_data="rental_buy_slot")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return
    
    text = f"""
{generate_header('PERPANJANG SLOT')}

{generate_separator(29)}
📋 *Pilih Slot yang Akan Diperpanjang:*
{generate_separator(29)}
"""
    
    keyboard = []
    for slot in active_slots:
        if slot.get('expiry_date') == "lifetime":
            expiry_text = "LIFETIME"
        else:
            try:
                expiry = datetime.fromisoformat(slot['expiry_date'])
                days_left = (expiry - datetime.now()).days
                expiry_text = f"{days_left} hari lagi"
            except:
                expiry_text = slot.get('expiry_date', 'N/A')[:10]
        
        button_text = f"🔄 Slot #{slot.get('slot_number')} - {expiry_text}"
        keyboard.append([
            InlineKeyboardButton(
                button_text,
                callback_data=f"rental_extend_slot_{slot['slot_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def user_rental_extend_slot_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih durasi perpanjangan untuk slot tertentu"""
    query = update.callback_query
    await query.answer()
    
    slot_id = query.data.replace("rental_extend_slot_", "")
    context.user_data["extend_slot_id"] = slot_id
    
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    # Cari slot
    slot = None
    for s in user.get('slots', []):
        if s.get('slot_id') == slot_id:
            slot = s
            break
    
    if not slot:
        await query.edit_message_text("❌ Slot tidak ditemukan.")
        return
    
    text = f"""
{generate_header('PERPANJANG SLOT')}

{generate_separator(29)}
📋 *Slot #{slot.get('slot_number')}*
├ Expiry Saat Ini: {slot.get('expiry_date')}
├ IP Terdaftar: {len(slot.get('ips', []))} IP
└ Max IP: {slot.get('max_ips_per_slot', 1)} IP

{generate_separator(29)}
💰 *Harga per Bulan:* {format_money(rental_db.get_price_per_slot())}

Pilih durasi perpanjangan:
"""
    
    keyboard = [
        [InlineKeyboardButton("1 Bulan", callback_data="rental_extend_slot_1")],
        [InlineKeyboardButton("3 Bulan", callback_data="rental_extend_slot_3")],
        [InlineKeyboardButton("6 Bulan", callback_data="rental_extend_slot_6")],
        [InlineKeyboardButton("12 Bulan", callback_data="rental_extend_slot_12")],
        [InlineKeyboardButton("Upgrade ke Lifetime", callback_data="rental_extend_slot_lifetime")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="rental_extend_slot_select")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return "RENTAL_EXTEND_SLOT_DURATION"

async def user_rental_extend_slot_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi perpanjangan slot"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    slot_id = context.user_data.get("extend_slot_id")
    
    if data == "rental_extend_slot_1":
        months = 1
    elif data == "rental_extend_slot_3":
        months = 3
    elif data == "rental_extend_slot_6":
        months = 6
    elif data == "rental_extend_slot_12":
        months = 12
    elif data == "rental_extend_slot_lifetime":
        months = 0
    else:
        await query.edit_message_text("❌ Pilihan tidak valid.")
        return ConversationHandler.END
    
    context.user_data["extend_months"] = months
    
    user_id = query.from_user.id
    price_per_slot = rental_db.get_price_per_slot()
    total_price = rental_db.calculate_price(months) if months > 0 else price_per_slot * 12
    
    text = f"""
{generate_header('KONFIRMASI PERPANJANGAN SLOT')}

{generate_separator(29)}
📋 *Detail Perpanjangan:*
├ Slot ID: `{slot_id[:8]}...`
├ Durasi: {'Lifetime' if months == 0 else f'{months} Bulan'}
├ Harga: {format_money(total_price)}
└ Metode: Potong saldo

{generate_separator(29)}
💰 *Saldo Anda:* {format_money(BalanceUpdateHandler.get_user_balance(user_id))}
💰 *Sisa Saldo:* {format_money(BalanceUpdateHandler.get_user_balance(user_id) - total_price)}
{generate_separator(29)}
"""
    
    if BalanceUpdateHandler.validate_user_balance(user_id, total_price):
        text += "✅ *Saldo cukup!*"
        keyboard = [
            [
                InlineKeyboardButton("✅ KONFIRMASI PERPANJANG", callback_data=f"rental_confirm_extend_slot_{months}"),
                InlineKeyboardButton("❌ BATALKAN", callback_data=f"rental_extend_slot_{slot_id}")
            ]
        ]
    else:
        text += "❌ *Saldo tidak cukup!*"
        keyboard = [
            [InlineKeyboardButton("💰 Top Up", callback_data="user_topup")],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"rental_extend_slot_{slot_id}")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return "RENTAL_EXTEND_SLOT_CONFIRM"

async def user_rental_execute_extend_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eksekusi perpanjangan slot"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    slot_id = context.user_data.get("extend_slot_id")
    months = context.user_data.get("extend_months")
    
    user_id = query.from_user.id
    price_per_slot = rental_db.get_price_per_slot()
    total_price = rental_db.calculate_price(months) if months > 0 else price_per_slot * 12
    
    # Cek saldo
    if not BalanceUpdateHandler.validate_user_balance(user_id, total_price):
        await query.edit_message_text("❌ Saldo tidak cukup.")
        return ConversationHandler.END
    
    # Proses pembayaran
    success = BalanceUpdateHandler.update_vpn_purchase(
        user_id=user_id,
        amount=total_price,
        description=f"Perpanjangan Slot Rental - {months if months > 0 else 'Lifetime'} bulan",
        metadata={
            "slot_extend": True,
            "slot_id": slot_id,
            "extend_months": months
        }
    )
    
    if not success:
        await query.edit_message_text("❌ Gagal memproses pembayaran.")
        return ConversationHandler.END
    
    # Perpanjang slot
    extend_success, new_expiry = rental_db.extend_slot(user_id, slot_id, months)
    
    if not extend_success:
        await query.edit_message_text(f"❌ Gagal memperpanjang slot: {new_expiry}")
        return ConversationHandler.END
    
    text = f"""
{generate_header('PERPANJANGAN SLOT BERHASIL')}

{generate_separator(29)}
✅ *Slot Berhasil Diperpanjang!*
{generate_separator(29)}
📋 *Detail:*
├ Slot ID: `{slot_id[:8]}...`
├ Durasi: {'Lifetime' if months == 0 else f'{months} Bulan'}
├ Harga: {format_money(total_price)}
├ Sisa Saldo: {format_money(BalanceUpdateHandler.get_user_balance(user_id))}
└ Expiry Baru: {new_expiry}

{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 Lihat Semua Slot", callback_data="rental_list_slots")],
        [InlineKeyboardButton("➕ Tambah IP ke Slot Ini", callback_data=f"rental_add_ip_slot_{slot_id}")],
        [InlineKeyboardButton("🏠 Menu Rental", callback_data="user_rental")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def user_rental_add_ip_to_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tambah IP ke slot tertentu"""
    query = update.callback_query
    await query.answer()
    
    slot_id = query.data.replace("rental_add_ip_slot_", "")
    context.user_data["add_ip_slot_id"] = slot_id
    
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    # Cari slot
    slot = None
    for s in user.get('slots', []):
        if s.get('slot_id') == slot_id:
            slot = s
            break
    
    if not slot:
        await query.edit_message_text("❌ Slot tidak ditemukan.")
        return
    
    if not rental_db.is_slot_active(slot):
        await query.edit_message_text("❌ Slot sudah expired. Perpanjang dulu ya.")
        return
    
    if slot.get('used_ips', 0) >= slot.get('max_ips_per_slot', 1):
        await query.edit_message_text("❌ Slot sudah penuh. Hapus IP lain atau upgrade slot.")
        return
    
    text = f"""
{generate_header('TAMBAH IP KE SLOT')}

{generate_separator(29)}
📋 *Slot #{slot.get('slot_number')}*
├ IP Saat Ini: {slot.get('used_ips', 0)}/{slot.get('max_ips_per_slot', 1)}
└ Expiry: {slot.get('expiry_date')}

{generate_separator(29)}
📝 *Langkah 1/2: Masukkan Username*
Masukkan username untuk IP ini:
{generate_separator(29)}
Contoh: `server1`, `vps-jepang`, `client-01`
{generate_separator(29)}
"""
    
    context.user_data["rental_add_ip_stage"] = "username"
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

async def user_rental_remove_ip_from_slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hapus IP dari slot"""
    query = update.callback_query
    await query.answer()
    
    slot_id = query.data.replace("rental_remove_ip_slot_", "")
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    # Cari slot
    slot = None
    for s in user.get('slots', []):
        if s.get('slot_id') == slot_id:
            slot = s
            break
    
    if not slot:
        await query.edit_message_text("❌ Slot tidak ditemukan.")
        return
    
    ips = slot.get('ips', [])
    
    if not ips:
        await query.edit_message_text("📭 Tidak ada IP di slot ini.")
        return
    
    text = f"""
{generate_header('HAPUS IP DARI SLOT')}

{generate_separator(29)}
📋 *Slot #{slot.get('slot_number')}*
Pilih IP yang akan dihapus:
{generate_separator(29)}
"""
    
    keyboard = []
    for ip_data in ips:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ {ip_data['ip']} ({ip_data['username']})",
                callback_data=f"rental_confirm_remove_ip_{slot_id}_{ip_data['ip']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data=f"rental_slot_detail_{slot_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def user_rental_confirm_remove_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi hapus IP dari slot"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.replace("rental_confirm_remove_ip_", "")
    slot_id, ip_address = data.split("_", 1)
    
    user_id = query.from_user.id
    
    text = f"""
{generate_header('KONFIRMASI HAPUS IP')}

{generate_separator(29)}
⚠️ *Hapus IP: `{ip_address}`*
{generate_separator(29)}
IP akan dihapus dari slot ini dan tidak bisa digunakan lagi.
{generate_separator(29)}
✅ *Yakin ingin menghapus?*
{generate_separator(29)}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ YA, HAPUS", callback_data=f"rental_execute_remove_ip_{slot_id}_{ip_address}"),
            InlineKeyboardButton("❌ BATAL", callback_data=f"rental_remove_ip_slot_{slot_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def user_rental_execute_remove_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eksekusi hapus IP"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.replace("rental_execute_remove_ip_", "")
    slot_id, ip_address = data.split("_", 1)
    
    user_id = query.from_user.id
    
    # Hapus IP
    success, message = rental_db.remove_ip_from_slot(user_id, slot_id, ip_address)
    
    if success:
        # Sync ke GitHub
        if rental_db.data["settings"].get("auto_sync", True):
            try:
                await asyncio.to_thread(github_mgr.sync_to_github)
            except:
                pass
        
        await query.edit_message_text(f"✅ IP `{ip_address}` berhasil dihapus dari slot.")
    else:
        await query.edit_message_text(f"❌ Gagal: {message}")
    
    # Kembali ke detail slot
    await asyncio.sleep(1)
    callback_query = type('obj', (object,), {
        'data': f"rental_slot_detail_{slot_id}",
        'from_user': query.from_user,
        'message': query.message,
        'answer': lambda: None
    })
    await user_rental_slot_detail(update._replace(callback_query=callback_query), context)

                
                
                    
                    
async def user_rental_buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pembelian rental"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    if data == "rental_buy_1":
        months = 1
    elif data == "rental_buy_3":
        months = 3
    elif data == "rental_buy_6":
        months = 6
    elif data == "rental_buy_12":
        months = 12
    elif data == "rental_buy_lifetime":
        months = 0  # lifetime
    else:
        await query.edit_message_text("❌ Pilihan tidak valid.")
        return ConversationHandler.END
    
    price = rental_db.calculate_price(months) if months > 0 else rental_db.get_price_per_month() * 12  # Lifetime = 12 bulan
    
    text = f"""
{generate_header('KONFIRMASI PEMBELIAN')}

{generate_separator(29)}
📋 *Detail Pembelian:*
├ Paket: {'Lifetime' if months == 0 else f'{months} Bulan'}
├ Harga: {format_money(price)}
└ Metode: Potong saldo

{generate_separator(29)}
💰 *Saldo Anda:* {format_money(BalanceUpdateHandler.get_user_balance(user_id))}
💰 *Sisa Saldo:* {format_money(BalanceUpdateHandler.get_user_balance(user_id) - price)}
{generate_separator(29)}
"""
    
    if BalanceUpdateHandler.validate_user_balance(user_id, price):
        text += "✅ *Saldo cukup!*"
        keyboard = [
            [
                InlineKeyboardButton("✅ KONFIRMASI", callback_data=f"rental_confirm_{months}"),
                InlineKeyboardButton("❌ BATALKAN", callback_data="user_rental")
            ]
        ]
    else:
        text += "❌ *Saldo tidak cukup!*"
        keyboard = [
            [InlineKeyboardButton("💰 Top Up", callback_data="user_topup")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return "RENTAL_CONFIRM"

async def user_rental_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi pembelian rental"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    months = int(data.replace("rental_confirm_", ""))
    price = rental_db.calculate_price(months) if months > 0 else rental_db.get_price_per_month() * 12
    
    # Cek saldo
    if not BalanceUpdateHandler.validate_user_balance(user_id, price):
        await query.edit_message_text("❌ Saldo tidak cukup.")
        return ConversationHandler.END
    
    # Proses pembayaran
    BalanceUpdateHandler.update_vpn_purchase(user_id, price, f"Rental Auto Script - {months if months > 0 else 'Lifetime'} bulan")
    
    # Daftarkan user
    rental_db.add_user(user_id, username, months)
    
    # Tampilkan sukses
    text = f"""
{generate_header('PEMBELIAN BERHASIL')}

{generate_separator(29)}
✅ *Selamat! Anda sekarang terdaftar.*
{generate_separator(29)}
📋 *Detail:*
├ Paket: {'Lifetime' if months == 0 else f'{months} Bulan'}
├ Harga: {format_money(price)}
├ Sisa Saldo: {format_money(BalanceUpdateHandler.get_user_balance(user_id))}
└ Slot IP: 1 slot

{generate_separator(29)}
🎉 *Anda sekarang bisa:*
├ Menambah IP sendiri
├ Mendapatkan script installer
├ Mengelola IP via bot
└ IP mengikuti masa aktif

{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Tambah IP", callback_data="rental_add_ip")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def user_rental_add_ip_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses tambah IP oleh user"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not rental_db.check_user_access(user_id):
        text = f"""
{generate_header('AKSES DITOLAK')}

{generate_separator(29)}
❌ *Akun Anda sudah expired!*
{generate_separator(29)}
Silakan perpanjang masa aktif untuk menambah IP.
{generate_separator(29)}
"""
        keyboard = [[InlineKeyboardButton("🔄 Perpanjang", callback_data="rental_extend")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return
    
    if not rental_db.can_user_add_ip(user_id):
        text = f"""
{generate_header('SLOT PENUH')}

{generate_separator(29)}
❌ *Slot IP sudah penuh!*
{generate_separator(29)}
Anda telah mencapai maksimal slot IP.
Silakan hapus IP yang tidak digunakan terlebih dahulu.
{generate_separator(29)}
"""
        keyboard = [[InlineKeyboardButton("📋 IP Saya", callback_data="rental_my_ips")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return
    
    context.user_data["rental_add_ip"] = {"stage": "username"}
    
    text = f"""
{generate_header('TAMBAH IP')}

{generate_separator(29)}
📝 *Langkah 1/2: Masukkan Username*
{generate_separator(29)}
Masukkan username untuk IP ini:
(bisa menggunakan nama yang mudah diingat)
{generate_separator(29)}
Contoh: `server1`, `vps-jepang`, `client-01`
{generate_separator(29)}
"""
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

async def user_rental_add_ip_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input untuk tambah IP"""
    if "rental_add_ip" not in context.user_data:
        return
    
    user_id = update.effective_user.id
    text = update.message.text.strip()
    stage = context.user_data["rental_add_ip"]["stage"]
    
    if stage == "username":
        if not text:
            await update.message.reply_text("❌ Username tidak boleh kosong!")
            return
        
        context.user_data["rental_add_ip"]["username"] = text
        context.user_data["rental_add_ip"]["stage"] = "ip"
        
        await update.message.reply_text(
            f"""
{generate_header('TAMBAH IP')}

{generate_separator(29)}
✅ Username: `{text}`
{generate_separator(29)}
📝 *Langkah 2/2: Masukkan Alamat IP*
{generate_separator(29)}
Masukkan alamat IP yang akan didaftarkan:
Format: xxx.xxx.xxx.xxx
{generate_separator(29)}
Contoh: `192.168.1.1`
{generate_separator(29)}
"""
        )
    
    elif stage == "ip":
        # Validasi format IP
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        if not re.match(ip_pattern, text):
            await update.message.reply_text(
                "❌ Format IP tidak valid!\n"
                "Format harus: xxx.xxx.xxx.xxx\n"
                "Contoh: 192.168.1.1\n"
                "Silakan masukkan lagi:"
            )
            return
        
        # Cek apakah IP sudah ada
        if rental_db.get_ip_by_address(text):
            await update.message.reply_text(
                f"❌ IP `{text}` sudah terdaftar!\n"
                "Silakan gunakan IP lain:"
            )
            return
        
        username = context.user_data["rental_add_ip"]["username"]
        
        # Tambah IP ke database
        success, result = rental_db.add_ip(text, username, user_id)
        
        if success:
            # Sync ke GitHub jika auto-sync aktif
            if rental_db.data["settings"].get("auto_sync", True):
                try:
                    await asyncio.to_thread(github_mgr.sync_to_github)
                except:
                    pass
            
            # Generate install script
            script = generate_install_script(
                text, 
                username,
                rental_db.data["settings"]["github_username"],
                rental_db.data["settings"]["github_repo"]
            )
            
            user = rental_db.get_user(user_id)
            
            text_response = f"""
{generate_header('IP BERHASIL DITAMBAH')}

{generate_separator(29)}
✅ *IP Berhasil Ditambahkan!*
{generate_separator(29)}
📋 *Detail IP:*
├ Username: `{username}`
├ IP Address: `{text}`
├ Slot: {user['used_slots']}/{user['max_slots']}
└ Status: Aktif

{generate_separator(29)}
📜 *Script Install:*
```

apt-get update && apt-get upgrade -y && apt install wget -y && wget https://raw.githubusercontent.com/{rental_db.data["settings"]["github_username"]}/{rental_db.data["settings"]["github_repo"]}/main/install2.sh && chmod +x install2.sh && ./install2.sh

```

{generate_separator(29)}
📋 *Cara Install:*
1. Login ke VPS Anda via SSH
2. Copy script di atas
3. Paste di terminal VPS
4. Tunggu hingga proses selesai
5. Gunakan username `{username}` saat instalasi

{generate_separator(29)}
"""
            
            keyboard = [
                [
                    InlineKeyboardButton("📋 IP Saya", callback_data="rental_my_ips"),
                    InlineKeyboardButton("➕ Tambah Lagi", callback_data="rental_add_ip")
                ],
                [InlineKeyboardButton("🔙 Menu Rental", callback_data="user_rental")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(text_response, reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"❌ Gagal menambah IP: {result}")
        
        # Reset session
        context.user_data.pop("rental_add_ip", None)

async def user_rental_my_ips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan IP milik user"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    if not user:
        await query.edit_message_text("❌ User tidak ditemukan.")
        return
    
    ips = user.get("ips", [])
    
    if not ips:
        text = f"""
{generate_header('IP SAYA')}

{generate_separator(29)}
📭 *Belum Ada IP*
{generate_separator(29)}
Anda belum memiliki IP terdaftar.
Silakan tambah IP terlebih dahulu.
{generate_separator(29)}
"""
        keyboard = [
            [InlineKeyboardButton("➕ Tambah IP", callback_data="rental_add_ip")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return
    
    text = f"""
{generate_header('IP SAYA')}

{generate_separator(29)}
📋 *Daftar IP Anda:*
{generate_separator(29)}
"""
    
    keyboard = []
    for i, ip_data in enumerate(ips, 1):
        # Cek status IP
        if rental_db.check_ip_expired(ip_data["ip"]):
            status = "🔴 Expired"
        else:
            status = "🟢 Aktif"
        
        text += f"{i}. `{ip_data['ip']}` ({ip_data['username']}) - {status}\n"
        
        # Tombol hapus untuk setiap IP
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ Hapus {ip_data['username'][:10]}...",
                callback_data=f"rental_delete_ip_{ip_data['ip']}"
            )
        ])
    
    text += f"""
{generate_separator(29)}
📊 *Total: {len(ips)} IP | Slot: {user['used_slots']}/{user['max_slots']}
{generate_separator(29)}
"""
    
    keyboard.append([InlineKeyboardButton("➕ Tambah IP", callback_data="rental_add_ip")])
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def user_rental_delete_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hapus IP user"""
    query = update.callback_query
    await query.answer()
    
    ip_address = query.data.replace("rental_delete_ip_", "")
    user_id = query.from_user.id
    
    # Konfirmasi
    text = f"""
{generate_header('KONFIRMASI HAPUS IP')}

{generate_separator(29)}
⚠️ *Hapus IP: `{ip_address}`*
{generate_separator(29)}
IP akan dihapus dari database dan tidak bisa digunakan lagi.
{generate_separator(29)}
✅ *Yakin ingin menghapus?*
{generate_separator(29)}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ YA, HAPUS", callback_data=f"rental_confirm_delete_{ip_address}"),
            InlineKeyboardButton("❌ BATAL", callback_data="rental_my_ips")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def user_rental_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi hapus IP"""
    query = update.callback_query
    await query.answer()
    
    ip_address = query.data.replace("rental_confirm_delete_", "")
    user_id = query.from_user.id
    
    # Hapus dari database
    rental_db.remove_ip(ip_address)
    
    # Sync ke GitHub jika auto-sync aktif
    if rental_db.data["settings"].get("auto_sync", True):
        try:
            await asyncio.to_thread(github_mgr.sync_to_github)
        except:
            pass
    
    text = f"""
{generate_header('IP DIHAPUS')}

{generate_separator(29)}
✅ *IP `{ip_address}` berhasil dihapus!*
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 IP Saya", callback_data="rental_my_ips")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def user_rental_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan status rental user"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = rental_db.get_user(user_id)
    
    if not user:
        await query.edit_message_text("❌ User tidak ditemukan.")
        return
    
    # Hitung sisa hari
    if user["expiry_date"] == "lifetime":
        days_left = "∞ (Lifetime)"
        expiry_status = "⭐ Lifetime"
        expiry_bar = "████████████████████ [LIFETIME]"
    else:
        try:
            expiry = datetime.fromisoformat(user["expiry_date"])
            now = datetime.now()
            total_days = 30 * user.get("months_added", 1)
            days_left = (expiry - now).days
            days_passed = total_days - days_left
            
            if days_left < 0:
                expiry_status = "🔴 EXPIRED"
                expiry_bar = "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒ [EXPIRED]"
            else:
                # Progress bar sederhana
                bar_length = 20
                filled = int((days_passed / total_days) * bar_length) if total_days > 0 else 0
                bar = "█" * min(filled, bar_length) + "▒" * (bar_length - min(filled, bar_length))
                expiry_bar = f"{bar} [{days_left} hari]"
                expiry_status = f"🟢 {days_left} hari lagi"
        except:
            days_left = "N/A"
            expiry_status = "❓ Unknown"
            expiry_bar = "▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒"
    
    text = f"""
{generate_header('STATUS RENTAL')}

{generate_separator(29)}
👤 *User:* {user['username']}
🆔 *ID:* `{user['user_id']}`

📅 *Masa Aktif:*
├ Status: {expiry_status}
├ Expiry: {user['expiry_date']}
└ {expiry_bar}

📊 *Penggunaan:*
├ Total IP: {len(user.get('ips', []))}
├ Slot: {user['used_slots']}/{user['max_slots']}
└ Total Spent: {format_money(user.get('total_spent', 0))}

📈 *Statistik:*
├ Terdaftar: {user['registered_at'][:10]}
├ Pembayaran: {user.get('months_added', 0)} bulan
└ Terakhir: {user.get('last_payment', 'N/A')[:10]}

{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Perpanjang", callback_data="rental_extend")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def user_rental_extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perpanjang masa aktif rental"""
    query = update.callback_query
    await query.answer()
    
    text = f"""
{generate_header('PERPANJANG RENTAL')}

{generate_separator(29)}
💰 *Pilih durasi perpanjangan:*
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("1 Bulan", callback_data="rental_extend_1")],
        [InlineKeyboardButton("3 Bulan", callback_data="rental_extend_3")],
        [InlineKeyboardButton("6 Bulan", callback_data="rental_extend_6")],
        [InlineKeyboardButton("12 Bulan", callback_data="rental_extend_12")],
        [InlineKeyboardButton("Lifetime", callback_data="rental_extend_lifetime")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    
    return "RENTAL_EXTEND"

async def user_rental_extend_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi perpanjangan rental"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    if data == "rental_extend_1":
        months = 1
    elif data == "rental_extend_3":
        months = 3
    elif data == "rental_extend_6":
        months = 6
    elif data == "rental_extend_12":
        months = 12
    elif data == "rental_extend_lifetime":
        months = 0
    else:
        await query.edit_message_text("❌ Pilihan tidak valid.")
        return ConversationHandler.END
    
    price = rental_db.calculate_price(months) if months > 0 else rental_db.get_price_per_month() * 12
    
    text = f"""
{generate_header('KONFIRMASI PERPANJANGAN')}

{generate_separator(29)}
📋 *Detail Perpanjangan:*
├ Durasi: {'Lifetime' if months == 0 else f'{months} Bulan'}
├ Harga: {format_money(price)}
└ Metode: Potong saldo

{generate_separator(29)}
💰 *Saldo Anda:* {format_money(BalanceUpdateHandler.get_user_balance(user_id))}
💰 *Sisa Saldo:* {format_money(BalanceUpdateHandler.get_user_balance(user_id) - price)}
{generate_separator(29)}
"""
    
    if BalanceUpdateHandler.validate_user_balance(user_id, price):
        text += "✅ *Saldo cukup!*"
        keyboard = [
            [
                InlineKeyboardButton("✅ KONFIRMASI", callback_data=f"rental_confirm_extend_{months}"),
                InlineKeyboardButton("❌ BATALKAN", callback_data="rental_extend")
            ]
        ]
    else:
        text += "❌ *Saldo tidak cukup!*"
        keyboard = [
            [InlineKeyboardButton("💰 Top Up", callback_data="user_topup")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="rental_extend")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    
    return "RENTAL_EXTEND_CONFIRM"

async def user_rental_extend_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eksekusi perpanjangan rental"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    
    months = int(data.replace("rental_confirm_extend_", ""))
    price = rental_db.calculate_price(months) if months > 0 else rental_db.get_price_per_month() * 12
    
    # Cek saldo
    if not BalanceUpdateHandler.validate_user_balance(user_id, price):
        await query.edit_message_text("❌ Saldo tidak cukup.")
        return ConversationHandler.END
    
    # Proses pembayaran
    BalanceUpdateHandler.update_vpn_purchase(user_id, price, f"Perpanjangan Rental - {months if months > 0 else 'Lifetime'} bulan")
    
    # Update user
    user = rental_db.get_user(user_id)
    if user:
        if user["expiry_date"] == "lifetime":
            # Jika sudah lifetime, tetap lifetime
            pass
        elif months == 0:
            user["expiry_date"] = "lifetime"
        else:
            try:
                current_expiry = datetime.fromisoformat(user["expiry_date"])
                new_expiry = current_expiry + timedelta(days=months * 30)
                user["expiry_date"] = new_expiry.isoformat()
            except:
                user["expiry_date"] = (datetime.now() + timedelta(days=months * 30)).isoformat()
        
        user["total_spent"] = user.get("total_spent", 0) + price
        user["last_payment"] = datetime.now().isoformat()
        user["months_added"] = user.get("months_added", 0) + months
        rental_db.save()
    
    text = f"""
{generate_header('PERPANJANGAN BERHASIL')}

{generate_separator(29)}
✅ *Masa aktif berhasil diperpanjang!*
{generate_separator(29)}
📋 *Detail:*
├ Durasi: {'Lifetime' if months == 0 else f'{months} Bulan'}
├ Harga: {format_money(price)}
├ Sisa Saldo: {format_money(BalanceUpdateHandler.get_user_balance(user_id))}
└ Expiry Baru: {user['expiry_date'] if user else 'N/A'}

{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("📊 Cek Status", callback_data="rental_status")],
        [InlineKeyboardButton("🔙 Menu Rental", callback_data="user_rental")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def user_rental_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panduan installasi"""
    query = update.callback_query
    await query.answer()
    
    text = f"""
{generate_header('PANDUAN INSTALL')}

{generate_separator(29)}
📋 *Cara Install Script di VPS:*

{generate_separator(29)}
🔧 *Metode 1 - Copy Paste:*
```

apt-get update && apt-get upgrade -y && apt install wget -y && wget https://raw.githubusercontent.com/{rental_db.data["settings"]["github_username"]}/{rental_db.data["settings"]["github_repo"]}/main/install2.sh && chmod +x install2.sh && ./install2.sh

```

{generate_separator(29)}
📝 *Metode 2 - Manual:*
1. Login ke VPS via SSH
2. Update sistem:
   `apt-get update && apt-get upgrade -y`
3. Install wget:
   `apt install wget -y`
4. Download script:
   `wget https://raw.githubusercontent.com/{rental_db.data["settings"]["github_username"]}/{rental_db.data["settings"]["github_repo"]}/main/install2.sh`
5. Buat executable:
   `chmod +x install2.sh`
6. Jalankan script:
   `./install2.sh`

{generate_separator(29)}
⚠️ *Catatan Penting:*
• Gunakan username yang sudah didaftarkan
• Pastikan koneksi internet stabil
• Tunggu hingga proses selesai
• Jangan tutup terminal selama proses

{generate_separator(29)}
💡 *Jika ada kendala, hubungi admin.*
{generate_separator(29)}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="user_rental")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

# ==================== ADMIN RENTAL ====================

async def admin_rental_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panel admin untuk rental system - VERSI SLOT"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text("❌ Akses ditolak.")
        return
    
    settings = rental_db.get_settings()
    users = rental_db.get_all_users()
    ips = rental_db.get_all_ips()
    
    # Hitung statistik slot
    total_slots = 0
    active_slots = 0
    for user in users:
        slots = user.get('slots', [])
        total_slots += len(slots)
        for slot in slots:
            if rental_db.is_slot_active(slot):
                active_slots += 1
    
    total_users = len(users)
    total_ips = len(ips)
    total_revenue = sum(u.get("total_spent", 0) for u in users)
    
    text = f"""
{generate_header('ADMIN RENTAL PANEL - SLOT SYSTEM')}

{generate_separator(29)}
📊 *Statistik Rental (Slot System):*
├ Total User: {total_users}
├ Total Slots: {total_slots}
├ Slot Aktif: {active_slots}
├ Total IP: {total_ips}
└ Total Revenue: {format_money(total_revenue)}

{generate_separator(29)}
⚙️ *Pengaturan:*
├ Harga/Slot/Bulan: {format_money(settings['price_per_slot'])}
├ Max Slots/User: {settings.get('max_slots_per_user', 10)}
├ Default IP/Slot: {settings.get('default_ips_per_slot', 1)}
├ GitHub: {'✅' if settings['github_token'] else '❌'} Terkoneksi
├ Auto Sync: {'✅ Ya' if settings.get('auto_sync', True) else '❌ Tidak'}
└ File IP: {settings['github_file_path']}

{generate_separator(29)}
📋 *Menu Admin:*
"""
    
    keyboard = [
        [InlineKeyboardButton("💰 Set Harga per Slot", callback_data="admin_rental_set_price")],
        [InlineKeyboardButton("🔧 Konfigurasi GitHub", callback_data="admin_rental_github")],
        [InlineKeyboardButton("👥 List User & Slots", callback_data="admin_rental_users")],
        [InlineKeyboardButton("📋 List IP", callback_data="admin_rental_ips")],
        [InlineKeyboardButton("➕ Tambah Slot ke User", callback_data="admin_rental_add_slot")],
        [InlineKeyboardButton("🗑️ Hapus Slot", callback_data="admin_rental_delete_slot")],
        [InlineKeyboardButton("🔄 Sync ke GitHub", callback_data="admin_rental_sync")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="admin_rental_settings")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def admin_rental_set_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set harga rental per bulan"""
    query = update.callback_query
    await query.answer()
    
    current_price = rental_db.get_price_per_month()
    
    text = f"""
{generate_header('SET HARGA RENTAL')}

{generate_separator(29)}
💰 *Harga Saat Ini:* {format_money(current_price)}/bulan
{generate_separator(29)}

Masukkan harga baru per bulan (dalam Rupiah):
Contoh: 50000, 75000, 100000
Ketik 'batal' untuk membatalkan.
{generate_separator(29)}
"""
    await query.edit_message_text(text)
    
    context.user_data["admin_rental_action"] = "set_price"
    return "ADMIN_RENTAL_SET_PRICE"

async def admin_rental_github_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfigurasi GitHub"""
    query = update.callback_query
    await query.answer()
    
    settings = rental_db.get_settings()
    
    text = f"""
{generate_header('KONFIGURASI GITHUB')}

{generate_separator(29)}
📁 *Konfigurasi Saat Ini:*
├ Token: {'✅ Tersimpan' if settings['github_token'] else '❌ Kosong'}
├ Username: {settings['github_username'] or '❌ Kosong'}
├ Repository: {settings['github_repo'] or '❌ Kosong'}
└ File Path: {settings['github_file_path']}

{generate_separator(29)}
📝 *Pilih yang akan diubah:*
"""
    
    keyboard = [
        [InlineKeyboardButton("🔑 Set Token", callback_data="admin_rental_github_token")],
        [InlineKeyboardButton("👤 Set Username", callback_data="admin_rental_github_username")],
        [InlineKeyboardButton("📁 Set Repository", callback_data="admin_rental_github_repo")],
        [InlineKeyboardButton("📄 Set File Path", callback_data="admin_rental_github_path")],
        [InlineKeyboardButton("🔄 Test Koneksi", callback_data="admin_rental_github_test")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_rental_github_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input untuk konfigurasi GitHub"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "admin_rental_github_token":
        context.user_data["admin_rental_github_field"] = "github_token"
        await query.edit_message_text(
            "Masukkan GitHub Personal Access Token:\n"
            "• Token bisa dibuat di GitHub Settings\n"
            "• Required scope: repo\n"
            "Ketik 'batal' untuk membatalkan."
        )
    
    elif data == "admin_rental_github_username":
        context.user_data["admin_rental_github_field"] = "github_username"
        await query.edit_message_text(
            "Masukkan GitHub Username:\n"
            "Contoh: storevpn\n"
            "Ketik 'batal' untuk membatalkan."
        )
    
    elif data == "admin_rental_github_repo":
        context.user_data["admin_rental_github_field"] = "github_repo"
        await query.edit_message_text(
            "Masukkan Repository Name:\n"
            "Contoh: project\n"
            "Ketik 'batal' untuk membatalkan."
        )
    
    elif data == "admin_rental_github_path":
        context.user_data["admin_rental_github_field"] = "github_file_path"
        await query.edit_message_text(
            "Masukkan File Path:\n"
            "Contoh: ip\n"
            "Ketik 'batal' untuk membatalkan."
        )
    
    elif data == "admin_rental_github_test":
        await query.edit_message_text("🔄 Testing koneksi ke GitHub...")
        
        if github_mgr.is_configured():
            # Coba get file SHA
            sha = github_mgr.get_file_sha()
            if sha:
                await query.edit_message_text(
                    "✅ **Koneksi GitHub Berhasil!**\n\n"
                    f"Repository: {github_mgr.username}/{github_mgr.repo}\n"
                    f"File: {github_mgr.file_path}\n"
                    f"SHA: {sha[:8]}...\n\n"
                    "Siap untuk sync.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_github")]
                    ])
                )
            else:
                await query.edit_message_text(
                    "⚠️ **File tidak ditemukan, tapi koneksi berhasil.**\n\n"
                    "File akan dibuat saat pertama kali sync.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_github")]
                    ])
                )
        else:
            await query.edit_message_text(
                "❌ **Konfigurasi GitHub belum lengkap!**\n\n"
                "Lengkapi semua field terlebih dahulu.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_github")]
                ])
            )
    
    return "ADMIN_RENTAL_GITHUB_INPUT"

async def admin_rental_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List semua user rental"""
    query = update.callback_query
    await query.answer()
    
    users = rental_db.get_all_users()
    
    if not users:
        await query.edit_message_text("📭 Belum ada user rental.")
        return
    
    text = f"""
{generate_header('LIST USER RENTAL')}

{generate_separator(29)}
👥 *Total: {len(users)} User*
{generate_separator(29)}
"""
    
    keyboard = []
    for user in users[:10]:  # Limit 10 per halaman
        # Status
        if rental_db.check_user_access(user["user_id"]):
            if user["expiry_date"] == "lifetime":
                status = "⭐ LIFETIME"
                status_emoji = "⭐"
            else:
                status = "🟢 ACTIVE"
                status_emoji = "🟢"
        else:
            status = "🔴 EXPIRED"
            status_emoji = "🔴"
        
        text += f"""
{status_emoji} *{user['username']}*
├ ID: `{user['user_id']}`
├ IP: {user['used_slots']}/{user['max_slots']}
├ Expiry: {user['expiry_date']}
└ Spent: {format_money(user.get('total_spent', 0))}
"""
        
        keyboard.append([
            InlineKeyboardButton(
                f"📊 {user['username'][:15]}...",
                callback_data=f"admin_rental_user_{user['user_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_rental_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detail user rental"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.replace("admin_rental_user_", ""))
    user = rental_db.get_user(user_id)
    
    if not user:
        await query.edit_message_text("❌ User tidak ditemukan.")
        return
    
    # Hitung sisa hari
    if user["expiry_date"] == "lifetime":
        days_left = "∞ (Lifetime)"
    else:
        try:
            expiry = datetime.fromisoformat(user["expiry_date"])
            days_left = (expiry - datetime.now()).days
        except:
            days_left = "N/A"
    
    text = f"""
{generate_header('DETAIL USER RENTAL')}

{generate_separator(29)}
👤 *Username:* {user['username']}
🆔 *User ID:* `{user['user_id']}`

📅 *Informasi Akun:*
├ Registered: {user['registered_at'][:10]}
├ Expiry: {user['expiry_date']}
├ Sisa Hari: {days_left}
└ Status: {'Aktif' if rental_db.check_user_access(user_id) else 'Expired'}

📊 *Penggunaan:*
├ Total IP: {len(user.get('ips', []))}
├ Slot: {user['used_slots']}/{user['max_slots']}
├ Total Spent: {format_money(user.get('total_spent', 0))}
├ Bulan Dibeli: {user.get('months_added', 0)} bulan
└ Last Payment: {user.get('last_payment', 'N/A')[:10]}

📋 *Daftar IP:*
"""
    
    if user.get("ips"):
        for ip in user["ips"]:
            text += f"├ `{ip['ip']}` ({ip['username']})\n"
    else:
        text += "├ Tidak ada IP\n"
    
    text += generate_separator(29)
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Tambah IP", callback_data=f"admin_rental_add_ip_user_{user_id}"),
            InlineKeyboardButton("🗑️ Hapus User", callback_data=f"admin_rental_delete_user_{user_id}")
        ],
        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_users")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_rental_list_ips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List semua IP rental"""
    query = update.callback_query
    await query.answer()
    
    ips = rental_db.get_all_ips()
    
    if not ips:
        await query.edit_message_text("📭 Belum ada IP terdaftar.")
        return
    
    text = f"""
{generate_header('LIST IP RENTAL')}

{generate_separator(29)}
📋 *Total: {len(ips)} IP*
{generate_separator(29)}
"""
    
    for ip in ips[:15]:  # Limit 15 IP
        # Status
        if rental_db.check_ip_expired(ip["ip"]):
            status = "🔴 EXPIRED"
        else:
            status = "🟢 ACTIVE"
        
        owner = rental_db.get_user(ip["owner_id"]) if ip["owner_id"] else None
        owner_name = owner["username"] if owner else "Tanpa Owner"
        
        text += f"""
{status} *{ip['username']}*
├ IP: `{ip['ip']}`
├ Owner: {owner_name}
├ Expiry: {ip['expiry_date']}
└ Added: {ip['added_at'][:10]}
"""
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Hapus IP", callback_data="admin_rental_delete_ip")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_rental_add_ip_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses tambah IP oleh admin"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "admin_rental_add_ip":
        # Tambah IP tanpa user tertentu
        context.user_data["admin_rental_add_ip"] = {"stage": "username", "user_id": None}
    elif data.startswith("admin_rental_add_ip_user_"):
        # Tambah IP untuk user tertentu
        user_id = int(data.replace("admin_rental_add_ip_user_", ""))
        user = rental_db.get_user(user_id)
        if not user:
            await query.edit_message_text("❌ User tidak ditemukan.")
            return
        context.user_data["admin_rental_add_ip"] = {"stage": "username", "user_id": user_id}
    else:
        return
    
    text = f"""
{generate_header('TAMBAH IP (ADMIN)')}

{generate_separator(29)}
📝 *Langkah 1/4: Masukkan Username*
{generate_separator(29)}
Masukkan username untuk IP ini:
{generate_separator(29)}
Contoh: `server1`, `vps-jepang`
{generate_separator(29)}
"""
    await query.edit_message_text(text)

async def admin_rental_delete_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu hapus IP oleh admin"""
    query = update.callback_query
    await query.answer()
    
    ips = rental_db.get_all_ips()
    
    if not ips:
        await query.edit_message_text("📭 Tidak ada IP untuk dihapus.")
        return
    
    text = f"""
{generate_header('HAPUS IP (ADMIN)')}

{generate_separator(29)}
🗑️ *Pilih IP yang akan dihapus:*
{generate_separator(29)}
"""
    
    keyboard = []
    for ip in ips[:15]:
        keyboard.append([
            InlineKeyboardButton(
                f"❌ {ip['ip']} ({ip['username']})",
                callback_data=f"admin_rental_confirm_delete_ip_{ip['ip']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def admin_rental_sync(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sync ke GitHub"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🔄 Menyinkronisasi ke GitHub...")
    
    success, message = await asyncio.to_thread(github_mgr.sync_to_github)
    
    if success:
        await query.edit_message_text(
            f"✅ **{message}**\n\n"
            f"📁 Repository: {github_mgr.username}/{github_mgr.repo}\n"
            f"📄 File: {github_mgr.file_path}\n"
            f"👤 Total IP: {len(rental_db.get_all_ips())}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_panel")]
            ])
        )
    else:
        await query.edit_message_text(
            f"❌ **{message}**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_panel")]
            ])
        )

async def admin_rental_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu settings rental"""
    query = update.callback_query
    await query.answer()
    
    settings = rental_db.get_settings()
    
    text = f"""
{generate_header('SETTINGS RENTAL')}

{generate_separator(29)}
⚙️ *Pengaturan Saat Ini:*
├ Harga/Bulan: {format_money(settings['price_per_month'])}
├ Max Slots/User: {settings.get('max_slots', 1)} IP
├ Auto Sync: {'✅ Ya' if settings.get('auto_sync', True) else '❌ Tidak'}
└ Default Expiry: {'Lifetime' if settings.get('default_expiry') == 0 else f"{settings.get('default_expiry', 30)} hari"}

{generate_separator(29)}
📝 *Ubah Pengaturan:*
"""
    
    keyboard = [
        [InlineKeyboardButton("💰 Ubah Harga", callback_data="admin_rental_set_price")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_rental_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# ==================== HANDLER MESSAGE UNTUK RENTAL ====================

async def handle_rental_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle message untuk proses rental"""
    if "rental_add_ip" in context.user_data:
        await user_rental_add_ip_message(update, context)
    
    elif "admin_rental_add_ip" in context.user_data:
        await admin_rental_add_ip_message(update, context)
    
    elif "admin_rental_action" in context.user_data:
        await admin_rental_action_message(update, context)
    
    elif "admin_rental_github_field" in context.user_data:
        await admin_rental_github_message(update, context)

async def admin_rental_add_ip_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input untuk admin tambah IP"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    text = update.message.text.strip()
    data = context.user_data["admin_rental_add_ip"]
    stage = data["stage"]
    
    if text.lower() == "batal":
        await update.message.reply_text("❌ Proses dibatalkan.")
        context.user_data.pop("admin_rental_add_ip", None)
        return
    
    if stage == "username":
        if not text:
            await update.message.reply_text("❌ Username tidak boleh kosong!")
            return
        
        data["username"] = text
        data["stage"] = "expiry"
        
        await update.message.reply_text(
            f"""
{generate_header('TAMBAH IP (ADMIN)')}

{generate_separator(29)}
✅ Username: `{text}`
{generate_separator(29)}
📝 *Langkah 2/4: Masukkan Masa Aktif*
{generate_separator(29)}
Masukkan masa aktif (dalam hari):
• Ketik angka (contoh: 30 untuk 30 hari)
• Ketik 0 untuk lifetime
• Ketik 'batal' untuk membatalkan
{generate_separator(29)}
"""
        )
    
    elif stage == "expiry":
        try:
            days = int(text)
            if days < 0:
                await update.message.reply_text("❌ Masukkan angka positif atau 0!")
                return
            
            data["days"] = days
            data["stage"] = "ip"
            
            expiry_text = "lifetime" if days == 0 else f"{days} hari"
            
            await update.message.reply_text(
                f"""
{generate_header('TAMBAH IP (ADMIN)')}

{generate_separator(29)}
✅ Masa aktif: {expiry_text}
{generate_separator(29)}
📝 *Langkah 3/4: Masukkan Alamat IP*
{generate_separator(29)}
Format: xxx.xxx.xxx.xxx
Contoh: 192.168.1.1
{generate_separator(29)}
"""
            )
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif stage == "ip":
        # Validasi format IP
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        if not re.match(ip_pattern, text):
            await update.message.reply_text(
                "❌ Format IP tidak valid!\n"
                "Format harus: xxx.xxx.xxx.xxx\n"
                "Contoh: 192.168.1.1\n"
                "Silakan masukkan lagi:"
            )
            return
        
        # Cek apakah IP sudah ada
        if rental_db.get_ip_by_address(text):
            await update.message.reply_text(
                f"❌ IP `{text}` sudah ada di database!\n"
                "Silakan gunakan IP lain:"
            )
            return
        
        data["ip"] = text
        data["stage"] = "owner"
        
        if data.get("user_id"):
            # Jika sudah punya target user, langsung proses
            username = data["username"]
            days = data["days"]
            ip_address = data["ip"]
            target_user_id = data["user_id"]
            
            # Tambah IP
            success, result = rental_db.add_ip(ip_address, username, target_user_id, days if days > 0 else None)
            
            if success:
                # Sync ke GitHub
                if rental_db.data["settings"].get("auto_sync", True):
                    try:
                        await asyncio.to_thread(github_mgr.sync_to_github)
                    except:
                        pass
                
                await update.message.reply_text(
                    f"✅ **IP Berhasil Ditambahkan untuk User!**\n\n"
                    f"Username: `{username}`\n"
                    f"IP: `{ip_address}`\n"
                    f"User ID: {target_user_id}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Menu Admin", callback_data="admin_rental_panel")]
                    ])
                )
            else:
                await update.message.reply_text(f"❌ Gagal: {result}")
            
            context.user_data.pop("admin_rental_add_ip", None)
        else:
            # Tanya owner
            await update.message.reply_text(
                f"""
{generate_header('TAMBAH IP (ADMIN)')}

{generate_separator(29)}
✅ IP: `{text}`
{generate_separator(29)}
📝 *Langkah 4/4: Masukkan User ID Owner*
{generate_separator(29)}
Masukkan User ID pemilik IP:
• Ketik angka User ID Telegram
• Ketik 0 atau kosongkan untuk tanpa owner
• Ketik 'batal' untuk membatalkan
{generate_separator(29)}
"""
            )
    
    elif stage == "owner":
        username = data["username"]
        days = data["days"]
        ip_address = data["ip"]
        
        owner_id = None
        if text and text != "0":
            try:
                owner_id = int(text)
                user = rental_db.get_user(owner_id)
                if not user:
                    await update.message.reply_text(
                        f"❌ User ID `{owner_id}` tidak ditemukan dalam database rental!\n"
                        "Masukkan User ID yang valid atau 0 untuk tanpa owner:"
                    )
                    return
            except ValueError:
                await update.message.reply_text("❌ User ID harus angka!")
                return
        
        # Tambah IP
        success, result = rental_db.add_ip(ip_address, username, owner_id, days if days > 0 else None)
        
        if success:
            # Sync ke GitHub
            if rental_db.data["settings"].get("auto_sync", True):
                try:
                    await asyncio.to_thread(github_mgr.sync_to_github)
                except:
                    pass
            
            await update.message.reply_text(
                f"✅ **IP Berhasil Ditambahkan!**\n\n"
                f"Username: `{username}`\n"
                f"IP: `{ip_address}`\n"
                f"Masa Aktif: {'lifetime' if days == 0 else f'{days} hari'}\n"
                f"Owner: {owner_id if owner_id else 'Tanpa owner'}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Menu Admin", callback_data="admin_rental_panel")]
                ])
            )
        else:
            await update.message.reply_text(f"❌ Gagal: {result}")
        
        context.user_data.pop("admin_rental_add_ip", None)

async def admin_rental_action_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input untuk aksi admin"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    text = update.message.text.strip()
    action = context.user_data["admin_rental_action"]
    
    if text.lower() == "batal":
        await update.message.reply_text("❌ Proses dibatalkan.")
        context.user_data.pop("admin_rental_action", None)
        return
    
    if action == "set_price":
        try:
            price = int(text)
            if price <= 0:
                await update.message.reply_text("❌ Harga harus lebih dari 0!")
                return
            
            rental_db.update_settings(price_per_month=price)
            
            await update.message.reply_text(
                f"✅ **Harga rental berhasil diupdate!**\n\n"
                f"Harga baru: {format_money(price)}/bulan",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Menu Admin", callback_data="admin_rental_panel")]
                ])
            )
            context.user_data.pop("admin_rental_action", None)
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")
    
    elif action == "set_slots":
        try:
            slots = int(text)
            if slots < 1:
                await update.message.reply_text("❌ Minimal 1 slot!")
                return
            
            settings = rental_db.get_settings()
            settings["max_slots"] = slots
            rental_db.save()
            
            await update.message.reply_text(
                f"✅ **Max slots berhasil diupdate!**\n\n"
                f"Max slots baru: {slots} IP per user",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Menu Admin", callback_data="admin_rental_panel")]
                ])
            )
            context.user_data.pop("admin_rental_action", None)
        except ValueError:
            await update.message.reply_text("❌ Masukkan angka yang valid!")

async def admin_rental_github_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input untuk konfigurasi GitHub"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return
    
    text = update.message.text.strip()
    field = context.user_data["admin_rental_github_field"]
    
    if text.lower() == "batal":
        await update.message.reply_text("❌ Proses dibatalkan.")
        context.user_data.pop("admin_rental_github_field", None)
        return
    
    # Update setting
    rental_db.update_settings(**{field: text})
    
    # Update GitHub manager instance
    global github_mgr
    github_mgr = GitHubManager()
    
    field_names = {
        "github_token": "Token",
        "github_username": "Username",
        "github_repo": "Repository",
        "github_file_path": "File Path"
    }
    
    await update.message.reply_text(
        f"✅ **{field_names.get(field, field)} berhasil disimpan!**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Kembali ke Konfigurasi", callback_data="admin_rental_github")]
        ])
    )
    
    context.user_data.pop("admin_rental_github_field", None)
                                                     

def get_final_price(vps_id: str, service_type: str, duration: str) -> Tuple[int, str]:
    """
    Get harga final dengan prioritas:
    1. Harga server khusus (jika ada dan bukan None)
    2. Harga default
    
    Returns: (harga, source)
    """
    # Cek harga server khusus
    server_prices = get_server_prices()
    if vps_id in server_prices and service_type in server_prices[vps_id]:
        server_price = server_prices[vps_id][service_type].get(duration)
        if server_price is not None:
            return server_price, "server_specific"
    
    # Fallback ke harga default
    default_prices = get_prices()
    if service_type in default_prices and duration in default_prices[service_type]:
        return default_prices[service_type][duration], "default"
    
    return 0, "none"

def get_available_durations(vps_id: str, service_type: str) -> List[str]:
    """Get semua durasi yang tersedia untuk kombinasi VPS dan layanan tertentu"""
    durations = set()
    
    # 1. Cek dari harga server khusus
    server_prices = get_server_prices()
    if vps_id in server_prices and service_type in server_prices[vps_id]:
        for dur in server_prices[vps_id][service_type].keys():
            # Skip jika harga None (tidak ada harga)
            if server_prices[vps_id][service_type][dur] is not None:
                durations.add(dur)
    
    # 2. Cek dari harga default
    default_prices = get_prices()
    if service_type in default_prices:
        for dur in default_prices[service_type].keys():
            durations.add(dur)
    
    # 3. Konversi ke list dan sort
    durations_list = list(durations)
    
    # Konversi ke integer untuk sorting
    try:
        durations_list = sorted([int(d) for d in durations_list])
        # Konversi kembali ke string
        durations_list = [str(d) for d in durations_list]
    except:
        # Jika ada yang bukan angka, sort sebagai string
        durations_list.sort()
    
    return durations_list


def format_duration_text(duration_str: str) -> str:
    """Format durasi menjadi teks yang mudah dibaca"""
    try:
        duration = int(duration_str)
        if duration == 1:
            return "1 Hari"
        elif duration == 7:
            return "7 Hari"
        elif duration == 15:
            return "15 Hari"
        elif duration == 30:
            return "30 Hari"
        elif duration == 90:
            return "90 Hari"
        elif duration == 365:
            return "1 Tahun"
        else:
            return f"{duration} Hari"
    except:
        return f"{duration_str} Hari"


def get_ip_limits() -> Dict:
    """Get semua IP limit default"""
    return load_json(IP_LIMIT_DB)

def get_ip_limit(vps_id: str, service_type: str, duration: str) -> int:
    """Get IP limit default untuk kombinasi tertentu"""
    ip_limits = get_ip_limits()
    key = f"{vps_id}_{service_type}_{duration}"
    return ip_limits.get(key, 1)  # Default 1 IP jika tidak ada setting

def set_ip_limit(vps_id: str, service_type: str, duration: str, limit: int):
    """Set IP limit default"""
    ip_limits = get_ip_limits()
    key = f"{vps_id}_{service_type}_{duration}"
    ip_limits[key] = limit
    save_json(IP_LIMIT_DB, ip_limits)


def load_json(file_path: str) -> Dict:
    """Load data dari file JSON"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_user(user_id: int) -> Dict:
    """Get user data"""
    users = load_json(USERS_DB)
    user_str = str(user_id)
    if user_str not in users:
        users[user_str] = {
            "user_id": user_id,
            "balance": 0,
            "role": "user",
            "created_at": datetime.now().isoformat(),
            "vpn_accounts": [],
            "total_spent": 0,
            "total_orders": 0,
            "trial_used": False
        }
        save_json(USERS_DB, users)
    return users[user_str]

def update_user(user_id: int, updates: Dict):
    """Update user data"""
    users = load_json(USERS_DB)
    user_str = str(user_id)
    if user_str in users:
        users[user_str].update(updates)
        save_json(USERS_DB, users)

def add_vps(vps_data: Dict) -> str:
    """Tambahkan VPS baru"""
    vps_list = load_json(VPS_DB)
    vps_id = str(uuid.uuid4())[:8]
    vps_data["id"] = vps_id
    vps_data["status"] = "active"
    vps_data["created_at"] = datetime.now().isoformat()
    vps_list[vps_id] = vps_data
    save_json(VPS_DB, vps_list)
    return vps_id

def update_vps(vps_id: str, updates: Dict) -> bool:
    """Update data VPS"""
    vps_list = load_json(VPS_DB)
    if vps_id in vps_list:
        vps_list[vps_id].update(updates)
        save_json(VPS_DB, vps_list)
        return True
    return False

def delete_vps(vps_id: str) -> bool:
    """Hapus VPS"""
    vps_list = load_json(VPS_DB)
    if vps_id in vps_list:
        del vps_list[vps_id]
        save_json(VPS_DB, vps_list)
        return True
    return False

def get_all_vps() -> Dict:
    """Get semua VPS"""
    return load_json(VPS_DB)

def get_vps(vps_id: str) -> Optional[Dict]:
    """Get VPS by ID"""
    vps_list = load_json(VPS_DB)
    return vps_list.get(vps_id)

def get_prices() -> Dict:
    """Get semua harga default"""
    return load_json(PRICES_DB)

def get_server_prices() -> Dict:
    """Get semua harga per server"""
    return load_json(SERVER_PRICES_DB)

def get_server_price(vps_id: str, service_type: str, duration: str) -> Optional[int]:
    """Get harga spesifik untuk server tertentu"""
    server_prices = get_server_prices()
    if vps_id in server_prices:
        if service_type in server_prices[vps_id]:
            return server_prices[vps_id][service_type].get(duration)
    return None

def update_price(service_type: str, duration: str, price: int):
    """Update harga default"""
    prices = get_prices()
    if service_type not in prices:
        prices[service_type] = {}
    prices[service_type][duration] = price
    save_json(PRICES_DB, prices)

def update_server_price(vps_id: str, service_type: str, duration: str, price: int):
    """Update harga untuk server tertentu"""
    server_prices = load_json(SERVER_PRICES_DB)
    
    if vps_id not in server_prices:
        server_prices[vps_id] = {}
    
    if service_type not in server_prices[vps_id]:
        server_prices[vps_id][service_type] = {}
    
    server_prices[vps_id][service_type][duration] = price
    save_json(SERVER_PRICES_DB, server_prices)

def add_transaction(transaction_data: Dict) -> str:
    """Tambahkan transaksi"""
    transactions = load_json(TRANSACTIONS_DB)
    tx_id = str(uuid.uuid4())[:8]
    transaction_data["id"] = tx_id
    transaction_data["created_at"] = datetime.now().isoformat()
    transactions[tx_id] = transaction_data
    save_json(TRANSACTIONS_DB, transactions)
    return tx_id

def add_order(order_data: Dict) -> str:
    """Tambahkan order"""
    orders = load_json(ORDERS_DB)
    order_id = str(uuid.uuid4())[:8]
    order_data["id"] = order_id
    order_data["created_at"] = datetime.now().isoformat()
    orders[order_id] = order_data
    save_json(ORDERS_DB, orders)
    return order_id

def get_order(order_id: str) -> Optional[Dict]:
    """Get order by ID"""
    orders = load_json(ORDERS_DB)
    return orders.get(order_id)

def update_order(order_id: str, updates: Dict):
    """Update order"""
    orders = load_json(ORDERS_DB)
    if order_id in orders:
        orders[order_id].update(updates)
        save_json(ORDERS_DB, orders)

def add_account(account_data: Dict) -> str:
    """Tambahkan akun VPN"""
    accounts = load_json(ACCOUNTS_DB)
    account_id = str(uuid.uuid4())[:8]
    account_data["id"] = account_id
    account_data["created_at"] = datetime.now().isoformat()
    accounts[account_id] = account_data
    save_json(ACCOUNTS_DB, accounts)
    return account_id

def get_account_by_username(username: str) -> Optional[Dict]:
    """Get account by username"""
    accounts = load_json(ACCOUNTS_DB)
    for acc_id, acc_data in accounts.items():
        if acc_data.get("username") == username:
            acc_data["id"] = acc_id
            return acc_data
    return None

def add_trial_account(account_data: Dict) -> str:
    """Tambahkan akun trial"""
    trials = load_json(TRIAL_ACCOUNTS_DB)
    trial_id = str(uuid.uuid4())[:8]
    account_data["id"] = trial_id
    account_data["created_at"] = datetime.now().isoformat()
    account_data["expires_at"] = (datetime.now() + timedelta(minutes=40)).isoformat()
    trials[trial_id] = account_data
    save_json(TRIAL_ACCOUNTS_DB, trials)
    return trial_id

def get_trial_account(trial_id: str) -> Optional[Dict]:
    """Get trial account by ID"""
    trials = load_json(TRIAL_ACCOUNTS_DB)
    return trials.get(trial_id)

def delete_trial_account(trial_id: str) -> bool:
    """Hapus akun trial"""
    trials = load_json(TRIAL_ACCOUNTS_DB)
    if trial_id in trials:
        del trials[trial_id]
        save_json(TRIAL_ACCOUNTS_DB, trials)
        return True
    return False


def save_json(file_path: str, data: Dict):
    """Simpan data ke file JSON"""
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving JSON to {file_path}: {e}")


async def admin_auto_reboot_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List semua auto reboot yang aktif"""
    query = update.callback_query
    await query.answer()
    
    auto_reboot_db = f"{DB_FOLDER}/auto_reboot.json"
    auto_reboot_data = load_json(auto_reboot_db)
    
    if not auto_reboot_data:
        text = f"""
{generate_header('AUTO REBOOT LIST')}

{generate_separator(29)}
📭 *Tidak Ada Auto Reboot Aktif*
{generate_separator(29)}
Belum ada jadwal auto reboot yang diset.
{generate_separator(29)}
"""
    else:
        text = f"""
{generate_header('AUTO REBOOT LIST')}

{generate_separator(29)}
⏰ *Total Jadwal:* {len(auto_reboot_data)}
{generate_separator(29)}
"""
        
        for vps_id, schedule in auto_reboot_data.items():
            vps = get_vps(vps_id)
            vps_name = vps.get('name', 'Unknown') if vps else 'Unknown'
            
            last_reboot = schedule.get('last_reboot')
            if last_reboot:
                last_reboot_text = format_datetime(last_reboot)
            else:
                last_reboot_text = "Belum pernah"
            
            text += f"""
🖥️ *{vps_name}* (`{vps_id}`)
├ Waktu: {schedule['time']}
├ Hari: {schedule['days_display']}
├ Status: {'🟢 Aktif' if schedule.get('status') == 'active' else '🔴 Nonaktif'}
├ Terakhir reboot: {last_reboot_text}
└ Set oleh: {schedule.get('set_by', 'N/A')}
"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Tambah Auto Reboot", callback_data="admin_auto_reboot")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)



# ============================================
# DECORATOR CHECK ADMIN
# ============================================

from functools import wraps
from typing import Callable, Any

def check_admin(func: Callable) -> Callable:
    """
    Decorator untuk mengecek apakah user adalah admin.
    Hanya user dengan ID yang terdaftar di ADMIN_IDS yang bisa mengakses.
    
    Usage:
    @check_admin
    async def admin_function(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # ... kode admin ...
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
        # Dapatkan user ID dari update
        if update.callback_query:
            user_id = update.callback_query.from_user.id
        elif update.message:
            user_id = update.message.from_user.id
        else:
            await update.effective_message.reply_text("❌ Tidak dapat mengidentifikasi user.")
            return ConversationHandler.END
        
        # Cek apakah user adalah admin
        if user_id not in ADMIN_IDS:
            # Tampilkan pesan error yang sesuai
            error_text = f"""
{generate_header('AKSES DITOLAK')}

{generate_separator(29)}
❌ *AKSES DITOLAK!*
{generate_separator(29)}
Anda tidak memiliki izin untuk mengakses fitur ini.
Fitur ini hanya tersedia untuk administrator.
{generate_separator(29)}
"""
            
            # Kirim pesan error
            if update.callback_query:
                await update.callback_query.answer("❌ Akses ditolak!", show_alert=True)
                await update.callback_query.edit_message_text(
                    error_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
                    ])
                )
            else:
                await update.message.reply_text(
                    error_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
                    ])
                )
            
            return ConversationHandler.END
        
        # Jika user adalah admin, jalankan fungsi asli
        return await func(update, context, *args, **kwargs)
    
    return wrapper

# ============================================
# DECORATOR CHECK ADMIN DENGAN LOGGING
# ============================================

def check_admin_with_log(func: Callable) -> Callable:
    """
    Decorator untuk mengecek admin dengan logging aktivitas.
    Mencatat siapa yang mengakses fungsi admin dan kapan.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
        # Dapatkan user ID dari update
        if update.callback_query:
            user_id = update.callback_query.from_user.id
            username = update.callback_query.from_user.username or "N/A"
            first_name = update.callback_query.from_user.first_name or "User"
        elif update.message:
            user_id = update.message.from_user.id
            username = update.message.from_user.username or "N/A"
            first_name = update.message.from_user.first_name or "User"
        else:
            await update.effective_message.reply_text("❌ Tidak dapat mengidentifikasi user.")
            return ConversationHandler.END
        
        # Log percobaan akses
        logging.info(f"User {user_id} ({username}) mencoba mengakses {func.__name__}")
        
        # Cek apakah user adalah admin
        if user_id not in ADMIN_IDS:
            # Log percobaan akses ilegal
            logging.warning(f"User {user_id} ({username}) ditolak mengakses {func.__name__}")
            
            # Kirim notifikasi ke admin (opsional)
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"⚠️ *PERINGATAN: Percobaan Akses Ilegal*\n\n"
                        f"User ID: `{user_id}`\n"
                        f"Username: @{username}\n"
                        f"Nama: {first_name}\n"
                        f"Fitur: {func.__name__}\n"
                        f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
            
            # Tampilkan pesan error ke user
            error_text = f"""
{generate_header('⛔ AKSES DITOLAK')}

{generate_separator(29)}
🚫 *AKSES DITOLAK!*
{generate_separator(29)}
Anda tidak memiliki izin untuk mengakses fitur admin.
{generate_separator(29)}
📋 *Detail:*
├ User ID: `{user_id}`
├ Username: @{username or 'N/A'}
├ Nama: {first_name}
├ Fitur: {func.__name__}
└ Waktu: {datetime.now().strftime('%H:%M:%S')}
{generate_separator(29)}
⚠️ *Percobaan akses ilegal telah dicatat.*
{generate_separator(29)}
"""
            
            if update.callback_query:
                await update.callback_query.answer("⛔ Akses ditolak!", show_alert=True)
                await update.callback_query.edit_message_text(
                    error_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
                    ])
                )
            else:
                await update.message.reply_text(
                    error_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
                    ])
                )
            
            return ConversationHandler.END
        
        # Log akses sukses admin
        logging.info(f"Admin {user_id} ({username}) mengakses {func.__name__}")
        
        # Jalankan fungsi asli untuk admin
        try:
            result = await func(update, context, *args, **kwargs)
            return result
        except Exception as e:
            # Log error jika terjadi
            logging.error(f"Error saat admin {user_id} menjalankan {func.__name__}: {e}")
            raise
    
    return wrapper

async def cleanup_expired_accounts():
    """Hapus akun reguler yang sudah expired"""
    accounts = load_json(ACCOUNTS_DB)
    now = datetime.now()
    expired_count = 0
    
    for account_id, account_data in list(accounts.items()):
        try:
            expires_at = account_data.get("expires_at")
            if expires_at:
                exp_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                
                if exp_date < now:
                    print(f"[CLEANUP] Menghapus expired account {account_data.get('username', 'N/A')}")
                    
                    # Hapus dari server
                    success = await delete_account_from_server(account_data)
                    if success:
                        print(f"[CLEANUP] Berhasil hapus expired account dari server")
                    
                    # Hapus dari database
                    del accounts[account_id]
                    expired_count += 1
                    
        except Exception as e:
            print(f"[CLEANUP ERROR] Account {account_id}: {e}")
            continue
    
    if expired_count > 0:
        save_json(ACCOUNTS_DB, accounts)
        print(f"[CLEANUP] {expired_count} expired account dihapus")
    
    return expired_count
                    
async def delete_zivpn_account(vps: Dict, username: str, password: str) -> bool:
    """Hapus akun ZiVPN dari server dengan script yang benar"""
    
    command = f"""
#!/bin/bash
CONFIG_FILE="/etc/zivpn/config.json"
USER_DB="/etc/zivpn/users.json"

echo "Deleting ZiVPN account: {username}"

# 1. Hapus password dari config.json menggunakan Python
python3 -c "
import json
import os

config_file = '{CONFIG_FILE}'
password_to_remove = '{password}'

try:
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Hapus password dari auth.config
        if 'auth' in config and 'config' in config['auth']:
            config['auth']['config'] = [p for p in config['auth']['config'] if p != password_to_remove]
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print('PASSWORD_REMOVED_FROM_CONFIG')
    else:
        print('CONFIG_FILE_NOT_FOUND')
except Exception as e:
    print(f'ERROR_CONFIG: {{str(e)}}')
"

# 2. Hapus user dari users.json
python3 -c "
import json
import os

user_db = '{USER_DB}'
username_to_remove = '{username}'

try:
    if os.path.exists(user_db):
        with open(user_db, 'r') as f:
            users_data = json.load(f)
        
        if 'users' in users_data and username_to_remove in users_data['users']:
            del users_data['users'][username_to_remove]
            
            with open(user_db, 'w') as f:
                json.dump(users_data, f, indent=2)
            
            print('USER_REMOVED_FROM_DB')
        else:
            print('USER_NOT_FOUND_IN_DB')
    else:
        print('USER_DB_NOT_FOUND')
except Exception as e:
    print(f'ERROR_DB: {{str(e)}}')
"

# 3. Hapus file detail
rm -f /detail/zivpn/{username}.txt 2>/dev/null || true
rm -f /var/www/html/zivpn-{username}.txt 2>/dev/null || true

# 4. Restart service
systemctl restart zivpn 2>/dev/null || true

echo "ZIVPN_DELETE_COMPLETED"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    return success and ("ZIVPN_DELETE_COMPLETED" in output or "USER_REMOVED_FROM_DB" in output)


async def delete_account_from_server(account_data: Dict) -> bool:
    """Hapus akun dari server SSH - VERSI DIPERBAIKI"""
    try:
        vps_id = account_data.get("vps_id")
        vps = get_vps(vps_id)
        if not vps:
            print(f"[DELETE] VPS {vps_id} tidak ditemukan")
            return False
        
        service_type = account_data.get("service_type", "").lower()
        username = account_data.get("username", "")
        
        print(f"[DELETE] Menghapus akun {username} ({service_type}) dari {vps.get('name', 'N/A')}")
        
        if service_type == "ssh":
            command = f"""
#!/bin/bash
# Hapus SSH account
echo "Deleting SSH account: {username}"

# 1. Nonaktifkan akun terlebih dahulu
passwd -l {username} 2>/dev/null || true

# 2. Hapus user dari sistem
userdel -r {username} 2>/dev/null || true

# 3. Hapus file-file terkait
rm -f /etc/ssh/{username} 2>/dev/null || true
rm -f /etc/limit/ssh/ip/{username} 2>/dev/null || true
rm -f /detail/ssh/{username}.txt 2>/dev/null || true
rm -f /var/www/html/ssh-{username}.txt 2>/dev/null || true

# 4. Hapus dari database
sed -i '/#ssh# {username} /d' /etc/ssh/.ssh.db 2>/dev/null || true

echo "SSH_DELETE_COMPLETED"
"""
        
        elif service_type == "zivpn":
            password = account_data.get("password", "")
            return await delete_zivpn_account(vps, username, password)
        
        elif service_type in ["vmess", "vless", "trojan", "ss"]:
            # Tentukan pattern berdasarkan service
            if service_type == "vmess":
                pattern = "###"
            elif service_type == "vless":
                pattern = "#&"
            elif service_type == "trojan":
                pattern = "#!"
            elif service_type == "ss":
                pattern = "#@&"
            else:
                pattern = "#"
            
            command = f"""
#!/bin/bash
# Hapus {service_type} account
echo "Deleting {service_type} account: {username}"

# 1. Backup config.json
TIMESTAMP=$(date +%s)
cp /etc/xray/config.json /etc/xray/config.json.backup_$TIMESTAMP 2>/dev/null || true

# 2. Hapus dari config.json
sed -i '/{pattern} {username} /d' /etc/xray/config.json 2>/dev/null || true
sed -i '/"email": "{username}"/d' /etc/xray/config.json 2>/dev/null || true

# 3. Perbaiki format JSON (hapus koma berlebih)
python3 -c "
import json
import re

try:
    with open('/etc/xray/config.json', 'r') as f:
        content = f.read()
    
    # Perbaiki JSON
    content = re.sub(r',\\s*}}', '}}', content)
    content = re.sub(r',\\s*]', ']', content)
    content = re.sub(r'}},\\s*{{', '}},{{', content)
    
    with open('/etc/xray/config.json', 'w') as f:
        f.write(content)
    
    print('JSON_FORMAT_FIXED')
except Exception as e:
    print(f'JSON_ERROR: {{e}}')
"

# 4. Hapus file-file terkait
rm -f /etc/limit/{service_type}/ip/{username} 2>/dev/null || true
rm -f /etc/{service_type}/{username} 2>/dev/null || true
rm -f /detail/{service_type}/{username}.txt 2>/dev/null || true
rm -f /var/www/html/{service_type}-{username}.txt 2>/dev/null || true

# 5. Hapus dari database
DB_FILE="/etc/{service_type}/.{service_type}.db"
if [ -f "$DB_FILE" ]; then
    sed -i '/{username} /d' "$DB_FILE" 2>/dev/null || true
fi

echo "{service_type.upper()}_DELETE_COMPLETED"
"""
        
        else:
            print(f"[DELETE] Service type tidak didukung: {service_type}")
            return False
        
        # Eksekusi command untuk layanan selain ZiVPN
        success, output = await execute_ssh_command(
            vps["ip"],
            vps.get("ssh_port", 22),
            vps["ssh_user"],
            vps["ssh_pass"],
            command
        )
        
        # Restart service jika perlu
        if service_type in ["vmess", "vless", "trojan", "ss"]:
            restart_cmd = "systemctl restart xray >/dev/null 2>&1 || true"
            await execute_ssh_command(
                vps["ip"],
                vps.get("ssh_port", 22),
                vps["ssh_user"],
                vps["ssh_pass"],
                restart_cmd
            )
        
        if success and ("_DELETE_COMPLETED" in output or "deleted" in output.lower()):
            print(f"[DELETE] Berhasil menghapus {service_type} account: {username}")
            return True
        else:
            print(f"[DELETE] Gagal menghapus {service_type} account: {username}")
            print(f"[DELETE] Output: {output[:200]}")
            return False
        
    except Exception as e:
        print(f"[DELETE ERROR] {str(e)}")
        return False
        
@check_admin
async def admin_delete_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses hapus akun (admin)"""
    query = update.callback_query
    await query.answer()
    
    text = f"""
{generate_header('HAPUS AKUN VPN')}

{generate_separator(29)}
⚠️ *HAPUS AKUN VPN*
{generate_separator(29)}
🔍 *Pilih metode pencarian:*
"""
    
    keyboard = [
        [InlineKeyboardButton("🔍 Search by Username", callback_data="delete_search_username")],
        [InlineKeyboardButton("👤 Search by User ID", callback_data="delete_search_userid")],
        [InlineKeyboardButton("📅 Search Expired Accounts", callback_data="delete_search_expired")],
        [InlineKeyboardButton("🎯 Delete Trial Accounts", callback_data="delete_all_trials")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def admin_delete_search_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pencarian berdasarkan username"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"""
{generate_header('HAPUS AKUN - CARI USERNAME')}

{generate_separator(29)}
🔍 *Cari Berdasarkan Username*
{generate_separator(29)}
Masukkan username yang ingin dihapus:
"""
    )
    
    context.user_data["delete_search_type"] = "username"
    return "DELETE_SEARCH_INPUT"


async def admin_delete_search_userid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pencarian berdasarkan User ID"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"""
{generate_header('HAPUS AKUN - CARI USER ID')}

{generate_separator(29)}
👤 *Cari Berdasarkan User ID*
{generate_separator(29)}
Masukkan User ID pemilik akun:
"""
    )
    
    context.user_data["delete_search_type"] = "userid"
    return "DELETE_SEARCH_INPUT"


async def admin_delete_search_expired(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pencarian akun expired"""
    query = update.callback_query
    await query.answer()
    
    processing_msg = await query.edit_message_text(
        f"""
{generate_header('MENCARI AKUN EXPIRED')}

{generate_separator(29)}
⏳ *Mencari akun yang sudah expired...*
{generate_separator(29)}
Harap tunggu sebentar.
{generate_separator(29)}
"""
    )
    
    # Cari akun expired
    accounts = load_json(ACCOUNTS_DB)
    now = datetime.now()
    expired_accounts = []
    
    for account_id, account_data in accounts.items():
        try:
            expires_at = account_data.get("expires_at")
            if expires_at:
                exp_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if exp_date < now:
                    expired_accounts.append((account_id, account_data))
        except:
            continue
    
    if not expired_accounts:
        await processing_msg.edit_text(
            f"""
{generate_header('AKUN EXPIRED')}

{generate_separator(29)}
✅ *Tidak ada akun yang expired*
{generate_separator(29)}
Semua akun masih aktif atau sudah dibersihkan.
{generate_separator(29)}
"""
        )
        return ConversationHandler.END
    
    context.user_data["expired_accounts"] = expired_accounts
    
    text = f"""
{generate_header('AKUN EXPIRED DITEMUKAN')}

{generate_separator(29)}
📋 *{len(expired_accounts)} Akun Expired Ditemukan*
{generate_separator(29)}
"""
    
    keyboard = []
    for i, (account_id, account_data) in enumerate(expired_accounts[:10], 1):  # Max 10
        username = account_data.get("username", "N/A")
        service = account_data.get("service_type", "N/A").upper()
        expired = format_datetime(account_data.get("expires_at", ""))
        vps = get_vps(account_data.get("vps_id", ""))
        vps_name = vps.get("name", "N/A") if vps else "N/A"
        
        text += f"""
{i}. `{username}` ({service})
├ Server: {vps_name}
├ Expired: {expired}
└ ID: `{account_id[:8]}...`
"""
        
        keyboard.append([
            InlineKeyboardButton(f"🗑️ Hapus {username}", callback_data=f"delete_expired_{account_id}")
        ])
    
    if len(expired_accounts) > 10:
        text += f"\n📝 ... dan {len(expired_accounts) - 10} akun expired lainnya."
        keyboard.append([
            InlineKeyboardButton("🗑️ Hapus Semua Expired", callback_data="delete_all_expired")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="admin_delete_account")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await processing_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return "DELETE_CONFIRM"


async def admin_delete_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input pencarian"""
    search_input = update.message.text.strip()
    search_type = context.user_data.get("delete_search_type", "username")
    
    processing_msg = await update.message.reply_text(
        f"""
{generate_header('MENCARI AKUN')}

{generate_separator(29)}
🔍 *Mencari akun...*
{generate_separator(29)}
Harap tunggu sebentar.
{generate_separator(29)}
"""
    )
    
    found_accounts = []
    
    if search_type == "username":
        # Cari berdasarkan username di semua database
        username = search_input
        
        # Cari di accounts database
        accounts = load_json(ACCOUNTS_DB)
        for account_id, account_data in accounts.items():
            if account_data.get("username") == username:
                found_accounts.append(("regular", account_id, account_data))
        
        # Cari di trial accounts
        trials = load_json(TRIAL_ACCOUNTS_DB)
        for trial_id, trial_data in trials.items():
            if trial_data.get("username") == username:
                found_accounts.append(("trial", trial_id, trial_data))
    
    elif search_type == "userid":
        # Cari berdasarkan user_id
        try:
            user_id = int(search_input)
            
            # Cari di accounts database
            accounts = load_json(ACCOUNTS_DB)
            for account_id, account_data in accounts.items():
                if account_data.get("user_id") == user_id:
                    found_accounts.append(("regular", account_id, account_data))
            
            # Cari di trial accounts
            trials = load_json(TRIAL_ACCOUNTS_DB)
            for trial_id, trial_data in trials.items():
                if trial_data.get("user_id") == user_id:
                    found_accounts.append(("trial", trial_id, trial_data))
                    
        except ValueError:
            await processing_msg.edit_text("❌ User ID harus angka.")
            return ConversationHandler.END
    
    if not found_accounts:
        await processing_msg.edit_text(
            f"""
{generate_header('AKUN TIDAK DITEMUKAN')}

{generate_separator(29)}
❌ *Akun tidak ditemukan*
{generate_separator(29)}
Tidak ada akun yang sesuai dengan pencarian.
{generate_separator(29)}
"""
        )
        return ConversationHandler.END
    
    context.user_data["found_accounts"] = found_accounts
    
    text = f"""
{generate_header('AKUN DITEMUKAN')}

{generate_separator(29)}
✅ *{len(found_accounts)} Akun Ditemukan*
{generate_separator(29)}
"""
    
    keyboard = []
    for i, (acc_type, acc_id, acc_data) in enumerate(found_accounts[:10], 1):
        username = acc_data.get("username", "N/A")
        service = acc_data.get("service_type", "N/A").upper()
        expires = format_datetime(acc_data.get("expires_at", ""))
        acc_type_display = "🎯 TRIAL" if acc_type == "trial" else "✅ REGULAR"
        
        text += f"""
{i}. `{username}` ({service}) {acc_type_display}
├ Expired: {expires}
└ ID: `{acc_id[:8]}...`
"""
        
        keyboard.append([
            InlineKeyboardButton(f"🗑️ Hapus {username}", callback_data=f"delete_account_{acc_type}_{acc_id}")
        ])
    
    if len(found_accounts) > 10:
        text += f"\n📝 ... dan {len(found_accounts) - 10} akun lainnya."
        keyboard.append([
            InlineKeyboardButton(f"🗑️ Hapus Semua ({len(found_accounts)} akun)", callback_data="delete_all_found")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="admin_delete_account")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await processing_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return "DELETE_CONFIRM"


async def admin_delete_account_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi penghapusan akun"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "delete_all_trials":
        # Hapus semua trial accounts
        text = f"""
{generate_header('HAPUS SEMUA TRIAL')}

{generate_separator(29)}
⚠️ *KONFIRMASI HAPUS SEMUA AKUN TRIAL*
{generate_separator(29)}
Anda akan menghapus **SEMUA** akun trial.
{generate_separator(29)}
✅ *Aksi ini akan:*
├ Hapus dari semua server
├ Hapus dari database trial
├ Tidak bisa dikembalikan
└ Membersihkan sistem
{generate_separator(29)}
🗑️ **Konfirmasi hapus semua trial?**
"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ HAPUS SEMUA TRIAL", callback_data="confirm_delete_all_trials"),
                InlineKeyboardButton("❌ BATALKAN", callback_data="admin_delete_account")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return "DELETE_EXECUTE"
    
    elif data.startswith("delete_account_"):
        # Hapus akun spesifik
        parts = data.split("_")
        acc_type = parts[2]  # regular atau trial
        acc_id = parts[3]
        
        if acc_type == "regular":
            accounts = load_json(ACCOUNTS_DB)
            acc_data = accounts.get(acc_id)
            db_name = "Akun Reguler"
        else:
            accounts = load_json(TRIAL_ACCOUNTS_DB)
            acc_data = accounts.get(acc_id)
            db_name = "Akun Trial"
        
        if not acc_data:
            await query.answer("❌ Akun tidak ditemukan", show_alert=True)
            return ConversationHandler.END
        
        username = acc_data.get("username", "N/A")
        service = acc_data.get("service_type", "N/A").upper()
        expires = format_datetime(acc_data.get("expires_at", ""))
        vps = get_vps(acc_data.get("vps_id", ""))
        vps_name = vps.get("name", "N/A") if vps else "N/A"
        
        text = f"""
{generate_header('KONFIRMASI HAPUS AKUN')}

{generate_separator(29)}
⚠️ *KONFIRMASI HAPUS AKUN*
{generate_separator(29)}
📋 *Detail Akun:*
├ Username: `{username}`
├ Service: {service}
├ Type: {db_name}
├ Server: {vps_name}
├ Expired: {expires}
└ ID: `{acc_id[:8]}...`
{generate_separator(29)}
✅ *Aksi ini akan:*
├ Hapus dari server VPS
├ Hapus dari database {db_name}
├ Tidak bisa dikembalikan
└ Informasikan ke pemilik (jika ada)
{generate_separator(29)}
🗑️ **Konfirmasi hapus akun ini?**
"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ HAPUS AKUN", callback_data=f"confirm_delete_{acc_type}_{acc_id}"),
                InlineKeyboardButton("❌ BATALKAN", callback_data="admin_delete_account")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return "DELETE_EXECUTE"
    
    elif data.startswith("delete_expired_"):
        # Hapus akun expired spesifik
        account_id = data.replace("delete_expired_", "")
        accounts = load_json(ACCOUNTS_DB)
        acc_data = accounts.get(account_id)
        
        if not acc_data:
            await query.answer("❌ Akun tidak ditemukan", show_alert=True)
            return ConversationHandler.END
        
        username = acc_data.get("username", "N/A")
        service = acc_data.get("service_type", "N/A").upper()
        expires = format_datetime(acc_data.get("expires_at", ""))
        
        text = f"""
{generate_header('KONFIRMASI HAPUS EXPIRED')}

{generate_separator(29)}
⚠️ *KONFIRMASI HAPUS AKUN EXPIRED*
{generate_separator(29)}
📋 *Detail Akun:*
├ Username: `{username}`
├ Service: {service}
├ Status: ⏰ **EXPIRED**
├ Expired: {expires}
└ ID: `{account_id[:8]}...`
{generate_separator(29)}
✅ *Aksi ini akan:*
├ Hapus dari server VPS
├ Hapus dari database
├ Membersihkan sistem
└ Tidak bisa dikembalikan
{generate_separator(29)}
🗑️ **Konfirmasi hapus akun expired ini?**
"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ HAPUS EXPIRED", callback_data=f"confirm_delete_expired_{account_id}"),
                InlineKeyboardButton("❌ BATALKAN", callback_data="delete_search_expired")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return "DELETE_EXECUTE"
    
    elif data == "delete_all_expired":
        # Hapus semua expired
        expired_accounts = context.user_data.get("expired_accounts", [])
        
        text = f"""
{generate_header('HAPUS SEMUA EXPIRED')}

{generate_separator(29)}
⚠️ *KONFIRMASI HAPUS SEMUA AKUN EXPIRED*
{generate_separator(29)}
Anda akan menghapus **{len(expired_accounts)}** akun expired.
{generate_separator(29)}
✅ *Aksi ini akan:*
├ Hapus dari semua server
├ Hapus dari database
├ Membersihkan sistem
├ Tidak bisa dikembalikan
└ Proses batch mungkin lama
{generate_separator(29)}
🗑️ **Konfirmasi hapus semua akun expired?**
"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ HAPUS SEMUA EXPIRED", callback_data="confirm_delete_all_expired"),
                InlineKeyboardButton("❌ BATALKAN", callback_data="delete_search_expired")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return "DELETE_EXECUTE"


async def admin_delete_account_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eksekusi penghapusan akun"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    admin_id = query.from_user.id
    
    processing_msg = await query.edit_message_text(
        f"""
{generate_header('MEMPROSES PENGHAPUSAN')}

{generate_separator(29)}
⏳ *Memproses penghapusan...*
{generate_separator(29)}
Harap tunggu, proses mungkin memakan waktu beberapa detik.
{generate_separator(29)}
"""
    )
    
    deleted_count = 0
    error_count = 0
    details = []
    
    try:
        if data == "confirm_delete_all_trials":
            # Hapus semua trial accounts
            trials = load_json(TRIAL_ACCOUNTS_DB)
            
            for trial_id, trial_data in list(trials.items()):
                try:
                    # Hapus dari server
                    success = await delete_account_from_server(trial_data)
                    if success:
                        # Hapus dari database
                        del trials[trial_id]
                        deleted_count += 1
                        details.append(f"✅ {trial_data.get('username', 'N/A')} - {trial_data.get('service_type', 'N/A')}")
                    else:
                        error_count += 1
                        details.append(f"❌ {trial_data.get('username', 'N/A')} - Gagal hapus dari server")
                except Exception as e:
                    error_count += 1
                    details.append(f"❌ ERROR: {str(e)[:50]}")
            
            if deleted_count > 0:
                save_json(TRIAL_ACCOUNTS_DB, trials)
            
            result_text = f"🗑️ *Semua Trial Accounts Dihapus:* {deleted_count} berhasil, {error_count} gagal"
            
        elif data.startswith("confirm_delete_"):
            # Hapus akun spesifik
            parts = data.split("_")
            acc_type = parts[2]  # regular atau trial
            acc_id = parts[3]
            
            if acc_type == "regular":
                accounts = load_json(ACCOUNTS_DB)
                acc_data = accounts.get(acc_id)
                db_file = ACCOUNTS_DB
                user_field = "user_id"
            else:
                accounts = load_json(TRIAL_ACCOUNTS_DB)
                acc_data = accounts.get(acc_id)
                db_file = TRIAL_ACCOUNTS_DB
                user_field = "user_id"
            
            if acc_data:
                username = acc_data.get("username", "N/A")
                service = acc_data.get("service_type", "N/A")
                
                # Hapus dari server
                success = await delete_account_from_server(acc_data)
                
                if success:
                    # Hapus dari database
                    del accounts[acc_id]
                    save_json(db_file, accounts)
                    deleted_count = 1
                    
                    # Hapus dari user accounts jika ada
                    user_id = acc_data.get(user_field)
                    if user_id:
                        user = get_user(user_id)
                        if user and "vpn_accounts" in user:
                            user["vpn_accounts"] = [acc for acc in user["vpn_accounts"] 
                                                   if acc.get("username") != username]
                            update_user(user_id, {"vpn_accounts": user["vpn_accounts"]})
                    
                    details.append(f"✅ {username} ({service}) - Berhasil dihapus")
                    
                    # Kirim notifikasi ke user jika ada
                    try:
                        await context.bot.send_message(
                            user_id,
                            f"""
{generate_header('AKUN DIHAPUS')}

{generate_separator(29)}
🗑️ *Akun Anda Telah Dihapus*
{generate_separator(29)}
📋 *Detail:*
├ Username: `{username}`
├ Service: {service.upper()}
├ Dihapus oleh: Admin
├ Alasan: Permintaan admin
└ Waktu: {datetime.now().strftime('%d/%m/%Y %H:%M')}
{generate_separator(29)}
💡 *Jika ini kesalahan, hubungi admin.*
{generate_separator(29)}
"""
                        )
                    except:
                        pass
                else:
                    error_count = 1
                    details.append(f"❌ {username} ({service}) - Gagal hapus dari server")
            
            result_text = f"🗑️ *Akun Dihapus:* {deleted_count} berhasil, {error_count} gagal"
        
        elif data.startswith("confirm_delete_expired_"):
            # Hapus expired spesifik
            account_id = data.replace("confirm_delete_expired_", "")
            accounts = load_json(ACCOUNTS_DB)
            acc_data = accounts.get(account_id)
            
            if acc_data:
                username = acc_data.get("username", "N/A")
                service = acc_data.get("service_type", "N/A")
                
                # Hapus dari server
                success = await delete_account_from_server(acc_data)
                
                if success:
                    # Hapus dari database
                    del accounts[account_id]
                    save_json(ACCOUNTS_DB, accounts)
                    deleted_count = 1
                    details.append(f"✅ {username} ({service}) - Expired dihapus")
                else:
                    error_count = 1
                    details.append(f"❌ {username} ({service}) - Gagal hapus expired")
            
            result_text = f"🗑️ *Expired Account Dihapus:* {deleted_count} berhasil, {error_count} gagal"
        
        elif data == "confirm_delete_all_expired":
            # Hapus semua expired accounts
            expired_accounts = context.user_data.get("expired_accounts", [])
            accounts = load_json(ACCOUNTS_DB)
            
            for account_id, acc_data in expired_accounts:
                try:
                    username = acc_data.get("username", "N/A")
                    service = acc_data.get("service_type", "N/A")
                    
                    # Hapus dari server
                    success = await delete_account_from_server(acc_data)
                    
                    if success:
                        # Hapus dari database
                        del accounts[account_id]
                        deleted_count += 1
                        details.append(f"✅ {username} ({service}) - Expired dihapus")
                    else:
                        error_count += 1
                        details.append(f"❌ {username} ({service}) - Gagal hapus")
                        
                except Exception as e:
                    error_count += 1
                    details.append(f"❌ ERROR: {str(e)[:50]}")
            
            if deleted_count > 0:
                save_json(ACCOUNTS_DB, accounts)
            
            result_text = f"🗑️ *Semua Expired Dihapus:* {deleted_count} berhasil, {error_count} gagal"
        
        else:
            result_text = "❌ Perintah tidak dikenali"
        
        # Buat laporan
        report = f"""
{generate_header('LAPORAN PENGHAPUSAN')}

{generate_separator(29)}
{result_text}
{generate_separator(29)}
📋 *Detail Penghapusan:*
"""
        
        for detail in details[:10]:  # Tampilkan max 10 detail
            report += f"├ {detail}\n"
        
        if len(details) > 10:
            report += f"├ ... dan {len(details) - 10} lainnya\n"
        
        report += f"""
{generate_separator(29)}
👤 *Admin:* {admin_id}
⏰ *Waktu:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
{generate_separator(29)}
"""
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Hapus Lainnya", callback_data="admin_delete_account")],
            [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(report, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        
    except Exception as e:
        error_text = f"""
{generate_header('ERROR PENGHAPUSAN')}

{generate_separator(29)}
❌ *Terjadi Error Saat Penghapusan*
{generate_separator(29)}
📛 *Error Details:*
`{str(e)[:200]}`
{generate_separator(29)}
"""
        await processing_msg.edit_text(error_text, parse_mode=ParseMode.MARKDOWN)
    
    return ConversationHandler.END
                           

async def cleanup_expired_trials():
    """Hapus akun trial yang sudah expired dengan script yang benar"""
    trials = load_json(TRIAL_ACCOUNTS_DB)
    now = datetime.now()
    expired_count = 0
    
    for trial_id, trial_data in list(trials.items()):
        try:
            expires_at = trial_data.get("expires_at")
            if expires_at:
                exp_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                
                if exp_date < now:
                    print(f"[CLEANUP] Menghapus trial account {trial_data.get('username', 'N/A')}")
                    
                    # Hapus dari server
                    success = await delete_account_from_server(trial_data)
                    if success:
                        print(f"[CLEANUP] Berhasil hapus dari server")
                    else:
                        print(f"[CLEANUP] Gagal hapus dari server, lanjut hapus dari database")
                    
                    # Hapus dari database
                    del trials[trial_id]
                    expired_count += 1
                    
        except Exception as e:
            print(f"[CLEANUP ERROR] Trial {trial_id}: {e}")
            continue
    
    if expired_count > 0:
        save_json(TRIAL_ACCOUNTS_DB, trials)
        print(f"[CLEANUP] {expired_count} trial account dihapus")
    
    return expired_count

                    
async def update_account_on_server_extended(vps: Dict, account: Dict, upgrade_type: str, days: int = None, extra_ips: int = None, new_quota: int = None) -> Tuple[bool, str]:
    """Update akun di server SSH dengan script yang lengkap"""
    try:
        service_type = account.get("service_type")
        username = account.get("username")
        domain = vps.get("domain", "super.oxygencrc.my.id")
        
        if upgrade_type == "extend":
            if service_type == "ssh":
                # Gunakan script SSH yang lengkap
                command = f"""
#!/bin/bash
USERNAME="{username}"
DAYS="{days}"
QUOTA="{new_quota or account.get('quota', 2)}"
IP_LIMIT="{account.get('ip_limit', 2)}"

# Update Expiration
TODAY=$(date +%s)
EXTEND_SECONDS=$((DAYS * 86400))
EXPIRY_DATE=$(($TODAY + $EXTEND_SECONDS))
FORMATTED_EXPIRY=$(date -u --date="1970-01-01 $EXPIRY_DATE sec GMT" +%Y/%m/%d)
EXPIRY_DISPLAY=$(date -u --date="1970-01-01 $EXPIRY_DATE sec GMT" '+%d %b %Y')
passwd -u $USERNAME
usermod -e $FORMATTED_EXPIRY $USERNAME

# Update Quota
mkdir -p /etc/ssh
QUOTA_BYTES=$(($QUOTA * 1024 * 1024 * 1024))
echo $QUOTA_BYTES > /etc/ssh/$USERNAME

# Update IP Limit
mkdir -p /etc/limit/ssh/ip
echo $IP_LIMIT > /etc/limit/ssh/ip/$USERNAME

# Update database SSH
sed -i "s|#ssh# $USERNAME .*|#ssh# $USERNAME $(grep '#ssh# $USERNAME' /etc/ssh/.ssh.db | cut -d' ' -f3-4) $IP_LIMIT $EXPIRY_DISPLAY|" /etc/ssh/.ssh.db

echo "SUCCESS: SSH Account extended for $USERNAME"
echo "Days Extended : $DAYS Days"
echo "Expires on    : $EXPIRY_DISPLAY"
echo "New Quota     : $QUOTA GB"
echo "New IP Limit  : $IP_LIMIT IP"
"""
            
            elif service_type == "vmess":
                command = f"""
#!/bin/bash
user="{username}"
masaaktif="{days}"
Quota="{new_quota or account.get('quota', 200)}"
iplim="{account.get('ip_limit', 2)}"

# Remove old limits
rm -f /etc/limit/vmess/ip/${{user}}
rm -f /etc/vmess/${{user}}

# Get current expiry
exp=$(grep -wE "^### {username}" "/etc/xray/config.json" | cut -d ' ' -f 3 | sort | uniq)

# Setup limit
mkdir -p /etc/limit/vmess/ip
echo ${{iplim}} > /etc/limit/vmess/ip/${{user}}

# Setup quota
if [ ! -e /etc/vmess/ ]; then
  mkdir -p /etc/vmess/
fi

if [ -z ${{Quota}} ]; then
  Quota="0"
fi

c=$(echo "${{Quota}}" | sed 's/[^0-9]*//g')
d=$((${{c}} * 1024 * 1024 * 1024))

if [[ ${{c}} != "0" ]]; then
  echo "${{d}}" >/etc/vmess/${{user}}
fi

# Calculate new expiry
now=$(date +%Y-%m-%d)
d1=$(date -d "$exp" +%s)
d2=$(date -d "$now" +%s)
exp2=$(( (d1 - d2) / 86400 ))
exp3=$(($exp2 + ${{masaaktif}}))
exp4=`date -d "${{exp3}} days" +"%Y-%m-%d"`

# Update config
sed -i "/### {username}/c\\### {username} $exp4" /etc/xray/config.json
sed -i "/### {username}/c\\### {username} $exp4" /etc/vmess/.vmess.db

# Restart service
systemctl restart xray > /dev/null 2>&1

echo "SUCCESS: VMess Account renewed for {username}"
echo "Expired On  : $exp4"
echo "User Quota  : ${{Quota}} GB"
echo "User Limit IP: ${{iplim}} IP"
"""
            
            elif service_type == "vless":
                command = f"""
#!/bin/bash
user="{username}"
masaaktif="{days}"
Quota="{new_quota or account.get('quota', 200)}"
iplim="{account.get('ip_limit', 2)}"

# Remove old limits
rm -f /etc/limit/vless/ip/${{user}}
rm -f /etc/vless/${{user}}

# Get current expiry
exp=$(grep -wE "^#& {username}" "/etc/xray/config.json" | cut -d ' ' -f 3 | sort | uniq)

# Setup limit
mkdir -p /etc/limit/vless/ip
echo ${{iplim}} > /etc/limit/vless/ip/${{user}}

# Setup quota
if [ ! -e /etc/vless/ ]; then
  mkdir -p /etc/vless/
fi

if [ -z ${{Quota}} ]; then
  Quota="0"
fi

c=$(echo "${{Quota}}" | sed 's/[^0-9]*//g')
d=$((${{c}} * 1024 * 1024 * 1024))

if [[ ${{c}} != "0" ]]; then
  echo "${{d}}" >/etc/vless/${{user}}
fi

# Calculate new expiry
now=$(date +%Y-%m-%d)
d1=$(date -d "$exp" +%s)
d2=$(date -d "$now" +%s)
exp2=$(( (d1 - d2) / 86400 ))
exp3=$(($exp2 + ${{masaaktif}}))
exp4=`date -d "${{exp3}} days" +"%Y-%m-%d"`

# Update config
sed -i "/#& {username}/c\\#& {username} $exp4" /etc/xray/config.json
sed -i "/#& {username}/c\\#& {username} $exp4" /etc/vless/.vless.db

# Restart service
systemctl restart xray > /dev/null 2>&1

echo "SUCCESS: VLESS Account renewed for {username}"
echo "Expired On  : $exp4"
echo "User Quota  : ${{Quota}} GB"
echo "User Limit IP: ${{iplim}} IP"
"""
            
            elif service_type == "trojan":
                command = f"""
#!/bin/bash
user="{username}"
masaaktif="{days}"
Quota="{new_quota or account.get('quota', 200)}"
iplim="{account.get('ip_limit', 2)}"

# Remove old limits
rm -f /etc/limit/trojan/ip/${{user}}
rm -f /etc/trojan/${{user}}

# Get current expiry
exp=$(grep -wE "^#! {username}" "/etc/xray/config.json" | cut -d ' ' -f 3 | sort | uniq)

# Setup limit
mkdir -p /etc/limit/trojan/ip
echo ${{iplim}} > /etc/limit/trojan/ip/${{user}}

# Setup quota
if [ ! -e /etc/trojan/ ]; then
  mkdir -p /etc/trojan/
fi

if [ -z ${{Quota}} ]; then
  Quota="0"
fi

c=$(echo "${{Quota}}" | sed 's/[^0-9]*//g')
d=$((${{c}} * 1024 * 1024 * 1024))

if [[ ${{c}} != "0" ]]; then
  echo "${{d}}" >/etc/trojan/${{user}}
fi

# Calculate new expiry
now=$(date +%Y-%m-%d)
d1=$(date -d "$exp" +%s)
d2=$(date -d "$now" +%s)
exp2=$(( (d1 - d2) / 86400 ))
exp3=$(($exp2 + ${{masaaktif}}))
exp4=`date -d "${{exp3}} days" +"%Y-%m-%d"`

# Update config
sed -i "/#! {username}/c\\#! {username} $exp4" /etc/xray/config.json
sed -i "/#! {username}/c\\#! {username} $exp4" /etc/trojan/.trojan.db

# Restart service
systemctl restart xray > /dev/null 2>&1

echo "SUCCESS: Trojan Account renewed for {username}"
echo "Expired On  : $exp4"
echo "User Quota  : ${{Quota}} GB"
echo "User Limit IP: ${{iplim}} IP"
"""
            
            elif service_type == "ss":
                command = f"""
#!/bin/bash
user="{username}"
masaaktif="{days}"
Quota="{new_quota or account.get('quota', 200)}"
iplim="{account.get('ip_limit', 2)}"

# Remove old limits
rm -f /etc/limit/shadowsocks/ip/${{user}}
rm -f /etc/shadowsocks/${{user}}

# Get current expiry
exp=$(grep -wE "^#@& {username}" "/etc/xray/config.json" | cut -d ' ' -f 3 | sort | uniq)

# Setup limit
mkdir -p /etc/limit/shadowsocks/ip
echo ${{iplim}} > /etc/limit/shadowsocks/ip/${{user}}

# Setup quota
if [ ! -e /etc/shadowsocks/ ]; then
  mkdir -p /etc/shadowsocks/
fi

if [ -z ${{Quota}} ]; then
  Quota="0"
fi

c=$(echo "${{Quota}}" | sed 's/[^0-9]*//g')
d=$((${{c}} * 1024 * 1024 * 1024))

if [[ ${{c}} != "0" ]]; then
  echo "${{d}}" >/etc/shadowsocks/${{user}}
fi

# Calculate new expiry
now=$(date +%Y-%m-%d)
d1=$(date -d "$exp" +%s)
d2=$(date -d "$now" +%s)
exp2=$(( (d1 - d2) / 86400 ))
exp3=$(($exp2 + ${{masaaktif}}))
exp4=`date -d "${{exp3}} days" +"%Y-%m-%d"`

# Update config
sed -i "/#@& {username}/c\\#@& {username} $exp4" /etc/xray/config.json
sed -i "/#@& {username}/c\\#@& {username} $exp4" /etc/shadowsocks/.shadowsocks.db

# Restart service
systemctl restart xray > /dev/null 2>&1

echo "SUCCESS: Shadowsocks Account renewed for {username}"
echo "Expired On  : $exp4"
echo "User Quota  : ${{Quota}} GB"
echo "User Limit IP: ${{iplim}} IP"
"""
            
            elif service_type == "zivpn":
                command = f"""
#!/bin/bash
USER_DB="/etc/zivpn/users.json"
SERVICE="zivpn"

username="{username}"
days="{days}"

# Get current expiry
current_expiry=$(jq -r ".users.\\"{username}\\"".expiry_date" "$USER_DB" 2>/dev/null)

if [ "$current_expiry" = "unlimited" ] || [ "$current_expiry" = "null" ] || [ -z "$current_expiry" ]; then
    new_expiry=$(date -d "+$days days" "+%Y-%m-%d")
else
    # Cek apakah expired
    expiry_ts=$(date -d "$current_expiry" +%s 2>/dev/null)
    now_ts=$(date +%s)
    
    if [ $expiry_ts -le $now_ts ]; then
        # Sudah expired, mulai dari sekarang
        new_expiry=$(date -d "+$days days" "+%Y-%m-%d")
    else
        # Masih aktif, tambah dari expiry lama
        new_expiry=$(date -d "$current_expiry + $days days" "+%Y-%m-%d")
    fi
fi

# Update database
jq --arg user "$username" --arg expiry "$new_expiry" '.users[$user].expiry_date = $expiry' "$USER_DB" > /tmp/zivpn_tmp.json
if [ $? -eq 0 ]; then
    mv /tmp/zivpn_tmp.json "$USER_DB"
    
    # Restart service
    systemctl restart "$SERVICE"
    
    echo "SUCCESS: ZiVPN Account renewed for {username}"
    echo "Periode: $days hari"
    echo "Expiry baru: $new_expiry"
else
    echo "ERROR: Failed to update ZiVPN user database"
    exit 1
fi
"""
            
            else:
                return False, f"Jenis layanan tidak didukung: {service_type}"
        
        elif upgrade_type == "ip_limit":
            # Update IP limit saja
            new_ip_limit = account.get("ip_limit", 1)
            
            if service_type == "ssh":
                command = f"""
#!/bin/bash
USERNAME="{username}"
IP_LIMIT="{new_ip_limit}"

# Update IP Limit
mkdir -p /etc/limit/ssh/ip
echo $IP_LIMIT > /etc/limit/ssh/ip/$USERNAME

# Update database SSH
current_info=$(grep '#ssh# $USERNAME' /etc/ssh/.ssh.db)
if [ ! -z "$current_info" ]; then
    quota=$(echo "$current_info" | cut -d' ' -f3)
    current_iplimit=$(echo "$current_info" | cut -d' ' -f4)
    expiry=$(echo "$current_info" | cut -d' ' -f5-)
    sed -i "s|#ssh# $USERNAME .*|#ssh# $USERNAME $quota $IP_LIMIT $expiry|" /etc/ssh/.ssh.db
fi

echo "SUCCESS: SSH IP limit updated for $USERNAME"
echo "New IP Limit: $IP_LIMIT IP"
"""
            
            elif service_type in ["vmess", "vless", "trojan", "ss"]:
                db_file = f"/etc/{service_type}/.{service_type}.db"
                command = f"""
#!/bin/bash
user="{username}"
iplim="{new_ip_limit}"

# Update IP limit
mkdir -p /etc/limit/{service_type}/ip
echo ${{iplim}} > /etc/limit/{service_type}/ip/${{user}}

# Update database
if [ -f "{db_file}" ]; then
    current_line=$(grep "{username}" "{db_file}")
    if [ ! -z "$current_line" ]; then
        # Format: #service username expiry uuid quota iplimit
        parts=($current_line)
        uuid="${{parts[2]}}"
        expiry="${{parts[1]}}"
        quota="${{parts[3]}}"
        sed -i "s|^.*{username}.*$|{service_type[0] if service_type != 'ss' else '#@&'} {username} $expiry $uuid $quota ${{iplim}}|" "{db_file}"
    fi
fi

echo "SUCCESS: {service_type.upper()} IP limit updated for {username}"
echo "New IP Limit: ${{iplim}} IP"
"""
            
            elif service_type == "zivpn":
                command = f"""
#!/bin/bash
USER_DB="/etc/zivpn/users.json"
SERVICE="zivpn"

username="{username}"
iplimit="{new_ip_limit}"

# Update IP limit in database
jq --arg user "$username" --arg iplimit "$iplimit" '.users[$user].ip_limit = ($iplimit | tonumber)' "$USER_DB" > /tmp/zivpn_tmp.json
if [ $? -eq 0 ]; then
    mv /tmp/zivpn_tmp.json "$USER_DB"
    
    # Restart service
    systemctl restart zivpn
    
    echo "SUCCESS: ZiVPN IP limit updated for {username}"
    echo "New IP Limit: $iplimit IP"
else
    echo "ERROR: Failed to update ZiVPN IP limit"
    exit 1
fi
"""
        
        # Execute command
        success, output = await execute_ssh_command(
            vps["ip"],
            vps.get("ssh_port", 22),
            vps["ssh_user"],
            vps["ssh_pass"],
            command
        )
        
        return success, output
        
    except Exception as e:
        print(f"Error updating account on server: {e}")
        return False, f"Error: {str(e)}"
                       
            
def cleanup_expired_accounts():
    """Hapus akun reguler yang sudah expired"""
    accounts = load_json(ACCOUNTS_DB)
    now = datetime.now()
    expired_count = 0
    
    account_ids = list(accounts.keys())
    for account_id in account_ids:
        account = accounts[account_id]
        expires_at = account.get("expires_at")
        if expires_at:
            try:
                exp_date = datetime.fromisoformat(expires_at)
                if exp_date < now:
                    # Coba hapus dari server
                    asyncio.create_task(delete_account_from_server(account))
                    # Hapus dari database
                    del accounts[account_id]
                    expired_count += 1
            except:
                pass
    
    if expired_count > 0:
        save_json(ACCOUNTS_DB, accounts)
    
    return expired_count

async def delete_account_from_server(account_data: Dict):
    """Hapus akun dari server SSH"""
    try:
        vps_id = account_data.get("vps_id")
        vps = get_vps(vps_id)
        if not vps:
            return False
        
        service_type = account_data.get("service_type", "")
        username = account_data.get("username", "")
        
        if service_type == "ssh":
            command = f"userdel -r {username} 2>/dev/null; echo 'SSH account deleted'"
        elif service_type == "vmess":
            command = f"""
            sed -i '/### {username} /d' /etc/xray/config.json
            rm -f /etc/limit/vmess/ip/{username} 2>/dev/null
            rm -f /etc/vmess/{username} 2>/dev/null
            rm -f /detail/vmess/{username}.txt 2>/dev/null
            rm -f /var/www/html/vmess-{username}.txt 2>/dev/null
            sed -i '/### {username} /d' /etc/vmess/.vmess.db
            echo 'VMess account deleted'
            """
        elif service_type == "vless":
            command = f"""
            sed -i '/#& {username} /d' /etc/xray/config.json
            rm -f /etc/limit/vless/ip/{username} 2>/dev/null
            rm -f /etc/vless/{username} 2>/dev/null
            rm -f /detail/vless/{username}.txt 2>/dev/null
            rm -f /var/www/html/vless-{username}.txt 2>/dev/null
            sed -i '/#& {username} /d' /etc/vless/.vless.db
            echo 'VLESS account deleted'
            """
        elif service_type == "trojan":
            command = f"""
            sed -i '/#! {username} /d' /etc/xray/config.json
            rm -f /etc/limit/trojan/ip/{username} 2>/dev/null
            rm -f /etc/trojan/{username} 2>/dev/null
            rm -f /detail/trojan/{username}.txt 2>/dev/null
            rm -f /var/www/html/trojan-{username}.txt 2>/dev/null
            sed -i '/#! {username} /d' /etc/trojan/.trojan.db
            echo 'Trojan account deleted'
            """
        elif service_type == "ss":
            command = f"""
            sed -i '/#@& {username} /d' /etc/xray/config.json
            rm -f /etc/limit/shadowsocks/ip/{username} 2>/dev/null
            rm -f /etc/shadowsocks/{username} 2>/dev/null
            rm -f /detail/shadowsocks/{username}.txt 2>/dev/null
            rm -f /var/www/html/ss-{username}.txt 2>/dev/null
            sed -i '/#@& {username} /d' /etc/shadowsocks/.shadowsocks.db
            echo 'Shadowsocks account deleted'
            """
        elif service_type == "zivpn":
            command = f"""
            jq 'del(.users."{username}")' /etc/zivpn/users.json > /tmp/zivpn_tmp.json && mv /tmp/zivpn_tmp.json /etc/zivpn/users.json
            echo 'ZiVPN account deleted'
            """
        else:
            return False
        
        success, _ = await execute_ssh_command(
            vps["ip"],
            vps.get("ssh_port", 22),
            vps["ssh_user"],
            vps["ssh_pass"],
            command
        )
        
        # Restart service jika perlu
        if service_type in ["vmess", "vless", "trojan", "ss"]:
            restart_cmd = "systemctl restart xray >/dev/null 2>&1"
            await execute_ssh_command(
                vps["ip"],
                vps.get("ssh_port", 22),
                vps["ssh_user"],
                vps["ssh_pass"],
                restart_cmd
            )
        elif service_type == "zivpn":
            restart_cmd = "systemctl restart zivpn >/dev/null 2>&1"
            await execute_ssh_command(
                vps["ip"],
                vps.get("ssh_port", 22),
                vps["ssh_user"],
                vps["ssh_pass"],
                restart_cmd
            )
        
        return success
    except Exception as e:
        print(f"Error deleting account from server: {e}")
        return False

# ============================================
# FUNGSI BANTUAN TAMPILAN
# ============================================

def generate_separator(length: int = 22, char: str = "─") -> str:
    """Generate separator line dengan panjang yang sesuai"""
    return char * length
                    
def generate_header(title: str) -> str:
    """Generate header dengan border yang rapi (23 karakter)"""
    border_length = 23
    
    # Top border
    top_border = "╔" + "═" * (border_length - 2) + "╗\n"
    
    # Title line (center aligned)
    title_with_emoji = f"✨ {title} ✨"
    title_space = border_length - 2 - len(title_with_emoji)
    left_space = title_space // 2
    right_space = title_space - left_space
    title_line = f"║{' ' * left_space}{title_with_emoji}{' ' * right_space}║\n"
    
    # Bottom border
    bottom_border = "╚" + "═" * (border_length - 2) + "╝"
    
    return top_border + title_line + bottom_border
                    
def format_money(amount: int) -> str:
    """Format uang dengan titik pemisah ribuan"""
    return f"Rp {amount:,}"

def format_date(date_str: str) -> str:
    """Format tanggal menjadi tampilan yang lebih baik"""
    try:
        date_obj = datetime.fromisoformat(date_str)
        return date_obj.strftime("%d %b, %Y")
    except:
        return date_str

def format_datetime(date_str: str) -> str:
    """Format tanggal dan waktu"""
    try:
        date_obj = datetime.fromisoformat(date_str)
        return date_obj.strftime("%d %b %Y, %H:%M")
    except:
        return date_str

# ============================================
# SSH UTILITIES
# ============================================

async def execute_ssh_command(host: str, port: int, username: str, password: str, command: str) -> Tuple[bool, str]:
    """Eksekusi command SSH dengan timeout dan error handling"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Koneksi dengan timeout
        ssh.connect(host, port=port, username=username, password=password, 
                   timeout=30, banner_timeout=30, auth_timeout=30)
        
        # Execute command dengan timeout
        stdin, stdout, stderr = ssh.exec_command(command, timeout=60)
        
        # Baca output
        output = stdout.read().decode('utf-8', errors='ignore').strip()
        error = stderr.read().decode('utf-8', errors='ignore').strip()
        
        ssh.close()
        
        # Gabungkan output dan error
        full_output = output + ("\n" + error if error else "")
        
        return True, full_output
        
    except paramiko.AuthenticationException:
        return False, "Authentication failed"
    except paramiko.SSHException as e:
        return False, f"SSH error: {str(e)}"
    except Exception as e:
        return False, f"Connection error: {str(e)}"

async def test_ssh_connection(host: str, port: int, username: str, password: str) -> bool:
    """Test koneksi SSH"""
    success, _ = await execute_ssh_command(host, port, username, password, "echo 'test'")
    return success

async def set_domain_on_vps(vps: Dict, domain: str) -> bool:
    """Set domain pada VPS"""
    command = f"""
#!/bin/bash
# Set domain
echo "{domain}" > /etc/xray/domain
echo "Domain {domain} telah diset di server."
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    return success and "telah diset" in output

# ============================================
# FUNGSI PEMBUATAN AKUN VPN
# ============================================

async def create_ssh_account(vps: Dict, username: str, password: str, duration: int, 
                           quota: int = 200, iplimit: int = 1, extra_ips: int = 0) -> Tuple[bool, str, Dict]:
    """Buat akun SSH dengan script yang diperbaiki"""
    
    domain = vps.get("domain", "super.oxygencrc.my.id")
    
    # Hitung total IP limit
    total_iplimit = iplimit + extra_ips
    
    # Buat command untuk membuat akun SSH
    command = f"""
#!/bin/bash
export TIME="10"
IP=$(curl -sS ipv4.icanhazip.com)
CITY=$(curl -s ipinfo.io/city)
domain="{domain}"
NS=$(cat /etc/xray/dns 2>/dev/null || echo "")
PUB=$(cat /etc/slowdns/server.pub 2>/dev/null || echo "")

# Data dari input
user="{username}"
Pass="{password}"
iplimit="{total_iplimit}"
Quota="{quota}"
masaaktif="{duration}"

# Buat akun SSH
if [[ $iplimit -gt 0 ]]; then
mkdir -p /etc/limit/ssh/ip
echo -e "$iplimit" > /etc/limit/ssh/ip/$user
fi

useradd -e $(date -d "$masaaktif days" +"%Y-%m-%d") -s /bin/false -M $user
echo -e "$Pass\\n$Pass\\n" | passwd $user &> /dev/null

# Setup quota
if [[ $Quota != "0" ]]; then
d=$((${{Quota}} * 1024 * 1024 * 1024))
echo "$d" >/etc/ssh/$user
fi

# Simpan ke database
echo "#ssh# $user $Pass $Quota $iplimit $(date -d "$masaaktif days" +"%d %b, %Y")" >> /etc/ssh/.ssh.db

# Buat file detail
mkdir -p /detail/ssh/
cat > /detail/ssh/$user.txt <<-END
-----------------------------------------
SSH Account
-----------------------------------------
Host             : $domain
IP               : $IP
Username         : $user
Password         : $Pass
-----------------------------------------
Limit Quota      : $Quota GB
Limit Ip         : $iplimit IP
Host Slowdns     : $NS
Pub Key          : $PUB
Port OpenSSH     : 22
Port DNS         : 53 ,2222
Port SSH UDP     : 1-65535
Port Dropbear    : 22, 109
Port SSH WS      : 80,8080,2086,8880
Port SSH WS SSL  : 443,8443
Port SSL/TLS     : 443
BadVPN UDP       : 7100, 7300, 7300
-----------------------------------------
HTTP CUSTOM      : $domain:1-65535@$user:$Pass
-----------------------------------------
Payload          : GET /cdn-cgi/trace HTTP/1.1[crlf]Host: Bug_Kalian[crlf][crlf]GET-RAY / HTTP/1.1[crlf]Host: [host]-----------------------------------------
-----------------------------------------
Save Link Account: https://$domain:81/ssh-$user.txt
-----------------------------------------
Aktif Selama     : $masaaktif Hari
Dibuat Pada      : $(date +"%d %b, %Y")
Berakhir Pada    : $(date -d "$masaaktif days" +"%d %b, %Y")
-----------------------------------------
END

# Buat file untuk download
cat > /var/www/html/ssh-$user.txt <<-END
-----------------------------------------
SSH Account
-----------------------------------------
Host             : $domain
IP               : $IP
Username         : $user
Password         : $Pass
-----------------------------------------
Limit Quota      : $Quota GB
Limit Ip         : $iplimit IP
Host Slowdns     : $NS
Pub Key          : $PUB
Port OpenSSH     : 22
Port DNS         : 53 ,2222
Port SSH UDP     : 1-65535
Port Dropbear    : 22, 109
Port SSH WS      : 80,8080,2086,8880
Port SSH WS SSL  : 443,8443
Port SSL/TLS     : 443
BadVPN UDP       : 7100, 7300, 7300
-----------------------------------------
HTTP CUSTOM      : $domain:1-65535@$user:$Pass
-----------------------------------------
Payload          : GET /cdn-cgi/trace HTTP/1.1[crlf]Host: Bug_Kalian[crlf][crlf]GET-RAY / HTTP/1.1[crlf]Host: [host]-----------------------------------------
-----------------------------------------
Save Link Account: https://$domain:81/ssh-$user.txt
-----------------------------------------
Aktif Selama     : $masaaktif Hari
Dibuat Pada      : $(date +"%d %b, %Y")
Berakhir Pada    : $(date -d "$masaaktif days" +"%d %b, %Y")
-----------------------------------------
END

echo "SUCCESS: SSH Account created for $user"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success and ("SUCCESS" in output or "success" in output.lower() or "created" in output.lower()):
        # Buat data akun
        account_data = {
            "service_type": "ssh",
            "username": username,
            "password": password,
            "vps_id": vps["id"],
            "domain": domain,
            "server_ip": vps["ip"],
            "ip_limit": total_iplimit,
            "base_ip_limit": iplimit,
            "extra_ips": extra_ips,
            "quota": quota,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=duration)).isoformat(),
            "duration": duration
        }
        
        return True, "✅ Akun SSH berhasil dibuat!", account_data
    else:
        return False, f"❌ Gagal membuat akun SSH: {output[:500]}", {}


async def create_vmess_account(vps: Dict, username: str, duration: int, 
                             quota: int = 200, iplimit: int = 1, extra_ips: int = 0) -> Tuple[bool, str, Dict]:
    """Buat akun VMess via SSH ke VPS"""
    
    domain = vps.get("domain", "super.oxygencrc.my.id")
    
    # Hitung total IP limit
    total_iplimit = iplimit + extra_ips
    
    command = f"""
#!/bin/bash
clear
domain="{domain}"
uuid=$(cat /proc/sys/kernel/random/uuid)
user="{username}"
masaaktif="{duration}"
exp=$(date -d "$masaaktif days" +"%Y-%m-%d")

# Tambahkan ke config.json
sed -i '/#vmess$/a\\\\### '"$user $exp"'\\\\\\n}},{{"id": "'"$uuid"'","alterId": 0,"email": "'"$user"'"' /etc/xray/config.json
sed -i '/#vmessgrpc$/a\\\\### '"$user $exp"'\\\\\\n}},{{"id": "'"$uuid"'","alterId": 0,"email": "'"$user"'"' /etc/xray/config.json

# Buat config VMess
vmess_tls_config='{{
  "v": "2",
  "ps": "{username}-TLS",
  "add": "$domain",
  "port": "443",
  "id": "$uuid",
  "aid": "0",
  "net": "ws",
  "path": "/vmess",
  "type": "none",
  "host": "$domain",
  "tls": "tls"
}}'

vmess_ntls_config='{{
  "v": "2",
  "ps": "{username}-NTLS",
  "add": "$domain",
  "port": "80",
  "id": "$uuid",
  "aid": "0",
  "net": "ws",
  "path": "/vmess",
  "type": "none",
  "host": "$domain",
  "tls": "none"
}}'

vmess_grpc_config='{{
  "v": "2",
  "ps": "{username}-GRPC",
  "add": "$domain",
  "port": "443",
  "id": "$uuid",
  "aid": "0",
  "net": "grpc",
  "path": "vmess-grpc",
  "type": "none",
  "host": "$domain",
  "tls": "tls"
}}'

# Encode ke base64
vmess_tls_base64=$(echo -n "$vmess_tls_config" | base64 -w 0)
vmess_ntls_base64=$(echo -n "$vmess_ntls_config" | base64 -w 0)
vmess_grpc_base64=$(echo -n "$vmess_grpc_config" | base64 -w 0)

# Restart service
systemctl restart xray > /dev/null 2>&1

# Setup limit
if [[ {total_iplimit} -gt 0 ]]; then
    mkdir -p /etc/limit/vmess/ip
    echo -e "{total_iplimit}" > /etc/limit/vmess/ip/{username}
fi

# Setup quota
if [[ {quota} != "0" ]]; then
    d=$(( {quota} * 1024 * 1024 * 1024 ))
    echo "$d" > /etc/vmess/{username}
fi

# Simpan ke database
echo "### {username} $exp $uuid {quota} {total_iplimit}" >> /etc/vmess/.vmess.db

# Buat file detail
mkdir -p /detail/vmess/
cat > /detail/vmess/{username}.txt <<-END
-----------------------------------------
CREATE VMESS ACCOUNT
-----------------------------------------
Username : {username}
Expired (days): {duration}
Limit GB: {quota}
Limit IP: {total_iplimit}
SUCCESS: VMess account created successfully!
{generate_separator(42)}
VMess Account Details:
Username: {username}
UUID: $uuid
Domain: $domain
Quota: {quota} GB
IP Limit: {total_iplimit} IP
Expired: $(date -d "{duration} days" +"%d %b, %Y")
{generate_separator(42)}
TLS Link: vmess://$vmess_tls_base64
Non-TLS Link: vmess://$vmess_ntls_base64
gRPC Link: vmess://$vmess_grpc_base64
{generate_separator(42)}
Account file: https://$domain:81/vmess-{username}.txt
{generate_separator(42)}
END

# Buat file untuk download
cat > /var/www/html/vmess-{username}.txt <<-END
-----------------------------------------
CREATE VMESS ACCOUNT
-----------------------------------------
Username : {username}
Expired (days): {duration}
Limit GB: {quota}
Limit IP: {total_iplimit}
SUCCESS: VMess account created successfully!
{generate_separator(42)}
VMess Account Details:
Username: {username}
UUID: $uuid
Domain: $domain
Quota: {quota} GB
IP Limit: {total_iplimit} IP
Expired: $(date -d "{duration} days" +"%d %b, %Y")
{generate_separator(42)}
TLS Link: vmess://$vmess_tls_base64
Non-TLS Link: vmess://$vmess_ntls_base64
gRPC Link: vmess://$vmess_grpc_base64
{generate_separator(42)}
Account file: https://$domain:81/vmess-{username}.txt
{generate_separator(42)}
END

echo "SUCCESS: VMess Account created for {username}"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success and ("SUCCESS" in output or "success" in output.lower()):
        # Ekstrak UUID dari output
        uuid_value = ""
        for line in output.split('\n'):
            if 'UUID:' in line:
                uuid_value = line.split(': ')[1].strip()
                break
        
        if not uuid_value:
            uuid_value = str(uuid.uuid4())
        
        # Buat link VMess TLS di Python
        vmess_data_tls = {
            "v": "2",
            "ps": f"{username}-TLS",
            "add": domain,
            "port": "443",
            "id": uuid_value,
            "aid": "0",
            "net": "ws",
            "path": "/vmess",
            "type": "none",
            "host": domain,
            "tls": "tls"
        }
        
        vmess_data_ntls = {
            "v": "2",
            "ps": f"{username}-NTLS",
            "add": domain,
            "port": "80",
            "id": uuid_value,
            "aid": "0",
            "net": "ws",
            "path": "/vmess",
            "type": "none",
            "host": domain,
            "tls": "none"
        }
        
        vmess_data_grpc = {
            "v": "2",
            "ps": f"{username}-GRPC",
            "add": domain,
            "port": "443",
            "id": uuid_value,
            "aid": "0",
            "net": "grpc",
            "path": "vmess-grpc",
            "type": "none",
            "host": domain,
            "tls": "tls"
        }
        
        vmess_tls = f"vmess://{base64.b64encode(json.dumps(vmess_data_tls).encode()).decode()}"
        vmess_ntls = f"vmess://{base64.b64encode(json.dumps(vmess_data_ntls).encode()).decode()}"
        vmess_grpc = f"vmess://{base64.b64encode(json.dumps(vmess_data_grpc).encode()).decode()}"
        
        account_data = {
            "service_type": "vmess",
            "username": username,
            "vps_id": vps["id"],
            "domain": domain,
            "uuid": uuid_value,
            "ip_limit": total_iplimit,
            "base_ip_limit": iplimit,
            "extra_ips": extra_ips,
            "quota": quota,
            "vmess_tls": vmess_tls,
            "vmess_ntls": vmess_ntls,
            "vmess_grpc": vmess_grpc,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=duration)).isoformat(),
            "duration": duration
        }
        
        return True, "✅ Akun VMess berhasil dibuat!", account_data
    else:
        return False, f"❌ Gagal membuat akun VMess: {output[:500]}", {}    

async def create_vless_account(vps: Dict, username: str, duration: int, 
                             quota: int = 200, iplimit: int = 1, extra_ips: int = 0) -> Tuple[bool, str, Dict]:
    """Buat akun VLESS dengan script yang Anda berikan"""
    
    domain = vps.get("domain", "super.oxygencrc.my.id")
    
    # Hitung total IP limit
    total_iplimit = iplimit + extra_ips
    
    command = f"""
#!/bin/bash
clear
domain="{domain}"
uuid=$(cat /proc/sys/kernel/random/uuid)
user="{username}"
masaaktif="{duration}"
exp=$(date -d "$masaaktif days" +"%Y-%m-%d")

# Tambahkan ke config.json
sed -i '/#vless$/a\\#& '"$user $exp"'\\\n}},{{"id": "'"$uuid"'","email": "'"$user"'"' /etc/xray/config.json
sed -i '/#vlessgrpc$/a\\#& '"$user $exp"'\\\n}},{{"id": "'"$uuid"'","email": "'"$user"'"' /etc/xray/config.json

# Buat link
vless_tls="vless://$uuid@$domain:443?path=/vless&security=tls&encryption=none&type=ws&host=$domain&sni=$domain#{username}"
vless_ntls="vless://$uuid@$domain:80?path=/vless&encryption=none&type=ws&host=$domain#{username}"
vless_grpc="vless://$uuid@$domain:443?mode=gun&security=tls&encryption=none&type=grpc&serviceName=vless-grpc&sni=$domain#{username}"

# Restart service
systemctl restart xray > /dev/null 2>&1

# Setup limit
if [[ {total_iplimit} -gt 0 ]]; then
mkdir -p /etc/limit/vless/ip
echo -e "{total_iplimit}" > /etc/limit/vless/ip/{username}
fi

# Setup quota
if [[ {quota} != "0" ]]; then
d=$(( {quota} * 1024 * 1024 * 1024 ))
echo "$d" > /etc/vless/{username}
fi

# Simpan ke database
echo "#& {username} $exp $uuid {quota} {total_iplimit}" >> /etc/vless/.vless.db

# Buat file detail
mkdir -p /detail/vless/
cat > /detail/vless/{username}.txt <<-END
-----------------------------------------
Xray/Vless Account
-----------------------------------------
Remarks     : {username}
Domain      : $domain
User Quota  : {quota} GB
User Ip     : {total_iplimit} IP
Port Non TLS: 80,8080,2086,8880
Port TLS    : 443,8443
User ID     : $uuid
Encryption  : none
Path TLS    : /vless
ServiceName : vless-grpc
-----------------------------------------
Link TLS    : $vless_tls
-----------------------------------------
Link NTLS   : $vless_ntls
-----------------------------------------
Link GRPC   : $vless_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/vless-{username}.txt
-----------------------------------------
Aktif Selama     : {duration} Hari
Dibuat Pada      : $(date +"%d %b, %Y")
Berakhir Pada    : $(date -d "{duration} days" +"%d %b, %Y")
-----------------------------------------
END

# Buat file untuk download
cat > /var/www/html/vless-{username}.txt <<-END
-----------------------------------------
Xray/Vless Account
-----------------------------------------
Remarks     : {username}
Domain      : $domain
User Quota  : {quota} GB
User Ip     : {total_iplimit} IP
Port Non TLS: 80,8080,2086,8880
Port TLS    : 443,8443
User ID     : $uuid
Encryption  : none
Path TLS    : /vless
ServiceName : vless-grpc
-----------------------------------------
Link TLS    : $vless_tls
-----------------------------------------
Link NTLS   : $vless_ntls
-----------------------------------------
Link GRPC   : $vless_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/vless-{username}.txt
-----------------------------------------
Aktif Selama     : {duration} Hari
Dibuat Pada      : $(date +"%d %b, %Y")
Berakhir Pada    : $(date -d "{duration} days" +"%d %b, %Y")
-----------------------------------------
END

echo "SUCCESS: VLESS Account created for {username}"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success and ("SUCCESS" in output or "success" in output.lower()):
        # Ekstrak UUID dari output
        uuid_value = ""
        for line in output.split('\n'):
            if 'User ID' in line:
                uuid_value = line.split(': ')[1].strip()
                break
        
        if not uuid_value:
            uuid_value = str(uuid.uuid4())
        
        # Buat link VLESS
        vless_tls = f"vless://{uuid_value}@{domain}:443?path=/vless&security=tls&encryption=none&type=ws&host={domain}&sni={domain}#{username}"
        vless_ntls = f"vless://{uuid_value}@{domain}:80?path=/vless&encryption=none&type=ws&host={domain}#{username}"
        vless_grpc = f"vless://{uuid_value}@{domain}:443?mode=gun&security=tls&encryption=none&type=grpc&serviceName=vless-grpc&sni={domain}#{username}"
        
        account_data = {
            "service_type": "vless",
            "username": username,
            "vps_id": vps["id"],
            "domain": domain,
            "uuid": uuid_value,
            "ip_limit": total_iplimit,
            "base_ip_limit": iplimit,
            "extra_ips": extra_ips,
            "quota": quota,
            "vless_tls": vless_tls,
            "vless_ntls": vless_ntls,
            "vless_grpc": vless_grpc,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=duration)).isoformat(),
            "duration": duration
        }
        
        return True, "✅ Akun VLESS berhasil dibuat!", account_data
    else:
        return False, f"❌ Gagal membuat akun VLESS: {output[:500]}", {}

async def create_trojan_account(vps: Dict, username: str, duration: int, 
                              quota: int = 200, iplimit: int = 1, extra_ips: int = 0) -> Tuple[bool, str, Dict]:
    """Buat akun Trojan dengan script yang Anda berikan"""
    
    domain = vps.get("domain", "super.oxygencrc.my.id")
    
    # Hitung total IP limit
    total_iplimit = iplimit + extra_ips
    
    command = f"""
#!/bin/bash
clear
domain="{domain}"
uuid=$(cat /proc/sys/kernel/random/uuid)
user="{username}"
masaaktif="{duration}"
exp=$(date -d "$masaaktif days" +"%Y-%m-%d")

# Tambahkan ke config.json
sed -i '/#trojanws$/a\\#! '"$user $exp"'\\\n}},{{"password": "'"$uuid"'","email": "'"$user"'"' /etc/xray/config.json
sed -i '/#trojangrpc$/a\\#! '"$user $exp"'\\\n}},{{"password": "'"$uuid"'","email": "'"$user"'"' /etc/xray/config.json

# Buat link
trojan_ws="trojan://$uuid@$domain:443?path=%2Ftrojan-ws&security=tls&host=$domain&type=ws&sni=$domain#{username}"
trojan_grpc="trojan://$uuid@$domain:443?mode=gun&security=tls&type=grpc&serviceName=trojan-grpc&sni=$domain#{username}"

# Restart service
systemctl restart xray > /dev/null 2>&1

# Setup limit
if [[ {total_iplimit} -gt 0 ]]; then
mkdir -p /etc/limit/trojan/ip
echo -e "{total_iplimit}" > /etc/limit/trojan/ip/{username}
fi

# Setup quota
if [[ {quota} != "0" ]]; then
d=$(( {quota} * 1024 * 1024 * 1024 ))
echo "$d" > /etc/trojan/{username}
fi

# Simpan ke database
echo "#! {username} $exp $uuid {quota} {total_iplimit}" >> /etc/trojan/.trojan.db

# Buat file detail
mkdir -p /detail/trojan/
cat > /detail/trojan/{username}.txt <<-END
-----------------------------------------
Xray/Trojan Account
-----------------------------------------
Remarks          : {username}
Host/IP          : $domain
User Quota       : {quota} GB
User Ip          : {total_iplimit} IP
Port             : 443,8443
Key              : $uuid
Path             : /trojan-ws
ServiceName      : trojan-grpc
-----------------------------------------
Link TLS         : $trojan_ws
-----------------------------------------
Link GRPC        : $trojan_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/trojan-{username}.txt
-----------------------------------------
Aktif Selama     : {duration} Hari
Dibuat Pada      : $(date +"%d %b, %Y")
Berakhir Pada    : $(date -d "{duration} days" +"%d %b, %Y")
-----------------------------------------
END

# Buat file untuk download
cat > /var/www/html/trojan-{username}.txt <<-END
-----------------------------------------
Xray/Trojan Account
-----------------------------------------
Remarks          : {username}
Host/IP          : $domain
User Quota       : {quota} GB
User Ip          : {total_iplimit} IP
Port             : 443,8443
Key              : $uuid
Path             : /trojan-ws
ServiceName      : trojan-grpc
-----------------------------------------
Link TLS         : $trojan_ws
-----------------------------------------
Link GRPC        : $trojan_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/trojan-{username}.txt
-----------------------------------------
Aktif Selama     : {duration} Hari
Dibuat Pada      : $(date +"%d %b, %Y")
Berakhir Pada    : $(date -d "{duration} days" +"%d %b, %Y")
-----------------------------------------
END

echo "SUCCESS: Trojan Account created for {username}"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success and ("SUCCESS" in output or "success" in output.lower()):
        # Ekstrak UUID dari output
        uuid_value = ""
        for line in output.split('\n'):
            if 'Key' in line:
                uuid_value = line.split(': ')[1].strip()
                break
        
        if not uuid_value:
            uuid_value = str(uuid.uuid4())
        
        # Buat link Trojan
        trojan_ws = f"trojan://{uuid_value}@{domain}:443?path=%2Ftrojan-ws&security=tls&host={domain}&type=ws&sni={domain}#{username}"
        trojan_grpc = f"trojan://{uuid_value}@{domain}:443?mode=gun&security=tls&type=grpc&serviceName=trojan-grpc&sni={domain}#{username}"
        
        account_data = {
            "service_type": "trojan",
            "username": username,
            "vps_id": vps["id"],
            "domain": domain,
            "uuid": uuid_value,
            "ip_limit": total_iplimit,
            "base_ip_limit": iplimit,
            "extra_ips": extra_ips,
            "quota": quota,
            "trojan_ws": trojan_ws,
            "trojan_grpc": trojan_grpc,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=duration)).isoformat(),
            "duration": duration
        }
        
        return True, "✅ Akun Trojan berhasil dibuat!", account_data
    else:
        return False, f"❌ Gagal membuat akun Trojan: {output[:500]}", {}

async def create_ss_account(vps: Dict, username: str, duration: int, 
                          quota: int = 200, iplimit: int = 1, extra_ips: int = 0) -> Tuple[bool, str, Dict]:
    """Buat akun Shadowsocks dengan script yang Anda berikan"""
    
    domain = vps.get("domain", "super.oxygencrc.my.id")
    
    # Hitung total IP limit
    total_iplimit = iplimit + extra_ips
    
    command = f"""
#!/bin/bash
clear
domain="{domain}"
uuid=$(cat /proc/sys/kernel/random/uuid)
cipher="aes-128-gcm"
user="{username}"
masaaktif="{duration}"
exp=$(date -d "$masaaktif days" +"%Y-%m-%d")

# Tambahkan ke config.json
sed -i '/#ssws$/a\\#@& '"$user $exp"'\\\n}},{{"password": "'"$uuid"'","method": "'"$cipher"'","email": "'"$user"'"' /etc/xray/config.json
sed -i '/#ssgrpc$/a\\#@& '"$user $exp"'\\\n}},{{"password": "'"$uuid"'","method": "'"$cipher"'","email": "'"$user"'"' /etc/xray/config.json

# Buat config Shadowsocks
ss_config="$cipher:$uuid"
ss_base64=$(echo -n "$ss_config" | base64)

# Buat link
ss_ws_tls="ss://$ss_base64@$domain:443?path=/ss-ws&security=tls&encryption=none&type=ws&host=$domain&sni=$domain#{username}"
ss_ws_ntls="ss://$ss_base64@$domain:80?path=/ss-ws&security=none&encryption=none&type=ws&host=$domain#{username}"
ss_grpc="ss://$ss_base64@$domain:443?mode=gun&security=tls&encryption=none&type=grpc&serviceName=ss-grpc&sni=$domain#{username}"

# Restart service
systemctl restart xray > /dev/null 2>&1

# Setup limit
if [[ {total_iplimit} -gt 0 ]]; then
mkdir -p /etc/limit/shadowsocks/ip
echo -e "{total_iplimit}" > /etc/limit/shadowsocks/ip/{username}
fi

# Setup quota
if [[ {quota} != "0" ]]; then
d=$(( {quota} * 1024 * 1024 * 1024 ))
echo "$d" > /etc/shadowsocks/{username}
fi

# Simpan ke database
echo "#@& {username} $exp $uuid {quota} {total_iplimit}" >> /etc/shadowsocks/.shadowsocks.db

# Buat file detail
mkdir -p /detail/shadowsocks/
cat > /detail/shadowsocks/{username}.txt <<-END
-----------------------------------------
Xray/Shadowsocks Account
-----------------------------------------
Remarks     : {username}
Domain      : $domain
User Quota  : {quota} GB
User Ip     : {total_iplimit} IP
Port Non TLS: 80,8080,2086,8880
Port TLS    : 443,8443
Password    : $uuid
Cipers      : $cipher
Network     : ws/grpc
Path        : /ss-ws
ServiceName : ss-grpc
-----------------------------------------
Link WS TLS : $ss_ws_tls
-----------------------------------------
Link WS None TLS : $ss_ws_ntls
-----------------------------------------
Link GRPC : $ss_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/ss-{username}.txt
-----------------------------------------
Aktif Selama   : {duration} Hari
Dibuat Pada    : $(date +"%d %b, %Y")
Berakhir Pada  : $(date -d "{duration} days" +"%d %b, %Y")
-----------------------------------------
END

# Buat file untuk download
cat > /var/www/html/ss-{username}.txt <<-END
-----------------------------------------
Xray/Shadowsocks Account
-----------------------------------------
Remarks     : {username}
Domain      : $domain
User Quota  : {quota} GB
User Ip     : {total_iplimit} IP
Port Non TLS: 80,8080,2086,8880
Port TLS    : 443,8443
Password    : $uuid
Cipers      : $cipher
Network     : ws/grpc
Path        : /ss-ws
ServiceName : ss-grpc
-----------------------------------------
Link WS TLS : $ss_ws_tls
-----------------------------------------
Link WS None TLS : $ss_ws_ntls
-----------------------------------------
Link GRPC : $ss_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/ss-{username}.txt
-----------------------------------------
Aktif Selama   : {duration} Hari
Dibuat Pada    : $(date +"%d %b, %Y")
Berakhir Pada  : $(date -d "{duration} days" +"%d %b, %Y")
-----------------------------------------
END

echo "SUCCESS: Shadowsocks Account created for {username}"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success and ("SUCCESS" in output or "success" in output.lower()):
        # Ekstrak UUID dari output
        uuid_value = ""
        for line in output.split('\n'):
            if 'Password' in line:
                uuid_value = line.split(': ')[1].strip()
                break
        
        if not uuid_value:
            uuid_value = str(uuid.uuid4())
        
        # Buat link Shadowsocks
        ss_config = f"aes-128-gcm:{uuid_value}"
        ss_base64 = base64.b64encode(ss_config.encode()).decode()
        ss_ws_tls = f"ss://{ss_base64}@{domain}:443?path=/ss-ws&security=tls&encryption=none&type=ws&host={domain}&sni={domain}#{username}"
        ss_ws_ntls = f"ss://{ss_base64}@{domain}:80?path=/ss-ws&security=none&encryption=none&type=ws&host={domain}#{username}"
        ss_grpc = f"ss://{ss_base64}@{domain}:443?mode=gun&security=tls&encryption=none&type=grpc&serviceName=ss-grpc&sni={domain}#{username}"
        
        account_data = {
            "service_type": "ss",
            "username": username,
            "vps_id": vps["id"],
            "domain": domain,
            "uuid": uuid_value,
            "cipher": "aes-128-gcm",
            "ip_limit": total_iplimit,
            "base_ip_limit": iplimit,
            "extra_ips": extra_ips,
            "quota": quota,
            "ss_ws_tls": ss_ws_tls,
            "ss_ws_ntls": ss_ws_ntls,
            "ss_grpc": ss_grpc,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=duration)).isoformat(),
            "duration": duration
        }
        
        return True, "✅ Akun Shadowsocks berhasil dibuat!", account_data
    else:
        return False, f"❌ Gagal membuat akun Shadowsocks: {output[:500]}", {}

async def create_zivpn_account(vps: Dict, username: str, duration: int, 
                             iplimit: int = 2, extra_ips: int = 0) -> Tuple[bool, str, Dict]:
    """Buat akun ZiVPN via SSH ke VPS"""
    
    domain = vps.get("domain", "super.oxygencrc.my.id")
    
    # Hitung total IP limit
    total_iplimit = iplimit + extra_ips
    
    command = f"""
#!/bin/bash

# CONFIGURATION
CONFIG_FILE="/etc/zivpn/config.json"
USER_DB="/etc/zivpn/users.json"
SERVICE="zivpn"
BACKUP_DIR="/etc/zivpn/backups"

# Function to get server IP
get_server_ip() {{
    if command -v curl &>/dev/null; then
        ip=$(curl -s https://api.ipify.org)
    elif command -v wget &>/dev/null; then
        ip=$(wget -qO- https://api.ipify.org)
    else
        ip=$(hostname -I | awk '{{print $1}}')
    fi
    echo "$ip"
}}

# Input data
user="{username}"
pass="$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 12 | head -n 1)"
masaaktif="{duration}"
exp=$(date -d "+{duration} days" "+%Y-%m-%d")

# Check if username exists
if jq -e ".users.\\"$user\\"" "$USER_DB" >/dev/null 2>&1; then
    echo "ERROR: Username '$user' already exists!"
    exit 1
fi

# Backup config
timestamp=$(date +"%Y%m%d_%H%M%S")
cp "$CONFIG_FILE" "${{CONFIG_FILE}}.backup_${{timestamp}}"

# Add password to config
if jq --arg p "$pass" '.auth.config += [$p]' "$CONFIG_FILE" > /tmp/zivpn_tmp.json 2>/dev/null; then
    mv /tmp/zivpn_tmp.json "$CONFIG_FILE"
else
    echo "ERROR: Failed to update config file"
    exit 1
fi

# Add to user database
current_date=$(date "+%Y-%m-%d %H:%M:%S")
jq --arg user "$user" \
   --arg pass "$pass" \
   --arg expiry "$exp" \
   --arg created "$current_date" \
   '.users[$user] = {{
       password: $pass,
       created_date: $created,
       expiry_date: $expiry,
       last_login: null,
       device_count: 0,
       is_active: true,
       is_trial: false,
       user_type: "regular",
       ip_limit: {total_iplimit}
   }}' "$USER_DB" > /tmp/zivpn_user_tmp.json 2>/dev/null && mv /tmp/zivpn_user_tmp.json "$USER_DB"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to update user database"
    exit 1
fi

# Restart service
systemctl restart $SERVICE 2>/dev/null

# Get server info
SERVER_IP=$(get_server_ip)

echo "SUCCESS: ZiVPN Account created for $user"
echo "USERNAME: $user"
echo "PASSWORD: $pass"
echo "EXPIRY: $exp"
echo "IP_LIMIT: {total_iplimit}"
echo "SERVER_IP: $SERVER_IP"
echo "DOMAIN: {domain}"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success and ("SUCCESS" in output or "success" in output.lower()):
        # Ekstrak data dari output
        password = ""
        server_ip = ""
        expiry_date = ""
        
        for line in output.split('\n'):
            if 'PASSWORD:' in line:
                password = line.split(': ')[1].strip()
            elif 'SERVER_IP:' in line:
                server_ip = line.split(': ')[1].strip()
            elif 'EXPIRY:' in line:
                expiry_date = line.split(': ')[1].strip()
        
        if not password:
            password = str(uuid.uuid4())[:12]
        if not server_ip:
            server_ip = vps["ip"]
        if not expiry_date:
            expiry_date = (datetime.now() + timedelta(days=duration)).strftime("%Y-%m-%d")
        
        account_data = {
            "service_type": "zivpn",
            "username": username,
            "password": password,
            "vps_id": vps["id"],
            "domain": domain,
            "server_ip": server_ip,
            "ip_limit": total_iplimit,
            "base_ip_limit": iplimit,
            "extra_ips": extra_ips,
            "created_at": datetime.now().isoformat(),
            "expires_at": expiry_date,
            "duration": duration
        }
        
        return True, "✅ Akun ZiVPN berhasil dibuat!", account_data
    else:
        return False, f"❌ Gagal membuat akun ZiVPN: {output[:500]}", {}

    
# ============================================
# FUNGSI TRIAL VPN
# ============================================

async def create_ssh_trial(vps: Dict, username: str) -> Tuple[bool, str, Dict]:
    """Buat trial SSH 40 menit dengan tampilan lengkap"""
    password = str(uuid.uuid4())[:8]
    domain = vps.get("domain", "super.oxygencrc.my.id")
    duration_minutes = 40
    
    command = f"""
#!/bin/bash
export TIME="10"
IP=$(curl -sS ipv4.icanhazip.com)
CITY=$(curl -s ipinfo.io/city)
domain="{domain}"
NS=$(cat /etc/xray/dns 2>/dev/null || echo "")
PUB=$(cat /etc/slowdns/server.pub 2>/dev/null || echo "")

# Data dari input
user="{username}"
Pass="{password}"
iplimit="1"
Quota="1"
masaaktif="40"  # dalam menit

# Buat akun SSH
if [[ $iplimit -gt 0 ]]; then
mkdir -p /etc/limit/ssh/ip
echo -e "$iplimit" > /etc/limit/ssh/ip/$user
fi

# Hitung waktu kedaluwarsa (40 menit dari sekarang)
expiry_date=$(date -d "+40 minutes" +"%Y-%m-%d %H:%M:%S")
useradd -e "$(date -d '+40 minutes' +'%Y-%m-%d %H:%M:%S')" -s /bin/false -M $user
echo -e "$Pass\\n$Pass\\n" | passwd $user &> /dev/null

# Setup quota
if [[ $Quota != "0" ]]; then
d=$((${{Quota}} * 1024 * 1024 * 1024))
echo "$d" >/etc/ssh/$user
fi

# Simpan ke database
echo "#ssh_trial# $user $Pass $Quota $iplimit $expiry_date" >> /etc/ssh/.ssh.db

# Buat file detail
mkdir -p /detail/ssh/
cat > /detail/ssh/$user.txt <<-END
-----------------------------------------
SSH Trial Account (40 Minutes)
-----------------------------------------
Host             : $domain
IP               : $IP
Username         : $user
Password         : $Pass
-----------------------------------------
Limit Quota      : $Quota GB
Limit Ip         : $iplimit IP
Host Slowdns     : $NS
Pub Key          : $PUB
Port OpenSSH     : 22
Port DNS         : 53 ,2222
Port SSH UDP     : 1-65529
Port Dropbear    : 22, 109
Port SSH WS      : 80,8080,2086,8880
Port SSH WS SSL  : 443,8443
Port SSL/TLS     : 443
BadVPN UDP       : 7100, 7300, 7300
-----------------------------------------
HTTP CUSTOM      : $domain:1-65529@$user:$Pass
-----------------------------------------
Payload          : GET /cdn-cgi/trace HTTP/1.1[crlf]Host: Bug_Kalian[crlf][crlf]GET-RAY / HTTP/1.1[crlf]Host: [host]
-----------------------------------------
Save Link Account: https://$domain:81/ssh-$user.txt
-----------------------------------------
Aktif Selama     : 40 Menit (Trial)
Dibuat Pada      : $(date +"%d %b, %Y %H:%M:%S")
Berakhir Pada    : $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

# Buat file untuk download
cat > /var/www/html/ssh-$user.txt <<-END
-----------------------------------------
SSH Trial Account (40 Minutes)
-----------------------------------------
Host             : $domain
IP               : $IP
Username         : $user
Password         : $Pass
-----------------------------------------
Limit Quota      : $Quota GB
Limit Ip         : $iplimit IP
Host Slowdns     : $NS
Pub Key          : $PUB
Port OpenSSH     : 22
Port DNS         : 53 ,2222
Port SSH UDP     : 1-65529
Port Dropbear    : 22, 109
Port SSH WS      : 80,8080,2086,8880
Port SSH WS SSL  : 443,8443
Port SSL/TLS     : 443
BadVPN UDP       : 7100, 7300, 7300
-----------------------------------------
HTTP CUSTOM      : $domain:1-65529@$user:$Pass
-----------------------------------------
Payload          : GET /cdn-cgi/trace HTTP/1.1[crlf]Host: Bug_Kalian[crlf][crlf]GET-RAY / HTTP/1.1[crlf]Host: [host]
-----------------------------------------
Save Link Account: https://$domain:81/ssh-$user.txt
-----------------------------------------
Aktif Selama     : 40 Menit (Trial)
Dibuat Pada      : $(date +"%d %b, %Y %H:%M:%S")
Berakhir Pada    : $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

echo "SUCCESS: SSH Trial Account created for $user"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success:
        account_data = {
            "service_type": "ssh",
            "username": username,
            "password": password,
            "vps_id": vps["id"],
            "domain": domain,
            "server_ip": vps["ip"],
            "ip_limit": 1,
            "quota": 1,
            "is_trial": True,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "trial_minutes": duration_minutes
        }
        trial_id = add_trial_account(account_data)
        account_data["trial_id"] = trial_id
        return True, "✅ Trial SSH berhasil dibuat!", account_data
    return False, f"❌ Gagal membuat trial SSH: {output[:500]}", {}

async def create_vmess_trial(vps: Dict, username: str) -> Tuple[bool, str, Dict]:
    """Buat trial VMess 40 menit dengan tampilan lengkap"""
    domain = vps.get("domain", "super.oxygencrc.my.id")
    uuid_value = str(uuid.uuid4())
    duration_minutes = 40
    
    command = f"""
#!/bin/bash
clear
domain="{domain}"
uuid="{uuid_value}"
user="{username}"
masaaktif="40"  # dalam menit
exp=$(date -d "+40 minutes" +"%Y-%m-%d %H:%M:%S")

# Tambahkan ke config.json
sed -i '/#vmess$/a\\###trial '"$user $exp"'\\\n}},{{"id": "'"$uuid"'","alterId": 0,"email": "'"$user"'"' /etc/xray/config.json
sed -i '/#vmessgrpc$/a\\###trial '"$user $exp"'\\\n}},{{"id": "'"$uuid"'","alterId": 0,"email": "'"$user"'"' /etc/xray/config.json

# Buat config VMess
vmess_tls_config='{{
  "v": "2",
  "ps": "{username}-Trial-TLS",
  "add": "$domain",
  "port": "443",
  "id": "$uuid",
  "aid": "0",
  "net": "ws",
  "path": "/vmess",
  "type": "none",
  "host": "$domain",
  "tls": "tls"
}}'

vmess_ntls_config='{{
  "v": "2",
  "ps": "{username}-Trial-NTLS",
  "add": "$domain",
  "port": "80",
  "id": "$uuid",
  "aid": "0",
  "net": "ws",
  "path": "/vmess",
  "type": "none",
  "host": "$domain",
  "tls": "none"
}}'

vmess_grpc_config='{{
  "v": "2",
  "ps": "{username}-Trial-GRPC",
  "add": "$domain",
  "port": "443",
  "id": "$uuid",
  "aid": "0",
  "net": "grpc",
  "path": "vmess-grpc",
  "type": "none",
  "host": "$domain",
  "tls": "tls"
}}'

# Encode ke base64
vmess_tls_base64=$(echo -n "$vmess_tls_config" | base64 -w 0)
vmess_ntls_base64=$(echo -n "$vmess_ntls_config" | base64 -w 0)
vmess_grpc_base64=$(echo -n "$vmess_grpc_config" | base64 -w 0)

# Restart service
systemctl restart xray > /dev/null 2>&1

# Setup limit
mkdir -p /etc/limit/vmess/ip
echo -e "1" > /etc/limit/vmess/ip/{username}

# Setup quota
d=$(( 50 * 1024 * 1024 * 1024 ))
echo "$d" > /etc/vmess/{username}

# Simpan ke database
echo "###trial {username} $exp $uuid 50 1" >> /etc/vmess/.vmess.db

# Buat file detail
mkdir -p /detail/vmess/
cat > /detail/vmess/{username}.txt <<-END
-----------------------------------------
CREATE VMESS TRIAL ACCOUNT (40 Minutes)
-----------------------------------------
Username : {username}
Expired (minutes): 40
Limit GB: 50
Limit IP: 1
TYPE: TRIAL ACCOUNT
-----------------------------------------
VMess Trial Account Details:
Username: {username}
UUID: $uuid
Domain: $domain
Quota: 50 GB
IP Limit: 1 IP
Expired: $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
-----------------------------------------
TLS Link: vmess://$vmess_tls_base64
Non-TLS Link: vmess://$vmess_ntls_base64
gRPC Link: vmess://$vmess_grpc_base64
-----------------------------------------
Account file: https://$domain:81/vmess-{username}.txt
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

# Buat file untuk download
cat > /var/www/html/vmess-{username}.txt <<-END
-----------------------------------------
CREATE VMESS TRIAL ACCOUNT (40 Minutes)
-----------------------------------------
Username : {username}
Expired (minutes): 40
Limit GB: 50
Limit IP: 1
TYPE: TRIAL ACCOUNT
-----------------------------------------
VMess Trial Account Details:
Username: {username}
UUID: $uuid
Domain: $domain
Quota: 50 GB
IP Limit: 1 IP
Expired: $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
-----------------------------------------
TLS Link: vmess://$vmess_tls_base64
Non-TLS Link: vmess://$vmess_ntls_base64
gRPC Link: vmess://$vmess_grpc_base64
-----------------------------------------
Account file: https://$domain:81/vmess-{username}.txt
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

echo "SUCCESS: VMess Trial Account created for {username}"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success:
        # Buat link VMess di Python
        vmess_data_tls = {
            "v": "2",
            "ps": f"{username}-Trial-TLS",
            "add": domain,
            "port": "443",
            "id": uuid_value,
            "aid": "0",
            "net": "ws",
            "path": "/vmess",
            "type": "none",
            "host": domain,
            "tls": "tls"
        }
        
        vmess_data_ntls = {
            "v": "2",
            "ps": f"{username}-Trial-NTLS",
            "add": domain,
            "port": "80",
            "id": uuid_value,
            "aid": "0",
            "net": "ws",
            "path": "/vmess",
            "type": "none",
            "host": domain,
            "tls": "none"
        }
        
        vmess_data_grpc = {
            "v": "2",
            "ps": f"{username}-Trial-GRPC",
            "add": domain,
            "port": "443",
            "id": uuid_value,
            "aid": "0",
            "net": "grpc",
            "path": "vmess-grpc",
            "type": "none",
            "host": domain,
            "tls": "tls"
        }
        
        vmess_tls = f"vmess://{base64.b64encode(json.dumps(vmess_data_tls).encode()).decode()}"
        vmess_ntls = f"vmess://{base64.b64encode(json.dumps(vmess_data_ntls).encode()).decode()}"
        vmess_grpc = f"vmess://{base64.b64encode(json.dumps(vmess_data_grpc).encode()).decode()}"
        
        account_data = {
            "service_type": "vmess",
            "username": username,
            "vps_id": vps["id"],
            "domain": domain,
            "uuid": uuid_value,
            "ip_limit": 1,
            "quota": 50,
            "vmess_tls": vmess_tls,
            "vmess_ntls": vmess_ntls,
            "vmess_grpc": vmess_grpc,
            "is_trial": True,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "trial_minutes": duration_minutes
        }
        trial_id = add_trial_account(account_data)
        account_data["trial_id"] = trial_id
        return True, "✅ Trial VMess berhasil dibuat!", account_data
    return False, f"❌ Gagal membuat trial VMess: {output[:500]}", {}

async def user_select_trial_vps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih VPS untuk trial"""
    query = update.callback_query
    await query.answer()
    
    vps_id = query.data.replace("trial_vps_", "")
    vps = get_vps(vps_id)
    
    if not vps:
        text = f"""
{generate_header('SERVER TIDAK DITEMUKAN')}

{generate_separator(29)}
❌ *Server tidak ditemukan!*
{generate_separator(29)}
Server yang Anda pilih tidak ditemukan dalam database.
{generate_separator(29)}
"""
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="user_trial_vpn")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ConversationHandler.END
    
    context.user_data["trial_vps_id"] = vps_id
    service_type = context.user_data["trial_service"]
    service_names = {
        "ssh": "🔐 SSH",
        "vmess": "⚡ VMess", 
        "vless": "🚀 VLESS",
        "trojan": "🛡️ Trojan",
        "ss": "🌓 Shadowsocks",
        "zivpn": "🟦 ZiVPN"
    }
    
    text = f"""
{generate_header('KONFIRMASI TRIAL')}

{generate_separator(29)}
🎯 *Detail Trial VPN*
{generate_separator(29)}
📋 *Konfigurasi Trial:*
├ Layanan: {service_names.get(service_type, service_type.upper())}
├ Server: {vps.get('name', 'VPS')}
├ Domain: {vps.get('domain', 'N/A')}
├ Lokasi: {vps.get('location', 'Unknown')}
├ Durasi: 40 Menit
├ IP Limit: 1 IP
└ Quota: 50 GB
{generate_separator(29)}
⚠️ *Informasi Penting:*
{generate_separator(29)}
📛 **FITUR TRIAL:**
├ 1 trial per user saja
├ Durasi 40 MENIT
├ Tidak bisa diperpanjang
├ Akan otomatis terhapus
└ Hanya untuk testing
{generate_separator(29)}
🎯 *Username akan digenerate otomatis*
{generate_separator(29)}
✅ **KONFIRMASI PEMBUATAN TRIAL?**
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ BUAT TRIAL SEKARANG", callback_data="create_trial"),
            InlineKeyboardButton("❌ BATALKAN", callback_data="user_trial_vpn")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_CREATE_TRIAL
    
    
async def create_vless_trial(vps: Dict, username: str) -> Tuple[bool, str, Dict]:
    """Buat trial VLESS 40 menit dengan tampilan lengkap"""
    domain = vps.get("domain", "super.oxygencrc.my.id")
    uuid_value = str(uuid.uuid4())
    duration_minutes = 40
    
    command = f"""
#!/bin/bash
clear
domain="{domain}"
uuid="{uuid_value}"
user="{username}"
masaaktif="40"  # dalam menit
exp=$(date -d "+40 minutes" +"%Y-%m-%d %H:%M:%S")

# Tambahkan ke config.json
sed -i '/#vless$/a\\#&trial '"$user $exp"'\\\n}},{{"id": "'"$uuid"'","email": "'"$user"'"' /etc/xray/config.json
sed -i '/#vlessgrpc$/a\\#&trial '"$user $exp"'\\\n}},{{"id": "'"$uuid"'","email": "'"$user"'"' /etc/xray/config.json

# Buat link
vless_tls="vless://$uuid@$domain:443?path=/vless&security=tls&encryption=none&type=ws&host=$domain&sni=$domain#{username}-Trial"
vless_ntls="vless://$uuid@$domain:80?path=/vless&encryption=none&type=ws&host=$domain#{username}-Trial"
vless_grpc="vless://$uuid@$domain:443?mode=gun&security=tls&encryption=none&type=grpc&serviceName=vless-grpc&sni=$domain#{username}-Trial"

# Restart service
systemctl restart xray > /dev/null 2>&1

# Setup limit
mkdir -p /etc/limit/vless/ip
echo -e "1" > /etc/limit/vless/ip/{username}

# Setup quota
d=$(( 50 * 1024 * 1024 * 1024 ))
echo "$d" > /etc/vless/{username}

# Simpan ke database
echo "#&trial {username} $exp $uuid 50 1" >> /etc/vless/.vless.db

# Buat file detail
mkdir -p /detail/vless/
cat > /detail/vless/{username}.txt <<-END
-----------------------------------------
Xray/Vless Trial Account (40 Minutes)
-----------------------------------------
Remarks     : {username}
Domain      : $domain
User Quota  : 50 GB
User Ip     : 1 IP
Port Non TLS: 80,8080,2086,8880
Port TLS    : 443,8443
User ID     : $uuid
Encryption  : none
Path TLS    : /vless
ServiceName : vless-grpc
TYPE        : TRIAL ACCOUNT
-----------------------------------------
Link TLS    : $vless_tls
-----------------------------------------
Link NTLS   : $vless_ntls
-----------------------------------------
Link GRPC   : $vless_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/vless-{username}.txt
-----------------------------------------
Aktif Selama     : 40 Menit (Trial)
Dibuat Pada      : $(date +"%d %b, %Y %H:%M:%S")
Berakhir Pada    : $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

# Buat file untuk download
cat > /var/www/html/vless-{username}.txt <<-END
-----------------------------------------
Xray/Vless Trial Account (40 Minutes)
-----------------------------------------
Remarks     : {username}
Domain      : $domain
User Quota  : 50 GB
User Ip     : 1 IP
Port Non TLS: 80,8080,2086,8880
Port TLS    : 443,8443
User ID     : $uuid
Encryption  : none
Path TLS    : /vless
ServiceName : vless-grpc
TYPE        : TRIAL ACCOUNT
-----------------------------------------
Link TLS    : $vless_tls
-----------------------------------------
Link NTLS   : $vless_ntls
-----------------------------------------
Link GRPC   : $vless_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/vless-{username}.txt
-----------------------------------------
Aktif Selama     : 40 Menit (Trial)
Dibuat Pada      : $(date +"%d %b, %Y %H:%M:%S")
Berakhir Pada    : $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

echo "SUCCESS: VLESS Trial Account created for {username}"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success:
        # Buat link VLESS
        vless_tls = f"vless://{uuid_value}@{domain}:443?path=/vless&security=tls&encryption=none&type=ws&host={domain}&sni={domain}#{username}-Trial"
        vless_ntls = f"vless://{uuid_value}@{domain}:80?path=/vless&encryption=none&type=ws&host={domain}#{username}-Trial"
        vless_grpc = f"vless://{uuid_value}@{domain}:443?mode=gun&security=tls&encryption=none&type=grpc&serviceName=vless-grpc&sni={domain}#{username}-Trial"
        
        account_data = {
            "service_type": "vless",
            "username": username,
            "vps_id": vps["id"],
            "domain": domain,
            "uuid": uuid_value,
            "ip_limit": 1,
            "quota": 50,
            "vless_tls": vless_tls,
            "vless_ntls": vless_ntls,
            "vless_grpc": vless_grpc,
            "is_trial": True,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "trial_minutes": duration_minutes
        }
        trial_id = add_trial_account(account_data)
        account_data["trial_id"] = trial_id
        return True, "✅ Trial VLESS berhasil dibuat!", account_data
    return False, f"❌ Gagal membuat trial VLESS: {output[:500]}", {}

async def create_trojan_trial(vps: Dict, username: str) -> Tuple[bool, str, Dict]:
    """Buat trial Trojan 40 menit dengan tampilan lengkap"""
    domain = vps.get("domain", "super.oxygencrc.my.id")
    uuid_value = str(uuid.uuid4())
    duration_minutes = 40
    
    command = f"""
#!/bin/bash
clear
domain="{domain}"
uuid="{uuid_value}"
user="{username}"
masaaktif="40"  # dalam menit
exp=$(date -d "+40 minutes" +"%Y-%m-%d %H:%M:%S")

# Tambahkan ke config.json
sed -i '/#trojanws$/a\\#!trial '"$user $exp"'\\\n}},{{"password": "'"$uuid"'","email": "'"$user"'"' /etc/xray/config.json
sed -i '/#trojangrpc$/a\\#!trial '"$user $exp"'\\\n}},{{"password": "'"$uuid"'","email": "'"$user"'"' /etc/xray/config.json

# Buat link
trojan_ws="trojan://$uuid@$domain:443?path=%2Ftrojan-ws&security=tls&host=$domain&type=ws&sni=$domain#{username}-Trial"
trojan_grpc="trojan://$uuid@$domain:443?mode=gun&security=tls&type=grpc&serviceName=trojan-grpc&sni=$domain#{username}-Trial"

# Restart service
systemctl restart xray > /dev/null 2>&1

# Setup limit
mkdir -p /etc/limit/trojan/ip
echo -e "1" > /etc/limit/trojan/ip/{username}

# Setup quota
d=$(( 50 * 1024 * 1024 * 1024 ))
echo "$d" > /etc/trojan/{username}

# Simpan ke database
echo "#!trial {username} $exp $uuid 50 1" >> /etc/trojan/.trojan.db

# Buat file detail
mkdir -p /detail/trojan/
cat > /detail/trojan/{username}.txt <<-END
-----------------------------------------
Xray/Trojan Trial Account (40 Minutes)
-----------------------------------------
Remarks          : {username}
Host/IP          : $domain
User Quota       : 50 GB
User Ip          : 1 IP
Port             : 443,8443
Key              : $uuid
Path             : /trojan-ws
ServiceName      : trojan-grpc
TYPE             : TRIAL ACCOUNT
-----------------------------------------
Link TLS         : $trojan_ws
-----------------------------------------
Link GRPC        : $trojan_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/trojan-{username}.txt
-----------------------------------------
Aktif Selama     : 40 Menit (Trial)
Dibuat Pada      : $(date +"%d %b, %Y %H:%M:%S")
Berakhir Pada    : $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

# Buat file untuk download
cat > /var/www/html/trojan-{username}.txt <<-END
-----------------------------------------
Xray/Trojan Trial Account (40 Minutes)
-----------------------------------------
Remarks          : {username}
Host/IP          : $domain
User Quota       : 50 GB
User Ip          : 1 IP
Port             : 443,8443
Key              : $uuid
Path             : /trojan-ws
ServiceName      : trojan-grpc
TYPE             : TRIAL ACCOUNT
-----------------------------------------
Link TLS         : $trojan_ws
-----------------------------------------
Link GRPC        : $trojan_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/trojan-{username}.txt
-----------------------------------------
Aktif Selama     : 40 Menit (Trial)
Dibuat Pada      : $(date +"%d %b, %Y %H:%M:%S")
Berakhir Pada    : $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

echo "SUCCESS: Trojan Trial Account created for {username}"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success:
        # Buat link Trojan
        trojan_ws = f"trojan://{uuid_value}@{domain}:443?path=%2Ftrojan-ws&security=tls&host={domain}&type=ws&sni={domain}#{username}-Trial"
        trojan_grpc = f"trojan://{uuid_value}@{domain}:443?mode=gun&security=tls&type=grpc&serviceName=trojan-grpc&sni={domain}#{username}-Trial"
        
        account_data = {
            "service_type": "trojan",
            "username": username,
            "vps_id": vps["id"],
            "domain": domain,
            "uuid": uuid_value,
            "ip_limit": 1,
            "quota": 50,
            "trojan_ws": trojan_ws,
            "trojan_grpc": trojan_grpc,
            "is_trial": True,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "trial_minutes": duration_minutes
        }
        trial_id = add_trial_account(account_data)
        account_data["trial_id"] = trial_id
        return True, "✅ Trial Trojan berhasil dibuat!", account_data
    return False, f"❌ Gagal membuat trial Trojan: {output[:500]}", {}

async def create_ss_trial(vps: Dict, username: str) -> Tuple[bool, str, Dict]:
    """Buat trial Shadowsocks 40 menit dengan tampilan lengkap"""
    domain = vps.get("domain", "super.oxygencrc.my.id")
    password = str(uuid.uuid4())[:12]
    duration_minutes = 40
    
    command = f"""
#!/bin/bash
clear
domain="{domain}"
pass="{password}"
cipher="aes-128-gcm"
user="{username}"
masaaktif="40"  # dalam menit
exp=$(date -d "+40 minutes" +"%Y-%m-%d %H:%M:%S")

# Tambahkan ke config.json
sed -i '/#ssws$/a\\#@&trial '"$user $exp"'\\\n}},{{"password": "'"$pass"'","method": "'"$cipher"'","email": "'"$user"'"' /etc/xray/config.json
sed -i '/#ssgrpc$/a\\#@&trial '"$user $exp"'\\\n}},{{"password": "'"$pass"'","method": "'"$cipher"'","email": "'"$user"'"' /etc/xray/config.json

# Buat config Shadowsocks
ss_config="$cipher:$pass"
ss_base64=$(echo -n "$ss_config" | base64)

# Buat link
ss_ws_tls="ss://$ss_base64@$domain:443?path=/ss-ws&security=tls&encryption=none&type=ws&host=$domain&sni=$domain#{username}-Trial"
ss_ws_ntls="ss://$ss_base64@$domain:80?path=/ss-ws&security=none&encryption=none&type=ws&host=$domain#{username}-Trial"
ss_grpc="ss://$ss_base64@$domain:443?mode=gun&security=tls&encryption=none&type=grpc&serviceName=ss-grpc&sni=$domain#{username}-Trial"

# Restart service
systemctl restart xray > /dev/null 2>&1

# Setup limit
mkdir -p /etc/limit/shadowsocks/ip
echo -e "1" > /etc/limit/shadowsocks/ip/{username}

# Setup quota
d=$(( 50 * 1024 * 1024 * 1024 ))
echo "$d" > /etc/shadowsocks/{username}

# Simpan ke database
echo "#@&trial {username} $exp $pass 50 1" >> /etc/shadowsocks/.shadowsocks.db

# Buat file detail
mkdir -p /detail/shadowsocks/
cat > /detail/shadowsocks/{username}.txt <<-END
-----------------------------------------
Xray/Shadowsocks Trial Account (40 Minutes)
-----------------------------------------
Remarks     : {username}
Domain      : $domain
User Quota  : 50 GB
User Ip     : 1 IP
Port Non TLS: 80,8080,2086,8880
Port TLS    : 443,8443
Password    : $pass
Cipers      : $cipher
Network     : ws/grpc
Path        : /ss-ws
ServiceName : ss-grpc
TYPE        : TRIAL ACCOUNT
-----------------------------------------
Link WS TLS : $ss_ws_tls
-----------------------------------------
Link WS None TLS : $ss_ws_ntls
-----------------------------------------
Link GRPC : $ss_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/ss-{username}.txt
-----------------------------------------
Aktif Selama   : 40 Menit (Trial)
Dibuat Pada    : $(date +"%d %b, %Y %H:%M:%S")
Berakhir Pada  : $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

# Buat file untuk download
cat > /var/www/html/ss-{username}.txt <<-END
-----------------------------------------
Xray/Shadowsocks Trial Account (40 Minutes)
-----------------------------------------
Remarks     : {username}
Domain      : $domain
User Quota  : 50 GB
User Ip     : 1 IP
Port Non TLS: 80,8080,2086,8880
Port TLS    : 443,8443
Password    : $pass
Cipers      : $cipher
Network     : ws/grpc
Path        : /ss-ws
ServiceName : ss-grpc
TYPE        : TRIAL ACCOUNT
-----------------------------------------
Link WS TLS : $ss_ws_tls
-----------------------------------------
Link WS None TLS : $ss_ws_ntls
-----------------------------------------
Link GRPC : $ss_grpc
-----------------------------------------
Format OpenClash : https://$domain:81/ss-{username}.txt
-----------------------------------------
Aktif Selama   : 40 Menit (Trial)
Dibuat Pada    : $(date +"%d %b, %Y %H:%M:%S")
Berakhir Pada  : $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

echo "SUCCESS: Shadowsocks Trial Account created for {username}"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success:
        # Buat link Shadowsocks
        ss_config = f"aes-128-gcm:{password}"
        ss_base64 = base64.b64encode(ss_config.encode()).decode()
        ss_ws_tls = f"ss://{ss_base64}@{domain}:443?path=/ss-ws&security=tls&encryption=none&type=ws&host={domain}&sni={domain}#{username}-Trial"
        ss_ws_ntls = f"ss://{ss_base64}@{domain}:80?path=/ss-ws&security=none&encryption=none&type=ws&host={domain}#{username}-Trial"
        ss_grpc = f"ss://{ss_base64}@{domain}:443?mode=gun&security=tls&encryption=none&type=grpc&serviceName=ss-grpc&sni={domain}#{username}-Trial"
        
        account_data = {
            "service_type": "ss",
            "username": username,
            "vps_id": vps["id"],
            "domain": domain,
            "password": password,
            "cipher": "aes-128-gcm",
            "ip_limit": 1,
            "quota": 50,
            "ss_ws_tls": ss_ws_tls,
            "ss_ws_ntls": ss_ws_ntls,
            "ss_grpc": ss_grpc,
            "is_trial": True,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "trial_minutes": duration_minutes
        }
        trial_id = add_trial_account(account_data)
        account_data["trial_id"] = trial_id
        return True, "✅ Trial Shadowsocks berhasil dibuat!", account_data
    return False, f"❌ Gagal membuat trial Shadowsocks: {output[:500]}", {}

async def create_zivpn_trial(vps: Dict, username: str) -> Tuple[bool, str, Dict]:
    """Buat trial ZiVPN 40 menit dengan tampilan lengkap"""
    domain = vps.get("domain", "super.oxygencrc.my.id")
    password = str(uuid.uuid4())[:12]
    duration_minutes = 40
    
    command = f"""
#!/bin/bash

# CONFIGURATION
CONFIG_FILE="/etc/zivpn/config.json"
USER_DB="/etc/zivpn/users.json"
SERVICE="zivpn"
BACKUP_DIR="/etc/zivpn/backups"

# Function to get server IP
get_server_ip() {{
    if command -v curl &>/dev/null; then
        ip=$(curl -s https://api.ipify.org)
    elif command -v wget &>/dev/null; then
        ip=$(wget -qO- https://api.ipify.org)
    else
        ip=$(hostname -I | awk '{{print $1}}')
    fi
    echo "$ip"
}}

# Input data
user="{username}"
pass="{password}"
masaaktif="40"  # dalam menit
exp=$(date -d "+40 minutes" +"%Y-%m-%d %H:%M:%S")

# Check if username exists
if [ -f "$USER_DB" ] && jq -e ".users.\\"$user\\"" "$USER_DB" >/dev/null 2>&1; then
    echo "ERROR: Username '$user' already exists!"
    exit 1
fi

# Backup config
timestamp=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"
cp "$CONFIG_FILE" "${{BACKUP_DIR}}/config.backup_${{timestamp}}"

# Add password to config
if jq --arg p "$pass" '.auth.config += [$p]' "$CONFIG_FILE" > /tmp/zivpn_tmp.json 2>/dev/null; then
    mv /tmp/zivpn_tmp.json "$CONFIG_FILE"
else
    echo "ERROR: Failed to update config file"
    exit 1
fi

# Create or update user database
if [ ! -f "$USER_DB" ]; then
    echo '{{"users": {{}}}}' > "$USER_DB"
fi

# Add to user database
current_date=$(date "+%Y-%m-%d %H:%M:%S")
jq --arg user "$user" \
   --arg pass "$pass" \
   --arg expiry "$exp" \
   --arg created "$current_date" \
   '.users[$user] = {{
       password: $pass,
       created_date: $created,
       expiry_date: $expiry,
       last_login: null,
       device_count: 0,
       is_active: true,
       is_trial: true,
       user_type: "trial",
       ip_limit: 1
   }}' "$USER_DB" > /tmp/zivpn_user_tmp.json 2>/dev/null && mv /tmp/zivpn_user_tmp.json "$USER_DB"

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to update user database"
    exit 1
fi

# Restart service
systemctl restart $SERVICE 2>/dev/null

# Get server info
SERVER_IP=$(get_server_ip)

# Buat file detail
mkdir -p /detail/zivpn/
cat > /detail/zivpn/{username}.txt <<-END
-----------------------------------------
ZiVPN Trial Account (40 Minutes)
-----------------------------------------
Username : {username}
Password : {password}
Domain   : {domain}
Server IP: $SERVER_IP
IP Limit : 1
Type     : TRIAL ACCOUNT
-----------------------------------------
Account Information:
Username: {username}
Password: {password}
Expired: $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
Created: $(date +"%d %b, %Y %H:%M:%S")
-----------------------------------------
Configuration:
- Protocol: ZiVPN
- Port: 443
- IP Limit: 1 device
- Trial: 40 minutes
-----------------------------------------
Account file: https://{domain}:81/zivpn-{username}.txt
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

# Buat file untuk download
cat > /var/www/html/zivpn-{username}.txt <<-END
-----------------------------------------
ZiVPN Trial Account (40 Minutes)
-----------------------------------------
Username : {username}
Password : {password}
Domain   : {domain}
Server IP: $SERVER_IP
IP Limit : 1
Type     : TRIAL ACCOUNT
-----------------------------------------
Account Information:
Username: {username}
Password: {password}
Expired: $(date -d "+40 minutes" +"%d %b, %Y %H:%M:%S")
Created: $(date +"%d %b, %Y %H:%M:%S")
-----------------------------------------
Configuration:
- Protocol: ZiVPN
- Port: 443
- IP Limit: 1 device
- Trial: 40 minutes
-----------------------------------------
Account file: https://{domain}:81/zivpn-{username}.txt
-----------------------------------------
NOTE: This is a TRIAL account valid for 40 minutes only
-----------------------------------------
END

echo "SUCCESS: ZiVPN Trial Account created for {username}"
echo "USERNAME: {username}"
echo "PASSWORD: {password}"
echo "EXPIRY: $exp"
echo "IP_LIMIT: 1"
echo "SERVER_IP: $SERVER_IP"
echo "DOMAIN: {domain}"
"""
    
    success, output = await execute_ssh_command(
        vps["ip"],
        vps.get("ssh_port", 22),
        vps["ssh_user"],
        vps["ssh_pass"],
        command
    )
    
    if success:
        account_data = {
            "service_type": "zivpn",
            "username": username,
            "password": password,
            "vps_id": vps["id"],
            "domain": domain,
            "server_ip": vps["ip"],
            "ip_limit": 1,
            "is_trial": True,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=duration_minutes)).isoformat(),
            "trial_minutes": duration_minutes
        }
        trial_id = add_trial_account(account_data)
        account_data["trial_id"] = trial_id
        return True, "✅ Trial ZiVPN berhasil dibuat!", account_data
    return False, f"❌ Gagal membuat trial ZiVPN: {output[:500]}", {}
    
# ============================================
# PRICE UTILITIES
# ============================================

def get_actual_price(vps_id: str, service_type: str, duration: str) -> int:
    """Get harga aktual (cek harga server, jika tidak ada gunakan harga default)"""
    server_price = get_server_price(vps_id, service_type, duration)
    if server_price is not None:
        return server_price
    
    prices = get_prices()
    return prices.get(service_type, {}).get(duration, 0)

def calculate_extra_ip_cost(extra_ips: int) -> int:
    """Hitung biaya tambahan IP"""
    global EXTRA_IP_PRICE
    return extra_ips * EXTRA_IP_PRICE

def update_extra_ip_price(new_price: int):
    """Update harga IP tambahan"""
    global EXTRA_IP_PRICE
    EXTRA_IP_PRICE = new_price

# ============================================
# HANDLERS - USER
# ============================================

async def user_upgrade_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu upgrade akun"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if not user.get("vpn_accounts"):
        text = f"""
{generate_header('UPGRADE AKUN')}

{generate_separator(29)}
📭 *Tidak Ada Akun Ditemukan*
{generate_separator(29)}
Anda belum memiliki akun VPN yang bisa di-upgrade.
Silakan beli akun terlebih dahulu.
{generate_separator(29)}
"""
        keyboard = [
            [InlineKeyboardButton("🛒 Beli VPN", callback_data="user_buy_vpn")],
            [InlineKeyboardButton("🔙 Menu Utama", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ConversationHandler.END
    
    text = f"""
{generate_header('UPGRADE AKUN')}

{generate_separator(29)}
🔄 *Pilih Akun untuk Upgrade*
{generate_separator(29)}
Pilih akun yang ingin Anda upgrade:
"""
    
    keyboard = []
    for i, account in enumerate(user["vpn_accounts"][:10]):  # Max 10 akun
        username = account.get("username", "N/A")
        service = account.get("service_type", "ssh").upper()
        expires = account.get("expires_at", "")
        expires_text = format_date(expires) if expires else "N/A"
        
        button_text = f"👤 {username} ({service}) - {expires_text}"
        callback_data = f"upgrade_select_{i}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("🔙 Menu Utama", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_SELECT_UPGRADE_TYPE

async def user_select_upgrade_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih tipe upgrade"""
    query = update.callback_query
    await query.answer()
    
    account_index = int(query.data.replace("upgrade_select_", ""))
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if account_index >= len(user["vpn_accounts"]):
        await query.edit_message_text("❌ Akun tidak ditemukan.")
        return ConversationHandler.END
    
    account = user["vpn_accounts"][account_index]
    context.user_data["upgrade_account"] = account
    context.user_data["upgrade_account_index"] = account_index
    
    username = account.get("username", "N/A")
    service = account.get("service_type", "ssh").upper()
    expires = account.get("expires_at", "")
    expires_text = format_date(expires) if expires else "N/A"
    current_ip_limit = account.get("ip_limit", 1)
    
    text = f"""
{generate_header('PILIH UPGRADE')}

{generate_separator(29)}
👤 *Akun:* {username}
🔧 *Layanan:* {service}
⏳ *Expired:* {expires_text}
🌐 *IP Limit Saat Ini:* {current_ip_limit} IP
{generate_separator(29)}

Pilih tipe upgrade yang diinginkan:
"""
    
    keyboard = [
        [InlineKeyboardButton("⏳ Perpanjang Masa Aktif", callback_data="upgrade_extend")],
        [InlineKeyboardButton("🌐 Tambah IP Limit", callback_data="upgrade_ip_limit")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="user_upgrade_account")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_UPGRADE_EXTEND

async def user_upgrade_extend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Perpanjang masa aktif dengan pilihan upgrade quota dan IP limit"""
    query = update.callback_query
    await query.answer()
    
    account = context.user_data["upgrade_account"]
    username = account.get("username", "N/A")
    service_type = account.get("service_type", "ssh").upper()
    current_expires = account.get("expires_at", "")
    current_quota = account.get("quota", 2 if service_type.lower() == "ssh" else 200)
    current_ip_limit = account.get("ip_limit", 2)
    
    text = f"""
{generate_header('PERPANJANG MASA AKTIF')}

{generate_separator(29)}
👤 *Akun:* {username}
🔧 *Layanan:* {service_type}
⏳ *Expired Saat Ini:* {format_datetime(current_expires)}
💾 *Quota Saat Ini:* {current_quota} GB
🌐 *IP Limit Saat Ini:* {current_ip_limit} IP
{generate_separator(29)}

📊 *Pilih Durasi Perpanjangan:*
"""
    
    keyboard = []
    durations = {
        "7": "7 Hari",
        "30": "30 Hari", 
        "90": "90 Hari",
        "180": "180 Hari",
        "365": "1 Tahun"
    }
    
    vps_id = account.get("vps_id")
    
    for dur_code, dur_name in durations.items():
        base_price = get_actual_price(vps_id, service_type.lower(), dur_code)
        button_text = f"{dur_name} - {format_money(base_price)}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"extend_{dur_code}")])
    
    # Tambahkan opsi upgrade quota dan IP
    keyboard.append([InlineKeyboardButton("📈 Upgrade Quota", callback_data="upgrade_quota")])
    keyboard.append([InlineKeyboardButton("🌐 Upgrade IP Limit", callback_data="upgrade_ip_limit_extend")])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="user_select_upgrade_type")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_CONFIRM_UPGRADE
    
async def user_upgrade_ip_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upgrade IP limit dengan skala harga"""
    query = update.callback_query
    await query.answer()
    
    account = context.user_data["upgrade_account"]
    username = account.get("username", "N/A")
    service_type = account.get("service_type", "ssh").upper()
    current_ip_limit = account.get("ip_limit", 1)
    base_ip_limit = account.get("base_ip_limit", 1)
    extra_ips = current_ip_limit - base_ip_limit
    
    # Tentukan batas maksimal berdasarkan layanan
    max_ip_limit = 100  # Default
    if service_type.lower() in ["ssh", "zivpn"]:
        max_ip_limit = 10  # SSH dan ZiVPN biasanya lebih kecil
    elif service_type.lower() in ["vmess", "vless", "trojan", "ss"]:
        max_ip_limit = 50  # Xray services bisa lebih banyak
    
    text = f"""
{generate_header('UPGRADE IP LIMIT')}

{generate_separator(29)}
👤 *Akun:* {username}
🔧 *Layanan:* {service_type}
🌐 *IP Limit Saat Ini:* {current_ip_limit} IP
├ IP Base: {base_ip_limit} IP
└ IP Tambahan: {extra_ips} IP
{generate_separator(29)}

💰 *Harga per IP tambahan:* {format_money(EXTRA_IP_PRICE)}
📊 *Batas Maksimal:* {max_ip_limit} IP
{generate_separator(29)}

Pilih jumlah IP tambahan yang ingin ditambahkan:
"""
    
    keyboard = []
    for i in range(1, 11):  # Max tambah 10 IP per transaksi
        new_total = current_ip_limit + i
        
        if new_total > max_ip_limit:
            continue
        
        cost = i * EXTRA_IP_PRICE
        button_text = f"➕ {i} IP (Total: {new_total} IP) - {format_money(cost)}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"add_ip_{i}")])
    
    # Opsi custom
    keyboard.append([InlineKeyboardButton("📝 Custom Jumlah IP", callback_data="custom_ip_amount")])
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="user_select_upgrade_type")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    context.user_data["upgrade_type"] = "ip_limit"
    return USER_CONFIRM_UPGRADE
    
async def user_confirm_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi upgrade dengan tampilan lengkap"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    account = context.user_data["upgrade_account"]
    user_id = query.from_user.id
    user = get_user(user_id)
    service_type = account.get("service_type", "ssh").lower()
    
    if data.startswith("extend_"):
        duration = int(data.replace("extend_", ""))
        vps_id = account.get("vps_id")
        base_price = get_actual_price(vps_id, service_type, str(duration))
        total_price = base_price
        
        # Tambah opsi upgrade quota jika ada di context
        if "upgrade_quota" in context.user_data:
            quota_upgrade_cost = context.user_data.get("quota_upgrade_cost", 0)
            total_price += quota_upgrade_cost
        
        upgrade_type = "perpanjangan"
        upgrade_desc = f"Perpanjang {duration} hari"
        
        text = f"""
{generate_header('KONFIRMASI PERPANJANGAN')}

{generate_separator(29)}
✅ *Konfirmasi Perpanjangan Masa Aktif*
{generate_separator(29)}
👤 *Akun:* {account.get('username')}
🔧 *Layanan:* {service_type.upper()}
⏳ *Durasi:* {duration} hari
💰 *Biaya Perpanjangan:* {format_money(base_price)}
"""
        
        # Tambah info quota upgrade jika ada
        if "new_quota" in context.user_data:
            new_quota = context.user_data["new_quota"]
            quota_cost = context.user_data.get("quota_upgrade_cost", 0)
            text += f"💾 *Quota Baru:* {new_quota} GB (+{format_money(quota_cost)})"
        
        text += f"""
💰 *Total Biaya:* {format_money(total_price)}
{generate_separator(29)}
💰 *Saldo Anda:* {format_money(user['balance'])}
💰 *Saldo Setelah:* {format_money(user['balance'] - total_price)}
{generate_separator(29)}
"""
    
    elif data.startswith("add_ip_"):
        extra_ips = int(data.replace("add_ip_", ""))
        current_ip_limit = account.get("ip_limit", 1)
        new_ip_limit = current_ip_limit + extra_ips
        total_price = extra_ips * EXTRA_IP_PRICE
        
        upgrade_type = "ip_limit"
        upgrade_desc = f"Tambah {extra_ips} IP"
        
        text = f"""
{generate_header('KONFIRMASI TAMBAH IP')}

{generate_separator(29)}
✅ *Konfirmasi Tambah IP Limit*
{generate_separator(29)}
👤 *Akun:* {account.get('username')}
🔧 *Layanan:* {service_type.upper()}
🌐 *IP Saat Ini:* {current_ip_limit} IP
🌐 *IP Baru:* {new_ip_limit} IP
➕ *Tambahan:* {extra_ips} IP
💰 *Biaya per IP:* {format_money(EXTRA_IP_PRICE)}
💰 *Total Biaya:* {format_money(total_price)}
{generate_separator(29)}
💰 *Saldo Anda:* {format_money(user['balance'])}
💰 *Saldo Setelah:* {format_money(user['balance'] - total_price)}
{generate_separator(29)}
"""
    
    else:
        await query.edit_message_text("❌ Upgrade tidak valid.")
        return ConversationHandler.END
    
    if user["balance"] < total_price:
        text += f"""
❌ *SALDO TIDAK CUKUP!*
{generate_separator(29)}
"""
        keyboard = [
            [InlineKeyboardButton("💰 Top Up Saldo", callback_data="user_topup")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="user_select_upgrade_type")]
        ]
    else:
        text += f"""
⚠️ *Apakah Anda yakin melanjutkan upgrade?*
{generate_separator(29)}
"""
        keyboard = [
            [
                InlineKeyboardButton("✅ KONFIRMASI UPGRADE", callback_data=f"do_upgrade_{data}"),
                InlineKeyboardButton("❌ BATALKAN", callback_data="user_select_upgrade_type")
            ]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END
        
async def do_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Eksekusi upgrade dengan script lengkap"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.replace("do_upgrade_", "")
    account = context.user_data["upgrade_account"]
    account_index = context.user_data["upgrade_account_index"]
    user_id = query.from_user.id
    user = get_user(user_id)
    vps = get_vps(account.get("vps_id"))
    service_type = account.get("service_type", "ssh")
    
    # Update user accounts list FIRST
    user_accounts = user.get("vpn_accounts", [])
    
    processing_msg = await query.edit_message_text(
        f"""
{generate_header('MEMPROSES UPGRADE')}

{generate_separator(29)}
⏳ *Memproses upgrade akun...*
{generate_separator(29)}
Layanan: {service_type.upper()}
Akun: {account.get('username')}
Harap tunggu sebentar.
{generate_separator(29)}
"""
    )
    
    try:
        if data.startswith("extend_"):
            duration = int(data.replace("extend_", ""))
            base_price = get_actual_price(account.get("vps_id"), service_type, str(duration))
            total_price = base_price
            
            # Tambah quota upgrade cost jika ada
            if "quota_upgrade_cost" in context.user_data:
                total_price += context.user_data["quota_upgrade_cost"]
                new_quota = context.user_data.get("new_quota", account.get("quota"))
            else:
                new_quota = account.get("quota")
            
            # Update expiry date
            try:
                current_expires = datetime.fromisoformat(account.get("expires_at"))
                new_expires = current_expires + timedelta(days=duration)
            except:
                # Jika format tanggal bermasalah, mulai dari sekarang
                new_expires = datetime.now() + timedelta(days=duration)
            
            account["expires_at"] = new_expires.isoformat()
            account["duration"] = account.get("duration", 0) + duration
            
            # Update quota jika ada perubahan
            if new_quota != account.get("quota"):
                account["quota"] = new_quota
            
            # Update di server via SSH dengan script lengkap
            success, output = await update_account_on_server_extended(
                vps, 
                account, 
                "extend", 
                days=duration,
                new_quota=new_quota
            )
            
            upgrade_type = "Perpanjangan"
            upgrade_desc = f"Perpanjang {duration} hari"
            
            if success and "SUCCESS" in output:
                # Parse output untuk mendapatkan info
                output_lines = output.split('\n')
                for line in output_lines:
                    if "Expires on" in line or "Expired On" in line:
                        expiry_info = line.split(':')[1].strip()
                        break
                else:
                    expiry_info = new_expires.strftime("%d %b %Y")
                
                success_msg = f"✅ Akun berhasil diperpanjang hingga {expiry_info}"
                if new_quota != account.get("quota", 0):
                    success_msg += f"\n💾 Quota baru: {new_quota} GB"
            
            else:
                success = False
                error_msg = output[:500]
        
        elif data.startswith("add_ip_"):
            extra_ips = int(data.replace("add_ip_", ""))
            total_price = extra_ips * EXTRA_IP_PRICE
            
            # Update IP limit
            current_ip = account.get("ip_limit", 1)
            account["ip_limit"] = current_ip + extra_ips
            account["extra_ips"] = account.get("extra_ips", 0) + extra_ips
            
            # Update di server via SSH
            success, output = await update_account_on_server_extended(
                vps, 
                account, 
                "ip_limit",
                extra_ips=extra_ips
            )
            
            upgrade_type = "Tambah IP"
            upgrade_desc = f"Tambah {extra_ips} IP"
            
            if success and "SUCCESS" in output:
                success_msg = f"✅ IP limit berhasil ditingkatkan menjadi {account['ip_limit']} IP"
            else:
                success = False
                error_msg = output[:500]
        
        else:
            success = False
            error_msg = "Tipe upgrade tidak dikenali"
        
        if success:
            # Update balance
            new_balance = user["balance"] - total_price
            update_user(user_id, {
                "balance": new_balance,
                "total_spent": user.get("total_spent", 0) + total_price
            })
            
            # Update account in user data - FIXED
            if account_index < len(user_accounts):
                user_accounts[account_index] = account
            else:
                user_accounts.append(account)
            
            update_user(user_id, {"vpn_accounts": user_accounts})
            
            # Update in accounts database
            accounts = load_json(ACCOUNTS_DB)
            account_updated = False
            for acc_id, acc_data in accounts.items():
                if acc_data.get("username") == account.get("username"):
                    accounts[acc_id].update(account)
                    account_updated = True
                    break
            
            if not account_updated:
                # Add as new account if not found
                account_id = add_account(account)
            
            save_json(ACCOUNTS_DB, accounts)
            
            # Add transaction
            add_transaction({
                "user_id": user_id,
                "type": "upgrade",
                "amount": total_price,
                "description": f"Upgrade {upgrade_desc} untuk akun {account.get('username')} ({service_type})",
                "status": "completed",
                "created_at": datetime.now().isoformat()
            })
            
            # Tampilkan info yang sudah diupdate
            expires_display = format_datetime(account.get("expires_at", ""))
            
            text = f"""
{generate_header('UPGRADE BERHASIL')}

{generate_separator(29)}
✅ *UPGRADE BERHASIL DIPROSES!*
{generate_separator(29)}
📋 *Detail Upgrade:*
├ Tipe: {upgrade_type}
├ Akun: {account.get('username')}
├ Layanan: {service_type.upper()}
├ {upgrade_desc}
├ Biaya: {format_money(total_price)}
└ Saldo Baru: {format_money(new_balance)}
{generate_separator(29)}
🎯 *Status Akun Terupdate:*
├ Expiry Baru: {expires_display}
├ IP Limit: {account.get('ip_limit', 2)} IP
└ Quota: {account.get('quota', 2)} GB
{generate_separator(29)}
{success_msg}
{generate_separator(29)}
"""
        else:
            text = f"""
{generate_header('UPGRADE GAGAL')}

{generate_separator(29)}
❌ *UPGRADE GAGAL!*
{generate_separator(29)}
Gagal memproses upgrade akun.
{generate_separator(29)}
📛 *Error Details:*
`{error_msg}`
{generate_separator(29)}
🔄 *Silakan coba lagi atau hubungi admin.*
{generate_separator(29)}
"""
    
    except Exception as e:
        text = f"""
{generate_header('UPGRADE GAGAL')}

{generate_separator(29)}
❌ *ERROR: {str(e)}*
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔍 Cek Akun", callback_data="user_check_account")],
        [InlineKeyboardButton("🔄 Upgrade Lain", callback_data="user_upgrade_account")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await processing_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END        

# Tambahkan fungsi-fungsi ini setelah fungsi do_upgrade

async def handle_upgrade_quota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle upgrade quota"""
    query = update.callback_query
    await query.answer()
    
    account = context.user_data["upgrade_account"]
    username = account.get("username", "N/A")
    service_type = account.get("service_type", "ssh").upper()
    current_quota = account.get("quota", 2 if service_type.lower() == "ssh" else 200)
    
    text = f"""
{generate_header('UPGRADE QUOTA')}

{generate_separator(29)}
👤 *Akun:* {username}
🔧 *Layanan:* {service_type}
💾 *Quota Saat Ini:* {current_quota} GB
{generate_separator(29)}

Masukkan quota baru (dalam GB):
📝 *Contoh:* 50, 100, 200, 500

💰 *Note:* Harga disesuaikan dengan layanan
"""
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return USER_UPGRADE_QUOTA

async def handle_quota_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input quota baru"""
    quota_input = update.message.text.strip()
    
    if not quota_input.isdigit():
        await update.message.reply_text("❌ Quota harus angka. Masukkan quota dalam GB:")
        return USER_UPGRADE_QUOTA
    
    new_quota = int(quota_input)
    account = context.user_data["upgrade_account"]
    current_quota = account.get("quota", 2)
    
    if new_quota <= current_quota:
        await update.message.reply_text(f"❌ Quota baru harus lebih besar dari {current_quota} GB. Masukkan quota baru:")
        return USER_UPGRADE_QUOTA
    
    # Hitung biaya (contoh: 1000 per GB tambahan)
    extra_gb = new_quota - current_quota
    cost_per_gb = 1000  # Rp 1,000 per GB
    total_cost = extra_gb * cost_per_gb
    
    context.user_data["new_quota"] = new_quota
    context.user_data["quota_upgrade_cost"] = total_cost
    
    text = f"""
{generate_header('KONFIRMASI UPGRADE QUOTA')}

{generate_separator(29)}
✅ *Konfirmasi Upgrade Quota*
{generate_separator(29)}
👤 *Akun:* {account.get('username')}
🔧 *Layanan:* {account.get('service_type', 'ssh').upper()}
💾 *Quota Lama:* {current_quota} GB
💾 *Quota Baru:* {new_quota} GB
➕ *Tambahan:* {extra_gb} GB
💰 *Biaya per GB:* {format_money(cost_per_gb)}
💰 *Total Biaya:* {format_money(total_cost)}
{generate_separator(29)}
⚠️ *Apakah Anda yakin ingin upgrade quota?*
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ KONFIRMASI", callback_data="confirm_quota_upgrade"),
            InlineKeyboardButton("❌ BATALKAN", callback_data="user_upgrade_extend")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_CONFIRM_UPGRADE_QUOTA

async def handle_quota_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle konfirmasi upgrade quota"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_quota_upgrade":
        await query.edit_message_text(
            f"""
{generate_header('UPGRADE QUOTA DIBATALKAN')}

{generate_separator(29)}
❌ *Upgrade quota dibatalkan.*
{generate_separator(29)}
Tidak ada perubahan yang dilakukan.
{generate_separator(29)}
"""
        )
        return ConversationHandler.END
    
    # Proses upgrade quota
    account = context.user_data["upgrade_account"]
    new_quota = context.user_data["new_quota"]
    quota_cost = context.user_data["quota_upgrade_cost"]
    user_id = query.from_user.id
    user = get_user(user_id)
    vps = get_vps(account.get("vps_id"))
    
    processing_msg = await query.edit_message_text(
        f"""
{generate_header('MEMPROSES UPGRADE QUOTA')}

{generate_separator(29)}
⏳ *Memproses upgrade quota...*
{generate_separator(29)}
Harap tunggu sebentar.
{generate_separator(29)}
"""
    )
    
    try:
        # Update quota di server
        success, output = await update_account_on_server_extended(
            vps,
            account,
            "extend",  # Gunakan extend dengan quota baru
            new_quota=new_quota
        )
        
        if success:
            # Update balance
            new_balance = user["balance"] - quota_cost
            update_user(user_id, {
                "balance": new_balance,
                "total_spent": user.get("total_spent", 0) + quota_cost
            })
            
            # Update account
            account["quota"] = new_quota
            
            # Update in user data
            user_accounts = user.get("vpn_accounts", [])
            for i, acc in enumerate(user_accounts):
                if acc.get("username") == account.get("username"):
                    user_accounts[i] = account
                    break
            update_user(user_id, {"vpn_accounts": user_accounts})
            
            # Update in accounts database
            accounts = load_json(ACCOUNTS_DB)
            for acc_id, acc_data in accounts.items():
                if acc_data.get("username") == account.get("username"):
                    accounts[acc_id]["quota"] = new_quota
                    break
            save_json(ACCOUNTS_DB, accounts)
            
            # Add transaction
            add_transaction({
                "user_id": user_id,
                "type": "upgrade_quota",
                "amount": quota_cost,
                "description": f"Upgrade quota ke {new_quota} GB untuk akun {account.get('username')}",
                "status": "completed",
                "created_at": datetime.now().isoformat()
            })
            
            text = f"""
{generate_header('UPGRADE QUOTA BERHASIL')}

{generate_separator(29)}
✅ *Upgrade Quota Berhasil!*
{generate_separator(29)}
📋 *Detail Upgrade:*
├ Akun: {account.get('username')}
├ Layanan: {account.get('service_type', 'ssh').upper()}
├ Quota Lama: {account.get('quota_old', 'N/A')} GB
├ Quota Baru: {new_quota} GB
├ Biaya: {format_money(quota_cost)}
└ Saldo Baru: {format_money(new_balance)}
{generate_separator(29)}
🎉 *Quota Anda telah berhasil diupgrade!*
{generate_separator(29)}
"""
        else:
            text = f"""
{generate_header('UPGRADE QUOTA GAGAL')}

{generate_separator(29)}
❌ *Upgrade Quota Gagal!*
{generate_separator(29)}
Gagal memproses upgrade quota.
{generate_separator(29)}
📛 *Error Details:*
`{output[:300]}`
{generate_separator(29)}
"""
    
    except Exception as e:
        text = f"""
{generate_header('UPGRADE QUOTA GAGAL')}

{generate_separator(29)}
❌ *ERROR: {str(e)[:200]}*
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔍 Cek Akun", callback_data="user_check_account")],
        [InlineKeyboardButton("🔄 Upgrade Lain", callback_data="user_upgrade_account")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await processing_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def handle_custom_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom IP amount"""
    query = update.callback_query
    await query.answer()
    
    account = context.user_data["upgrade_account"]
    username = account.get("username", "N/A")
    service_type = account.get("service_type", "ssh").upper()
    current_ip_limit = account.get("ip_limit", 1)
    
    # Tentukan batas maksimal
    max_ip_limit = 100
    if service_type.lower() in ["ssh", "zivpn"]:
        max_ip_limit = 10
    elif service_type.lower() in ["vmess", "vless", "trojan", "ss"]:
        max_ip_limit = 50
    
    text = f"""
{generate_header('CUSTOM IP TAMBAHAN')}

{generate_separator(29)}
👤 *Akun:* {username}
🔧 *Layanan:* {service_type}
🌐 *IP Limit Saat Ini:* {current_ip_limit} IP
💰 *Harga per IP:* {format_money(EXTRA_IP_PRICE)}
📊 *Batas Maksimal:* {max_ip_limit} IP
{generate_separator(29)}

Masukkan jumlah IP tambahan yang diinginkan:
📝 *Contoh:* 3, 5, 10, 20
"""
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return USER_UPGRADE_CUSTOM_IP

async def handle_custom_ip_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input custom IP amount"""
    ip_input = update.message.text.strip()
    
    if not ip_input.isdigit():
        await update.message.reply_text("❌ Jumlah harus angka. Masukkan jumlah IP:")
        return USER_UPGRADE_CUSTOM_IP
    
    extra_ips = int(ip_input)
    account = context.user_data["upgrade_account"]
    current_ip_limit = account.get("ip_limit", 1)
    service_type = account.get("service_type", "ssh").lower()
    
    # Tentukan batas maksimal
    max_ip_limit = 100
    if service_type in ["ssh", "zivpn"]:
        max_ip_limit = 10
    elif service_type in ["vmess", "vless", "trojan", "ss"]:
        max_ip_limit = 50
    
    new_ip_limit = current_ip_limit + extra_ips
    
    if extra_ips <= 0:
        await update.message.reply_text("❌ Jumlah IP harus lebih dari 0. Masukkan jumlah IP:")
        return USER_UPGRADE_CUSTOM_IP
    
    if new_ip_limit > max_ip_limit:
        await update.message.reply_text(
            f"❌ Jumlah IP melebihi batas maksimal ({max_ip_limit} IP).\n" +
            f"IP Saat Ini: {current_ip_limit} IP\n" +
            f"Maksimal tambahan: {max_ip_limit - current_ip_limit} IP\n" +
            "Masukkan jumlah yang valid:"
        )
        return USER_UPGRADE_CUSTOM_IP
    
    total_price = extra_ips * EXTRA_IP_PRICE
    
    context.user_data["custom_extra_ips"] = extra_ips
    context.user_data["custom_ip_cost"] = total_price
    
    text = f"""
{generate_header('KONFIRMASI CUSTOM IP')}

{generate_separator(29)}
✅ *Konfirmasi Tambah IP Custom*
{generate_separator(29)}
👤 *Akun:* {account.get('username')}
🔧 *Layanan:* {service_type.upper()}
🌐 *IP Saat Ini:* {current_ip_limit} IP
🌐 *IP Baru:* {new_ip_limit} IP
➕ *Tambahan:* {extra_ips} IP
💰 *Biaya per IP:* {format_money(EXTRA_IP_PRICE)}
💰 *Total Biaya:* {format_money(total_price)}
{generate_separator(29)}
⚠️ *Apakah Anda yakin ingin menambah IP?*
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ KONFIRMASI", callback_data=f"add_ip_{extra_ips}"),
            InlineKeyboardButton("❌ BATALKAN", callback_data="user_upgrade_ip_limit")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_CONFIRM_UPGRADE

async def user_confirm_upgrade_quota(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi upgrade quota (redirect ke handler utama)"""
    query = update.callback_query
    await query.answer()
    
    # Simpan data quota ke context untuk diproses bersama extend
    if "new_quota" in context.user_data:
        # Redirect ke konfirmasi extend dengan quota
        data = query.data.replace("confirm_quota_", "")
        await user_confirm_upgrade(update, context)
    else:
        await query.edit_message_text("❌ Data quota tidak ditemukan.")
        return ConversationHandler.END
        
        
async def update_account_on_server(vps: Dict, account: Dict, upgrade_type: str, value: int) -> bool:
    """Update akun di server SSH"""
    try:
        service_type = account.get("service_type")
        username = account.get("username")
        
        if upgrade_type == "extend":
            # Perpanjang masa aktif
            if service_type == "ssh":
                command = f"""
                chage -E $(date -d "+{value} days" +"%Y-%m-%d") {username}
                sed -i "s/#ssh# {username} .*/#ssh# {username} $(grep '#ssh# {username}' /etc/ssh/.ssh.db | cut -d' ' -f3-5) $(date -d '+{value} days' '+%d %b, %Y')/" /etc/ssh/.ssh.db
                echo "SUCCESS: Account extended"
                """
            elif service_type in ["vmess", "vless", "trojan", "ss"]:
                new_expiry = (datetime.now() + timedelta(days=value)).strftime("%Y-%m-%d")
                db_file = f"/etc/{service_type}/.{service_type}.db"
                command = f"""
                sed -i "s/.*{username}.*/{account.get('uuid', '')} {username} {new_expiry} {account.get('quota', 200)} {account.get('ip_limit', 2)}/" {db_file}
                echo "SUCCESS: Account extended"
                """
        
        elif upgrade_type == "ip_limit":
            # Tambah IP limit
            new_ip_limit = account.get("ip_limit", 1)
            if service_type == "ssh":
                command = f"""
                mkdir -p /etc/limit/ssh/ip
                echo "{new_ip_limit}" > /etc/limit/ssh/ip/{username}
                sed -i "s/#ssh# {username} .*/#ssh# {username} $(grep '#ssh# {username}' /etc/ssh/.ssh.db | cut -d' ' -f3-4) {new_ip_limit} $(grep '#ssh# {username}' /etc/ssh/.ssh.db | cut -d' ' -f6-)/" /etc/ssh/.ssh.db
                echo "SUCCESS: IP limit updated"
                """
            elif service_type in ["vmess", "vless", "trojan", "ss"]:
                command = f"""
                mkdir -p /etc/limit/{service_type}/ip
                echo "{new_ip_limit}" > /etc/limit/{service_type}/ip/{username}
                sed -i "s/.*{username}.*/{account.get('uuid', '')} {username} $(grep '{username}' /etc/{service_type}/.{service_type}.db | cut -d' ' -f3-4) {account.get('quota', 200)} {new_ip_limit}/" /etc/{service_type}/.{service_type}.db
                echo "SUCCESS: IP limit updated"
                """
        
        success, output = await execute_ssh_command(
            vps["ip"],
            vps.get("ssh_port", 22),
            vps["ssh_user"],
            vps["ssh_pass"],
            command
        )
        
        return success and "SUCCESS" in output
        
    except Exception as e:
        print(f"Error updating account on server: {e}")
        return False
        
async def admin_set_ip_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set IP limit default"""
    query = update.callback_query
    await query.answer()
    
    vps_list = get_all_vps()
    active_vps = {k: v for k, v in vps_list.items() if v.get("status") == "active"}
    
    if not active_vps:
        text = f"""
{generate_header('SET IP LIMIT DEFAULT')}

{generate_separator(29)}
⚠️ *Tidak Ada Server Aktif*
{generate_separator(29)}
Belum ada server VPS aktif.
{generate_separator(29)}
"""
        keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ConversationHandler.END
    
    text = f"""
{generate_header('SET IP LIMIT DEFAULT')}

{generate_separator(29)}
🌐 *Set IP Limit Default*
{generate_separator(29)}
Pilih server untuk set IP limit default:
"""
    
    keyboard = []
    for vps_id, vps in active_vps.items():
        name = vps.get('name', f"VPS {vps['ip']}")
        domain = vps.get('domain', 'N/A')
        vps_type = vps.get('type', 'regular')
        type_icon = "🟦" if vps_type == "zivpn" else "🟩"
        
        button_text = f"{type_icon} {name} ({domain})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"ip_limit_vps_{vps_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ADMIN_SET_IP_LIMIT_SELECT

# ============================================
# BROADCAST HANDLERS
# ============================================

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast process"""
    query = update.callback_query
    if query:
        await query.answer()
    
    text = f"""
{generate_header('📢 BROADCAST MESSAGE')}

{generate_separator(29)}
📤 *BROADCAST KE SEMUA USER*
{generate_separator(29)}
Pilih tipe broadcast yang ingin dikirim:
"""
    
    keyboard = [
        [InlineKeyboardButton("📝 Text Only", callback_data="broadcast_type_text")],
        [InlineKeyboardButton("🖼️ Text dengan Foto", callback_data="broadcast_type_photo")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_panel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return BROADCAST_TYPE

async def admin_broadcast_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast type selection"""
    query = update.callback_query
    await query.answer()
    
    broadcast_type = query.data.replace("broadcast_type_", "")
    context.user_data["broadcast_type"] = broadcast_type
    
    if broadcast_type == "text":
        text = f"""
{generate_header('📢 BROADCAST TEXT')}

{generate_separator(29)}
📝 *BROADCAST TEXT ONLY*
{generate_separator(29)}
Kirimkan pesan yang ingin di-broadcast:

💡 *Formatting:*
• Gunakan markdown untuk formatting
• Contoh: *tebal*, _miring_, `code`
• Emoji: ✅ ❌ ⚠️ 🔥 🎉
{generate_separator(29)}
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    else:  # photo
        text = f"""
{generate_header('📢 BROADCAST DENGAN FOTO')}

{generate_separator(29)}
🖼️ *BROADCAST TEXT DENGAN FOTO*
{generate_separator(29)}
Kirimkan foto terlebih dahulu:
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return BROADCAST_MESSAGE

async def admin_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast message input"""
    broadcast_type = context.user_data.get("broadcast_type", "text")
    
    if broadcast_type == "text":
        if not update.message or not update.message.text:
            await update.message.reply_text("❌ Mohon kirim teks untuk broadcast.")
            return BROADCAST_MESSAGE
        
        message_text = update.message.text
        context.user_data["broadcast_message"] = message_text
        
        # Preview broadcast
        text = f"""
{generate_header('📢 PREVIEW BROADCAST')}

{generate_separator(29)}
✅ *PREVIEW PESAN BROADCAST*
{generate_separator(29)}
{message_text}
{generate_separator(29)}
👥 *Akan dikirim ke:* Semua user
📊 *Estimasi:* {len(load_json(USERS_DB))} user
{generate_separator(29)}
⚠️ *Konfirmasi broadcast?*
"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ KONFIRMASI BROADCAST", callback_data="broadcast_confirm"),
                InlineKeyboardButton("❌ BATALKAN", callback_data="admin_broadcast")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        
    else:  # photo
        if not update.message or not update.message.photo:
            await update.message.reply_text("❌ Mohon kirim foto untuk broadcast.")
            return BROADCAST_MESSAGE
        
        # Simpan foto ID
        photo_file = update.message.photo[-1]
        context.user_data["broadcast_photo_id"] = photo_file.file_id
        
        # Minta caption
        text = f"""
{generate_header('📢 BROADCAST DENGAN FOTO')}

{generate_separator(29)}
✅ *Foto telah diterima!*
{generate_separator(29)}
Sekarang kirimkan caption/teks untuk foto:
💡 *Formatting:* Dukung markdown
"""
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
        return BROADCAST_CONFIRM
    
    return ConversationHandler.END

async def admin_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast confirmation for photo with caption"""
    if not update.message or not update.message.text:
        await update.message.reply_text("❌ Mohon kirim caption untuk foto.")
        return BROADCAST_CONFIRM
    
    caption_text = update.message.text
    context.user_data["broadcast_message"] = caption_text
    
    # Preview broadcast dengan foto
    text = f"""
{generate_header('📢 PREVIEW BROADCAST')}

{generate_separator(29)}
✅ *PREVIEW BROADCAST DENGAN FOTO*
{generate_separator(29)}
📸 *Caption:*
{caption_text}
{generate_separator(29)}
👥 *Akan dikirim ke:* Semua user
📊 *Estimasi:* {len(load_json(USERS_DB))} user
{generate_separator(29)}
⚠️ *Konfirmasi broadcast?*
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ KONFIRMASI BROADCAST", callback_data="broadcast_confirm"),
            InlineKeyboardButton("❌ BATALKAN", callback_data="admin_broadcast")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def admin_execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute broadcast dengan animasi loading"""
    query = update.callback_query
    await query.answer()
    
    broadcast_type = context.user_data.get("broadcast_type", "text")
    message_text = context.user_data.get("broadcast_message", "")
    photo_id = context.user_data.get("broadcast_photo_id")
    
    # Animasi loading
    loading_messages = [
        "⏳ *Mempersiapkan broadcast...*",
        "📊 *Mengumpulkan data user...*",
        "👥 *Menyiapkan daftar penerima...*",
        "🚀 *Memulai proses broadcast...*"
    ]
    
    progress_msg = await query.edit_message_text(
        f"""
{generate_header('📢 BROADCAST PROSES')}

{generate_separator(29)}
{loading_messages[0]}
{generate_separator(29)}
🔄 *Proses akan dimulai...*
📊 Total user: {len(load_json(USERS_DB))}
⏱️ Estimasi waktu: 30-60 detik
{generate_separator(29)}
""",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Update animasi loading
    for i, msg in enumerate(loading_messages[1:], 1):
        await asyncio.sleep(1)
        await progress_msg.edit_text(
            f"""
{generate_header('📢 BROADCAST PROSES')}

{generate_separator(29)}
{msg}
{generate_separator(29)}
🔄 *Proses sedang berjalan...*
📊 Total user: {len(load_json(USERS_DB))}
⏱️ Estimasi selesai: {30 - i*5} detik
{generate_separator(29)}
""",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Mulai broadcast
    users = load_json(USERS_DB)
    total_users = len(users)
    successful = 0
    failed = 0
    blocked = 0
    
    await progress_msg.edit_text(
        f"""
{generate_header('📢 BROADCAST PROSES')}

{generate_separator(29)}
✅ *MENGIRIM PESAN...*
{generate_separator(29)}
📤 *Status:* Memulai pengiriman
📊 *Progress:* 0/{total_users}
✅ *Berhasil:* 0
❌ *Gagal:* 0
🚫 *Blocked:* 0
{generate_separator(29)}
""",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Kirim ke setiap user
    for i, (user_id_str, user_data) in enumerate(users.items(), 1):
        try:
            user_id = int(user_id_str)
            
            if broadcast_type == "text":
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:  # photo
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo_id,
                    caption=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            successful += 1
            
            # Update progress setiap 10 user
            if i % 10 == 0 or i == total_users:
                await progress_msg.edit_text(
                    f"""
{generate_header('📢 BROADCAST PROSES')}

{generate_separator(29)}
✅ *MENGIRIM PESAN...*
{generate_separator(29)}
📤 *Status:* Berjalan
📊 *Progress:* {i}/{total_users}
✅ *Berhasil:* {successful}
❌ *Gagal:* {failed}
🚫 *Blocked:* {blocked}
{generate_separator(29)}
""",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Delay untuk menghindari rate limit
            await asyncio.sleep(0.1)
            
        except Exception as e:
            error_msg = str(e)
            if "blocked" in error_msg.lower() or "deactivated" in error_msg.lower():
                blocked += 1
            else:
                failed += 1
    
    # Tampilkan hasil akhir
    result_text = f"""
{generate_header('📢 BROADCAST SELESAI')}

{generate_separator(29)}
✅ *BROADCAST BERHASIL DIKIRIM!*
{generate_separator(29)}
📊 *HASIL PENGIRIMAN:*
├ Total User: {total_users}
├ ✅ Berhasil: {successful}
├ ❌ Gagal: {failed}
└ 🚫 Blocked: {blocked}
{generate_separator(29)}
📈 *STATISTIK:*
├ Success Rate: {successful/total_users*100:.1f}%
├ Delivery Rate: {(successful+blocked)/total_users*100:.1f}%
└ Fail Rate: {failed/total_users*100:.1f}%
{generate_separator(29)}
🎯 *DETAIL:*
"""
    
    if failed > 0:
        result_text += "├ ⚠️ Beberapa user gagal menerima\n"
    if blocked > 0:
        result_text += f"├ 🚫 {blocked} user memblokir bot\n"
    
    result_text += f"└ 📝 Tipe: {'Text' if broadcast_type == 'text' else 'Photo'}\n"
    result_text += f"{generate_separator(29)}"
    
    keyboard = [
        [InlineKeyboardButton("📊 Lihat User Gagal", callback_data=f"show_failed_{failed}_{blocked}")],
        [InlineKeyboardButton("📢 Broadcast Lagi", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await progress_msg.edit_text(result_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    # Log broadcast
    add_broadcast_log({
        "type": broadcast_type,
        "message": message_text[:100] + "..." if len(message_text) > 100 else message_text,
        "total_users": total_users,
        "successful": successful,
        "failed": failed,
        "blocked": blocked,
        "admin_id": query.from_user.id,
        "created_at": datetime.now().isoformat()
    })
    
    return ConversationHandler.END
        
async def admin_execute_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute broadcast dengan animasi loading"""
    query = update.callback_query
    await query.answer()
    
    broadcast_type = context.user_data.get("broadcast_type", "text")
    message_text = context.user_data.get("broadcast_message", "")
    photo_id = context.user_data.get("broadcast_photo_id")
    
    # Animasi loading
    loading_messages = [
        "⏳ *Mempersiapkan broadcast...*",
        "📊 *Mengumpulkan data user...*",
        "👥 *Menyiapkan daftar penerima...*",
        "🚀 *Memulai proses broadcast...*"
    ]
    
    progress_msg = await query.edit_message_text(
        f"""
{generate_header('📢 BROADCAST PROSES')}

{generate_separator(29)}
{loading_messages[0]}
{generate_separator(29)}
🔄 *Proses akan dimulai...*
📊 Total user: {len(load_json(USERS_DB))}
⏱️ Estimasi waktu: 30-60 detik
{generate_separator(29)}
""",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Update animasi loading
    for i, msg in enumerate(loading_messages[1:], 1):
        await asyncio.sleep(1)
        await progress_msg.edit_text(
            f"""
{generate_header('📢 BROADCAST PROSES')}

{generate_separator(29)}
{msg}
{generate_separator(29)}
🔄 *Proses sedang berjalan...*
📊 Total user: {len(load_json(USERS_DB))}
⏱️ Estimasi selesai: {30 - i*5} detik
{generate_separator(29)}
""",
            parse_mode=ParseMode.MARKDOWN
        )
    
    # Mulai broadcast
    users = load_json(USERS_DB)
    total_users = len(users)
    successful = 0
    failed = 0
    blocked = 0
    
    await progress_msg.edit_text(
        f"""
{generate_header('📢 BROADCAST PROSES')}

{generate_separator(29)}
✅ *MENGIRIM PESAN...*
{generate_separator(29)}
📤 *Status:* Memulai pengiriman
📊 *Progress:* 0/{total_users}
✅ *Berhasil:* 0
❌ *Gagal:* 0
🚫 *Blocked:* 0
{generate_separator(29)}
""",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Kirim ke setiap user
    for i, (user_id_str, user_data) in enumerate(users.items(), 1):
        try:
            user_id = int(user_id_str)
            
            if broadcast_type == "text":
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:  # photo
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo_id,
                    caption=message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            successful += 1
            
            # Update progress setiap 10 user
            if i % 10 == 0 or i == total_users:
                await progress_msg.edit_text(
                    f"""
{generate_header('📢 BROADCAST PROSES')}

{generate_separator(29)}
✅ *MENGIRIM PESAN...*
{generate_separator(29)}
📤 *Status:* Berjalan
📊 *Progress:* {i}/{total_users}
✅ *Berhasil:* {successful}
❌ *Gagal:* {failed}
🚫 *Blocked:* {blocked}
{generate_separator(29)}
""",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Delay untuk menghindari rate limit
            await asyncio.sleep(0.1)
            
        except Exception as e:
            error_msg = str(e)
            if "blocked" in error_msg.lower() or "deactivated" in error_msg.lower():
                blocked += 1
            else:
                failed += 1
    
    # Tampilkan hasil akhir
    result_text = f"""
{generate_header('📢 BROADCAST SELESAI')}

{generate_separator(29)}
✅ *BROADCAST BERHASIL DIKIRIM!*
{generate_separator(29)}
📊 *HASIL PENGIRIMAN:*
├ Total User: {total_users}
├ ✅ Berhasil: {successful}
├ ❌ Gagal: {failed}
└ 🚫 Blocked: {blocked}
{generate_separator(29)}
📈 *STATISTIK:*
├ Success Rate: {successful/total_users*100:.1f}%
├ Delivery Rate: {(successful+blocked)/total_users*100:.1f}%
└ Fail Rate: {failed/total_users*100:.1f}%
{generate_separator(29)}
🎯 *DETAIL:*
"""
    
    if failed > 0:
        result_text += "├ ⚠️ Beberapa user gagal menerima\n"
    if blocked > 0:
        result_text += f"├ 🚫 {blocked} user memblokir bot\n"
    
    result_text += f"└ 📝 Tipe: {'Text' if broadcast_type == 'text' else 'Photo'}\n"
    result_text += f"{generate_separator(29)}"
    
    keyboard = [
        [InlineKeyboardButton("📊 Lihat User Gagal", callback_data=f"show_failed_{failed}_{blocked}")],
        [InlineKeyboardButton("📢 Broadcast Lagi", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await progress_msg.edit_text(result_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    # Log broadcast
    add_broadcast_log({
        "type": broadcast_type,
        "message": message_text[:100] + "..." if len(message_text) > 100 else message_text,
        "total_users": total_users,
        "successful": successful,
        "failed": failed,
        "blocked": blocked,
        "admin_id": query.from_user.id,
        "created_at": datetime.now().isoformat()
    })
    
    return ConversationHandler.END

# Fungsi bantuan untuk broadcast
def add_broadcast_log(data: Dict):
    """Tambahkan log broadcast"""
    broadcast_logs = load_json(f"{DB_FOLDER}/broadcast_logs.json")
    log_id = str(uuid.uuid4())[:8]
    data["id"] = log_id
    broadcast_logs[log_id] = data
    save_json(f"{DB_FOLDER}/broadcast_logs.json", broadcast_logs)
    return log_id

async def show_failed_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan user yang gagal menerima broadcast"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.replace("show_failed_", "")
    failed, blocked = data.split("_")
    
    text = f"""
{generate_header('📊 USER GAGAL BROADCAST')}

{generate_separator(29)}
⚠️ *INFORMASI USER GAGAL*
{generate_separator(29)}
📊 *Statistik Gagal:*
├ ❌ Gagal Kirim: {failed} user
├ 🚫 Blocked Bot: {blocked} user
└ Total Gagal: {int(failed) + int(blocked)} user
{generate_separator(29)}
💡 *Kemungkinan Penyebab:*
1. User memblokir bot
2. Akun user dihapus/dinonaktifkan
3. Koneksi internet user bermasalah
4. Limit Telegram API
{generate_separator(29)}
🔄 *Tindakan:*
• Tidak perlu khawatir, ini normal
• Blocked user akan otomatis terfilter
• User aktif tetap menerima broadcast
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast Lagi", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def admin_broadcast_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tampilkan log broadcast sebelumnya"""
    query = update.callback_query
    await query.answer()
    
    logs = load_json(f"{DB_FOLDER}/broadcast_logs.json")
    
    if not logs:
        text = f"""
{generate_header('📋 LOG BROADCAST')}

{generate_separator(29)}
📭 *Belum Ada Log Broadcast*
{generate_separator(29)}
Belum ada broadcast yang dilakukan.
{generate_separator(29)}
"""
    else:
        text = f"""
{generate_header('📋 LOG BROADCAST')}

{generate_separator(29)}
📊 *Riwayat Broadcast*
{generate_separator(29)}
"""
        
        sorted_logs = sorted(
            logs.values(), 
            key=lambda x: x.get("created_at", ""), 
            reverse=True
        )[:10]  # Tampilkan 10 terbaru
        
        for log in sorted_logs:
            date = format_datetime(log.get("created_at", ""))
            broadcast_type = "Text" if log.get("type") == "text" else "Photo"
            success_rate = (log.get("successful", 0) / log.get("total_users", 1)) * 100
            
            text += f"""
📅 *{date}*
├ Tipe: {broadcast_type}
├ Total: {log.get('total_users', 0)} user
├ Berhasil: {log.get('successful', 0)} user
├ Gagal: {log.get('failed', 0)} user
└ Rate: {success_rate:.1f}%
{generate_separator(20)}
"""
    
    keyboard = [
        [InlineKeyboardButton("📢 Broadcast Baru", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# Command broadcast
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command /broadcast untuk admin"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa menggunakan command ini.")
        return
    
    await admin_broadcast_start(update, context)
               
               
async def admin_set_ip_limit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih server untuk set IP limit"""
    query = update.callback_query
    await query.answer()
    
    vps_id = query.data.replace("ip_limit_vps_", "")
    vps = get_vps(vps_id)
    
    if not vps:
        await query.edit_message_text("❌ Server tidak ditemukan.")
        return ConversationHandler.END
    
    context.user_data["ip_limit_vps_id"] = vps_id
    context.user_data["ip_limit_vps_info"] = vps
    
    vps_type = vps.get("type", "regular")
    
    keyboard = []
    if vps_type == "zivpn":
        services = ["zivpn"]
    else:
        services = ["ssh", "vmess", "vless", "trojan", "ss"]
    
    text = f"""
{generate_header('SET IP LIMIT DEFAULT')}

{generate_separator(29)}
🖥️ *Server:* {vps.get('name', 'VPS')}
🌐 *Domain:* {vps.get('domain', 'N/A')}
🔧 *Tipe:* {'ZiVPN ONLY' if vps_type == 'zivpn' else 'REGULAR'}
{generate_separator(29)}

Pilih layanan untuk set IP limit default:
"""
    
    for service in services:
        icon = {
            "ssh": "🔐", "vmess": "⚡", "vless": "🚀", 
            "trojan": "🛡️", "ss": "🌓", "zivpn": "🟦"
        }.get(service, "🔧")
        keyboard.append([InlineKeyboardButton(f"{icon} {service.upper()}", callback_data=f"ip_limit_service_{service}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="admin_set_ip_limit")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ADMIN_SET_IP_LIMIT_VALUE

# Tambahkan fungsi handler baru
async def handle_ip_limit_service_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle selection of service for IP limit setting"""
    query = update.callback_query
    await query.answer()
    
    service_type = query.data.replace("ip_limit_service_", "")
    context.user_data["ip_limit_service"] = service_type
    
    await query.edit_message_text(
        f"""
{generate_header('SET IP LIMIT DEFAULT')}

{generate_separator(29)}
🔧 Layanan: {service_type.upper()}
{generate_separator(29)}
Masukkan IP limit default (1-100):
"""
    )
    
    return ADMIN_SET_IP_LIMIT_VALUE
        

async def user_topup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses top up"""
    query = update.callback_query
    await query.answer()
    
    # Get user data
    user = get_user(query.from_user.id)
    topup_user = get_topup_user(query.from_user.id)
    
    text = f"""
{generate_header('TOP UP SALDO')}

{generate_separator(29)}
💰 *Top Up Saldo*

📊 **SALDO SAAT INI:** {format_money(user['balance'])}

💳 **SISTEM TOPUP OTOMATIS:**
├─ Scan QRIS & transfer
├─ Validasi otomatis
├─ Saldo bertambah langsung
└─ 24/7 tanpa admin

⚡ **PILIH JUMLAH:**
{generate_separator(29)}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("Rp 2,000", callback_data="topup_2000"),
            InlineKeyboardButton("Rp 5,000", callback_data="topup_5000"),
            InlineKeyboardButton("Rp 7,000", callback_data="topup_7000")
        ],
        [
            InlineKeyboardButton("Rp 10,000", callback_data="topup_10000"),
            InlineKeyboardButton("Rp 15,000", callback_data="topup_15000"),
            InlineKeyboardButton("Rp 20,000", callback_data="topup_20000")
        ],
        [
            InlineKeyboardButton("Rp 25,000", callback_data="topup_25000"),
            InlineKeyboardButton("Rp 30,000", callback_data="topup_30000"),
            InlineKeyboardButton("Rp 50,000", callback_data="topup_50000")
        ],
        [
            InlineKeyboardButton("Rp 75,000", callback_data="topup_75000"),
            InlineKeyboardButton("Rp 100,000", callback_data="topup_100000"),
            InlineKeyboardButton("Rp 150,000", callback_data="topup_150000")
        ],
        [
            InlineKeyboardButton("Rp 200,000", callback_data="topup_200000"),
            InlineKeyboardButton("Rp 250,000", callback_data="topup_250000"),
            InlineKeyboardButton("Rp 500,000", callback_data="topup_500000")
        ],
        [
            InlineKeyboardButton("📋 History", callback_data="topup_history"),
        ],
        [
            InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="back_to_main"),
            InlineKeyboardButton("💰 Cek Saldo", callback_data="user_balance")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
        
        
async def user_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle topup amount selection"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "topup_custom":
        await query.edit_message_text(
            f"💰 **TOPUP CUSTOM**\n\n"
            f"Masukkan jumlah topup (hanya angka):\n\n"
            f"📊 Minimal: Rp {MIN_TOPUP:,}\n"
            f"📊 Maksimal: Rp {MAX_TOPUP:,}\n\n"
            f"Contoh: 25000",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Kembali", callback_data="user_topup")]
            ])
        )
        context.user_data['awaiting_custom_amount'] = True
        return
    
    elif data == "topup_history":
        await user_topup_history(update, context)
        return
    
    # Extract amount from callback data
    amount = int(data.split('_')[1])
    await create_invoice_payment(query.from_user.id, amount, context)

async def user_topup_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom amount input"""
    if 'awaiting_custom_amount' in context.user_data and context.user_data['awaiting_custom_amount']:
        try:
            amount = int(update.message.text)
            
            if amount < MIN_TOPUP:
                await update.message.reply_text(
                    f"❌ **Jumlah Terlalu Kecil**\n\n"
                    f"Minimal topup adalah Rp {MIN_TOPUP:,}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Kembali ke Topup", callback_data="user_topup")]
                    ])
                )
                return
                
            if amount > MAX_TOPUP:
                await update.message.reply_text(
                    f"❌ **Jumlah Terlalu Besar**\n\n"
                    f"Maksimal topup adalah Rp {MAX_TOPUP:,}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Kembali ke Topup", callback_data="user_topup")]
                    ])
                )
                return
            
            await create_invoice_payment(update.effective_user.id, amount, context)
            context.user_data.pop('awaiting_custom_amount', None)
            
        except ValueError:
            await update.message.reply_text(
                "❌ **Format Salah!**\n\n"
                "Harap masukkan angka saja.\n"
                "Contoh: 25000",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Kembali ke Topup", callback_data="user_topup")]
                ])
            )

async def create_invoice_payment(user_id, amount, context):
    """Create invoice for payment"""
    user = get_user(user_id)
    topup_user = get_topup_user(user_id)
    
    # Generate invoice code
    invoice_code, validator = generate_invoice_code(amount)
    transfer_amount = invoice_code
    
    # Add transaction - GUNAKAN FUNGSI YANG BENAR
    transaction = add_topup_transaction(user_id, amount, invoice_code)
    
    # Get active QRIS
    system = get_topup_system()
    qris_path = os.path.join(QRIS_FOLDER, system.get('current_qris', 'qris_default.png'))
    
    # Create invoice message
    expiry_time = datetime.now() + timedelta(minutes=INVOICE_EXPIRY)
    expiry_str = expiry_time.strftime('%H:%M:%S')
    
    invoice_text = (
        f"{generate_header('INVOICE TOPUP')}\n\n"
        f"{generate_separator(29)}\n"
        f"👤 **User:** {user.get('first_name', 'User')}\n"
        f"💰 **Jumlah Topup:** {format_money(amount)}\n"
        f"🔢 **Invoice Code:** `{invoice_code}`\n"
        f"🔐 **Validator:** {validator}\n"
        f"⏰ **Berlaku sampai:** {expiry_str}\n\n"
        f"**📋 PANDUAN PEMBAYARAN:**\n"
        f"1. Scan QRIS di bawah ini\n"
        f"2. **Transfer tepat: {format_money(transfer_amount)}**\n"
        f"3. Sistem otomatis verifikasi dalam 1-2 menit\n\n"
        f"**💡 INFORMASI:**\n"
        f"- Topup: {format_money(amount)}\n"
        f"- Validator: {validator}\n"
        f"- Total transfer: {format_money(transfer_amount)}\n"
        f"- Invoice kadaluarsa setelah {INVOICE_EXPIRY} menit\n"
        f"{generate_separator(29)}"
    )
    
    # Send invoice with QRIS
    keyboard = [
        [
            InlineKeyboardButton("🔄 Cek Status", callback_data=f"check_payment_{invoice_code}"),
            InlineKeyboardButton("💰 Cek Saldo", callback_data="user_balance")
        ],
        [
            InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="back_to_main")
        ]
    ]
    
    if os.path.exists(qris_path):
        with open(qris_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption=invoice_text,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text=invoice_text + "\n\n⚠️ **QRIS tidak tersedia. Hubungi admin.**",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Hubungi Admin", url=f"tg://openmessage?user_id={ADMIN_IDS[0]}" if ADMIN_IDS else "tg://openmessage?user_id=6770986538")]
            ])
        )
    
    # Send confirmation message
    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ **Invoice berhasil dibuat!**\n\n"
             f"**Detail Transfer:**\n"
             f"💰 Topup: {format_money(amount)}\n"
             f"🔐 Validator: {validator}\n"
             f"💳 Transfer: {format_money(transfer_amount)}\n\n"
             f"Silakan scan QRIS dan transfer **{format_money(transfer_amount)}**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="back_to_main")]
        ])
    )
                
async def user_check_payment_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check payment status"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('check_payment_'):
        invoice_code = int(query.data.replace('check_payment_', ''))
        
        # Check transaction status
        data = load_topup_database()
        user_id = query.from_user.id
        
        for uid, user_data in data['users'].items():
            if int(uid) == user_id:
                for transaction in user_data.get('transactions', []):
                    if transaction.get('invoice_code') == invoice_code:
                        status = transaction.get('status', 'pending')
                        amount = transaction.get('amount', 0)
                        
                        if status == 'completed':
                            await query.edit_message_text(
                                f"✅ **PEMBAYARAN BERHASIL!**\n\n"
                                f"💰 Jumlah: {format_money(amount)}\n"
                                f"🔢 Invoice: `{invoice_code}`\n"
                                f"🕒 Waktu: {transaction.get('validated_at', 'N/A')}\n\n"
                                f"Saldo telah ditambahkan ke akun Anda.",
                                parse_mode="Markdown",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("💰 Cek Saldo", callback_data="user_balance")],
                                    [InlineKeyboardButton("🔙 Kembali", callback_data="user_topup")]
                                ])
                            )
                        else:
                            await query.edit_message_text(
                                f"⏳ **MENUNGGU PEMBAYARAN**\n\n"
                                f"💰 Jumlah: {format_money(amount)}\n"
                                f"🔢 Invoice: `{invoice_code}`\n\n"
                                f"Status: {status.upper()}\n"
                                f"Silakan selesaikan pembayaran.",
                                parse_mode="Markdown",
                                reply_markup=InlineKeyboardMarkup([
                                    [InlineKeyboardButton("🔄 Refresh", callback_data=f"check_payment_{invoice_code}")],
                                    [InlineKeyboardButton("🔙 Kembali", callback_data="user_topup")]
                                ])
                            )
                        return
        
        await query.edit_message_text(
            "❌ **Invoice tidak ditemukan**\n\n"
            "Silakan buat invoice baru.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Topup Baru", callback_data="user_topup")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ])
        )

async def user_topup_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show topup history"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    topup_user = get_topup_user(user_id)
    transactions = topup_user.get('transactions', [])
    
    if not transactions:
        text = f"""
{generate_header('RIWAYAT TOPUP')}

{generate_separator(29)}
📋 *Riwayat Transaksi*

Belum ada transaksi topup.

{generate_separator(29)}
"""
    else:
        # Get last 5 transactions
        recent_transactions = transactions[-5:]
        text = f"""
{generate_header('RIWAYAT TOPUP')}

{generate_separator(29)}
📋 *Riwayat Transaksi*

"""
        for i, trans in enumerate(reversed(recent_transactions), 1):
            status = "✅" if trans.get('status') == 'completed' else "⏳"
            amount = trans.get('amount', 0)
            invoice = trans.get('invoice_code', 'N/A')
            time = trans.get('timestamp', 'N/A')[:19].replace('T', ' ')
            
            text += f"{i}. {status} {format_money(amount)}\n"
            text += f"   📄 Invoice: `{invoice}`\n"
            text += f"   🕒 {time}\n\n"
        
        text += f"Total transaksi: {len(transactions)}\n"
        text += generate_separator(29)
    
    keyboard = [
        [InlineKeyboardButton("💳 Topup Baru", callback_data="user_topup")],
        [InlineKeyboardButton("💰 Cek Saldo", callback_data="user_balance")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
    ]
    
    await query.edit_message_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ==================== USER BALANCE HANDLER ====================

async def user_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user balance dengan sistem baru"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Dapatkan summary finansial
    summary = BalanceUpdateHandler.get_user_financial_summary(user_id)
    
    # Cek status rental
    rental_user = rental_db.get_user(user_id)
    rental_info = ""
    if rental_user:
        if rental_db.check_user_access(user_id):
            if rental_user.get("expiry_date") == "lifetime":
                rental_info = "⭐ *Rental:* Lifetime"
            else:
                try:
                    expiry = datetime.fromisoformat(rental_user.get("expiry_date", ""))
                    days_left = (expiry - datetime.now()).days
                    rental_info = f"📦 *Rental:* {days_left} hari lagi"
                except:
                    rental_info = "📦 *Rental:* Aktif"
        else:
            rental_info = "⚠️ *Rental:* Expired"
    
    # Hitung statistik dari database terpisah
    topup_data = load_topup_database()
    topup_user = topup_data.get('users', {}).get(str(user_id), {})
    
    total_transactions = len(topup_user.get('transactions', []))
    completed_transactions = len([t for t in topup_user.get('transactions', []) 
                                 if t.get('status') == 'completed'])
    
    text = f"""
{generate_header('INFORMASI SALDO')}

{generate_separator(29)}
💰 *SALDO ANDA*

👤 User: {update.effective_user.first_name}
💳 Saldo: {format_money(summary['current_balance'])}
{rental_info}

📊 **STATISTIK:**
├─ 💰 Total Topup: {format_money(summary['total_topup'])}
├─ 🛒 Total VPN: {format_money(summary['total_vpn_spent'])}  
├─ 📋 Transaksi Topup: {total_transactions}
└─ ✅ Topup Berhasil: {completed_transactions}

📦 **RENTAL SCRIPT:**
├─ Harga: {format_money(rental_db.get_price_per_month())}/bulan
├─ Slot IP: {len(rental_user.get('slots', [])) if rental_user else 0}/{rental_user.get('max_slots', 5) if rental_user else 5}
└─ Status: {'Terdaftar' if rental_user else 'Belum terdaftar'}

{generate_separator(29)}
"""
    
    keyboard = [
        [
            InlineKeyboardButton("💳 Topup", callback_data="user_topup"),
            InlineKeyboardButton("🛒 Beli VPN", callback_data="user_buy_vpn")
        ],
        [
            InlineKeyboardButton("📦 Rental Script", callback_data="user_rental"),
            InlineKeyboardButton("🔄 Upgrade", callback_data="user_upgrade_account")
        ],
        [
            InlineKeyboardButton("📋 History", callback_data="topup_history"),
            InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")
        ]
    ]
    
    await query.edit_message_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )              
              
# ==================== ADMIN TOPUP PANEL ====================

async def admin_topup_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Topup admin panel"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text("❌ **Akses Ditolak!**\n\nHanya admin yang dapat mengakses panel ini.")
        return
    
    system = get_topup_system()
    
    # Count statistics
    qris_list = os.listdir(QRIS_FOLDER)
    data = load_topup_database()
    
    total_users = len(data['users'])
    total_balance = sum(user.get('balance', 0) for user in data['users'].values())
    pending_count = 0
    
    for user in data['users'].values():
        for transaction in user.get('transactions', []):
            if transaction.get('status') == 'pending':
                pending_count += 1
    
    keyboard = [
        [InlineKeyboardButton("📤 Upload QRIS Baru", callback_data="admin_upload_qris")],
        [InlineKeyboardButton("🗑️ Hapus QRIS", callback_data="admin_delete_qris")],
        [InlineKeyboardButton("📊 Statistik Topup", callback_data="admin_topup_stats")],
        [InlineKeyboardButton("🔄 Test Validasi", callback_data="admin_test_validation")],
        [InlineKeyboardButton("🔙 Kembali ke Menu", callback_data="back_to_main")]
    ]
    
    text = f"""
{generate_header('ADMIN TOPUP PANEL')}

{generate_separator(29)}
👑 *Sistem Topup Otomatis*

📁 **QRIS Aktif:** `{system.get('current_qris', 'qris_default.png')}`
📊 **Total QRIS:** {len(qris_list)}

📈 **STATISTIK SISTEM:**
├─ 👥 Total User: {total_users}
├─ 💰 Total Saldo: {format_money(total_balance)}
├─ ⏳ Transaksi Pending: {pending_count}
└─ 📁 Notifikasi: {len(list(Path(NOTIFICATIONS_FOLDER).glob('*.json')))}

⚙️ **PENGATURAN:**
├─ ⏳ Invoice Expiry: {INVOICE_EXPIRY} menit
├─ 💰 Min Topup: {format_money(MIN_TOPUP)}
└─ 💰 Max Topup: {format_money(MAX_TOPUP)}

{generate_separator(29)}
"""
    
    await query.edit_message_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_upload_qris(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Upload new QRIS"""
    query = update.callback_query
    await query.answer()
    
    text = f"""
{generate_header('UPLOAD QRIS BARU')}

{generate_separator(29)}
📤 *Upload QRIS*

Silakan kirim gambar QRIS (format PNG/JPG):

⚠️ **PERHATIAN:**
- Gambar akan otomatis menjadi QRIS aktif
- Format disarankan PNG transparan
- Ukuran disarankan 500x500px

{generate_separator(29)}
"""
    
    await query.edit_message_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_topup_panel")]
        ])
    )
    context.user_data['awaiting_qris'] = True

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo upload for QRIS"""
    if 'awaiting_qris' in context.user_data and context.user_data['awaiting_qris']:
        user_id = update.effective_user.id
        
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("❌ Hanya admin yang bisa upload QRIS!")
            return
        
        photo = update.message.photo[-1]
        file = await photo.get_file()
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"qris_{timestamp}.png"
        file_path = os.path.join(QRIS_FOLDER, filename)
        
        await file.download_to_drive(file_path)
        
        # Update active QRIS
        system = get_topup_system()
        system['current_qris'] = filename
        update_topup_system(system)
        
        await update.message.reply_text(
            f"✅ **QRIS BERHASIL DIUPLOAD!**\n\n"
            f"Nama file: `{filename}`\n"
            f"QRIS ini sekarang aktif untuk semua invoice.\n\n"
            f"📏 Ukuran: {photo.width}x{photo.height}px\n"
            f"⏰ Waktu: {datetime.now().strftime('%H:%M:%S')}",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_topup_panel")]
            ])
        )
        
        context.user_data.pop('awaiting_qris', None)

async def admin_topup_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show topup statistics"""
    query = update.callback_query
    await query.answer()
    
    data = load_topup_database()
    
    # Calculate statistics
    total_users = len(data['users'])
    total_balance = sum(user.get('balance', 0) for user in data['users'].values())
    
    total_transactions = 0
    completed_transactions = 0
    pending_transactions = 0
    total_topup_amount = 0
    
    for user in data['users'].values():
        transactions = user.get('transactions', [])
        total_transactions += len(transactions)
        
        for transaction in transactions:
            if transaction.get('status') == 'completed':
                completed_transactions += 1
                total_topup_amount += transaction.get('amount', 0)
            elif transaction.get('status') == 'pending':
                pending_transactions += 1
    
    text = f"""
{generate_header('STATISTIK TOPUP')}

{generate_separator(29)}
📊 *Statistik Sistem Topup*

👥 **PENGGUNA:**
├─ Total User: {total_users}
└─ Total Saldo: {format_money(total_balance)}

🧾 **TRANSAKSI:**
├─ Total Transaksi: {total_transactions}
├─ Berhasil: {completed_transactions}
├─ Pending: {pending_transactions}
└─ Total Topup: {format_money(total_topup_amount)}

📁 **SISTEM:**
├─ File Notifikasi: {len(list(Path(NOTIFICATIONS_FOLDER).glob('*.json')))}
└─ QRIS Tersedia: {len(os.listdir(QRIS_FOLDER))}

{generate_separator(29)}
"""
    
    await query.edit_message_text(
        text=text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Kembali ke Admin", callback_data="admin_topup_panel")]
        ])
    )

# ==================== VALIDATION SYSTEM ====================

def scan_notification_files():
    """Scan all JSON files in notifications folder for numbers including various formats"""
    notifications_folder = Path(NOTIFICATIONS_FOLDER)
    found_numbers = []
    
    if not notifications_folder.exists():
        return found_numbers
    
    json_files = list(notifications_folder.glob("*.json"))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Pattern untuk menangkap angka dengan atau tanpa titik sebagai pemisah ribuan
                # Format yang didukung: 
                # - 1000, 1.000, 10.000, 100.000, 1.000.000, dll
                # - Rp2.635, 2635 !, 5.000 !, dll (dari contoh notifikasi)
                numbers = re.findall(r'\bRp?\s*\d{1,3}(?:\.\d{3})*\b|\b\d{1,3}(?:\.\d{3})+\b|\b\d+\b', content)
                
                for number_str in numbers:
                    try:
                        # Hapus semua karakter non-digit kecuali titik (untuk pemisah ribuan)
                        # Pisahkan angka dari Rp, tanda seru, spasi, dll
                        cleaned = re.sub(r'[^\d\.]', '', number_str)
                        
                        # Hapus titik pemisah ribuan jika ada
                        if '.' in cleaned:
                            # Cek apakah titik sebagai pemisah ribuan atau desimal
                            parts = cleaned.split('.')
                            if len(parts) > 1:
                                # Jika bagian terakhir 3 digit, kemungkinan pemisah ribuan
                                if len(parts[-1]) == 3:
                                    cleaned = cleaned.replace('.', '')
                        
                        # Konversi ke integer
                        number = int(cleaned)
                        
                        if number >= 1000:  # Minimal 1000 untuk topup
                            found_numbers.append(number)
                    except ValueError:
                        continue
                        
        except Exception as e:
            print(f"⚠️ Error membaca file {json_file}: {e}")
            continue
    
    return list(set(found_numbers))                
                
                
def parse_amount_from_notification(text):
    """
    Parse amount dari teks notifikasi pembayaran.
    Mendukung berbagai format:
    - Rp2.635
    - 2635 !
    - 5.000 !
    - Rp 10.000
    - 10000
    """
    
    # Pattern untuk menangkap angka dalam berbagai format
    patterns = [
        r'Rp\s*(\d{1,3}(?:\.\d{3})*)',  # Rp2.635, Rp 10.000
        r'(\d{1,3}(?:\.\d{3})+)\s*!',    # 5.000 !, 10.000!
        r'(\d+)\s*!',                     # 2635 !, 10000!
        r'(\d{1,3}(?:\.\d{3})+)',        # 1.000, 10.000
        r'(\d{4,})'                       # 1000, 10000
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                # Hapus semua non-digit kecuali titik
                cleaned = re.sub(r'[^\d\.]', '', match)
                
                # Hapus titik jika ada (asumsi pemisah ribuan)
                if '.' in cleaned:
                    # Cek apakah ini pemisah ribuan atau desimal
                    parts = cleaned.split('.')
                    if len(parts) == 2 and len(parts[1]) == 3:
                        # Format seperti 1.000, 10.000
                        cleaned = cleaned.replace('.', '')
                    elif len(parts) == 2 and len(parts[1]) <= 2:
                        # Format desimal seperti 1.5, skip
                        continue
                
                amount = int(cleaned)
                
                # Validasi jumlah masuk akal
                if 1000 <= amount <= 1000000:
                    return amount
                    
            except (ValueError, AttributeError):
                continue
    
    return None


def scan_notification_files_v2():
    """Versi baru untuk scanning notifikasi yang lebih akurat"""
    notifications_folder = Path(NOTIFICATIONS_FOLDER)
    found_numbers = []
    
    if not notifications_folder.exists():
        return found_numbers
    
    json_files = list(notifications_folder.glob("*.json"))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Cari di semua field teks
                text_fields = []
                for value in data.values():
                    if isinstance(value, str):
                        text_fields.append(value)
                
                # Gabungkan semua teks
                all_text = ' '.join(text_fields)
                
                # Parse amount
                amount = parse_amount_from_notification(all_text)
                if amount:
                    found_numbers.append(amount)
                        
        except Exception as e:
            print(f"⚠️ Error membaca file {json_file}: {e}")
            continue
    
    return list(set(found_numbers))                
               
                
def cleanup_old_files():
    """Delete old JSON files (>15 minutes)"""
    notifications_folder = Path(NOTIFICATIONS_FOLDER)
    now = datetime.now()
    
    if not notifications_folder.exists():
        return
    
    files_deleted = 0
    for json_file in notifications_folder.glob("*.json"):
        try:
            filename = json_file.stem
            try:
                file_time = datetime.strptime(filename, NOTIFICATION_PATTERN)
            except ValueError:
                file_age = now - datetime.fromtimestamp(json_file.stat().st_mtime)
                if file_age.total_seconds() > (INVOICE_EXPIRY * 60):
                    os.remove(json_file)
                    files_deleted += 1
                continue
            
            if (now - file_time).total_seconds() > (INVOICE_EXPIRY * 60):
                os.remove(json_file)
                files_deleted += 1
                
        except Exception as e:
            print(f"⚠️ Error membersihkan file {json_file}: {e}")
            continue
    
    if files_deleted > 0:
        print(f"🗑️  Dihapus {files_deleted} file lama")

def validate_pending_transactions():
    """Validate pending transactions by scanning notification files"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Memindai file notifications...")
    
    # Clean old files
    cleanup_old_files()
    
    # Scan all files for numbers - GUNAKAN VERSI BARU
    found_numbers = scan_notification_files_v2()
    
    if found_numbers:
        print(f"📄 Ditemukan {len(found_numbers)} angka unik: {found_numbers}")
    
    validated_transactions = []
    
    # Validate each found number
    for invoice_code in found_numbers:
        try:
            user_id, new_balance = validate_topup_transaction(invoice_code)
            if user_id:
                validated_transactions.append({
                    'user_id': user_id,
                    'invoice_code': invoice_code,
                    'new_balance': new_balance
                })
                print(f"✅ Transaksi valid: {invoice_code} untuk user {user_id}")
        except Exception as e:
            print(f"⚠️ Error validasi invoice {invoice_code}: {e}")
    
    return validated_transactions
                    
                    
async def notify_users(validated_transactions):
    """Send notifications to users with successful transactions"""
    from telegram import Bot
    
    for transaction in validated_transactions:
        try:
            amount, validator = extract_amount_from_invoice(transaction['invoice_code'])
            
            notification_text = (
                f"{generate_header('TOPUP BERHASIL!')}\n\n"
                f"{generate_separator(29)}\n"
                f"✅ *Pembayaran telah diverifikasi*\n\n"
                f"💰 **Jumlah:** {format_money(amount)}\n"
                f"🔢 **Invoice:** `{transaction['invoice_code']}`\n"
                f"🔐 **Validator:** {validator:03d}\n"
                f"💳 **Saldo Baru:** {format_money(transaction['new_balance'])}\n\n"
                f"Terima kasih telah melakukan topup! 🎊\n"
                f"{generate_separator(29)}"
            )
            
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(
                chat_id=transaction['user_id'],
                text=notification_text,
                parse_mode='Markdown'
            )
            print(f"📨 Notifikasi terkirim ke user {transaction['user_id']}")
            
        except Exception as e:
            print(f"⚠️ Error mengirim notifikasi ke user {transaction['user_id']}: {e}")

def validation_loop():
    """Loop for automatic validation"""
    print("🔄 Memulai sistem validasi otomatis...")
    print(f"⏱️  Interval: setiap 10 detik")
    print(f"⏳ Masa berlaku invoice: {INVOICE_EXPIRY} menit")
    print(f"📁 Folder notifications: {NOTIFICATIONS_FOLDER}")
    
    while True:
        try:
            validated_transactions = validate_pending_transactions()
            
            if validated_transactions:
                print(f"📊 {len(validated_transactions)} transaksi divalidasi")
                asyncio.run(notify_users(validated_transactions))
            
            time_module.sleep(10)
            
        except Exception as e:
            print(f"⚠️ Error dalam loop validasi: {e}")
            time_module.sleep(30)
                    
# ============================================
# ADMIN PANEL - VERSI LENGKAP DENGAN RENTAL SLOT
# ============================================

                    
async def admin_rental_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistik detail untuk rental slot system"""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        await query.edit_message_text("❌ Akses ditolak.")
        return
    
    try:
        users = rental_db.get_all_users()
        ips = rental_db.get_all_ips()
        
        # Statistik detail
        total_users = len(users)
        
        # Slot statistics
        total_slots = 0
        active_slots = 0
        expired_slots = 0
        lifetime_slots = 0
        slots_per_user = []
        ips_per_slot = []
        
        for user in users:
            slots = user.get('slots', [])
            total_slots += len(slots)
            slots_per_user.append(len(slots))
            
            for slot in slots:
                ip_count = len(slot.get('ips', []))
                ips_per_slot.append(ip_count)
                
                if rental_db.is_slot_active(slot):
                    active_slots += 1
                    if slot.get('expiry_date') == "lifetime":
                        lifetime_slots += 1
                else:
                    expired_slots += 1
        
        # IP statistics
        total_ips = len(ips)
        
        # Revenue statistics
        total_revenue = sum(u.get("total_spent", 0) for u in users)
        
        # Average calculations
        avg_slots_per_user = total_slots / total_users if total_users > 0 else 0
        avg_ips_per_slot = total_ips / total_slots if total_slots > 0 else 0
        
        text = f"""
{generate_header('📊 RENTAL SLOT STATISTICS')}

{generate_separator(29)}
👥 *USER STATISTICS:*
├ Total Users: {total_users}
├ Users with slots: {sum(1 for u in users if u.get('slots'))}
└ Users without slots: {sum(1 for u in users if not u.get('slots'))}

📦 *SLOT STATISTICS:*
├ Total Slots: {total_slots}
├ Active Slots: {active_slots}
├ Expired Slots: {expired_slots}
├ Lifetime Slots: {lifetime_slots}
├ Avg Slots/User: {avg_slots_per_user:.2f}
└ Slot Distribution: {sorted(set(slots_per_user))}

🌐 *IP STATISTICS:*
├ Total IPs: {total_ips}
├ IPs in Slots: {sum(ips_per_slot)}
├ Empty Slots: {sum(1 for count in ips_per_slot if count == 0)}
├ Avg IPs/Slot: {avg_ips_per_slot:.2f}
└ Max IPs in a Slot: {max(ips_per_slot) if ips_per_slot else 0}

💰 *REVENUE STATISTICS:*
├ Total Revenue: {format_money(total_revenue)}
├ Avg Revenue/User: {format_money(total_revenue / total_users) if total_users > 0 else 0}
└ Avg Revenue/Slot: {format_money(total_revenue / total_slots) if total_slots > 0 else 0}

⚙️ *SETTINGS:*
├ Price per Slot: {format_money(rental_db.get_price_per_slot())}/month
├ Max Slots/User: {rental_db.data['settings'].get('max_slots_per_user', 10)}
├ Default IP/Slot: {rental_db.data['settings'].get('default_ips_per_slot', 1)}
└ Auto Sync: {'✅' if rental_db.data['settings'].get('auto_sync', True) else '❌'}

{generate_separator(29)}
"""
        
        keyboard = [
            [InlineKeyboardButton("📋 List User", callback_data="admin_rental_users")],
            [InlineKeyboardButton("📋 List IP", callback_data="admin_rental_ips")],
            [InlineKeyboardButton("🔙 Rental Panel", callback_data="admin_rental_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        
    except Exception as e:
        print(f"[ERROR] admin_rental_stats: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")

# ============================================
# ADMIN PANEL - VERSI LENGKAP DENGAN RENTAL SLOT
# ============================================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panel admin utama - Versi Lengkap dengan Rental Slot"""
    
    # Cek apakah user adalah admin
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ *Akses Ditolak!*\n\nHanya admin yang dapat mengakses panel ini.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "❌ *Akses Ditolak!*\n\nHanya admin yang dapat mengakses panel ini.",
                parse_mode="Markdown"
            )
        return
    
    # Ambil data statistik
    try:
        # User stats
        users_data = load_json(USERS_DB)
        total_users = len(users_data)
        active_users = sum(1 for u in users_data.values() if len(u.get("vpn_accounts", [])) > 0)
        
        # VPS stats
        vps_list = get_all_vps()
        total_vps = len(vps_list)
        active_vps = sum(1 for v in vps_list.values() if v.get("status") == "active")
        
        # Order stats
        orders_data = load_json(ORDERS_DB)
        today = datetime.now().date()
        today_orders = sum(
            1 for o in orders_data.values()
            if datetime.fromisoformat(o["created_at"]).date() == today 
            and o.get("status") == "completed"
        )
        
        # Rental stats (SLOT SYSTEM)
        rental_users = rental_db.get_all_users()
        total_slots = 0
        active_slots = 0
        total_rental_ips = 0
        
        for user in rental_users:
            slots = user.get('slots', [])
            total_slots += len(slots)
            for slot in slots:
                if rental_db.is_slot_active(slot):
                    active_slots += 1
                total_rental_ips += len(slot.get('ips', []))
        
        total_rental_users = len(rental_users)
        
        # GitHub status
        github_configured = github_mgr.is_configured() if 'github_mgr' in dir() else False
        
        # Settings
        price_per_slot = rental_db.get_price_per_slot()
        max_slots_per_user = rental_db.data['settings'].get('max_slots_per_user', 10)
        default_ips_per_slot = rental_db.data['settings'].get('default_ips_per_slot', 1)
        
    except Exception as e:
        print(f"[ERROR] Gagal mengambil data statistik: {e}")
        total_users = active_users = total_vps = active_vps = today_orders = 0
        total_slots = active_slots = total_rental_ips = total_rental_users = 0
        price_per_slot = 10000
        max_slots_per_user = 1000
        default_ips_per_slot = 1
        github_configured = False
    
    # ==================== HEADER PANEL ====================
    text = f"""
{generate_header('👑 ADMIN PANEL')}

{generate_separator(29)}
📊 *STATISTIK SISTEM*
{generate_separator(29)}
👥 *User:*
├ Total User: {total_users}
├ User Aktif: {active_users}
└ Order Hari Ini: {today_orders}

🖥️ *Server:*
├ Total VPS: {total_vps}
├ VPS Aktif: {active_vps}
└ VPS Nonaktif: {total_vps - active_vps}

📦 *RENTAL SLOT SYSTEM:*
├ User Rental: {total_rental_users}
├ Total Slots: {total_slots}
├ Slot Aktif: {active_slots}
├ Total IP: {total_rental_ips}
└ Harga/Slot: {format_money(price_per_slot)}/bln

⚙️ *PENGATURAN RENTAL:*
├ Max Slots/User: {max_slots_per_user}
├ Default IP/Slot: {default_ips_per_slot}
├ GitHub: {'✅ Terkoneksi' if github_configured else '❌ Belum'}
└ Auto Sync: {'✅ Ya' if rental_db.data['settings'].get('auto_sync', True) else '❌ Tidak'}

{generate_separator(29)}
📋 *MENU ADMIN:*
{generate_separator(29)}
"""
    
    # ==================== KEYBOARD LENGKAP ====================
    keyboard = [
        # ============ BARIS 1: MANAJEMEN VPS ============
        [
            InlineKeyboardButton("➕ Tambah VPS", callback_data="admin_add_vps"),
            InlineKeyboardButton("✏️ Edit/Hapus VPS", callback_data="admin_edit_vps")
        ],
        
        # ============ BARIS 2: MANAJEMEN HARGA ============
        [
            InlineKeyboardButton("💰 Set Harga Default", callback_data="admin_set_price"),
            InlineKeyboardButton("🎯 Set Harga Server", callback_data="admin_set_server_price")
        ],
        
        # ============ BARIS 3: PENGATURAN IP ============
        [
            InlineKeyboardButton("🌐 Set IP Limit", callback_data="admin_set_ip_limit"),
            InlineKeyboardButton("🔧 Set IP Tambahan", callback_data="admin_set_extra_ip_price")
        ],
        
        # ============ BARIS 4: RENTAL SLOT SYSTEM ============
        [
            InlineKeyboardButton("📦 RENTAL PANEL", callback_data="admin_rental_panel"),
            InlineKeyboardButton("📊 Rental Stats", callback_data="admin_rental_stats")
        ],
        
        # ============ BARIS 5: PENGATURAN RENTAL SLOT ============
        [
            InlineKeyboardButton("⚙️ Set Max Slots", callback_data="admin_rental_set_max_slots"),
            InlineKeyboardButton("🔧 Set IP per Slot", callback_data="admin_rental_set_ip_per_slot")
        ],
        
        # ============ BARIS 6: MANAJEMEN RENTAL ============
        [
            InlineKeyboardButton("➕ Add Slot ke User", callback_data="admin_rental_add_slot"),
            InlineKeyboardButton("🗑️ Delete Slot", callback_data="admin_rental_delete_slot")
        ],
        
        # ============ BARIS 7: KOMUNIKASI ============
        [
            InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
            InlineKeyboardButton("📋 Log Broadcast", callback_data="broadcast_logs")
        ],
        
        # ============ BARIS 8: TOPUP SYSTEM ============
        [
            InlineKeyboardButton("👑 Topup Panel", callback_data="admin_topup_panel"),
            InlineKeyboardButton("📤 Upload QRIS", callback_data="admin_upload_qris")
        ],
        
        # ============ BARIS 9: MANAJEMEN USER ============
        [
            InlineKeyboardButton("👥 List User", callback_data="admin_list_users"),
            InlineKeyboardButton("➕ Tambah Saldo", callback_data="admin_add_balance")
        ],
        
        # ============ BARIS 10: MANAJEMEN AKUN ============
        [
            InlineKeyboardButton("🗑️ Delete Account", callback_data="admin_delete_account"),
            InlineKeyboardButton("🔑 Cek Akun", callback_data="user_check_account")
        ],
        
        # ============ BARIS 11: FITUR LANJUTAN ============
        [
            InlineKeyboardButton("🔄 Rebuild VPS", callback_data="admin_rebuild_vps"),
            InlineKeyboardButton("⏰ Auto Reboot", callback_data="admin_auto_reboot")
        ],
        
        # ============ BARIS 12: DASHBOARD & STATS ============
        [
            InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard"),
            InlineKeyboardButton("📈 Statistik", callback_data="admin_stats")
        ],
        
        # ============ BARIS 13: LIST VPS & IP ============
        [
            InlineKeyboardButton("🖥️ List VPS", callback_data="admin_list_vps"),
            InlineKeyboardButton("📋 List IP", callback_data="admin_rental_ips")
        ],
        
        # ============ BARIS 14: GITHUB & SYNC ============
        [
            InlineKeyboardButton("🔧 GitHub Config", callback_data="admin_rental_github"),
            InlineKeyboardButton("🔄 Sync GitHub", callback_data="admin_rental_sync")
        ],
        
        # ============ BARIS 15: PENGATURAN UMUM ============
        [
            InlineKeyboardButton("⚙️ Rental Settings", callback_data="admin_rental_settings"),
            InlineKeyboardButton("📋 Rental Guide", callback_data="rental_guide")
        ],
        
        # ============ BARIS 16: FITUR USER ============
        [
            InlineKeyboardButton("🛒 Beli VPN", callback_data="user_buy_vpn"),
            InlineKeyboardButton("🎁 Trial VPN", callback_data="user_trial_vpn")
        ],
        
        # ============ BARIS 17: KEMBALI ============
        [
            InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main"),
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_panel")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Kirim pesan
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
                    
                    
                    
# ============================================
# MESSAGE HANDLER UNTUK RENTAL SLOT INPUT
# ============================================

async def handle_rental_slot_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle message untuk proses rental slot (tambah IP, dll)"""
    
    # Cek apakah sedang dalam proses tambah IP ke slot
    if "rental_add_ip_stage" in context.user_data:
        stage = context.user_data["rental_add_ip_stage"]
        slot_id = context.user_data.get("add_ip_slot_id")
        
        if not slot_id:
            await update.message.reply_text("❌ Session tidak valid. Silakan mulai ulang.")
            context.user_data.pop("rental_add_ip_stage", None)
            return
        
        text = update.message.text.strip()
        
        if text.lower() == "batal":
            await update.message.reply_text("❌ Proses dibatalkan.")
            context.user_data.pop("rental_add_ip_stage", None)
            context.user_data.pop("add_ip_slot_id", None)
            return
        
        if stage == "username":
            if not text:
                await update.message.reply_text("❌ Username tidak boleh kosong!")
                return
            
            context.user_data["rental_add_ip_username"] = text
            context.user_data["rental_add_ip_stage"] = "ip"
            
            await update.message.reply_text(
                f"""
{generate_header('TAMBAH IP KE SLOT')}

{generate_separator(29)}
✅ Username: `{text}`
{generate_separator(29)}
📝 *Langkah 2/2: Masukkan Alamat IP*
{generate_separator(29)}
Masukkan alamat IP yang akan didaftarkan:
Format: xxx.xxx.xxx.xxx
{generate_separator(29)}
Contoh: `192.168.1.1`
{generate_separator(29)}
"""
            )
        
        elif stage == "ip":
            # Validasi format IP
            ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
            if not re.match(ip_pattern, text):
                await update.message.reply_text(
                    "❌ Format IP tidak valid!\n"
                    "Format harus: xxx.xxx.xxx.xxx\n"
                    "Contoh: 192.168.1.1\n"
                    "Silakan masukkan lagi:"
                )
                return
            
            username = context.user_data["rental_add_ip_username"]
            user_id = update.effective_user.id
            
            # Tambah IP ke slot
            success, result = rental_db.add_ip_to_slot(user_id, slot_id, text, username)
            
            if success:
                # Sync ke GitHub
                if rental_db.data["settings"].get("auto_sync", True):
                    try:
                        await asyncio.to_thread(github_mgr.sync_to_github)
                    except:
                        pass
                
                # Generate install script
                script = generate_install_script(
                    text, 
                    username,
                    rental_db.data["settings"]["github_username"],
                    rental_db.data["settings"]["github_repo"]
                )
                
                text_response = f"""
{generate_header('IP BERHASIL DITAMBAH KE SLOT')}

{generate_separator(29)}
✅ *IP Berhasil Ditambahkan!*
{generate_separator(29)}
📋 *Detail:*
├ Username: `{username}`
├ IP Address: `{text}`
└ Slot ID: `{slot_id[:8]}...`

{generate_separator(29)}
📜 *Script Install:*
```

apt-get update && apt-get upgrade -y && apt install wget -y && wget https://raw.githubusercontent.com/{rental_db.data["settings"]["github_username"]}/{rental_db.data["settings"]["github_repo"]}/main/install2.sh && chmod +x install2.sh && ./install2.sh


{generate_separator(29)}
📋 *Cara Install:*
1. Login ke VPS Anda via SSH
2. Copy script di atas
3. Paste di terminal VPS
4. Tunggu hingga proses selesai
5. Gunakan username `{username}` saat instalasi

{generate_separator(29)}
"""
                
                keyboard = [
                    [
                        InlineKeyboardButton("📋 Lihat Slot", callback_data=f"rental_slot_detail_{slot_id}"),
                        InlineKeyboardButton("➕ Tambah Lagi", callback_data=f"rental_add_ip_slot_{slot_id}")
                    ],
                    [InlineKeyboardButton("🔙 Menu Rental", callback_data="user_rental")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(text_response, reply_markup=reply_markup)
            else:
                await update.message.reply_text(f"❌ Gagal menambah IP: {result}")
            
            # Bersihkan session
            context.user_data.pop("rental_add_ip_stage", None)
            context.user_data.pop("rental_add_ip_username", None)
            context.user_data.pop("add_ip_slot_id", None)
                    
                    
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /start - Tampilkan menu utama dengan layout yang rapi"""
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    # Update user info in topup database
    try:
        topup_user = get_topup_user(user_id)
        topup_user['username'] = update.effective_user.username or ''
        topup_user['first_name'] = update.effective_user.first_name or ''
        update_topup_user(user_id, topup_user)
    except:
        # Jika error, tetap lanjutkan
        pass
    
    header = generate_header("VPN STORE BOT")
    
    # ============ PERBAIKAN DI SINI ============
    # Cek apakah ADMIN_IDS adalah list
    if isinstance(ADMIN_IDS, (list, tuple, set)):
        is_admin_user = user_id in ADMIN_IDS
    else:
        # Jika bukan list, bandingkan langsung
        is_admin_user = (user_id == ADMIN_IDS)
    
    if is_admin_user:
        # ==================== LAYOUT UNTUK ADMIN ====================
        keyboard = [
            # Row 1: Management Akun
            [
                InlineKeyboardButton("🗑️ Hapus Akun", callback_data="admin_delete_account"),
                InlineKeyboardButton("👥 List User", callback_data="admin_list_users")
            ],
            # Row 2: Management VPS
            [
                InlineKeyboardButton("➕ Tambah VPS", callback_data="admin_add_vps"),
                InlineKeyboardButton("✏️ Edit VPS", callback_data="admin_edit_vps")
            ],
            # Row 3: Pengaturan Sistem
            [
                InlineKeyboardButton("💰 Set Harga", callback_data="admin_set_price"),
                InlineKeyboardButton("🎯 Harga Server", callback_data="admin_set_server_price")
            ],
            # Row 4: Komunikasi & Monitoring
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                InlineKeyboardButton("⏰ Auto Reboot", callback_data="admin_auto_reboot")
            ],
            # Row 5: Fitur User
            [
                InlineKeyboardButton("🔄 Rebuild VPS", callback_data="admin_rebuild_vps"),
                InlineKeyboardButton("🛒 Beli VPN", callback_data="user_buy_vpn")
            ],
            # Row 6: Fitur Lainnya
            [
                InlineKeyboardButton("🔑 Cek Akun", callback_data="user_check_account"),
                InlineKeyboardButton("💳 Topup", callback_data="user_topup")
            ],
            # Row 7: Admin Panel Topup
            [
                InlineKeyboardButton("👑 Topup Admin", callback_data="admin_topup_panel")
            ],
            # Row 8: QRIS Management
            [
                InlineKeyboardButton("📤 Upload QRIS", callback_data="admin_upload_qris")
            ],
            # Row 9: Rental System Admin
            [
                InlineKeyboardButton("📋 Rental Admin", callback_data="admin_rental_panel"),
                InlineKeyboardButton("📦 Rental User", callback_data="user_rental")
            ]
        ]
        
        # Cek status rental
        rental_stats = ""
        try:
            if 'rental_db' in globals() and rental_db:
                total_users = len(rental_db.get_all_users())
                total_ips = len(rental_db.get_all_ips())
                price = rental_db.get_price_per_month()
                rental_stats = f"""
📦 **SISTEM RENTAL:**
├─ Harga/bulan: {format_money(price)}
├─ Total User: {total_users}
├─ Total IP: {total_ips}
└─ GitHub: {'✅ Terkoneksi' if github_mgr.is_configured() else '❌ Belum konfigurasi'}
"""
        except:
            rental_stats = "\n📦 **SISTEM RENTAL:** ❌ Error loading data\n"
        
        text = f"""
{header}

👑 **ADMIN PANEL**

📊 **INFORMASI AKUN:**
├─ 👤 User: {update.effective_user.first_name}
├─ 💰 Saldo: {format_money(user['balance'])}
├─ 📦 Orders: {user.get('total_orders', 0)}
└─ 💸 Spent: {format_money(user.get('total_spent', 0))}

⚡ **FITUR SISTEM:**
├─ 💳 Topup: ✅ (OTOMATIS)
├─ 🔄 Rebuild: ✅
├─ 📢 Broadcast: ✅
├─ ⏰ Auto Reboot: ✅
└─ 📦 Rental System: ✅ **BARU!**
{rental_stats}
📝 **Pilih menu:**
"""
    else:
        # ==================== LAYOUT UNTUK USER BIASA ====================
        
        # Cek status rental user
        rental_status = ""
        rental_price_info = ""
        
        try:
            if 'rental_db' in globals() and rental_db:
                rental_user = None
                try:
                    rental_user = rental_db.get_user(user_id)
                except:
                    pass
                
                if rental_user:
                    if rental_db.check_user_access(user_id):
                        if rental_user.get("expiry_date") == "lifetime":
                            rental_status = "⭐ *Rental: Lifetime*"
                        else:
                            try:
                                expiry = datetime.fromisoformat(rental_user.get("expiry_date", ""))
                                days_left = (expiry - datetime.now()).days
                                if days_left >= 0:
                                    rental_status = f"📦 *Rental: {days_left} hari lagi*"
                                else:
                                    rental_status = "⚠️ *Rental: Expired*"
                            except:
                                rental_status = "📦 *Rental: Aktif*"
                    else:
                        rental_status = "⚠️ *Rental: Expired*"
                
                # Tampilkan harga rental
                price = rental_db.get_price_per_month()
                rental_price_info = f"├─ 📦 Rental: {format_money(price)}/bln"
        except:
            rental_status = ""
            rental_price_info = ""
        
        keyboard = [
            # Row 1: Transaksi Utama
            [
                InlineKeyboardButton("💳 TOP UP", callback_data="user_topup"),
                InlineKeyboardButton("🛒 BELI VPN", callback_data="user_buy_vpn")
            ],
            # Row 2: Rental System
            [
                InlineKeyboardButton("📦 RENTAL SCRIPT", callback_data="user_rental"),
                InlineKeyboardButton("🔄 UPGRADE", callback_data="user_upgrade_account")
            ],
            # Row 3: Management Akun
            [
                InlineKeyboardButton("🔑 CEK AKUN", callback_data="user_check_account"),
                InlineKeyboardButton("🎁 TRIAL", callback_data="user_trial_vpn")
            ],
            # Row 4: Informasi & Bantuan
            [
                InlineKeyboardButton("💰 SALDO", callback_data="user_balance"),
                InlineKeyboardButton("📖 PANDUAN", callback_data="user_guide")
            ]
        ]
        
        # Hitung statistik user
        try:
            user_vpn_count = len(user.get('vpn_accounts', []))
        except:
            user_vpn_count = 0
        
        text = f"""
{header}

👋 **Halo, {update.effective_user.first_name}!**

📊 **AKUN ANDA:**
├─ 💰 Saldo: {format_money(user['balance'])}
├─ 📦 Orders: {user.get('total_orders', 0)}
├─ 💸 Spent: {format_money(user.get('total_spent', 0))}
├─ 🔑 VPN Aktif: {user_vpn_count}
{rental_price_info}
{rental_status}

🎯 **LAYANAN:**
├─ SSH, VMess, VLESS
├─ Trojan, SS, ZiVPN
├─ ✅ Trial 40 Menit
└─ ✅ Upgrade Fleksibel

📦 **RENTAL SCRIPT:**
├─ Sewa script installer
├─ Kelola IP sendiri
├─ Masa aktif fleksibel
└─ Harga mulai {format_money(rental_db.get_price_per_month() if 'rental_db' in globals() and rental_db else 50000)}/bln

📝 **Pilih menu:**
"""
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, 
                parse_mode=ParseMode.MARKDOWN, 
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                text, 
                parse_mode=ParseMode.MARKDOWN, 
                reply_markup=reply_markup
            )
    except Exception as e:
        # Fallback jika ada error markdown
        print(f"Error in start handler: {e}")
        simple_text = f"Selamat datang {update.effective_user.first_name}!\nSaldo: {format_money(user['balance'])}"
        if update.callback_query:
            await update.callback_query.edit_message_text(simple_text)
        else:
            await update.message.reply_text(simple_text)
    
    return ConversationHandler.END                                            
                  
                  
# ============================================
# FITUR REBUILD VPS (ADMIN ONLY)
# ============================================

@check_admin
async def admin_rebuild_vps_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses rebuild VPS"""
    query = update.callback_query
    await query.answer()
    
    vps_list = get_all_vps()
    
    if not vps_list:
        text = f"""
{generate_header('REBUILD VPS')}

{generate_separator(29)}
📭 *Tidak Ada Server VPS*
{generate_separator(29)}
Belum ada server VPS yang ditambahkan.
Tambahkan server terlebih dahulu untuk menggunakan fitur rebuild.
{generate_separator(29)}
"""
        keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ConversationHandler.END
    
    text = f"""
{generate_header('REBUILD VPS')}

{generate_separator(29)}
⚠️ *PERINGATAN: FITUR REBUILD*
{generate_separator(29)}
🔄 *Fitur rebuild akan:*
├ 1. Install ulang sistem operasi
├ 2. Format seluruh hard disk
├ 3. Hapus semua data yang ada
├ 4. Install OS baru yang dipilih
└ 5. Reset semua konfigurasi
{generate_separator(29)}
❌ *DATA AKAN HILANG PERMANEN!*
{generate_separator(29)}
Pilih server VPS yang akan di-rebuild:
"""
    
    keyboard = []
    for vps_id, vps in vps_list.items():
        if vps.get("status") == "active":
            name = vps.get('name', f"VPS {vps['ip']}")
            domain = vps.get('domain', 'N/A')
            vps_type = vps.get('type', 'regular')
            type_icon = "🟦" if vps_type == "zivpn" else "🟩"
            
            button_text = f"{type_icon} {name} ({domain})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"rebuild_select_{vps_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return REBUILD_SELECT_VPS

async def admin_rebuild_select_vps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pemilihan VPS untuk rebuild"""
    query = update.callback_query
    await query.answer()
    
    vps_id = query.data.replace("rebuild_select_", "")
    vps = get_vps(vps_id)
    
    if not vps:
        await query.edit_message_text("❌ Server tidak ditemukan.")
        return ConversationHandler.END
    
    context.user_data["rebuild_vps_id"] = vps_id
    context.user_data["rebuild_vps_info"] = vps
    
    text = f"""
{generate_header('PILIH SISTEM OPERASI')}

{generate_separator(29)}
🖥️ *Server:* {vps.get('name', 'VPS')}
🌐 *IP:* `{vps['ip']}`
📍 *Domain:* {vps.get('domain', 'N/A')}
{generate_separator(29)}

Pilih sistem operasi untuk install ulang:
"""
    
    # Buat keyboard dengan OS yang tersedia
    keyboard = []
    row = []
    os_names = list(OS_LIST.keys())
    
    for i, os_name in enumerate(os_names):
        row.append(InlineKeyboardButton(os_name.capitalize(), callback_data=f"rebuild_os_{os_name}"))
        if (i + 1) % 3 == 0:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="admin_rebuild_vps")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return REBUILD_SELECT_OS

async def admin_rebuild_select_os(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pemilihan OS"""
    query = update.callback_query
    await query.answer()
    
    os_name = query.data.replace("rebuild_os_", "")
    context.user_data["rebuild_os"] = os_name
    
    vps = context.user_data["rebuild_vps_info"]
    versions = OS_LIST.get(os_name, [])
    
    if not versions:
        # Jika tidak ada versi (seperti Arch, Kali)
        context.user_data["rebuild_version"] = ""
        
        text = f"""
{generate_header('SET PASSWORD')}

{generate_separator(29)}
🖥️ *Server:* {vps.get('name', 'VPS')}
🔧 *OS:* {os_name.capitalize()}
{generate_separator(29)}

Masukkan password root baru untuk server:
💡 *Kosongkan* untuk generate otomatis (12 karakter)
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        return REBUILD_SET_PASSWORD
    
    text = f"""
{generate_header('PILIH VERSI OS')}

{generate_separator(29)}
🖥️ *Server:* {vps.get('name', 'VPS')}
🔧 *OS:* {os_name.capitalize()}
{generate_separator(29)}

Pilih versi {os_name.capitalize()}:
"""
    
    keyboard = []
    for version in versions:
        if version:
            button_text = f"{os_name.capitalize()} {version}"
        else:
            button_text = f"{os_name.capitalize()} (Latest)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"rebuild_ver_{version}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data=f"rebuild_select_{context.user_data['rebuild_vps_id']}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return REBUILD_SELECT_VERSION

async def admin_rebuild_select_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pemilihan versi OS"""
    query = update.callback_query
    await query.answer()
    
    version = query.data.replace("rebuild_ver_", "")
    context.user_data["rebuild_version"] = version
    
    vps = context.user_data["rebuild_vps_info"]
    os_name = context.user_data["rebuild_os"]
    
    text = f"""
{generate_header('SET PASSWORD')}

{generate_separator(29)}
🖥️ *Server:* {vps.get('name', 'VPS')}
🔧 *OS:* {os_name.capitalize()} {version if version else '(Latest)'}
{generate_separator(29)}

Masukkan password root baru untuk server:
💡 *Kosongkan* untuk generate otomatis (12 karakter)
"""
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return REBUILD_SET_PASSWORD

async def admin_rebuild_set_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input password untuk rebuild"""
    password = update.message.text.strip()
    
    if not password:
        # Generate random password
        import random, string
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    context.user_data["rebuild_password"] = password
    
    vps_id = context.user_data["rebuild_vps_id"]
    vps = context.user_data["rebuild_vps_info"]
    os_name = context.user_data["rebuild_os"]
    version = context.user_data.get("rebuild_version", "")
    
    text = f"""
{generate_header('KONFIRMASI REBUILD')}

{generate_separator(29)}
⚠️ *PERINGATAN: TINDAKAN INI TIDAK DAPAT DIBATALKAN!*
{generate_separator(29)}
📋 *Detail Rebuild:*
├ Server: {vps.get('name', 'VPS')}
├ IP: `{vps['ip']}`
├ OS: {os_name.capitalize()} {version if version else '(Latest)'}
├ Password: `{password}`
└ SSH Port: {vps.get('ssh_port', 22)}
{generate_separator(29)}
❌ *SEMUA DATA AKAN DIHAPUS!*
{generate_separator(29)}
Proses ini akan:
1. Format seluruh hard disk
2. Install OS baru
3. Reset semua konfigurasi
4. Hapus semua akun VPN yang ada
{generate_separator(29)}
⏳ *Estimasi waktu:* 10-30 menit
{generate_separator(29)}
✅ *Konfirmasi rebuild?*
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ YA, REBUILD SEKARANG", callback_data="confirm_rebuild"),
            InlineKeyboardButton("❌ BATALKAN", callback_data="admin_panel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return REBUILD_CONFIRMATION

async def admin_rebuild_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi dan eksekusi rebuild"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_rebuild":
        await query.edit_message_text("❌ Rebuild dibatalkan.")
        return ConversationHandler.END
    
    # Dapatkan data dari context
    vps_id = context.user_data["rebuild_vps_id"]
    vps = context.user_data["rebuild_vps_info"]
    os_name = context.user_data["rebuild_os"]
    version = context.user_data.get("rebuild_version", "")
    password = context.user_data["rebuild_password"]
    
    # Tampilkan pesan processing
    processing_msg = await query.edit_message_text(
        f"""
{generate_header('SEDANG MEMPROSES')}

{generate_separator(29)}
⏳ *MEMULAI PROSES REBUILD...*
{generate_separator(29)}
🔄 Menghubungkan ke server...
📥 Downloading script install...
⚙️ Menyiapkan environment...
{generate_separator(29)}
⏱️ *Mohon tunggu, proses mungkin memakan waktu 10-30 menit.*
{generate_separator(29)}
"""
    )
    
    try:
        # Step 1: Download reinstall script
        download_cmd = """
        apt-get update && apt-get upgrade -y && \
        apt install wget curl -y && \
        wget -O reinstall.sh https://raw.github.com/bin456789/reinstall/main/reinstall.sh && \
        chmod +x reinstall.sh
        """
        
        success, output = await execute_ssh_command(
            vps["ip"],
            vps.get("ssh_port", 22),
            vps["ssh_user"],
            vps["ssh_pass"],
            download_cmd
        )
        
        if not success:
            error_text = f"""
{generate_header('GAGAL DOWNLOAD SCRIPT')}

{generate_separator(29)}
❌ *Gagal mendownload script install!*
{generate_separator(29)}
📛 Error Details:
`{output[:300]}`
{generate_separator(29)}
🔧 *Kemungkinan penyebab:*
├ Koneksi internet server bermasalah
├ Repository package tidak tersedia
├ Server out of disk space
└ Firewall memblokir download
{generate_separator(29)}
"""
            await processing_msg.edit_text(error_text, parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
        
        await processing_msg.edit_text(
            f"""
{generate_header('MENGINSTALL OS')}

{generate_separator(29)}
✅ Script berhasil didownload
{generate_separator(29)}
🚀 *Memulai install {os_name.capitalize()} {version if version else ''}...*
{generate_separator(29)}
⏱️ Proses install akan dimulai...
💡 *Tips:* Jangan tutup chat ini selama proses berjalan
{generate_separator(29)}
"""
        )
        
        # Step 2: Execute reinstall command
        if os_name in ['windows', 'dd']:
            install_cmd = f"bash reinstall.sh {os_name} {version}"
        elif version:
            install_cmd = f"echo -e '{password}\\n{password}' | timeout 1800 bash reinstall.sh {os_name} {version}"
        else:
            install_cmd = f"echo -e '{password}\\n{password}' | timeout 1800 bash reinstall.sh {os_name}"
        
        success, output = await execute_ssh_command(
            vps["ip"],
            vps.get("ssh_port", 22),
            vps["ssh_user"],
            vps["ssh_pass"],
            install_cmd
        )
        
        if not success:
            error_text = f"""
{generate_header('GAGAL MENGINSTALL')}

{generate_separator(29)}
❌ *Gagal menginstall OS!*
{generate_separator(29)}
📛 Error Details:
`{output[:500]}`
{generate_separator(29)}
🔧 *Kemungkinan penyebab:*
├ Image OS tidak tersedia
├ Tidak support architecture
├ Disk space tidak cukup
├ Network timeout
└ Script error
{generate_separator(29)}
"""
            await processing_msg.edit_text(error_text, parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
        
        # Step 3: Parse output untuk informasi
        info_match = re.search(r'\*\*\*\*\* INFO \*\*\*\*\*(.*?)Reboot to start', output, re.DOTALL)
        if info_match:
            info_text = info_match.group(1)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"📋 *Informasi Install:*\n```\n{info_text[:1000]}\n```",
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Step 4: Reboot server
        await execute_ssh_command(
            vps["ip"],
            vps.get("ssh_port", 22),
            vps["ssh_user"],
            vps["ssh_pass"],
            "reboot"
        )
        
        # Step 5: Update VPS password di database
        update_vps(vps_id, {"ssh_pass": password})
        
        # Step 6: Tampilkan success message
        success_text = f"""
{generate_header('REBUILD BERHASIL')}

{generate_separator(29)}
✅ *REBUILD SELESAI!*
{generate_separator(29)}
🎉 Server berhasil di-rebuild dengan:
{generate_separator(29)}
📋 *Detail Server Baru:*
├ Server: {vps.get('name', 'VPS')}
├ IP: `{vps['ip']}`
├ OS: {os_name.capitalize()} {version if version else '(Latest)'}
├ Password: `{password}`
├ SSH User: `{vps['ssh_user']}`
└ SSH Port: {vps.get('ssh_port', 22)}
{generate_separator(29)}
⚡ *Instruksi:*
1. Tunggu 5-10 menit untuk booting selesai
2. Login dengan password baru di atas
3. Install script VPN jika diperlukan
4. Set domain: `{vps.get('domain', 'super.oxygencrc.my.id')}`
{generate_separator(29)}
💡 *Password telah diupdate di database.*
{generate_separator(29)}
"""
        
        keyboard = [
            [InlineKeyboardButton("🔄 Rebuild Lain", callback_data="admin_rebuild_vps")],
            [InlineKeyboardButton("🖥️ List VPS", callback_data="admin_list_vps")],
            [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(success_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        
        # Step 7: Kirim notifikasi ke admin lain
        for admin_id in ADMIN_IDS:
            if admin_id != query.from_user.id:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"⚠️ *REBUILD NOTIFICATION*\n\n"
                        f"Server `{vps['ip']}` ({vps.get('name', 'VPS')}) "
                        f"telah di-rebuild oleh {query.from_user.first_name}\n"
                        f"OS: {os_name} {version}\n"
                        f"Waktu: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
        
    except Exception as e:
        error_text = f"""
{generate_header('ERROR REBUILD')}

{generate_separator(29)}
❌ *TERJADI ERROR SAAT REBUILD!*
{generate_separator(29)}
📛 Error Details:
`{str(e)[:300]}`
{generate_separator(29)}
🔧 *Silakan coba lagi atau hubungi developer.*
{generate_separator(29)}
"""
        await processing_msg.edit_text(error_text, parse_mode=ParseMode.MARKDOWN)
    
    return ConversationHandler.END

@check_admin
async def admin_auto_reboot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses set auto reboot"""
    query = update.callback_query
    await query.answer()
    
    text = f"""
{generate_header('AUTO REBOOT')}

{generate_separator(29)}
⏰ *SET AUTO REBOOT SERVER*
{generate_separator(29)}
Fitur ini akan membuat server reboot otomatis
pada waktu yang ditentukan.
{generate_separator(29)}
Pilih server untuk set auto reboot:
"""
    
    vps_list = get_all_vps()
    keyboard = []
    
    for vps_id, vps in vps_list.items():
        if vps.get("status") == "active":
            name = vps.get('name', f"VPS {vps['ip']}")
            button_text = f"🖥️ {name}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"auto_reboot_select_{vps_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return AUTO_REBOOT_TIME
                
        
async def user_trial_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fitur trial VPN"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user.get("trial_used", False):
        text = f"""
{generate_header('TRIAL SUDAH DIGUNAKAN')}

{generate_separator(29)}
❌ *Anda sudah menggunakan trial sebelumnya!*

Fitur trial hanya bisa digunakan sekali per user.
Silakan beli paket reguler untuk melanjutkan.
{generate_separator(29)}
"""
        
        keyboard = [
            [InlineKeyboardButton("🛒 Beli VPN", callback_data="user_buy_vpn")],
            [InlineKeyboardButton("🔙 Menu Utama", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ConversationHandler.END
    
    text = f"""
{generate_header('TRIAL VPN 40 MENIT')}

{generate_separator(29)}
🎁 *Dapatkan Trial VPN Gratis 40 Menit!*

⚠️ *Syarat & Ketentuan:*
├ 1 trial per user
├ Maksimal 40 menit
├ Limit 1 IP
├ Akun akan dihapus otomatis setelah expired
└ Tidak bisa diperpanjang
{generate_separator(29)}

Pilih jenis layanan trial:
"""
    
    keyboard = [
        [InlineKeyboardButton("🔐 SSH Trial", callback_data="trial_service_ssh")],
        [InlineKeyboardButton("⚡ VMess Trial", callback_data="trial_service_vmess")],
        [InlineKeyboardButton("🚀 VLESS Trial", callback_data="trial_service_vless")],
        [InlineKeyboardButton("🛡️ Trojan Trial", callback_data="trial_service_trojan")],
        [InlineKeyboardButton("🌓 Shadowsocks Trial", callback_data="trial_service_ss")],
        [InlineKeyboardButton("🟦 ZiVPN Trial", callback_data="trial_service_zivpn")],
        [InlineKeyboardButton("🔙 Menu Utama", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_SELECT_TRIAL_SERVICE

async def user_select_trial_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih layanan trial"""
    query = update.callback_query
    await query.answer()
    
    service_type = query.data.replace("trial_service_", "")
    context.user_data["trial_service"] = service_type
    
    service_names = {
        "ssh": "🔐 SSH",
        "vmess": "⚡ VMess", 
        "vless": "🚀 VLESS",
        "trojan": "🛡️ Trojan",
        "ss": "🌓 Shadowsocks",
        "zivpn": "🟦 ZiVPN"
    }
    
    vps_list = get_all_vps()
    
    if service_type == "zivpn":
        available_vps = {k: v for k, v in vps_list.items() 
                        if v.get("status") == "active" and v.get("type") == "zivpn"}
    else:
        available_vps = {k: v for k, v in vps_list.items() 
                        if v.get("status") == "active" and v.get("type") != "zivpn"}
    
    if not available_vps:
        text = f"""
{generate_header('TIDAK ADA SERVER')}

{generate_separator(29)}
⚠️ *Tidak Ada Server Tersedia*

Belum ada server {service_names.get(service_type)} yang aktif.
Silakan coba lagi nanti atau hubungi admin.
{generate_separator(29)}
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="user_trial_vpn")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ConversationHandler.END
    
    text = f"""
{generate_header(f'TRIAL {service_type.upper()}')}

{generate_separator(29)}
{service_names.get(service_type)} Trial - 40 Menit

Pilih server untuk trial:
"""
    
    keyboard = []
    for vps_id, vps in available_vps.items():
        name = vps.get('name', f"VPS {vps['ip']}")
        domain = vps.get('domain', 'N/A')
        
        button_text = f"🟢 {name} ({domain})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"trial_vps_{vps_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="user_trial_vpn")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_SELECT_TRIAL_VPS

async def user_create_trial(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buat akun trial dengan format yang mudah dicopy"""
    query = update.callback_query
    await query.answer()
    
    vps_id = context.user_data["trial_vps_id"]
    service_type = context.user_data["trial_service"]
    vps = get_vps(vps_id)
    
    user_id = query.from_user.id
    timestamp = int(datetime.now().timestamp())
    username = f"trial{user_id % 1000}_{timestamp % 10000}"
    
    processing_msg = await query.edit_message_text(
        f"""
{generate_header('MEMPROSES TRIAL')}

⏳ *Membuat akun trial {service_type.upper()}...*

Harap tunggu sebentar, proses mungkin memakan waktu 10-20 detik.
"""
    )
    
    if service_type == "ssh":
        success, error_msg, account_data = await create_ssh_trial(vps, username)
    elif service_type == "vmess":
        success, error_msg, account_data = await create_vmess_trial(vps, username)
    elif service_type == "vless":
        success, error_msg, account_data = await create_vless_trial(vps, username)
    elif service_type == "trojan":
        success, error_msg, account_data = await create_trojan_trial(vps, username)
    elif service_type == "ss":
        success, error_msg, account_data = await create_ss_trial(vps, username)
    elif service_type == "zivpn":
        success, error_msg, account_data = await create_zivpn_trial(vps, username)
    else:
        error_msg = "Jenis layanan tidak dikenal"
        success = False
    
    if success:
        update_user(user_id, {"trial_used": True})
        
        trial_id = account_data.get("trial_id", "")
        
        # Create account display yang mudah dicopy
        account_display = create_account_display(account_data, service_type, is_trial=True)
        
        # Buat header dengan emoji berbeda
        if service_type == "ssh":
            header_emoji = "🔐"
        elif service_type == "vmess":
            header_emoji = "⚡"
        elif service_type == "vless":
            header_emoji = "🚀"
        elif service_type == "trojan":
            header_emoji = "🛡️"
        elif service_type == "ss":
            header_emoji = "🌓"
        elif service_type == "zivpn":
            header_emoji = "🟦"
        else:
            header_emoji = "🎯"
        
        text = f"""
{generate_header(f'{header_emoji} TRIAL {service_type.upper()} BERHASIL')}

✅ *AKUN TRIAL BERHASIL DIBUAT!*

{account_display}

⚠️ *PERHATIAN:*
• Trial hanya berlaku 40 menit
• Tidak bisa diperpanjang
• Hanya untuk testing
• Akan otomatis terhapus setelah expired

📋 *CARA MENGGUNAKAN:*
1. Copy seluruh teks konfigurasi di atas
2. Import ke aplikasi VPN favorit Anda
3. Setup sesuai dengan petunjuk
4. Nikmati akses VPN trial!

💡 *TIP:*
• Gunakan aplikasi seperti HTTP Injector, AnXray, atau V2RayNG
• Pastikan koneksi internet aktif
• Jika ada masalah, restart aplikasi VPN
"""
        
        # Schedule deletion after 40 minutes
        asyncio.create_task(
            delete_trial_account_after_delay(trial_id, 40 * 60)
        )
        
        # Kirim sebagai quote agar mudah dicopy
        try:
            # Kirim konfigurasi sebagai teks biasa (tanpa markdown) untuk memudahkan copy
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=account_display,
                reply_to_message_id=processing_msg.message_id
            )
            
            # Kirim pesan sukses terpisah
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"✅ *TRIAL {service_type.upper()} BERHASIL DIBUAT!*\n\nAkun trial Anda telah siap digunakan. Copy konfigurasi di pesan sebelumnya dan import ke aplikasi VPN Anda.",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            print(f"Error sending trial account: {e}")
            # Fallback ke cara lama jika ada error
            keyboard = [
                [InlineKeyboardButton("🔄 Coba Layanan Lain", callback_data="user_trial")],
                [InlineKeyboardButton("🛒 Beli VPN Reguler", callback_data="user_buy_vpn")],
                [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    else:
        # Error message
        text = f"""
{generate_header('❌ GAGAL MEMBUAT TRIAL')}

❌ *GAGAL MEMBUAT AKUN TRIAL!*

📛 *Error Details:*
`{error_msg[:300]}`

🔄 *Solusi yang bisa dicoba:*
1. Coba lagi beberapa menit kemudian
2. Pilih server/VPS yang berbeda
3. Hubungi admin jika masalah berlanjut

💡 *Tips:*
- Pastikan server VPS aktif dan online
- Coba jenis layanan yang berbeda
- Gunakan username yang unik
"""
        
        keyboard = [
            [InlineKeyboardButton("🔄 Coba Layanan Lain", callback_data="user_trial_vpn")],
            [InlineKeyboardButton("📞 Bantuan Admin", url=f"https://t.me/nusasarivpn{context.bot.username}")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END    

async def delete_trial_account_after_delay(trial_id: str, delay_seconds: int):
    """Hapus akun trial setelah delay tertentu"""
    await asyncio.sleep(delay_seconds)
    
    delete_trial_account(trial_id)
    
    print(f"✅ Trial account {trial_id} deleted after {delay_seconds} seconds")

async def user_check_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cek detail akun yang dimiliki user"""
    query = update.callback_query
    await query.answer()
    
    text = f"""
{generate_header('CEK DETAIL AKUN')}

{generate_separator(29)}
🔍 Masukkan username akun VPN yang ingin Anda cek:
{generate_separator(29)}
"""
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return USER_INPUT_ACCOUNT_USERNAME

async def handle_check_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pencarian akun dengan tampilan LENGKAP"""
    username = update.message.text.strip()
    
    # Cari di semua database
    accounts = load_json(ACCOUNTS_DB)
    account_data = None
    
    for acc_id, acc in accounts.items():
        if acc.get("username") == username:
            account_data = acc
            account_data["id"] = acc_id
            break
    
    # Jika tidak ditemukan di accounts, coba di trial accounts
    if not account_data:
        trials = load_json(TRIAL_ACCOUNTS_DB)
        for trial_id, trial in trials.items():
            if trial.get("username") == username:
                account_data = trial
                account_data["id"] = trial_id
                account_data["is_trial"] = True
                break
    
    if not account_data:
        # Coba cari di akun user
        user_id = update.effective_user.id
        user = get_user(user_id)
        
        for acc in user.get("vpn_accounts", []):
            if acc.get("username") == username:
                account_data = acc
                break
    
    if not account_data:
        await update.message.reply_text(
            f"""
{generate_header('❌ AKUN TIDAK DITEMUKAN')}

{generate_separator(29)}
🔍 *PENCARIAN AKUN GAGAL*
{generate_separator(29)}
Username: `{username}`
{generate_separator(29)}
📛 *Akun tidak ditemukan atau tidak ada akses*
{generate_separator(29)}
"""
        )
        return ConversationHandler.END
    
    # TAMPILAN LENGKAP TANPA DIPANGKAS
    service_type = account_data.get("service_type", "ssh")
    is_trial = account_data.get("is_trial", False)
    trial_label = " (TRIAL)" if is_trial else ""
    
    # Header berdasarkan tipe layanan
    service_icons = {
        "ssh": "🔐", "vmess": "⚡", "vless": "🚀",
        "trojan": "🛡️", "ss": "🌓", "zivpn": "🟦"
    }
    icon = service_icons.get(service_type, "🔧")
    
    # Format tanggal
    created_date = format_datetime(account_data.get('created_at', ''))
    expires_date = format_datetime(account_data.get('expires_at', ''))
    
    # Hitung sisa waktu
    try:
        expires = datetime.fromisoformat(account_data.get('expires_at', '').replace('Z', '+00:00'))
        now = datetime.now()
        remaining = expires - now
        if remaining.days < 0:
            remaining_text = "⏳ *EXPIRED*"
        else:
            remaining_text = f"⏳ *Sisa:* {remaining.days} hari {remaining.seconds//3600} jam"
    except:
        remaining_text = "⏳ *Masa aktif:* N/A"
    
    # Buat tampilan lengkap
    display = f"""
{generate_header(f'{icon} DETAIL AKUN {service_type.upper()}{trial_label}')}

{'=' * 40}
📋 *INFORMASI AKUN*
{'=' * 40}
👤 *Username:* `{account_data.get('username', 'N/A')}`
🔧 *Tipe Layanan:* {service_type.upper()}{' (TRIAL)' if is_trial else ''}
🆔 *Account ID:* `{account_data.get('id', 'N/A')}`
{'=' * 40}

🌐 *INFORMASI SERVER*
{'=' * 40}
🖥️ *Server:* {account_data.get('vps_id', 'N/A')}
📍 *Domain:* {account_data.get('domain', 'N/A')}
🌍 *IP Server:* {account_data.get('server_ip', account_data.get('vps_ip', 'N/A'))}
{'=' * 40}

⚙️ *KONFIGURASI*
{'=' * 40}
"""
    
    # Tambahkan konfigurasi berdasarkan tipe layanan
    if service_type == "ssh":
        display += f"""
🔐 *Password:* `{account_data.get('password', 'N/A')}`
🌐 *IP Limit:* {account_data.get('ip_limit', 2)} IP
├ Base IP: {account_data.get('base_ip_limit', 1)} IP
└ Extra IP: {account_data.get('extra_ips', 0)} IP
💾 *Quota:* {account_data.get('quota', 2)} GB
{'=' * 40}
🔌 *PORT & PROTOCOL*
{'=' * 40}
📡 OpenSSH: 22
⚡ Dropbear: 22, 109
🔌 SSH WS: 80, 8080, 2086, 8880
🔒 SSL/TLS: 443, 8443
🌀 BadVPN: 7100, 7300
{'=' * 40}
🌐 *HTTP CUSTOM*
{'=' * 40}
`{account_data.get('domain', 'N/A')}:1-65535@{account_data.get('username', 'N/A')}:{account_data.get('password', 'N/A')}`
{'=' * 40}
"""
    
    elif service_type == "vmess":
        display += f"""
🆔 *UUID:* `{account_data.get('uuid', 'N/A')}`
🌐 *IP Limit:* {account_data.get('ip_limit', 2)} IP
💾 *Quota:* {account_data.get('quota', 200)} GB
{'=' * 40}
🔗 *LINK KONFIGURASI*
{'=' * 40}
⚡ *TLS (443):*
`{account_data.get('vmess_tls', 'N/A')}`
{'=' * 40}
⚡ *Non-TLS (80):*
`{account_data.get('vmess_ntls', 'N/A')}`
{'=' * 40}
⚡ *gRPC (443):*
`{account_data.get('vmess_grpc', 'N/A')}`
{'=' * 40}
"""
    
    elif service_type == "vless":
        display += f"""
🆔 *UUID:* `{account_data.get('uuid', 'N/A')}`
🌐 *IP Limit:* {account_data.get('ip_limit', 2)} IP
💾 *Quota:* {account_data.get('quota', 200)} GB
{'=' * 40}
🔗 *LINK KONFIGURASI*
{'=' * 40}
🚀 *TLS (443):*
`{account_data.get('vless_tls', 'N/A')}`
{'=' * 40}
🚀 *Non-TLS (80):*
`{account_data.get('vless_ntls', 'N/A')}`
{'=' * 40}
🚀 *gRPC (443):*
`{account_data.get('vless_grpc', 'N/A')}`
{'=' * 40}
"""
    
    elif service_type == "trojan":
        display += f"""
🔑 *Password:* `{account_data.get('uuid', 'N/A')}`
🌐 *IP Limit:* {account_data.get('ip_limit', 2)} IP
💾 *Quota:* {account_data.get('quota', 200)} GB
{'=' * 40}
🔗 *LINK KONFIGURASI*
{'=' * 40}
🛡️ *WS TLS (443):*
`{account_data.get('trojan_ws', 'N/A')}`
{'=' * 40}
🛡️ *gRPC (443):*
`{account_data.get('trojan_grpc', 'N/A')}`
{'=' * 40}
"""
    
    elif service_type == "ss":
        display += f"""
🔑 *Password:* `{account_data.get('uuid', account_data.get('password', 'N/A'))}`
🔐 *Cipher:* {account_data.get('cipher', 'aes-128-gcm')}
🌐 *IP Limit:* {account_data.get('ip_limit', 2)} IP
💾 *Quota:* {account_data.get('quota', 200)} GB
{'=' * 40}
🔗 *LINK KONFIGURASI*
{'=' * 40}
🌓 *WS TLS (443):*
`{account_data.get('ss_ws_tls', 'N/A')}`
{'=' * 40}
🌓 *WS Non-TLS (80):*
`{account_data.get('ss_ws_ntls', 'N/A')}`
{'=' * 40}
🌓 *gRPC (443):*
`{account_data.get('ss_grpc', 'N/A')}`
{'=' * 40}
"""
    
    elif service_type == "zivpn":
        display += f"""
🔑 *Password:* `{account_data.get('password', 'N/A')}`
🌐 *IP Limit:* {account_data.get('ip_limit', 2)} IP
{'=' * 40}
🔧 *KONFIGURASI ZIVPN*
{'=' * 40}
📡 *Protocol:* ZiVPN
🔌 *Port:* 443
📱 *Device Limit:* {account_data.get('ip_limit', 2)} device
{'=' * 40}
"""
    
    # Tambahkan informasi waktu
    display += f"""
⏰ *INFORMASI WAKTU*
{'=' * 40}
📅 *Dibuat:* {created_date}
⏳ *Berakhir:* {expires_date}
{remaining_text}
📆 *Durasi:* {account_data.get('duration', 1)} hari
{'=' * 40}
"""
    
    # Tambahkan status
    try:
        expires = datetime.fromisoformat(account_data.get('expires_at', '').replace('Z', '+00:00'))
        if datetime.now() > expires:
            status = "❌ *STATUS: EXPIRED*"
        elif is_trial:
            status = "⚠️ *STATUS: TRIAL*"
        else:
            status = "✅ *STATUS: AKTIF*"
    except:
        status = "❓ *STATUS: UNKNOWN*"
    
    display += f"""
{status}
{'=' * 40}
"""
    
    # Tambahkan link download config
    if not is_trial:
        domain = account_data.get('domain', 'N/A')
        username = account_data.get('username', 'N/A')
        display += f"""
🔗 *DOWNLOAD CONFIG*
{'=' * 40}
🌐 *File Config:*
https://{domain}:81/{service_type}-{username}.txt
{'=' * 40}
"""
    
    # Kirim pesan
    try:
        # Karena Telegram punya batas 4096 karakter, kita split jika terlalu panjang
        if len(display) > 4000:
            # Split menjadi beberapa bagian
            parts = []
            current_part = ""
            lines = display.split('\n')
            
            for line in lines:
                if len(current_part) + len(line) + 1 < 4000:
                    current_part += line + '\n'
                else:
                    parts.append(current_part)
                    current_part = line + '\n'
            
            if current_part:
                parts.append(current_part)
            
            for i, part in enumerate(parts):
                if i == 0:
                    await update.message.reply_text(part, parse_mode=ParseMode.MARKDOWN)
                else:
                    await update.message.reply_text(f"```\n{part}\n```", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(display, parse_mode=ParseMode.MARKDOWN)
    
    except Exception as e:
        # Fallback ke format sederhana jika ada error
        simple_display = f"""
Account: {account_data.get('username')}
Type: {service_type}
Domain: {account_data.get('domain')}
IP Limit: {account_data.get('ip_limit', 2)}
Expires: {expires_date}
Status: {'Trial' if is_trial else 'Active'}
"""
        await update.message.reply_text(simple_display)
    
    # Tambahkan tombol aksi
    keyboard = [
        [InlineKeyboardButton("🔄 Upgrade Akun Ini", callback_data=f"upgrade_account_{account_data.get('username', '')}")],
        [InlineKeyboardButton("🔍 Cek Akun Lain", callback_data="user_check_account")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Pilih aksi untuk akun ini:",
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END
                    
                    
                    
async def admin_topup_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin melihat semua transaksi topup"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("❌ Akses ditolak.")
        return
    
    transactions = load_json(TOPUP_DB)
    
    if not transactions:
        text = f"""
{generate_header('SEMUA TRANSAKSI TOPUP')}

{generate_separator(29)}
📭 *TIDAK ADA TRANSAKSI*
{generate_separator(29)}
Belum ada transaksi topup.
{generate_separator(29)}
"""
    else:
        # Hitung statistik
        total_transactions = len(transactions)
        completed = sum(1 for tx in transactions.values() if tx.get("status") == "completed")
        pending = sum(1 for tx in transactions.values() if tx.get("status") == "pending")
        expired = sum(1 for tx in transactions.values() if tx.get("status") == "expired")
        total_amount = sum(tx.get("amount", 0) for tx in transactions.values() if tx.get("status") == "completed")
        
        text = f"""
{generate_header('SEMUA TRANSAKSI TOPUP')}

{generate_separator(29)}
📊 *STATISTIK:*
├ Total Transaksi: {total_transactions}
├ Berhasil: {completed}
├ Pending: {pending}
├ Expired: {expired}
└ Total Amount: {format_money(total_amount)}
{generate_separator(29)}
"""
        
        # Tampilkan 10 transaksi terbaru
        sorted_tx = sorted(
            transactions.values(),
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )[:10]
        
        for i, tx in enumerate(sorted_tx, 1):
            user_id_tx = tx.get("user_id", "N/A")
            amount = tx.get("amount", 0)
            status = tx.get("status", "unknown")
            created = format_datetime(tx.get("created_at", ""))
            ref_id = tx.get("ref_id", "")[:8]
            
            text += f"""
{i}. *{ref_id}...* - {format_money(amount)}
├ User: {user_id_tx}
├ Status: {status.upper()}
└ Created: {created}
{generate_separator(20)}
"""
    
    keyboard = [
        [InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
                    
                    
async def user_buy_vpn_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses pembelian VPN"""
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    if user["balance"] < 1000:
        text = f"""
{generate_header('SALDO TIDAK CUKUP')}

{generate_separator(29)}
⚠️ *Insufficient Balance*

💰 Your Balance: {format_money(user['balance'])}
💰 Minimum Required: {format_money(1000)}
{generate_separator(29)}
"""
        keyboard = [
            [InlineKeyboardButton("💰 Top Up Saldo", callback_data="user_topup")],
            [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ConversationHandler.END
    
    vps_list = get_all_vps()
    active_vps = {k: v for k, v in vps_list.items() if v.get("status") == "active"}
    
    if not active_vps:
        text = f"""
{generate_header('NO SERVER AVAILABLE')}

{generate_separator(29)}
⚠️ *No VPN Servers Available*
{generate_separator(29)}
"""
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    text = f"""
{generate_header('PILIH SERVER VPS')}

{generate_separator(29)}
🖥️ *Available VPN Servers*
{generate_separator(29)}
"""
    
    keyboard = []
    for vps_id, vps in active_vps.items():
        name = vps.get('name', f"VPS {vps['ip']}")
        vps_type = vps.get('type', 'regular')
        icon = "🟦" if vps_type == "zivpn" else "🟩"
        status = "🟢" if vps.get("status") == "active" else "🔴"
        
        button_text = f"{icon}{status} {name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_vps_{vps_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Batalkan", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_SELECT_VPS

async def user_select_vps_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk memilih VPS"""
    query = update.callback_query
    await query.answer()
    
    vps_id = query.data.replace("select_vps_", "")
    vps = get_vps(vps_id)
    
    if not vps:
        await query.edit_message_text("❌ Server tidak ditemukan.")
        return ConversationHandler.END
    
    context.user_data["selected_vps"] = vps_id
    context.user_data["vps_info"] = vps
    
    vps_type = vps.get("type", "regular")
    
    keyboard = []
    
    if vps_type == "zivpn":
        keyboard.append([InlineKeyboardButton("🟦 ZiVPN ONLY", callback_data="service_zivpn")])
    else:
        keyboard.append([InlineKeyboardButton("🔐 SSH", callback_data="service_ssh")])
        keyboard.append([InlineKeyboardButton("⚡ VMess", callback_data="service_vmess")])
        keyboard.append([InlineKeyboardButton("🚀 VLESS", callback_data="service_vless")])
        keyboard.append([InlineKeyboardButton("🛡️ Trojan", callback_data="service_trojan")])
        keyboard.append([InlineKeyboardButton("🌓 Shadowsocks", callback_data="service_ss")])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="user_buy_vpn")])
    
    text = f"""
{generate_header('PILIH JENIS LAYANAN')}

{generate_separator(29)}
🖥️ *Server:* {vps.get('name', 'VPS')}
📍 *Location:* {vps.get('location', 'Unknown')}
🌐 *Domain:* {vps.get('domain', 'N/A')}
🔧 *Tipe:* {'ZiVPN ONLY' if vps_type == 'zivpn' else 'REGULAR'}
{generate_separator(29)}

Pilih jenis layanan VPN:
"""
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_SELECT_SERVICE

async def user_select_service_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk memilih jenis layanan"""
    query = update.callback_query
    await query.answer()
    
    service_type = query.data.replace("service_", "")
    context.user_data["selected_service"] = service_type
    
    service_names = {
        "ssh": "🔐 SSH",
        "vmess": "⚡ VMess",
        "vless": "🚀 VLESS",
        "trojan": "🛡️ Trojan",
        "ss": "🌓 Shadowsocks",
        "zivpn": "🟦 ZiVPN"
    }
    
    text = f"""
{generate_header('INPUT USERNAME')}

{generate_separator(29)}
{service_names.get(service_type, service_type.upper())}
{generate_separator(29)}

📝 *Masukkan username yang diinginkan:*

📌 *Persyaratan:*
├ 3-15 karakter
├ Hanya huruf, angka, underscore
└ Tidak boleh ada spasi atau karakter khusus

✍️ *Contoh:* `user123`, `vpn_user`, `client01`
"""
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return USER_INPUT_USERNAME

async def user_input_username_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk input username"""
    username = update.message.text.strip()
    
    if not re.match(r'^[a-zA-Z0-9_]{3,15}$', username):
        await update.message.reply_text(
            f"""
{generate_header('INVALID USERNAME')}

{generate_separator(29)}
❌ *Format Username Tidak Valid!*
{generate_separator(29)}
Username harus memenuhi persyaratan:
├ 3-15 karakter
├ Hanya huruf, angka, underscore
└ Tidak boleh ada spasi atau karakter khusus

💡 *Contoh:* `user123`, `vpn_user`, `client01`
{generate_separator(29)}
"""
        )
        return USER_INPUT_USERNAME
    
    context.user_data["username"] = username
    
    text = f"""
{generate_header('TAMBAH IP EKSTRA')}

{generate_separator(29)}
👤 Username: `{username}`
🔧 Service: {context.user_data['selected_service'].upper()}
📊 IP Limit Default: 1 IP
{generate_separator(29)}

Apakah Anda ingin menambah IP ekstra?
💰 *Harga per IP tambahan:* {format_money(EXTRA_IP_PRICE)}
{generate_separator(29)}

Pilih jumlah IP tambahan:
"""
    
    keyboard = [
        [InlineKeyboardButton("➕ 0 IP Tambahan (Total 1 IP)", callback_data="extra_ips_0")],
        [InlineKeyboardButton("➕ 1 IP Tambahan (Total 2 IP)", callback_data="extra_ips_1")],
        [InlineKeyboardButton("➕ 2 IP Tambahan (Total 3 IP)", callback_data="extra_ips_2")],
        [InlineKeyboardButton("➕ 3 IP Tambahan (Total 4 IP)", callback_data="extra_ips_3")],
        [InlineKeyboardButton("➕ 4 IP Tambahan (Total 5 IP)", callback_data="extra_ips_4")],
        [InlineKeyboardButton("➕ 5 IP Tambahan (Total  IP)", callback_data="extra_ips_5")],
        [InlineKeyboardButton("🔙 Kembali", callback_data=f"service_{context.user_data['selected_service']}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_SELECT_EXTRA_IPS

async def user_select_extra_ips_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk memilih jumlah IP tambahan"""
    query = update.callback_query
    await query.answer()
    
    extra_ips = int(query.data.replace("extra_ips_", ""))
    context.user_data["extra_ips"] = extra_ips
    
    vps_id = context.user_data["selected_vps"]
    service_type = context.user_data["selected_service"]
    
    keyboard = []
    durations = {
        "7": "7 Day",
        "15": "15 Days", 
        "30": "30 Days",
        "90": "90 Days",
        "365": "1 Year"
    }
    
    extra_ip_cost = calculate_extra_ip_cost(extra_ips)
    
    text = f"""
{generate_header('SELECT DURATION')}

{generate_separator(29)}
👤 Username: `{context.user_data["username"]}`
🔧 Service: {service_type.upper()}
➕ IP Tambahan: {extra_ips} IP (+{format_money(extra_ip_cost)})
{generate_separator(29)}

📅 *Pilih Durasi Langganan:*
"""
    
    for dur_code, dur_name in durations.items():
        base_price = get_actual_price(vps_id, service_type, dur_code)
        total_price = base_price + extra_ip_cost
        if total_price > 0:
            button_text = f"{dur_name} - {format_money(total_price)}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"duration_{dur_code}")])
            text += f"\n{dur_name}: {format_money(total_price)}"
    
    text += "\n\n💡 *Note:* Durasi lebih lama lebih hemat!"
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data=f"service_{service_type}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_SELECT_DURATION

async def user_select_duration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk memilih durasi"""
    query = update.callback_query
    await query.answer()
    
    duration = int(query.data.replace("duration_", ""))
    context.user_data["selected_duration"] = duration
    
    vps_id = context.user_data["selected_vps"]
    service_type = context.user_data["selected_service"]
    extra_ips = context.user_data.get("extra_ips", 0)
    
    base_price = get_actual_price(vps_id, service_type, str(duration))
    extra_ip_cost = calculate_extra_ip_cost(extra_ips)
    total_price = base_price + extra_ip_cost
    
    # Simpan semua harga ke context
    context.user_data["price"] = total_price
    context.user_data["base_price"] = base_price
    context.user_data["extra_ip_cost"] = extra_ip_cost
    
    user_id = query.from_user.id
    user = get_user(user_id)
    
    username = context.user_data["username"]
    vps = context.user_data["vps_info"]
    vps_name = vps.get("name", "VPS")
    
    durations_text = {"7": "7 Hari", "15": "15 Hari", "30": "30 Hari", "90": "90 Hari", "365": "1 Tahun"}
    duration_text = durations_text.get(str(duration), f"{duration} Hari")
    
    if user["balance"] < total_price:
        text = f"""
{generate_header('SALDO TIDAK CUKUP')}

{generate_separator(29)}
❌ *Saldo Tidak Mencukupi!*
{generate_separator(29)}
💰 *Rincian Harga:*
├ Harga Base ({duration_text}): {format_money(base_price)}
├ Tambahan IP ({extra_ips} IP): {format_money(extra_ip_cost)}
└ **TOTAL ORDER: {format_money(total_price)}**
{generate_separator(29)}
💰 *Status Saldo:*
├ Saldo Anda: {format_money(user['balance'])}
├ Biaya Order: {format_money(total_price)}
└ **KEKURANGAN: {format_money(total_price - user['balance'])}**
{generate_separator(29)}
"""
        keyboard = [
            [InlineKeyboardButton("💰 Top Up Sekarang", callback_data="user_topup")],
            [InlineKeyboardButton("🔙 Pilih Durasi Lain", callback_data=f"service_{service_type}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return USER_SELECT_DURATION
    
    if service_type == "ssh" or service_type == "zivpn":
        password = str(uuid.uuid4())[:12]
        context.user_data["password"] = password
        password_info = f"\n├ Password: `{password}`"
    else:
        password_info = ""
    
    text = f"""
{generate_header('KONFIRMASI ORDER')}

{generate_separator(29)}
✅ *Siap Menyelesaikan Order Anda!*
{generate_separator(29)}
📋 *Detail Order:*
┌ Layanan: {service_type.upper()}
├ Username: `{username}`{password_info}
├ Server: {vps_name}
├ Domain: {vps.get('domain', 'N/A')}
├ Durasi: {duration_text}
├ IP Limit Base: 1 IP
├ IP Tambahan: {extra_ips} IP
├ **Biaya Base: {format_money(base_price)}**
├ **Biaya IP Tambahan: {format_money(extra_ip_cost)}**
└ **TOTAL HARGA: {format_money(total_price)}**
{generate_separator(29)}
💰 *Informasi Saldo:*
├ Saldo Saat Ini: {format_money(user['balance'])}
├ Biaya Order: {format_money(total_price)}
└ **Sisa Saldo: {format_money(user['balance'] - total_price)}**
{generate_separator(29)}
⚠️ *Silakan konfirmasi order Anda:*
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ KONFIRMASI & BAYAR SEKARANG", callback_data="confirm_payment")],
        [InlineKeyboardButton("❌ BATALKAN ORDER", callback_data="cancel_payment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_CONFIRM_ORDER


async def show_duration_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """Tampilkan halaman durasi dengan pagination"""
    query = update.callback_query
    await query.answer()
    
    print(f"[DEBUG] show_duration_page called with page: {page}")
    
    vps_id = context.user_data["selected_vps"]
    service_type = context.user_data["selected_service"]
    extra_ips = context.user_data.get("extra_ips", 0)
    
    # Dapatkan semua durasi yang tersedia
    available_durations = get_available_durations(vps_id, service_type)
    
    if not available_durations:
        text = f"""
{generate_header('TIDAK ADA DURASI TERSEDIA')}

{generate_separator(29)}
⚠️ *Tidak Ada Durasi Tersedia*
{generate_separator(29)}
Belum ada harga yang diatur untuk layanan {service_type.upper()} di server ini.
{generate_separator(29)}
"""
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"service_{service_type}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return USER_SELECT_DURATION
    
    # Pagination
    items_per_page = 8
    total_pages = (len(available_durations) + items_per_page - 1) // items_per_page
    
    # Validasi page
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * items_per_page
    end_idx = min(page * items_per_page, len(available_durations))
    
    current_durations = available_durations[start_idx:end_idx]
    
    keyboard = []
    
    for duration_str in current_durations:
        final_price, price_source = get_final_price(vps_id, service_type, duration_str)
        extra_ip_cost = calculate_extra_ip_cost(extra_ips)
        total_price = final_price + extra_ip_cost
        
        if final_price == 0:
            continue  # Skip jika harga 0
        
        duration_text = format_duration_text(duration_str)
        
        # Tentukan icon berdasarkan source harga
        if price_source == "server_specific":
            icon = "💰"  # Harga khusus server
        elif price_source == "default":
            icon = "💲"  # Harga default
        else:
            icon = "⚠️"
        
        button_text = f"{icon} {duration_text} - {format_money(total_price)}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"duration_{duration_str}")])
    
    # Navigation buttons
    nav_buttons = []
    
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Sebelumnya", callback_data=f"duration_page_{page-1}"))
    
    # Tombol halaman tengah
    nav_buttons.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("Selanjutnya ➡️", callback_data=f"duration_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Info durasi yang tersedia
    duration_info = f"📋 Durasi tersedia: {len(available_durations)} pilihan"
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data=f"service_{service_type}")])
    
    text = f"""
{generate_header('PILIH DURASI')}

{generate_separator(29)}
{duration_info}
{generate_separator(29)}
📊 *Halaman {page}/{total_pages}*
{generate_separator(29)}
📅 *Pilih Durasi Langganan:*
{generate_separator(29)}
💰 = Harga khusus untuk server ini
💲 = Harga default
{generate_separator(29)}
"""
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return USER_SELECT_DURATION

async def user_confirm_order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk konfirmasi order dengan tampilan lengkap"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_payment":
        await query.edit_message_text(
            f"""
{generate_header('❌ ORDER DIBATALKAN')}

{generate_separator(29)}
📛 *ORDER DIBATALKAN*
{generate_separator(29)}
🔄 Order VPN Anda telah dibatalkan.
💰 Tidak ada pemotongan saldo yang dilakukan.
📋 Anda bisa membuat order baru kapan saja.
{generate_separator(29)}
🔄 *Kembali ke menu utama...*
{generate_separator(29)}
"""
        )
        return ConversationHandler.END
    
    user_id = query.from_user.id
    vps_id = context.user_data["selected_vps"]
    vps = context.user_data["vps_info"]
    service_type = context.user_data["selected_service"]
    duration = context.user_data["selected_duration"]
    total_price = context.user_data["price"]
    base_price = context.user_data["base_price"]
    extra_ip_cost = context.user_data["extra_ip_cost"]
    extra_ips = context.user_data.get("extra_ips", 0)
    username = context.user_data["username"]
    
    # Validasi saldo menggunakan handler baru
    if not BalanceUpdateHandler.validate_user_balance(user_id, total_price):
        text = f"""
{generate_header('❌ SALDO TIDAK CUKUP')}

{generate_separator(29)}
💰 *SALDO TIDAK CUKUP*
{generate_separator(29)}
📊 Saldo Anda: {format_money(BalanceUpdateHandler.get_user_balance(user_id))}
💳 Kebutuhan: {format_money(total_price)}
📉 Kekurangan: {format_money(total_price - BalanceUpdateHandler.get_user_balance(user_id))}
{generate_separator(29)}
💡 *Silakan top up saldo terlebih dahulu.*
{generate_separator(29)}
"""
        keyboard = [
            [InlineKeyboardButton("💰 Top Up Sekarang", callback_data="user_topup")],
            [InlineKeyboardButton("🔙 Pilih Durasi Lain", callback_data=f"service_{service_type}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return USER_SELECT_DURATION
    
    order_data = {
        "user_id": user_id,
        "vps_id": vps_id,
        "service_type": service_type,
        "duration": duration,
        "price": total_price,
        "base_price": base_price,
        "extra_ip_cost": extra_ip_cost,
        "extra_ips": extra_ips,
        "status": "processing",
        "username": username,
        "vps_name": vps.get('name', 'VPS'),
        "vps_ip": vps.get('ip', 'N/A'),
        "vps_domain": vps.get('domain', 'N/A'),
        "created_at": datetime.now().isoformat()
    }
    
    order_id = add_order(order_data)
    context.user_data["order_id"] = order_id
    
    # Dapatkan saldo dari BalanceUpdateHandler
    user_balance = BalanceUpdateHandler.get_user_balance(user_id)
    new_balance = user_balance - total_price
    
    # Animation messages
    animation_steps = [
        f"""
{generate_header('⚙️ MEMPROSES ORDER')}

{generate_separator(29)}
⏳ *MEMPERSIAPKAN ORDER...*
{generate_separator(29)}
🔄 Memverifikasi data order...
📋 Memeriksa ketersediaan server...
💾 Menyiapkan konfigurasi...
{generate_separator(29)}
""",
        f"""
{generate_header('⚙️ MEMPROSES ORDER')}

{generate_separator(29)}
⏳ *MENGHUBUNGKAN KE SERVER...*
{generate_separator(29)}
🌐 Menghubungkan ke server {vps.get('name', 'VPS')}...
🔐 Autentikasi SSH...
📡 Membuka koneksi remote...
{generate_separator(29)}
""",
        f"""
{generate_header('⚙️ MEMPROSES ORDER')}

{generate_separator(29)}
⏳ *MEMBUAT AKUN VPN...*
{generate_separator(29)}
👤 Membuat username: `{username}`
🔧 Menjalankan script di server...
⚙️ Mengkonfigurasi {service_type.upper()}...
🔄 Restarting service...
{generate_separator(29)}
"""
    ]
    
    processing_msg = await query.edit_message_text(
        animation_steps[0],
        parse_mode=ParseMode.MARKDOWN
    )
    
    for i, step in enumerate(animation_steps[1:], 1):
        await asyncio.sleep(2)
        await processing_msg.edit_text(step, parse_mode=ParseMode.MARKDOWN)
    
    await asyncio.sleep(1)
    
    success = False
    error_msg = ""
    account_data = {}
    
    try:
        if service_type == "ssh":
            password = context.user_data.get("password", str(uuid.uuid4())[:8])
            success, error_msg, account_data = await create_ssh_account(
                vps, username, password, duration, extra_ips=extra_ips
            )
        elif service_type == "vmess":
            success, error_msg, account_data = await create_vmess_account(
                vps, username, duration, extra_ips=extra_ips
            )
        elif service_type == "vless":
            success, error_msg, account_data = await create_vless_account(
                vps, username, duration, extra_ips=extra_ips
            )
        elif service_type == "trojan":
            success, error_msg, account_data = await create_trojan_account(
                vps, username, duration, extra_ips=extra_ips
            )
        elif service_type == "ss":
            success, error_msg, account_data = await create_ss_account(
                vps, username, duration, extra_ips=extra_ips
            )
        elif service_type == "zivpn":
            password = context.user_data.get("password", str(uuid.uuid4())[:12])
            success, error_msg, account_data = await create_zivpn_account(
                vps, username, duration, extra_ips=extra_ips
            )
        else:
            error_msg = f"Jenis layanan tidak dikenal: {service_type}"
    except Exception as e:
        success = False
        error_msg = f"Error: {str(e)}"
        import traceback
        print(f"Error creating account: {traceback.format_exc()}")
    
    if success:
        # Gunakan handler baru untuk update pembelian VPN
        BalanceUpdateHandler.update_vpn_purchase(
            user_id, 
            total_price, 
            f"Pembelian {service_type} {duration} hari + {extra_ips} IP"
        )
        
        # Update data user lainnya
        user = get_user(user_id)
        if "vpn_accounts" not in user:
            user["vpn_accounts"] = []
        account_data["order_id"] = order_id
        account_data["extra_ips"] = extra_ips
        user["vpn_accounts"].append(account_data)
        
        # Update statistik user (menggunakan fungsi lama untuk data tambahan)
        update_user(user_id, {
            "total_spent": user.get("total_spent", 0) + total_price,
            "total_orders": user.get("total_orders", 0) + 1,
            "last_active": datetime.now().isoformat(),
            "vpn_accounts": user["vpn_accounts"]
        })
        
        account_data["user_id"] = user_id
        account_id = add_account(account_data)
        
        update_order(order_id, {
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "account_id": account_id,
            "account_data": account_data
        })
        
        # Tambahkan transaksi (opsional, tergantung apakah BalanceUpdateHandler sudah menangani ini)
        add_transaction({
            "user_id": user_id,
            "type": "purchase",
            "amount": total_price,
            "description": f"Pembelian {service_type} {duration} hari + {extra_ips} IP tambahan",
            "order_id": order_id,
            "account_id": account_id,
            "status": "completed",
            "created_at": datetime.now().isoformat()
        })
        
        # Create account display based on service type
        account_display = create_account_display(account_data, service_type, is_trial=False)
        
        # Dapatkan saldo terbaru setelah pembelian
        latest_balance = BalanceUpdateHandler.get_user_balance(user_id)
        
        # Create order summary
        order_summary = f"""
{generate_header('🎉 ORDER BERHASIL 🎉')}

{generate_separator(29)}
✅ *AKUN VPN BERHASIL DIBUAT!*
{generate_separator(29)}
📋 *DETAIL ORDER:*
{generate_separator(29)}
🆔 Order ID: `{order_id}`
👤 Username: `{username}`
🛒 Service: {service_type.upper()}
🖥️ Server: {vps['name']}
📍 Domain: {vps.get('domain', 'N/A')}
📅 Duration: {duration} days
🌐 IP Limit: {account_data.get('ip_limit', 2 + extra_ips)} IPs
➕ Extra IPs: {extra_ips} IPs
{generate_separator(29)}
💰 *PAYMENT DETAILS:*
{generate_separator(29)}
💵 Base Price: {format_money(base_price)}
➕ Extra IP Cost: {format_money(extra_ip_cost)}
💰 Total Price: {format_money(total_price)}
💳 New Balance: {format_money(latest_balance)}
{generate_separator(29)}
⏰ *VALIDITY PERIOD:*
{generate_separator(29)}
📅 Created: {format_datetime(datetime.now().isoformat())}
⏳ Expires: {format_datetime(account_data.get('expires_at', ''))}
📆 Duration: {duration} days ({duration*24} hours)
{generate_separator(29)}
"""
        
        text = f"""
{order_summary}
{account_display}

{generate_separator(29)}
💡 *INSTRUCTIONS:*
{generate_separator(29)}
1. Copy configuration details above
2. Import to your VPN app
3. Connect and enjoy!
4. Save this message for reference
{generate_separator(29)}
🚀 *NEED HELP?*
Contact admin if you encounter issues
{generate_separator(29)}
🎉 *THANK YOU FOR YOUR PURCHASE!*
{generate_separator(29)}
"""
        
        # Send notification to all admins with complete details
        for admin_id in ADMIN_IDS:
            try:
                admin_text = create_admin_notification(
                    user=query.from_user,
                    user_id=user_id,
                    order_data=order_data,
                    account_data=account_data,
                    service_type=service_type
                )
                
                # Send order notification
                await context.bot.send_message(
                    admin_id, 
                    admin_text, 
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Send account details separately
                admin_account_details = f"""
{generate_header('📊 ACCOUNT DETAILS')}

{generate_separator(29)}
🔍 *ACCOUNT INFORMATION FOR ORDER #{order_id}*
{generate_separator(29)}
{account_display}
{generate_separator(29)}
"""
                await context.bot.send_message(
                    admin_id,
                    admin_account_details,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Send quick links if available
                if service_type == "vmess" and account_data.get('vmess_tls'):
                    await context.bot.send_message(
                        admin_id,
                        f"{generate_separator(29)}\n⚡ QUICK LINK:\n`{account_data['vmess_tls']}`\n{generate_separator(29)}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                elif service_type == "ssh" and account_data.get('password'):
                    await context.bot.send_message(
                        admin_id,
                        f"{generate_separator(29)}\n🌐 HTTP CUSTOM:\n`{vps.get('domain')}:1-65529@{username}:{account_data['password']}`\n{generate_separator(29)}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
            except Exception as e:
                print(f"Failed to notify admin {admin_id}: {e}")
    
    else:
        # Jika gagal, saldo tidak dipotong (karena belum dipotong di BalanceUpdateHandler)
        
        update_order(order_id, {
            "status": "failed", 
            "error": error_msg[:500],
            "failed_at": datetime.now().isoformat()
        })
        
        # Dapatkan saldo terbaru
        current_balance = BalanceUpdateHandler.get_user_balance(user_id)
        
        text = f"""
{generate_header('❌ ORDER GAGAL')}

{generate_separator(29)}
📛 *PEMBUATAN AKUN GAGAL*
{generate_separator(29)}
🔄 Order ID: `{order_id}`
👤 Username: `{username}`
🛒 Service: {service_type.upper()}
🖥️ Server: {vps['name']}
{generate_separator(29)}
💥 *ERROR DETAILS:*
{generate_separator(29)}
`{error_msg[:400]}`
{generate_separator(29)}
💰 *SALDO TIDAK DIPOTONG*
{generate_separator(29)}
📊 Current Balance: {format_money(current_balance)}
{generate_separator(29)}
🔧 *TROUBLESHOOTING:*
{generate_separator(29)}
• Server mungkin sedang maintenance
• Koneksi SSH terputus
• Username sudah digunakan
• Script error di server
• Network timeout
{generate_separator(29)}
📞 *HUBUNGI ADMIN UNTUK BANTUAN*
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔍 Cek Akun", callback_data="user_check_account")],
        [InlineKeyboardButton("📊 My Accounts", callback_data="user_my_accounts")],
        [InlineKeyboardButton("🛒 Beli Lagi", callback_data="user_buy_vpn")],
        [InlineKeyboardButton("💰 Top Up", callback_data="user_topup")],
        [InlineKeyboardButton("🏠 Menu Utama", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await processing_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    # Send additional config links if successful
    if success and service_type in ["vmess", "vless", "ssh"]:
        await asyncio.sleep(1)
        await send_additional_links(context, query.message.chat_id, account_data, service_type, vps.get('domain'))
    
    return ConversationHandler.END
                                

def create_account_display(account_data: dict, service_type: str, is_trial: bool = False) -> str:
    """Create formatted account display yang mudah dicopy dengan debugging"""
    
    # Debug: Print data yang masuk
    print(f"[DEBUG] Service Type: {service_type}")
    print(f"[DEBUG] Account Data Keys: {list(account_data.keys())}")
    print(f"[DEBUG] Is Trial: {is_trial}")
    
    # Normalize service type
    service_type = service_type.lower().strip()
    
    trial_label = " (TRIAL)" if is_trial else ""
    
    # Format tanggal dengan safe access
    created_date = format_date(account_data.get('created_at', ''))
    expires_date = format_date(account_data.get('expires_at', ''))
    
    # Hitung durasi
    if is_trial:
        duration_text = f"{account_data.get('trial_minutes', 40)} Menit (Trial)"
    else:
        duration_days = account_data.get('duration', account_data.get('days', 1))
        duration_text = f"{duration_days} Hari"
    
    # Jika service_type adalah SSH
    if service_type == "ssh":
        # Pastikan semua field yang diperlukan ada
        domain = account_data.get('domain', account_data.get('host', 'N/A'))
        username = account_data.get('username', 'N/A')
        password = account_data.get('password', 'N/A')
        server_ip = account_data.get('server_ip', 
                                    account_data.get('vps_ip', 
                                                    account_data.get('ip', 'N/A')))
        
        print(f"[DEBUG SSH] Domain: {domain}")
        print(f"[DEBUG SSH] Username: {username}")
        print(f"[DEBUG SSH] Password: {password}")
        
        return f"""
-----------------------------------------
SSH Account{trial_label}
-----------------------------------------
Host             : {domain}
IP               : {server_ip}
Username         : {username}
Password         : {password}
-----------------------------------------
Limit Quota      : {account_data.get('quota', 2)} GB
Limit Ip         : {account_data.get('ip_limit', 2)} IP
Host Slowdns     : {account_data.get('slowdns_host', 'N/A')}
Pub Key          : {account_data.get('pub_key', 'N/A')}
Port OpenSSH     : {account_data.get('ssh_port', 22)}
Port DNS         : 53 ,2222
Port SSH UDP     : 1-65535
Port Dropbear    : 22, 109
Port SSH WS      : 80,8080,2086,8880
Port SSH WS SSL  : 443,8443
Port SSL/TLS     : 443
BadVPN UDP       : 7100, 7200, 7300
-----------------------------------------
HTTP CUSTOM      : {domain}:1-65535@{username}:{password}
-----------------------------------------
Payload          : GET /cdn-cgi/trace HTTP/1.1[crlf]Host: {domain}[crlf][crlf]GET-RAY / HTTP/1.1[crlf]Host: [host][crlf]Connection: Upgrade[crlf]User-Agent: [ua][crlf]Upgrade: websocket[crlf][crlf]
-----------------------------------------
Save Link Account: https://{domain}:81/ssh-{username}.txt
-----------------------------------------
Aktif Selama     : {duration_text}
Dibuat Pada      : {created_date}
Berakhir Pada    : {expires_date}
-----------------------------------------
"""
    
    elif service_type == "vmess":
        uuid_value = account_data.get('uuid', '')
        return f"""
-----------------------------------------
Xray/Vmess Account{trial_label}
-----------------------------------------
Remarks          : {account_data.get('username', 'N/A')}
Domain           : {account_data.get('domain', 'N/A')}
User Quota       : {account_data.get('quota', 200)} GB
User IP          : {account_data.get('ip_limit', 2)} IP
Port Non TLS     : 80,8080,2086,8880
Port TLS         : 443,8443
id               : {uuid_value}
alterId          : 0
Security         : auto
Network          : ws
Path             : /vmess
Dynamic          : https://bugmu.com/path
ServiceName      : vmess-grpc
-----------------------------------------
Link TLS         : {account_data.get('vmess_tls', 'N/A')}
-----------------------------------------
Link none TLS    : {account_data.get('vmess_ntls', 'N/A')}
-----------------------------------------
Link GRPC        : {account_data.get('vmess_grpc', 'N/A')}
-----------------------------------------
Open Clash       : https://{account_data.get('domain', 'N/A')}:81/vmess-{account_data.get('username', 'N/A')}.txt
-----------------------------------------
Aktif Selama     : {duration_text}
Dibuat Pada      : {created_date}
Berakhir Pada    : {expires_date}
-----------------------------------------
"""
    
    elif service_type == "vless":
        uuid_value = account_data.get('uuid', '')
        return f"""
-----------------------------------------
Xray/Vless Account{trial_label}
-----------------------------------------
Remarks     : {account_data.get('username', 'N/A')}
Domain      : {account_data.get('domain', 'N/A')}
User Quota  : {account_data.get('quota', 200)} GB
User Ip     : {account_data.get('ip_limit', 2)} IP
Port Non TLS: 80,8080,2086,8880
Port TLS    : 443,8443
User ID     : {uuid_value}
Encryption  : none
Path TLS    : /vless
ServiceName : vless-grpc
-----------------------------------------
Link TLS    : {account_data.get('vless_tls', 'N/A')}
-----------------------------------------
Link NTLS   : {account_data.get('vless_ntls', 'N/A')}
-----------------------------------------
Link GRPC   : {account_data.get('vless_grpc', 'N/A')}
-----------------------------------------
Format OpenClash : https://{account_data.get('domain', 'N/A')}:81/vless-{account_data.get('username', 'N/A')}.txt
-----------------------------------------
Aktif Selama     : {duration_text}
Dibuat Pada      : {created_date}
Berakhir Pada    : {expires_date}
-----------------------------------------
"""
    
    elif service_type == "trojan":
        uuid_value = account_data.get('uuid', '')
        return f"""
-----------------------------------------
Xray/Trojan Account{trial_label}
-----------------------------------------
Remarks          : {account_data.get('username', 'N/A')}
Host/IP          : {account_data.get('domain', 'N/A')}
User Quota       : {account_data.get('quota', 200)} GB
User Ip          : {account_data.get('ip_limit', 2)} IP
Port             : 443,8443
Key              : {uuid_value}
Path             : /trojan-ws
ServiceName      : trojan-grpc
-----------------------------------------
Link TLS         : {account_data.get('trojan_ws', 'N/A')}
-----------------------------------------
Link GRPC        : {account_data.get('trojan_grpc', 'N/A')}
-----------------------------------------
Format OpenClash : https://{account_data.get('domain', 'N/A')}:81/trojan-{account_data.get('username', 'N/A')}.txt
-----------------------------------------
Aktif Selama     : {duration_text}
Dibuat Pada      : {created_date}
Berakhir Pada    : {expires_date}
-----------------------------------------
"""
    
    elif service_type == "ss":
        password = account_data.get('password', account_data.get('uuid', ''))
        cipher = account_data.get('cipher', 'aes-128-gcm')
        return f"""
-----------------------------------------
Xray/Shadowsocks Account{trial_label}
-----------------------------------------
Remarks     : {account_data.get('username', 'N/A')}
Domain      : {account_data.get('domain', 'N/A')}
User Quota  : {account_data.get('quota', 200)} GB
User Ip     : {account_data.get('ip_limit', 1)} IP
Port Non TLS: 80,8080,2086,8880
Port TLS    : 443,8443
Password    : {password}
Cipers      : {cipher}
Network     : ws/grpc
Path        : /ss-ws
ServiceName : ss-grpc
-----------------------------------------
Link WS TLS : {account_data.get('ss_ws_tls', 'N/A')}
-----------------------------------------
Link WS None TLS : {account_data.get('ss_ws_ntls', 'N/A')}
-----------------------------------------
Link GRPC : {account_data.get('ss_grpc', 'N/A')}
-----------------------------------------
Format OpenClash : https://{account_data.get('domain', 'N/A')}:81/ss-{account_data.get('username', 'N/A')}.txt
-----------------------------------------
Aktif Selama   : {duration_text}
Dibuat Pada    : {created_date}
Berakhir Pada  : {expires_date}
-----------------------------------------
"""
    
    elif service_type == "zivpn":
        password = account_data.get('password', 'N/A')
        return f"""
════════════════════════════════════════════════════════════
                    USER BERHASIL DITAMBAHKAN!
════════════════════════════════════════════════════════════
   INFORMASI USER
════════════════════════════════════════════════════════
Username      : {account_data.get('username', 'N/A')}
Password      : {password}
Tipe User     : {"trial" if is_trial else "regular"}
Masa Aktif    : {duration_text}
Expired Date  : {expires_date.split(',')[0] if ',' in expires_date else expires_date}
Tanggal Buat  : {created_date.split(',')[0] if ',' in created_date else created_date} {datetime.fromisoformat(account_data.get('created_at', '')).strftime('%H:%M:%S') if account_data.get('created_at') else ''}
════════════════════════════════════════════════════════
   INFORMASI KONEKSI
════════════════════════════════════════════════════════
domain        : {account_data.get('domain', 'N/A')}
Port          : 443
Protocol      : UDP
OBFS          : zivpn
════════════════════════════════════════════════════════
"""
    
    return f"""
-----------------------------------------
{service_type.upper()} Account{trial_label}
-----------------------------------------
Username: {account_data.get('username', 'N/A')}
Domain: {account_data.get('domain', 'N/A')}
IP Limit: {account_data.get('ip_limit', 2)} IP
Quota: {account_data.get('quota', 'Unlimited')} GB
Created: {created_date}
Expires: {expires_date}
Duration: {duration_text}
-----------------------------------------
"""
        

def create_admin_notification(user, user_id: int, order_data: dict, account_data: dict, service_type: str) -> str:
    """Create admin notification message"""
    return f"""
{generate_header('📢 PEMBELIAN BARU')}

{generate_separator(29)}
🎯 *NEW ORDER COMPLETED*
{generate_separator(29)}
👤 *CUSTOMER INFO*
{generate_separator(29)}
Name: {user.first_name} {user.last_name or ''}
Username: @{user.username or 'N/A'}
User ID: {user_id}
{generate_separator(29)}
🛒 *ORDER DETAILS*
{generate_separator(29)}
🆔 Order ID: {order_data.get('order_id', 'N/A')}
📋 Service: {service_type.upper()}
👤 Account: {account_data.get('username', 'N/A')}
🖥️ Server: {order_data.get('vps_name', 'N/A')}
📍 Domain: {order_data.get('vps_domain', 'N/A')}
🌐 IP: {order_data.get('vps_ip', 'N/A')}
📅 Duration: {order_data.get('duration', 0)} days
➕ Extra IPs: {order_data.get('extra_ips', 0)} IPs
{generate_separator(29)}
💰 *PAYMENT INFO*
{generate_separator(29)}
💵 Base Price: {format_money(order_data.get('base_price', 0))}
➕ Extra IPs: {format_money(order_data.get('extra_ip_cost', 0))}
💰 **TOTAL: {format_money(order_data.get('price', 0))}**
{generate_separator(29)}
⏰ *TIMESTAMP*
{generate_separator(29)}
📅 {format_datetime(order_data.get('created_at', datetime.now().isoformat()))}
{generate_separator(29)}
📊 *ACCOUNT SUMMARY*
{generate_separator(29)}
📡 Type: {service_type.upper()}
👤 Username: {account_data.get('username', 'N/A')}
🌐 IP Limit: {account_data.get('ip_limit', 2)} IPs
💾 Quota: {account_data.get('quota', 'Unlimited')} GB
⏳ Expires: {format_datetime(account_data.get('expires_at', ''))}
{generate_separator(29)}
"""


async def send_additional_links(context, chat_id: int, account_data: dict, service_type: str, domain: str):
    """Send additional configuration links"""
    if service_type == "ssh" and account_data.get('password'):
        await context.bot.send_message(
            chat_id,
            f"{generate_separator(29)}\n🌐 *HTTP CUSTOM SSH*\n{generate_separator(29)}\n`{domain}:1-65529@{account_data['username']}:{account_data['password']}`\n{generate_separator(29)}",
            parse_mode=ParseMode.MARKDOWN
        )
    elif service_type == "vmess" and account_data.get('vmess_tls'):
        await context.bot.send_message(
            chat_id,
            f"{generate_separator(29)}\n⚡ *QUICK CONNECT VMESS*\n{generate_separator(29)}\n`{account_data['vmess_tls'][:100]}...`\n{generate_separator(29)}",
            parse_mode=ParseMode.MARKDOWN
        )
    elif service_type == "vless" and account_data.get('vless_tls'):
        await context.bot.send_message(
            chat_id,
            f"{generate_separator(29)}\n🚀 *QUICK CONNECT VLESS*\n{generate_separator(29)}\n`{account_data['vless_tls'][:100]}...`\n{generate_separator(29)}",
            parse_mode=ParseMode.MARKDOWN
        )


def format_money(amount: float) -> str:
    """Format money with IDR currency"""
    return f"Rp {amount:,.0f}".replace(",", ".")


def format_datetime(datetime_str: str) -> str:
    """Format datetime string to readable format"""
    try:
        if not datetime_str:
            return "Unknown"
        
        if isinstance(datetime_str, str):
            if 'T' in datetime_str:
                dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
            else:
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d-%m-%Y %H:%M:%S']:
                    try:
                        dt = datetime.strptime(datetime_str, fmt)
                        break
                    except:
                        continue
                else:
                    return datetime_str[:19]
        else:
            dt = datetime_str
        
        return dt.strftime("%d %b %Y, %H:%M:%S")
    except:
        return str(datetime_str)[:19]
        
async def user_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Panduan penggunaan bot"""
    query = update.callback_query
    await query.answer()
    
    text = f"""
{generate_header('USER GUIDE')}

{generate_separator(29)}
📚 *Panduan Penggunaan VPN Store Bot*
{generate_separator(29)}
1️⃣ *TOP UP SALDO*
   - Klik "Top Up Saldo"
   - Ikuti instruksi pembayaran
   - Saldo akan ditambahkan otomatis

2️⃣ *BELI VPN*
   - Klik "Beli VPN"
   - Pilih server VPS
   - Pilih jenis layanan (SSH, VMess, dll)
   - Masukkan username
   - Pilih jumlah IP tambahan (opsional)
   - Pilih durasi
   - Konfirmasi pembayaran

3️⃣ *TRIAL VPN*
   - Klik "Trial VPN"
   - Pilih jenis layanan
   - Pilih server
   - Dapatkan akun trial 40 menit
   - Otomatis terhapus setelah expired

4️⃣ *CEK AKUN*
   - Klik "Cek Akun"
   - Masukkan username akun Anda
   - Detail akun akan ditampilkan

5️⃣ *JENIS LAYANAN:*
   🔐 *SSH:* Koneksi terenkripsi standar
   ⚡ *VMess:* Protokol V2Ray performa tinggi
   🚀 *VLESS:* Ringan tanpa enkripsi
   🛡️ *Trojan:* Menyerupai traffic HTTPS
   🌓 *Shadowsocks:* Proxy SOCKS5 ringan
   🟦 *ZiVPN:* Layanan VPN khusus

6️⃣ *IP TAMBAHAN:*
   - Default: 2 IP per akun
   - Bisa tambah hingga 5 IP ekstra
   - Biaya tambahan per IP

7️⃣ *TIPS:*
   - Durasi lebih lama = Harga lebih murah
   - Simpan detail akun dengan aman
   - Hubungi admin jika ada masalah
   - Cek saldo secara berkala
{generate_separator(29)}
📞 *SUPPORT:* Hubungi admin untuk bantuan
{generate_separator(29)}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Menu Utama", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# ============================================
# HANDLERS - ADMIN
# ============================================

@check_admin
async def admin_add_balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses tambah saldo ke user"""
    query = update.callback_query
    await query.answer()
    
    text = f"""
{generate_header('TAMBAH SALDO KE USER')}

{generate_separator(29)}
💰 *TAMBAH SALDO KE USER*
{generate_separator(29)}

Masukkan User ID yang ingin ditambahkan saldonya:
"""
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return ADMIN_ADD_BALANCE_USER_ID

@check_admin
async def admin_add_balance_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Input user ID untuk tambah saldo"""
    user_id_input = update.message.text.strip()
    
    try:
        target_user_id = int(user_id_input)
        
        user = get_user(target_user_id)
        
        context.user_data["add_balance_user_id"] = target_user_id
        context.user_data["add_balance_user_info"] = user
        
        await update.message.reply_text(
            f"""
{generate_header('TAMBAH SALDO')}

{generate_separator(29)}
👤 *User Ditemukan:*
{generate_separator(29)}
User ID: `{target_user_id}`
Saldo Saat Ini: {format_money(user['balance'])}
{generate_separator(29)}

Masukkan jumlah saldo yang ingin ditambahkan (dalam Rupiah):
"""
        )
        
        return ADMIN_ADD_BALANCE_AMOUNT
        
    except ValueError:
        await update.message.reply_text(
            "❌ User ID harus angka. Masukkan kembali User ID:"
        )
        return ADMIN_ADD_BALANCE_USER_ID

@check_admin      
async def admin_add_balance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Input jumlah saldo yang akan ditambahkan"""
    amount_input = update.message.text.strip()
    
    if not amount_input.isdigit():
        await update.message.reply_text(
            "❌ Jumlah harus angka. Masukkan jumlah dalam Rupiah:"
        )
        return ADMIN_ADD_BALANCE_AMOUNT
    
    amount = int(amount_input)
    
    if amount <= 0:
        await update.message.reply_text(
            "❌ Jumlah harus lebih dari 0. Masukkan jumlah yang valid:"
        )
        return ADMIN_ADD_BALANCE_AMOUNT
    
    target_user_id = context.user_data["add_balance_user_id"]
    user = context.user_data["add_balance_user_info"]
    
    context.user_data["add_balance_amount"] = amount
    
    text = f"""
{generate_header('KONFIRMASI TAMBAH SALDO')}

{generate_separator(29)}
✅ *Konfirmasi Penambahan Saldo*
{generate_separator(29)}
👤 *User Target:*
├ User ID: `{target_user_id}`
├ Saldo Saat Ini: {format_money(user['balance'])}
└ Saldo Setelah: {format_money(user['balance'] + amount)}
{generate_separator(29)}
💰 *Penambahan Saldo:*
└ **Jumlah: {format_money(amount)}**
{generate_separator(29)}
⚠️ *Konfirmasi penambahan saldo ini?*
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ KONFIRMASI", callback_data="confirm_add_balance"),
            InlineKeyboardButton("❌ BATALKAN", callback_data="cancel_add_balance")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ADMIN_ADD_BALANCE_CONFIRM

@check_admin
async def admin_add_balance_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi penambahan saldo - VERSI DIPERBAIKI DENGAN BALANCE HANDLER"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_add_balance":
        await query.edit_message_text(
            f"""
{generate_header('PENAMBAHAN SALDO DIBATALKAN')}

{generate_separator(29)}
❌ *Penambahan saldo dibatalkan.*
{generate_separator(29)}
Tidak ada perubahan saldo yang dilakukan.
{generate_separator(29)}
"""
        )
        return ConversationHandler.END
    
    # Dapatkan data dari context
    target_user_id = context.user_data["add_balance_user_id"]
    amount = context.user_data["add_balance_amount"]
    admin_id = query.from_user.id
    
    # ===== PERBAIKAN: Gunakan BalanceUpdateHandler =====
    
    # 1. Dapatkan saldo terkini (auto-sync)
    current_balance = BalanceUpdateHandler.get_user_balance(target_user_id)
    
    # 2. Buat invoice code unik untuk tracking
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    invoice_code = f"ADMIN_{timestamp}_{admin_id}_{amount}"
    
    # 3. Gunakan metode topup dari handler (akan auto-sync)
    success = BalanceUpdateHandler.update_topup(
        user_id=target_user_id,
        amount=amount,
        invoice_code=invoice_code,
        metadata={
            "admin_id": admin_id,
            "admin_name": query.from_user.first_name,
            "type": "admin_topup"
        }
    )
    
    if success:
        # Dapatkan saldo baru setelah topup
        new_balance = BalanceUpdateHandler.get_user_balance(target_user_id)
        
        # Tambahkan transaksi untuk log admin (opsional)
        add_transaction({
            "user_id": target_user_id,
            "type": "topup_admin",
            "amount": amount,
            "description": f"Top up oleh admin {admin_id}",
            "admin_id": admin_id,
            "status": "completed",
            "created_at": datetime.now().isoformat()
        })
        
        # Kirim notifikasi ke user
        try:
            await context.bot.send_message(
                target_user_id,
                f"""
{generate_header('💰 SALDO DITAMBAHKAN OLEH ADMIN')}

{generate_separator(29)}
✅ *Saldo Berhasil Ditambahkan!*
{generate_separator(29)}
📋 *Detail Transaksi:*
├ Jumlah: {format_money(amount)}
├ Saldo Sebelum: {format_money(current_balance)}
├ **Saldo Baru: {format_money(new_balance)}**
└ Admin: {admin_id}
{generate_separator(29)}
🎉 Terima kasih telah menggunakan layanan kami!
{generate_separator(29)}
"""
            )
        except Exception as e:
            print(f"[NOTIFICATION ERROR] Gagal kirim notifikasi ke user {target_user_id}: {e}")
        
        # Tampilkan konfirmasi ke admin
        text = f"""
{generate_header('💰 SALDO BERHASIL DITAMBAHKAN')}

{generate_separator(29)}
✅ *Penambahan saldo berhasil!*
{generate_separator(29)}
📋 *Detail Transaksi:*
├ User ID: `{target_user_id}`
├ Jumlah Ditambahkan: {format_money(amount)}
├ Saldo Sebelum: {format_money(current_balance)}
├ **Saldo Baru: {format_money(new_balance)}**
└ Admin: {admin_id}
{generate_separator(29)}
📊 *Status:* Berhasil diproses dengan BalanceUpdateHandler
📝 *Invoice:* `{invoice_code[:20]}...`
{generate_separator(29)}
"""
    else:
        # Jika gagal
        text = f"""
{generate_header('❌ GAGAL MENAMBAH SALDO')}

{generate_separator(29)}
❌ *Penambahan saldo GAGAL!*
{generate_separator(29)}
📋 *Detail:*
├ User ID: `{target_user_id}`
├ Jumlah: {format_money(amount)}
└ Admin: {admin_id}
{generate_separator(29)}
⚠️ *Kemungkinan Penyebab:*
├ Database error
├ User tidak ditemukan
└ Internal system error
{generate_separator(29)}
💡 *Silakan coba lagi atau hubungi developer.*
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Tambah Saldo Lain", callback_data="admin_add_balance")],
        [InlineKeyboardButton("💰 Cek Saldo User", callback_data="admin_list_users")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

@check_admin
async def admin_edit_vps_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses edit/hapus VPS"""
    query = update.callback_query
    await query.answer()
    
    vps_list = get_all_vps()
    
    if not vps_list:
        text = f"""
{generate_header('EDIT/HAPUS VPS')}

{generate_separator(29)}
📭 *Tidak Ada Server VPS Ditemukan*
{generate_separator(29)}
Belum ada server VPN yang ditambahkan.
Tambahkan server pertama Anda untuk memulai.
{generate_separator(29)}
"""
        keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ConversationHandler.END
    
    text = f"""
{generate_header('EDIT/HAPUS VPS')}

{generate_separator(29)}
🖥️ *Pilih VPS yang ingin diedit/dihapus:*
{generate_separator(29)}
"""
    
    keyboard = []
    for vps_id, vps in vps_list.items():
        name = vps.get('name', f"VPS {vps['ip']}")
        status = "🟢" if vps.get("status") == "active" else "🔴"
        domain = vps.get('domain', 'N/A')
        vps_type = vps.get('type', 'regular')
        type_icon = "🟦" if vps_type == "zivpn" else "🟩"
        
        button_text = f"{type_icon}{status} {name} ({domain})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"edit_vps_select_{vps_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ADMIN_EDIT_VPS_SELECT

@check_admin
async def admin_edit_vps_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pemilihan VPS untuk diedit"""
    query = update.callback_query
    await query.answer()
    
    vps_id = query.data.replace("edit_vps_select_", "")
    vps = get_vps(vps_id)
    
    if not vps:
        await query.edit_message_text("❌ Server tidak ditemukan.")
        return ConversationHandler.END
    
    context.user_data["edit_vps_id"] = vps_id
    context.user_data["edit_vps_info"] = vps
    
    vps_type = vps.get('type', 'regular')
    type_text = "ZiVPN ONLY" if vps_type == "zivpn" else "Regular"
    
    text = f"""
{generate_header('EDIT/HAPUS VPS')}

{generate_separator(29)}
🖥️ *Server:* {vps.get('name', 'VPS')}
🌐 *IP:* `{vps['ip']}`
🌐 *Domain:* {vps.get('domain', 'N/A')}
📍 *Location:* {vps.get('location', 'Unknown')}
🔧 *Tipe:* {type_text}
⚡ *Status:* {vps.get('status', 'active')}
{generate_separator(29)}

Pilih opsi untuk server ini:
"""
    
    keyboard = [
        [
            InlineKeyboardButton("📝 Edit Nama", callback_data="edit_field_name"),
            InlineKeyboardButton("🌐 Edit Domain", callback_data="edit_field_domain")
        ],
        [
            InlineKeyboardButton("📍 Edit Lokasi", callback_data="edit_field_location"),
            InlineKeyboardButton("🔧 Edit Status", callback_data="edit_field_status")
        ],
        [
            InlineKeyboardButton("🔄 Edit Tipe", callback_data="edit_field_type"),
            InlineKeyboardButton("⚠️ Hapus VPS", callback_data="delete_vps_confirm")
        ],
        [
            InlineKeyboardButton("🔙 Kembali", callback_data="admin_edit_vps")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ADMIN_EDIT_VPS_FIELD

@check_admin
async def admin_edit_vps_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pemilihan field untuk diedit"""
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == "delete_vps_confirm":
        vps_id = context.user_data["edit_vps_id"]
        vps = context.user_data["edit_vps_info"]
        vps_type = vps.get('type', 'regular')
        type_text = "ZiVPN ONLY" if vps_type == "zivpn" else "Regular"
        
        text = f"""
{generate_header('KONFIRMASI HAPUS VPS')}

{generate_separator(29)}
⚠️ *PERINGATAN: Hapus VPS*
{generate_separator(29)}
Anda akan menghapus server:
🖥️ *Nama:* {vps.get('name', 'VPS')}
🌐 *IP:* `{vps['ip']}`
🌐 *Domain:* {vps.get('domain', 'N/A')}
🔧 *Tipe:* {type_text}
{generate_separator(29)}
❌ *Tindakan ini tidak dapat dibatalkan!*
❌ *Semua akun di server ini akan terpengaruh!*
{generate_separator(29)}
Apakah Anda yakin ingin menghapus server ini?
{generate_separator(29)}
"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ YA, HAPUS", callback_data="delete_vps_yes"),
                InlineKeyboardButton("❌ BATAL", callback_data="edit_vps_select_" + vps_id)
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ADMIN_DELETE_VPS
    
    field_map = {
        "edit_field_name": ("nama", "Masukkan nama baru untuk server ini:"),
        "edit_field_domain": ("domain", "Masukkan domain baru (contoh: super.oxygencrc.my.id):"),
        "edit_field_location": ("location", "Masukkan lokasi baru (contoh: Singapore, USA, Japan):"),
        "edit_field_status": ("status", "Masukkan status baru (active/inactive):"),
        "edit_field_type": ("type", "Masukkan tipe server (regular/zivpn):")
    }
    
    if action in field_map:
        field_name, prompt = field_map[action]
        context.user_data["edit_field"] = field_name
        
        await query.edit_message_text(
            f"✏️ *Edit {field_name.upper()}*\n\n{prompt}"
        )
        
        return ADMIN_EDIT_VPS_VALUE
    
    await query.edit_message_text("❌ Aksi tidak dikenal.")
    return ADMIN_EDIT_VPS_FIELD

@check_admin
async def admin_edit_vps_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input nilai baru untuk field VPS"""
    new_value = update.message.text.strip()
    vps_id = context.user_data["edit_vps_id"]
    field_name = context.user_data["edit_field"]
    
    if field_name == "status":
        if new_value.lower() not in ["active", "inactive"]:
            await update.message.reply_text(
                "❌ Status harus 'active' atau 'inactive'. Masukkan kembali:"
            )
            return ADMIN_EDIT_VPS_VALUE
    
    if field_name == "type":
        if new_value.lower() not in ["regular", "zivpn"]:
            await update.message.reply_text(
                "❌ Tipe harus 'regular' atau 'zivpn'. Masukkan kembali:"
            )
            return ADMIN_EDIT_VPS_VALUE
    
    update_data = {field_name: new_value.lower() if field_name in ["status", "type"] else new_value}
    if update_vps(vps_id, update_data):
        vps = get_vps(vps_id)
        
        text = f"""
{generate_header('VPS BERHASIL DIUPDATE')}

{generate_separator(29)}
✅ *Perubahan berhasil disimpan!*
{generate_separator(29)}
📋 *Detail Update:*
├ Field: {field_name.upper()}
├ Nilai Baru: {new_value}
└ Server: {vps.get('name', 'VPS')}
{generate_separator(29)}
🔄 *Data server telah diperbarui.*
{generate_separator(29)}
"""
        
        keyboard = [
            [InlineKeyboardButton("✏️ Edit Lainnya", callback_data=f"edit_vps_select_{vps_id}")],
            [InlineKeyboardButton("🔄 List VPS Lain", callback_data="admin_edit_vps")],
            [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    else:
        await update.message.reply_text("❌ Gagal mengupdate VPS. Server tidak ditemukan.")
    
    return ConversationHandler.END

@check_admin
async def admin_delete_vps_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle konfirmasi hapus VPS"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "delete_vps_yes":
        vps_id = context.user_data["edit_vps_id"]
        vps = context.user_data["edit_vps_info"]
        
        if delete_vps(vps_id):
            server_prices = get_server_prices()
            if vps_id in server_prices:
                del server_prices[vps_id]
                save_json(SERVER_PRICES_DB, server_prices)
            
            text = f"""
{generate_header('VPS BERHASIL DIHAPUS')}

{generate_separator(29)}
✅ *Server VPS berhasil dihapus!*
{generate_separator(29)}
🗑️ *Server yang dihapus:*
├ Nama: {vps.get('name', 'VPS')}
├ IP: `{vps['ip']}`
├ Domain: {vps.get('domain', 'N/A')}
├ Tipe: {vps.get('type', 'regular')}
└ Status: ❌ **TERHAPUS**
{generate_separator(29)}
⚠️ *Catatan:* Harga khusus untuk server ini juga telah dihapus.
{generate_separator(29)}
"""
        else:
            text = f"""
{generate_header('GAGAL MENGHAPUS VPS')}

{generate_separator(29)}
❌ *Gagal menghapus server VPS!*
{generate_separator(29)}
Server mungkin tidak ditemukan atau sudah dihapus sebelumnya.
{generate_separator(29)}
"""
    else:
        vps_id = context.user_data["edit_vps_id"]
        text = f"""
{generate_header('PENGHAPUSAN DIBATALKAN')}

{generate_separator(29)}
❌ *Penghapusan VPS dibatalkan.*
{generate_separator(29)}
Server tidak jadi dihapus.
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Edit VPS Lain", callback_data="admin_edit_vps")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

@check_admin
async def admin_add_vps_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses tambah VPS"""
    query = update.callback_query
    await query.answer()
    
    text = f"""
{generate_header('TAMBAH SERVER VPS BARU')}

{generate_separator(29)}
➕ *Tambahkan Server VPN Baru*
{generate_separator(29)}
Masukkan nama untuk server ini:
📝 *Contoh:* `SG-01`, `US-02`, `JP-Premium`

💡 *Tips:* Gunakan penamaan yang jelas untuk pengelolaan mudah.
"""
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return ADMIN_ADD_VPS_NAME

async def admin_add_vps_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Input nama VPS"""
    name = update.message.text.strip()
    context.user_data["vps_name"] = name
    
    await update.message.reply_text(
        f"""
{generate_header('TAMBAH SERVER VPS')}

{generate_separator(29)}
🌐 *Masukkan Alamat IP Server*
{generate_separator(29)}
Masukkan alamat IPv4 server:
📝 *Contoh:* `192.168.1.1`, `103.123.45.67`

🔍 *Catatan:* Pastikan IP dapat diakses publik.
"""
    )
    
    return ADMIN_ADD_VPS_IP

@check_admin
async def admin_add_vps_ip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Input IP VPS"""
    ip = update.message.text.strip()
    
    ip_pattern = r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'
    if not re.match(ip_pattern, ip):
        await update.message.reply_text(
            "❌ *Format IP Tidak Valid!* Masukkan alamat IPv4 yang valid:"
        )
        return ADMIN_ADD_VPS_IP
    
    context.user_data["vps_ip"] = ip
    
    await update.message.reply_text(
        f"""
{generate_header('TAMBAH SERVER VPS')}

{generate_separator(29)}
🌐 *Masukkan Domain Server*
{generate_separator(29)}
Masukkan domain untuk server ini (contoh: super.oxygencrc.my.id):
"""
    )
    
    return ADMIN_ADD_VPS_DOMAIN

@check_admin
async def admin_add_vps_domain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Input domain VPS"""
    domain = update.message.text.strip()
    
    if not '.' in domain:
        await update.message.reply_text(
            "❌ *Format Domain Tidak Valid!* Masukkan domain yang valid (contoh: super.oxygencrc.my.id):"
        )
        return ADMIN_ADD_VPS_DOMAIN
    
    context.user_data["vps_domain"] = domain
    
    await update.message.reply_text(
        f"""
{generate_header('TAMBAH SERVER VPS')}

{generate_separator(29)}
📍 *Masukkan Lokasi Server*
{generate_separator(29)}
Masukkan lokasi server (contoh: Singapore, USA, Japan):
"""
    )
    
    return ADMIN_ADD_VPS_LOCATION

async def admin_add_vps_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Input lokasi VPS"""
    location = update.message.text.strip()
    context.user_data["vps_location"] = location
    
    text = f"""
{generate_header('TAMBAH SERVER VPS')}

{generate_separator(29)}
🔧 *Pilih Tipe Server*
{generate_separator(29)}
Pilih tipe server yang ingin ditambahkan:

🟩 *REGULAR* - Mendukung SSH, VMess, VLESS, Trojan, Shadowsocks
🟦 *ZiVPN ONLY* - Hanya mendukung layanan ZiVPN
{generate_separator(29)}

Pilih tipe server:
"""
    
    keyboard = [
        [InlineKeyboardButton("🟩 REGULAR", callback_data="vps_type_regular")],
        [InlineKeyboardButton("🟦 ZiVPN ONLY", callback_data="vps_type_zivpn")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ADMIN_ADD_VPS_TYPE

@check_admin
async def admin_add_vps_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih tipe VPS"""
    query = update.callback_query
    await query.answer()
    
    vps_type = query.data.replace("vps_type_", "")
    context.user_data["vps_type"] = vps_type
    
    type_text = "Regular" if vps_type == "regular" else "ZiVPN ONLY"
    
    await query.edit_message_text(
        f"""
{generate_header('TAMBAH SERVER VPS')}

{generate_separator(29)}
✅ Tipe server dipilih: *{type_text}*
{generate_separator(29)}
👤 *Masukkan SSH Username*
{generate_separator(29)}
Masukkan username SSH untuk akses server:
"""
    )
    
    return ADMIN_ADD_VPS_SSH_USER

async def admin_add_vps_ssh_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Input SSH username"""
    ssh_user = update.message.text.strip()
    context.user_data["ssh_user"] = ssh_user
    
    await update.message.reply_text(
        f"""
{generate_header('TAMBAH SERVER VPS')}

{generate_separator(29)}
🔑 *Masukkan SSH Password*
{generate_separator(29)}
Masukkan password SSH:
"""
    )
    
    return ADMIN_ADD_VPS_SSH_PASS

async def admin_add_vps_ssh_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Input SSH password"""
    ssh_pass = update.message.text.strip()
    context.user_data["ssh_pass"] = ssh_pass
    
    await update.message.reply_text(
        f"""
{generate_header('TAMBAH SERVER VPS')}

{generate_separator(29)}
🚪 *Masukkan SSH Port*
{generate_separator(29)}
Masukkan port SSH (default: 22):
"""
    )
    
    return ADMIN_ADD_VPS_SSH_PORT

async def admin_add_vps_ssh_port(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Input SSH port"""
    ssh_port = update.message.text.strip()
    
    if not ssh_port.isdigit():
        ssh_port = 22
    else:
        ssh_port = int(ssh_port)
    
    context.user_data["ssh_port"] = ssh_port
    
    processing_msg = await update.message.reply_text(
        f"""
{generate_header('MENGUJI KONEKSI')}

{generate_separator(29)}
🔄 *Menguji Koneksi SSH...*
{generate_separator(29)}
Harap tunggu sementara kami menguji koneksi ke server Anda.
Proses ini mungkin memakan waktu beberapa detik.
{generate_separator(29)}
"""
    )
    
    ip = context.user_data["vps_ip"]
    ssh_user = context.user_data["ssh_user"]
    ssh_pass = context.user_data["ssh_pass"]
    name = context.user_data["vps_name"]
    domain = context.user_data["vps_domain"]
    location = context.user_data["vps_location"]
    vps_type = context.user_data["vps_type"]
    
    success = await test_ssh_connection(ip, ssh_port, ssh_user, ssh_pass)
    
    if success:
        if vps_type != "zivpn":
            temp_vps = {
                "ip": ip,
                "ssh_user": ssh_user,
                "ssh_pass": ssh_pass,
                "ssh_port": ssh_port
            }
            domain_set = await set_domain_on_vps(temp_vps, domain)
        else:
            domain_set = True
        
        vps_data = {
            "ip": ip,
            "ssh_user": ssh_user,
            "ssh_pass": ssh_pass,
            "ssh_port": ssh_port,
            "name": name,
            "domain": domain,
            "location": location,
            "type": vps_type,
            "max_users": 100,
            "current_users": 0,
            "status": "active"
        }
        
        vps_id = add_vps(vps_data)
        
        type_display = "Regular" if vps_type == "regular" else "ZiVPN ONLY"
        
        text = f"""
{generate_header('VPS BERHASIL DITAMBAHKAN')}

{generate_separator(29)}
✅ *Server VPS Baru Ditambahkan!*
{generate_separator(29)}
📋 *Detail Server:*
├ Server ID: `{vps_id}`
├ Nama: {name}
├ Tipe: {type_display}
├ Domain: {domain}
├ Lokasi: {location}
├ Alamat IP: `{ip}`
├ SSH Username: `{ssh_user}`
├ SSH Password: `{ssh_pass}`
└ SSH Port: `{ssh_port}`
{generate_separator(29)}
🔄 *Status Koneksi:* ✅ **Berhasil**
🌐 *Status Domain:* {'✅ Berhasil diset' if domain_set else '⚠️ Skipped (ZiVPN)'}
🎉 *Server siap untuk pembuatan akun VPN!*
{generate_separator(29)}
"""
        
    else:
        text = f"""
{generate_header('KONEKSI GAGAL')}

{generate_separator(29)}
❌ *Koneksi SSH Gagal!*
{generate_separator(29)}
Tidak dapat terhubung ke server dengan kredensial yang diberikan.
{generate_separator(29)}
🔍 *Checklist Troubleshooting:*
├ ✅ Verifikasi alamat IP benar
├ 🔄 Cek apakah port SSH ({ssh_port}) terbuka
├ 🔑 Verifikasi username dan password
├ 🌐 Pastikan server dapat diakses dari jaringan
├ 🔧 Cek pengaturan firewall
└ 📞 Hubungi provider server jika perlu
{generate_separator(29)}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await processing_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

@check_admin
async def admin_set_extra_ip_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set harga IP tambahan"""
    query = update.callback_query
    await query.answer()
    
    global EXTRA_IP_PRICE
    
    text = f"""
{generate_header('SET HARGA IP TAMBAHAN')}

{generate_separator(29)}
💰 *SET HARGA IP TAMBAHAN*
{generate_separator(29)}
Harga IP tambahan saat ini: {format_money(EXTRA_IP_PRICE)}
{generate_separator(29)}

Masukkan harga baru per IP tambahan (dalam Rupiah):
"""
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return ADMIN_SET_EXTRA_IP_PRICE

async def handle_extra_ip_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input harga IP tambahan"""
    price_input = update.message.text.strip()
    
    if not price_input.isdigit():
        await update.message.reply_text(
            "❌ Harga harus angka. Masukkan harga dalam Rupiah:"
        )
        return ADMIN_SET_EXTRA_IP_PRICE
    
    new_price = int(price_input)
    
    if new_price <= 0:
        await update.message.reply_text(
            "❌ Harga harus lebih dari 0. Masukkan harga yang valid:"
        )
        return ADMIN_SET_EXTRA_IP_PRICE
    
    update_extra_ip_price(new_price)
    
    text = f"""
{generate_header('HARGA IP TAMBAHAN BERHASIL DIUPDATE')}

{generate_separator(29)}
✅ *Harga IP Tambahan Berhasil Diperbarui!*
{generate_separator(29)}
💰 *Harga Baru:* {format_money(new_price)} per IP
{generate_separator(29)}
💡 *Catatan:* Harga ini akan berlaku untuk semua pembelian baru.
{generate_separator(29)}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def handle_server_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input harga untuk set harga server"""
    price_input = update.message.text.strip()
    
    vps_id = context.user_data["server_price_vps_id"]
    service_type = context.user_data["server_price_service"]
    duration = context.user_data["server_price_duration"]
    vps = context.user_data["server_price_vps_info"]
    
    durations_text = {"7": "7 Hari", "15": "15 Hari", "30": "30 Hari", "90": "90 Hari", "365": "1 Tahun"}
    duration_text = durations_text.get(duration, f"{duration} Hari")
    
    if price_input == "":
        server_prices = get_server_prices()
        if vps_id in server_prices and service_type in server_prices[vps_id]:
            if duration in server_prices[vps_id][service_type]:
                del server_prices[vps_id][service_type][duration]
                if not server_prices[vps_id][service_type]:
                    del server_prices[vps_id][service_type]
                if not server_prices[vps_id]:
                    del server_prices[vps_id]
                save_json(SERVER_PRICES_DB, server_prices)
        
        default_prices = get_prices()
        default_price = default_prices.get(service_type, {}).get(duration, 0)
        
        text = f"""
{generate_header('HARGA SERVER DI RESET')}

{generate_separator(29)}
✅ *Harga Server Direset ke Default!*
{generate_separator(29)}
📋 *Detail Reset:*
├ Server: {vps.get('name', 'VPS')}
├ Layanan: {service_type.upper()}
├ Durasi: {duration_text}
└ Harga Default: {format_money(default_price)}
{generate_separator(29)}
💰 Harga telah direset ke nilai default.
{generate_separator(29)}
"""
    else:
        if not price_input.isdigit():
            await update.message.reply_text(
                "❌ Harga harus angka. Masukkan harga dalam Rupiah:"
            )
            return ADMIN_SET_SERVER_PRICE_VALUE
        
        price = int(price_input)
        
        update_server_price(vps_id, service_type, duration, price)
        
        text = f"""
{generate_header('HARGA SERVER BERHASIL DIUPDATE')}

{generate_separator(29)}
✅ *Harga Server Berhasil Diperbarui!*
{generate_separator(29)}
📋 *Detail Pembaruan:*
├ Server: {vps.get('name', 'VPS')}
├ Layanan: {service_type.upper()}
├ Durasi: {duration_text}
└ Harga Baru: {format_money(price)}
{generate_separator(29)}
💰 Harga khusus telah disimpan untuk server ini.
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Set Harga Lain", callback_data=f"server_price_service_{service_type}")],
        [InlineKeyboardButton("🎯 Pilih Server Lain", callback_data="admin_set_server_price")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END


@check_admin
async def admin_set_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mulai proses set harga default"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔐 SSH", callback_data="price_ssh")],
        [InlineKeyboardButton("⚡ VMess", callback_data="price_vmess")],
        [InlineKeyboardButton("🚀 VLESS", callback_data="price_vless")],
        [InlineKeyboardButton("🛡️ Trojan", callback_data="price_trojan")],
        [InlineKeyboardButton("🌓 Shadowsocks", callback_data="price_ss")],
        [InlineKeyboardButton("🟦 ZiVPN", callback_data="price_zivpn")],
        [InlineKeyboardButton("➕ Harga IP Tambahan", callback_data="admin_set_extra_ip_price")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="admin_panel")]
    ]
    
    text = f"""
{generate_header('SET HARGA DEFAULT')}

{generate_separator(29)}
💰 *SET HARGA DEFAULT*
{generate_separator(29)}
Pilih jenis layanan yang ingin diatur harganya:
"""
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ADMIN_SET_PRICE_TYPE

async def admin_set_price_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pilih jenis layanan untuk set harga default"""
    query = update.callback_query
    await query.answer()
    
    service_type = query.data.replace("price_", "")
    context.user_data["price_service"] = service_type
    
    prices = get_prices()
    current_prices = prices.get(service_type, {})
    
    text = f"""
{generate_header('SET HARGA DEFAULT')}

{generate_separator(29)}
💰 *SET HARGA DEFAULT - {service_type.upper()}*
{generate_separator(29)}
Harga saat ini:
"""
    
    durations = {"7": "7 Hari", "15": "15 Hari", "30": "30 Hari", "90": "90 Hari", "365": "1 Tahun"}
    
    for dur_code, dur_name in durations.items():
        price = current_prices.get(dur_code, 0)
        text += f"├ {dur_name}: Rp {price:,}\n"
    
    text += "\nMasukkan durasi (7, 15, 30, 90, 365):"
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return ADMIN_SET_PRICE_VALUE

async def handle_server_price_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input durasi untuk set harga server"""
    duration = update.message.text.strip()
    
    if duration not in ["7", "15", "30", "90", "365"]:
        await update.message.reply_text(
            "❌ Durasi tidak valid. Masukkan 7, 15, 30, 90, atau 365:"
        )
        return ADMIN_SET_SERVER_PRICE_DURATION
    
    context.user_data["server_price_duration"] = duration
    
    vps_id = context.user_data["server_price_vps_id"]
    service_type = context.user_data["server_price_service"]
    vps = context.user_data["server_price_vps_info"]
    
    default_prices = get_prices()
    default_price = default_prices.get(service_type, {}).get(duration, 0)
    
    durations_text = {"7": "7 Hari", "15": "15 Hari", "30": "30 Hari", "90": "90 Hari", "365": "1 Tahun"}
    duration_text = durations_text.get(duration, f"{duration} Hari")
    
    await update.message.reply_text(
        f"""
{generate_header('SET HARGA SERVER')}

{generate_separator(29)}
💰 *Set Harga Server*
{generate_separator(29)}
🖥️ Server: {vps.get('name', 'VPS')}
🔧 Layanan: {service_type.upper()}
📅 Durasi: {duration_text}
{generate_separator(29)}
💡 *Harga Default:* {format_money(default_price)}
{generate_separator(29)}

Masukkan harga khusus untuk server ini (dalam Rupiah):
Kosongkan untuk menggunakan harga default:
"""
    )
    
    return ADMIN_SET_SERVER_PRICE_VALUE



async def handle_price_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input durasi untuk set harga default"""
    duration = update.message.text.strip()
    
    if duration not in ["7", "15", "30", "90", "365"]:
        await update.message.reply_text(
            "❌ Durasi tidak valid. Masukkan 1, 7, 30, 90, atau 365:"
        )
        return ADMIN_SET_PRICE_VALUE
    
    context.user_data["price_duration"] = duration
    
    service_type = context.user_data["price_service"]
    durations_text = {"7": "7 Hari", "15": "15 Hari", "30": "30 Hari", "90": "90 Hari", "365": "1 Tahun"}
    duration_text = durations_text.get(duration, f"{duration} Hari")
    
    await update.message.reply_text(
        f"💰 Masukkan harga untuk {service_type.upper()} {duration_text} (dalam Rupiah):"
    )
    
    return ADMIN_ADD_VPS_PRICE


async def handle_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input harga untuk set harga default"""
    price_input = update.message.text.strip()
    
    if not price_input.isdigit():
        await update.message.reply_text(
            "❌ Harga harus angka. Masukkan harga dalam Rupiah:"
        )
        return ADMIN_ADD_VPS_PRICE
    
    price = int(price_input)
    service_type = context.user_data["price_service"]
    duration = context.user_data["price_duration"]
    
    update_price(service_type, duration, price)
    
    durations_text = {"7": "7 Hari", "15": "15 Hari", "30": "30 Hari", "90": "90 Hari", "365": "1 Tahun"}
    duration_text = durations_text.get(duration, f"{duration} Hari")
    
    text = f"""
{generate_header('HARGA BERHASIL DIUPDATE')}

{generate_separator(29)}
✅ *Harga Default Berhasil Diperbarui!*
{generate_separator(29)}
📋 *Detail Pembaruan:*
├ Layanan: {service_type.upper()}
├ Durasi: {duration_text}
└ Harga Baru: {format_money(price)}
{generate_separator(29)}
💰 Harga telah disimpan sebagai default untuk layanan ini.
{generate_separator(29)}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END


async def handle_ip_limit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input IP limit default"""
    ip_limit_input = update.message.text.strip()
    
    vps_id = context.user_data["ip_limit_vps_id"]
    service_type = context.user_data["ip_limit_service"]
    vps = context.user_data["ip_limit_vps_info"]
    
    if not ip_limit_input.isdigit():
        await update.message.reply_text(
            "❌ IP limit harus angka. Masukkan jumlah IP (1-100):"
        )
        return ADMIN_SET_IP_LIMIT_VALUE
    
    ip_limit = int(ip_limit_input)
    
    if ip_limit < 1 or ip_limit > 100:
        await update.message.reply_text(
            "❌ IP limit harus antara 1-100. Masukkan jumlah yang valid:"
        )
        return ADMIN_SET_IP_LIMIT_VALUE
    
    durations = ["1", "7", "30", "90", "365"]
    
    for duration in durations:
        set_ip_limit(vps_id, service_type, duration, ip_limit)
    
    text = f"""
{generate_header('IP LIMIT DEFAULT BERHASIL DISET')}

{generate_separator(29)}
✅ *IP Limit Default Berhasil Diset!*
{generate_separator(29)}
📋 *Detail Konfigurasi:*
├ Server: {vps.get('name', 'VPS')}
├ Layanan: {service_type.upper()}
├ IP Limit: {ip_limit} IP
├ Berlaku untuk: Semua durasi (1,7,30,90,365 hari)
└ Tipe: Default untuk order baru
{generate_separator(29)}
💡 *Catatan:* IP limit ini akan berlaku untuk semua order baru
dengan kombinasi server dan layanan ini.
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Set untuk Layanan Lain", callback_data=f"ip_limit_vps_{vps_id}")],
        [InlineKeyboardButton("🎯 Set untuk Server Lain", callback_data="admin_set_ip_limit")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END


async def admin_set_server_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start server price setting process"""
    query = update.callback_query
    await query.answer()
    
    vps_list = get_all_vps()
    active_vps = {k: v for k, v in vps_list.items() if v.get("status") == "active"}
    
    if not active_vps:
        text = f"""
{generate_header('TIDAK ADA SERVER')}

{generate_separator(29)}
⚠️ Tidak ada server VPS aktif ditemukan.
{generate_separator(29)}
Harap tambahkan server VPS terlebih dahulu sebelum mengatur harga spesifik server.
{generate_separator(29)}
"""
        keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return ConversationHandler.END
    
    keyboard = []
    for vps_id, vps in active_vps.items():
        name = vps.get('name', f"VPS {vps['ip']}")
        domain = vps.get('domain', 'N/A')
        vps_type = vps.get('type', 'regular')
        type_icon = "🟦" if vps_type == "zivpn" else "🟩"
        
        button_text = f"{type_icon} {name} ({domain})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"server_price_vps_{vps_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")])
    
    text = f"""
{generate_header('SET HARGA SERVER')}

{generate_separator(29)}
🎯 *Set Harga Spesifik Server*
{generate_separator(29)}
Pilih server untuk mengatur harga khusus:
"""
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ADMIN_SET_SERVER_PRICE_SELECT_VPS

async def admin_set_server_price_select_vps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle VPS selection for server price setting"""
    query = update.callback_query
    await query.answer()
    
    vps_id = query.data.replace("server_price_vps_", "")
    vps = get_vps(vps_id)
    
    if not vps:
        await query.edit_message_text("❌ Server tidak ditemukan.")
        return ConversationHandler.END
    
    context.user_data["server_price_vps_id"] = vps_id
    context.user_data["server_price_vps_info"] = vps
    
    keyboard = []
    vps_type = vps.get("type", "regular")
    
    if vps_type == "zivpn":
        services = ["zivpn"]
    else:
        services = ["ssh", "vmess", "vless", "trojan", "ss", "zivpn"]
    
    text = f"""
{generate_header('SET HARGA SERVER')}

{generate_separator(29)}
🖥️ *Server:* {vps.get('name', 'VPS')}
🌐 *Domain:* {vps.get('domain', 'N/A')}
🔧 *Tipe:* {'ZiVPN ONLY' if vps_type == 'zivpn' else 'REGULAR'}
{generate_separator(29)}

Pilih layanan untuk mengatur harga khusus:
"""
    
    for service in services:
        icon = {
            "ssh": "🔐", "vmess": "⚡", "vless": "🚀", 
            "trojan": "🛡️", "ss": "🌓", "zivpn": "🟦"
        }.get(service, "🔧")
        keyboard.append([InlineKeyboardButton(f"{icon} {service.upper()}", callback_data=f"server_price_service_{service}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="admin_set_server_price")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ADMIN_SET_SERVER_PRICE_SELECT_SERVICE

async def admin_set_server_price_select_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle service selection for server price setting"""
    query = update.callback_query
    await query.answer()
    
    service_type = query.data.replace("server_price_service_", "")
    context.user_data["server_price_service"] = service_type
    
    vps_id = context.user_data["server_price_vps_id"]
    vps = context.user_data["server_price_vps_info"]
    
    text = f"""
{generate_header('SET HARGA SERVER')}

{generate_separator(29)}
🖥️ *Server:* {vps.get('name', 'VPS')}
🔧 *Layanan:* {service_type.upper()}
{generate_separator(29)}

Masukkan durasi yang ingin dimodifikasi (1, 7, 30, 90, 365):
"""
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    
    return ADMIN_SET_SERVER_PRICE_DURATION

async def handle_price_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input durasi untuk set harga default - SUPPORT 1-365 HARI"""
    duration = update.message.text.strip()
    
    # Validasi: harus angka antara 1-365
    if not duration.isdigit():
        await update.message.reply_text(
            "❌ Durasi harus angka. Masukkan durasi (1-365):"
        )
        return ADMIN_SET_PRICE_VALUE
    
    duration_int = int(duration)
    if duration_int < 1 or duration_int > 365:
        await update.message.reply_text(
            "❌ Durasi harus antara 1-365 hari. Masukkan durasi yang valid:"
        )
        return ADMIN_SET_PRICE_VALUE
    
    context.user_data["price_duration"] = duration
    
    service_type = context.user_data["price_service"]
    
    # Format durasi text yang lebih baik
    if duration_int == 1:
        duration_text = "1 Hari"
    elif duration_int == 365:
        duration_text = "1 Tahun"
    else:
        duration_text = f"{duration_int} Hari"
    
    await update.message.reply_text(
        f"💰 Masukkan harga untuk {service_type.upper()} {duration_text} (dalam Rupiah):"
    )
    
    return ADMIN_ADD_VPS_PRICE

async def handle_price_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input harga untuk set harga default - SUPPORT 1-365 HARI"""
    price_input = update.message.text.strip()
    
    if not price_input.isdigit():
        await update.message.reply_text(
            "❌ Harga harus angka. Masukkan harga dalam Rupiah:"
        )
        return ADMIN_ADD_VPS_PRICE
    
    price = int(price_input)
    service_type = context.user_data["price_service"]
    duration = context.user_data["price_duration"]
    
    # Validasi durasi
    try:
        duration_int = int(duration)
        if duration_int < 1 or duration_int > 365:
            await update.message.reply_text(
                "❌ Durasi tidak valid. Durasi harus 1-365 hari."
            )
            return ADMIN_ADD_VPS_PRICE
    except:
        await update.message.reply_text(
            "❌ Format durasi tidak valid. Durasi harus angka 1-365."
        )
        return ADMIN_ADD_VPS_PRICE
    
    # Update harga
    update_price(service_type, duration, price)
    
    # Format durasi text yang lebih baik
    if duration_int == 1:
        duration_text = "1 Hari"
    elif duration_int == 365:
        duration_text = "1 Tahun"
    else:
        duration_text = f"{duration_int} Hari"
    
    text = f"""
{generate_header('HARGA BERHASIL DIUPDATE')}

{generate_separator(29)}
✅ *Harga Default Berhasil Diperbarui!*
{generate_separator(29)}
📋 *Detail Pembaruan:*
├ Layanan: {service_type.upper()}
├ Durasi: {duration_text}
└ Harga Baru: {format_money(price)}
{generate_separator(29)}
💰 Harga telah disimpan sebagai default untuk layanan ini.
{generate_separator(29)}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dashboard admin"""
    query = update.callback_query
    await query.answer()
    
    users = load_json(USERS_DB)
    vps_list = get_all_vps()
    orders = load_json(ORDERS_DB)
    transactions = load_json(TRANSACTIONS_DB)
    trials = load_json(TRIAL_ACCOUNTS_DB)
    
    expired_trials = cleanup_expired_trials()
    
    total_users = len(users)
    active_users = sum(1 for u in users.values() if len(u.get("vpn_accounts", [])) > 0)
    total_vps = len(vps_list)
    active_vps = sum(1 for v in vps_list.values() if v.get("status") == "active")
    regular_vps = sum(1 for v in vps_list.values() if v.get("type") == "regular")
    zivpn_vps = sum(1 for v in vps_list.values() if v.get("type") == "zivpn")
    active_trials = len(trials)
    
    today = datetime.now().date()
    today_income = sum(
        tx.get("amount", 0) for tx in transactions.values() 
        if datetime.fromisoformat(tx["created_at"]).date() == today and tx.get("type") == "purchase"
    )
    
    total_income = sum(tx.get("amount", 0) for tx in transactions.values() if tx.get("type") == "purchase")
    
    today_orders = sum(
        1 for o in orders.values()
        if datetime.fromisoformat(o["created_at"]).date() == today and o.get("status") == "completed"
    )
    
    text = f"""
{generate_header('DASHBOARD ADMIN')}

{generate_separator(29)}
📊 *OVERVIEW SISTEM*
{generate_separator(29)}
👥 *Statistik Pengguna:*
├ Total Users: {total_users}
├ Active Users: {active_users}
└ Inactive Users: {total_users - active_users}
{generate_separator(29)}
🖥️ *Statistik Server:*
├ Total Servers: {total_vps}
├ Active Servers: {active_vps}
├ Regular Servers: {regular_vps}
├ ZiVPN Servers: {zivpn_vps}
└ Inactive Servers: {total_vps - active_vps}
{generate_separator(29)}
💰 *Statistik Pendapatan:*
├ Pendapatan Hari Ini: {format_money(today_income)}
├ Total Pendapatan: {format_money(total_income)}
└ Order Hari Ini: {today_orders}
{generate_separator(29)}
📈 *Metrik Performa:*
├ Total Orders: {len(orders)}
├ Completed: {sum(1 for o in orders.values() if o.get('status') == 'completed')}
├ Failed: {sum(1 for o in orders.values() if o.get('status') == 'failed')}
├ Pending: {sum(1 for o in orders.values() if o.get('status') == 'processing')}
├ Active Trials: {active_trials}
└ Expired Trials Cleaned: {expired_trials}
{generate_separator(29)}
🔄 *Status Sistem:* ✅ **Operasional**
⚙️ *Extra IP Price:* {format_money(EXTRA_IP_PRICE)} per IP
{generate_separator(29)}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def admin_list_vps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List semua VPS"""
    query = update.callback_query
    await query.answer()
    
    vps_list = get_all_vps()
    
    if not vps_list:
        text = f"""
{generate_header('SERVER VPS')}

{generate_separator(29)}
📭 *Tidak Ada Server VPS Ditemukan*
{generate_separator(29)}
Belum ada server VPN yang ditambahkan.
Tambahkan server pertama Anda untuk memulai.
{generate_separator(29)}
"""
    else:
        text = f"""
{generate_header('DAFTAR SERVER VPS')}

{generate_separator(29)}
🖥️ *Total Server:* {len(vps_list)}
{generate_separator(29)}
"""
        
        for i, (vps_id, vps) in enumerate(vps_list.items(), 1):
            status = "🟢" if vps.get("status") == "active" else "🔴"
            vps_type = vps.get('type', 'regular')
            type_icon = "🟦" if vps_type == "zivpn" else "🟩"
            type_text = "ZiVPN" if vps_type == "zivpn" else "Regular"
            created = datetime.fromisoformat(vps["created_at"]).strftime('%d %b %Y')
            
            text += f"""
{type_icon}{status} *{vps.get('name', 'VPS')}*
├ ID: `{vps_id}`
├ IP: `{vps['ip']}`
├ Domain: {vps.get('domain', 'N/A')}
├ Type: {type_text}
├ SSH User: `{vps['ssh_user']}`
├ SSH Port: {vps.get('ssh_port', 22)}
├ Location: {vps.get('location', 'Unknown')}
└ Ditambahkan: {created}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

async def admin_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List semua user"""
    query = update.callback_query
    await query.answer()
    
    users = load_json(USERS_DB)
    
    if not users:
        text = f"""
{generate_header('DAFTAR USER')}

{generate_separator(29)}
📭 *Tidak Ada User Ditemukan*
{generate_separator(29)}
Belum ada user yang terdaftar.
Bagikan bot Anda untuk mendapatkan user!
{generate_separator(29)}
"""
    else:
        text = f"""
{generate_header('DAFTAR USER')}

{generate_separator(29)}
👥 *Total Users:* {len(users)}
{generate_separator(29)}

*10 User Terbaru:*
"""
        
        sorted_users = sorted(users.values(), key=lambda x: x.get("created_at", ""), reverse=True)[:10]
        
        for user in sorted_users:
            join_date = datetime.fromisoformat(user["created_at"]).strftime('%d %b %Y')
            role = "👑" if user.get("role") == "admin" else "👤"
            active_accounts = len(user.get("vpn_accounts", []))
            
            text += f"""
{role} *User ID:* `{user['user_id']}`
├ Balance: {format_money(user.get('balance', 0))}
├ Active Accounts: {active_accounts}
├ Total Spent: {format_money(user.get('total_spent', 0))}
├ Trial Used: {'✅ Ya' if user.get('trial_used', False) else '❌ Belum'}
└ Joined: {join_date}
"""
        
        if len(users) > 10:
            text += f"\n📝 ... dan {len(users) - 10} user lainnya."
    
    keyboard = [[InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

          
            
async def auto_reboot_time_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input waktu auto reboot"""
    time_str = update.message.text.strip()
    
    # Validasi format waktu
    try:
        datetime.datetime.strptime(time_str, "%H:%M")
    except:
        await update.message.reply_text("❌ Format waktu salah. Gunakan HH:MM\nContoh: 03:00")
        return AUTO_REBOOT_TIME
    
    context.user_data["auto_reboot_time"] = time_str
    
    await update.message.reply_text(
        "Masukkan hari reboot (pisah dengan koma):\n"
        "0=Minggu, 1=Senin, 2=Selasa, 3=Rabu, 4=Kamis, 5=Jumat, 6=Sabtu\n"
        "Contoh: 1,3,5 untuk Senin, Rabu, Jumat\n"
        "atau 'daily' untuk setiap hari"
    )
    
    return AUTO_REBOOT_DAYS

async def auto_reboot_days_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle input hari auto reboot"""
    days_input = update.message.text.strip().lower()
    
    vps_id = context.user_data.get("auto_reboot_vps_id")
    time_str = context.user_data.get("auto_reboot_time")
    
    if not vps_id or not time_str:
        await update.message.reply_text("❌ Data tidak lengkap. Silakan mulai ulang.")
        return ConversationHandler.END
    
    # Parse hari
    if days_input == 'daily':
        days = [0, 1, 2, 3, 4, 5, 6]  # Semua hari
        days_display = "Setiap hari"
    else:
        try:
            days = [int(d.strip()) for d in days_input.split(',')]
            # Validasi hari 0-6
            if any(day < 0 or day > 6 for day in days):
                raise ValueError
            
            # Konversi ke nama hari
            day_names = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]
            days_display = ", ".join([day_names[day] for day in days])
            
        except:
            await update.message.reply_text(
                "❌ Format hari salah.\n"
                "Gunakan angka 0-6 dipisah koma (contoh: 1,3,5) atau 'daily'"
            )
            return AUTO_REBOOT_DAYS
    
    vps = get_vps(vps_id)
    if not vps:
        await update.message.reply_text("❌ VPS tidak ditemukan.")
        return ConversationHandler.END
    
    context.user_data["auto_reboot_days"] = days
    context.user_data["auto_reboot_days_display"] = days_display
    
    text = f"""
{generate_header('KONFIRMASI AUTO REBOOT')}

{generate_separator(29)}
📋 *Detail Auto Reboot:*
├ Server: {vps.get('name', 'VPS')}
├ IP: `{vps['ip']}`
├ Waktu: {time_str} (24 jam)
├ Hari: {days_display}
└ Total hari: {len(days)} hari/minggu
{generate_separator(29)}
⚡ Server akan reboot otomatis sesuai jadwal.
{generate_separator(29)}
✅ Konfirmasi set auto reboot?
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ SET AUTO REBOOT", callback_data="confirm_auto_reboot"),
            InlineKeyboardButton("❌ BATALKAN", callback_data="cancel_auto_reboot")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return AUTO_REBOOT_CONFIRM

async def auto_reboot_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Konfirmasi dan simpan auto reboot"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_auto_reboot":
        await query.edit_message_text("❌ Auto reboot dibatalkan.")
        return ConversationHandler.END
    
    # Dapatkan data dari context
    vps_id = context.user_data.get("auto_reboot_vps_id")
    time_str = context.user_data.get("auto_reboot_time")
    days = context.user_data.get("auto_reboot_days")
    days_display = context.user_data.get("auto_reboot_days_display")
    
    if not all([vps_id, time_str, days]):
        await query.edit_message_text("❌ Data tidak lengkap.")
        return ConversationHandler.END
    
    vps = get_vps(vps_id)
    if not vps:
        await query.edit_message_text("❌ VPS tidak ditemukan.")
        return ConversationHandler.END
    
    # Simpan ke database khusus auto reboot
    auto_reboot_db = f"{DB_FOLDER}/auto_reboot.json"
    auto_reboot_data = load_json(auto_reboot_db)
    
    auto_reboot_data[vps_id] = {
        "vps_name": vps.get('name', 'VPS'),
        "vps_ip": vps['ip'],
        "time": time_str,
        "days": days,
        "days_display": days_display,
        "set_by": query.from_user.id,
        "set_at": datetime.now().isoformat(),
        "last_reboot": None,
        "status": "active"
    }
    
    save_json(auto_reboot_db, auto_reboot_data)
    
    # Start auto reboot scheduler jika belum berjalan
    if not hasattr(context.application, 'auto_reboot_scheduler_started'):
        asyncio.create_task(auto_reboot_scheduler(context.application))
        context.application.auto_reboot_scheduler_started = True
    
    text = f"""
{generate_header('AUTO REBOOT BERHASIL DISET')}

{generate_separator(29)}
✅ *Auto Reboot Telah Diaktifkan!*
{generate_separator(29)}
📋 *Detail Jadwal:*
├ Server: {vps.get('name', 'VPS')}
├ IP: `{vps['ip']}`
├ Waktu: {time_str} (24 jam)
├ Hari: {days_display}
└ Status: 🟢 AKTIF
{generate_separator(29)}
⚡ Server akan reboot otomatis sesuai jadwal.
⏰ Next check: 60 detik sekali
{generate_separator(29)}
🔔 *Notifikasi reboot akan dikirim ke admin.*
{generate_separator(29)}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Set Lainnya", callback_data="admin_auto_reboot")],
        [InlineKeyboardButton("🔙 Panel Admin", callback_data="admin_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def auto_reboot_scheduler(application):
    """Scheduler untuk auto reboot"""
    import asyncio
    from datetime import datetime
    
    auto_reboot_db = f"{DB_FOLDER}/auto_reboot.json"
    
    while True:
        try:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_day = now.weekday()  # 0=Senin, 6=Minggu (sesuai Python)
            
            # Baca data auto reboot
            auto_reboot_data = load_json(auto_reboot_db)
            
            for vps_id, schedule in auto_reboot_data.items():
                if schedule.get("status") != "active":
                    continue
                
                # Cek waktu dan hari
                if current_time == schedule["time"] and current_day in schedule["days"]:
                    # Cek apakah sudah reboot hari ini
                    last_reboot = schedule.get("last_reboot")
                    today = now.date()
                    
                    if last_reboot:
                        try:
                            last_reboot_date = datetime.fromisoformat(last_reboot).date()
                            if last_reboot_date == today:
                                continue  # Sudah reboot hari ini
                        except:
                            pass
                    
                    # Dapatkan data VPS
                    vps = get_vps(vps_id)
                    if not vps:
                        continue
                    
                    # Execute reboot command
                    success, output = await execute_ssh_command(
                        vps["ip"],
                        vps.get("ssh_port", 22),
                        vps["ssh_user"],
                        vps["ssh_pass"],
                        "reboot"
                    )
                    
                    # Update last reboot time
                    auto_reboot_data[vps_id]["last_reboot"] = now.isoformat()
                    save_json(auto_reboot_db, auto_reboot_data)
                    
                    # Kirim notifikasi ke semua admin
                    for admin_id in ADMIN_IDS:
                        try:
                            await application.bot.send_message(
                                admin_id,
                                f"⏰ *AUTO REBOOT EXECUTED*\n\n"
                                f"Server: {vps.get('name', 'VPS')}\n"
                                f"IP: `{vps['ip']}`\n"
                                f"Waktu: {current_time}\n"
                                f"Hari: {schedule['days_display']}\n"
                                f"Status: {'✅ Berhasil' if success else '❌ Gagal'}\n"
                                f"Output: `{output[:100] if output else 'N/A'}`",
                                parse_mode=ParseMode.MARKDOWN
                            )
                        except:
                            pass
            
            # Tunggu 60 detik sebelum check lagi
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"Error in auto_reboot_scheduler: {e}")
            await asyncio.sleep(60)                
            
        
async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command untuk admin menambahkan saldo user"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ Hanya admin yang bisa menggunakan command ini.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Format: /addbalance <user_id> <jumlah>")
        return
    
    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
        
        user = get_user(target_user_id)
        new_balance = user["balance"] + amount
        
        update_user(target_user_id, {"balance": new_balance})
        
        add_transaction({
            "user_id": target_user_id,
            "type": "topup_admin",
            "amount": amount,
            "description": f"Top up oleh admin",
            "admin_id": user_id,
            "status": "completed",
            "created_at": datetime.now().isoformat()
        })
        
        try:
            await context.bot.send_message(
                target_user_id,
                f"""
{generate_header('SALDO DITAMBAHKAN')}

{generate_separator(29)}
✅ *Saldo Berhasil Ditambahkan!*
{generate_separator(29)}
💰 Jumlah Ditambahkan: {format_money(amount)}
💰 Saldo Baru: {format_money(new_balance)}
{generate_separator(29)}
🎉 Terima kasih telah menggunakan layanan kami!
{generate_separator(29)}
"""
            )
        except:
            pass
        
        await update.message.reply_text(
            f"""
{generate_header('SALDO DITAMBAHKAN')}

{generate_separator(29)}
✅ *Saldo berhasil ditambahkan!*
{generate_separator(29)}
👤 User ID: {target_user_id}
💰 Jumlah: {format_money(amount)}
💰 Saldo Baru: {format_money(new_balance)}
{generate_separator(29)}
"""
        )
        
    except ValueError:
        await update.message.reply_text("❌ Format tidak valid. Gunakan: /addbalance <user_id> <jumlah>")

# ============================================
# SCHEDULED TASKS

# ============================================

async def scheduled_cleanup_task():
    """Task scheduled untuk cleanup otomatis"""
    while True:
        try:
            print(f"[SCHEDULED CLEANUP] Running at {datetime.now()}")
            
            # Cleanup expired trials
            trial_count = await cleanup_expired_trials()
            if trial_count > 0:
                print(f"[SCHEDULED CLEANUP] {trial_count} trial accounts cleaned")
            
            # Cleanup expired regular accounts
            account_count = await cleanup_expired_accounts()
            if account_count > 0:
                print(f"[SCHEDULED CLEANUP] {account_count} expired accounts cleaned")
            
            # Tunggu 5 menit sebelum cleanup berikutnya
            await asyncio.sleep(300)
            
        except Exception as e:
            print(f"[SCHEDULED CLEANUP ERROR] {e}")
            await asyncio.sleep(60)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua callback query dengan routing yang benar"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    try:
        # Routing callback queries dengan pattern matching
        if data == "back_to_main":
            await start(update, context)
            return ConversationHandler.END
        
        # ==================== RENTAL SLOT HANDLERS (NEW) ====================
        
        # List semua slot
        elif data == "rental_list_slots":
            await user_rental_list_slots(update, context)
            return
        
        # Beli slot baru - entry point
        elif data == "rental_buy_slot":
            await user_rental_buy_slot(update, context)
            return "RENTAL_BUY_SLOT"
        
        # Beli slot dengan durasi tertentu (1,3,6,12,lifetime)
        elif data.startswith("rental_buy_slot_"):
            # Pattern: rental_buy_slot_1, rental_buy_slot_3, rental_buy_slot_lifetime, dll
            await user_rental_buy_slot_confirm(update, context)
            return "RENTAL_BUY_SLOT"
        
        # Konfirmasi beli slot
        elif data.startswith("rental_confirm_slot_"):
            # Pattern: rental_confirm_slot_1, rental_confirm_slot_3, rental_confirm_slot_lifetime, dll
            await user_rental_execute_buy_slot(update, context)
            return
        
        # Pilih slot untuk diperpanjang
        elif data == "rental_extend_slot_select":
            await user_rental_extend_slot_select(update, context)
            return
        
        # Pilih durasi perpanjangan untuk slot tertentu
        elif data.startswith("rental_extend_slot_") and len(data.split("_")) == 4:
            # Pattern: rental_extend_slot_abc123 (slot_id)
            await user_rental_extend_slot_duration(update, context)
            return "RENTAL_EXTEND_SLOT_DURATION"
        
        # Konfirmasi perpanjangan dengan durasi (1,3,6,12,lifetime)
        elif data.startswith("rental_extend_slot_") and data.split("_")[3] in ["1","3","6","12","lifetime"]:
            # Pattern: rental_extend_slot_1, rental_extend_slot_3, dll
            await user_rental_extend_slot_confirm(update, context)
            return "RENTAL_EXTEND_SLOT_CONFIRM"
        
        # Eksekusi perpanjangan slot
        elif data.startswith("rental_confirm_extend_slot_"):
            # Pattern: rental_confirm_extend_slot_abc123_1 (slot_id_duration)
            await user_rental_execute_extend_slot(update, context)
            return
        
        # Detail slot tertentu
        elif data.startswith("rental_slot_detail_"):
            # Pattern: rental_slot_detail_abc123 (slot_id)
            await user_rental_slot_detail(update, context)
            return
        
        # Tambah IP ke slot tertentu
        elif data.startswith("rental_add_ip_slot_"):
            # Pattern: rental_add_ip_slot_abc123 (slot_id)
            await user_rental_add_ip_to_slot(update, context)
            return
        
        # Hapus IP dari slot (menu pilih IP)
        elif data.startswith("rental_remove_ip_slot_"):
            # Pattern: rental_remove_ip_slot_abc123 (slot_id)
            await user_rental_remove_ip_from_slot(update, context)
            return
        
        # Konfirmasi hapus IP tertentu
        elif data.startswith("rental_confirm_remove_ip_"):
            # Pattern: rental_confirm_remove_ip_abc123_192.168.1.1 (slot_id_ip)
            await user_rental_confirm_remove_ip(update, context)
            return
        
        # Eksekusi hapus IP
        elif data.startswith("rental_execute_remove_ip_"):
            # Pattern: rental_execute_remove_ip_abc123_192.168.1.1 (slot_id_ip)
            await user_rental_execute_remove_ip(update, context)
            return
        
        # ==================== ADMIN RENTAL SLOT HANDLERS ====================
        
        elif data == "admin_rental_set_max_slots":
            await admin_rental_set_max_slots(update, context)
            return
        
        elif data == "admin_rental_set_ip_per_slot":
            await admin_rental_set_ip_per_slot(update, context)
            return
        
        elif data == "admin_rental_add_slot":
            await admin_rental_add_slot_start(update, context)
            return
        
        elif data == "admin_rental_delete_slot":
            await admin_rental_delete_slot_start(update, context)
            return
        
        elif data.startswith("admin_rental_user_slots_"):
            user_id = int(data.replace("admin_rental_user_slots_", ""))
            await admin_rental_user_slots(update, context, user_id)
            return
        
        elif data.startswith("admin_rental_slot_detail_"):
            slot_id = data.replace("admin_rental_slot_detail_", "")
            await admin_rental_slot_detail(update, context, slot_id)
            return
        
        elif data.startswith("admin_rental_delete_slot_"):
            slot_id = data.replace("admin_rental_delete_slot_", "")
            await admin_rental_delete_slot_confirm(update, context, slot_id)
            return
        
        # ==================== ADMIN DELETE ACCOUNT ====================
        elif data == "admin_delete_account":
            await admin_delete_account_start(update, context)
        
        elif data in ["delete_search_username", "delete_search_userid", "delete_search_expired", "delete_all_trials"]:
            # Routing ke conversation handler
            if data == "delete_search_username":
                await admin_delete_search_username(update, context)
            elif data == "delete_search_userid":
                await admin_delete_search_userid(update, context)
            elif data == "delete_search_expired":
                await admin_delete_search_expired(update, context)
            elif data == "delete_all_trials":
                await admin_delete_account_confirm(update, context)
        
        elif data.startswith("delete_account_") or data.startswith("delete_expired_"):
            await admin_delete_account_confirm(update, context)
        
        elif data.startswith("confirm_delete_"):
            await admin_delete_account_execute(update, context)
        
        # ==================== ADMIN TOPUP ====================
        elif data == "admin_topup_panel":
            await admin_topup_panel(update, context)
        
        elif data == "admin_upload_qris":
            await admin_upload_qris(update, context)
        
        elif data == "admin_topup_stats":
            await admin_topup_stats(update, context)
        
        # ==================== TOPUP HANDLERS ====================
        elif data == "user_topup":
            await user_topup_start(update, context)
        
        elif data.startswith("topup_"):
            await user_topup_amount(update, context)
        
        elif data.startswith("check_payment_"):
            await user_check_payment_status(update, context)
        
        # ==================== ADMIN PANEL ====================
        elif data == "admin_panel":
            # Ambil data dari database untuk ditampilkan
            try:
                rental_price = rental_db.get_price_per_month() if 'rental_db' in dir() else 12000
                total_rental_users = len(rental_db.get_all_users()) if 'rental_db' in dir() else 0
                total_rental_ips = len(rental_db.get_all_ips()) if 'rental_db' in dir() else 0
                github_configured = github_mgr.is_configured() if 'github_mgr' in dir() else False
            except:
                rental_price = 12000
                total_rental_users = 0
                total_rental_ips = 0
                github_configured = False
            
            keyboard = [
                [
                    InlineKeyboardButton("➕ Tambah VPS", callback_data="admin_add_vps"),
                    InlineKeyboardButton("✏️ Edit/Hapus VPS", callback_data="admin_edit_vps")
                ],
                [
                    InlineKeyboardButton("💰 Set Harga", callback_data="admin_set_price"),
                    InlineKeyboardButton("🎯 Set Harga Server", callback_data="admin_set_server_price")
                ],
                [
                    InlineKeyboardButton("🌐 Set IP Limit", callback_data="admin_set_ip_limit"),
                    InlineKeyboardButton("📊 Dashboard", callback_data="admin_dashboard")
                ],
                [
                    InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                    InlineKeyboardButton("📋 Log Broadcast", callback_data="broadcast_logs")
                ],
                [
                    InlineKeyboardButton("🖥️ List VPS", callback_data="admin_list_vps"),
                    InlineKeyboardButton("👥 List User", callback_data="admin_list_users")
                ],
                [
                    InlineKeyboardButton("➕ Tambah Saldo", callback_data="admin_add_balance"),
                    InlineKeyboardButton("🔧 Set IP Tambahan", callback_data="admin_set_extra_ip_price")
                ],
                # Baris baru: RENTAL SYSTEM
                [
                    InlineKeyboardButton("📦 RENTAL SYSTEM", callback_data="admin_rental_panel"),
                    InlineKeyboardButton("👑 Topup Admin", callback_data="admin_topup_panel")
                ],
                [
                    InlineKeyboardButton("📤 Upload QRIS", callback_data="admin_upload_qris"),
                    InlineKeyboardButton("🧪 Test Rental", callback_data="user_rental")
                ],
                # Baris tambahan admin
                [
                    InlineKeyboardButton("🔄 Rebuild VPS", callback_data="admin_rebuild_vps"),
                    InlineKeyboardButton("⏰ Auto Reboot", callback_data="admin_auto_reboot")
                ],
                [
                    InlineKeyboardButton("🗑️ Delete Account", callback_data="admin_delete_account"),
                    InlineKeyboardButton("📊 Statistik", callback_data="admin_stats")
                ],
                # Baris terakhir: Fitur User
                [
                    InlineKeyboardButton("🛒 Beli VPN", callback_data="user_buy_vpn"),
                    InlineKeyboardButton("🔑 Cek Akun", callback_data="user_check_account")
                ],
                [
                    InlineKeyboardButton("🎁 Trial VPN", callback_data="user_trial_vpn"),
                    InlineKeyboardButton("📋 Panduan", callback_data="user_guide")
                ]
            ]
            
            text = f"""
{generate_header('PANEL ADMIN')}

{generate_separator(29)}
👑 *Selamat datang kembali, Admin!*
{generate_separator(29)}
📊 *STATUS SISTEM:*
├─ 💳 Topup: ✅ Aktif
├─ 📦 Rental: ✅ **BARU!**
├─ 🔄 Auto Reboot: ✅
└─ 📢 Broadcast: ✅ Tersedia

📦 *RENTAL SYSTEM:*
├─ Harga/bulan: {format_money(rental_price)}
├─ Total User: {total_rental_users}
├─ Total IP: {total_rental_ips}
└─ GitHub: {'✅ Terkoneksi' if github_configured else '❌ Belum konfigurasi'}

Pilih opsi dari menu admin di bawah:
{generate_separator(29)}
"""
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        
        # ==================== RENTAL HANDLERS ====================
        elif data == "user_rental":
            await user_rental_start(update, context)
            return

        elif data == "admin_rental_panel":
            await admin_rental_panel(update, context)
            return

        elif data == "admin_rental_set_price":
            await admin_rental_set_price(update, context)
            return

        elif data == "admin_rental_github":
            await admin_rental_github_config(update, context)
            return

        elif data.startswith("admin_rental_github_"):
            await admin_rental_github_input(update, context)
            return

        elif data == "admin_rental_users":
            await admin_rental_list_users(update, context)
            return

        elif data.startswith("admin_rental_user_"):
            await admin_rental_user_detail(update, context)
            return

        elif data == "admin_rental_ips":
            await admin_rental_list_ips(update, context)
            return

        elif data == "admin_rental_add_ip" or data.startswith("admin_rental_add_ip_user_"):
            await admin_rental_add_ip_start(update, context)
            return

        elif data == "admin_rental_delete_ip":
            await admin_rental_delete_ip(update, context)
            return

        elif data == "admin_rental_sync":
            await admin_rental_sync(update, context)
            return

        elif data == "admin_rental_settings":
            await admin_rental_settings(update, context)
            return

        elif data.startswith("admin_rental_confirm_delete_ip_"):
            ip_address = data.replace("admin_rental_confirm_delete_ip_", "")
            # Hapus IP
            if 'rental_db' in dir():
                rental_db.remove_ip(ip_address)
            await query.edit_message_text(f"✅ IP `{ip_address}` berhasil dihapus.", parse_mode="Markdown")
            await admin_rental_panel(update, context)
            return

        elif data.startswith("rental_"):
            # Handle rental callbacks yang belum tertangani (legacy handlers)
            if data == "rental_add_ip":
                await user_rental_add_ip_start(update, context)
            elif data == "rental_my_ips":
                await user_rental_my_ips(update, context)
            elif data.startswith("rental_delete_ip_"):
                await user_rental_delete_ip(update, context)
            elif data.startswith("rental_confirm_delete_"):
                await user_rental_confirm_delete(update, context)
            elif data == "rental_status":
                await user_rental_status(update, context)
            elif data == "rental_guide":
                await user_rental_guide(update, context)
            elif data == "rental_extend":
                await user_rental_extend(update, context)
            elif data.startswith("rental_buy_"):
                await user_rental_buy_handler(update, context)
            elif data.startswith("rental_confirm_"):
                await user_rental_confirm_handler(update, context)
            elif data.startswith("rental_extend_"):
                await user_rental_extend_confirm(update, context)
            elif data.startswith("rental_confirm_extend_"):
                await user_rental_extend_execute(update, context)
        
        # ==================== USER MENU ====================
        elif data == "user_buy_vpn":
            await user_buy_vpn_start(update, context)
        
        elif data == "user_balance":
            await user_balance(update, context)
        
        elif data == "user_check_account":
            await user_check_account(update, context)
        
        elif data == "user_trial_vpn":
            await user_trial_vpn(update, context)
        
        elif data == "user_guide":
            await user_guide(update, context)
        
        elif data == "user_upgrade_account":
            await user_upgrade_account(update, context)
        
        # ==================== ADMIN VPS MANAGEMENT ====================
        elif data == "admin_add_vps":
            await admin_add_vps_start(update, context)
        
        elif data == "admin_edit_vps":
            await admin_edit_vps_start(update, context)
        
        elif data == "admin_add_balance":
            await admin_add_balance_start(update, context)
        
        elif data == "admin_set_price":
            await admin_set_price_start(update, context)
        
        elif data == "admin_set_extra_ip_price":
            await admin_set_extra_ip_price(update, context)
        
        elif data == "admin_set_server_price":
            await admin_set_server_price_start(update, context)
        
        elif data == "admin_dashboard":
            await admin_dashboard(update, context)
        
        elif data == "admin_list_vps":
            await admin_list_vps(update, context)
        
        elif data == "admin_list_users":
            await admin_list_users(update, context)
        
        elif data == "admin_set_ip_limit":
            await admin_set_ip_limit(update, context)
        
        elif data == "admin_stats":
            await admin_stats(update, context)
        
        # ==================== BROADCAST ====================
        elif data == "admin_broadcast":
            await admin_broadcast_start(update, context)
        
        elif data == "broadcast_logs":
            await admin_broadcast_logs(update, context)
        
        elif data == "broadcast_confirm":
            await admin_execute_broadcast(update, context)
        
        elif data.startswith("show_failed_"):
            await show_failed_users(update, context)
        
        # ==================== USER VPS SELECTION ====================
        elif data.startswith("select_vps_"):
            await user_select_vps_handler(update, context)
        
        elif data.startswith("service_"):
            await user_select_service_handler(update, context)
        
        elif data.startswith("duration_"):
            await user_select_duration_handler(update, context)
        
        elif data.startswith("duration_page_"):
            page = int(data.replace("duration_page_", ""))
            context.user_data["duration_page"] = page
            await show_duration_page(update, context, page)
        
        elif data.startswith("extra_ips_"):
            await user_select_extra_ips_handler(update, context)
        
        # ==================== UPGRADE HANDLERS ====================
        elif data.startswith("upgrade_select_"):
            await user_select_upgrade_type(update, context)
        
        elif data == "upgrade_extend":
            await user_upgrade_extend(update, context)
        
        elif data == "upgrade_ip_limit":
            await user_upgrade_ip_limit(update, context)
        
        elif data.startswith("extend_"):
            await user_confirm_upgrade(update, context)
        
        elif data.startswith("add_ip_"):
            await user_confirm_upgrade(update, context)
        
        elif data.startswith("do_upgrade_"):
            await do_upgrade(update, context)
        
        # ==================== IP LIMIT MANAGEMENT ====================
        elif data.startswith("ip_limit_vps_"):
            await admin_set_ip_limit_select(update, context)
        
        elif data.startswith("ip_limit_service_"):
            await handle_ip_limit_service_selection(update, context)
        
        # ==================== TRIAL HANDLERS ====================
        elif data.startswith("trial_service_"):
            await user_select_trial_service(update, context)
        
        elif data.startswith("trial_vps_"):
            await user_select_trial_vps(update, context)
        
        elif data == "create_trial":
            await user_create_trial(update, context)
        
        # ==================== PRICE MANAGEMENT ====================
        elif data.startswith("server_price_vps_"):
            await admin_set_server_price_select_vps(update, context)
        
        elif data.startswith("price_"):
            await admin_set_price_type(update, context)
        
        elif data.startswith("server_price_service_"):
            await admin_set_server_price_select_service(update, context)
        
        # ==================== VPS EDITING ====================
        elif data.startswith("edit_vps_select_"):
            await admin_edit_vps_select(update, context)
        
        elif data.startswith("edit_field_"):
            await admin_edit_vps_field(update, context)
        
        elif data in ["delete_vps_confirm", "delete_vps_yes"]:
            await admin_delete_vps_handler(update, context)
        
        # ==================== VPS TYPES ====================
        elif data.startswith("vps_type_"):
            await admin_add_vps_type(update, context)
        
        # ==================== QUOTA UPGRADE ====================
        elif data == "upgrade_quota":
            await handle_upgrade_quota(update, context)
        
        elif data == "custom_ip_amount":
            await handle_custom_ip(update, context)
        
        elif data.startswith("confirm_quota_"):
            await handle_quota_confirmation(update, context)
        
        # ==================== REBUILD VPS ====================
        elif data == "admin_rebuild_vps":
            await admin_rebuild_vps_start(update, context)
        
        elif data.startswith("rebuild_select_"):
            await admin_rebuild_select_vps(update, context)
        
        elif data.startswith("rebuild_os_"):
            await admin_rebuild_select_os(update, context)
        
        elif data.startswith("rebuild_ver_"):
            await admin_rebuild_select_version(update, context)
        
        elif data == "confirm_rebuild":
            await admin_rebuild_confirm(update, context)
        
        elif data == "cancel_rebuild":
            await query.edit_message_text("❌ Rebuild dibatalkan.")
            return ConversationHandler.END
        
        # ==================== AUTO REBOOT ====================
        elif data == "admin_auto_reboot":
            await admin_auto_reboot_start(update, context)
        
        elif data.startswith("auto_reboot_select_"):
            vps_id = data.replace("auto_reboot_select_", "")
            context.user_data["auto_reboot_vps_id"] = vps_id
            await query.edit_message_text(
                f"⏰ *Auto Reboot VPS*\n\n"
                f"Masukkan waktu reboot (format HH:MM, 24 jam):\n"
                f"Contoh: `03:00` untuk reboot jam 3 pagi\n\n"
                f"Ketik /cancel untuk membatalkan.",
                parse_mode="Markdown"
            )
            return 'AUTO_REBOOT_TIME'
        
        # ==================== PAYMENT CONFIRMATION ====================
        elif data in ["confirm_payment", "cancel_payment"]:
            await user_confirm_order_handler(update, context)
        
        elif data in ["confirm_add_balance", "cancel_add_balance"]:
            await admin_add_balance_confirm(update, context)
        
        elif data in ["confirm_quota_upgrade", "cancel_quota_upgrade"]:
            await handle_quota_confirmation(update, context)
        
        # ==================== UNHANDLED CALLBACK ====================
        else:
            # Log untuk debugging
            print(f"Unhandled callback data: {data}")
            await query.edit_message_text(
                f"⚠️ *Handler belum tersedia*\n\n"
                f"Callback data: `{data}`\n\n"
                f"Silakan coba lagi atau hubungi admin.",
                parse_mode="Markdown"
            )
    
    except Exception as e:
        print(f"Error in callback handler: {e}")
        import traceback
        traceback.print_exc()
        await query.edit_message_text(
            "❌ *Terjadi error!*\n\nSilakan coba lagi atau hubungi admin.",
            parse_mode="Markdown"
        )
    
    # Default return (hanya untuk handler yang tidak mengembalikan ConversationHandler.END sendiri)
    return ConversationHandler.END            
              
            
            
async def cleanup_trial_accounts_task():
    """Task untuk membersihkan akun trial yang expired"""
    while True:
        try:
            expired_trials = cleanup_expired_trials()
            expired_accounts = cleanup_expired_accounts()
            
            if expired_trials > 0 or expired_accounts > 0:
                print(f"✅ Cleaned up {expired_trials} trial accounts and {expired_accounts} expired accounts")
            
            await asyncio.sleep(300)
        except Exception as e:
            print(f"Error in cleanup task: {e}")
            await asyncio.sleep(60)

            
def setup_validation_thread():
    """Setup thread for automatic validation"""
    validation_thread = Thread(target=validation_loop, daemon=True)
    validation_thread.start()
    print("✅ Thread validasi otomatis berjalan...")
            
            
async def scheduled_balance_sync():
    """Task scheduled untuk sync balance semua user secara berkala"""
    while True:
        try:
            print(f"[BALANCE SYNC] Running scheduled sync at {datetime.now()}")
            
            # Sync semua user yang ada di database
            users_data = load_json(USERS_DB)
            sync_count = 0
            
            for user_id_str in users_data.keys():
                try:
                    user_id = int(user_id_str)
                    if BalanceUpdateHandler.sync_user_balance(user_id):
                        sync_count += 1
                except:
                    continue
            
            if sync_count > 0:
                print(f"[BALANCE SYNC] {sync_count} users synced")
            
            # Tunggu 10 menit sebelum sync berikutnya
            await asyncio.sleep(600)
            
        except Exception as e:
            print(f"[BALANCE SYNC ERROR] {e}")
            await asyncio.sleep(60)
          
# ============================================
# MAIN FUNCTION - VERSI LENGKAP DENGAN PERBAIKAN
# ============================================

def main():
    """Main function dengan setup lengkap untuk menjalankan bot Telegram"""
    # Setup logging untuk monitoring
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Inisialisasi database
    init_database()
    
    # Setup thread validasi otomatis
    setup_validation_thread()
    
    # Buat aplikasi bot
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ==================== REGISTER COMMAND HANDLERS ====================
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addbalance", add_balance))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # ==================== CONVERSATION HANDLERS ====================
    
    # 1. Broadcast Conversation
    broadcast_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_broadcast_start, pattern='^admin_broadcast$'),
            CommandHandler('broadcast', broadcast_command)
        ],
        states={
            BROADCAST_TYPE: [
                CallbackQueryHandler(admin_broadcast_type, pattern='^broadcast_type_')
            ],
            BROADCAST_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_message),
                MessageHandler(filters.PHOTO & ~filters.COMMAND, admin_broadcast_message)
            ],
            BROADCAST_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_confirm)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(admin_execute_broadcast, pattern='^broadcast_confirm$'),
            CallbackQueryHandler(show_failed_users, pattern='^show_failed_'),
            CallbackQueryHandler(admin_panel, pattern='^admin_panel$')
        ],
        name="broadcast_conversation",
        persistent=False,
    )
    
    # 2. Check Account Conversation
    check_account_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(user_check_account, pattern='^user_check_account$')],
        states={
            USER_INPUT_ACCOUNT_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_check_account)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(start, pattern='^back_to_main$'),
            CommandHandler('start', start)
        ],
        name="check_account_conversation",
        persistent=False,
    )
    
    # 3. Trial VPN Conversation
    trial_vpn_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(user_trial_vpn, pattern='^user_trial_vpn$')],
        states={
            USER_SELECT_TRIAL_SERVICE: [
                CallbackQueryHandler(user_select_trial_service, pattern='^trial_service_')
            ],
            USER_SELECT_TRIAL_VPS: [
                CallbackQueryHandler(user_select_trial_vps, pattern='^trial_vps_')
            ],
            USER_CREATE_TRIAL: [
                CallbackQueryHandler(user_create_trial, pattern='^create_trial$')
            ],
        },
        fallbacks=[
            CallbackQueryHandler(start, pattern='^back_to_main$'),
            CommandHandler('start', start)
        ],
        name="trial_vpn_conversation",
        persistent=False,
    )
    
    # 4. Buy VPN Conversation
    buy_vpn_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(user_buy_vpn_start, pattern='^user_buy_vpn$')],
        states={
            USER_SELECT_VPS: [
                CallbackQueryHandler(user_select_vps_handler, pattern='^select_vps_')
            ],
            USER_SELECT_SERVICE: [
                CallbackQueryHandler(user_select_service_handler, pattern='^service_')
            ],
            USER_INPUT_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_input_username_handler)
            ],
            USER_SELECT_EXTRA_IPS: [
                CallbackQueryHandler(user_select_extra_ips_handler, pattern='^extra_ips_')
            ],
            USER_SELECT_DURATION: [
                CallbackQueryHandler(user_select_duration_handler, pattern='^duration_'),
                CallbackQueryHandler(show_duration_page, pattern='^duration_page_')
            ],
            USER_CONFIRM_ORDER: [
                CallbackQueryHandler(user_confirm_order_handler, pattern='^(confirm_payment|cancel_payment)$')
            ],
        },
        fallbacks=[
            CallbackQueryHandler(start, pattern='^back_to_main$'),
            CommandHandler('start', start)
        ],
        name="buy_vpn_conversation",
        persistent=False,
    )
    
    # 5. Add VPS Conversation
    add_vps_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_vps_start, pattern='^admin_add_vps$')],
        states={
            ADMIN_ADD_VPS_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_vps_name)
            ],
            ADMIN_ADD_VPS_IP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_vps_ip)
            ],
            ADMIN_ADD_VPS_DOMAIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_vps_domain)
            ],
            ADMIN_ADD_VPS_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_vps_location)
            ],
            ADMIN_ADD_VPS_TYPE: [
                CallbackQueryHandler(admin_add_vps_type, pattern='^vps_type_')
            ],
            ADMIN_ADD_VPS_SSH_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_vps_ssh_user)
            ],
            ADMIN_ADD_VPS_SSH_PASS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_vps_ssh_pass)
            ],
            ADMIN_ADD_VPS_SSH_PORT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_vps_ssh_port)
            ],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern='^admin_panel$')],
        name="add_vps_conversation",
        persistent=False,
    )
    
    # 6. Edit VPS Conversation
    edit_vps_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_edit_vps_start, pattern='^admin_edit_vps$')],
        states={
            ADMIN_EDIT_VPS_SELECT: [
                CallbackQueryHandler(admin_edit_vps_select, pattern='^edit_vps_select_')
            ],
            ADMIN_EDIT_VPS_FIELD: [
                CallbackQueryHandler(admin_edit_vps_field, pattern='^(edit_field_|delete_vps_confirm)$')
            ],
            ADMIN_EDIT_VPS_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_vps_value)
            ],
            ADMIN_DELETE_VPS: [
                CallbackQueryHandler(admin_delete_vps_handler, pattern='^(delete_vps_yes|delete_vps_confirm)$')
            ],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern='^admin_panel$')],
        name="edit_vps_conversation",
        persistent=False,
    )
    
    # 7. Set Price Default Conversation
    set_price_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_price_start, pattern='^admin_set_price$')],
        states={
            ADMIN_SET_PRICE_TYPE: [
                CallbackQueryHandler(admin_set_price_type, pattern='^price_')
            ],
            ADMIN_SET_PRICE_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price_duration)
            ],
            ADMIN_ADD_VPS_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price_value)
            ],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern='^admin_panel$')],
        name="set_price_conversation",
        persistent=False,
    )
    
    # 8. Set Server Price Conversation
    set_server_price_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_server_price_start, pattern='^admin_set_server_price$')],
        states={
            ADMIN_SET_SERVER_PRICE_SELECT_VPS: [
                CallbackQueryHandler(admin_set_server_price_select_vps, pattern='^server_price_vps_')
            ],
            ADMIN_SET_SERVER_PRICE_SELECT_SERVICE: [
                CallbackQueryHandler(admin_set_server_price_select_service, pattern='^server_price_service_')
            ],
            ADMIN_SET_SERVER_PRICE_DURATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_server_price_duration)
            ],
            ADMIN_SET_SERVER_PRICE_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_server_price_value)
            ],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern='^admin_panel$')],
        name="set_server_price_conversation",
        persistent=False,
    )
    
    # 9. Set Extra IP Price Conversation
    set_extra_ip_price_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_extra_ip_price, pattern='^admin_set_extra_ip_price$')],
        states={
            ADMIN_SET_EXTRA_IP_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_extra_ip_price)
            ],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern='^admin_panel$')],
        name="set_extra_ip_price_conversation",
        persistent=False,
    )
    
    # 10. Add Balance Conversation
    add_balance_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_balance_start, pattern='^admin_add_balance$')],
        states={
            ADMIN_ADD_BALANCE_USER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_balance_user_id)
            ],
            ADMIN_ADD_BALANCE_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_balance_amount)
            ],
            ADMIN_ADD_BALANCE_CONFIRM: [
                CallbackQueryHandler(admin_add_balance_confirm, pattern='^(confirm_add_balance|cancel_add_balance)$')
            ],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern='^admin_panel$')],
        name="add_balance_conversation",
        persistent=False,
    )
    
    # 11. Upgrade Account Conversation
    upgrade_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(user_upgrade_account, pattern='^user_upgrade_account$')],
        states={
            USER_SELECT_UPGRADE_TYPE: [
                CallbackQueryHandler(user_select_upgrade_type, pattern='^upgrade_select_')
            ],
            USER_UPGRADE_EXTEND: [
                CallbackQueryHandler(user_upgrade_extend, pattern='^upgrade_extend$'),
                CallbackQueryHandler(user_upgrade_ip_limit, pattern='^upgrade_ip_limit$'),
                CallbackQueryHandler(handle_upgrade_quota, pattern='^upgrade_quota$'),
                CallbackQueryHandler(handle_custom_ip, pattern='^custom_ip_amount$'),
            ],
            USER_UPGRADE_QUOTA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quota_input)
            ],
            USER_UPGRADE_CUSTOM_IP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_ip_input)
            ],
            USER_CONFIRM_UPGRADE: [
                CallbackQueryHandler(user_confirm_upgrade, pattern='^(extend_|add_ip_|do_upgrade_)'),
                CallbackQueryHandler(user_confirm_upgrade_quota, pattern='^confirm_quota_')
            ],
            USER_CONFIRM_UPGRADE_QUOTA: [
                CallbackQueryHandler(handle_quota_confirmation, pattern='^(confirm_quota_upgrade|cancel_quota_upgrade)$')
            ],
        },
        fallbacks=[
            CallbackQueryHandler(start, pattern='^back_to_main$'),
            CommandHandler('start', start)
        ],
        name="upgrade_conversation",
        persistent=False,
    )
    
    # 12. Set IP Limit Conversation
    set_ip_limit_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_set_ip_limit, pattern='^admin_set_ip_limit$')],
        states={
            ADMIN_SET_IP_LIMIT_SELECT: [
                CallbackQueryHandler(admin_set_ip_limit_select, pattern='^ip_limit_vps_')
            ],
            ADMIN_SET_IP_LIMIT_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ip_limit_value)
            ],
        },
        fallbacks=[CallbackQueryHandler(admin_panel, pattern='^admin_panel$')],
        name="set_ip_limit_conversation",
        persistent=False,
    )
    
    # 13. Rebuild VPS Conversation
    rebuild_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_rebuild_vps_start, pattern='^admin_rebuild_vps$')],
        states={
            REBUILD_SELECT_VPS: [
                CallbackQueryHandler(admin_rebuild_select_vps, pattern='^rebuild_select_'),
                CallbackQueryHandler(admin_panel, pattern='^admin_panel$')
            ],
            REBUILD_SELECT_OS: [
                CallbackQueryHandler(admin_rebuild_select_os, pattern='^rebuild_os_'),
                CallbackQueryHandler(admin_rebuild_vps_start, pattern='^admin_rebuild_vps$')
            ],
            REBUILD_SELECT_VERSION: [
                CallbackQueryHandler(admin_rebuild_select_version, pattern='^rebuild_ver_'),
                CallbackQueryHandler(admin_rebuild_select_os, pattern='^rebuild_os_')
            ],
            REBUILD_SET_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_rebuild_set_password)
            ],
            REBUILD_CONFIRMATION: [
                CallbackQueryHandler(admin_rebuild_confirm, pattern='^(confirm_rebuild|cancel_rebuild)$'),
                CallbackQueryHandler(admin_rebuild_vps_start, pattern='^admin_rebuild_vps$')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin_panel, pattern='^admin_panel$'),
            CommandHandler('cancel', lambda u, c: ConversationHandler.END)
        ],
        name="rebuild_conversation",
        persistent=False,
    )
    
    # 14. Topup Conversation
    topup_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_topup_start, pattern='^user_topup$'),
            CallbackQueryHandler(user_topup_history, pattern='^topup_history$')
        ],
        states={
            "TOPUP_AMOUNT": [
                CallbackQueryHandler(user_topup_amount, pattern='^topup_'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, user_topup_custom_amount)
            ],
            "TOPUP_CHECK": [
                CallbackQueryHandler(user_check_payment_status, pattern='^check_payment_')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(start, pattern='^back_to_main$'),
            CommandHandler('start', start)
        ],
        name="topup_conversation",
        persistent=False,
    )
    
    # 15. Auto Reboot Conversation
    auto_reboot_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_auto_reboot_start, pattern='^admin_auto_reboot$')],
        states={
            AUTO_REBOOT_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reboot_time_input)
            ],
            AUTO_REBOOT_DAYS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reboot_days_input)
            ],
            AUTO_REBOOT_CONFIRM: [
                CallbackQueryHandler(auto_reboot_confirm, pattern='^(confirm_auto_reboot|cancel_auto_reboot)$')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(admin_panel, pattern='^admin_panel$'),
            CommandHandler('cancel', lambda u, c: ConversationHandler.END)
        ],
        name="auto_reboot_conversation",
        persistent=False,
    )
    
    # 16. Delete Account Conversation
    delete_account_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_delete_account_start, pattern='^admin_delete_account$')],
        states={
            "DELETE_SEARCH_INPUT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_delete_search_input)
            ],
            "DELETE_CONFIRM": [
                CallbackQueryHandler(admin_delete_account_confirm, pattern='^delete_(search_username|search_userid|search_expired|all_trials|account_.*|expired_.*|all_expired)$')
            ],
            "DELETE_EXECUTE": [
                CallbackQueryHandler(admin_delete_account_execute, pattern='^confirm_delete_.*$')
            ],
        },
        fallbacks=[
            CallbackQueryHandler(admin_panel, pattern='^admin_panel$'),
            CommandHandler('cancel', lambda u, c: ConversationHandler.END)
        ],
        name="delete_account_conversation",
        persistent=False,
    )
    
    # ==================== RENTAL SLOT CONVERSATIONS ====================
    
    # 17. Beli Slot Conversation
    buy_slot_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_rental_buy_slot_confirm, pattern='^rental_buy_slot_[0-9]+$|^rental_buy_slot_lifetime$')
        ],
        states={
            "RENTAL_CONFIRM_SLOT": [
                CallbackQueryHandler(user_rental_execute_buy_slot, pattern='^rental_confirm_slot_')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(user_rental_buy_slot, pattern='^rental_buy_slot$'),
            CallbackQueryHandler(user_rental_list_slots, pattern='^rental_list_slots$')
        ],
        name="buy_slot_conversation",
        persistent=False,
    )
    
    # 18. Extend Slot Conversation
    extend_slot_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(user_rental_extend_slot_confirm, pattern='^rental_extend_slot_[0-9]+$|^rental_extend_slot_lifetime$')
        ],
        states={
            "RENTAL_EXTEND_SLOT_CONFIRM": [
                CallbackQueryHandler(user_rental_execute_extend_slot, pattern='^rental_confirm_extend_slot_')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(user_rental_extend_slot_select, pattern='^rental_extend_slot_select$'),
            CallbackQueryHandler(user_rental_list_slots, pattern='^rental_list_slots$')
        ],
        name="extend_slot_conversation",
        persistent=False,
    )
    
    # 19. Admin Set Max Slots Conversation
    #admin_set_max_slots_conv = ConversationHandler(
        #entry_points=[CallbackQueryHandler(admin_rental_set_max_slots, pattern='^admin_rental_set_max_slots$')],
        #states={
            #"ADMIN_RENTAL_SET_MAX_SLOTS": [
                #MessageHandler(filters.TEXT & ~filters.COMMAND, admin_rental_set_max_slots_value)
            #]
        #},
        #fallbacks=[CallbackQueryHandler(admin_rental_panel, pattern='^admin_rental_panel$')],
        #name="admin_set_max_slots_conv",
        #persistent=False,
    #)
    
    # 20. Admin Set IP Per Slot Conversation
    #admin_set_ip_per_slot_conv = ConversationHandler(
        #entry_points=[CallbackQueryHandler(admin_rental_set_ip_per_slot, pattern='^admin_rental_set_ip_per_slot$')],
        #states={
            #"ADMIN_RENTAL_SET_IP_PER_SLOT": [
                #MessageHandler(filters.TEXT & ~filters.COMMAND, admin_rental_set_ip_per_slot_value)
            #]
        #},
        #fallbacks=[CallbackQueryHandler(admin_rental_panel, pattern='^admin_rental_panel$')],
        #name="admin_set_ip_per_slot_conv",
        #persistent=False,
    #)
    
    # 21. Admin Add Slot Conversation
    #admin_add_slot_conv = ConversationHandler(
        #entry_points=[CallbackQueryHandler(admin_rental_add_slot_start, pattern='^admin_rental_add_slot$')],
        #states={
            #"ADMIN_RENTAL_ADD_SLOT_SELECT_USER": [
                #CallbackQueryHandler(admin_rental_add_slot_select_user, pattern='^admin_add_slot_user_')
            #],
            #"ADMIN_RENTAL_ADD_SLOT_MONTHS": [
                #MessageHandler(filters.TEXT & ~filters.COMMAND, admin_rental_add_slot_months)
            #]
        #},
        #fallbacks=[CallbackQueryHandler(admin_rental_panel, pattern='^admin_rental_panel$')],
        #name="admin_add_slot_conv",
        #persistent=False,
    #)
    
    # ==================== TAMBAHKAN SEMUA CONVERSATION HANDLERS ====================
    application.add_handler(broadcast_conversation)
    application.add_handler(check_account_conversation)
    application.add_handler(trial_vpn_conversation)
    application.add_handler(buy_vpn_conversation)
    application.add_handler(add_vps_conversation)
    application.add_handler(edit_vps_conversation)
    application.add_handler(set_price_conversation)
    application.add_handler(set_server_price_conversation)
    application.add_handler(set_extra_ip_price_conversation)
    application.add_handler(add_balance_conversation)
    application.add_handler(upgrade_conversation)
    application.add_handler(set_ip_limit_conversation)
    application.add_handler(rebuild_conv)
    application.add_handler(topup_conversation)
    application.add_handler(auto_reboot_conv)
    application.add_handler(delete_account_conversation)
    
    # Rental slot conversations
    application.add_handler(buy_slot_conv)
    application.add_handler(extend_slot_conv)
    #application.add_handler(admin_set_max_slots_conv)
    #application.add_handler(admin_set_ip_per_slot_conv)
    #application.add_handler(admin_add_slot_conv)
    
    # ==================== CALLBACK QUERY HANDLER ====================
    # Ini harus ditambahkan setelah semua conversation handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # ==================== MESSAGE HANDLERS ====================
    
    # Message handler untuk rental slot (tambah IP)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_rental_slot_message
    ))
    
    # Message handler untuk rental legacy
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_rental_message
    ))
    
    # Message handler untuk topup custom
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        user_topup_custom_amount
    ))
    
    # Message handler untuk photo (QRIS)
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # ==================== TOPUP HANDLERS ====================
    application.add_handler(CallbackQueryHandler(user_topup_start, pattern='^user_topup$'))
    application.add_handler(CallbackQueryHandler(user_topup_history, pattern='^topup_history$'))
    application.add_handler(CallbackQueryHandler(user_check_payment_status, pattern='^check_payment_'))
    application.add_handler(CallbackQueryHandler(admin_topup_panel, pattern='^admin_topup_panel$'))
    application.add_handler(CallbackQueryHandler(admin_upload_qris, pattern='^admin_upload_qris$'))
    application.add_handler(CallbackQueryHandler(admin_topup_stats, pattern='^admin_topup_stats$'))
    
    # ==================== RENTAL CALLBACK HANDLERS ====================
    # User rental handlers (legacy)
    application.add_handler(CallbackQueryHandler(user_rental_start, pattern='^user_rental$'))
    application.add_handler(CallbackQueryHandler(user_rental_add_ip_start, pattern='^rental_add_ip$'))
    application.add_handler(CallbackQueryHandler(user_rental_my_ips, pattern='^rental_my_ips$'))
    application.add_handler(CallbackQueryHandler(user_rental_delete_ip, pattern='^rental_delete_ip_'))
    application.add_handler(CallbackQueryHandler(user_rental_confirm_delete, pattern='^rental_confirm_delete_'))
    application.add_handler(CallbackQueryHandler(user_rental_status, pattern='^rental_status$'))
    application.add_handler(CallbackQueryHandler(user_rental_guide, pattern='^rental_guide$'))
    
    # Admin rental handlers (legacy)
    application.add_handler(CallbackQueryHandler(admin_rental_panel, pattern='^admin_rental_panel$'))
    application.add_handler(CallbackQueryHandler(admin_rental_set_price, pattern='^admin_rental_set_price$'))
    application.add_handler(CallbackQueryHandler(admin_rental_github_config, pattern='^admin_rental_github$'))
    application.add_handler(CallbackQueryHandler(admin_rental_github_input, pattern='^admin_rental_github_'))
    application.add_handler(CallbackQueryHandler(admin_rental_list_users, pattern='^admin_rental_users$'))
    application.add_handler(CallbackQueryHandler(admin_rental_user_detail, pattern='^admin_rental_user_'))
    application.add_handler(CallbackQueryHandler(admin_rental_list_ips, pattern='^admin_rental_ips$'))
    application.add_handler(CallbackQueryHandler(admin_rental_add_ip_start, pattern='^admin_rental_add_ip'))
    application.add_handler(CallbackQueryHandler(admin_rental_delete_ip, pattern='^admin_rental_delete_ip$'))
    application.add_handler(CallbackQueryHandler(admin_rental_sync, pattern='^admin_rental_sync$'))
    application.add_handler(CallbackQueryHandler(admin_rental_settings, pattern='^admin_rental_settings$'))
    
    # ==================== SCHEDULED TASKS ====================
    asyncio.get_event_loop().create_task(scheduled_cleanup_task())
    asyncio.get_event_loop().create_task(scheduled_balance_sync())
    
    # ==================== BANNER STARTUP ====================
    print("=" * 60)
    print("🤖 VPN STORE BOT - VERSI SUPER LENGKAP DENGAN SLOT SYSTEM")
    print("=" * 60)
    print("✅ SEMUA FITUR TELAH DITAMBAHKAN:")
    print(" 1. ✅ Rental Slot System (Multiple slots per user)")
    print(" 2. ✅ Beli slot baru dengan masa aktif sendiri")
    print(" 3. ✅ Perpanjang slot secara terpisah")
    print(" 4. ✅ Kelola IP per slot")
    print(" 5. ✅ Trial VPN (SSH, VMess, VLESS, Trojan, SS, ZiVPN)")
    print(" 6. ✅ Cleanup akun exp & trial otomatis")
    print(" 7. ✅ Set harga IP tambahan")
    print(" 8. ✅ Tampilan garis presisi")
    print(" 9. ✅ Format header yang rapi")
    print("10. ✅ Multi jenis layanan")
    print("11. ✅ Admin panel lengkap")
    print("12. ✅ Pembelian VPN dengan IP tambahan")
    print("13. ✅ FITUR BROADCAST LENGKAP")
    print("14. ✅ FITUR REBUILD VPS")
    print("15. ✅ FITUR AUTO REBOOT")
    print("16. ✅ FITUR DELETE ACCOUNT")
    print("=" * 60)
    print("📊 Database initialized")
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    print(f"💰 Extra IP Price: {format_money(EXTRA_IP_PRICE)}")
    print(f"💰 Rental Price per Slot: {format_money(rental_db.get_price_per_slot())}/bulan")
    print("=" * 60)
    print("🚀 Bot is now running...")
    print("=" * 60)
    
    # Jalankan bot dengan polling
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
            
