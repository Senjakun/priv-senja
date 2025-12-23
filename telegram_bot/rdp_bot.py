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
    """Setelah pilih Windows:
    - Docker: langsung siap /install
    - Dedicated: tampilkan list image .img/.img.gz dari GDrive
    """
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

    # Docker tidak pakai image GDrive
    if rdp_type == "docker":
        bot.answer_callback_query(call.id, f"✅ {win_name} dipilih")

        text = f"""✅ <b>Pilihan Anda:</b>

📦 <b>Tipe:</b> {type_name}
🪟 <b>Windows:</b> {win_name}

Kirim IP dan Password VPS dengan format:
<code>/install IP PASSWORD</code>

Contoh: <code>/install 167.71.123.45 password123</code>"""

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="install_rdp"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        return

    # Dedicated: wajib GDrive
    bot.answer_callback_query(call.id, f"✅ {win_name} - Loading images...")

    rclone_conf = os.path.expanduser("~/.config/rclone/rclone.conf")
    if not os.path.exists(rclone_conf):
        text = f"""✅ <b>Pilihan Anda:</b>

📦 <b>Tipe:</b> {type_name}
🪟 <b>Windows:</b> {win_name}

❌ <b>GDrive belum dikonfigurasi!</b>

Owner perlu setup GDrive dulu di menu:
⚙️ Settings Owner → ☁️ Google Drive Manager"""

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="install_rdp"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
        return

    def list_and_show_images():
        def human_size(n: int) -> str:
            units = ["B", "KB", "MB", "GB", "TB"]
            size = float(n)
            for u in units:
                if size < 1024 or u == units[-1]:
                    if u == "B":
                        return f"{int(size)} {u}"
                    return f"{size:.1f} {u}"
                size /= 1024
            return f"{n} B"

        try:
            # Auto-create folder rdp-images jika belum ada
            subprocess.run(["rclone", "mkdir", "gdrive:rdp-images"], capture_output=True, timeout=30)

            # List file image (rekursif) agar folder tidak ke-detect sebagai file
            result = subprocess.run(
                [
                    "rclone",
                    "lsf",
                    "gdrive:rdp-images/",
                    "--recursive",
                    "--files-only",
                    "--format",
                    "sp",
                ],
                capture_output=True,
                text=True,
                timeout=45,
            )

            files: list[tuple[str, int, bool]] = []  # (path, bytes, is_golden)
            if result.returncode == 0:
                output = (result.stdout or "").strip()
                if output:
                    for line in output.split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split(";", 1)
                        if len(parts) != 2:
                            continue
                        size_str, path = parts[0].strip(), parts[1].strip()
                        if not path:
                            continue

                        base = os.path.basename(path)
                        low = base.lower()

                        # hanya terima file image
                        if not (low.endswith(".img") or low.endswith(".img.gz")):
                            continue

                        try:
                            size_bytes = int(size_str)
                        except Exception:
                            size_bytes = 0

                        is_golden = "golden" in low
                        files.append((path, size_bytes, is_golden))

            if not files:
                text = f"""✅ <b>Pilihan Anda:</b>

📦 <b>Tipe:</b> {type_name}
🪟 <b>Windows:</b> {win_name}

❌ <b>Belum ada image di GDrive</b>

Upload file <code>.img</code> / <code>.img.gz</code> ke:
<code>gdrive:rdp-images/</code>"""

                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="install_rdp"))
                bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)
                return

            # Pisahkan golden dan regular
            golden_files = [(p, s) for p, s, g in files if g]
            regular_files = [(p, s) for p, s, g in files if not g]

            # Simpan mapping pilihan → path (hindari callback_data kepanjangan)
            USER_IMAGE_CHOICES[call.from_user.id] = {}

            files_text = ""
            if golden_files:
                files_text += "🏆 <b>Golden Images (CEPAT 1-2 menit):</b>\n"
                for path, size in golden_files[:10]:
                    files_text += f"  • <code>{os.path.basename(path)}</code> ({human_size(size)})\n"
                files_text += "\n"

            if regular_files:
                files_text += "📁 <b>Regular Images:</b>\n"
                for path, size in regular_files[:10]:
                    files_text += f"  • <code>{os.path.basename(path)}</code> ({human_size(size)})\n"

            text = f"""☁️ <b>PILIH IMAGE DARI GDRIVE</b>
━━━━━━━━━━━━━━━━━━

📦 <b>Tipe:</b> {type_name}
🪟 <b>Windows:</b> {win_name}

{files_text}
<b>Klik image untuk install:</b>"""

            markup = types.InlineKeyboardMarkup()

            idx = 1
            for path, size in golden_files[:20]:
                choice_id = str(idx)
                USER_IMAGE_CHOICES[call.from_user.id][choice_id] = path
                short_name = os.path.basename(path)
                short_name = short_name[:25] + "..." if len(short_name) > 25 else short_name
                markup.add(
                    types.InlineKeyboardButton(
                        f"🏆 {short_name} ({human_size(size)})",
                        callback_data=f"use_img:{choice_id}",
                    )
                )
                idx += 1

            for path, size in regular_files[:20]:
                choice_id = str(idx)
                USER_IMAGE_CHOICES[call.from_user.id][choice_id] = path
                short_name = os.path.basename(path)
                short_name = short_name[:25] + "..." if len(short_name) > 25 else short_name
                markup.add(
                    types.InlineKeyboardButton(
                        f"📦 {short_name} ({human_size(size)})",
                        callback_data=f"use_img:{choice_id}",
                    )
                )
                idx += 1

            markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="install_rdp"))

            bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=list_and_show_images, daemon=True).start()

# ==================== PILIH IMAGE DARI GDRIVE ====================
USER_SELECTED_IMAGE: dict[int, str] = {}
USER_IMAGE_CHOICES: dict[int, dict[str, str]] = {}

