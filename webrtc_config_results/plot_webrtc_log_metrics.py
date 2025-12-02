#!/usr/bin/env python3
"""
Generate a WebRTC congestion-control dashboard from a log file.

The script parses ratio, bitrate, and RTT series from detailed WebRTC logs
and renders a figure that mimics the illustrated reference:
  * Top panel: cellular ratio (raw + smoothed), bitrate targets, and overuse events
  * Bottom panel: RTT trends with percentile guides and overuse markers

Example:
    python plot_webrtc_log_metrics.py \
        --log /home/qwu26/webrtc-local/webrtc_config_results/s1016ender_local.log \
        --output webrtc_dashboard.png
"""

from __future__ import annotations

import argparse
import pathlib
import re
from typing import Dict, List, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


RatioRecord = Dict[str, float]
RttRecord = Dict[str, float]
GccRecord = Dict[str, object]
TargetRecord = Dict[str, float]


def parse_log(path: pathlib.Path) -> Dict[str, pd.DataFrame]:
    """Parse the log file and return data frames for ratio, RTT, and GCC metrics."""
    ratio_pattern = re.compile(
        r"\[CellularRatio\] MonoTime: (?P<time>\d+) ms, "
        r"Ratio: (?P<ratio>-?\d+(?:\.\d+)?), "
        r"Saturation: (?P<saturation>-?\d+(?:\.\d+)?), "
        r"Influence: (?P<influence>\w+)"
    )
    rtt_pattern = re.compile(
        r"\[RttBWE-Update\] MonoTime: (?P<time>\d+) ms, "
        r"PropagationRtt: (?P<prop>\d+(?:\.\d+)?) ms, "
        r"CorrectedRtt: (?P<corr>\d+(?:\.\d+)?) ms"
    )
    gcc_pattern = re.compile(
        r"\[GCC-DECISION-SNAPSHOT\] MonoTime: (?P<time>\d+) ms \| "
        r"DelayState: (?P<state>\w+), .*?"
        r"BweTargetBps: (?P<bwe>-?\d+) \| "
        r"AckedBitrateBps: (?P<acked>-?\d+) \| "
        r"FinalTargetBps: (?P<final>-?\d+)"
    )
    target_pattern = re.compile(
        r"\[GCC-OUTPUT\] TargetRateUpdate MonoTime: (?P<time>\d+) ms, "
        r"DelayBasedBps: (?P<delay>-?\d+), "
        r"LossBasedBps: (?P<loss>-?\d+), "
        r"FinalTargetBps: (?P<final>-?\d+)"
    )

    ratio_records: List[RatioRecord] = []
    rtt_records: List[RttRecord] = []
    gcc_records: List[GccRecord] = []
    target_records: List[TargetRecord] = []

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if "[CellularRatio]" in line:
                match = ratio_pattern.search(line)
                if match:
                    ratio_records.append(
                        {
                            "time_ms": float(match.group("time")),
                            "ratio": float(match.group("ratio")),
                            "saturation": float(match.group("saturation")),
                        }
                    )
                continue

            if "[RttBWE-Update]" in line:
                match = rtt_pattern.search(line)
                if match:
                    rtt_records.append(
                        {
                            "time_ms": float(match.group("time")),
                            "propagation_rtt_ms": float(match.group("prop")),
                            "corrected_rtt_ms": float(match.group("corr")),
                        }
                    )
                continue

            if "[GCC-DECISION-SNAPSHOT]" in line:
                match = gcc_pattern.search(line)
                if match:
                    gcc_records.append(
                        {
                            "time_ms": float(match.group("time")),
                            "delay_state": match.group("state"),
                            "bwe_target_bps": float(match.group("bwe")),
                            "acked_bitrate_bps": float(match.group("acked")),
                            "final_target_bps": float(match.group("final")),
                        }
                    )
                continue

            if "[GCC-OUTPUT]" in line:
                match = target_pattern.search(line)
                if match:
                    target_records.append(
                        {
                            "time_ms": float(match.group("time")),
                            "final_target_bps": float(match.group("final")),
                        }
                    )

    data_frames: Dict[str, pd.DataFrame] = {
        "ratio": pd.DataFrame(ratio_records),
        "rtt": pd.DataFrame(rtt_records),
        "gcc": pd.DataFrame(gcc_records),
        "target": pd.DataFrame(target_records),
    }
    return data_frames


