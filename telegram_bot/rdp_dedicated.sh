#!/bin/bash

# Dedicated RDP Installer - Download from GDrive
# Usage: bash rdp_dedicated.sh [IP] [PASSWORD] [WIN_CODE] [CHAT_ID] [BOT_TOKEN] [GDRIVE_IMAGE]

IP=$1
PASSWORD=$2
WIN_CODE=$3
CHAT_ID=$4
BOT_TOKEN=$5
GDRIVE_IMAGE=$6  # Nama file image di GDrive (optional)

# Map WIN_CODE to name
case $WIN_CODE in
    1) WIN_NAME="Windows Server 2012 R2" ;;
    2) WIN_NAME="Windows Server 2016" ;;
    3) WIN_NAME="Windows Server 2019" ;;
    4) WIN_NAME="Windows Server 2022" ;;
    5) WIN_NAME="Windows Server 2025" ;;
    6) WIN_NAME="Windows 10 SuperLite" ;;
    7) WIN_NAME="Windows 11 SuperLite" ;;
    8) WIN_NAME="Windows 10 Atlas" ;;
    9) WIN_NAME="Windows 11 Atlas" ;;
    10) WIN_NAME="Windows 10 Pro" ;;
    11) WIN_NAME="Windows 11 Pro" ;;
    12) WIN_NAME="Tiny10 23H2" ;;
    13) WIN_NAME="Tiny11 23H2" ;;
    *) WIN_NAME="Windows 10" ;;
esac

send_telegram() {
    local message="$1"
    if [ -n "$BOT_TOKEN" ] && [ -n "$CHAT_ID" ]; then
        curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
            -d chat_id="$CHAT_ID" \
            -d text="$message" \
            -d parse_mode="HTML" > /dev/null 2>&1
    fi
}

# Validasi
if [ -z "$IP" ] || [ -z "$PASSWORD" ]; then
    echo "Error: IP dan PASSWORD harus diisi"
    exit 1
fi

echo "================================================"
echo "🖥 Dedicated RDP Installer"
echo "📍 IP: $IP"
echo "🪟 Windows: $WIN_NAME ($WIN_CODE)"
if [ -n "$GDRIVE_IMAGE" ]; then
    echo "☁️ GDrive Image: $GDRIVE_IMAGE"
fi
echo "================================================"

# Install sshpass
apt-get install -y sshpass > /dev/null 2>&1

# Test koneksi
echo "🔌 Testing koneksi ke VPS..."
if ! sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=no root@"$IP" "echo 'connected'" 2>/dev/null; then
    echo "❌ Gagal konek ke VPS"
    send_telegram "❌ <b>INSTALASI GAGAL!</b>

📍 <b>IP:</b> <code>$IP</code>
🪟 <b>Windows:</b> $WIN_NAME

<b>Penyebab:</b> Tidak bisa konek ke VPS

<b>Solusi:</b>
1. Cek IP benar
2. Cek password benar
3. Cek VPS menyala
4. Cek port 22 terbuka"
    exit 1
fi

echo "✅ Koneksi berhasil!"
send_telegram "🔌 <b>VPS Terhubung</b>

📍 <b>IP:</b> <code>$IP</code>
🪟 <b>Windows:</b> $WIN_NAME

⏳ Proses instalasi sedang berjalan...
Mohon tunggu 15-30 menit."

# Copy rclone config dari bot server ke VPS user (jika ada)
RCLONE_CONF="$HOME/.config/rclone/rclone.conf"
if [ -f "$RCLONE_CONF" ] && [ -n "$GDRIVE_IMAGE" ]; then
    echo "📤 Syncing rclone config ke VPS user..."
    
    # Install rclone di VPS user
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@"$IP" << 'RCLONE_INSTALL'
if ! command -v rclone &> /dev/null; then
    apt-get update -qq
    apt-get install -y rclone > /dev/null 2>&1 || curl -s https://rclone.org/install.sh | bash > /dev/null 2>&1
fi
mkdir -p ~/.config/rclone
RCLONE_INSTALL
    
    # Copy rclone.conf
    sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no "$RCLONE_CONF" root@"$IP":~/.config/rclone/rclone.conf
    
    echo "✅ Rclone config synced"
fi

# Jalankan instalasi
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=30 root@"$IP" "WIN_CODE='$WIN_CODE' GDRIVE_IMAGE='$GDRIVE_IMAGE' bash -s" << 'ENDSSH'
set -e

echo "📦 Update sistem..."
apt-get update -y
apt-get install -y wget curl bzip2

# Cek RAM
RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
echo "💾 RAM: ${RAM_MB}MB"

