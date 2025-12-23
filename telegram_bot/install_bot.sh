#!/bin/bash
# ==========================================
# RDP BOT INSTALLER - One Click Setup
# ==========================================

set -euo pipefail

# Non-interactive install (prevents stuck prompts on Ubuntu)
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

# Colors (define early for use in functions)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Retry helper (handles apt locks / slow mirrors)
run_with_retries() {
    local -r max_attempts="${1:-5}"; shift
    local attempt=1

    until "$@"; do
        if [ "$attempt" -ge "$max_attempts" ]; then
            echo -e "${RED}❌ Gagal menjalankan: $*${NC}"
            return 1
        fi
        echo -e "${YELLOW}⚠️  Gagal (percobaan ${attempt}/${max_attempts}). Coba lagi 10 detik...${NC}"
        attempt=$((attempt + 1))
        sleep 10
    done
}

# Wait for apt/dpkg locks (common on fresh VPS due to unattended upgrades)
wait_for_apt_locks() {
    local -r timeout_seconds="${1:-300}"
    local start_ts
    start_ts="$(date +%s)"

    while true; do
        local locked=0

        if command -v fuser >/dev/null 2>&1; then
            fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 && locked=1 || true
            fuser /var/lib/dpkg/lock >/dev/null 2>&1 && locked=1 || true
            fuser /var/lib/apt/lists/lock >/dev/null 2>&1 && locked=1 || true
            fuser /var/cache/apt/archives/lock >/dev/null 2>&1 && locked=1 || true
        else
            (pgrep -x apt >/dev/null 2>&1 || pgrep -x apt-get >/dev/null 2>&1 || pgrep -x dpkg >/dev/null 2>&1) && locked=1 || true
        fi

        if [ "$locked" -eq 0 ]; then
            return 0
        fi

        local now_ts
        now_ts="$(date +%s)"
        if [ $((now_ts - start_ts)) -ge "$timeout_seconds" ]; then
            echo -e "${RED}❌ Masih ada proses apt/dpkg yang mengunci sistem (> ${timeout_seconds}s).${NC}"
            echo -e "${YELLOW}➡️  Jalankan ini lalu ulangi installer:${NC}"
            echo "   systemctl stop apt-daily.service apt-daily-upgrade.service unattended-upgrades 2>/dev/null || true"
            echo "   killall apt apt-get dpkg 2>/dev/null || true"
            echo "   dpkg --configure -a"
            return 1
        fi

        echo -e "${YELLOW}⏳ Menunggu apt/dpkg lock dilepas...${NC}"
        sleep 5
    done
}

apt_get() {
    wait_for_apt_locks 300
    apt-get "$@"
}

# Install Python packages dengan berbagai metode
install_python_packages() {
    echo -e "${BLUE}⏳ Menginstall Python packages...${NC}"

    # Packages required by rdp_bot.py (GDrive feature uses rclone, not google-api-python-client)
    local packages="pyTelegramBotAPI paramiko requests"

    # Method 1: python3 -m pip dengan --break-system-packages (Ubuntu 23+)
    if python3 -m pip install --no-cache-dir --break-system-packages $packages 2>/dev/null; then
        return 0
    fi

    # Method 2: python3 -m pip tanpa --break-system-packages (Ubuntu 22 dan sebelumnya)
    if python3 -m pip install --no-cache-dir $packages 2>/dev/null; then
        return 0
    fi

    # Method 3: pip3 langsung dengan --break-system-packages
    if pip3 install --break-system-packages $packages 2>/dev/null; then
        return 0
    fi

    # Method 4: pip3 langsung
    if pip3 install $packages 2>/dev/null; then
        return 0
    fi

    # Method 5: Install pip dulu kalau belum ada
    echo -e "${YELLOW}⚠️  Mencoba install pip terlebih dahulu...${NC}"
    apt_get install -y python3-pip 2>/dev/null || true

    if pip3 install $packages 2>/dev/null; then
        return 0
    fi

    return 1
}

# Verify Python packages
verify_python_packages() {
    python3 -c "import telebot, paramiko, requests" 2>/dev/null
}


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
echo -e "${BLUE}⏳ Menginstall system dependencies...${NC}"

# Update & install dependencies
run_with_retries 5 apt_get update
run_with_retries 5 apt_get install -y \
  -o Dpkg::Options::=--force-confdef \
  -o Dpkg::Options::=--force-confold \
  python3 python3-pip git sshpass curl psmisc

# Install Python packages dengan retry
attempts=0
max_attempts=3
while [ $attempts -lt $max_attempts ]; do
    if install_python_packages; then
        break
    fi
    attempts=$((attempts + 1))
    echo -e "${YELLOW}⚠️  Retry install Python packages (${attempts}/${max_attempts})...${NC}"
    sleep 5
done

# Verify packages installed
echo -e "${BLUE}⏳ Verifikasi Python packages...${NC}"
if verify_python_packages; then
    echo -e "${GREEN}✅ Semua Python packages terinstall${NC}"
