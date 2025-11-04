#!/usr/bin/env python3
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
from scipy.optimize import curve_fit

# 定义目标控制点
control_points = {
    'ratio': [0.0, 0.2, 0.5, 1.0, 2.0],
    'gain': [0.5, 0.7, 1.1, 1.7, 2.0]
}

ratios = np.array(control_points['ratio'])
gains = np.array(control_points['gain'])

# 方案1: 三次样条插值 (Cubic Spline)
from scipy.interpolate import CubicSpline
cs = CubicSpline(ratios, gains)

# 方案2: 分段线性插值
linear_interp = interp1d(ratios, gains, kind='linear')

# 方案3: 多项式拟合
poly_coeffs = np.polyfit(ratios, gains, 3)
poly_func = np.poly1d(poly_coeffs)

# 方案4: 指数函数拟合
def exp_func(x, a, b, c):
    return a * (1 - np.exp(-b * x)) + c

try:
    popt_exp, _ = curve_fit(exp_func, ratios, gains, p0=[1.5, 2.0, 0.5], maxfev=5000)
    exp_fitted = lambda x: exp_func(x, *popt_exp)
except:
    exp_fitted = None
    print("Warning: Exponential fit failed")

# 方案5: 自定义分段函数 (推荐)
def piecewise_smooth(ratio):
    """
    分段平滑函数，使用二次/三次多项式确保连续性和平滑性
    """
    ratio = np.clip(ratio, 0.0, 2.0)

    if isinstance(ratio, np.ndarray):
        result = np.zeros_like(ratio, dtype=float)

        # 区间1: [0, 0.2] -> gain [0.5, 0.7]
        mask1 = ratio <= 0.2
        result[mask1] = 0.5 + (0.7 - 0.5) * (ratio[mask1] / 0.2)

        # 区间2: [0.2, 0.5] -> gain [0.7, 1.1]
        mask2 = (ratio > 0.2) & (ratio <= 0.5)
        t = (ratio[mask2] - 0.2) / (0.5 - 0.2)
        result[mask2] = 0.7 + (1.1 - 0.7) * t

        # 区间3: [0.5, 1.0] -> gain [1.1, 1.7]
        mask3 = (ratio > 0.5) & (ratio <= 1.0)
        t = (ratio[mask3] - 0.5) / (1.0 - 0.5)
        result[mask3] = 1.1 + (1.7 - 1.1) * t

        # 区间4: [1.0, 2.0] -> gain [1.7, 2.0]
        mask4 = ratio > 1.0
        t = (ratio[mask4] - 1.0) / (2.0 - 1.0)
        result[mask4] = 1.7 + (2.0 - 1.7) * t

        return result
    else:
        if ratio <= 0.2:
            return 0.5 + (0.7 - 0.5) * (ratio / 0.2)
        elif ratio <= 0.5:
            t = (ratio - 0.2) / (0.5 - 0.2)
            return 0.7 + (1.1 - 0.7) * t
        elif ratio <= 1.0:
            t = (ratio - 0.5) / (1.0 - 0.5)
            return 1.1 + (1.7 - 1.1) * t
        else:
            t = (ratio - 1.0) / (2.0 - 1.0)
            return 1.7 + (2.0 - 1.7) * t

