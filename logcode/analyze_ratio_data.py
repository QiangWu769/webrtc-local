#!/usr/bin/env python3

import numpy as np
import matplotlib.pyplot as plt

def analyze_and_plot():
    # Read and parse data
    tti_values = []
    ratios = []

    with open('/home/wuq/webrtc-local/logcode/ratio_data.txt', 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split('\t')
                if len(parts) == 4:
                    tti = int(parts[0])
                    ratio = float(parts[3])
                    tti_values.append(tti)
                    ratios.append(ratio)

    print(f"Total data points: {len(ratios)}")
    print(f"TTI range: {min(tti_values)} to {max(tti_values)}")
    print(f"Ratio range: {min(ratios):.6f} to {max(ratios):.6f}")

    # Analyze ratio distribution
    unique_ratios = np.unique(ratios)
    print(f"Unique ratio values (first 20): {unique_ratios[:20]}")

    # Count specific values
    count_1 = sum(1 for r in ratios if abs(r - 1.0) < 0.001)
    count_2 = sum(1 for r in ratios if abs(r - 2.0) < 0.001)
    count_0 = sum(1 for r in ratios if abs(r - 0.0) < 0.001)
    count_other = len(ratios) - count_1 - count_2 - count_0

    print(f"Ratio = 1.0: {count_1} ({count_1/len(ratios)*100:.1f}%)")
    print(f"Ratio = 2.0: {count_2} ({count_2/len(ratios)*100:.1f}%)")
    print(f"Ratio = 0.0: {count_0} ({count_0/len(ratios)*100:.1f}%)")
    print(f"Other values: {count_other} ({count_other/len(ratios)*100:.1f}%)")

    # Create simple time axis (data point sequence)
    time_axis = np.arange(len(ratios))

    # Plot with simple approach
    plt.figure(figsize=(15, 8))
    plt.plot(time_axis, ratios, color='#2E86AB', linewidth=1, alpha=0.8, label='Cellular Ratio')

    # Add reference lines
    plt.axhline(y=1.0, color='red', linestyle=':', alpha=0.6, label='Ratio = 1.0')
    plt.axhline(y=0.5, color='orange', linestyle=':', alpha=0.6, label='Ratio = 0.5')

    plt.xlabel('Data Point Index', fontsize=12)
    plt.ylabel('Cellular Ratio', fontsize=12)
    plt.title('Cellular Ratio Data Analysis', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend()

    # Set reasonable y-limits
    plt.ylim(-0.1, max(3.0, np.percentile(ratios, 95)))

    plt.tight_layout()
    plt.savefig('/home/wuq/webrtc-local/logcode/ratio_analysis.png', dpi=300, bbox_inches='tight')
    print("Plot saved to ratio_analysis.png")
    plt.show()

if __name__ == "__main__":
    analyze_and_plot()