@bot.callback_query_handler(func=lambda call: call.data.startswith("use_img:"))
def select_gdrive_image(call):
    """User pilih image dari GDrive untuk install"""
    if not is_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Akses ditolak!")
        return

    choice_id = call.data.replace("use_img:", "").strip()
    choices = USER_IMAGE_CHOICES.get(call.from_user.id, {})

    if not choice_id or choice_id not in choices:
        bot.answer_callback_query(call.id, "❗ List image sudah kadaluarsa, buka lagi menu install.")
        bot.send_message(call.message.chat.id, "❗ List image sudah kadaluarsa. Silakan buka lagi: 🖥 Install RDP")
        return

    image_path = choices[choice_id]
    USER_SELECTED_IMAGE[call.from_user.id] = image_path

    saved = USER_SELECTED_OS.get(call.from_user.id)
    rdp_type = USER_SELECTED_TYPE.get(call.from_user.id, "docker")
    type_name = RDP_TYPES[rdp_type]["name"]
    win_name = saved.get("name") if saved else "Windows"

    text = f"""✅ <b>Pilihan Anda:</b>

📦 <b>Tipe:</b> {type_name}
🪟 <b>Windows:</b> {win_name}
☁️ <b>Image:</b> <code>{os.path.basename(image_path)}</code>

Sekarang kirim IP dan Password VPS dengan format:
<code>/install IP PASSWORD</code>

Contoh: <code>/install 167.71.123.45 password123</code>"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="install_rdp"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    bot.answer_callback_query(call.id, f"✅ Image dipilih")

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
        
        # Ambil image dari GDrive jika user sudah pilih
        gdrive_image = USER_SELECTED_IMAGE.get(message.from_user.id, "")

        # Dedicated wajib pilih image (hapus mode Online)
        if rdp_type == "dedicated" and not gdrive_image:
            bot.reply_to(
                message,
                "❗ Dedicated RDP wajib pilih <b>Image GDrive</b> dulu (tidak ada mode Online).\n\nBuka: 🖥 Install RDP → pilih Dedicated → pilih Windows → pilih Image.",
                parse_mode="HTML",
            )
            return

        # Cek apakah pakai golden image (deploy cepat 1-2 menit)
        base_image = os.path.basename(gdrive_image) if gdrive_image else ""
        is_golden_image = (
            rdp_type == "dedicated"
            and bool(gdrive_image)
            and (base_image.lower().endswith(".img") or base_image.lower().endswith(".img.gz"))
        )

        # Kirim pesan awal + estimasi
        if rdp_type == "docker":
            eta_text = "10-15 menit"
        elif is_golden_image:
            eta_text = "1-2 menit (Golden Image)"
        else:
            eta_text = "15-30 menit"

        image_info = f"\n☁️ <b>Image:</b> <code>{base_image}</code>" if gdrive_image else ""

        if not os.path.exists(script_path):
            bot.reply_to(message, f"❌ File {os.path.basename(script_path)} tidak ditemukan. Pastikan sudah git pull.")
            return

        subprocess.run(["chmod", "+x", script_path], check=False)

        chat_id = str(message.chat.id)

        # Fungsi untuk jalankan instalasi di background
        def run_install():
            try:
                log_path = os.path.join(script_dir, "rdp_install.log")

                if is_golden_image:
                    # Deploy golden image (cepat 1-2 menit!)
                    result = subprocess.run(
                        ["bash", script_path, ip, password, image_name, chat_id, BOT_TOKEN],
                        capture_output=True,
                        text=True,
                        timeout=600  # 10 menit timeout untuk golden image
                    )
                else:
                    # Install biasa (15-30 menit)
                    result = subprocess.run(
                        ["bash", script_path, ip, password, win_code, chat_id, BOT_TOKEN, gdrive_image],
                        capture_output=True,
                        text=True,
                        timeout=2400  # 40 menit timeout
                    )

                output = result.stdout + result.stderr
                exit_code = result.returncode

                # Simpan log
                with open(log_path, "a") as log:
                    log.write(f"\n{'='*50}\n")
                    log.write(f"User: {message.from_user.id} | IP: {ip} | OS: {win_code} | Type: {rdp_type} | Image: {gdrive_image}\n")
                    log.write(output)
                    log.write(f"\nExit code: {exit_code}\n")
                
                # Clear selected image setelah install
                if message.from_user.id in USER_SELECTED_IMAGE:
                    del USER_SELECTED_IMAGE[message.from_user.id]

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
        source_info = f"☁️ Image: {gdrive_image}" if gdrive_image else "☁️ Sumber: Online"
        
        # Estimasi waktu berdasarkan tipe
        if is_golden_image:
            time_estimate = "⚡ Golden Image: 1-2 menit"
        elif rdp_type == "docker":
            time_estimate = "🐳 Docker RDP: 10-15 menit"
        else:
            time_estimate = "🖥 Dedicated RDP: 15-30 menit"
        
        bot.send_message(
            message.chat.id,
            f"""🚀 <b>Proses Instalasi Dimulai!</b>
━━━━━━━━━━━━━━━━━━

📦 <b>Tipe:</b> {type_name}
📍 <b>IP:</b> <code>{ip}</code>
🪟 <b>Windows:</b> {win_name}
{source_info}

⏳ Instalasi berjalan di background.
Kamu akan menerima notifikasi saat selesai.

