# Running the Erdos-Straus Solver on Android (Termux + SSH)

Use your phone as a compute node for brute-forcing hard residues.

---

## Quick Start (CPU Solver via SSH)

### On the phone (Termux)

1. Install Termux from **F-Droid** (not Play Store -- the Play Store version is outdated).
2. Run initial setup:
   ```
   pkg update && pkg upgrade
   pkg install python openssh
   ```
3. Set a password (needed for SSH login):
   ```
   passwd
   ```
4. Start the SSH server:
   ```
   sshd
   ```
   This runs on **port 8022** by default.
5. Find the phone's IP:
   ```
   ifconfig wlan0
   ```
   Look for `inet` -- something like `192.168.1.42`.
6. Create a working directory:
   ```
   mkdir -p ~/erdos
   ```

### On your PC

7. Copy the solver and a chunk file to the phone:
   ```
   scp -P 8022 phone_solver.py phone_chunk.txt user@192.168.1.42:~/erdos/
   ```
   Replace `user` with your Termux username (run `whoami` in Termux to check).

8. SSH into the phone:
   ```
   ssh -p 8022 user@192.168.1.42
   ```

9. Run the solver:
   ```
   cd ~/erdos
   python phone_solver.py 10000000 4 phone_chunk.txt
   ```
   Arguments: `<batch_size> <workers> <chunk_file>`

10. Copy results back to your PC:
    ```
    scp -P 8022 user@192.168.1.42:~/erdos/phone_results.csv .
    ```

---

## GPU Solver (Adreno 610 OpenCL)

The Adreno 610 supports OpenCL, but accessing it from Termux requires the vendor OpenCL library.

1. Install clang:
   ```
   pkg install clang
   ```

2. Compile the GPU solver:
   ```
   clang -O2 -o phone_gpu phone_gpu_solver.c -ldl
   ```
   The solver loads `libOpenCL.so` at runtime via `dlopen`, so no link-time dependency is needed.

3. Run it:
   ```
   ./phone_gpu phone_chunk.txt 10000000
   ```

### OpenCL access caveats

- The solver needs access to `/vendor/lib64/libOpenCL.so` (or `/vendor/lib/libOpenCL.so` on 32-bit).
- On Android 10 and older this usually just works. On Android 11+ the linker namespace restrictions may block access.
- Workarounds:
  - **Symlink** (may need root): `ln -s /vendor/lib64/libOpenCL.so $PREFIX/lib/`
  - **Copy** (may need root): `cp /vendor/lib64/libOpenCL.so $PREFIX/lib/`
  - **Set library path**: `export LD_LIBRARY_PATH=/vendor/lib64:$LD_LIBRARY_PATH`
- If none of that works, the CPU solver is still plenty fast with 4 workers.

---

## Generating Chunk Files

A chunk file is a list of target `n` values (one per line) to test. Typically these are the "hard residues" that passed earlier modular filters.

### Generate a range of candidates

```bash
python -c "
for n in range(100_000_001, 200_000_001, 2):
    if n % 4 == 3 or n % 4 == 1:
        print(n)
" > phone_chunk.txt
```

Adjust the range and filter to match whatever region you want the phone to search.

### Split a big chunk file for multiple devices

```bash
split -l 500000 all_targets.txt chunk_ --additional-suffix=.txt
```

This gives you `chunk_aa.txt`, `chunk_ab.txt`, etc. Send one to the phone, keep the rest on the PC.

---

## Tips

### Keep jobs alive after disconnect

Install `tmux` or `screen` so your solver keeps running when you close the SSH session:

```
pkg install tmux
tmux new -s erdos
python phone_solver.py 10000000 4 phone_chunk.txt
```

Detach with `Ctrl+B, D`. Reattach later with `tmux attach -t erdos`.

### Thermal throttling

Phones throttle the CPU when they get hot. If the phone is warm:

- Reduce workers: `python phone_solver.py 10000000 2 phone_chunk.txt`
- Take the phone case off
- Point a fan at it (seriously, it helps)
- Run overnight when ambient temp is lower

### Battery

- Plug the phone in. 4 workers uses roughly 2W above idle.
- Keeping the charge between 20-80% is fine for long runs -- modern Android stops charging at full anyway.

### Logging progress

The solver prints batch progress to stdout. Pipe through `tee` to save a log:

```
python phone_solver.py 10000000 4 phone_chunk.txt | tee run.log
```

---

## Pulling Results Back to PC

### Option 1: scp (simplest)

From your PC:

```
scp -P 8022 user@192.168.1.42:~/erdos/phone_results.csv ./results/
```

### Option 2: rsync (for partial transfers / resume)

```
pkg install rsync
```

From PC:

```
rsync -avz -e 'ssh -p 8022' user@192.168.1.42:~/erdos/phone_results.csv ./results/
```

### Option 3: Termux:API + cloud upload

Install the Termux:API app from F-Droid, then:

```
pkg install termux-api
termux-share -a send phone_results.csv
```

This opens the Android share sheet -- pick Google Drive, email, etc.
