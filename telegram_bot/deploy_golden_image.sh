#!/bin/bash

# Deploy Golden Image Script
# Deploy golden image ke VPS user dalam 1-2 menit
# Usage: bash deploy_golden_image.sh [IP] [PASSWORD] [IMAGE_NAME] [CHAT_ID] [BOT_TOKEN]

IP=$1
PASSWORD=$2
IMAGE_PATH=$3  # contoh: win10-golden.img.gz atau folder/win10-golden.img.gz
CHAT_ID=$4
BOT_TOKEN=$5

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
if [ -z "$IP" ] || [ -z "$PASSWORD" ] || [ -z "$IMAGE_PATH" ]; then
    echo "Usage: bash deploy_golden_image.sh [IP] [PASSWORD] [IMAGE_PATH] [CHAT_ID] [BOT_TOKEN]"
    exit 1
fi

IMAGE_BASENAME=$(basename "$IMAGE_PATH")

echo "================================================"
echo "🚀 DEPLOY GOLDEN IMAGE"
echo "================================================"
echo "📍 Target IP: $IP"
echo "📦 Image: $IMAGE_PATH"
echo "================================================"

# Install sshpass
apt-get install -y sshpass > /dev/null 2>&1

# Test koneksi
echo "🔌 Testing koneksi ke VPS..."
if ! sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 root@"$IP" "echo 'connected'" 2>/dev/null; then
    echo "❌ Gagal konek ke VPS"
    send_telegram "❌ <b>DEPLOY GAGAL!</b>

📍 <b>IP:</b> <code>$IP</code>
📦 <b>Image:</b> $IMAGE_BASENAME

<b>Penyebab:</b> Tidak bisa konek ke VPS

<b>Solusi:</b>
1. Cek IP benar
2. Cek password benar
3. Cek VPS menyala
4. Cek port 22 terbuka"
    exit 1
fi

echo "✅ Koneksi berhasil!"
send_telegram "🚀 <b>DEPLOY GOLDEN IMAGE</b>
━━━━━━━━━━━━━━━━━━

📍 <b>IP:</b> <code>$IP</code>
📦 <b>Image:</b> $IMAGE_BASENAME

⏳ Proses deploy dimulai...
Estimasi: 1-2 menit"

# Copy rclone config ke VPS user
RCLONE_CONF="$HOME/.config/rclone/rclone.conf"
if [ -f "$RCLONE_CONF" ]; then
    echo "📤 Syncing rclone config..."

    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@"$IP" << 'RCLONE_SETUP'
apt-get update -qq
apt-get install -y rclone pigz pv > /dev/null 2>&1
mkdir -p ~/.config/rclone
RCLONE_SETUP

    sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=no "$RCLONE_CONF" root@"$IP":~/.config/rclone/rclone.conf
fi

# Deploy image ke VPS user
echo "🚀 Deploying image..."
START_TIME=$(date +%s)

sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 root@"$IP" "IMAGE_PATH='$IMAGE_PATH' bash -s" << 'DEPLOY_SCRIPT'
set -e

echo "📥 Downloading golden image from GDrive..."

# Cek target disk
TARGET_DISK="/dev/vda"
if [ ! -b "$TARGET_DISK" ]; then
    TARGET_DISK="/dev/sda"
fi

if [ ! -b "$TARGET_DISK" ]; then
    echo "❌ Target disk tidak ditemukan!"
    exit 1
fi

echo "💿 Target disk: $TARGET_DISK"

cd /tmp

# Download dan extract langsung ke disk
if echo "$IMAGE_PATH" | grep -qi "\.img\.gz$"; then
    echo "📥 Streaming $IMAGE_PATH (.img.gz)..."
    rclone cat "gdrive:rdp-images/$IMAGE_PATH" | gunzip | dd of="$TARGET_DISK" bs=4M status=progress
elif echo "$IMAGE_PATH" | grep -qi "\.img$"; then
    echo "📥 Streaming $IMAGE_PATH (.img)..."
    rclone cat "gdrive:rdp-images/$IMAGE_PATH" | dd of="$TARGET_DISK" bs=4M status=progress
else
    echo "❌ Format image tidak didukung: $IMAGE_PATH"
    exit 1
fi

# Sync dan resize partition
sync
echo "🔧 Resizing partition..."
growpart "$TARGET_DISK" 1 2>/dev/null || true

# Cleanup rclone config (security)
rm -rf ~/.config/rclone ~/.rclone.conf

echo "DEPLOY_SUCCESS"
DEPLOY_SCRIPT

# Sync dan resize partition
sync
echo "🔧 Resizing partition..."
growpart "$TARGET_DISK" 1 2>/dev/null || true

# Cleanup rclone config (security)
rm -rf ~/.config/rclone ~/.rclone.conf

echo "DEPLOY_SUCCESS"
DEPLOY_SCRIPT

RESULT=$?
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Cleanup rclone config di VPS user (double check)
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@"$IP" "rm -rf ~/.config/rclone ~/.rclone.conf 2>/dev/null" 2>/dev/null || true

if [ $RESULT -eq 0 ]; then
    echo ""
    echo "================================================"
    echo "✅ DEPLOY BERHASIL! (${DURATION} detik)"
    echo "================================================"
    echo ""
    echo "⚠️ VPS akan reboot dalam 5 detik..."
    
    # Reboot VPS
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@"$IP" "sleep 5 && reboot" &
    
    send_telegram "✅ <b>DEPLOY BERHASIL!</b>
━━━━━━━━━━━━━━━━━━

📍 <b>IP:</b> <code>$IP</code>
📦 <b>Image:</b> $IMAGE_NAME
⏱ <b>Waktu:</b> ${DURATION} detik

<b>Akses RDP:</b>
• IP: <code>$IP</code>
• Port: <code>3389</code>

<b>Kredensial Default:</b>
• Username: <code>Admin</code>
• Password: <code>Admin@123</code>

⚠️ <b>PENTING:</b> Segera ganti password setelah login!

🔄 VPS sedang reboot, tunggu 1-2 menit lalu coba RDP."
    
    exit 0
else
    # Cleanup meski gagal
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@"$IP" "rm -rf ~/.config/rclone ~/.rclone.conf 2>/dev/null" 2>/dev/null || true
    
    send_telegram "❌ <b>DEPLOY GAGAL!</b>

📍 <b>IP:</b> <code>$IP</code>
📦 <b>Image:</b> $IMAGE_NAME

<b>Kemungkinan penyebab:</b>
1. Image tidak ada di GDrive
2. Disk space tidak cukup
3. Koneksi terputus

Coba lagi atau hubungi owner."
    exit 1
fi
