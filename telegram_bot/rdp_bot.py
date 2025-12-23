#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDP Installer Telegram Bot
Fitur:
- Hanya owner & user yang diizinkan yang bisa akses
- Install RDP dengan pilihan Windows
- Link Owner & Channel bisa diedit
- Multi Tumbal VPS support
- Google Drive Manager
"""

import telebot
from telebot import types
import json
import os
import subprocess
import threading

# ==================== KONFIGURASI ====================
# Disarankan set via environment variables (lebih aman dan tidak hilang saat update):
#   BOT_TOKEN="123456:ABCDEF"  (harus ada tanda ':')
#   OWNER_ID="123456789"
BOT_TOKEN = (os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE").strip()
try:
    OWNER_ID = int(os.getenv("OWNER_ID") or "123456789")
except ValueError:
    raise SystemExit("OWNER_ID harus angka")

if ":" not in BOT_TOKEN:
    raise SystemExit("BOT_TOKEN tidak valid (Token must contain a colon). Set BOT_TOKEN yang benar.")


def resolve_env_path() -> str:
    """Resolve persistent .env path (prefer project root /root/rdp-bot/.env)."""
    here = os.path.dirname(os.path.abspath(__file__))
    cwd_env = os.path.join(os.getcwd(), ".env")
    here_env = os.path.join(here, ".env")
    parent_env = os.path.join(os.path.dirname(here), ".env")

    for p in (cwd_env, parent_env, here_env):
        if os.path.exists(p):
            return p

    # Default: if script inside telegram_bot/, write one level above
    if os.path.basename(here) == "telegram_bot":
        return parent_env
    return here_env


def write_env(bot_token: str, owner_id: int) -> str:
    env_path = resolve_env_path()
    with open(env_path, "w") as f:
        f.write(f"BOT_TOKEN={bot_token}\n")
        f.write(f"OWNER_ID={owner_id}\n")
    try:
        os.chmod(env_path, 0o600)
    except Exception:
        pass
    return env_path

# File untuk menyimpan data
DATA_FILE = "bot_data.json"

# ==================== LOAD/SAVE DATA ====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            loaded = json.load(f)
            # Migrasi dari single tumbal_vps ke multiple tumbal_list
            if "tumbal_vps" in loaded and "tumbal_list" not in loaded:
                old_tumbal = loaded.pop("tumbal_vps")
                if old_tumbal.get("enabled") and old_tumbal.get("ip"):
                    loaded["tumbal_list"] = [{
                        "id": "tumbal1",
                        "name": "Tumbal VPS 1",
                        "ip": old_tumbal["ip"],
                        "password": old_tumbal["password"],
                        "enabled": True
                    }]
                    loaded["active_tumbal"] = "tumbal1"
                else:
                    loaded["tumbal_list"] = []
                    loaded["active_tumbal"] = ""
            return loaded
    return {
        "allowed_users": [OWNER_ID],
        "owner_link": "https://t.me/username_owner",
        "channel_link": "https://t.me/channel_name",
        "tumbal_list": [],  # List of tumbal VPS: [{id, name, ip, password, enabled}]
        "active_tumbal": ""  # ID of currently active tumbal VPS
    }

def get_active_tumbal():
    """Get the active tumbal VPS configuration"""
    active_id = data.get("active_tumbal", "")
    if not active_id:
        return None
    for t in data.get("tumbal_list", []):
        if t["id"] == active_id and t.get("enabled"):
            return t
    return None

def get_tumbal_by_id(tumbal_id):
    """Get tumbal VPS by ID"""
    for t in data.get("tumbal_list", []):
        if t["id"] == tumbal_id:
            return t
    return None

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ==================== INISIALISASI ====================
bot = telebot.TeleBot(BOT_TOKEN)
data = load_data()

# ==================== RDP TYPE OPTIONS ====================
RDP_TYPES = {
    "docker": {
        "name": "🐳 Docker RDP",
        "desc": "• Instalasi cepat (10-15 menit)\n• Berbagai versi Windows tersedia\n• Port 3389 & 8006 (web interface)\n• Cocok untuk testing & development"
    },
    "dedicated": {
        "name": "🖥 Dedicated RDP",
        "desc": "• Windows langsung di VPS (15-30 menit)\n• Performa optimal\n• Port 22 (custom untuk keamanan)\n• Cocok untuk production use"
    }
}

# ==================== WINDOWS OPTIONS ====================
WINDOWS_OPTIONS = {
    "1": "Windows Server 2012 R2",
    "2": "Windows Server 2016",
    "3": "Windows Server 2019",
    "4": "Windows Server 2022",
    "5": "Windows Server 2025",
    "6": "Windows 10 SuperLite",
    "7": "Windows 11 SuperLite",
    "8": "Windows 10 Atlas",
    "9": "Windows 11 Atlas",
    "10": "Windows 10 Pro",
    "11": "Windows 11 Pro",
    "12": "Tiny10 23H2",
    "13": "Tiny11 23H2"
}

# Simpan pilihan user (OS dan tipe RDP)
USER_SELECTED_OS = {}
USER_SELECTED_TYPE = {}

# ==================== MENU TEXT ====================
RDP_TYPE_MENU_TEXT = """🖥 <b>Pilih Jenis RDP Installation:</b>

🐳 <b>Docker RDP</b> - 1 kuota
• Instalasi cepat (10-15 menit)
• Berbagai versi Windows tersedia
• Port 3389 & 8006 (web interface)
• Cocok untuk testing & development

🖥 <b>Dedicated RDP</b> - 1 kuota
• Windows langsung di VPS (15-30 menit)
• Performa optimal
• Port 22 (custom untuk keamanan)
• Cocok untuk production use"""

WINDOWS_MENU_TEXT = """🖥 <b>Silahkan Pilih Versi Windows Anda</b> 🖥

1 Windows Server 2012 R2
2 Windows Server 2016
3 Windows Server 2019
4 Windows Server 2022
5 Windows Server 2025
6 Windows 10 SuperLite
7 Windows 11 SuperLite
8 Windows 10 Atlas
9 Windows 11 Atlas
10 Windows 10 Pro
11 Windows 11 Pro
12 Tiny10 23H2
13 Tiny11 23H2

Silahkan klik tombol OS di bawah 👇"""

def build_rdp_type_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🐳 Docker RDP (1 kuota)", callback_data="rdp_type_docker"))
    markup.add(types.InlineKeyboardButton("🖥 Dedicated RDP (1 kuota)", callback_data="rdp_type_dedicated"))
    markup.add(types.InlineKeyboardButton("🏠 Kembali ke Menu", callback_data="back_main"))
    return markup

def build_windows_menu_markup():
    markup = types.InlineKeyboardMarkup(row_width=3)

    row1 = [types.InlineKeyboardButton(str(i), callback_data=f"win_{i}") for i in range(1, 4)]
    row2 = [types.InlineKeyboardButton(str(i), callback_data=f"win_{i}") for i in range(4, 7)]
    row3 = [types.InlineKeyboardButton(str(i), callback_data=f"win_{i}") for i in range(7, 10)]
    row4 = [types.InlineKeyboardButton(str(i), callback_data=f"win_{i}") for i in range(10, 13)]

    markup.row(*row1)
    markup.row(*row2)
    markup.row(*row3)
    markup.row(*row4)
    markup.add(types.InlineKeyboardButton("13", callback_data="win_13"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="install_rdp"))

    return markup

# ==================== CEK AKSES ====================
def is_allowed(user_id):
    return user_id in data["allowed_users"] or user_id == OWNER_ID

def is_owner(user_id):
    return user_id == OWNER_ID

# ==================== HANDLER /start ====================
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id

    if not is_allowed(user_id):
        bot.reply_to(message, "⛔ Akses ditolak!\nHubungi owner untuk mendapatkan akses.")
        return

    user_name = message.from_user.first_name or "User"

    text = f"""🚀 <b>RDP INSTALLER BOT</b>
