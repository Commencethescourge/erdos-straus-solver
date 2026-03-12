#!/bin/bash
# Termux SSH setup — run this on your phone in Termux
# One-time setup to enable WiFi file transfers with your PC

set -e

echo "=== Erdős–Straus Termux Setup ==="

# Install essentials
pkg update -y
pkg install -y python openssh tmux

# Create working directory
mkdir -p ~/erdos
cd ~/erdos

# Set up SSH server
echo ""
echo "Setting SSH password (you'll need this for first connection)..."
passwd

# Add PC's public key for passwordless SSH
mkdir -p ~/.ssh
cat >> ~/.ssh/authorized_keys << 'PUBKEY'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAII/fU1z/EkSxeBNLA6wrl5AmD0VY02oHEShvVsZKNuZa dasha@hp-victus
PUBKEY
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys

# Start SSH server
sshd
echo ""
echo "=== Setup Complete ==="
echo ""
echo "SSH server running on port 8022"
echo "Your phone IP:"
ip -4 addr show wlan0 2>/dev/null | grep inet | awk '{print $2}' | cut -d/ -f1 || echo "(check ifconfig)"
echo ""
echo "From your PC, run:"
echo "  ssh -p 8022 $(whoami)@<phone-ip>"
echo ""
echo "Or update ~/.ssh/config with your phone IP and just run:"
echo "  ssh phone"
echo ""
echo "To send a chunk file from PC:"
echo "  scp -P 8022 chunk.txt $(whoami)@<phone-ip>:~/erdos/"
echo ""
echo "To run the solver in background (survives disconnect):"
echo "  tmux new -s erdos"
echo "  python phone_solver.py 10000000 4 chunk.txt"
echo "  # Ctrl+B then D to detach"
echo "  # tmux attach -t erdos to reconnect"
