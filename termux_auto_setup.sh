#!/data/data/com.termux/files/usr/bin/bash
# Auto setup — no interactive prompts
set -e

echo "=== Erdős–Straus Termux Auto Setup ==="

# Install essentials
yes | pkg update
yes | pkg install -y python openssh tmux clang

# Create working directory
mkdir -p ~/erdos

# Copy files from shared storage
cp /storage/emulated/0/Download/phone_solver.py ~/erdos/
cp /storage/emulated/0/Download/phone_gpu_solver.c ~/erdos/
echo "Files copied to ~/erdos/"

# Set up SSH key auth (no password needed)
mkdir -p ~/.ssh
cat > ~/.ssh/authorized_keys << 'PUBKEY'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAII/fU1z/EkSxeBNLA6wrl5AmD0VY02oHEShvVsZKNuZa dasha@hp-victus
PUBKEY
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys

# Start SSH server
pkill sshd 2>/dev/null || true
sshd

# Get IP
echo ""
echo "=== DONE ==="
echo "SSH running on port 8022"
echo "Phone IP:"
ip -4 addr show wlan0 2>/dev/null | grep inet | awk '{print $2}' | cut -d/ -f1
echo ""
echo "From PC: ssh -p 8022 $(whoami)@<IP>"
