#!/bin/bash
# USB sync — transfer sieve results between PC and phone via USB/MTP
# Works with Android MTP (no root needed) or direct USB storage
#
# Usage:
#   ./usb_sync.sh push-phone          Push sieve solver + data to phone
#   ./usb_sync.sh pull-phone          Pull sieve results from phone
#   ./usb_sync.sh pull-drive [path]   Pull all results from Google Drive folder
#   ./usb_sync.sh collect             Collect all results into one directory
#   ./usb_sync.sh status              Show all result files and progress

RESULTS_DIR="collected_results"
PHONE_MTP="/run/user/$(id -u)/gvfs/mtp:*"  # Linux MTP path
# Windows: phone shows as a drive letter or under "This PC"
# Adjust PHONE_DIR for your setup:
PHONE_DIR=""

# Auto-detect phone path
detect_phone() {
    # Windows (Git Bash / MSYS2): check common MTP paths
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        # Try adb first (most reliable on Windows)
        if command -v adb &>/dev/null && adb devices | grep -q "device$"; then
            echo "adb"
            return 0
        fi
        echo ""
        echo "Phone not detected. Options:"
        echo "  1. Enable USB debugging + install ADB"
        echo "  2. Use WiFi SSH: ./phone_sync.sh pull"
        echo "  3. Copy manually from phone's file manager"
        return 1
    fi
    # Linux: check MTP mount
    local mtp_path=$(ls -d /run/user/*/gvfs/mtp:* 2>/dev/null | head -1)
    if [[ -n "$mtp_path" ]]; then
        echo "$mtp_path"
        return 0
    fi
    echo ""
    return 1
}

case "${1:-help}" in
    push-phone)
        echo "=== Push sieve solver to phone via ADB ==="
        if ! command -v adb &>/dev/null; then
            echo "ADB not found. Install Android SDK Platform Tools."
            echo "Or use WiFi SSH: ./phone_sync.sh push phone_sieve.py"
            exit 1
        fi
        REMOTE="/sdcard/erdos"
        adb shell "mkdir -p $REMOTE $REMOTE/sieve_data"
        echo "Pushing phone_sieve.py..."
        adb push phone_sieve.py "$REMOTE/"
        if [[ -f sieve_data/Residues.txt ]]; then
            echo "Pushing sieve data (114MB, may take a minute)..."
            adb push sieve_data/Residues.txt "$REMOTE/sieve_data/"
            adb push sieve_data/Filters.txt "$REMOTE/sieve_data/"
        else
            echo "No local sieve_data/ — phone will download from GitHub"
        fi
        echo ""
        echo "Done. On phone (Termux):"
        echo "  cp -r /sdcard/erdos ~/erdos"
        echo "  cd ~/erdos"
        echo "  python phone_sieve.py 2901 3864 2"
        ;;

    pull-phone)
        echo "=== Pull sieve results from phone ==="
        mkdir -p "$RESULTS_DIR"
        if command -v adb &>/dev/null && adb devices | grep -q "device$"; then
            echo "Using ADB..."
            adb pull "/sdcard/erdos/sieve_results*.csv" "$RESULTS_DIR/" 2>/dev/null
            # Also try Termux home
            adb shell "run-as com.termux cat ~/erdos/sieve_results*.csv" > /dev/null 2>&1
            # Fallback: pull from multiple possible locations
            for dir in "/sdcard/erdos" "/data/data/com.termux/files/home/erdos"; do
                adb shell "ls $dir/sieve_results*.csv 2>/dev/null" | while read f; do
                    echo "  Pulling $f..."
                    adb pull "$f" "$RESULTS_DIR/" 2>/dev/null
                done
            done
        else
            echo "ADB not connected. Alternatives:"
            echo "  1. WiFi SSH: ./phone_sync.sh pull"
            echo "  2. Copy from phone manually to $RESULTS_DIR/"
        fi
        echo ""
        echo "Results in $RESULTS_DIR/:"
        ls -la "$RESULTS_DIR"/sieve_results*.csv 2>/dev/null || echo "  (none found)"
        ;;

    pull-drive)
        DRIVE_PATH="${2:-}"
        echo "=== Pull results from Google Drive ==="
        mkdir -p "$RESULTS_DIR"
        if [[ -n "$DRIVE_PATH" ]]; then
            # Direct path provided (e.g., mounted Drive or local sync folder)
            echo "Copying from $DRIVE_PATH..."
            cp "$DRIVE_PATH"/sieve_results*.csv "$RESULTS_DIR/" 2>/dev/null
            cp "$DRIVE_PATH"/*.csv "$RESULTS_DIR/" 2>/dev/null
        else
            # Check common Drive sync locations
            for candidate in \
                "$HOME/Google Drive/erdos_straus" \
                "$HOME/GoogleDrive/erdos_straus" \
                "/c/Users/$USER/Google Drive/erdos_straus" \
                "/c/Users/$USER/My Drive/erdos_straus" \
                "$USERPROFILE/Google Drive/erdos_straus"; do
                if [[ -d "$candidate" ]]; then
                    echo "Found Drive folder: $candidate"
                    cp "$candidate"/sieve_results*.csv "$RESULTS_DIR/" 2>/dev/null
                    cp "$candidate"/*.csv "$RESULTS_DIR/" 2>/dev/null
                    break
                fi
            done
        fi
        echo ""
        echo "Results in $RESULTS_DIR/:"
        ls -la "$RESULTS_DIR"/*.csv 2>/dev/null || echo "  (none found)"
        echo ""
        echo "If Drive isn't synced locally, download from:"
        echo "  https://drive.google.com -> erdos_straus folder"
        ;;

    collect)
        echo "=== Collect all sieve results ==="
        mkdir -p "$RESULTS_DIR"
        # Copy local results
        cp sieve_results*.csv "$RESULTS_DIR/" 2>/dev/null
        echo "Local results copied."
        echo ""
        echo "Results in $RESULTS_DIR/:"
        ls -la "$RESULTS_DIR"/*.csv 2>/dev/null
        echo ""
        echo "To merge: python cloud_coordinator.py merge"
        echo "To check: python cloud_coordinator.py status"
        ;;

    status)
        echo "=== All sieve result files ==="
        echo ""
        total_batches=0
        for f in sieve_results*.csv "$RESULTS_DIR"/sieve_results*.csv; do
            [[ -f "$f" ]] || continue
            lines=$(wc -l < "$f" 2>/dev/null)
            batches=$((lines - 1))  # minus header
            size=$(du -h "$f" 2>/dev/null | cut -f1)
            echo "  $f: $batches batches ($size)"
            total_batches=$((total_batches + batches))
        done
        echo ""
        echo "Total batches across all files: $total_batches"
        echo "Target for 10^14: 3,865 batches"
        if [[ $total_batches -ge 3865 ]]; then
            echo "*** 10^14 COMPLETE ***"
        else
            remaining=$((3865 - total_batches))
            echo "Remaining: $remaining batches"
        fi
        ;;

    *)
        echo "USB/Drive sync for Erdos-Straus sieve results"
        echo ""
        echo "Usage:"
        echo "  ./usb_sync.sh push-phone          Push solver to phone via USB/ADB"
        echo "  ./usb_sync.sh pull-phone           Pull results from phone"
        echo "  ./usb_sync.sh pull-drive [path]    Pull from Google Drive sync folder"
        echo "  ./usb_sync.sh collect              Gather all local results"
        echo "  ./usb_sync.sh status               Show all result files"
        ;;
esac
