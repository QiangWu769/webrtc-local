#!/usr/bin/env python3
"""
Explain bandwidth calculation in detail
"""

# Read sample data
data = []
with open('/home/wuq/webrtc-local/logcode/test0/ratio_data.txt', 'r') as f:
    for i, line in enumerate(f):
        if i < 30:  # First 30 lines
            parts = line.strip().split()
            if len(parts) >= 4:
                tti = int(parts[0])
                requested = int(parts[1])
                allocated = int(parts[2])
                ratio = float(parts[3])
                data.append((tti, requested, allocated, ratio))

print("="*80)
print("BANDWIDTH CALCULATION EXPLANATION")
print("="*80)

print("\n📁 DATA FORMAT:")
print("   ratio_data.txt has 4 columns:")
print("   Column 1: TTI (Transmission Time Interval)")
print("   Column 2: Requested resources")
print("   Column 3: Allocated resources")
print("   Column 4: Ratio (allocated/requested)")

print("\n📊 SAMPLE DATA (first 10 rows):")
print(f"\n{'Index':>5} | {'TTI':>6} | {'Requested':>10} | {'Allocated':>10} | {'Ratio':>10}")
print("-" * 55)
for i, (tti, req, alloc, ratio) in enumerate(data[:10]):
    print(f"{i:5d} | {tti:6d} | {req:10d} | {alloc:10d} | {ratio:10.2f}")

print("\n" + "="*80)
print("BANDWIDTH CALCULATION STEPS")
print("="*80)

# Step 1: Handle TTI wraparound
print("\n1️⃣  STEP 1: Create continuous time (handle TTI wraparound)")
print("-" * 80)

continuous_time = []
time_offset = 0
prev_tti = data[0][0]

print(f"\n   Initial TTI: {prev_tti}")
print(f"   TTI wraparound detection: if current_TTI < prev_TTI and gap > 5000")
print(f"   When wraparound detected: add offset of 10240 (TTI max value)")

for i, (tti, req, alloc, ratio) in enumerate(data):
    if tti < prev_tti and (prev_tti - tti) > 5000:
        time_offset += 10240
        print(f"\n   ⚠️  Wraparound detected at index {i}!")
        print(f"      prev_TTI={prev_tti}, current_TTI={tti}")
        print(f"      Adding offset: 10240, new offset={time_offset}")

    continuous_time.append(tti + time_offset)
    prev_tti = tti

print(f"\n   Final continuous time range: [{min(continuous_time)}, {max(continuous_time)}]")

# Step 2: Calculate bandwidth
print("\n2️⃣  STEP 2: Calculate bandwidth = allocated / time_diff")
print("-" * 80)

bandwidth = []
print(f"\n   Formula: BW[i] = allocated[i] / (time[i] - time[i-1])")
print(f"\n   Example calculations:")

for i in range(1, min(15, len(data))):
    diff = continuous_time[i] - continuous_time[i-1]
    if diff > 0:
        bw = data[i][2] / diff  # allocated / time_diff
        bandwidth.append(bw)

        if i <= 5 or (data[i][2] > 0 and len([x for x in bandwidth if x > 0]) <= 3):
            print(f"\n   Index {i}:")
            print(f"      time_diff = {continuous_time[i]} - {continuous_time[i-1]} = {diff}")
            print(f"      allocated = {data[i][2]}")
            print(f"      BW = {data[i][2]} / {diff} = {bw:.4f} bits/TTI")
    else:
        bandwidth.append(0)

print("\n3️⃣  PHYSICAL MEANING:")
print("-" * 80)
print(f"\n   📡 Bandwidth = Allocated Resources / Time Interval")
print(f"\n   Units: bits per TTI (Transmission Time Interval)")
print(f"          1 TTI = 1ms in LTE/5G networks")
print(f"\n   Example:")
print(f"      If allocated 2915 bits in time_diff of 779 TTI:")
print(f"      BW = 2915 / 779 = 3.74 bits/TTI")
print(f"\n   High BW → Network is allocating many resources per unit time")
print(f"   Low BW  → Network is allocating few resources per unit time")

print("\n4️⃣  WHY THIS MATTERS FOR PEAK DETECTION:")
print("-" * 80)
print(f"\n   Peak bandwidth = Maximum sustainable allocation rate")
print(f"   When BW stops increasing despite more requests → AT PEAK!")
print(f"\n   Our metric correlates with BW to detect when we're approaching/at peak")

# Check actual bandwidth distribution
bandwidth_all = []
for i in range(1, len(data)):
    diff = continuous_time[i] - continuous_time[i-1]
    if diff > 0:
        bw = data[i][2] / diff
        bandwidth_all.append(bw)

import numpy as np

print("\n5️⃣  BANDWIDTH STATISTICS (first 30 samples):")
print("-" * 80)
print(f"\n   Total samples: {len(bandwidth_all)}")
print(f"   Min:  {min(bandwidth_all):.4f} bits/TTI")
print(f"   Max:  {max(bandwidth_all):.4f} bits/TTI")
print(f"   Mean: {np.mean(bandwidth_all):.4f} bits/TTI")
print(f"   Median: {np.median(bandwidth_all):.4f} bits/TTI")
print(f"\n   Non-zero samples: {sum(1 for bw in bandwidth_all if bw > 0)}")
print(f"   Zero samples: {sum(1 for bw in bandwidth_all if bw == 0)}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"\n✅ Bandwidth Calculation:")
print(f"   1. Read TTI, Requested, Allocated from ratio_data.txt")
print(f"   2. Handle TTI wraparound (create continuous time)")
print(f"   3. Calculate: BW[i] = Allocated[i] / (Time[i] - Time[i-1])")
print(f"   4. Result: Bandwidth in bits/TTI")
print(f"\n📊 This represents the actual resource allocation rate from the network")
print(f"🎯 Our metric predicts when this rate will reach its maximum (peak)")