━━━━━━━━━━━━━━━━━━

📊 <b>PROFILE ANDA</b>
<b>ID PROFILE</b> : <code>{user_id}</code>
<b>NAMA</b> : {user_name}

📊 <b>INFORMASI INSTALL</b>
<b>PROVIDER</b> : DigitalOcean / Vultr
<b>RAM/SPEK</b> : Minimal 2GB
<b>OS</b> : Ubuntu 22/20 - Debian 11/12
━━━━━━━━━━━━━━━━━━"""

    markup = types.InlineKeyboardMarkup(row_width=2)

    btn_install = types.InlineKeyboardButton("🖥 Install RDP", callback_data="install_rdp")
    btn_owner = types.InlineKeyboardButton("💬 Owner ↗", url=data["owner_link"])
    btn_channel = types.InlineKeyboardButton("📢 Channel ↗", url=data["channel_link"])

    markup.add(btn_install)
    markup.add(btn_owner, btn_channel)

    # Tombol khusus owner
    if is_owner(user_id):
        btn_settings = types.InlineKeyboardButton("⚙️ Settings Owner", callback_data="owner_settings")
        markup.add(btn_settings)

    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

# ==================== INSTALL RDP MENU ====================
@bot.callback_query_handler(func=lambda call: call.data == "install_rdp")
def install_rdp_menu(call):
    if not is_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Akses ditolak!")
        return

    text = RDP_TYPE_MENU_TEXT
    markup = build_rdp_type_markup()

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== PILIH TIPE RDP ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("rdp_type_"))
def select_rdp_type(call):
    if not is_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Akses ditolak!")
        return

    rdp_type = call.data.replace("rdp_type_", "")
    USER_SELECTED_TYPE[call.from_user.id] = rdp_type

    type_name = RDP_TYPES[rdp_type]["name"]
    bot.answer_callback_query(call.id, f"✅ Dipilih: {type_name}")

    text = WINDOWS_MENU_TEXT
    markup = build_windows_menu_markup()

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== PILIH WINDOWS ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("win_"))
def select_windows(call):
    if not is_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Akses ditolak!")
        return

    win_num = call.data.replace("win_", "")
    win_name = WINDOWS_OPTIONS.get(win_num, "Unknown")

    # Ambil tipe RDP yang dipilih
    rdp_type = USER_SELECTED_TYPE.get(call.from_user.id, "docker")
    type_name = RDP_TYPES[rdp_type]["name"]

    # Simpan pilihan OS user untuk dipakai saat /install
    USER_SELECTED_OS[call.from_user.id] = {"code": win_num, "name": win_name}

    text = f"""✅ <b>Pilihan Anda:</b>

📦 <b>Tipe:</b> {type_name}
🪟 <b>Windows:</b> {win_name} (<code>{win_num}</code>)

Sekarang kirim IP dan Password VPS dengan format:
<code>/install IP PASSWORD</code>

Contoh: <code>/install 167.71.123.45 password123</code>"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="install_rdp"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    bot.answer_callback_query(call.id, f"✅ Dipilih: {win_name}")

# ==================== BACK TO MAIN ====================
@bot.callback_query_handler(func=lambda call: call.data == "back_main")
def back_to_main(call):
    try:
        # Recreate start message
        user_id = call.from_user.id
        user_name = call.from_user.first_name or "User"

        text = f"""🚀 <b>RDP INSTALLER BOT</b>
━━━━━━━━━━━━━━━━━━

📊 <b>PROFILE ANDA</b>
<b>ID PROFILE</b> : <code>{user_id}</code>
<b>NAMA</b> : {user_name}

📊 <b>INFORMASI INSTALL</b>
<b>PROVIDER</b> : DigitalOcean / Vultr
<b>RAM/SPEK</b> : Minimal 2GB
<b>OS</b> : Ubuntu 22/20 - Debian 11/12
━━━━━━━━━━━━━━━━━━"""

        markup = types.InlineKeyboardMarkup(row_width=2)

        btn_install = types.InlineKeyboardButton("🖥 Install RDP", callback_data="install_rdp")
        btn_owner = types.InlineKeyboardButton("💬 Owner ↗", url=data["owner_link"])
        btn_channel = types.InlineKeyboardButton("📢 Channel ↗", url=data["channel_link"])

        markup.add(btn_install)
        markup.add(btn_owner, btn_channel)

        if is_owner(user_id):
            btn_settings = types.InlineKeyboardButton("⚙️ Settings Owner", callback_data="owner_settings")
            markup.add(btn_settings)

        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    except Exception as e:
        print(f"Error back_to_main: {e}")
        bot.answer_callback_query(call.id, "Silakan ketik /start lagi")