<b>Estimasi waktu:</b>
{time_estimate}

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
    markup.add(types.InlineKeyboardButton("📟 Run Command", callback_data="tumbal_run"))
    markup.add(types.InlineKeyboardButton("🏗 Build Golden Image", callback_data="tumbal_build_golden"))
    markup.add(types.InlineKeyboardButton("📋 List Local Images", callback_data="tumbal_list"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="owner_settings"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== BUILD GOLDEN IMAGE MENU ====================
@bot.callback_query_handler(func=lambda call: call.data == "tumbal_build_golden")
def tumbal_build_golden_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS tumbal aktif!")
        return

    text = f"""🏗 <b>BUILD GOLDEN IMAGE</b>
━━━━━━━━━━━━━━━━━━

📍 <b>VPS:</b> {tumbal['name']} ({tumbal['ip']})

<b>Pilih Windows untuk di-build:</b>

Golden Image adalah Windows yang sudah:
✅ Terinstall lengkap
✅ RDP aktif
✅ Driver lengkap
✅ Siap clone ke VPS user

⏱ <b>Estimasi build:</b> 30-60 menit
💾 <b>Output:</b> ~5-10GB compressed"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🪟 Windows 10", callback_data="build_golden:10"))
    markup.add(types.InlineKeyboardButton("🪟 Windows 11", callback_data="build_golden:11"))
    markup.add(types.InlineKeyboardButton("🖥 Server 2019", callback_data="build_golden:2019"))
    markup.add(types.InlineKeyboardButton("🖥 Server 2022", callback_data="build_golden:2022"))
    markup.add(types.InlineKeyboardButton("⚡ Tiny10 (Light)", callback_data="build_golden:tiny10"))
    markup.add(types.InlineKeyboardButton("⚡ Tiny11 (Light)", callback_data="build_golden:tiny11"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="tumbal_menu"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== START BUILD GOLDEN IMAGE ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("build_golden:"))
def start_build_golden(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS tumbal aktif!")
        return

    win_code = call.data.replace("build_golden:", "")
    win_names = {
        "10": "Windows 10",
        "11": "Windows 11", 
        "2019": "Windows Server 2019",
        "2022": "Windows Server 2022",
        "tiny10": "Tiny10 23H2",
        "tiny11": "Tiny11 23H2"
    }
    win_name = win_names.get(win_code, "Windows")
    image_name = f"golden-{win_code}"

    bot.answer_callback_query(call.id, f"⏳ Memulai build {win_name}...")

    ip = tumbal["ip"]
    password = tumbal["password"]
    name = tumbal["name"]

    bot.send_message(call.message.chat.id, f"""🏗 <b>BUILD GOLDEN IMAGE</b>
━━━━━━━━━━━━━━━━━━

📍 <b>VPS:</b> {name} ({ip})
🪟 <b>Windows:</b> {win_name}
📦 <b>Output:</b> {image_name}.img.gz

⏳ <b>Proses build dimulai...</b>

⏱ Estimasi: 30-60 menit
💡 Kamu akan dinotifikasi saat selesai.

📺 <b>Monitor via VNC:</b>
   <code>{ip}:5900</code>""", parse_mode="HTML")

    def run_build():
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(script_dir, "build_golden_image.sh")
            
            if not os.path.exists(script_path):
                bot.send_message(call.message.chat.id, "❌ Script build_golden_image.sh tidak ditemukan!")
                return
            
            # Copy script ke tumbal VPS
            subprocess.run(["chmod", "+x", script_path], check=False)
            subprocess.run(
                ["sshpass", "-p", password, "scp", "-o", "StrictHostKeyChecking=no",
                 script_path, f"root@{ip}:/root/build_golden_image.sh"],
                capture_output=True, timeout=60
            )
            
            # Jalankan script
            result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ServerAliveInterval=60", "-o", "ServerAliveCountMax=60",
                 f"root@{ip}", f"bash /root/build_golden_image.sh {win_code} {image_name}"],
                capture_output=True, text=True, timeout=7200  # 2 jam timeout
            )
            
            if "BUILD COMPLETE" in result.stdout:
                bot.send_message(call.message.chat.id, f"""✅ <b>BUILD SELESAI!</b>
━━━━━━━━━━━━━━━━━━

🪟 <b>Windows:</b> {win_name}
📦 <b>File:</b> {image_name}.img.gz
📍 <b>Lokasi:</b> /root/rdp-images/

<b>Default Credentials:</b>
• Username: <code>Admin</code>
• Password: <code>Admin@123</code>

📤 <b>Upload ke GDrive:</b>
Gunakan menu "List Local Images" untuk upload.""", parse_mode="HTML")
            else:
                bot.send_message(call.message.chat.id, f"⚠️ Build mungkin gagal. Cek log:\n<code>{result.stdout[-1000:]}</code>", parse_mode="HTML")
            
        except subprocess.TimeoutExpired:
            bot.send_message(call.message.chat.id, "⏰ Build timeout (>2 jam). Cek manual di VPS tumbal.")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=run_build, daemon=True).start()

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
                # Cari nama file hasil build
                list_result = subprocess.run(
                    ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                     f"root@{ip}", "ls -t /root/rdp-images/ 2>/dev/null | head -1"],
                    capture_output=True, text=True, timeout=30
                )
                latest_file = list_result.stdout.strip() if list_result.returncode == 0 else ""
                
                if latest_file:
                    file_path = f"/root/rdp-images/{latest_file}"
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton(
                        "📤 Upload ke GDrive", 
                        callback_data=f"quick_upload:{file_path}"
                    ))
                    markup.add(types.InlineKeyboardButton("📋 List Files", callback_data="tumbal_list"))
                    
                    bot.send_message(chat_id, f"""✅ <b>Build Selesai!</b>

🪟 <b>Windows:</b> {win_name}
📍 <b>VPS:</b> {name}
📁 <b>File:</b> <code>{file_path}</code>

Klik tombol di bawah untuk upload ke Google Drive:""", parse_mode="HTML", reply_markup=markup)
                else:
                    bot.send_message(chat_id, f"""✅ <b>Build Selesai!</b>

🪟 <b>Windows:</b> {win_name}
📍 <b>VPS:</b> {name}
📁 <b>Lokasi:</b> /root/rdp-images/

Gunakan <code>/listlocal</code> untuk lihat file, lalu <code>/upload [path] rdp-images</code>""", parse_mode="HTML")
            else:
                bot.send_message(chat_id, f"""❌ <b>Build Gagal!</b>

<code>{result.stderr[:500]}</code>""", parse_mode="HTML")

        except subprocess.TimeoutExpired:
            bot.send_message(chat_id, "⏰ Build timeout (>2 jam)")
        except Exception as e:
            bot.send_message(chat_id, f"❌ Error: {str(e)}")

    threading.Thread(target=do_build, daemon=True).start()

# ==================== QUICK UPLOAD (dari tombol setelah build) ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("quick_upload:"))
def quick_upload_handler(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    file_path = call.data.split(":", 1)[1]
    bot.answer_callback_query(call.id, "⏳ Memulai upload...")

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.send_message(call.message.chat.id, "❌ Tidak ada VPS aktif!")
        return

    def do_remote_upload():
        try:
            ip = tumbal["ip"]
            password = tumbal["password"]
            
            # Cek file size dulu
            size_result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 f"root@{ip}", f"du -h {file_path} 2>/dev/null | cut -f1"],
                capture_output=True, text=True, timeout=30
            )
            file_size = size_result.stdout.strip() or "?"
            
            bot.send_message(call.message.chat.id, f"""⏳ <b>Uploading ke GDrive...</b>

📁 <b>File:</b> <code>{file_path}</code>
📊 <b>Size:</b> {file_size}

Ini bisa memakan waktu lama untuk file besar.""", parse_mode="HTML")

            # Upload via rclone di VPS tumbal
            upload_result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 f"root@{ip}", f"rclone copy {file_path} gdrive:rdp-images/ -P 2>&1"],
                capture_output=True, text=True, timeout=7200  # 2 jam timeout
            )

            if upload_result.returncode == 0:
                filename = os.path.basename(file_path)
                bot.send_message(call.message.chat.id, f"""✅ <b>Upload Berhasil!</b>

📁 <b>File:</b> {filename}
📂 <b>GDrive:</b> rdp-images/{filename}
📊 <b>Size:</b> {file_size}""", parse_mode="HTML")
            else:
                bot.send_message(call.message.chat.id, f"""❌ <b>Upload Gagal!</b>

<code>{upload_result.stderr[:500] if upload_result.stderr else upload_result.stdout[:500]}</code>

Pastikan rclone sudah dikonfigurasi di VPS tumbal.""", parse_mode="HTML")

        except subprocess.TimeoutExpired:
            bot.send_message(call.message.chat.id, "⏰ Upload timeout (>2 jam)")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=do_remote_upload, daemon=True).start()

# ==================== RUN COMMAND ON TUMBAL VPS ====================
@bot.message_handler(commands=['run'])
def run_cmd(message):
    """Command /run - Jalankan perintah di VPS tumbal"""
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.reply_to(message, "❌ Belum ada VPS tumbal aktif! Tambah dulu via /start → Settings Owner → Tumbal VPS")
        return

    try:
        # Get command after /run
        cmd_text = message.text.split(maxsplit=1)
        if len(cmd_text) < 2:
            bot.reply_to(message, """📟 <b>RUN COMMAND</b>

<b>Format:</b> <code>/run [perintah]</code>

<b>Contoh:</b>
<code>/run ls -la /root</code>
<code>/run df -h</code>
<code>/run free -h</code>
<code>/run ls -lh /root/rdp-images/</code>
<code>/run apt update</code>
<code>/run cat /etc/os-release</code>

⚠️ Hati-hati dengan perintah berbahaya!""", parse_mode="HTML")
            return

        command = cmd_text[1]
        ip = tumbal["ip"]
        password = tumbal["password"]
        name = tumbal["name"]

        bot.reply_to(message, f"⏳ Menjalankan di <b>{name}</b>...\n<code>{command}</code>", parse_mode="HTML")

        def execute_cmd():
            try:
                result = subprocess.run(
                    ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                     "-o", "ConnectTimeout=15", f"root@{ip}", command],
                    capture_output=True, text=True, timeout=120  # 2 menit timeout
                )

                output = result.stdout.strip() if result.stdout else ""
                error = result.stderr.strip() if result.stderr else ""
                
                # Combine output
                full_output = ""
                if output:
                    full_output += output
                if error:
                    if full_output:
                        full_output += "\n\n⚠️ STDERR:\n" + error
                    else:
                        full_output = error

                if not full_output:
                    full_output = "(tidak ada output)"

                # Truncate if too long
                if len(full_output) > 3500:
                    full_output = full_output[:3500] + "\n\n... (output terpotong)"

                status = "✅" if result.returncode == 0 else "⚠️"
                
                text = f"""{status} <b>OUTPUT dari {name}</b>
━━━━━━━━━━━━━━━━━━
📍 IP: <code>{ip}</code>
💻 CMD: <code>{command}</code>
📊 Exit: {result.returncode}
━━━━━━━━━━━━━━━━━━

<code>{full_output}</code>"""

                bot.send_message(message.chat.id, text, parse_mode="HTML")

            except subprocess.TimeoutExpired:
                bot.send_message(message.chat.id, f"⏰ Timeout! Perintah memakan waktu >2 menit")
            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

        threading.Thread(target=execute_cmd, daemon=True).start()

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "tumbal_run")
def tumbal_run_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS aktif!")
        return

    bot.answer_callback_query(call.id)
    
    text = f"""📟 <b>RUN COMMAND - {tumbal['name']}</b>
━━━━━━━━━━━━━━━━━━

📍 IP: <code>{tumbal['ip']}</code>

Gunakan command:
<code>/run [perintah]</code>

<b>Quick Commands:</b>"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📊 Disk Usage", callback_data="qcmd_df"))
    markup.add(types.InlineKeyboardButton("💾 Memory", callback_data="qcmd_free"))
    markup.add(types.InlineKeyboardButton("📁 List /root", callback_data="qcmd_ls"))
    markup.add(types.InlineKeyboardButton("🖼 List Images", callback_data="qcmd_images"))
    markup.add(types.InlineKeyboardButton("📂 Buat Folder Images", callback_data="mkdir_images"))
    markup.add(types.InlineKeyboardButton("🔄 Uptime", callback_data="qcmd_uptime"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="tumbal_menu"))

    bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("qcmd_"))
