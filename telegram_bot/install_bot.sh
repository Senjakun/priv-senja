#!/bin/bash
# ==========================================
# RDP BOT INSTALLER - One Click Setup
# ==========================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║     RDP TELEGRAM BOT INSTALLER        ║"
echo "║         One Click Setup               ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}"

# Check root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Jalankan sebagai root!${NC}"
    echo "Gunakan: sudo bash install_bot.sh"
    exit 1
fi

# Get user input
echo -e "${YELLOW}📝 Masukkan konfigurasi bot:${NC}"
echo ""

read -p "🔑 Bot Token (dari @BotFather): " BOT_TOKEN
read -p "👤 Owner Telegram ID: " OWNER_ID
read -p "📂 GitHub Repo URL (kosongkan jika lokal): " GITHUB_REPO

INSTALL_DIR="/root/rdp-bot"

echo ""
echo -e "${BLUE}⏳ Menginstall dependencies...${NC}"

# Update & install dependencies
apt update -qq
apt install -y python3 python3-pip git sshpass curl > /dev/null 2>&1

# Install Python packages
pip3 install pyTeleBot paramiko requests -q

echo -e "${GREEN}✅ Dependencies terinstall${NC}"

# Clone or copy repo
if [ -n "$GITHUB_REPO" ]; then
    echo -e "${BLUE}⏳ Cloning dari GitHub...${NC}"
    rm -rf $INSTALL_DIR
    git clone $GITHUB_REPO $INSTALL_DIR
else
    echo -e "${BLUE}⏳ Menggunakan file lokal...${NC}"
    mkdir -p $INSTALL_DIR
    # Copy current directory files if exists
    if [ -f "rdp_bot.py" ]; then
        cp -r ./* $INSTALL_DIR/
    elif [ -f "telegram_bot/rdp_bot.py" ]; then
        cp -r telegram_bot/* $INSTALL_DIR/
    fi
fi

# Update config in bot file
BOT_FILE="$INSTALL_DIR/rdp_bot.py"
if [ ! -f "$BOT_FILE" ] && [ -f "$INSTALL_DIR/telegram_bot/rdp_bot.py" ]; then
    BOT_FILE="$INSTALL_DIR/telegram_bot/rdp_bot.py"
fi

if [ -f "$BOT_FILE" ]; then
    echo -e "${BLUE}⏳ Mengupdate konfigurasi...${NC}"
    sed -i "s/BOT_TOKEN = .*/BOT_TOKEN = \"$BOT_TOKEN\"/" $BOT_FILE
    sed -i "s/OWNER_ID = .*/OWNER_ID = $OWNER_ID/" $BOT_FILE
    echo -e "${GREEN}✅ Konfigurasi diupdate${NC}"
else
    echo -e "${RED}❌ File rdp_bot.py tidak ditemukan!${NC}"
    exit 1
fi

# Create systemd service
echo -e "${BLUE}⏳ Membuat systemd service...${NC}"

cat > /etc/systemd/system/rdpbot.service << EOF
[Unit]
Description=RDP Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$(dirname $BOT_FILE)
ExecStart=/usr/bin/python3 $(basename $BOT_FILE)
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable rdpbot
systemctl start rdpbot

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ✅ INSTALASI BERHASIL!            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}📍 Lokasi bot: $BOT_FILE${NC}"
echo ""
echo -e "${BLUE}📋 Commands:${NC}"
echo "   • Status  : systemctl status rdpbot"
echo "   • Stop    : systemctl stop rdpbot"
echo "   • Start   : systemctl start rdpbot"
echo "   • Restart : systemctl restart rdpbot"
echo "   • Logs    : journalctl -u rdpbot -f"
echo ""
echo -e "${BLUE}🔄 Update bot dari GitHub:${NC}"
echo "   cd $(dirname $BOT_FILE) && git pull && systemctl restart rdpbot"
echo ""

# Check if running
sleep 2
if systemctl is-active --quiet rdpbot; then
    echo -e "${GREEN}🤖 Bot sedang berjalan! Coba kirim /start di Telegram${NC}"
else
    echo -e "${RED}⚠️ Bot gagal start. Cek log: journalctl -u rdpbot -f${NC}"
fi