# ==================== OWNER SETTINGS ====================
@bot.callback_query_handler(func=lambda call: call.data == "owner_settings")
def owner_settings(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    user_count = len(data["allowed_users"])

    # Tumbal VPS status
    tumbal_list = data.get("tumbal_list", [])
    tumbal_count = len(tumbal_list)
    active_tumbal = get_active_tumbal()
    active_info = f"✅ {active_tumbal['name']} ({active_tumbal['ip']})" if active_tumbal else "❌ Belum dipilih"

    text = f"""⚙️ <b>OWNER SETTINGS</b>
━━━━━━━━━━━━━━━━━━

👥 <b>Total User:</b> {user_count}
🔗 <b>Owner Link:</b> {data["owner_link"]}
📢 <b>Channel Link:</b> {data["channel_link"]}
🖥 <b>Tumbal VPS:</b> {tumbal_count} VPS terdaftar
📍 <b>Aktif:</b> {active_info}

<b>Commands:</b>
/adduser [id] - Tambah user
/deluser [id] - Hapus user
/setowner [link] - Set link owner
/setchannel [link] - Set link channel
/settoken [token] - Ganti bot token
/setownerid [id] - Ganti owner ID
/listuser - Lihat daftar user"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🖥 Tumbal VPS Manager", callback_data="tumbal_menu"))
    markup.add(types.InlineKeyboardButton("☁️ Google Drive Manager", callback_data="gdrive_menu"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="back_main"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== ADD USER ====================
@bot.message_handler(commands=['adduser'])
def add_user(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner yang bisa menambah user!")
        return

    try:
        user_id = int(message.text.split()[1])
        if user_id not in data["allowed_users"]:
            data["allowed_users"].append(user_id)
            save_data(data)
            bot.reply_to(message, f"✅ User <code>{user_id}</code> berhasil ditambahkan!", parse_mode="HTML")
        else:
            bot.reply_to(message, "⚠️ User sudah ada dalam daftar!")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Format: /adduser [telegram_id]\nContoh: /adduser 123456789")

# ==================== DELETE USER ====================
@bot.message_handler(commands=['deluser'])
def del_user(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner yang bisa menghapus user!")
        return

    try:
        user_id = int(message.text.split()[1])
        if user_id == OWNER_ID:
            bot.reply_to(message, "⚠️ Tidak bisa menghapus owner!")
            return
        if user_id in data["allowed_users"]:
            data["allowed_users"].remove(user_id)
            save_data(data)
            bot.reply_to(message, f"✅ User <code>{user_id}</code> berhasil dihapus!", parse_mode="HTML")
        else:
            bot.reply_to(message, "⚠️ User tidak ditemukan!")
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Format: /deluser [telegram_id]")

# ==================== SET OWNER LINK ====================
@bot.message_handler(commands=['setowner'])
def set_owner_link(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        link = message.text.split(maxsplit=1)[1]
        data["owner_link"] = link
        save_data(data)
        bot.reply_to(message, f"✅ Owner link diubah ke:\n{link}")
    except IndexError:
        bot.reply_to(message, "❌ Format: /setowner [link]\nContoh: /setowner https://t.me/username")

# ==================== SET CHANNEL LINK ====================
@bot.message_handler(commands=['setchannel'])
def set_channel_link(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        link = message.text.split(maxsplit=1)[1]
        data["channel_link"] = link
        save_data(data)
        bot.reply_to(message, f"✅ Channel link diubah ke:\n{link}")
    except IndexError:
        bot.reply_to(message, "❌ Format: /setchannel [link]")

# ==================== SET BOT TOKEN ====================
@bot.message_handler(commands=['settoken'])
def set_bot_token(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        new_token = message.text.split(maxsplit=1)[1].strip()
        if ":" not in new_token:
            bot.reply_to(message, "❌ Token tidak valid (harus ada tanda ':'). Contoh: /settoken 123456:ABC-xyz")
            return

        owner_env = int(os.getenv("OWNER_ID") or OWNER_ID)
        env_path = write_env(new_token, owner_env)

        bot.reply_to(
            message,
            f"""✅ <b>BOT_TOKEN tersimpan!</b>

🔑 Token baru: <code>{new_token[:10]}...{new_token[-5:]}</code>
📄 File: <code>{env_path}</code>

⚠️ <b>PENTING:</b> Restart bot untuk menerapkan perubahan!
<code>systemctl restart rdpbot</code>""",
            parse_mode="HTML",
        )
    except IndexError:
        bot.reply_to(message, "❌ Format: /settoken [token_baru]\nContoh: /settoken 123456:ABC-xyz")



# ==================== SET OWNER ID ====================
@bot.message_handler(commands=['setownerid'])
def set_owner_id(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        new_owner = int(message.text.split()[1])

        # Update allowed_users
        if new_owner not in data["allowed_users"]:
            data["allowed_users"].append(new_owner)
            save_data(data)

        token_env = os.getenv("BOT_TOKEN") or BOT_TOKEN
        env_path = write_env(token_env, new_owner)

        bot.reply_to(
            message,
            f"""✅ <b>OWNER_ID tersimpan!</b>

👤 Owner baru: <code>{new_owner}</code>
📄 File: <code>{env_path}</code>

⚠️ <b>PENTING:</b> Restart bot untuk menerapkan perubahan!
<code>systemctl restart rdpbot</code>""",
            parse_mode="HTML",
        )
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Format: /setownerid [telegram_id]\nContoh: /setownerid 123456789")



# ==================== LIST USER ====================
@bot.message_handler(commands=['listuser'])
def list_users(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    user_list = "\n".join([f"• <code>{uid}</code>" for uid in data["allowed_users"]])
    text = f"👥 <b>Daftar User ({len(data['allowed_users'])}):</b>\n\n{user_list}"
    bot.reply_to(message, text, parse_mode="HTML")

# ==================== INSTALL COMMAND /install ====================
@bot.message_handler(commands=['install'])
def install_command(message):
    if not is_allowed(message.from_user.id):
        bot.reply_to(message, "⛔ Akses ditolak!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 3:
            raise ValueError

        ip = parts[1]
        password = parts[2]

        # WIN_CODE bisa diambil dari argumen ke-3 atau dari pilihan terakhir user
        win_code = parts[3] if len(parts) >= 4 else None
        if not win_code:
            saved = USER_SELECTED_OS.get(message.from_user.id)
            win_code = saved.get("code") if saved else None

        if not win_code or win_code not in WINDOWS_OPTIONS:
            bot.reply_to(
                message,
                "❗ Kamu belum memilih OS. Pilih OS dulu di bawah ini, lalu ulangi: <code>/install IP PASSWORD</code>",
                parse_mode="HTML",
            )
            bot.send_message(
                message.chat.id,
                RDP_TYPE_MENU_TEXT,
                parse_mode="HTML",
                reply_markup=build_rdp_type_markup(),
            )
            return

        # Ambil tipe RDP yang dipilih
        rdp_type = USER_SELECTED_TYPE.get(message.from_user.id, "docker")
        type_name = RDP_TYPES[rdp_type]["name"]
        win_name = WINDOWS_OPTIONS[win_code]

        # Kirim pesan awal
        bot.reply_to(
            message,
            f"""🔌 <b>Menghubungkan ke VPS...</b>

📦 <b>Tipe:</b> {type_name}
📍 <b>IP:</b> <code>{ip}</code>
🪟 <b>Windows:</b> {win_name} ({win_code})""",
            parse_mode="HTML"
        )

        # Jalankan script instalasi berdasarkan tipe
        script_dir = os.path.dirname(os.path.abspath(__file__))

        if rdp_type == "docker":
            script_path = os.path.join(script_dir, "rdp_docker.sh")
        else:
            script_path = os.path.join(script_dir, "rdp_dedicated.sh")

        if not os.path.exists(script_path):
            bot.reply_to(message, f"❌ File {os.path.basename(script_path)} tidak ditemukan. Pastikan sudah git pull.")
            return

        subprocess.run(["chmod", "+x", script_path], check=False)

        chat_id = str(message.chat.id)

        # Fungsi untuk jalankan instalasi di background
        def run_install():
            try:
                log_path = os.path.join(script_dir, "rdp_install.log")

                result = subprocess.run(
                    ["bash", script_path, ip, password, win_code, chat_id, BOT_TOKEN],
                    capture_output=True,
                    text=True,
                    timeout=2400  # 40 menit timeout
                )

                output = result.stdout + result.stderr
                exit_code = result.returncode

                # Simpan log
                with open(log_path, "a") as log:
                    log.write(f"\n{'='*50}\n")
                    log.write(f"User: {message.from_user.id} | IP: {ip} | OS: {win_code} | Type: {rdp_type}\n")
                    log.write(output)
                    log.write(f"\nExit code: {exit_code}\n")

            except subprocess.TimeoutExpired:
                bot.send_message(
                    message.chat.id,
                    f"""⏰ <b>TIMEOUT!</b>
━━━━━━━━━━━━━━━━━━

📍 <b>IP:</b> <code>{ip}</code>
🪟 <b>Windows:</b> {win_name}

Proses melebihi batas waktu.
Kemungkinan instalasi masih berjalan di VPS.

Coba cek VPS secara manual.""",
                    parse_mode="HTML"
                )
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"""⚠️ <b>ERROR!</b>
━━━━━━━━━━━━━━━━━━

Terjadi error: <code>{str(e)}</code>

Silakan coba lagi.""",
                    parse_mode="HTML"
                )

        # Jalankan di background thread
        install_thread = threading.Thread(target=run_install, daemon=True)
        install_thread.start()

        # Kirim konfirmasi
        bot.send_message(
            message.chat.id,
            f"""🚀 <b>Proses Instalasi Dimulai!</b>
━━━━━━━━━━━━━━━━━━

📦 <b>Tipe:</b> {type_name}
📍 <b>IP:</b> <code>{ip}</code>
🪟 <b>Windows:</b> {win_name}

⏳ Instalasi berjalan di background.
Kamu akan menerima notifikasi saat selesai.

<b>Estimasi waktu:</b>
• Docker RDP: 10-15 menit
• Dedicated RDP: 15-30 menit

💡 Kamu bisa menutup chat ini, notifikasi akan dikirim otomatis.""",
            parse_mode="HTML"
        )

    except Exception:
        bot.reply_to(message, "❌ Format: /install [IP] [PASSWORD]\nContoh: /install 167.71.123.45 password123")

# ==================== TUMBAL VPS MENU ====================
@bot.callback_query_handler(func=lambda call: call.data == "tumbal_menu")
def tumbal_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal_list = data.get("tumbal_list", [])
    active_tumbal = get_active_tumbal()

    # Build VPS list text
    if tumbal_list:
        vps_list_text = ""
        for i, t in enumerate(tumbal_list, 1):
            status = "🟢" if t["id"] == data.get("active_tumbal") else "⚪"
            vps_list_text += f"{status} <b>{t['name']}</b> - <code>{t['ip']}</code>\n"
    else:
        vps_list_text = "Belum ada VPS tumbal terdaftar.\n"

    text = f"""🖥 <b>TUMBAL VPS MANAGER</b>
━━━━━━━━━━━━━━━━━━

<b>VPS Terdaftar:</b> {len(tumbal_list)}
<b>Aktif:</b> {active_tumbal['name'] if active_tumbal else 'Belum dipilih'}

{vps_list_text}
<b>Apa itu Tumbal VPS?</b>
VPS 8GB RAM khusus untuk build Windows image.
Bisa pakai banyak VPS untuk paralel build.

<b>Commands:</b>
<code>/addtumbal [nama] [ip] [password]</code> - Tambah VPS
<code>/deltumbal [id]</code> - Hapus VPS
<code>/listtumbal</code> - Lihat semua VPS"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Tambah Tumbal VPS", callback_data="tumbal_add"))
    markup.add(types.InlineKeyboardButton("📋 List & Pilih VPS", callback_data="tumbal_select"))
    markup.add(types.InlineKeyboardButton("🔌 Test Koneksi", callback_data="tumbal_test"))
    markup.add(types.InlineKeyboardButton("🏗 Build Image", callback_data="tumbal_build"))
    markup.add(types.InlineKeyboardButton("📋 List Local Images", callback_data="tumbal_list"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="owner_settings"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== ADD TUMBAL VPS ====================
@bot.callback_query_handler(func=lambda call: call.data == "tumbal_add")
def tumbal_add_info(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    text = """➕ <b>TAMBAH TUMBAL VPS</b>
━━━━━━━━━━━━━━━━━━

Gunakan command:
<code>/addtumbal [NAMA] [IP] [PASSWORD]</code>

Contoh:
<code>/addtumbal Hetzner1 167.71.123.45 mypass123</code>
<code>/addtumbal Contabo1 45.76.89.12 secret456</code>

<b>Syarat VPS Tumbal:</b>
• RAM minimal 8GB
• Storage minimal 50GB
• OS: Ubuntu 22.04 / Debian 12
• Akses root via SSH

<b>Tips Provider:</b>
• Hetzner, OVH, Contabo - toleran high CPU
• DigitalOcean, Vultr - ok tapi monitor CPU"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="tumbal_menu"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['addtumbal'])
def add_tumbal(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 4:
            bot.reply_to(message, "❌ Format: /addtumbal [NAMA] [IP] [PASSWORD]\nContoh: /addtumbal Hetzner1 167.71.123.45 mypass123")
            return

        name = parts[1]
        ip = parts[2]
        password = parts[3]

        # Generate unique ID
        tumbal_list = data.get("tumbal_list", [])
        tumbal_id = f"tumbal{len(tumbal_list) + 1}_{ip.replace('.', '_')}"

        # Check if IP already exists
        for t in tumbal_list:
            if t["ip"] == ip:
                bot.reply_to(message, f"⚠️ VPS dengan IP <code>{ip}</code> sudah terdaftar!", parse_mode="HTML")
                return

        new_tumbal = {
            "id": tumbal_id,
            "name": name,
            "ip": ip,
            "password": password,
            "enabled": True
        }

        tumbal_list.append(new_tumbal)
        data["tumbal_list"] = tumbal_list

        # Auto-set as active if this is the first one
        if len(tumbal_list) == 1:
            data["active_tumbal"] = tumbal_id

        save_data(data)

        bot.reply_to(message, f"""✅ <b>Tumbal VPS berhasil ditambahkan!</b>

📛 <b>Nama:</b> {name}
📍 <b>IP:</b> <code>{ip}</code>
🔑 <b>ID:</b> <code>{tumbal_id}</code>

Total VPS: {len(tumbal_list)}
Gunakan /testtumbal untuk test koneksi SSH.""", parse_mode="HTML")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== SELECT TUMBAL VPS ====================
@bot.callback_query_handler(func=lambda call: call.data == "tumbal_select")
def tumbal_select_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal_list = data.get("tumbal_list", [])

    if not tumbal_list:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS tumbal!")
        return

    text = """📋 <b>PILIH TUMBAL VPS AKTIF</b>
━━━━━━━━━━━━━━━━━━

Pilih VPS yang akan digunakan untuk build image.
🟢 = Aktif sekarang"""

    markup = types.InlineKeyboardMarkup()
    for t in tumbal_list:
        status = "🟢" if t["id"] == data.get("active_tumbal") else "⚪"
        btn_text = f"{status} {t['name']} ({t['ip']})"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"select_tumbal_{t['id']}"))

    markup.add(types.InlineKeyboardButton("🗑 Hapus VPS", callback_data="tumbal_delete_menu"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="tumbal_menu"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("select_tumbal_"))
def select_tumbal(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal_id = call.data.replace("select_tumbal_", "")
    tumbal = get_tumbal_by_id(tumbal_id)

    if not tumbal:
        bot.answer_callback_query(call.id, "❌ VPS tidak ditemukan!")
        return

    data["active_tumbal"] = tumbal_id
    save_data(data)

    bot.answer_callback_query(call.id, f"✅ {tumbal['name']} dipilih sebagai VPS aktif!")

    # Refresh menu
    tumbal_select_menu(call)

# ==================== DELETE TUMBAL VPS ====================
@bot.callback_query_handler(func=lambda call: call.data == "tumbal_delete_menu")
def tumbal_delete_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal_list = data.get("tumbal_list", [])

    if not tumbal_list:
        bot.answer_callback_query(call.id, "❌ Tidak ada VPS untuk dihapus!")
        return

    text = """🗑 <b>HAPUS TUMBAL VPS</b>
━━━━━━━━━━━━━━━━━━

Pilih VPS yang akan dihapus:"""

    markup = types.InlineKeyboardMarkup()
    for t in tumbal_list:
        btn_text = f"❌ {t['name']} ({t['ip']})"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"del_tumbal_{t['id']}"))

    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="tumbal_select"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_tumbal_"))
def delete_tumbal_btn(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal_id = call.data.replace("del_tumbal_", "")
    tumbal_list = data.get("tumbal_list", [])

    # Find and remove
    new_list = [t for t in tumbal_list if t["id"] != tumbal_id]

    if len(new_list) == len(tumbal_list):
        bot.answer_callback_query(call.id, "❌ VPS tidak ditemukan!")
        return

    data["tumbal_list"] = new_list

    # Reset active if deleted
    if data.get("active_tumbal") == tumbal_id:
        data["active_tumbal"] = new_list[0]["id"] if new_list else ""

    save_data(data)

    bot.answer_callback_query(call.id, "✅ VPS berhasil dihapus!")

    # Go back to menu
    if new_list:
        tumbal_delete_menu(call)
    else:
        tumbal_menu(call)

@bot.message_handler(commands=['deltumbal'])
def del_tumbal_cmd(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            # Show list
            tumbal_list = data.get("tumbal_list", [])
            if not tumbal_list:
                bot.reply_to(message, "❌ Tidak ada VPS tumbal terdaftar!")
                return

            text = "📋 <b>Daftar ID VPS Tumbal:</b>\n\n"
            for t in tumbal_list:
                text += f"• <code>{t['id']}</code> - {t['name']} ({t['ip']})\n"
            text += "\nGunakan: /deltumbal [ID]"
            bot.reply_to(message, text, parse_mode="HTML")
            return

        tumbal_id = parts[1]
        tumbal_list = data.get("tumbal_list", [])

        # Find and remove
        new_list = [t for t in tumbal_list if t["id"] != tumbal_id]

        if len(new_list) == len(tumbal_list):
            bot.reply_to(message, "❌ ID tidak ditemukan!")
            return

        data["tumbal_list"] = new_list

        # Reset active if deleted
        if data.get("active_tumbal") == tumbal_id:
            data["active_tumbal"] = new_list[0]["id"] if new_list else ""

        save_data(data)
        bot.reply_to(message, f"✅ VPS <code>{tumbal_id}</code> berhasil dihapus!", parse_mode="HTML")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['listtumbal'])
def list_tumbal(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    tumbal_list = data.get("tumbal_list", [])

    if not tumbal_list:
        bot.reply_to(message, "❌ Belum ada VPS tumbal terdaftar!\nGunakan /addtumbal [NAMA] [IP] [PASSWORD]")
        return

    text = f"🖥 <b>DAFTAR TUMBAL VPS ({len(tumbal_list)})</b>\n━━━━━━━━━━━━━━━━━━\n\n"

    for t in tumbal_list:
        status = "🟢 AKTIF" if t["id"] == data.get("active_tumbal") else "⚪"
        text += f"{status}\n"
        text += f"📛 <b>Nama:</b> {t['name']}\n"
        text += f"📍 <b>IP:</b> <code>{t['ip']}</code>\n"
        text += f"🔑 <b>ID:</b> <code>{t['id']}</code>\n\n"

    bot.reply_to(message, text, parse_mode="HTML")

# ==================== UPDATE TUMBAL VPS ====================
@bot.message_handler(commands=['updatetumbal'])
def update_tumbal_cmd(message):
    """Update existing tumbal VPS - /updatetumbal [ID] [field] [value]"""
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 4:
            # Show usage
            tumbal_list = data.get("tumbal_list", [])

            if not tumbal_list:
                bot.reply_to(message, "❌ Belum ada tumbal VPS terdaftar.")
                return

            text = "📝 <b>UPDATE TUMBAL VPS</b>\n━━━━━━━━━━━━━━━━━━\n\n"
            text += "Format: <code>/updatetumbal [ID] [field] [value]</code>\n\n"
            text += "<b>Fields yang bisa diupdate:</b>\n"
            text += "• <code>name</code> - Nama VPS\n"
            text += "• <code>ip</code> - IP Address\n"
            text += "• <code>password</code> - Password\n\n"
            text += "<b>Contoh:</b>\n"
            text += "<code>/updatetumbal abc123 name VPS-Baru</code>\n"
            text += "<code>/updatetumbal abc123 ip 192.168.1.100</code>\n"
            text += "<code>/updatetumbal abc123 password newpass123</code>\n\n"
            text += "<b>VPS Terdaftar:</b>\n"
            for vps in tumbal_list:
                active = "🟢" if vps.get("id") == data.get("active_tumbal") else "⚪"
                text += f"{active} <code>{vps['id']}</code> - {vps['name']}\n"
            bot.reply_to(message, text, parse_mode="HTML")
            return

        tumbal_id = parts[1]
        field = parts[2].lower()
        value = parts[3]

        valid_fields = ["name", "ip", "password"]
        if field not in valid_fields:
            bot.reply_to(message, f"❌ Field tidak valid!\nGunakan: {', '.join(valid_fields)}")
            return

        tumbal_list = data.get("tumbal_list", [])

        # Find and update VPS
        found = False
        old_value = ""
        for vps in tumbal_list:
            if vps.get("id") == tumbal_id:
                old_value = vps.get(field, "N/A")
                vps[field] = value
                found = True
                break

        if not found:
            bot.reply_to(message, f"❌ Tumbal VPS dengan ID <code>{tumbal_id}</code> tidak ditemukan.", parse_mode="HTML")
            return

        data["tumbal_list"] = tumbal_list
        save_data(data)

        # Mask password in response
        display_value = value if field != "password" else "********"
        display_old = old_value if field != "password" else "********"

        bot.reply_to(message, f"""✅ <b>Tumbal VPS Updated!</b>

🔑 <b>ID:</b> <code>{tumbal_id}</code>
📝 <b>Field:</b> <code>{field}</code>
📤 <b>Lama:</b> <code>{display_old}</code>
📥 <b>Baru:</b> <code>{display_value}</code>""", parse_mode="HTML")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['settumbal'])
def set_tumbal_legacy(message):
    """Legacy command - redirect to addtumbal"""
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    bot.reply_to(message, """⚠️ Command /settumbal sudah diganti!

Gunakan:
<code>/addtumbal [NAMA] [IP] [PASSWORD]</code>

Contoh:
<code>/addtumbal Hetzner1 167.71.123.45 mypass123</code>""", parse_mode="HTML")

# ==================== TEST TUMBAL ====================
@bot.callback_query_handler(func=lambda call: call.data == "tumbal_test")
def tumbal_test_btn(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS aktif! Tambah VPS dulu.")
        return

    bot.answer_callback_query(call.id, f"⏳ Testing {tumbal['name']}...")

    def test_ssh():
        try:
            ip = tumbal["ip"]
            password = tumbal["password"]
            name = tumbal["name"]

            result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=10", f"root@{ip}", "echo 'OK' && free -h && df -h /"],
                capture_output=True, text=True, timeout=30
            )

            if "OK" in result.stdout:
                bot.send_message(call.message.chat.id, f"""✅ <b>Koneksi SSH Berhasil!</b>

📛 <b>Nama:</b> {name}
📍 <b>IP:</b> <code>{ip}</code>

<b>System Info:</b>
<code>{result.stdout}</code>""", parse_mode="HTML")
            else:
                bot.send_message(call.message.chat.id, f"❌ Koneksi ke {name} gagal:\n<code>{result.stderr[:500]}</code>", parse_mode="HTML")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=test_ssh, daemon=True).start()

@bot.message_handler(commands=['testtumbal'])
def test_tumbal_cmd(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.reply_to(message, "❌ Belum ada VPS tumbal aktif!\nGunakan /addtumbal [NAMA] [IP] [PASSWORD]")
        return

    bot.reply_to(message, f"⏳ Testing koneksi ke {tumbal['name']}...")

    def test_ssh():
        try:
            ip = tumbal["ip"]
            password = tumbal["password"]
            name = tumbal["name"]

            result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=10", f"root@{ip}", "echo 'OK' && free -h && df -h /"],
                capture_output=True, text=True, timeout=30
            )

            if "OK" in result.stdout:
                bot.send_message(message.chat.id, f"""✅ <b>Koneksi SSH Berhasil!</b>

📛 <b>Nama:</b> {name}
📍 <b>IP:</b> <code>{ip}</code>

<b>System Info:</b>
<code>{result.stdout}</code>""", parse_mode="HTML")
            else:
                bot.send_message(message.chat.id, f"❌ Koneksi gagal:\n<code>{result.stderr[:500]}</code>", parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=test_ssh, daemon=True).start()

# ==================== BUILD IMAGE ====================
@bot.callback_query_handler(func=lambda call: call.data == "tumbal_build")
def tumbal_build_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS aktif! Tambah VPS dulu.")
        return

    text = f"""🏗 <b>BUILD WINDOWS IMAGE</b>
━━━━━━━━━━━━━━━━━━

<b>VPS Aktif:</b> {tumbal['name']} ({tumbal['ip']})

Proses ini akan:
1. SSH ke Tumbal VPS
2. Download ISO Windows
3. Install & konfigurasi Windows
4. Compress menjadi .img.gz
5. Upload ke Google Drive (jika dikonfigurasi)

<b>Command:</b>
<code>/buildimage [kode_windows]</code>

<b>Kode Windows:</b>
1 - Windows Server 2012 R2
2 - Windows Server 2016
3 - Windows Server 2019
4 - Windows Server 2022
5 - Windows Server 2025
6 - Windows 10 SuperLite
7 - Windows 11 SuperLite
8 - Windows 10 Atlas
9 - Windows 11 Atlas
10 - Windows 10 Pro
11 - Windows 11 Pro

Contoh: <code>/buildimage 8</code>"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔨 Build Win10 Atlas", callback_data="build_8"))
    markup.add(types.InlineKeyboardButton("🔨 Build Win11 Atlas", callback_data="build_9"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="tumbal_menu"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("build_"))
def build_quick(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    win_code = call.data.replace("build_", "")
    win_name = WINDOWS_OPTIONS.get(win_code, "Unknown")

    bot.answer_callback_query(call.id, f"⏳ Memulai build {win_name}...")
    start_build_image(call.message.chat.id, win_code)

@bot.message_handler(commands=['buildimage'])
def build_image_cmd(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Format: /buildimage [kode_windows]\nContoh: /buildimage 8")
            return

        win_code = parts[1]
        if win_code not in WINDOWS_OPTIONS:
            bot.reply_to(message, "❌ Kode Windows tidak valid! Gunakan 1-11")
            return

        start_build_image(message.chat.id, win_code)

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

def start_build_image(chat_id, win_code):
    tumbal = get_active_tumbal()
    if not tumbal:
        bot.send_message(chat_id, "❌ Belum ada VPS tumbal aktif!\nGunakan /addtumbal [NAMA] [IP] [PASSWORD]")
        return

    win_name = WINDOWS_OPTIONS.get(win_code, "Unknown")
    ip = tumbal["ip"]
    password = tumbal["password"]
    name = tumbal["name"]

    bot.send_message(chat_id, f"""🏗 <b>Memulai Build Image</b>
━━━━━━━━━━━━━━━━━━

🪟 <b>Windows:</b> {win_name}
📍 <b>Tumbal VPS:</b> {name} (<code>{ip}</code>)

⏳ Menghubungkan ke VPS...
Proses ini bisa memakan waktu 30-60 menit.""", parse_mode="HTML")

    def do_build():
        try:
            # Script build akan dijalankan di tumbal VPS
            build_script = f'''
#!/bin/bash
cd /tmp

# Update system
apt update -y
apt install -y wget curl qemu-utils gzip

# Buat folder untuk images
mkdir -p /root/rdp-images

echo "🔽 Downloading Windows image builder..."
# Di sini bisa ditambahkan script untuk download dan build Windows image
# Untuk sekarang, kita buat placeholder

echo "📦 Windows code: {win_code}"
echo "📁 Output akan disimpan di /root/rdp-images/"

# Placeholder - ganti dengan script build yang sebenarnya
echo "BUILD_COMPLETE"
'''

            result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 f"root@{ip}", build_script],
                capture_output=True, text=True, timeout=7200  # 2 jam timeout
            )

            if "BUILD_COMPLETE" in result.stdout:
                bot.send_message(chat_id, f"""✅ <b>Build Selesai!</b>

🪟 <b>Windows:</b> {win_name}
📍 <b>VPS:</b> {name}
📁 <b>Lokasi:</b> /root/rdp-images/

Gunakan menu Google Drive untuk upload ke cloud.""", parse_mode="HTML")
            else:
                bot.send_message(chat_id, f"""❌ <b>Build Gagal!</b>

<code>{result.stderr[:500]}</code>""", parse_mode="HTML")

        except subprocess.TimeoutExpired:
            bot.send_message(chat_id, "⏰ Build timeout (>2 jam)")
        except Exception as e:
            bot.send_message(chat_id, f"❌ Error: {str(e)}")

    threading.Thread(target=do_build, daemon=True).start()

# ==================== LIST LOCAL IMAGES ====================
@bot.callback_query_handler(func=lambda call: call.data == "tumbal_list")
def tumbal_list_images(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS aktif! Tambah VPS dulu.")
        return

    bot.answer_callback_query(call.id, f"⏳ Mengambil images dari {tumbal['name']}...")

    def list_images():
        try:
            ip = tumbal["ip"]
            password = tumbal["password"]
            name = tumbal["name"]

            result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 f"root@{ip}", "ls -lh /root/rdp-images/ 2>/dev/null || echo 'EMPTY'"],
                capture_output=True, text=True, timeout=30
            )

            if "EMPTY" in result.stdout or not result.stdout.strip():
                text = f"""📋 <b>LOCAL IMAGES DI {name.upper()}</b>
━━━━━━━━━━━━━━━━━━

📍 IP: <code>{ip}</code>

Folder kosong. Belum ada image yang dibuild."""
            else:
                text = f"""📋 <b>LOCAL IMAGES DI {name.upper()}</b>
━━━━━━━━━━━━━━━━━━

📍 IP: <code>{ip}</code>

<code>{result.stdout}</code>"""

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="tumbal_list"))
            markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="tumbal_menu"))

            bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=list_images, daemon=True).start()

