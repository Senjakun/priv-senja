#!/bin/bash

# Docker RDP Installer - Optimized for 2GB RAM
# Usage: bash rdp_docker.sh [IP] [PASSWORD] [WIN_CODE] [CHAT_ID] [BOT_TOKEN]

IP=$1
PASSWORD=$2
WIN_CODE=$3
CHAT_ID=$4
BOT_TOKEN=$5

# Map WIN_CODE to actual version
case $WIN_CODE in
    1) WIN_VER="2k12" ;;
    2) WIN_VER="2k16" ;;
    3) WIN_VER="2k19" ;;
    4) WIN_VER="2k22" ;;
    5) WIN_VER="2k25" ;;
    6) WIN_VER="ltsc10" ;;
    7) WIN_VER="11" ;;
    8) WIN_VER="ltsc10" ;;
    9) WIN_VER="11" ;;
    10) WIN_VER="10" ;;
    11) WIN_VER="11" ;;
    12) WIN_VER="tiny10" ;;
    13) WIN_VER="tiny11" ;;
    *) WIN_VER="ltsc10" ;;
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
echo "🐳 Docker RDP Installer"
echo "📍 IP: $IP"
echo "🪟 Windows: $WIN_VER"
echo "================================================"

# Install sshpass
apt-get install -y sshpass > /dev/null 2>&1

# Test koneksi dulu
echo "🔌 Testing koneksi ke VPS..."
if ! sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=no root@"$IP" "echo 'connected'" 2>/dev/null; then
    echo "❌ Gagal konek ke VPS"
    send_telegram "❌ <b>INSTALASI GAGAL!</b>

📍 <b>IP:</b> <code>$IP</code>

<b>Penyebab:</b> Tidak bisa konek ke VPS

<b>Solusi:</b>
1. Cek IP benar
2. Cek password benar
3. Cek VPS menyala
4. Cek port 22 terbuka"
    exit 1
fi

echo "✅ Koneksi berhasil!"

# Install Docker dan jalankan Windows
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@"$IP" "WIN_VER='$WIN_VER' PASSWORD='$PASSWORD' bash -s" << 'ENDSSH'
set -e

echo "📦 Update sistem..."
apt-get update -y > /dev/null 2>&1
apt-get install -y curl wget > /dev/null 2>&1

# Cek RAM
RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
echo "💾 RAM: ${RAM_MB}MB"

if [ "$RAM_MB" -lt 1800 ]; then
    echo "❌ RAM kurang dari 2GB!"
    exit 2
fi

# Cek KVM support
if [ ! -e /dev/kvm ]; then
    echo "⚠️ KVM tidak tersedia, mencoba tanpa KVM..."
    KVM_FLAG=""
else
    echo "✅ KVM tersedia"
    KVM_FLAG="--device=/dev/kvm"
fi

# Install Docker jika belum ada
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com | sh > /dev/null 2>&1
    systemctl enable docker > /dev/null 2>&1
    systemctl start docker
fi

# Stop container lama jika ada
docker stop windows 2>/dev/null || true
docker rm windows 2>/dev/null || true

echo "📥 Pulling Windows image..."
docker pull dockurr/windows:latest

echo "🚀 Starting Windows container..."
docker run -d \
    --name windows \
    $KVM_FLAG \
    --cap-add NET_ADMIN \
    -p 8006:8006 \
    -p 3389:3389/tcp \
    -p 3389:3389/udp \
    -e RAM_SIZE="1.5G" \
    -e CPU_CORES="2" \
    -e DISK_SIZE="20G" \
    -e VERSION="$WIN_VER" \
    -v /windows:/storage \
    --restart unless-stopped \
    dockurr/windows

echo "✅ Container started!"
echo "INSTALL_SUCCESS"
ENDSSH

RESULT=$?

if [ $RESULT -eq 0 ]; then
    echo "✅ Instalasi berhasil!"
    send_telegram "✅ <b>INSTALASI BERHASIL!</b>
━━━━━━━━━━━━━━━━━━

📦 <b>Tipe:</b> 🐳 Docker RDP
📍 <b>IP:</b> <code>$IP</code>
🪟 <b>Windows:</b> $WIN_VER

<b>Akses RDP:</b>
• IP: <code>$IP</code>
• Port RDP: <code>3389</code>
• Port Web: <code>8006</code>

<b>Web Interface:</b>
http://$IP:8006

<b>Kredensial Default:</b>
• Username: <code>Docker</code>
• Password: (set saat pertama login)

⚠️ Windows membutuhkan 5-10 menit untuk boot pertama kali."
    exit 0
elif [ $RESULT -eq 2 ]; then
    send_telegram "❌ <b>INSTALASI GAGAL!</b>

📍 <b>IP:</b> <code>$IP</code>

<b>Penyebab:</b> RAM kurang dari 2GB

<b>Solusi:</b> Gunakan VPS dengan RAM minimal 2GB"
    exit 1
else
    send_telegram "❌ <b>INSTALASI GAGAL!</b>

📍 <b>IP:</b> <code>$IP</code>

<b>Penyebab:</b> Error saat instalasi

<b>Solusi:</b>
1. Pastikan VPS fresh (baru install OS)
2. Gunakan Ubuntu 22.04 atau Debian 12
3. Coba lagi dalam beberapa menit"
    exit 1
fi