def quick_cmd(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS aktif!")
        return

    cmd_map = {
        "qcmd_df": "df -h",
        "qcmd_free": "free -h",
        "qcmd_ls": "ls -la /root",
        "qcmd_images": "ls -lhS /root/rdp-images/ 2>/dev/null || echo 'Folder tidak ada'",
        "qcmd_uptime": "uptime && cat /etc/os-release | head -5"
    }

    cmd = cmd_map.get(call.data, "echo 'Unknown command'")
    ip = tumbal["ip"]
    password = tumbal["password"]
    name = tumbal["name"]

    bot.answer_callback_query(call.id, f"⏳ Running: {cmd[:30]}...")

    def execute_cmd():
        try:
            result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=15", f"root@{ip}", cmd],
                capture_output=True, text=True, timeout=60
            )

            output = result.stdout.strip() if result.stdout else result.stderr.strip()
            if not output:
                output = "(tidak ada output)"

            if len(output) > 3000:
                output = output[:3000] + "\n... (terpotong)"

            status = "✅" if result.returncode == 0 else "⚠️"
            
            text = f"""{status} <b>OUTPUT - {name}</b>
━━━━━━━━━━━━━━━━━━
💻 <code>{cmd}</code>
━━━━━━━━━━━━━━━━━━

<code>{output}</code>"""

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="tumbal_run"))

            bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=execute_cmd, daemon=True).start()

# ==================== MKDIR COMMAND ====================
@bot.message_handler(commands=['mkdir'])
def mkdir_cmd(message):
    """Command /mkdir - Buat folder di VPS tumbal"""
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.reply_to(message, "❌ Belum ada VPS tumbal aktif!")
        return

    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, """📁 <b>BUAT FOLDER</b>

<b>Format:</b> <code>/mkdir [path]</code>

<b>Contoh:</b>
<code>/mkdir /root/rdp-images</code>
<code>/mkdir /root/backup</code>
<code>/mkdir /home/data/windows</code>

💡 Otomatis pakai <code>mkdir -p</code> (buat parent folder jika belum ada)""", parse_mode="HTML")
            return

        folder_path = parts[1].strip()
        ip = tumbal["ip"]
        password = tumbal["password"]
        name = tumbal["name"]

        bot.reply_to(message, f"⏳ Membuat folder di <b>{name}</b>...", parse_mode="HTML")

        def create_folder():
            try:
                result = subprocess.run(
                    ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                     "-o", "ConnectTimeout=15", f"root@{ip}", f"mkdir -p {folder_path} && echo 'SUCCESS' && ls -la {folder_path}"],
                    capture_output=True, text=True, timeout=30
                )

                if "SUCCESS" in result.stdout:
                    output = result.stdout.replace("SUCCESS\n", "").strip()
                    text = f"""✅ <b>Folder Berhasil Dibuat!</b>
━━━━━━━━━━━━━━━━━━

📁 <b>Path:</b> <code>{folder_path}</code>
📍 <b>VPS:</b> {name}

<b>Isi folder:</b>
<code>{output if output else '(kosong)'}</code>"""
                else:
                    error = result.stderr.strip() if result.stderr else result.stdout
                    text = f"""❌ <b>Gagal Buat Folder!</b>

<code>{error[:500]}</code>"""

                bot.send_message(message.chat.id, text, parse_mode="HTML")

            except Exception as e:
                bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

        threading.Thread(target=create_folder, daemon=True).start()

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "mkdir_images")
def quick_mkdir_images(call):
    """Quick button untuk buat folder rdp-images"""
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS aktif!")
        return

    ip = tumbal["ip"]
    password = tumbal["password"]
    name = tumbal["name"]

    bot.answer_callback_query(call.id, "⏳ Membuat folder...")

    def create_folder():
        try:
            result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=15", f"root@{ip}", "mkdir -p /root/rdp-images && echo 'SUCCESS' && ls -la /root/rdp-images"],
                capture_output=True, text=True, timeout=30
            )

            if "SUCCESS" in result.stdout:
                text = f"""✅ <b>Folder /root/rdp-images Siap!</b>
━━━━━━━━━━━━━━━━━━

📍 <b>VPS:</b> {name}
📁 <b>Path:</b> <code>/root/rdp-images/</code>

Folder sudah siap untuk menyimpan image."""
            else:
                text = f"❌ Gagal: {result.stderr[:300]}"

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📋 List Images", callback_data="tumbal_list"))
            markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="tumbal_run"))

            bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=create_folder, daemon=True).start()

# ==================== LIST LOCAL IMAGES ====================
@bot.message_handler(commands=['listlocal'])
def list_local_cmd(message):
    """Command /listlocal - List file di /root/rdp-images/ VPS tumbal"""
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.reply_to(message, "❌ Belum ada VPS tumbal aktif! Tambah dulu via /start → Settings Owner → Tumbal VPS")
        return

    bot.reply_to(message, f"⏳ Mengambil daftar file dari {tumbal['name']}...")

    def list_images():
        try:
            ip = tumbal["ip"]
            password = tumbal["password"]
            name = tumbal["name"]

            result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 f"root@{ip}", "ls -lhS /root/rdp-images/ 2>/dev/null || echo 'EMPTY'"],
                capture_output=True, text=True, timeout=30
            )

            if "EMPTY" in result.stdout or not result.stdout.strip():
                text = f"""📋 <b>LOCAL IMAGES DI {name.upper()}</b>
━━━━━━━━━━━━━━━━━━

📍 IP: <code>{ip}</code>

Folder kosong. Belum ada image yang dibuild."""
            else:
                # Parse dan format output
                lines = result.stdout.strip().split('\n')
                files_info = []
                for line in lines[1:]:  # Skip header line
                    parts = line.split()
                    if len(parts) >= 9:
                        size = parts[4]
                        filename = parts[-1]
                        files_info.append(f"• <code>{filename}</code> ({size})")
                
                text = f"""📋 <b>LOCAL IMAGES DI {name.upper()}</b>
━━━━━━━━━━━━━━━━━━

📍 IP: <code>{ip}</code>

{chr(10).join(files_info) if files_info else result.stdout}

<b>Upload:</b>
<code>/upload /root/rdp-images/[nama_file] rdp-images</code>"""

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="tumbal_list"))

            bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)

        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=list_images, daemon=True).start()

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

            # Hitung jumlah file dan list dengan ukuran
            result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 f"root@{ip}", """
mkdir -p /root/rdp-images
cd /root/rdp-images
count=$(find . -maxdepth 1 -type f 2>/dev/null | wc -l)
echo "FILE_COUNT:$count"
if [ "$count" -gt 0 ]; then
    ls -1 --time-style=+"%Y-%m-%d" -lhS 2>/dev/null | grep -v "^total" | awk '{print $5"|"$6"|"$NF}'
fi
"""],
                capture_output=True, text=True, timeout=30
            )

            output = result.stdout.strip()
            
            # Parse file count
            file_count = 0
            files_list = []  # List of (filename, size, date)
            
            for line in output.split('\n'):
                if line.startswith("FILE_COUNT:"):
                    try:
                        file_count = int(line.replace("FILE_COUNT:", "").strip())
                    except:
                        pass
                elif "|" in line:
                    parts = line.split("|")
                    if len(parts) >= 3:
                        size = parts[0]
                        date = parts[1]
                        filename = parts[2]
                        if filename and filename not in ['.', '..']:
                            files_list.append((filename, size, date))

            markup = types.InlineKeyboardMarkup()

            if file_count == 0:
                text = f"""📋 <b>LOCAL IMAGES DI {name.upper()}</b>
━━━━━━━━━━━━━━━━━━

📍 IP: <code>{ip}</code>

📁 <b>Total: 0 file</b>

Folder kosong. Gunakan <b>🏗 Build Image</b> untuk membuat image."""
                
                markup.add(types.InlineKeyboardButton("🏗 Build Image", callback_data="tumbal_build"))
            else:
                # Build file list text
                files_text = ""
                for i, (filename, size, date) in enumerate(files_list[:10]):  # Max 10 files
                    files_text += f"📦 <code>{filename}</code>\n   📐 {size} | 📅 {date}\n\n"
                    # Add upload button for each file
                    markup.add(types.InlineKeyboardButton(
                        f"📤 Upload: {filename[:25]}{'...' if len(filename) > 25 else ''}", 
                        callback_data=f"ul_img:{filename[:50]}"
                    ))
                
                text = f"""📋 <b>LOCAL IMAGES DI {name.upper()}</b>
━━━━━━━━━━━━━━━━━━

📍 IP: <code>{ip}</code>

📁 <b>Total: {file_count} file</b>

{files_text}
💡 Klik tombol di bawah untuk upload ke GDrive"""

            markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="tumbal_list"))
            markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="tumbal_menu"))

            bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=list_images, daemon=True).start()

