#!/usr/bin/env python3
"""Fix raise statements in except blocks to include 'from e'."""

import sys
from pathlib import Path


def fix_raises_in_file(file_path: Path) -> int:
    """Fix raise statements without 'from' in except blocks.

    Returns number of fixes made.
    """
    lines = file_path.read_text().splitlines()
    fixed = []
    fixes_made = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is an except clause
        if 'except' in line and ' as ' in line and ':' in line:
            # Extract the exception variable name
            parts = line.split(' as ')
            if len(parts) >= 2:
                var_part = parts[1].split(':')[0].strip()
                except_var = var_part

                # Now look for raise statements in this except block
                base_indent = len(line) - len(line.lstrip())
                fixed.append(line)
                i += 1

                # Process the except block
                while i < len(lines):
                    curr_line = lines[i]
                    curr_stripped = curr_line.lstrip()

                    # Check if we've left the except block
                    if curr_stripped and not curr_stripped.startswith('#'):
                        curr_indent = len(curr_line) - len(curr_stripped)
                        if curr_indent <= base_indent:
                            # Left the except block
                            break

                    # Check if this is a raise statement
                    if curr_stripped.startswith('raise ') and ' from ' not in curr_line:
                        # Check if this is a multi-line raise
                        if curr_line.rstrip().endswith(',') or '(' in curr_line and ')' not in curr_line:
                            # Multi-line raise - need to find the end
                            raise_lines = [curr_line]
                            i += 1
                            while i < len(lines):
                                raise_lines.append(lines[i])
                                if ')' in lines[i]:
                                    # Found the end
                                    # Add 'from except_var' after the closing paren
                                    last_line = raise_lines[-1]
                                    if last_line.rstrip().endswith(')'):
                                        raise_lines[-1] = last_line.rstrip() + f' from {except_var}'
                                        fixes_made += 1
                                    fixed.extend(raise_lines)
                                    i += 1
                                    break
                                i += 1
                            continue
                        else:
                            # Single line raise
                            if curr_line.rstrip().endswith(')'):
                                fixed.append(curr_line.rstrip() + f' from {except_var}')
                            else:
                                fixed.append(curr_line.rstrip() + f' from {except_var}')
                            fixes_made += 1
                            i += 1
                            continue

                    fixed.append(curr_line)
                    i += 1
                continue

        fixed.append(line)
        i += 1

    if fixes_made > 0:
        file_path.write_text('\n'.join(fixed) + '\n')
        print(f"✓ {file_path}: Fixed {fixes_made} raise statements")

    return fixes_made


def main():
    """Fix all Python files in src/."""
    src_dir = Path('src')
    total_fixes = 0
    total_files = 0

    for py_file in sorted(src_dir.rglob('*.py')):
        fixes = fix_raises_in_file(py_file)
        if fixes > 0:
            total_fixes += fixes
            total_files += 1

    print(f"\n{'='*60}")
    print(f"Summary: Fixed {total_fixes} raise statements in {total_files} files")
    print(f"{'='*60}")
    return 0 if total_fixes > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
