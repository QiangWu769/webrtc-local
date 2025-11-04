#!/usr/bin/env python3
import re
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

# Parse Saturation and overuse state from log
monotime_to_saturation = {}
monotime_to_overuse = {}

with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        # Extract Saturation with MonoTime
        sat_match = re.search(r'MonoTime:\s*(\d+)\s*ms,\s*Ratio:\s*[\d.]+,\s*Saturation:\s*([-\d.]+)', line)
        if sat_match:
            monotime = int(sat_match.group(1))
            saturation = float(sat_match.group(2))
            monotime_to_saturation[monotime] = saturation

        # Extract overuse state (DelayState)
        overuse_match = re.search(r'MonoTime:\s*(\d+)ms.*DelayState:\s*(\w+)', line)
        if overuse_match:
            monotime = int(overuse_match.group(1))
            state = overuse_match.group(2)
            # Convert to numeric: Overusing=2, Normal=1, Underusing=0
            if state == 'Overusing':
                monotime_to_overuse[monotime] = 2
            elif state == 'Normal':
                monotime_to_overuse[monotime] = 1
            elif state == 'Underusing':
                monotime_to_overuse[monotime] = 0

# Match by monotime (allow 100ms tolerance)
data = []
for mono_sat, saturation in monotime_to_saturation.items():
    for mono_overuse, overuse in monotime_to_overuse.items():
        if abs(mono_sat - mono_overuse) <= 100:
            data.append((saturation, overuse))
            break

if len(data) == 0:
    print("No matching data found!")
    exit(1)

saturations = np.array([d[0] for d in data])
overuse_states = np.array([d[1] for d in data])

print(f"Total matched pairs: {len(data)}")
print(f"Saturation range: [{saturations.min():.2f}, {saturations.max():.2f}]")

# Count by state
underusing_count = np.sum(overuse_states == 0)
normal_count = np.sum(overuse_states == 1)
overusing_count = np.sum(overuse_states == 2)

print(f"\nOveruse state distribution:")
print(f"  Underusing: {underusing_count:5d} ({100*underusing_count/len(data):5.2f}%)")
print(f"  Normal:     {normal_count:5d} ({100*normal_count/len(data):5.2f}%)")
print(f"  Overusing:  {overusing_count:5d} ({100*overusing_count/len(data):5.2f}%)")

# Calculate saturation statistics by state
for state, name in [(0, 'Underusing'), (1, 'Normal'), (2, 'Overusing')]:
    mask = overuse_states == state
    if mask.sum() > 0:
        sats = saturations[mask]
        print(f"\n{name}:")
        print(f"  Count: {mask.sum()}")
        print(f"  Saturation mean: {sats.mean():.4f}")
        print(f"  Saturation median: {np.median(sats):.4f}")
        print(f"  Saturation std: {sats.std():.4f}")
        print(f"  Saturation range: [{sats.min():.4f}, {sats.max():.4f}]")

# Calculate point-biserial correlation (for binary Overusing vs not)
overusing_binary = (overuse_states == 2).astype(int)
correlation, p_value = stats.pointbiserialr(overusing_binary, saturations)
print(f"\nPoint-biserial correlation (Overusing vs Saturation): r = {correlation:+.4f}, p = {p_value:.4e}")

# Create visualization
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# 1. Box plot by state
ax1 = axes[0, 0]
state_names = ['Underusing', 'Normal', 'Overusing']
state_data = [saturations[overuse_states == i] for i in range(3)]
bp = ax1.boxplot(state_data, labels=state_names, patch_artist=True)
for patch, color in zip(bp['boxes'], ['lightgreen', 'lightyellow', 'lightcoral']):
    patch.set_facecolor(color)
ax1.set_ylabel('Saturation', fontsize=12, fontweight='bold')
ax1.set_title('Saturation Distribution by Overuse State', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3, axis='y')

# 2. Histogram by state (stacked)
ax2 = axes[0, 1]
bins = np.linspace(saturations.min(), saturations.max(), 50)
ax2.hist([saturations[overuse_states == 0],
          saturations[overuse_states == 1],
          saturations[overuse_states == 2]],
         bins=bins, label=state_names, color=['lightgreen', 'lightyellow', 'lightcoral'],
         alpha=0.7, stacked=True)
ax2.set_xlabel('Saturation', fontsize=12, fontweight='bold')
ax2.set_ylabel('Count', fontsize=12, fontweight='bold')
ax2.set_title('Saturation Distribution (Stacked)', fontsize=13, fontweight='bold')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3. Binned analysis: Saturation vs Overusing percentage
ax3 = axes[1, 0]
# Filter extreme outliers for better binning
sat_percentile_99 = np.percentile(saturations, 99)
sat_percentile_1 = np.percentile(saturations, 1)
valid_mask = (saturations >= sat_percentile_1) & (saturations <= sat_percentile_99)
sats_filtered = saturations[valid_mask]
overuse_filtered = overuse_states[valid_mask]

bins_sat = np.linspace(sats_filtered.min(), sats_filtered.max(), 31)
bin_indices = np.digitize(sats_filtered, bins_sat)

bin_centers = []
overusing_pcts = []
normal_pcts = []
underusing_pcts = []

for b in range(1, len(bins_sat)):
    mask = bin_indices == b
    count = np.sum(mask)
    if count >= 3:
        bin_centers.append((bins_sat[b-1] + bins_sat[b]) / 2)
        states_in_bin = overuse_filtered[mask]
        overusing_pcts.append(100 * np.sum(states_in_bin == 2) / count)
        normal_pcts.append(100 * np.sum(states_in_bin == 1) / count)
        underusing_pcts.append(100 * np.sum(states_in_bin == 0) / count)

bin_centers = np.array(bin_centers)
overusing_pcts = np.array(overusing_pcts)
normal_pcts = np.array(normal_pcts)
underusing_pcts = np.array(underusing_pcts)

ax3.plot(bin_centers, overusing_pcts, 'r-', linewidth=2.5, marker='o', label='Overusing %')
ax3.plot(bin_centers, normal_pcts, 'y-', linewidth=2.5, marker='s', label='Normal %')
ax3.plot(bin_centers, underusing_pcts, 'g-', linewidth=2.5, marker='^', label='Underusing %')
ax3.set_xlabel('Saturation', fontsize=12, fontweight='bold')
ax3.set_ylabel('Percentage (%)', fontsize=12, fontweight='bold')
ax3.set_title('Overuse State % vs Saturation (Binned)', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.legend()

# 4. Scatter plot with jitter
ax4 = axes[1, 1]
jitter = np.random.normal(0, 0.05, len(saturations))
ax4.scatter(saturations, overuse_states + jitter, alpha=0.3, s=20, c=overuse_states,
            cmap='RdYlGn_r', vmin=0, vmax=2)
ax4.set_xlabel('Saturation', fontsize=12, fontweight='bold')
ax4.set_ylabel('Overuse State', fontsize=12, fontweight='bold')
ax4.set_yticks([0, 1, 2])
ax4.set_yticklabels(state_names)
ax4.set_title(f'Saturation vs Overuse State\nCorrelation: r = {correlation:+.4f}',
              fontsize=13, fontweight='bold')
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/webrtc_config_results/saturation_vs_overuse.png', dpi=150, bbox_inches='tight')
print(f"\nPlot saved: saturation_vs_overuse.png")
