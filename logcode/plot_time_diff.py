import argparse
import sys
from datetime import datetime
from typing import List, Tuple


def read_time_differences(report_path: str) -> Tuple[List[datetime], List[float]]:
    """
    Read the diag report file and compute latency per line vs time.

    Supports two formats:
    - New format (tab-separated header includes 'Pipeline_Latency_ms'):
      X = Bridge_Read_Timestamp (Unix float) as datetime
      Y = Pipeline_Latency_ms (milliseconds)
    - Old format (first column is Unix_Timestamp_At_Print, last is RAN_Event_Unix_TS):
      X = Unix_Timestamp_At_Print as datetime
      Y = (Unix_Timestamp_At_Print - RAN_Event_Unix_TS) * 1000 (milliseconds)
    """
    x_times: List[datetime] = []
    y_ms: List[float] = []

    try:
        with open(report_path, "r", encoding="utf-8") as f:
            header: List[str] = []
            # Read until we find a non-empty line; treat the first as header if it contains text
            pos = f.tell()
            first_line = f.readline()
            if first_line:
                first_parts = first_line.strip().split("\t")
                header = [h.strip() for h in first_parts]
            else:
                return x_times, y_ms

            is_new_format = "Pipeline_Latency_ms" in header and "Bridge_Read_Timestamp" in header

            # For new format, build column index map
            col_index = {name: idx for idx, name in enumerate(header)} if is_new_format else {}

            if not is_new_format:
                # Not the new format; rewind to include this line in processing as data/header
                f.seek(pos)

            for line_number, line in enumerate(f, start=2 if is_new_format else 1):
                stripped = line.strip()
                if not stripped:
                    continue
                parts = stripped.split("\t")

                if is_new_format:
                    # Expect at least latency and bridge ts columns
                    try:
                        bridge_ts_unix = float(parts[col_index["Bridge_Read_Timestamp"]])
                        latency_ms = float(parts[col_index["Pipeline_Latency_ms"]])
                    except (KeyError, ValueError, IndexError):
                        continue

                    try:
                        x_time = datetime.fromtimestamp(bridge_ts_unix)
                    except (OverflowError, OSError, ValueError):
                        x_time = datetime.fromtimestamp(0)

                    x_times.append(x_time)
                    y_ms.append(latency_ms)
                else:
                    # Old format fallback
                    if len(parts) < 11:
                        continue
                    try:
                        unix_timestamp_at_print = float(parts[0])
                        ran_event_unix_ts = float(parts[10])
                    except ValueError:
                        # header or malformed row
                        continue

                    latency_ms = (unix_timestamp_at_print - ran_event_unix_ts) * 1000.0
                    try:
                        x_time = datetime.fromtimestamp(unix_timestamp_at_print)
                    except (OverflowError, OSError, ValueError):
                        x_time = datetime.fromtimestamp(0)

                    x_times.append(x_time)
                    y_ms.append(latency_ms)
    except FileNotFoundError:
        print(f"Error: file not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    return x_times, y_ms


def plot_differences(x_times: List[datetime], y_ms: List[float], title: str, save_path: str = None, show: bool = True) -> None:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except Exception as exc:
        print("Error: matplotlib is required. Install via: pip install matplotlib", file=sys.stderr)
        print(f"Details: {exc}", file=sys.stderr)
        sys.exit(1)

    if not x_times:
        print("No data to plot (empty or malformed file).", file=sys.stderr)
        sys.exit(2)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x_times, y_ms, linewidth=1.2)

    ax.set_title(title)
    ax.set_xlabel("Time (Unix_Timestamp_At_Print)")
    ax.set_ylabel("Latency (ms)")

    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.AutoDateFormatter(ax.xaxis.get_major_locator()))
    fig.autofmt_xdate()
    ax.grid(True, linestyle='--', alpha=0.4)

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot to: {save_path}")

    if show:
        plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot per-line time difference between Unix_Timestamp_At_Print and RAN_Event_Unix_TS.")
    parser.add_argument("--file", default="diag_report.txt", help="Path to diag report file (TSV)")
    parser.add_argument("--save", default=None, help="Optional path to save the plot image (e.g., plot.png)")
    parser.add_argument("--no-show", action="store_true", help="Do not show the plot window (use with --save)")
    args = parser.parse_args()

    x_times, y_ms = read_time_differences(args.file)
    title = f"Latency over time ({len(y_ms)} points)"
    plot_differences(x_times, y_ms, title, save_path=args.save, show=(not args.no_show))


if __name__ == "__main__":
    main()