# ==================== UPLOAD FROM LIST BUTTON ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("ul_img:"))
def upload_from_list(call):
    """Upload file dari list dengan satu klik"""
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    tumbal = get_active_tumbal()
    if not tumbal:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS aktif!")
        return

    filename = call.data.replace("ul_img:", "")
    file_path = f"/root/rdp-images/{filename}"
    ip = tumbal["ip"]
    password = tumbal["password"]
    name = tumbal["name"]

    bot.answer_callback_query(call.id, f"⏳ Uploading {filename}...")

    bot.send_message(call.message.chat.id, f"""📤 <b>UPLOAD KE GDRIVE</b>
━━━━━━━━━━━━━━━━━━

📁 <b>File:</b> <code>{filename}</code>
📍 <b>Dari:</b> {name} ({ip})
☁️ <b>Ke:</b> GDrive/rdp-images/

⏳ Proses upload dimulai...""", parse_mode="HTML")

    def do_upload():
        try:
            # Cek duplikat dulu sebelum upload
            check_result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 f"root@{ip}", f"""
# Cek konfigurasi gdrive
if ! rclone listremotes | grep -q "gdrive:"; then
    echo "ERROR:GDrive belum dikonfigurasi"
    exit 1
fi

# Auto-create folder rdp-images jika belum ada
rclone mkdir gdrive:rdp-images 2>/dev/null

# Cek apakah file sudah ada di GDrive (duplikat)
if rclone lsf gdrive:rdp-images/ 2>/dev/null | grep -q "^{filename}$"; then
    echo "DUPLICATE_EXISTS"
else
    echo "NO_DUPLICATE"
fi
"""],
                capture_output=True, text=True, timeout=60
            )
            
            check_output = check_result.stdout.strip()
            
            if "ERROR:" in check_output:
                error_msg = check_output.split("ERROR:")[-1].strip()
                bot.send_message(call.message.chat.id, f"❌ {error_msg}")
                return
            
            # Jika duplikat, hapus yang lama dulu
            if "DUPLICATE_EXISTS" in check_output:
                bot.send_message(call.message.chat.id, f"⚠️ <b>File duplikat terdeteksi!</b>\n\n<code>{filename}</code> sudah ada di GDrive.\n🗑 Menghapus file lama dan upload yang baru...", parse_mode="HTML")
                
                # Hapus duplikat
                subprocess.run(
                    ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                     f"root@{ip}", f"rclone delete gdrive:rdp-images/{filename}"],
                    capture_output=True, text=True, timeout=60
                )
            
            # Upload via rclone dari tumbal VPS
            result = subprocess.run(
                ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                 f"root@{ip}", f"""
# Auto-install rclone jika belum ada
if ! command -v rclone &> /dev/null; then
    echo "📦 Rclone belum ada, menginstall..."
    apt-get update -qq
    apt-get install -y rclone > /dev/null 2>&1
    if ! command -v rclone &> /dev/null; then
        curl -s https://rclone.org/install.sh | bash > /dev/null 2>&1
    fi
    if ! command -v rclone &> /dev/null; then
        echo "ERROR:Gagal install rclone"
        exit 1
    fi
    echo "✅ Rclone terinstall!"
fi

if [ ! -f "{file_path}" ]; then
    echo "ERROR:File tidak ditemukan: {file_path}"
    exit 1
fi

echo "⏳ Uploading {filename}..."
rclone copy "{file_path}" gdrive:rdp-images/ -P 2>&1

if [ $? -eq 0 ]; then
    echo "SUCCESS"
else
    echo "ERROR:Upload gagal"
fi
"""],
                capture_output=True, text=True, timeout=7200
            )

            output = result.stdout.strip()
            
            if "SUCCESS" in output:
                bot.send_message(call.message.chat.id, f"""✅ <b>Upload Berhasil!</b>

📁 <b>File:</b> <code>{filename}</code>
☁️ <b>Lokasi:</b> GDrive/rdp-images/{filename}""", parse_mode="HTML")
            elif "ERROR:" in output:
                error_msg = output.split("ERROR:")[-1].strip()
                bot.send_message(call.message.chat.id, f"❌ {error_msg}")
            else:
                bot.send_message(call.message.chat.id, f"⚠️ Status tidak jelas:\n<code>{output[:500]}</code>", parse_mode="HTML")

        except subprocess.TimeoutExpired:
            bot.send_message(call.message.chat.id, "⏰ Upload timeout (>2 jam)")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=do_upload, daemon=True).start()

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
    markup.add(types.InlineKeyboardButton("🔄 Sync Config ke Tumbal", callback_data="gdrive_sync_config"))
    markup.add(types.InlineKeyboardButton("📋 List Images di GDrive", callback_data="gdrive_list"))
    markup.add(types.InlineKeyboardButton("🗑 Delete Image", callback_data="gdrive_delete"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="owner_settings"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== SYNC GDRIVE CONFIG - PILIH VPS ====================
@bot.callback_query_handler(func=lambda call: call.data == "gdrive_sync_config")
def gdrive_sync_config_menu(call):
    """Tampilkan daftar VPS tumbal untuk dipilih"""
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    # Cek apakah rclone.conf ada di bot server
    rclone_conf = os.path.expanduser("~/.config/rclone/rclone.conf")
    if not os.path.exists(rclone_conf):
        bot.answer_callback_query(call.id, "❌ rclone.conf tidak ada!")
        bot.send_message(call.message.chat.id, """❌ <b>Rclone belum dikonfigurasi di bot server!</b>

Jalankan dulu di bot server:
<code>rclone config</code>

Setelah itu baru bisa sync ke VPS tumbal.""", parse_mode="HTML")
        return

    tumbal_list = data.get("tumbal_list", [])
    if not tumbal_list:
        bot.answer_callback_query(call.id, "❌ Belum ada VPS tumbal!")
        return

    bot.answer_callback_query(call.id, "Pilih VPS tujuan...")

    text = """🔄 <b>SYNC GDRIVE CONFIG</b>
━━━━━━━━━━━━━━━━━━

📤 <b>Dari:</b> Bot Server
📥 <b>Ke:</b> Pilih VPS di bawah

<b>Pilih VPS tujuan:</b>"""

    markup = types.InlineKeyboardMarkup()
    
    # Tombol untuk setiap VPS
    for t in tumbal_list:
        status = "✅" if t.get("enabled") else "❌"
        markup.add(types.InlineKeyboardButton(
            f"{status} {t['name']} ({t['ip']})", 
            callback_data=f"sync_to:{t['id']}"
        ))
    
    # Tombol sync ke SEMUA VPS
    if len(tumbal_list) > 1:
        markup.add(types.InlineKeyboardButton("🔄 Sync ke SEMUA VPS", callback_data="sync_to:ALL"))
    
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="gdrive_menu"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== SYNC TO SPECIFIC VPS ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("sync_to:"))
def gdrive_sync_to_vps(call):
    """Sync rclone.conf ke VPS yang dipilih"""
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    target_id = call.data.replace("sync_to:", "")
    
    rclone_conf = os.path.expanduser("~/.config/rclone/rclone.conf")
    if not os.path.exists(rclone_conf):
        bot.answer_callback_query(call.id, "❌ rclone.conf tidak ada!")
        return

    # Baca config
    with open(rclone_conf, 'r') as f:
        conf_content = f.read()

    # Tentukan target VPS
    if target_id == "ALL":
        targets = [t for t in data.get("tumbal_list", []) if t.get("enabled")]
        target_names = ", ".join([t["name"] for t in targets])
    else:
        tumbal = get_tumbal_by_id(target_id)
        if not tumbal:
            bot.answer_callback_query(call.id, "❌ VPS tidak ditemukan!")
            return
        targets = [tumbal]
        target_names = tumbal["name"]

    if not targets:
        bot.answer_callback_query(call.id, "❌ Tidak ada VPS aktif!")
        return

    bot.answer_callback_query(call.id, f"⏳ Syncing ke {len(targets)} VPS...")

    bot.send_message(call.message.chat.id, f"""🔄 <b>SYNC GDRIVE CONFIG</b>
━━━━━━━━━━━━━━━━━━

📤 <b>Dari:</b> Bot Server
📥 <b>Ke:</b> {target_names}

⏳ Proses sync dimulai...""", parse_mode="HTML")

    def do_sync():
        results = []
        for tumbal in targets:
            ip = tumbal["ip"]
            password = tumbal["password"]
            name = tumbal["name"]
            
            try:
                result = subprocess.run(
                    ["sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
                     f"root@{ip}", f"""
# Install rclone jika belum ada
if ! command -v rclone &> /dev/null; then
    apt-get update -qq
    apt-get install -y rclone > /dev/null 2>&1 || curl -s https://rclone.org/install.sh | bash > /dev/null 2>&1
fi

# Buat folder config
mkdir -p ~/.config/rclone

# Tulis rclone.conf
cat > ~/.config/rclone/rclone.conf << 'RCLONE_EOF'
{conf_content}
RCLONE_EOF

# Verify
if rclone listremotes | grep -q "gdrive:"; then
    echo "SUCCESS"
else
    echo "ERROR:gdrive remote tidak ditemukan"
fi
"""],
                    capture_output=True, text=True, timeout=120
                )

                output = result.stdout.strip()
                if "SUCCESS" in output:
                    results.append(f"✅ {name}: Berhasil")
                elif "ERROR:" in output:
                    error_msg = output.split("ERROR:")[-1].strip()
                    results.append(f"❌ {name}: {error_msg}")
                else:
                    results.append(f"⚠️ {name}: Status tidak jelas")

            except Exception as e:
                results.append(f"❌ {name}: {str(e)[:50]}")

        # Kirim hasil
        results_text = "\n".join(results)
        bot.send_message(call.message.chat.id, f"""🔄 <b>HASIL SYNC</b>
━━━━━━━━━━━━━━━━━━

{results_text}""", parse_mode="HTML")

    threading.Thread(target=do_sync, daemon=True).start()

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
 scope = drive.file
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
    """Authorize Google Drive tanpa SSH (Device Code Flow)."""
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    # Cek apakah rclone sudah terinstall
    if not os.path.exists("/usr/bin/rclone"):
        bot.reply_to(
            message,
            """❌ <b>Rclone belum terinstall!</b>

Jalankan dulu:
<code>/setuprclone</code>""",
            parse_mode="HTML",
        )
        return

    config_path = os.path.expanduser("~/.config/rclone/rclone.conf")
    if not os.path.exists(config_path):
        bot.reply_to(
            message,
            """❌ <b>GDrive belum dikonfigurasi!</b>

Jalankan dulu:
<code>/configgdrive [client_id] [client_secret]</code>

⚠️ Disarankan bikin OAuth Client type <b>Desktop app</b> (bukan Web).""",
            parse_mode="HTML",
        )
        return

    bot.reply_to(message, "⏳ Menyiapkan authorize Google Drive...")

    def _read_gdrive_creds() -> tuple[str, str]:
        import configparser

        cfg = configparser.ConfigParser()
        cfg.read(config_path)
        if "gdrive" not in cfg.sections():
            raise ValueError("Config [gdrive] tidak ditemukan")

        client_id = cfg.get("gdrive", "client_id", fallback="").strip()
        client_secret = cfg.get("gdrive", "client_secret", fallback="").strip()
        if not client_id:
            raise ValueError("client_id kosong")
        return client_id, client_secret

    def _set_rclone_token(token_json: str) -> None:
        # Update token di section [gdrive] tanpa merusak format file terlalu banyak
        with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()

        out = []
        in_gdrive = False
        token_set = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                # Jika keluar dari section gdrive dan token belum diset, insert sebelum section berikutnya
                if in_gdrive and not token_set:
                    out.append(f"token = {token_json}")
                    token_set = True
                in_gdrive = stripped.lower() == "[gdrive]"
                out.append(line)
                continue

            if in_gdrive and stripped.lower().startswith("token"):
                out.append(f"token = {token_json}")
                token_set = True
            else:
                out.append(line)

        if in_gdrive and not token_set:
            out.append(f"token = {token_json}")

        with open(config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")

    def generate_device_flow():
        try:
            import json
            import time
            import urllib.parse
            import urllib.request

            client_id, client_secret = _read_gdrive_creds()

            # Step 1: Minta device_code + user_code
            device_url = "https://oauth2.googleapis.com/device/code"
            payload = urllib.parse.urlencode(
                {
                    "client_id": client_id,
                    # Device Code Flow Google hanya support scope Drive tertentu (bukan full drive)
                    # https://developers.google.com/identity/protocols/oauth2/limited-input-device#allowedscopes
                    "scope": "https://www.googleapis.com/auth/drive.file",
                }
            ).encode()

            req = urllib.request.Request(device_url, data=payload, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    dc = json.loads(resp.read().decode())
            except Exception as e:
                # HTTP 400/401 bisa karena: 1) OAuth type salah, 2) App masih Testing mode
                try:
                    import urllib.error

                    if isinstance(e, urllib.error.HTTPError):
                        body = e.read().decode(errors="ignore")
                        
                        error_msg = f"""❌ <b>Authorize ditolak Google</b>

HTTP: <code>{e.code}</code>

<b>Kemungkinan penyebab:</b>

<b>1️⃣ Aplikasi masih mode Testing</b>
   → OAuth consent screen → <b>Test users</b> → Add email kamu
   → Atau klik <b>Publish App</b> untuk production

<b>2️⃣ OAuth Client type salah</b>
   → Harus tipe <b>TVs and Limited Input devices</b>
   → Bukan "Web application" atau "Desktop"

<b>3️⃣ Scope belum diaktifkan</b>
   → OAuth consent screen → Scopes
   → Tambahkan: <code>../auth/drive.file</code>

Setelah fix, jalankan ulang:
<code>/authgdrive</code>"""
                        
                        if body:
                            error_msg += f"\n\nDetail: <code>{body[:150]}</code>"
                        
                        bot.send_message(message.chat.id, error_msg, parse_mode="HTML")
                        return
                except Exception:
                    pass

                bot.send_message(message.chat.id, f"❌ Error: {str(e)}")
                return

            if not dc.get("device_code"):
                bot.send_message(message.chat.id, f"❌ Gagal memulai authorize: {dc}")
                return

            user_code = dc.get("user_code")
            verify_url = dc.get("verification_url") or dc.get("verification_uri")
            device_code = dc.get("device_code")
            interval = int(dc.get("interval", 5))
            expires_in = int(dc.get("expires_in", 900))

            bot.send_message(
                message.chat.id,
                f"""🔐 <b>AUTHORIZE GOOGLE DRIVE</b>
━━━━━━━━━━━━━━━━━━

<b>1)</b> Buka link ini:
{verify_url}

<b>2)</b> Masukkan kode ini:
<code>{user_code}</code>

<b>3)</b> Setelah approve, tunggu… bot akan auto-connect.

⏰ Expire: {expires_in//60} menit""",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

            # Step 2: Poll token endpoint sampai user approve
            token_url = "https://oauth2.googleapis.com/token"
            deadline = time.time() + expires_in

            while time.time() < deadline:
                token_payload = {
                    "client_id": client_id,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                }
                if client_secret:
                    token_payload["client_secret"] = client_secret

                data = urllib.parse.urlencode(token_payload).encode()
                treq = urllib.request.Request(token_url, data=data, method="POST")
                treq.add_header("Content-Type", "application/x-www-form-urlencoded")

                try:
                    with urllib.request.urlopen(treq, timeout=30) as tresp:
                        token_data = json.loads(tresp.read().decode())
                except Exception as e:
                    # retry a bit on transient errors
                    time.sleep(max(interval, 5))
                    continue

                if token_data.get("error"):
                    err = token_data.get("error")
                    if err == "authorization_pending":
                        time.sleep(interval)
                        continue
                    if err == "slow_down":
                        interval += 5
                        time.sleep(interval)
                        continue
                    if err in ("access_denied", "expired_token"):
                        bot.send_message(
                            message.chat.id,
                            f"❌ Authorize gagal: {err}. Jalankan /authgdrive lagi.",
                        )
                        return

                    # unauthorized_client biasanya karena client type bukan Desktop/TV
                    bot.send_message(
                        message.chat.id,
                        f"""❌ Authorize error: <code>{err}</code>

Biasanya karena OAuth Client kamu bukan <b>TVs and Limited Input devices</b>.
Buat ulang OAuth Client (TV/limited input) lalu jalankan /configgdrive lagi.""",
                        parse_mode="HTML",
                    )
                    return

                access_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token", "")
                expires = token_data.get("expires_in", 3600)

                if not access_token:
                    time.sleep(interval)
                    continue

                # Simpan token ke rclone.conf
                expiry_iso = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + int(expires))
                )
                token_json = json.dumps(
                    {
                        "access_token": access_token,
                        "token_type": "Bearer",
                        "refresh_token": refresh_token,
                        "expiry": expiry_iso,
                    }
                )
                _set_rclone_token(token_json)

                # Test koneksi rclone
                test_result = subprocess.run(
                    ["rclone", "lsd", "gdrive:"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if test_result.returncode == 0:
                    bot.send_message(
                        message.chat.id,
                        """✅ <b>Google Drive berhasil terkoneksi!</b>

Sekarang kamu bisa:
• <code>/upload [file] [folder]</code>
• <code>/download [path] [local]</code>
• <code>/gdrive_list</code> (menu)
""",
                        parse_mode="HTML",
                    )
                else:
                    bot.send_message(
                        message.chat.id,
                        f"""⚠️ Token tersimpan tapi test gagal.

Error: <code>{(test_result.stderr or '')[:300]}</code>

Coba restart bot lalu coba /upload.""",
                        parse_mode="HTML",
                    )
                return

            bot.send_message(
                message.chat.id,
                "⏰ Kode authorize expired. Jalankan /authgdrive lagi.",
            )

        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=generate_device_flow, daemon=True).start()


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
                    "expiry": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + token_data.get('expires_in', 3600)))
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
def _list_gdrive_files(chat_id, folder="rdp-images"):
    """Helper untuk list OS/image di GDrive (rekursif, hanya .img/.img.gz)"""
    try:
        result = subprocess.run(
            [
                "rclone",
                "lsf",
                f"gdrive:{folder}/",
                "--recursive",
                "--files-only",
                "--format",
                "sp",
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )

        def guess_os_label(filename: str) -> str:
            n = filename.lower()
            if "server" in n or "2k" in n:
                if "2012" in n or "2k12" in n:
                    return "Windows Server 2012 R2"
                if "2016" in n or "2k16" in n:
                    return "Windows Server 2016"
                if "2019" in n or "2k19" in n:
                    return "Windows Server 2019"
                if "2022" in n or "2k22" in n:
                    return "Windows Server 2022"
                if "2025" in n or "2k25" in n:
                    return "Windows Server 2025"

            if "tiny11" in n:
                return "Tiny11 23H2"
            if "tiny10" in n:
                return "Tiny10 23H2"

            if "superlite" in n:
                if "11" in n:
                    return "Windows 11 SuperLite"
                return "Windows 10 SuperLite"

            if "atlas" in n:
                if "11" in n:
                    return "Windows 11 Atlas"
                return "Windows 10 Atlas"

            if "pro" in n:
                if "11" in n:
                    return "Windows 11 Pro"
                if "10" in n:
                    return "Windows 10 Pro"

            if "win11" in n or "windows11" in n or "windows-11" in n:
                return "Windows 11"
            if "win10" in n or "windows10" in n or "windows-10" in n:
                return "Windows 10"

            return os.path.basename(filename)

        if result.returncode == 0 and (result.stdout or "").strip():
            lines = (result.stdout or "").strip().split("\n")
            image_paths: list[str] = []

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(";", 1)
                if len(parts) != 2:
                    continue
                _, path = parts[0].strip(), parts[1].strip()
                base = os.path.basename(path)
                low = base.lower()
                if low.endswith(".img") or low.endswith(".img.gz"):
                    image_paths.append(path)

            if not image_paths:
                text = f"""📋 <b>DAFTAR OS IMAGE (GDRIVE)</b>
━━━━━━━━━━━━━━━━━━

Tidak ada file <code>.img</code>/<code>.img.gz</code> di:
<code>gdrive:{folder}/</code>

Total OS: 0"""
            else:
                os_set = {}
                for p in image_paths:
                    label = guess_os_label(os.path.basename(p))
                    os_set[label] = True

                os_list = sorted(os_set.keys())
                text = f"""📋 <b>DAFTAR OS IMAGE (GDRIVE)</b>
━━━━━━━━━━━━━━━━━━

""" + "\n".join([f"• {name}" for name in os_list]) + f"\n\nTotal OS: {len(os_list)}"
        else:
            error_info = result.stderr[:200] if result.stderr else "Folder kosong"
            text = f"""📋 <b>DAFTAR OS IMAGE (GDRIVE)</b>
━━━━━━━━━━━━━━━━━━

Folder kosong atau error.

<code>{error_info}</code>"""

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="gdrive_list"))
        markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="gdrive_menu"))

        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data == "gdrive_list")