if [ "$RAM_MB" -lt 1800 ]; then
    echo "RAM_ERROR"
    exit 2
fi

# Cek disk space
DISK_GB=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
echo "💿 Free Disk: ${DISK_GB}GB"

if [ "$DISK_GB" -lt 20 ]; then
    echo "DISK_ERROR"
    exit 3
fi

# Download image dari GDrive jika ada
if [ -n "$GDRIVE_IMAGE" ]; then
    echo "☁️ Downloading image dari GDrive..."
    mkdir -p /root/rdp-images
    
    if command -v rclone &> /dev/null && rclone listremotes | grep -q "gdrive:"; then
        rclone copy "gdrive:rdp-images/$GDRIVE_IMAGE" /root/rdp-images/ -P
        
        if [ -f "/root/rdp-images/$GDRIVE_IMAGE" ]; then
            echo "✅ Image downloaded: $GDRIVE_IMAGE"
            # Install menggunakan image yang didownload
            # TODO: Tambahkan logic install dari local image
        else
            echo "❌ Gagal download image dari GDrive"
        fi
    else
        echo "⚠️ Rclone/GDrive tidak tersedia, menggunakan installer online..."
    fi
fi

echo "📥 Downloading RDP installer..."
cd /tmp

# Download installer
wget -q https://raw.githubusercontent.com/Bintang73/auto-install-rdp/main/install.sh -O install.sh
chmod +x install.sh

echo "🔧 Installing RDP (this takes 15-30 minutes)..."
if [ -n "$WIN_CODE" ]; then
    printf "%s\n" "$WIN_CODE" | timeout 1800 ./install.sh
else
    timeout 1800 ./install.sh
fi

echo "INSTALL_SUCCESS"

# SECURITY: Hapus rclone config setelah download selesai
echo "🔒 Cleaning up rclone config..."
rm -rf ~/.config/rclone
rm -f ~/.rclone.conf
echo "✅ Rclone config dihapus dari VPS user"
ENDSSH

RESULT=$?

# SECURITY: Pastikan rclone config dihapus dari VPS user (double check)
if [ -n "$GDRIVE_IMAGE" ]; then
    echo "🔒 Double-check: Menghapus rclone config dari VPS user..."
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@"$IP" "rm -rf ~/.config/rclone ~/.rclone.conf /root/.config/rclone 2>/dev/null; echo 'Cleaned'" 2>/dev/null || true
fi

if [ $RESULT -eq 0 ]; then
    echo "✅ Instalasi berhasil!"
    send_telegram "✅ <b>INSTALASI BERHASIL!</b>
━━━━━━━━━━━━━━━━━━

📦 <b>Tipe:</b> 🖥 Dedicated RDP
📍 <b>IP:</b> <code>$IP</code>
🪟 <b>Windows:</b> $WIN_NAME

<b>Akses RDP:</b>
• IP: <code>$IP</code>
• Port: <code>3389</code>

<b>Kredensial:</b>
• Username: <code>Administrator</code>
• Password: <code>$PASSWORD</code>

🎉 Selamat! RDP sudah siap digunakan."
    exit 0
elif [ $RESULT -eq 2 ]; then
    send_telegram "❌ <b>INSTALASI GAGAL!</b>

📍 <b>IP:</b> <code>$IP</code>
🪟 <b>Windows:</b> $WIN_NAME

<b>Penyebab:</b> RAM kurang dari 2GB

<b>Solusi:</b> Gunakan VPS dengan RAM minimal 2GB"
    exit 1
elif [ $RESULT -eq 3 ]; then
    send_telegram "❌ <b>INSTALASI GAGAL!</b>

📍 <b>IP:</b> <code>$IP</code>
🪟 <b>Windows:</b> $WIN_NAME

<b>Penyebab:</b> Disk space kurang dari 20GB

<b>Solusi:</b> Gunakan VPS dengan disk minimal 25GB"
    exit 1
else
    # Tetap hapus rclone config meski gagal
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@"$IP" "rm -rf ~/.config/rclone ~/.rclone.conf /root/.config/rclone 2>/dev/null" 2>/dev/null || true
    
    send_telegram "❌ <b>INSTALASI GAGAL!</b>

📍 <b>IP:</b> <code>$IP</code>
🪟 <b>Windows:</b> $WIN_NAME

<b>Penyebab:</b> Error saat instalasi atau koneksi terputus

<b>Solusi:</b>
1. Pastikan VPS stabil
2. Gunakan Ubuntu 22.04 atau Debian 12
3. Pastikan RAM minimal 2GB
4. Coba lagi"
    exit 1
fi
