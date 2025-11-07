#!/usr/bin/env python3
"""Script to add 'from err' to raise statements inside except blocks."""

import re
from pathlib import Path


def fix_exception_handling(file_path: Path) -> tuple[bool, int]:
    """Fix exception handling in a Python file.

    Returns:
        (changed, count) where changed is True if file was modified,
        and count is number of fixes made
    """
    content = file_path.read_text()
    original_content = content
    fixes = 0

    # Pattern to match raise statements inside except blocks
    # This looks for:
    # except SomeError as e:
    #     ...
    #     raise SomeOtherError(...)

    # We need to find except blocks and add 'from e' to raises
    lines = content.split('\n')
    new_lines = []
    in_except_block = False
    except_var = None
    indent_level = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # Check if we're entering an except block
        except_match = re.match(r'except\s+\w+\s+as\s+(\w+):', stripped)
        if except_match:
            in_except_block = True
            except_var = except_match.group(1)
            indent_level = len(line) - len(stripped)
            new_lines.append(line)
            i += 1
            continue

        # Check if we're leaving the except block (dedent or new except/finally)
        if in_except_block:
            current_indent = len(line) - len(stripped) if stripped else indent_level + 4
            if stripped and current_indent <= indent_level:
                in_except_block = False
                except_var = None

        # Fix raise statements in except blocks
        if in_except_block and stripped.startswith('raise '):
            # Check if already has 'from'
            if ' from ' not in line:
                # Add 'from except_var' before the closing parenthesis or at end
                if line.rstrip().endswith(')'):
                    # Multi-line or single-line with parens
                    line = line.rstrip()[:-1] + f') from {except_var}'
                    fixes += 1
                elif line.rstrip().endswith(','):
                    # Part of multi-line, need to find closing paren
                    fixed_line = line
                    new_lines.append(fixed_line)
                    i += 1
                    # Continue collecting lines until we find the closing paren
                    while i < len(lines):
                        next_line = lines[i]
                        if ')' in next_line and ' from ' not in next_line:
                            next_line = next_line.replace(')', f') from {except_var}', 1)
                            new_lines.append(next_line)
                            fixes += 1
                            i += 1
                            break
                        new_lines.append(next_line)
                        i += 1
                    continue
                else:
                    # Simple raise without parens
                    line = line.rstrip() + f' from {except_var}'
                    fixes += 1

        new_lines.append(line)
        i += 1

    new_content = '\n'.join(new_lines)
    changed = new_content != original_content

    if changed:
        file_path.write_text(new_content)
        print(f"✓ Fixed {fixes} exceptions in {file_path}")

    return changed, fixes


def main():
    """Fix all Python files in src/ directory."""
    src_dir = Path(__file__).parent / 'src'
    total_files = 0
    total_fixes = 0

    for py_file in src_dir.rglob('*.py'):
        changed, fixes = fix_exception_handling(py_file)
        if changed:
            total_files += 1
            total_fixes += fixes

    print(f"\n Summary: Fixed {total_fixes} exceptions across {total_files} files")


if __name__ == '__main__':
    main()