# 方案6: Hermite插值 (更平滑)
def hermite_smooth(ratio):
    """
    使用Hermite插值的平滑函数
    """
    ratio = np.clip(ratio, 0.0, 2.0)

    def smooth_step(edge0, edge1, x):
        """平滑步进函数 (smoothstep)"""
        t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    if isinstance(ratio, np.ndarray):
        result = np.zeros_like(ratio, dtype=float)

        # 区间1: [0, 0.2]
        mask1 = ratio <= 0.2
        t1 = smooth_step(0.0, 0.2, ratio[mask1])
        result[mask1] = 0.5 + (0.7 - 0.5) * t1

        # 区间2: [0.2, 0.5]
        mask2 = (ratio > 0.2) & (ratio <= 0.5)
        t2 = smooth_step(0.2, 0.5, ratio[mask2])
        result[mask2] = 0.7 + (1.1 - 0.7) * t2

        # 区间3: [0.5, 1.0]
        mask3 = (ratio > 0.5) & (ratio <= 1.0)
        t3 = smooth_step(0.5, 1.0, ratio[mask3])
        result[mask3] = 1.1 + (1.7 - 1.1) * t3

        # 区间4: [1.0, 2.0]
        mask4 = ratio > 1.0
        t4 = smooth_step(1.0, 2.0, ratio[mask4])
        result[mask4] = 1.7 + (2.0 - 1.7) * t4

        return result
    else:
        if ratio <= 0.2:
            t = smooth_step(0.0, 0.2, ratio)
            return 0.5 + (0.7 - 0.5) * t
        elif ratio <= 0.5:
            t = smooth_step(0.2, 0.5, ratio)
            return 0.7 + (1.1 - 0.7) * t
        elif ratio <= 1.0:
            t = smooth_step(0.5, 1.0, ratio)
            return 1.1 + (1.7 - 1.1) * t
        else:
            t = smooth_step(1.0, 2.0, ratio)
            return 1.7 + (2.0 - 1.7) * t

# 生成测试数据
test_ratios = np.linspace(0, 2, 200)

# 可视化对比
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 子图1: 所有方法对比
ax1 = axes[0, 0]
ax1.plot(control_points['ratio'], control_points['gain'], 'ro', markersize=10,
         label='Control Points', zorder=5)
ax1.plot(test_ratios, cs(test_ratios), 'b-', linewidth=2, label='Cubic Spline', alpha=0.7)
ax1.plot(test_ratios, linear_interp(test_ratios), 'g--', linewidth=2,
         label='Linear Interpolation', alpha=0.7)
ax1.plot(test_ratios, poly_func(test_ratios), 'm:', linewidth=2,
         label='Polynomial (deg=3)', alpha=0.7)
if exp_fitted:
    ax1.plot(test_ratios, exp_fitted(test_ratios), 'c-.', linewidth=2,
             label='Exponential Fit', alpha=0.7)