else
    echo -e "${RED}❌ Gagal install Python packages!${NC}"
    echo -e "${YELLOW}Mencoba install manual...${NC}"
    pip3 install pyTelegramBotAPI paramiko requests || true

    if ! verify_python_packages; then
        echo -e "${RED}❌ Python packages masih gagal. Coba manual:${NC}"
        echo "pip3 install pyTelegramBotAPI paramiko requests"
        exit 1
    fi
fi

echo -e "${GREEN}✅ Dependencies terinstall${NC}"

# Clone or copy repo
if [ -n "$GITHUB_REPO" ]; then
    echo -e "${BLUE}⏳ Cloning dari GitHub...${NC}"
    rm -rf $INSTALL_DIR
    git clone $GITHUB_REPO $INSTALL_DIR
else
    echo -e "${BLUE}⏳ Menggunakan file lokal...${NC}"
    mkdir -p $INSTALL_DIR
    
    # Find and copy bot files
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    if [ -f "$SCRIPT_DIR/rdp_bot.py" ]; then
        cp -r "$SCRIPT_DIR"/* $INSTALL_DIR/
    elif [ -f "rdp_bot.py" ]; then
        cp -r ./* $INSTALL_DIR/
    elif [ -f "telegram_bot/rdp_bot.py" ]; then
        cp -r telegram_bot/* $INSTALL_DIR/
    elif [ -f "../rdp_bot.py" ]; then
        cp -r ../* $INSTALL_DIR/
    fi
fi

# Update config: simpan ke .env (tidak hilang saat update)
BOT_FILE="$INSTALL_DIR/rdp_bot.py"
if [ ! -f "$BOT_FILE" ] && [ -f "$INSTALL_DIR/telegram_bot/rdp_bot.py" ]; then
    BOT_FILE="$INSTALL_DIR/telegram_bot/rdp_bot.py"
fi

if [ -f "$BOT_FILE" ]; then
    echo -e "${BLUE}⏳ Menyimpan konfigurasi ke .env...${NC}"
    cat > "$INSTALL_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN
OWNER_ID=$OWNER_ID
EOF
    chmod 600 "$INSTALL_DIR/.env"
    echo -e "${GREEN}✅ Konfigurasi tersimpan: $INSTALL_DIR/.env${NC}"
else
    echo -e "${RED}❌ File rdp_bot.py tidak ditemukan!${NC}"
    echo -e "${YELLOW}Files in $INSTALL_DIR:${NC}"
    ls -la $INSTALL_DIR/
    exit 1
fi

# Create startup script that auto-installs deps if missing
echo -e "${BLUE}⏳ Membuat startup script...${NC}"
cat > $INSTALL_DIR/start_bot.sh << 'STARTSCRIPT'
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

# Load env (token + owner) - persistent across updates
if [ -f "./.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "./.env"
  set +a
fi

# Validate token early to avoid systemd restart loop
if [ -z "${BOT_TOKEN:-}" ] || [ "${BOT_TOKEN:-}" = "YOUR_BOT_TOKEN_HERE" ] || [[ "${BOT_TOKEN:-}" != *:* ]]; then
  echo "❌ BOT_TOKEN tidak valid. Isi BOT_TOKEN di /root/rdp-bot/.env (format harus ada ':')" >&2
  exit 1
fi

# Auto-detect bot path
BOT_FILE=""
if [ -f "./rdp_bot.py" ]; then
  BOT_FILE="./rdp_bot.py"
elif [ -f "./telegram_bot/rdp_bot.py" ]; then
  BOT_FILE="./telegram_bot/rdp_bot.py"
else
  echo "❌ rdp_bot.py tidak ditemukan di $(pwd)" >&2
  ls -la >&2
  exit 1
fi

# Auto-install dependencies if missing
if ! python3 -c "import telebot, paramiko, requests" 2>/dev/null; then
  echo "Installing missing Python packages..." >&2
  python3 -m pip install --no-cache-dir pyTelegramBotAPI paramiko requests 2>/dev/null || \
  pip3 install pyTelegramBotAPI paramiko requests 2>/dev/null || true
fi

exec python3 -u "$BOT_FILE"
STARTSCRIPT
chmod +x $INSTALL_DIR/start_bot.sh

# Create systemd service
echo -e "${BLUE}⏳ Membuat systemd service...${NC}"

cat > /etc/systemd/system/rdpbot.service << EOF
[Unit]
Description=RDP Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=/bin/bash $INSTALL_DIR/start_bot.sh
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Stop existing service if running
systemctl stop rdpbot 2>/dev/null || true

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
echo "   cd $INSTALL_DIR && git pull && systemctl restart rdpbot"
echo ""

# Check if running
sleep 3
if systemctl is-active --quiet rdpbot; then
    echo -e "${GREEN}🤖 Bot sedang berjalan! Coba kirim /start di Telegram${NC}"
else
    echo -e "${YELLOW}⏳ Bot sedang starting... Cek status:${NC}"
    echo "   systemctl status rdpbot"
    echo "   journalctl -u rdpbot -f"
fi
