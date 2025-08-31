#!/usr/bin/env python
# Fix all remaining f-strings in diag_bsr.py

import re

with open('diag_bsr.py', 'r') as f:
    content = f.read()

# Pattern to match f-strings
replacements = [
    (r'print\(f"([^"]+)"\)', lambda m: 'print("{}")'.format(m.group(1).replace('{', '{}'))),
    (r'fp\.write\(f"([^"]+)"\)', lambda m: 'fp.write("{}")'.format(m.group(1).replace('{', '{}'))),
    (r'= f"([^"]+)"', lambda m: '= "{}"'.format(m.group(1).replace('{', '{}'))),
]

# Manual replacements for specific f-strings
manual_replacements = [
    ('print(f"[INFO] Device timestamp written to {self._report_filename}")',
     'print("[INFO] Device timestamp written to {}".format(self._report_filename))'),
    ('print(f"Error writing timestamp header: {e}")',
     'print("Error writing timestamp header: {}".format(e))'),
    ('print(f"--- Latency Analysis ---")',
     'print("--- Latency Analysis ---")'),
    ('print(f"T_ran_event: {ts_ran_event}")',
     'print("T_ran_event: {}".format(ts_ran_event))'),
    ('print(f"T_bridge_read: {ts_bridge_read}")',
     'print("T_bridge_read: {}".format(ts_bridge_read))'),
    ('print(f"Diag Pipeline Latency: {diag_pipeline_latency_ms:.3f}ms")',
     'print("Diag Pipeline Latency: {:.3f}ms".format(diag_pipeline_latency_ms))'),
]

for old, new in manual_replacements:
    content = content.replace(old, new)

with open('diag_bsr.py', 'w') as f:
    f.write(content)

print("Fixed f-strings in diag_bsr.py")
