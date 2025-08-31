#!/usr/bin/env python
# Fix all f-strings in diag_bsr.py

import re

with open('diag_bsr.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'f"' in line or "f'" in line:
        # Manual replacement for each f-string pattern
        if 'fp.write(f"' in line:
            # Extract the content and replace placeholders
            match = re.search(r'fp\.write\(f"([^"]+)"\)', line)
            if match:
                content = match.group(1)
                # Find all {expr} patterns
                placeholders = re.findall(r'\{([^}]+)\}', content)
                # Replace {expr} with {}
                new_content = re.sub(r'\{[^}]+\}', '{}', content)
                # Build format arguments
                if placeholders:
                    format_args = ', '.join(placeholders)
                    line = line[:match.start()] + 'fp.write("{}".format({}))'.format(new_content, format_args) + line[match.end():]
                else:
                    line = line[:match.start()] + 'fp.write("{}")'.format(new_content) + line[match.end():]
        elif 'print(f"' in line:
            match = re.search(r'print\(f"([^"]+)"\)', line)
            if match:
                content = match.group(1)
                placeholders = re.findall(r'\{([^}]+)\}', content)
                new_content = re.sub(r'\{[^}]+\}', '{}', content)
                if placeholders:
                    format_args = ', '.join(placeholders)
                    line = line[:match.start()] + 'print("{}".format({}))'.format(new_content, format_args) + line[match.end():]
                else:
                    line = line[:match.start()] + 'print("{}")'.format(new_content) + line[match.end():]
        elif '= f"' in line:
            match = re.search(r'= f"([^"]+)"', line)
            if match:
                content = match.group(1)
                placeholders = re.findall(r'\{([^}]+)\}', content)
                new_content = re.sub(r'\{[^}]+\}', '{}', content)
                if placeholders:
                    format_args = ', '.join(placeholders)
                    line = line[:match.start()] + '= "{}".format({})'.format(new_content, format_args) + line[match.end():]
                else:
                    line = line[:match.start()] + '= "{}"'.format(new_content) + line[match.end():]
        elif "f'" in line:
            # Handle single quote f-strings
            match = re.search(r"= f'([^']+)'", line)
            if match:
                content = match.group(1)
                placeholders = re.findall(r'\{([^}]+)\}', content)
                new_content = re.sub(r'\{[^}]+\}', '{}', content)
                if placeholders:
                    format_args = ', '.join(placeholders)
                    line = line[:match.start()] + '= "{}".format({})'.format(new_content, format_args) + line[match.end():]
    new_lines.append(line)

with open('diag_bsr.py', 'w') as f:
    f.writelines(new_lines)

print("Fixed all f-strings")
