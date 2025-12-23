#!/bin/bash

# Build Golden Image Script
# Jalankan di VPS Tumbal untuk membuat golden image Windows
# Usage: bash build_golden_image.sh [WIN_CODE] [IMAGE_NAME]

WIN_CODE=${1:-"10"}
IMAGE_NAME=${2:-"win10-golden"}
WORK_DIR="/root/golden-build"
OUTPUT_DIR="/root/rdp-images"

# Windows versions
declare -A WIN_URLS
WIN_URLS["10"]="https://archive.org/download/windows-10-ltsc-2021-x64/Win10_LTSC_2021_x64.iso"
WIN_URLS["11"]="https://archive.org/download/windows-11-pro-x64/Win11_Pro_x64.iso"
WIN_URLS["2019"]="https://archive.org/download/windows-server-2019/WinServer2019.iso"
WIN_URLS["2022"]="https://archive.org/download/windows-server-2022/WinServer2022.iso"
WIN_URLS["tiny10"]="https://archive.org/download/tiny10-23h2/tiny10_x64_23h2.iso"
WIN_URLS["tiny11"]="https://archive.org/download/tiny11-23h2/tiny11_x64_23h2.iso"

# Virtio drivers
VIRTIO_URL="https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso"

echo "================================================"
echo "🏗️ BUILD GOLDEN IMAGE"
echo "================================================"
echo "📦 Windows: $WIN_CODE"
echo "📁 Output: $OUTPUT_DIR/${IMAGE_NAME}.img"
echo "================================================"

# Install dependencies
echo "📦 Installing dependencies..."
apt-get update -qq
apt-get install -y qemu-kvm qemu-utils libvirt-daemon-system virtinst \
    bridge-utils cpu-checker wget curl gzip pigz > /dev/null 2>&1

# Check KVM support
if ! kvm-ok 2>/dev/null | grep -q "can be used"; then
    echo "⚠️ KVM tidak tersedia, akan menggunakan emulasi (lebih lambat)"
    KVM_FLAG=""
else
    echo "✅ KVM tersedia"
    KVM_FLAG="-enable-kvm"
fi

# Create directories
mkdir -p "$WORK_DIR" "$OUTPUT_DIR"
cd "$WORK_DIR"

# Download Windows ISO if not exists
WIN_ISO="$WORK_DIR/windows.iso"
if [ ! -f "$WIN_ISO" ]; then
    WIN_URL="${WIN_URLS[$WIN_CODE]}"
    if [ -z "$WIN_URL" ]; then
        echo "❌ WIN_CODE tidak valid: $WIN_CODE"
        echo "Pilihan: 10, 11, 2019, 2022, tiny10, tiny11"
        exit 1
    fi
    
    echo "📥 Downloading Windows ISO..."
    wget -q --show-progress -O "$WIN_ISO" "$WIN_URL"
    
    if [ ! -f "$WIN_ISO" ] || [ ! -s "$WIN_ISO" ]; then
        echo "❌ Gagal download Windows ISO"
        exit 1
    fi
fi

# Download VirtIO drivers if not exists
VIRTIO_ISO="$WORK_DIR/virtio-win.iso"
if [ ! -f "$VIRTIO_ISO" ]; then
    echo "📥 Downloading VirtIO drivers..."
    wget -q --show-progress -O "$VIRTIO_ISO" "$VIRTIO_URL"
fi

# Create virtual disk
DISK_IMG="$WORK_DIR/disk.qcow2"
DISK_SIZE="25G"

echo "💿 Creating virtual disk ($DISK_SIZE)..."
qemu-img create -f qcow2 "$DISK_IMG" "$DISK_SIZE"