def gdrive_list_menu(call):
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    bot.answer_callback_query(call.id, "⏳ Mengambil daftar file...")
    threading.Thread(target=_list_gdrive_files, args=(call.message.chat.id,), daemon=True).start()

@bot.message_handler(commands=['gdrivelist'])
def gdrive_list_cmd(message):
    """Command /gdrivelist - List file di Google Drive"""
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    bot.reply_to(message, "⏳ Mengambil daftar file...")
    threading.Thread(target=_list_gdrive_files, args=(message.chat.id,), daemon=True).start()

# ==================== GDRIVE DELETE ====================
@bot.callback_query_handler(func=lambda call: call.data == "gdrive_delete")
def gdrive_delete_menu(call):
    """Tampilkan daftar image di GDrive untuk dihapus"""
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    bot.answer_callback_query(call.id, "⏳ Mengambil daftar image...")

    # Cek rclone config
    rclone_conf = os.path.expanduser("~/.config/rclone/rclone.conf")
    if not os.path.exists(rclone_conf):
        bot.edit_message_text(
            """❌ <b>GDrive belum dikonfigurasi!</b>

Setup dulu di menu:
⚙️ Settings Owner → ☁️ Google Drive Manager → Setup Rclone""",
            call.message.chat.id, call.message.message_id, parse_mode="HTML"
        )
        return

    def list_for_delete():
        try:
            # List images dari GDrive
            result = subprocess.run(
                ["rclone", "lsf", "gdrive:rdp-images/", "--format", "ps"],
                capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                bot.send_message(call.message.chat.id, f"❌ Error: {result.stderr[:300]}")
                return

            output = result.stdout.strip()
            files = []

            for line in output.split('\n'):
                if line.strip():
                    parts = line.split(';')
                    if len(parts) >= 2:
                        size = parts[0].strip()
                        name = parts[1].strip()
                        if name:
                            # Tandai golden image vs regular
                            is_golden = name.startswith("golden-") or "golden" in name.lower()
                            files.append((name, size, is_golden))

            if not files:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="gdrive_menu"))
                bot.send_message(call.message.chat.id, """📋 <b>TIDAK ADA IMAGE</b>

Folder rdp-images/ kosong.""", parse_mode="HTML", reply_markup=markup)
                return

            # Pisahkan golden dan regular
            golden_files = [(n, s) for n, s, g in files if g]
            regular_files = [(n, s) for n, s, g in files if not g]

            text = """🗑 <b>HAPUS IMAGE DARI GDRIVE</b>
━━━━━━━━━━━━━━━━━━

"""
            if golden_files:
                text += "🏆 <b>Golden Images:</b>\n"
                for name, size in golden_files:
                    text += f"  📦 <code>{name}</code> ({size})\n"
                text += "\n"

            if regular_files:
                text += "📁 <b>Regular Images:</b>\n"
                for name, size in regular_files:
                    text += f"  📦 <code>{name}</code> ({size})\n"
                text += "\n"

            text += "⚠️ <b>Klik untuk HAPUS (tidak bisa dikembalikan!):</b>"

            markup = types.InlineKeyboardMarkup()

            # Tombol hapus untuk regular images (prioritas hapus)
            for name, size in regular_files[:8]:
                short_name = name[:25] + "..." if len(name) > 25 else name
                markup.add(types.InlineKeyboardButton(
                    f"🗑 {short_name}",
                    callback_data=f"del_img:{name[:50]}"
                ))

            # Tombol hapus untuk golden images
            for name, size in golden_files[:5]:
                short_name = name[:22] + "..." if len(name) > 22 else name
                markup.add(types.InlineKeyboardButton(
                    f"🗑🏆 {short_name}",
                    callback_data=f"del_img:{name[:50]}"
                ))

            markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="gdrive_menu"))

            bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=list_for_delete, daemon=True).start()

