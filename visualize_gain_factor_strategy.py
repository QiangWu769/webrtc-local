#!/usr/bin/env python3
"""
Visualize the Gain Factor Strategy based on Ratio Score

Shows how different score ranges map to different gain factors for bandwidth increase.
"""

import numpy as np
import matplotlib.pyplot as plt

def calculate_score(ratio, center=0.5, steepness=15.0):
    """Calculate score from ratio using inverse sigmoid"""
    sigmoid_value = 1.0 / (1.0 + np.exp(-steepness * (ratio - center)))
    return (1.0 - sigmoid_value) * 100.0

def get_gain_factor(score):
    """Get gain factor based on score range"""
    if score >= 90.0:
        return 0.0  # [90-100]: Stop growth
    elif score >= 70.0:
        return 0.5  # [70-90): Conservative
    elif score >= 50.0:
        return 1.0  # [50-70): Normal
    elif score >= 20.0:
        return 1.5  # [20-50): Aggressive
    else:
        return 2.0  # [0-20): Very aggressive

# Generate data
ratios = np.linspace(0.0, 1.0, 1000)
scores = [calculate_score(r) for r in ratios]
gains = [get_gain_factor(s) for s in scores]

# Calculate effective increase rate
base_rate = 10000  # Example: 10 kbps/s base increase rate
effective_rates = [base_rate * g for g in gains]

# Create visualization
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: Ratio to Score mapping
ax1 = axes[0, 0]
ax1.plot(ratios, scores, linewidth=2, color='blue')
ax1.axhline(y=90, color='red', linestyle='--', alpha=0.5, label='Peak threshold (90)')
ax1.axhline(y=70, color='orange', linestyle='--', alpha=0.5, label='Score 70')
ax1.axhline(y=50, color='yellow', linestyle='--', alpha=0.5, label='Score 50')
ax1.axhline(y=20, color='green', linestyle='--', alpha=0.5, label='Score 20')
ax1.set_xlabel('Cellular Resource Ratio', fontsize=12)
ax1.set_ylabel('Score', fontsize=12)
ax1.set_title('Ratio → Score Mapping (Inverse Sigmoid)', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=9)
ax1.set_xlim(0, 1)
ax1.set_ylim(0, 105)

# Plot 2: Score to Gain Factor mapping
ax2 = axes[0, 1]
ax2.plot(scores, gains, linewidth=2, color='green')
ax2.axvline(x=90, color='red', linestyle='--', alpha=0.5)
ax2.axvline(x=70, color='orange', linestyle='--', alpha=0.5)
ax2.axvline(x=50, color='yellow', linestyle='--', alpha=0.5)
ax2.axvline(x=20, color='green', linestyle='--', alpha=0.5)

# Add annotations
ax2.text(95, 0.1, '[90-100]:\nStop (0.0x)', fontsize=9, ha='left', va='bottom',
         bbox=dict(boxstyle='round', facecolor='red', alpha=0.3))
ax2.text(80, 0.6, '[70-90):\nConservative (0.5x)', fontsize=9, ha='center', va='center',
         bbox=dict(boxstyle='round', facecolor='orange', alpha=0.3))
ax2.text(60, 1.1, '[50-70):\nNormal (1.0x)', fontsize=9, ha='center', va='center',
         bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.3))
ax2.text(35, 1.6, '[20-50):\nAggressive (1.5x)', fontsize=9, ha='center', va='center',
         bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.3))
ax2.text(10, 2.1, '[0-20):\nVery Aggressive (2.0x)', fontsize=9, ha='center', va='center',
         bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))