# ==================== GOOGLE DRIVE MENU ====================
@bot.callback_query_handler(func=lambda call: call.data == "gdrive_menu")
def gdrive_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    # Cek apakah rclone sudah terinstall
    rclone_status = "✅ Terinstall" if os.path.exists("/usr/bin/rclone") else "❌ Belum terinstall"

    # Cek apakah gdrive sudah dikonfigurasi
    gdrive_configured = os.path.exists(os.path.expanduser("~/.config/rclone/rclone.conf"))
    gdrive_status = "✅ Terkonfigurasi" if gdrive_configured else "❌ Belum dikonfigurasi"

    text = f"""☁️ <b>GOOGLE DRIVE MANAGER</b>
━━━━━━━━━━━━━━━━━━

📦 <b>Rclone:</b> {rclone_status}
🔗 <b>GDrive:</b> {gdrive_status}

<b>Pilih aksi:</b>"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔧 Setup Rclone + GDrive", callback_data="gdrive_setup"))
    markup.add(types.InlineKeyboardButton("📤 Upload Image", callback_data="gdrive_upload"))
    markup.add(types.InlineKeyboardButton("📥 Download Image", callback_data="gdrive_download"))
    markup.add(types.InlineKeyboardButton("📋 List Images", callback_data="gdrive_list"))
    markup.add(types.InlineKeyboardButton("🗑 Delete Image", callback_data="gdrive_delete"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="owner_settings"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== GDRIVE SETUP ====================
@bot.callback_query_handler(func=lambda call: call.data == "gdrive_setup")
def gdrive_setup(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    text = """🔧 <b>SETUP RCLONE + GOOGLE DRIVE</b>
━━━━━━━━━━━━━━━━━━

