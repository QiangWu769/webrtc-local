#!/usr/bin/env python3
import re
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

# Parse log to get ratio distribution and bandwidth relationship
ratios = []
bitrates = []

with open('/home/wuq/webrtc-local/webrtc_config_results/sender_local.log', 'r') as f:
    lines = f.readlines()

    for i, line in enumerate(lines):
        # Find ratio
        ratio_match = re.search(r'smoothed:\s*([\d.]+)\)', line)
        if ratio_match:
            ratio = float(ratio_match.group(1))
            ratios.append(ratio)

            # Find nearby bitrate
            for j in range(max(0, i-5), min(len(lines), i+5)):
                bwe_match = re.search(r'AckedBitrate:\s*(-?\d+)', lines[j])
                if bwe_match:
                    bitrate = int(bwe_match.group(1))
                    if bitrate > 0:
                        bitrates.append(bitrate / 1e6)
                        break
            else:
                bitrates.append(0)

ratios = np.array(ratios)
bitrates = np.array([b for b in bitrates if b > 0])
ratios = ratios[:len(bitrates)]

print(f"Total samples: {len(ratios)}")

# Analyze data density
bins = np.linspace(0, 2, 41)
hist, bin_edges = np.histogram(ratios, bins=bins)

print("\n=== Data Density Analysis ===")
print("Ratio Range | Count | Percentage")
print("-" * 40)

key_ranges = [
    (0.0, 0.2, "Very Low"),
    (0.2, 0.3, "Low"),
    (0.3, 0.4, "Medium-Low"),
    (0.4, 0.6, "Medium"),
    (0.6, 0.8, "Medium-High"),
    (0.8, 1.0, "High"),
    (1.0, 2.0, "Very High")
]

for low, high, desc in key_ranges:
    mask = (ratios >= low) & (ratios < high)
    count = np.sum(mask)
    pct = 100 * count / len(ratios)
    print(f"[{low:.1f}, {high:.1f}) {desc:12s} | {count:5d} | {pct:5.1f}%")

# Analyze ratio-bitrate relationship by density
print("\n=== Ratio vs Bitrate by Density ===")
for low, high, desc in key_ranges:
    mask = (ratios >= low) & (ratios < high)
    if np.sum(mask) > 0:
        bw_subset = bitrates[mask]
        print(f"{desc:12s} [{low:.1f}-{high:.1f}): "
              f"median_bw={np.median(bw_subset):.2f} Mbps, "
              f"std={np.std(bw_subset):.2f}, "
              f"samples={np.sum(mask)}")

# Create comprehensive visualization
fig = plt.figure(figsize=(16, 10))
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

# Plot 1: Histogram of ratio distribution
ax1 = fig.add_subplot(gs[0, :2])
ax1.hist(ratios, bins=50, alpha=0.7, color='steelblue', edgecolor='black')
ax1.set_xlabel('Smoothed Ratio', fontsize=12, fontweight='bold')
ax1.set_ylabel('Frequency', fontsize=12, fontweight='bold')
ax1.set_title('Ratio Distribution (Data Density)', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3, axis='y')
ax1.axvline(x=0.3, color='red', linestyle='--', linewidth=2, label='High density center')
ax1.legend()