# Create autounattend.xml for unattended installation
cat > "$WORK_DIR/autounattend.xml" << 'AUTOUNATTEND'
<?xml version="1.0" encoding="utf-8"?>
<unattend xmlns="urn:schemas-microsoft-com:unattend">
    <settings pass="windowsPE">
        <component name="Microsoft-Windows-International-Core-WinPE" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
            <SetupUILanguage>
                <UILanguage>en-US</UILanguage>
            </SetupUILanguage>
            <InputLocale>en-US</InputLocale>
            <SystemLocale>en-US</SystemLocale>
            <UILanguage>en-US</UILanguage>
            <UserLocale>en-US</UserLocale>
        </component>
        <component name="Microsoft-Windows-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
            <DiskConfiguration>
                <Disk wcm:action="add">
                    <CreatePartitions>
                        <CreatePartition wcm:action="add">
                            <Order>1</Order>
                            <Type>Primary</Type>
                            <Extend>true</Extend>
                        </CreatePartition>
                    </CreatePartitions>
                    <ModifyPartitions>
                        <ModifyPartition wcm:action="add">
                            <Order>1</Order>
                            <PartitionID>1</PartitionID>
                            <Format>NTFS</Format>
                            <Label>Windows</Label>
                            <Letter>C</Letter>
                            <Active>true</Active>
                        </ModifyPartition>
                    </ModifyPartitions>
                    <DiskID>0</DiskID>
                    <WillWipeDisk>true</WillWipeDisk>
                </Disk>
            </DiskConfiguration>
            <ImageInstall>
                <OSImage>
                    <InstallTo>
                        <DiskID>0</DiskID>
                        <PartitionID>1</PartitionID>
                    </InstallTo>
                </OSImage>
            </ImageInstall>
            <UserData>
                <AcceptEula>true</AcceptEula>
                <ProductKey>
                    <WillShowUI>Never</WillShowUI>
                </ProductKey>
            </UserData>
        </component>
    </settings>
    <settings pass="specialize">
        <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
            <ComputerName>RDPSERVER</ComputerName>
            <TimeZone>UTC</TimeZone>
        </component>
        <component name="Microsoft-Windows-TerminalServices-LocalSessionManager" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
            <fDenyTSConnections>false</fDenyTSConnections>
        </component>
        <component name="Microsoft-Windows-TerminalServices-RDP-WinStationExtensions" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
            <UserAuthentication>0</UserAuthentication>
        </component>
        <component name="Networking-MPSSVC-Svc" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
            <FirewallGroups>
                <FirewallGroup wcm:action="add" wcm:keyValue="RemoteDesktop">
                    <Active>true</Active>
                    <Group>Remote Desktop</Group>
                    <Profile>all</Profile>
                </FirewallGroup>
            </FirewallGroups>
        </component>
    </settings>
    <settings pass="oobeSystem">
        <component name="Microsoft-Windows-Shell-Setup" processorArchitecture="amd64" publicKeyToken="31bf3856ad364e35" language="neutral" versionScope="nonSxS">
            <OOBE>
                <HideEULAPage>true</HideEULAPage>
                <HideLocalAccountScreen>true</HideLocalAccountScreen>
                <HideOEMRegistrationScreen>true</HideOEMRegistrationScreen>
                <HideOnlineAccountScreens>true</HideOnlineAccountScreens>
                <HideWirelessSetupInOOBE>true</HideWirelessSetupInOOBE>
                <ProtectYourPC>3</ProtectYourPC>
            </OOBE>
            <UserAccounts>
                <AdministratorPassword>
                    <Value>Admin@123</Value>
                    <PlainText>true</PlainText>
                </AdministratorPassword>
                <LocalAccounts>
                    <LocalAccount wcm:action="add">
                        <Password>
                            <Value>Admin@123</Value>
                            <PlainText>true</PlainText>
                        </Password>
                        <DisplayName>Administrator</DisplayName>
                        <Group>Administrators</Group>
                        <Name>Admin</Name>
                    </LocalAccount>
                </LocalAccounts>
            </UserAccounts>
            <AutoLogon>
                <Password>
                    <Value>Admin@123</Value>
                    <PlainText>true</PlainText>
                </Password>
                <Enabled>true</Enabled>
                <Username>Admin</Username>
            </AutoLogon>
            <FirstLogonCommands>
                <SynchronousCommand wcm:action="add">
                    <Order>1</Order>
                    <CommandLine>powershell -Command "Enable-NetFirewallRule -DisplayGroup 'Remote Desktop'"</CommandLine>
                </SynchronousCommand>
                <SynchronousCommand wcm:action="add">
                    <Order>2</Order>
                    <CommandLine>powershell -Command "Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name 'fDenyTSConnections' -Value 0"</CommandLine>
                </SynchronousCommand>
                <SynchronousCommand wcm:action="add">
                    <Order>3</Order>
                    <CommandLine>powershell -Command "Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name 'UserAuthentication' -Value 0"</CommandLine>
                </SynchronousCommand>
            </FirstLogonCommands>
        </component>
    </settings>