# ==================== CONFIRM DELETE IMAGE ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("del_img:"))
def confirm_delete_image(call):
    """Konfirmasi hapus image"""
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    filename = call.data.replace("del_img:", "")
    bot.answer_callback_query(call.id)

    is_golden = filename.startswith("golden-") or "golden" in filename.lower()
    warning = "\n\n🏆 <b>INI GOLDEN IMAGE!</b> Yakin mau hapus?" if is_golden else ""

    text = f"""⚠️ <b>KONFIRMASI HAPUS</b>
━━━━━━━━━━━━━━━━━━

📁 <b>File:</b> <code>{filename}</code>
{warning}

<b>File yang dihapus TIDAK BISA dikembalikan!</b>

Yakin hapus file ini?"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "✅ Ya, Hapus!", 
        callback_data=f"confirm_del:{filename[:50]}"
    ))
    markup.add(types.InlineKeyboardButton("❌ Batal", callback_data="gdrive_delete"))

    bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=markup)

# ==================== EXECUTE DELETE ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_del:"))
def execute_delete_image(call):
    """Eksekusi hapus image dari GDrive"""
    if not is_owner(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Hanya untuk owner!")
        return

    filename = call.data.replace("confirm_del:", "")
    bot.answer_callback_query(call.id, f"⏳ Menghapus {filename}...")

    bot.send_message(call.message.chat.id, f"""🗑 <b>MENGHAPUS...</b>