# Plot 2: Cumulative distribution
ax2 = fig.add_subplot(gs[0, 2])
sorted_ratios = np.sort(ratios)
cumulative = np.arange(1, len(sorted_ratios) + 1) / len(sorted_ratios) * 100
ax2.plot(sorted_ratios, cumulative, 'b-', linewidth=2)
ax2.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax2.set_ylabel('Cumulative %', fontsize=12, fontweight='bold')
ax2.set_title('CDF', fontsize=13, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.axhline(y=50, color='red', linestyle='--', alpha=0.5)
ax2.axvline(x=np.median(ratios), color='red', linestyle='--', alpha=0.5)

# Plot 3: Ratio vs Bitrate scatter with density
ax3 = fig.add_subplot(gs[1, :])
# Create 2D histogram for density
h, xedges, yedges = np.histogram2d(ratios, bitrates, bins=[40, 30])
extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
im = ax3.imshow(h.T, origin='lower', extent=extent, aspect='auto', cmap='YlOrRd', alpha=0.8)
ax3.scatter(ratios, bitrates, alpha=0.1, s=5, c='blue')
ax3.set_xlabel('Smoothed Ratio', fontsize=12, fontweight='bold')
ax3.set_ylabel('Acked Bitrate (Mbps)', fontsize=12, fontweight='bold')
ax3.set_title('Ratio vs Bitrate (Color = Data Density)', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3)
plt.colorbar(im, ax=ax3, label='Sample Count')

# Plot 4: Proposed gain functions comparison
ax4 = fig.add_subplot(gs[2, :])

test_ratios = np.linspace(0, 2, 200)

# Current linear
linear_gain = 0.5 + 0.75 * test_ratios

# Proposal 1: Sigmoid (sensitive in middle, saturates at ends)
def sigmoid_gain(r):
    # Map [0, 2] to [0.5, 2.0] with sigmoid shape
    x = (r - 1.0) * 3  # Center at ratio=1.0
    sigmoid = 1.0 / (1.0 + np.exp(-x))
    return 0.5 + 1.5 * sigmoid

# Proposal 2: Power function (more sensitive at low ratio)
def power_gain(r):
    # sqrt-like curve, more sensitive when ratio is low
    normalized = r / 2.0  # [0, 2] -> [0, 1]
    return 0.5 + 1.5 * np.sqrt(normalized)

# Proposal 3: Piecewise with steep slope in high-density region
def piecewise_gain(r):
    # Steeper in [0.2, 0.5] where data is dense
    if isinstance(r, np.ndarray):
        result = np.zeros_like(r)
        # Slow growth in sparse region [0, 0.2]
        mask1 = r <= 0.2
        result[mask1] = 0.5 + 0.5 * (r[mask1] / 0.2)  # 0.5 -> 1.0

        # Fast growth in dense region [0.2, 0.5]
        mask2 = (r > 0.2) & (r <= 0.5)
        t = (r[mask2] - 0.2) / 0.3
        result[mask2] = 1.0 + 0.5 * t  # 1.0 -> 1.5

        # Medium growth [0.5, 1.5]
        mask3 = (r > 0.5) & (r <= 1.5)
        t = (r[mask3] - 0.5) / 1.0
        result[mask3] = 1.5 + 0.4 * t  # 1.5 -> 1.9

        # Slow approach to max [1.5, 2.0]
        mask4 = r > 1.5
        t = (r[mask4] - 1.5) / 0.5
        result[mask4] = 1.9 + 0.1 * t  # 1.9 -> 2.0

        return result
    return 0.5 + 0.75 * r  # fallback

ax4.plot(test_ratios, linear_gain, 'b-', linewidth=2, label='Current Linear', alpha=0.7)
ax4.plot(test_ratios, sigmoid_gain(test_ratios), 'g-', linewidth=2.5,
         label='Sigmoid (smooth S-curve)', alpha=0.8)
ax4.plot(test_ratios, power_gain(test_ratios), 'm-', linewidth=2.5,
         label='Square Root (sensitive at low ratio)', alpha=0.8)
ax4.plot(test_ratios, piecewise_gain(test_ratios), 'r-', linewidth=2.5,
         label='Piecewise (adaptive to density)', alpha=0.8)

# Highlight high-density region
ax4.axvspan(0.2, 0.5, alpha=0.2, color='yellow', label='High density region')

ax4.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax4.set_ylabel('Gain Factor', fontsize=12, fontweight='bold')
ax4.set_title('Proposed Gain Functions (Compared)', fontsize=13, fontweight='bold')
ax4.grid(True, alpha=0.3)
ax4.legend(fontsize=10)
ax4.set_xlim(0, 2)
ax4.set_ylim(0, 2.2)

plt.savefig('/home/wuq/webrtc-local/ratio_density_analysis_for_gain.png', dpi=150, bbox_inches='tight')
print("\nPlot saved: ratio_density_analysis_for_gain.png")

# Print recommendations
print("\n=== Recommendations ===")
print("1. Most data is in [0.2, 0.5] range (high density)")
print("2. Gain function should be MORE SENSITIVE in this region")
print("3. Can be less sensitive in sparse regions (>1.0)")
print("\nRecommended: Square Root or Sigmoid function")