def weighted_ratio(series: Sequence[float], window: int = 20, latest_weight: float = 0.6) -> np.ndarray:
    """Compute a weighted moving average where the latest sample holds a fixed weight."""
    values = np.asarray(series, dtype=float)
    if values.size == 0:
        return np.array([])

    smoothed = np.empty_like(values)
    for idx in range(values.size):
        start = max(0, idx - window + 1)
        window_values = values[start : idx + 1]
        if window_values.size == 1:
            smoothed[idx] = window_values[-1]
            continue

        weights = np.full(window_values.size, (1.0 - latest_weight) / (window_values.size - 1))
        weights[-1] = latest_weight
        smoothed[idx] = np.dot(window_values, weights)
    return smoothed


def prepare_data(data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """Clean and enrich raw data frames with time offsets and derived series."""
    frames = {}

    # Determine common time origin from available series
    minima = []
    for df in data.values():
        if not df.empty and "time_ms" in df:
            minima.append(df["time_ms"].min())
    if not minima:
        raise ValueError("No time-stamped records were found in the provided log.")
    time_zero = min(minima)

    # Ratio data with smoothing
    ratio_df = data["ratio"].copy()
    if not ratio_df.empty:
        ratio_df.sort_values("time_ms", inplace=True)
        ratio_df["time_s"] = (ratio_df["time_ms"] - time_zero) / 1000.0
        ratio_df["smoothed_ratio"] = weighted_ratio(ratio_df["ratio"].to_numpy())
    frames["ratio"] = ratio_df

    # RTT data
    rtt_df = data["rtt"].copy()
    if not rtt_df.empty:
        rtt_df.sort_values("time_ms", inplace=True)
        rtt_df["time_s"] = (rtt_df["time_ms"] - time_zero) / 1000.0
    frames["rtt"] = rtt_df

    # GCC decisions
    gcc_df = data["gcc"].copy()
    if not gcc_df.empty:
        gcc_df.sort_values("time_ms", inplace=True)
        gcc_df["time_s"] = (gcc_df["time_ms"] - time_zero) / 1000.0
    frames["gcc"] = gcc_df

    # Target updates
    target_df = data["target"].copy()
    if not target_df.empty:
        target_df.sort_values("time_ms", inplace=True)
        target_df["time_s"] = (target_df["time_ms"] - time_zero) / 1000.0
    frames["target"] = target_df

    frames["time_zero"] = time_zero
    return frames


def compute_overuse_events(gcc_df: pd.DataFrame) -> pd.DataFrame:
    """Extract timestamps where GCC enters an overusing state."""
    if gcc_df.empty:
        return pd.DataFrame(columns=["time_ms", "time_s", "delay_state"])

    events: List[Dict[str, object]] = []
    previous_overusing = False
    for _, row in gcc_df.iterrows():
        state_raw = str(row["delay_state"])
        state = state_raw.lower()
        is_overusing = "overusing" in state
        if is_overusing and not previous_overusing:
            events.append(
                {
                    "time_ms": row["time_ms"],
                    "time_s": row["time_s"],
                    "delay_state": state_raw,
                }
            )
        previous_overusing = is_overusing

    return pd.DataFrame(events)


def build_acked_target_alignment(gcc_df: pd.DataFrame, target_df: pd.DataFrame) -> pd.DataFrame:
    """Align acked bitrate snapshots with the latest known target bitrate."""
    if gcc_df.empty:
        return pd.DataFrame(columns=["time_ms", "time_s", "acked_bps", "target_bps"])

    acked = gcc_df[["time_ms", "time_s", "acked_bitrate_bps"]].rename(
        columns={"acked_bitrate_bps": "acked_bps"}
    )
    if target_df.empty:
        acked["target_bps"] = np.nan
        return acked

    aligned = pd.merge_asof(
        acked.sort_values("time_ms"),
        target_df[["time_ms", "final_target_bps"]].sort_values("time_ms"),
        on="time_ms",
        direction="backward",
    )
    aligned.rename(columns={"final_target_bps": "target_bps"}, inplace=True)
    return aligned


def summarize_metrics(aligned: pd.DataFrame, rtt_df: pd.DataFrame) -> Dict[str, float]:
    """Calculate aggregate metrics for annotation blocks."""
    summary: Dict[str, float] = {}

    if not aligned.empty:
        target_valid = aligned["target_bps"].dropna()
        if not target_valid.empty:
            summary["avg_target_mbps"] = float(target_valid.mean() / 1e6)
        else:
            summary["avg_target_mbps"] = float("nan")

        summary["avg_acked_mbps"] = float(aligned["acked_bps"].mean() / 1e6)

        ratio_mask = (aligned["target_bps"] > 0) & aligned["target_bps"].notna()
        if ratio_mask.any():
            acked_sum = aligned.loc[ratio_mask, "acked_bps"].sum()
            target_sum = aligned.loc[ratio_mask, "target_bps"].sum()
            summary["acked_target_ratio_pct"] = float(100.0 * acked_sum / target_sum) if target_sum else float("nan")
        else:
            summary["acked_target_ratio_pct"] = float("nan")
    else:
        summary["avg_target_mbps"] = float("nan")
        summary["avg_acked_mbps"] = float("nan")
        summary["acked_target_ratio_pct"] = float("nan")

    if not rtt_df.empty:
        corrected = rtt_df["corrected_rtt_ms"]
        summary["median_rtt_ms"] = float(corrected.median())
        summary["p90_rtt_ms"] = float(corrected.quantile(0.9))
        summary["mean_rtt_ms"] = float(corrected.mean())
        summary["max_rtt_ms"] = float(corrected.max())
    else:
        for key in ("median_rtt_ms", "p90_rtt_ms", "mean_rtt_ms", "max_rtt_ms"):
            summary[key] = float("nan")

    return summary


def annotate_summary(ax: plt.Axes, text_lines: Sequence[str], location: str = "upper right") -> None:
    """Add a text box with summary lines to the provided axes."""
    text = "\n".join(text_lines)
    box_props = dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9, edgecolor="#666666")
    ax.text(
        0.98 if "right" in location else 0.02,
        0.98 if "upper" in location else 0.02,
        text,
        transform=ax.transAxes,
        ha="right" if "right" in location else "left",
        va="top" if "upper" in location else "bottom",
        fontsize=9,
        family="monospace",
        bbox=box_props,
    )