ax1.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax1.set_ylabel('Gain Factor', fontsize=12, fontweight='bold')
ax1.set_title('Comparison of Mapping Functions', fontsize=13, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(fontsize=9)
ax1.set_xlim(0, 2)
ax1.set_ylim(0, 2.5)

# 子图2: 推荐方案对比
ax2 = axes[0, 1]
ax2.plot(control_points['ratio'], control_points['gain'], 'ro', markersize=10,
         label='Control Points', zorder=5)
ax2.plot(test_ratios, piecewise_smooth(test_ratios), 'b-', linewidth=2.5,
         label='Piecewise Linear (Simple)', alpha=0.8)
ax2.plot(test_ratios, hermite_smooth(test_ratios), 'g-', linewidth=2.5,
         label='Hermite Smooth (Recommended)', alpha=0.8)
ax2.plot(test_ratios, cs(test_ratios), 'r--', linewidth=2,
         label='Cubic Spline', alpha=0.6)

ax2.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax2.set_ylabel('Gain Factor', fontsize=12, fontweight='bold')
ax2.set_title('Recommended Smooth Mapping Functions', fontsize=13, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.legend(fontsize=10)
ax2.set_xlim(0, 2)
ax2.set_ylim(0, 2.5)

# 子图3: 导数对比 (检查平滑性)
ax3 = axes[1, 0]
dx = 0.001
derivative_hermite = np.gradient(hermite_smooth(test_ratios), test_ratios)
derivative_piecewise = np.gradient(piecewise_smooth(test_ratios), test_ratios)
derivative_spline = cs(test_ratios, 1)

ax3.plot(test_ratios, derivative_hermite, 'g-', linewidth=2, label='Hermite Smooth')
ax3.plot(test_ratios, derivative_piecewise, 'b-', linewidth=2, label='Piecewise Linear')
ax3.plot(test_ratios, derivative_spline, 'r--', linewidth=2, label='Cubic Spline')
ax3.set_xlabel('Ratio', fontsize=12, fontweight='bold')
ax3.set_ylabel('Derivative (dGain/dRatio)', fontsize=12, fontweight='bold')
ax3.set_title('Smoothness Check (Derivative)', fontsize=13, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.legend(fontsize=10)
ax3.set_xlim(0, 2)

# 子图4: 关键点验证
ax4 = axes[1, 1]
test_points = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0]
hermite_values = [hermite_smooth(r) for r in test_points]
piecewise_values = [piecewise_smooth(r) for r in test_points]

x_pos = np.arange(len(test_points))
width = 0.35

ax4.bar(x_pos - width/2, hermite_values, width, label='Hermite Smooth', alpha=0.8)
ax4.bar(x_pos + width/2, piecewise_values, width, label='Piecewise Linear', alpha=0.8)
ax4.set_xlabel('Ratio Test Points', fontsize=12, fontweight='bold')
ax4.set_ylabel('Gain Factor', fontsize=12, fontweight='bold')
ax4.set_title('Gain Values at Key Ratios', fontsize=13, fontweight='bold')
ax4.set_xticks(x_pos)
ax4.set_xticklabels([f'{r:.1f}' for r in test_points])
ax4.legend(fontsize=10)
ax4.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('/home/wuq/webrtc-local/ratio_to_gain_mapping_design.png', dpi=150, bbox_inches='tight')
print("Plot saved: ratio_to_gain_mapping_design.png")

# 打印关键点的值
print("\n=== Key Point Verification ===")
print("Ratio -> Gain (Hermite Smooth):")
for r in [0.0, 0.2, 0.5, 1.0, 2.0]:
    g = hermite_smooth(r)
    print(f"  ratio={r:.1f} -> gain={g:.3f}")

print("\n=== Function Code for C++ Implementation ===")
print("""
// Recommended: Hermite Smooth Function
double CalculateGainFromRatio(double ratio) {
  ratio = std::clamp(ratio, 0.0, 2.0);

  // Smoothstep function
  auto smooth_step = [](double edge0, double edge1, double x) {
    double t = std::clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0);
    return t * t * (3.0 - 2.0 * t);
  };

  if (ratio <= 0.2) {
    double t = smooth_step(0.0, 0.2, ratio);
    return 0.5 + (0.7 - 0.5) * t;
  } else if (ratio <= 0.5) {
    double t = smooth_step(0.2, 0.5, ratio);
    return 0.7 + (1.1 - 0.7) * t;
  } else if (ratio <= 1.0) {
    double t = smooth_step(0.5, 1.0, ratio);
    return 1.1 + (1.7 - 1.1) * t;
  } else {
    double t = smooth_step(1.0, 2.0, ratio);
    return 1.7 + (2.0 - 1.7) * t;
  }
}

// Alternative: Simple Piecewise Linear (faster, less smooth)
double CalculateGainFromRatioSimple(double ratio) {
  ratio = std::clamp(ratio, 0.0, 2.0);

  if (ratio <= 0.2) {
    return 0.5 + (0.7 - 0.5) * (ratio / 0.2);
  } else if (ratio <= 0.5) {
    double t = (ratio - 0.2) / (0.5 - 0.2);
    return 0.7 + (1.1 - 0.7) * t;
  } else if (ratio <= 1.0) {
    double t = (ratio - 0.5) / (1.0 - 0.5);
    return 1.1 + (1.7 - 1.1) * t;
  } else {
    double t = (ratio - 1.0) / (2.0 - 1.0);
    return 1.7 + (2.0 - 1.7) * t;
  }
}
""")
