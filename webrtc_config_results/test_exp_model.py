#!/usr/bin/env python3

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# 创建测试数据，模拟指数衰减
time = np.linspace(0, 10, 100)
# 指数衰减: y = 1.5 * exp(-0.5*t) + 0.2
ratio_values = 1.5 * np.exp(-0.5 * time) + 0.2 + np.random.normal(0, 0.05, len(time))

# 测试线性回归
def linear_regression(x, y):
    n = len(x)
    x_mean = np.mean(x)
    y_mean = np.mean(y)
    
    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)
    
    if denominator < 1e-10:
        return 0.0, y_mean, 0.0
    
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    
    # 计算R²
    y_pred = slope * x + intercept
    ss_tot = np.sum((y - y_mean) ** 2)
    ss_res = np.sum((y - y_pred) ** 2)
    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-10 else 0.0
    
    return slope, intercept, r_squared

# 测试指数拟合
def exponential_fit(x, y):
    # 简化的指数拟合
    y_min = np.min(y)
    y_max = np.max(y)
    
    C = y_min * 0.9
    A = y_max - C
    
    best_lambda = 0.1
    best_r_squared = 0.0
    
    for lambda_val in np.linspace(0.01, 2.0, 50):
        try:
            y_pred = A * np.exp(-lambda_val * x) + C
            
            y_mean = np.mean(y)
            ss_tot = np.sum((y - y_mean) ** 2)
            ss_res = np.sum((y - y_pred) ** 2)
            r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-10 else 0.0
            
            if r_squared > best_r_squared:
                best_r_squared = r_squared
                best_lambda = lambda_val
        except:
            continue
    
    # 使用最佳lambda计算最终预测
    y_pred_best = A * np.exp(-best_lambda * x) + C
    equivalent_slope = -A * best_lambda
    
    return equivalent_slope, C, best_r_squared, y_pred_best

# 测试两种模型
linear_slope, linear_intercept, linear_r2 = linear_regression(time, ratio_values)
exp_slope, exp_intercept, exp_r2, exp_pred = exponential_fit(time, ratio_values)

print("线性回归结果:")
print(f"  斜率: {linear_slope:.4f}")
print(f"  R²: {linear_r2:.4f}")

print(f"\n指数衰减结果:")
print(f"  等效斜率: {exp_slope:.4f}")
print(f"  R²: {exp_r2:.4f}")

# 可视化对比
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

# 线性拟合
linear_pred = linear_slope * time + linear_intercept
ax1.scatter(time, ratio_values, alpha=0.6, s=20, label='数据点')
ax1.plot(time, linear_pred, 'r-', linewidth=2, label=f'线性拟合 (R²={linear_r2:.3f})')
ax1.set_title('线性回归拟合')
ax1.set_xlabel('时间')
ax1.set_ylabel('Ratio值')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 指数拟合
ax2.scatter(time, ratio_values, alpha=0.6, s=20, label='数据点')
ax2.plot(time, exp_pred, 'g-', linewidth=2, label=f'指数拟合 (R²={exp_r2:.3f})')
ax2.set_title('指数衰减拟合')
ax2.set_xlabel('时间')
ax2.set_ylabel('Ratio值')
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('model_test_comparison.png', dpi=150, bbox_inches='tight')
print(f"\n对比图已保存为: model_test_comparison.png")

# 判断哪个模型更好
if exp_r2 > linear_r2:
    print(f"✓ 指数模型拟合更好 (R²差异: {exp_r2 - linear_r2:.4f})")
else:
    print(f"✓ 线性模型拟合更好 (R²差异: {linear_r2 - exp_r2:.4f})")