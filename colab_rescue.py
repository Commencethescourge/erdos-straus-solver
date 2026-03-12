"""
Erdos-Straus Colab Rescue — paste this into Google Colab.
Gets a free T4 GPU or CPU instance to crunch survivors.

Instructions:
1. Go to colab.research.google.com
2. New notebook
3. Runtime → Change runtime type → T4 GPU (or CPU is fine too)
4. Paste this entire script into a cell and run it
5. Upload your chunk file when prompted
"""

# Step 1: Mount Google Drive (crash-safe — results persist)
from google.colab import drive
drive.mount('/content/drive')

# Step 2: Install the solver
!pip install erdos-straus-solver -q

# Step 3: Upload chunk file
from google.colab import files
import os

print("Upload your chunk file (e.g. survivors.txt)")
uploaded = files.upload()
chunk_file = list(uploaded.keys())[0]
print(f"Got {chunk_file}")

# Step 3: Count values
with open(chunk_file) as f:
    values = [line.strip() for line in f if line.strip()]
print(f"{len(values):,} values to solve")

# Step 4: Run the CPU solver (works everywhere)
import math
import multiprocessing as mp
import csv
import time


def solve_single(n, step_cap=10_000_000, y_cap_per_x=1_000_000):
    if n <= 1:
        return None
    steps = 0
    x_min = max(1, math.ceil(n / 4))
    x_max = n
    for x in range(x_min, x_max + 1):
        num_r = 4 * x - n
        if num_r <= 0:
            steps += 1
            if steps >= step_cap:
                return None
            continue
        den_r = n * x
        y_min = math.ceil(den_r / num_r)
        y_max = 2 * den_r // num_r
        y_steps = 0
        for y in range(max(x, y_min), y_max + 1):
            steps += 1
            y_steps += 1
            if steps >= step_cap:
                return None
            if y_steps >= y_cap_per_x:
                break
            denom_z = num_r * y - den_r
            if denom_z <= 0:
                continue
            num_z = den_r * y
            if num_z % denom_z == 0:
                z = num_z // denom_z
                if z >= y:
                    return {"n": n, "x": x, "y": y, "z": z, "steps": steps}
    return None


def worker(args):
    n, cap = args
    result = solve_single(n, step_cap=cap)
    if result:
        result["solved"] = True
        return result
    return {"n": n, "x": 0, "y": 0, "z": 0, "steps": cap, "solved": False}


# Colab gives 2 CPUs on free tier
workers = mp.cpu_count()
cap = 10_000_000
batch_size = workers * 8
ns = [int(v) for v in values]
total = len(ns)
solved_count = 0
# Write to Google Drive — survives disconnects
drive_dir = "/content/drive/MyDrive/erdos_straus"
os.makedirs(drive_dir, exist_ok=True)
out_path = os.path.join(drive_dir, "colab_results.csv")
t0 = time.time()

print(f"\n[colab] {total:,} values, step_cap={cap:,}, workers={workers}")
print(f"[colab] Starting...\n")

fields = ["n", "x", "y", "z", "steps", "solved"]
with open(out_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    with mp.Pool(workers) as pool:
        for i in range(0, total, batch_size):
            batch = ns[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size
            bt = time.time()
            results = pool.map(worker, [(n, cap) for n in batch])
            elapsed = time.time() - bt
            batch_solved = 0
            for r in results:
                writer.writerow(r)
                if r["solved"]:
                    batch_solved += 1
                    solved_count += 1
            if batch_num % 25 == 0 or batch_num == total_batches:
                f.flush()
                pct = 100 * (i + len(batch)) / total
                print(f"  [{pct:5.1f}%] batch {batch_num}/{total_batches}: "
                      f"{batch_solved}/{len(batch)} "
                      f"({elapsed:.1f}s) -- total: {solved_count:,}")

total_time = time.time() - t0
print(f"\n[colab] Done in {total_time:.1f}s")
print(f"[colab] Solved: {solved_count:,} / {total:,}")

# Results are already on Google Drive — no download needed
print(f"Results saved to Google Drive: {out_path}")
print("Check My Drive → erdos_straus → colab_results.csv")