<b>Step 1:</b> Install rclone (otomatis)
<b>Step 2:</b> Konfigurasi Google Drive

Gunakan command:
<code>/setuprclone</code> - Install rclone otomatis
<code>/configgdrive [client_id] [client_secret]</code> - Config GDrive

<b>Cara dapat Client ID & Secret:</b>
1. Buka https://console.cloud.google.com
2. Buat project baru
3. Enable Google Drive API
4. Buat OAuth credentials
5. Salin Client ID & Secret"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔧 Auto Install Rclone", callback_data="gdrive_install_rclone"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="gdrive_menu"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== AUTO INSTALL RCLONE ====================
@bot.callback_query_handler(func=lambda call: call.data == "gdrive_install_rclone")
def gdrive_install_rclone(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    bot.answer_callback_query(call.id, "⏳ Menginstall rclone...")

    def install_rclone():
        try:
            # Install rclone
            result = subprocess.run(
                ["bash", "-c", "curl https://rclone.org/install.sh | sudo bash"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if os.path.exists("/usr/bin/rclone"):
                bot.send_message(
                    call.message.chat.id,
                    """✅ <b>Rclone berhasil diinstall!</b>

Sekarang konfigurasi Google Drive:
<code>/configgdrive [client_id] [client_secret]</code>

Atau bisa juga manual:
<code>rclone config</code>""",
                    parse_mode="HTML"
                )
            else:
                bot.send_message(
                    call.message.chat.id,
                    f"❌ Gagal install rclone:\n<code>{result.stderr[:500]}</code>",
                    parse_mode="HTML"
                )
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=install_rclone, daemon=True).start()

# ==================== CONFIG GDRIVE ====================
@bot.message_handler(commands=['configgdrive'])
def config_gdrive(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, """❌ Format: /configgdrive [client_id] [client_secret]

Contoh:
<code>/configgdrive 123456789.apps.googleusercontent.com GOCSPX-xxxxx</code>""", parse_mode="HTML")
            return

        client_id = parts[1]
        client_secret = parts[2]

        # Buat config rclone
        config_dir = os.path.expanduser("~/.config/rclone")
        os.makedirs(config_dir, exist_ok=True)

        config_content = f"""[gdrive]
type = drive
client_id = {client_id}
client_secret = {client_secret}
scope = drive
"""

        with open(os.path.join(config_dir, "rclone.conf"), "w") as f:
            f.write(config_content)

        bot.reply_to(message, """✅ <b>Konfigurasi GDrive disimpan!</b>

Sekarang authorize dengan command:
<code>/authgdrive</code>

Atau manual di VPS:
<code>rclone config reconnect gdrive:</code>""", parse_mode="HTML")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


# ==================== AUTH GDRIVE (OAuth dari Telegram) ====================
@bot.message_handler(commands=['authgdrive'])
def auth_gdrive(message):
    """Generate OAuth link untuk authorize Google Drive langsung dari Telegram"""
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    # Cek apakah rclone sudah terinstall
    if not os.path.exists("/usr/bin/rclone"):
        bot.reply_to(message, """❌ <b>Rclone belum terinstall!</b>

Jalankan dulu:
<code>/setuprclone</code>""", parse_mode="HTML")
        return

    # Cek apakah config sudah ada
    config_path = os.path.expanduser("~/.config/rclone/rclone.conf")
    if not os.path.exists(config_path):
        bot.reply_to(message, """❌ <b>GDrive belum dikonfigurasi!</b>

Jalankan dulu:
<code>/configgdrive [client_id] [client_secret]</code>""", parse_mode="HTML")
        return

    # Baca client_id dari config
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read(config_path)
        
        if 'gdrive' not in config.sections():
            bot.reply_to(message, "❌ Config gdrive tidak ditemukan. Jalankan /configgdrive dulu.")
            return
        
        client_id = config.get('gdrive', 'client_id', fallback=None)
        if not client_id:
            bot.reply_to(message, "❌ Client ID tidak ditemukan di config.")
            return

        # Generate OAuth URL langsung
        import urllib.parse
        redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
        scope = "https://www.googleapis.com/auth/drive"
        
        auth_url = (
            f"https://accounts.google.com/o/oauth2/auth"
            f"?client_id={urllib.parse.quote(client_id)}"
            f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
            f"&response_type=code"
            f"&scope={urllib.parse.quote(scope)}"
            f"&access_type=offline"
            f"&prompt=consent"
        )

        bot.reply_to(
            message,
            f"""🔗 <b>AUTHORIZE GOOGLE DRIVE</b>
━━━━━━━━━━━━━━━━━━

<b>Step 1:</b> Buka link berikut di browser:

{auth_url}

<b>Step 2:</b> Login dengan akun Google

<b>Step 3:</b> Izinkan akses, lalu copy kode verifikasi

<b>Step 4:</b> Kirim kode dengan command:
<code>/gdrivecode [kode_verifikasi]</code>

⏰ Kode berlaku beberapa menit saja""",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")


# ==================== GDRIVE CODE (Submit OAuth Code) ====================
@bot.message_handler(commands=['gdrivecode'])
def gdrive_code(message):
    """Submit kode verifikasi OAuth Google Drive dan exchange ke token"""
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, """❌ Format: /gdrivecode [kode]

Contoh:
<code>/gdrivecode 4/0AX4XfWh...</code>""", parse_mode="HTML")
            return

        auth_code = parts[1].strip()
        
        bot.reply_to(message, "⏳ Memproses kode verifikasi...")

        def process_code():
            try:
                import configparser
                import json
                
                config_path = os.path.expanduser("~/.config/rclone/rclone.conf")
                config = configparser.ConfigParser()
                config.read(config_path)
                
                client_id = config.get('gdrive', 'client_id')
                client_secret = config.get('gdrive', 'client_secret')
                
                # Exchange auth code untuk access token
                import urllib.request
                import urllib.parse
                
                token_url = "https://oauth2.googleapis.com/token"
                data = urllib.parse.urlencode({
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'code': auth_code,
                    'grant_type': 'authorization_code',
                    'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'
                }).encode()
                
                req = urllib.request.Request(token_url, data=data, method='POST')
                req.add_header('Content-Type', 'application/x-www-form-urlencoded')
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    token_data = json.loads(response.read().decode())
                
                if 'access_token' not in token_data:
                    bot.send_message(
                        message.chat.id,
                        f"❌ Gagal mendapatkan token: {token_data.get('error_description', 'Unknown error')}",
                        parse_mode="HTML"
                    )
                    return
                
                # Format token untuk rclone
                import time
                token_json = json.dumps({
                    "access_token": token_data['access_token'],
                    "token_type": "Bearer",
                    "refresh_token": token_data.get('refresh_token', ''),
                    "expiry": time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(time.time() + token_data.get('expires_in', 3600)))
                })
                
                # Update rclone config dengan token
                config.set('gdrive', 'token', token_json)
                
                with open(config_path, 'w') as f:
                    config.write(f)
                
                # Test koneksi
                test_result = subprocess.run(
                    ["rclone", "lsd", "gdrive:"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if test_result.returncode == 0:
                    bot.send_message(
                        message.chat.id,
                        """✅ <b>Google Drive berhasil terkoneksi!</b>

Sekarang kamu bisa:
• <code>/upload [file] [folder]</code> - Upload ke GDrive
• <code>/download [path] [local]</code> - Download dari GDrive
• Gunakan menu Google Drive di /start → Settings Owner""",
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(
                        message.chat.id,
                        f"""⚠️ <b>Token tersimpan tapi test gagal</b>

Error: <code>{test_result.stderr[:300] if test_result.stderr else 'Unknown'}</code>

Coba restart bot dan test lagi dengan /gdrivelist""",
                        parse_mode="HTML"
                    )

            except urllib.error.HTTPError as e:
                error_body = e.read().decode() if e.fp else str(e)
                bot.send_message(
                    message.chat.id,
                    f"""❌ <b>Gagal exchange token</b>

Pastikan kode verifikasi benar dan belum expired.

Error: <code>{error_body[:300]}</code>""",
                    parse_mode="HTML"
                )
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

        threading.Thread(target=process_code, daemon=True).start()

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== GDRIVE UPLOAD ====================
@bot.callback_query_handler(func=lambda call: call.data == "gdrive_upload")
def gdrive_upload_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    text = """📤 <b>UPLOAD KE GOOGLE DRIVE</b>
━━━━━━━━━━━━━━━━━━

Gunakan command:
<code>/upload [path_file] [folder_gdrive]</code>

Contoh:
<code>/upload /tmp/win10.img.gz rdp-images</code>
<code>/upload /home/user/image.img.gz</code>

File akan diupload ke folder 'rdp-images' di GDrive.
Jika folder tidak ada, akan dibuat otomatis."""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="gdrive_menu"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['upload'])
def upload_to_gdrive(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Format: /upload [path_file] [folder_gdrive]")
            return

        file_path = parts[1]
        folder = parts[2] if len(parts) >= 3 else "rdp-images"

        if not os.path.exists(file_path):
            bot.reply_to(message, f"❌ File tidak ditemukan: {file_path}")
            return

        file_size = os.path.getsize(file_path) / (1024 * 1024 * 1024)  # GB
        bot.reply_to(message, f"⏳ Mengupload {os.path.basename(file_path)} ({file_size:.2f} GB)...")

        def do_upload():
            try:
                result = subprocess.run(
                    ["rclone", "copy", file_path, f"gdrive:{folder}/", "-P"],
                    capture_output=True,
                    text=True,
                    timeout=7200  # 2 jam timeout
                )

                if result.returncode == 0:
                    bot.send_message(
                        message.chat.id,
                        f"""✅ <b>Upload Berhasil!</b>

📁 <b>File:</b> {os.path.basename(file_path)}
📂 <b>Folder:</b> gdrive:{folder}/
📊 <b>Size:</b> {file_size:.2f} GB""",
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(message.chat.id, f"❌ Upload gagal:\n<code>{result.stderr[:500]}</code>", parse_mode="HTML")
            except subprocess.TimeoutExpired:
                bot.send_message(message.chat.id, "⏰ Upload timeout (>2 jam)")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

        threading.Thread(target=do_upload, daemon=True).start()

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== GDRIVE DOWNLOAD ====================
@bot.callback_query_handler(func=lambda call: call.data == "gdrive_download")
def gdrive_download_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    text = """📥 <b>DOWNLOAD DARI GOOGLE DRIVE</b>
━━━━━━━━━━━━━━━━━━

Gunakan command:
<code>/download [gdrive_path] [local_path]</code>

Contoh:
<code>/download rdp-images/win10.img.gz /tmp/</code>
<code>/download rdp-images/win11.img.gz /home/user/</code>

File akan didownload dari GDrive ke VPS."""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="gdrive_menu"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['download'])
def download_from_gdrive(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Format: /download [gdrive_path] [local_path]")
            return

        gdrive_path = parts[1]
        local_path = parts[2] if len(parts) >= 3 else "/tmp/"

        bot.reply_to(message, f"⏳ Mengdownload {gdrive_path}...")

        def do_download():
            try:
                result = subprocess.run(
                    ["rclone", "copy", f"gdrive:{gdrive_path}", local_path, "-P"],
                    capture_output=True,
                    text=True,
                    timeout=7200
                )

                if result.returncode == 0:
                    bot.send_message(
                        message.chat.id,
                        f"""✅ <b>Download Berhasil!</b>

📁 <b>File:</b> {gdrive_path}
📂 <b>Lokasi:</b> {local_path}""",
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(message.chat.id, f"❌ Download gagal:\n<code>{result.stderr[:500]}</code>", parse_mode="HTML")
            except subprocess.TimeoutExpired:
                bot.send_message(message.chat.id, "⏰ Download timeout (>2 jam)")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

        threading.Thread(target=do_download, daemon=True).start()

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== GDRIVE LIST ====================
@bot.callback_query_handler(func=lambda call: call.data == "gdrive_list")
def gdrive_list_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    bot.answer_callback_query(call.id, "⏳ Mengambil daftar file...")

    def list_files():
        try:
            result = subprocess.run(
                ["rclone", "lsl", "gdrive:rdp-images/"],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0 and result.stdout.strip():
                files = result.stdout.strip().split("\n")
                file_list = []
                for f in files[:20]:  # Max 20 files
                    parts = f.split()
                    if len(parts) >= 4:
                        size = int(parts[0]) / (1024 * 1024 * 1024)  # GB
                        name = parts[-1]
                        file_list.append(f"• {name} ({size:.2f} GB)")

                text = f"""📋 <b>DAFTAR IMAGE DI GDRIVE</b>
━━━━━━━━━━━━━━━━━━

{chr(10).join(file_list) if file_list else "Tidak ada file"}

Total: {len(files)} file"""
            else:
                text = """📋 <b>DAFTAR IMAGE DI GDRIVE</b>
━━━━━━━━━━━━━━━━━━

Folder kosong atau belum dikonfigurasi.

Pastikan sudah setup GDrive dengan benar."""

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="gdrive_list"))
            markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="gdrive_menu"))

            bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=list_files, daemon=True).start()

# ==================== GDRIVE DELETE ====================
@bot.callback_query_handler(func=lambda call: call.data == "gdrive_delete")
def gdrive_delete_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    text = """🗑 <b>DELETE FILE DI GOOGLE DRIVE</b>
━━━━━━━━━━━━━━━━━━

Gunakan command:
<code>/deletegdrive [nama_file]</code>

Contoh:
<code>/deletegdrive rdp-images/win10.img.gz</code>
<code>/deletegdrive rdp-images/win11-old.img.gz</code>

⚠️ <b>HATI-HATI!</b> File yang dihapus tidak bisa dikembalikan."""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="gdrive_menu"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['deletegdrive'])
def delete_from_gdrive(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Format: /deletegdrive [path_file]")
            return

        file_path = parts[1]

        bot.reply_to(message, f"⏳ Menghapus {file_path}...")

        def do_delete():
            try:
                result = subprocess.run(
                    ["rclone", "delete", f"gdrive:{file_path}"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode == 0:
                    bot.send_message(
                        message.chat.id,
                        f"✅ <b>File berhasil dihapus:</b>\n{file_path}",
                        parse_mode="HTML"
                    )
                else:
                    bot.send_message(message.chat.id, f"❌ Gagal menghapus:\n<code>{result.stderr[:500]}</code>", parse_mode="HTML")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

        threading.Thread(target=do_delete, daemon=True).start()

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== SETUP RCLONE COMMAND ====================
@bot.message_handler(commands=['setuprclone'])
def setup_rclone_cmd(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    bot.reply_to(message, "⏳ Menginstall rclone...")

    def install():
        try:
            result = subprocess.run(
                ["bash", "-c", "curl https://rclone.org/install.sh | sudo bash"],
                capture_output=True,
                text=True,
                timeout=120
            )

            if os.path.exists("/usr/bin/rclone"):
                bot.send_message(
                    message.chat.id,
                    """✅ <b>Rclone berhasil diinstall!</b>

Sekarang konfigurasi Google Drive:
<code>/configgdrive [client_id] [client_secret]</code>""",
                    parse_mode="HTML"
                )
            else:
                bot.send_message(message.chat.id, f"❌ Gagal install:\n<code>{result.stderr[:500]}</code>", parse_mode="HTML")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=install, daemon=True).start()

# ==================== RUN BOT ====================
if __name__ == "__main__":
    print("🤖 Bot sedang berjalan...")
    bot.infinity_polling()
