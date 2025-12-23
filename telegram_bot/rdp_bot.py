#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RDP Installer Telegram Bot
Fitur:
- Hanya owner & user yang diizinkan yang bisa akses
- Install RDP dengan pilihan Windows
- Link Owner & Channel bisa diedit
"""

import telebot
from telebot import types
import json
import os
import subprocess

# ==================== KONFIGURASI ====================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Ganti di VPS, jangan di sini!
OWNER_ID = 123456789  # Ganti dengan Telegram ID kamu

# File untuk menyimpan data
DATA_FILE = "bot_data.json"

# ==================== LOAD/SAVE DATA ====================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        "allowed_users": [OWNER_ID],
        "owner_link": "https://t.me/username_owner",
        "channel_link": "https://t.me/channel_name"
    }

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ==================== INISIALISASI ====================
bot = telebot.TeleBot(BOT_TOKEN)
data = load_data()

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

    text = """🖥 <b>Silahkan Pilih Versi Windows Anda</b> 🖥

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

    markup = types.InlineKeyboardMarkup(row_width=3)

    # Baris 1-4 (tombol 1-12)
    row1 = [types.InlineKeyboardButton(str(i), callback_data=f"win_{i}") for i in range(1, 4)]
    row2 = [types.InlineKeyboardButton(str(i), callback_data=f"win_{i}") for i in range(4, 7)]
    row3 = [types.InlineKeyboardButton(str(i), callback_data=f"win_{i}") for i in range(7, 10)]
    row4 = [types.InlineKeyboardButton(str(i), callback_data=f"win_{i}") for i in range(10, 13)]

    markup.row(*row1)
    markup.row(*row2)
    markup.row(*row3)
    markup.row(*row4)
    markup.add(types.InlineKeyboardButton("13", callback_data="win_13"))
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="back_main"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

# ==================== PILIH WINDOWS ====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("win_"))
def select_windows(call):
    if not is_allowed(call.from_user.id):
        bot.answer_callback_query(call.id, "⛔ Akses ditolak!")
        return

    win_num = call.data.replace("win_", "")
    win_name = WINDOWS_OPTIONS.get(win_num, "Unknown")

    text = f"""✅ <b>Windows Dipilih:</b> {win_name}

Sekarang kirim IP dan Password VPS dengan format:
<code>/install IP PASSWORD</code>

Contoh: <code>/install 123.456.78.90 password123</code>"""

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("◀️ Kembali", callback_data="install_rdp"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

    # Simpan pilihan user (opsional)
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

    text = f"""⚙️ <b>OWNER SETTINGS</b>
━━━━━━━━━━━━━━━━━━

👥 <b>Total User:</b> {user_count}
🔗 <b>Owner Link:</b> {data["owner_link"]}
📢 <b>Channel Link:</b> {data["channel_link"]}

<b>Commands:</b>
/adduser [id] - Tambah user
/deluser [id] - Hapus user
/setowner [link] - Set link owner
/setchannel [link] - Set link channel
/listuser - Lihat daftar user"""

    markup = types.InlineKeyboardMarkup()
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

        bot.reply_to(message, f"⏳ Memulai instalasi RDP...\nIP: {ip}")

        # Jalankan script instalasi (pakai path absolut agar tidak tergantung folder saat menjalankan bot)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(script_dir, "rdp.sh")

        if not os.path.exists(script_path):
            bot.reply_to(message, "❌ File rdp.sh tidak ditemukan (telegram_bot/rdp.sh). Pastikan sudah git pull.")
            return

        subprocess.run(["chmod", "+x", script_path], check=False)
        with open(os.path.join(script_dir, "rdp_install.log"), "ab") as log:
            subprocess.Popen(["bash", script_path, ip, password], stdout=log, stderr=log, start_new_session=True)

        bot.send_message(message.chat.id, "✅ Proses instalasi dimulai!\nTunggu beberapa menit sampai selesai.")

    except:
        bot.reply_to(message, "❌ Format: /install [IP] [PASSWORD]\nContoh: /install 123.456.78.90 password123")

# ==================== RUN BOT ====================
if __name__ == "__main__":
    print("🤖 Bot sedang berjalan...")
    bot.infinity_polling()