</unattend>
AUTOUNATTEND

# Create floppy image with autounattend
echo "📝 Creating autounattend floppy..."
dd if=/dev/zero of="$WORK_DIR/floppy.img" bs=1440K count=1 2>/dev/null
mkfs.msdos "$WORK_DIR/floppy.img" > /dev/null 2>&1
mkdir -p /mnt/floppy
mount -o loop "$WORK_DIR/floppy.img" /mnt/floppy
cp "$WORK_DIR/autounattend.xml" /mnt/floppy/
umount /mnt/floppy

echo ""
echo "🚀 Starting Windows installation..."
echo "⏳ Ini akan memakan waktu 20-40 menit..."
echo ""

# Run QEMU for installation
qemu-system-x86_64 \
    $KVM_FLAG \
    -m 4096 \
    -smp 2 \
    -cpu host \
    -drive file="$DISK_IMG",format=qcow2,if=virtio \
    -drive file="$WIN_ISO",media=cdrom \
    -drive file="$VIRTIO_ISO",media=cdrom \
    -drive file="$WORK_DIR/floppy.img",format=raw,if=floppy \
    -boot d \
    -vga std \
    -net nic,model=virtio \
    -net user \
    -vnc :0 \
    -daemonize

QEMU_PID=$!

echo "📺 VNC tersedia di port 5900"
echo "⏳ Menunggu instalasi selesai..."
echo ""
echo "💡 Tips: Gunakan VNC viewer untuk monitor progress"
echo "   - Alamat: $(hostname -I | awk '{print $1}'):5900"
echo ""

# Wait for installation (check if QEMU is still running)
echo "⏳ Menunggu instalasi selesai (auto-detect shutdown)..."
while pgrep -x qemu-system-x86_64 > /dev/null; do
    sleep 30
    echo "   ... masih berjalan"
done

echo ""
echo "✅ Instalasi Windows selesai!"
echo ""

# Convert to raw image for faster deployment
echo "🔄 Converting to raw image..."
RAW_IMG="$OUTPUT_DIR/${IMAGE_NAME}.img"
qemu-img convert -f qcow2 -O raw "$DISK_IMG" "$RAW_IMG"

# Compress the image
echo "📦 Compressing image..."
pigz -k -f "$RAW_IMG"
COMPRESSED_IMG="${RAW_IMG}.gz"

# Get file sizes
RAW_SIZE=$(du -h "$RAW_IMG" | cut -f1)
COMPRESSED_SIZE=$(du -h "$COMPRESSED_IMG" | cut -f1)

echo ""
echo "================================================"
echo "✅ BUILD COMPLETE!"
echo "================================================"
echo "📁 Raw Image: $RAW_IMG ($RAW_SIZE)"
echo "📦 Compressed: $COMPRESSED_IMG ($COMPRESSED_SIZE)"
echo ""
echo "🔐 Default Credentials:"
echo "   Username: Admin"
echo "   Password: Admin@123"
echo ""
echo "📤 Upload ke GDrive dengan:"
echo "   rclone copy $COMPRESSED_IMG gdrive:rdp-images/"
echo ""
echo "================================================"