📁 <code>{filename}</code>

⏳ Mohon tunggu...""", parse_mode="HTML")

    def do_delete():
        try:
            # Coba beberapa metode delete
            # Method 1: rclone delete dengan path lengkap
            full_path = f"gdrive:rdp-images/{filename}"
            
            # Cek dulu apakah file ada
            check_result = subprocess.run(
                ["rclone", "lsf", "gdrive:rdp-images/", "--include", filename],
                capture_output=True, text=True, timeout=30
            )
            
            file_exists = filename in check_result.stdout
            
            if not file_exists:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🔄 Refresh List", callback_data="gdrive_delete"))
                markup.add(types.InlineKeyboardButton("◀️ Menu GDrive", callback_data="gdrive_menu"))
                
                bot.send_message(call.message.chat.id, f"""⚠️ <b>FILE TIDAK DITEMUKAN</b>

📁 <code>{filename}</code>

File mungkin sudah dihapus atau nama berubah.""", parse_mode="HTML", reply_markup=markup)
                return
            
            # Method: gunakan rclone delete dengan filter
            result = subprocess.run(
                ["rclone", "delete", "gdrive:rdp-images/", "--include", filename, "-v"],
                capture_output=True, text=True, timeout=120
            )
            
            # Verifikasi apakah file sudah terhapus
            verify_result = subprocess.run(
                ["rclone", "lsf", "gdrive:rdp-images/", "--include", filename],
                capture_output=True, text=True, timeout=30
            )
            
            file_deleted = filename not in verify_result.stdout
            
            if file_deleted:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🗑 Hapus Lainnya", callback_data="gdrive_delete"))
                markup.add(types.InlineKeyboardButton("◀️ Menu GDrive", callback_data="gdrive_menu"))

                bot.send_message(call.message.chat.id, f"""✅ <b>BERHASIL DIHAPUS!</b>

📁 <code>{filename}</code>

File sudah dihapus dari Google Drive.""", parse_mode="HTML", reply_markup=markup)
            else:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
                bot.send_message(call.message.chat.id, f"""❌ <b>GAGAL HAPUS!</b>

📁 <code>{filename}</code>

<code>{error_msg[:500] if error_msg else 'Unknown error'}</code>

Coba hapus manual: <code>rclone delete gdrive:rdp-images/{filename}</code>""", parse_mode="HTML")

        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error: {str(e)}")

    threading.Thread(target=do_delete, daemon=True).start()

@bot.message_handler(commands=['deletegdrive'])
def delete_from_gdrive(message):
    if not is_owner(message.from_user.id):
        bot.reply_to(message, "⛔ Hanya owner!")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Format: /deletegdrive [path_file]\n\nAtau gunakan menu: Settings → GDrive → Delete Image")
            return

        file_path = parts[1]

        bot.reply_to(message, f"⏳ Menghapus {file_path}...")

        def do_delete():
            try:
                # Gunakan deletefile untuk file tunggal
                result = subprocess.run(
                    ["rclone", "deletefile", f"gdrive:{file_path}"],
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
                    error_msg = result.stderr.strip()
                    if "not found" in error_msg.lower():
                        bot.send_message(message.chat.id, f"⚠️ File tidak ditemukan (mungkin sudah dihapus):\n{file_path}")
                    else:
                        bot.send_message(message.chat.id, f"❌ Gagal menghapus:\n<code>{error_msg[:500]}</code>", parse_mode="HTML")
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