ax2.set_xlabel('Score', fontsize=12)
ax2.set_ylabel('Gain Factor', fontsize=12)
ax2.set_title('Score → Gain Factor Strategy', fontsize=13, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.set_xlim(0, 105)
ax2.set_ylim(-0.1, 2.3)

# Plot 3: Ratio to Effective Increase Rate
ax3 = axes[1, 0]
ax3.plot(ratios, [r/1000 for r in effective_rates], linewidth=2, color='purple')
ax3.axhline(y=base_rate/1000, color='gray', linestyle='--', alpha=0.5,
            label=f'Base rate ({base_rate/1000} kbps/s)')
ax3.set_xlabel('Cellular Resource Ratio', fontsize=12)
ax3.set_ylabel('Effective Increase Rate (kbps/s)', fontsize=12)
ax3.set_title('Ratio → Effective Bandwidth Increase Rate', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.legend(fontsize=9)
ax3.set_xlim(0, 1)

# Add key ratio markers
key_ratios = [0.1, 0.3, 0.5, 0.7, 0.9]
for kr in key_ratios:
    score_val = calculate_score(kr)
    gain_val = get_gain_factor(score_val)
    rate_val = base_rate * gain_val / 1000
    ax3.plot(kr, rate_val, 'ro', markersize=8)
    ax3.text(kr, rate_val + 0.5, f'{kr:.1f}\n{score_val:.0f}pts\n{gain_val:.1f}x',
             fontsize=8, ha='center', va='bottom')

# Plot 4: Strategy Comparison Table
ax4 = axes[1, 1]
ax4.axis('off')

# Create table data
table_data = [
    ['Score Range', 'Network State', 'Gain Factor', 'Strategy'],
    ['[90-100]', 'Saturated', '0.0×', 'STOP growth'],
    ['[70-90)', 'High utilization', '0.5×', 'Conservative'],
    ['[50-70)', 'Moderate', '1.0×', 'Normal (default)'],
    ['[20-50)', 'Low utilization', '1.5×', 'Aggressive'],
    ['[0-20)', 'Very low', '2.0×', 'Very aggressive']
]

# Color mapping
row_colors = [
    ['lightgray', 'lightgray', 'lightgray', 'lightgray'],
    ['#ffcccc', '#ffcccc', '#ffcccc', '#ffcccc'],
    ['#ffe6cc', '#ffe6cc', '#ffe6cc', '#ffe6cc'],
    ['#ffffcc', '#ffffcc', '#ffffcc', '#ffffcc'],
    ['#ccffcc', '#ccffcc', '#ccffcc', '#ccffcc'],
    ['#cce6ff', '#cce6ff', '#cce6ff', '#cce6ff']
]

table = ax4.table(cellText=table_data, cellLoc='left', loc='center',
                  colWidths=[0.20, 0.25, 0.18, 0.25],
                  cellColours=row_colors)
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 2.5)

# Make header row bold
for i in range(4):
    cell = table[(0, i)]
    cell.set_text_props(weight='bold', fontsize=11)
    cell.set_facecolor('lightsteelblue')

ax4.set_title('Gain Factor Strategy Summary', fontsize=13, fontweight='bold', pad=20)

# Add explanation text
explanation = (
    "Design Philosophy:\n"
    "• Low ratio → High score → Network busy → Stop/slow growth (avoid congestion)\n"
    "• High ratio → Low score → Network idle → Fast growth (utilize capacity)\n"
    "\n"
    "Key Parameters:\n"
    "• Sigmoid center: 0.5 (ratio=0.5 → score=50)\n"
    "• Sigmoid steepness: 15.0 (sharp transitions)\n"
    "• Base increase rate: 10 kbps/s (example)\n"
)

fig.text(0.5, 0.02, explanation, ha='center', fontsize=9,
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

plt.suptitle('Cellular Ratio-Based Gain Factor Strategy for WebRTC Bandwidth Control',
             fontsize=15, fontweight='bold', y=0.98)

plt.tight_layout(rect=[0, 0.10, 1, 0.96])
plt.savefig('gain_factor_strategy_visualization.png', dpi=150, bbox_inches='tight')
print("\n✅ Visualization saved: gain_factor_strategy_visualization.png")

# Print example calculations
print("\n" + "="*70)
print("Example Calculations:")
print("="*70)
print(f"{'Ratio':<10} {'Score':<10} {'Gain':<10} {'Base Rate':<15} {'Effective Rate':<15}")
print("-"*70)

example_ratios = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
for ratio in example_ratios:
    score = calculate_score(ratio)
    gain = get_gain_factor(score)
    base = base_rate
    effective = base * gain
    print(f"{ratio:<10.1f} {score:<10.1f} {gain:<10.1f} {base:<15.0f} {effective:<15.0f}")

print("\n" + "="*70)
print("Strategy Interpretation:")
print("="*70)
print("When ratio = 0.1 (10%):")
print("  → Score = 100 → Gain = 0.0 → STOP growth (network saturated)")
print("\nWhen ratio = 0.3 (30%):")
print("  → Score = 95 → Gain = 0.0 → STOP growth (still near peak)")
print("\nWhen ratio = 0.5 (50%):")
print("  → Score = 50 → Gain = 1.0 → Normal growth (moderate utilization)")
print("\nWhen ratio = 0.7 (70%):")
print("  → Score = 5 → Gain = 2.0 → Very aggressive growth (network very idle)")
print("\nWhen ratio = 1.0 (100%+):")
print("  → Score = 0 → Gain = 2.0 → Very aggressive growth (network completely idle)")
print("="*70)