def plot_dashboard(
    ratio_df: pd.DataFrame,
    rtt_df: pd.DataFrame,
    gcc_df: pd.DataFrame,
    target_df: pd.DataFrame,
    summary: Dict[str, float],
    overuse_events: pd.DataFrame,
    output_path: pathlib.Path,
) -> None:
    """Render and save the congestion-control dashboard."""
    fig, (ax_top, ax_bottom) = plt.subplots(
        2,
        1,
        figsize=(13, 9),
        sharex=False,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.28},
    )

    # --- Top panel: ratio + bitrate series ---
    # Color palette aligned with plot_ratio_trend.py
    color_smoothed_ratio = "#2E86AB"
    color_gain_neutral = "green"
    color_congestion = "red"
    color_acked = "#1E90FF"
    color_target = "#C73E1D"
    color_overuse = "#C73E1D"

    legend_handles_top: List[object] = []
    legend_labels_top: List[str] = []

    def register_top(handle) -> None:
        label = handle.get_label()
        if label not in legend_labels_top:
            legend_labels_top.append(label)
            legend_handles_top.append(handle)

    if not ratio_df.empty:
        smoothed_handle = ax_top.plot(
            ratio_df["time_s"],
            ratio_df["smoothed_ratio"],
            color=color_smoothed_ratio,
            linewidth=2.5,
            alpha=0.9,
            label="Smoothed Ratio (20-point weighted, latest=0.6)",
        )[0]
        register_top(smoothed_handle)

    gain_neutral = 0.3
    congestion_threshold = 0.4
    gain_handle = ax_top.axhline(
        gain_neutral,
        color=color_gain_neutral,
        linestyle="--",
        linewidth=1.4,
        alpha=0.7,
        label="Gain Neutral (0.3)",
    )
    register_top(gain_handle)
    congestion_handle = ax_top.axhline(
        congestion_threshold,
        color=color_congestion,
        linestyle=":",
        linewidth=1.4,
        alpha=0.7,
        label="Congestion Threshold (0.4)",
    )
    register_top(congestion_handle)

    ax_top.set_ylabel("Ratio")
    ax_top.set_title("Smoothed Ratio, Bitrates & Network Events")
    ax_top.grid(alpha=0.25, linestyle="--")

    # Secondary axis for bitrates
    ax_top_bandwidth = ax_top.twinx()
    handles_bandwidth: List[object] = []

    if not gcc_df.empty:
        aligned = build_acked_target_alignment(gcc_df, target_df)
        acked_handle = ax_top_bandwidth.plot(
            aligned["time_s"],
            aligned["acked_bps"] / 1e6,
            color=color_acked,
            linestyle="--",
            linewidth=2.0,
            alpha=0.9,
            label="Acked Bitrate (Mbps)",
        )[0]
        handles_bandwidth.append(acked_handle)
    else:
        aligned = pd.DataFrame()

    if not target_df.empty:
        target_handle = ax_top_bandwidth.step(
            target_df["time_s"],
            target_df["final_target_bps"] / 1e6,
            where="post",
            color=color_target,
            linewidth=2.2,
            alpha=0.9,
            label="Target Bitrate (Mbps)",
        )[0]
        handles_bandwidth.append(target_handle)

    ax_top_bandwidth.set_ylabel("Bandwidth (Mbps)")
    if not aligned.empty or not target_df.empty:
        ax_top_bandwidth.set_ylim(bottom=0)

    # Ensure ratio limits resemble reference
    ratio_max = 1.6
    if not ratio_df.empty:
        ratio_max = max(ratio_max, float(ratio_df["smoothed_ratio"].max() * 1.1))
    ax_top.set_ylim(0, ratio_max)

    overuse_times = overuse_events["time_s"].to_numpy() if not overuse_events.empty else np.array([])

    # Overuse markers (if any)
    overuse_handle = None
    if overuse_times.size:
        overuse_y = np.full_like(overuse_times, ax_top.get_ylim()[0] + 0.02 * ratio_max, dtype=float)
        overuse_handle = ax_top.scatter(
            overuse_times,
            overuse_y,
            marker="^",
            s=80,
            facecolor=color_overuse,
            edgecolor="darkred",
            linewidths=0.4,
            label=f"Overusing Events ({len(overuse_events)})",
            zorder=6,
        )
        register_top(overuse_handle)

    for bw_handle in handles_bandwidth:
        register_top(bw_handle)

    ax_top.legend(legend_handles_top, legend_labels_top, loc="upper left", fontsize=9)

    # Summary annotation
    summary_lines = [
        f"Avg Target: {summary['avg_target_mbps']:.2f} Mbps" if summary["avg_target_mbps"] == summary["avg_target_mbps"] else "Avg Target: n/a",
        f"Avg Acked: {summary['avg_acked_mbps']:.2f} Mbps" if summary["avg_acked_mbps"] == summary["avg_acked_mbps"] else "Avg Acked: n/a",
        f"Acked/Target: {summary['acked_target_ratio_pct']:.1f}%" if summary["acked_target_ratio_pct"] == summary["acked_target_ratio_pct"] else "Acked/Target: n/a",
        f"Median RTT: {summary['median_rtt_ms']:.0f} ms" if summary["median_rtt_ms"] == summary["median_rtt_ms"] else "Median RTT: n/a",
    ]
    annotate_summary(ax_top, summary_lines, location="upper right")

    # --- Bottom panel: RTT trends ---
    color_rtt = "#2E86AB"
    color_prop_rtt = "#6C5B7B"
    color_median = "#FFA500"
    color_p90 = "#8B0000"

    legend_handles_bottom: List[object] = []
    legend_labels_bottom: List[str] = []

    def register_bottom(handle) -> None:
        label = handle.get_label()
        if label not in legend_labels_bottom:
            legend_labels_bottom.append(label)
            legend_handles_bottom.append(handle)

    if not rtt_df.empty:
        rtt_handle = ax_bottom.plot(
            rtt_df["time_s"],
            rtt_df["corrected_rtt_ms"],
            color=color_rtt,
            linewidth=1.6,
            alpha=0.9,
            label="RTT (ms)",
        )[0]
        register_bottom(rtt_handle)
        prop_handle = ax_bottom.plot(
            rtt_df["time_s"],
            rtt_df["propagation_rtt_ms"],
            color=color_prop_rtt,
            linewidth=1.4,
            alpha=0.75,
            label="Propagation RTT (ms)",
        )[0]
        register_bottom(prop_handle)
        median_handle = ax_bottom.axhline(
            summary["median_rtt_ms"],
            color=color_median,
            linestyle="--",
            linewidth=1.4,
            label=f"Median RTT ({summary['median_rtt_ms']:.0f} ms)",
        )
        register_bottom(median_handle)
        p90_handle = ax_bottom.axhline(
            summary["p90_rtt_ms"],
            color=color_p90,
            linestyle=":",
            linewidth=1.4,
            label=f"90th Percentile RTT ({summary['p90_rtt_ms']:.0f} ms)",
        )
        register_bottom(p90_handle)

    if not rtt_df.empty:
        rtt_ylim = max(350.0, float(rtt_df["corrected_rtt_ms"].max() * 1.1))
        ax_bottom.set_ylim(0, rtt_ylim)
    else:
        ax_bottom.set_ylim(0, 350)

    if overuse_times.size:
        overuse_bottom_y = np.full(overuse_times.shape[0], ax_bottom.get_ylim()[0] + 5.0, dtype=float)
        overuse_bottom_handle = ax_bottom.scatter(
            overuse_times,
            overuse_bottom_y,
            marker="^",
            s=80,
            facecolor=color_overuse,
            edgecolor="darkred",
            linewidths=0.4,
            label=f"Overusing Events ({len(overuse_events)})",
            zorder=6,
        )
        register_bottom(overuse_bottom_handle)

    ax_bottom.set_title("RTT Trends & Overuse Events")
    ax_bottom.set_xlabel("Time (seconds)")
    ax_bottom.set_ylabel("RTT (ms)")
    ax_bottom.grid(alpha=0.25, linestyle="--")
    ax_bottom.legend(legend_handles_bottom, legend_labels_bottom, loc="upper right", fontsize=9)

    rtt_lines = [
        f"Median RTT: {summary['median_rtt_ms']:.0f} ms",
        f"90th Percentile RTT: {summary['p90_rtt_ms']:.0f} ms",
        f"Mean RTT: {summary['mean_rtt_ms']:.1f} ms",
        f"Max RTT: {summary['max_rtt_ms']:.0f} ms",
    ]
    annotate_summary(ax_bottom, rtt_lines, location="upper left")

    # Shared X range based on available data
    all_times = []
    for df in (ratio_df, rtt_df, target_df):
        if not df.empty:
            all_times.append(df["time_s"].to_numpy())
    if all_times:
        concatenated = np.concatenate(all_times)
        ax_bottom.set_xlim(concatenated.min(), concatenated.max())
        ax_top.set_xlim(concatenated.min(), concatenated.max())

    plt.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    default_log = pathlib.Path("/home/qwu26/webrtc-local/webrtc_config_results/sender_local.log")
    parser = argparse.ArgumentParser(description="Plot WebRTC GCC metrics from a detailed log file.")
    parser.add_argument(
        "--log",
        default=str(default_log),
        help=f"Path to the WebRTC log file (default: {default_log}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to the output PNG file (default: <log_basename>_dashboard.png).",
    )
    args = parser.parse_args()

    log_path = pathlib.Path(args.log).expanduser().resolve()
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    if args.output:
        output_path = pathlib.Path(args.output).expanduser().resolve()
    else:
        output_path = log_path.with_name(f"{log_path.stem}_dashboard.png")

    raw_data = parse_log(log_path)
    prepared = prepare_data(raw_data)

    ratio_df = prepared.get("ratio", pd.DataFrame())
    rtt_df = prepared.get("rtt", pd.DataFrame())
    gcc_df = prepared.get("gcc", pd.DataFrame())
    target_df = prepared.get("target", pd.DataFrame())

    aligned = build_acked_target_alignment(gcc_df, target_df)
    overuse_events = compute_overuse_events(gcc_df)
    summary = summarize_metrics(aligned, rtt_df)

    plot_dashboard(
        ratio_df=ratio_df,
        rtt_df=rtt_df,
        gcc_df=gcc_df,
        target_df=target_df,
        summary=summary,
        overuse_events=overuse_events,
        output_path=output_path,
    )

    print(f"Dashboard saved to: {output_path}")


if __name__ == "__main__":
    main()
