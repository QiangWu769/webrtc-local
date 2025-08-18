# WebRTC Diagnostic Data Visualization

## Overview
This directory contains Python scripts for visualizing WebRTC diagnostic events from the `diag_report.txt` file. The visualization shows events organized by timestamp, SubFN (subframe number), and SysFN (system frame number), allowing precise analysis of each event.

## Files

### Main Scripts
- `simple_viz.py` - Simple, reliable visualization script (recommended)
- `diag_viz_clean.py` - More complex visualization with time-series plots
- `diag_bsr.py` - Main diagnostic data collection and parsing script

### Generated Visualizations
- `diag_report_simple_viz.png` - Basic event analysis charts
- `diag_report_visualization.png` - Complex time-series visualization
- `diag_report_combined_visualization.png` - Combined analysis charts

## Usage

### Simple Visualization (Recommended)
```bash
python3 simple_viz.py /path/to/diag_report.txt
```

This creates four charts:
1. **SubFN vs SysFN Distribution** - Shows the relationship between subframe and system frame numbers
2. **SysFN Over Time** - Events plotted by their order in the data file, colored by SubFN
3. **SubFN Distribution** - Histogram of SubFN values
4. **Latency Distribution** - Histogram of pipeline latency (if available)

### Complex Visualization
```bash
python3 diag_viz_clean.py /path/to/diag_report.txt
```

This creates:
1. **Event Timeline** - Time-series plot grouped by SubFN
2. **SubFN vs SysFN Heatmap** - Frequency analysis
3. **Pipeline Latency Over Time** - Latency analysis with statistics

## Data Format

The `diag_report.txt` file contains tab-separated values with columns:
- `RAN_Event_Unix_Timestamp` - Event timestamp in Unix format
- `Bridge_Read_Timestamp` - Bridge processing timestamp  
- `Python_Recv_Timestamp` - Python reception timestamp
- `SubFN` - Subframe number (0-9)
- `SysFN` - System frame number (0-1023)
- `LCG_0`, `LCG_1`, `LCG_2`, `LCG_3` - Logical Channel Group buffer sizes
- `Num_RBs` - Number of resource blocks
- `TBS_Index` - Transport Block Size index
- `Pipeline_Latency_ms` - Processing latency in milliseconds

## Event Analysis

The visualization reveals:
- **Precise Event Timing** - Same timestamp events are differentiated by SubFN/SysFN combinations
- **Resource Allocation Patterns** - SubFN ranges 0-9, SysFN ranges 0-1023
- **Buffer Status** - LCG values show logical channel group buffer states
- **Performance Metrics** - Latency analysis shows processing delays

## Example Output

From the sample data (95,032 events):
- SubFN range: 0-9 (10 unique values)
- SysFN range: 0-1023 (1000 unique values) 
- Events grouped by timestamp show multiple SubFN/SysFN combinations per timestamp
- Pipeline latency statistics available for performance analysis

## Requirements
- Python 3.x
- pandas
- matplotlib 
- numpy

## Notes
- Uses non-interactive matplotlib backend (Agg) for server environments
- Handles large datasets (95K+ events) efficiently
- Generates high-resolution PNG outputs (300 DPI)
- Provides both statistical summaries and visual analysis