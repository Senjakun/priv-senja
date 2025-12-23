#!/bin/bash

# RDP Auto Installer - Called by Telegram Bot
# Usage: bash rdp.sh [IP] [PASSWORD] [WIN_CODE]

IP=$1
PASSWORD=$2
WIN_CODE=$3

# Validasi parameter
if [ -z "$IP" ] || [ -z "$PASSWORD" ]; then
    echo "Error: IP dan PASSWORD harus diisi"
    exit 1
fi

echo "================================================"
echo "🚀 Memulai instalasi RDP..."
echo "📍 Target IP: $IP"
echo "🪟 Windows: $WIN_CODE"
echo "================================================"

# Install sshpass jika belum ada
apt-get install -y sshpass > /dev/null 2>&1

# SSH ke VPS target dan jalankan instalasi RDP
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@$IP << 'ENDSSH'
    echo "📦 Mengupdate sistem..."
    apt update -y
    apt install -y bzip2 wget

    echo "📥 Mendownload installer RDP..."
    wget -q https://github.com/Bintang73/auto-install-rdp/raw/refs/heads/main/main -O /tmp/rdp_setup
    chmod +x /tmp/rdp_setup

    echo "🔧 Menjalankan instalasi RDP..."
    cd /tmp && ./rdp_setup

    echo "✅ Instalasi selesai!"
ENDSSH

if [ $? -eq 0 ]; then
    echo "================================================"
    echo "✅ RDP berhasil diinstal di $IP"
    echo "🔑 Password: $PASSWORD"
    echo "================================================"
else
    echo "❌ Gagal menginstal RDP. Periksa IP dan password."
    exit 1
fi
