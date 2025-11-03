# Natural Sorting Utility Guide

## Overview

The natural sorting utility module (`src/utils/sorting.py`) provides comprehensive functions for sorting step identifiers in natural order. This is critical for proper step navigation and progress calculation in the VisGuiAI system.

## The Problem

Step identifiers are strings that combine numbers and optional letters (e.g., "1", "1a", "1b", "2", "10", "10a"). Regular string sorting produces incorrect results:

```python
# WRONG - Regular string sort
["1", "10", "10a", "1a", "1b", "2"]

# CORRECT - Natural sort
["1", "1a", "1b", "2", "10", "10a"]
```

## Purpose

This utility ensures that:
- Steps are displayed in the correct order
- Navigation (next/previous) works correctly
- Progress calculations are accurate
- Comparisons between step identifiers are meaningful

## Functions

### 1. natural_sort_key(identifier: str) -> Tuple[int, str]

Parses a step identifier into a sortable tuple.

**Parameters:**
- `identifier`: A step identifier string (e.g., "1", "1a", "10")

**Returns:**
- Tuple of (numeric_part, letter_part)

**Examples:**
```python
from src.utils.sorting import natural_sort_key

natural_sort_key("1")      # Returns (1, "")
natural_sort_key("1a")     # Returns (1, "a")
natural_sort_key("10")     # Returns (10, "")
natural_sort_key("10a")    # Returns (10, "a")
```

**Edge Cases:**
- Empty string: Returns (0, "")
- Invalid format (e.g., "abc"): Returns (0, "abc")
- Uppercase letters: Normalized to lowercase

---

### 2. sort_step_identifiers(identifiers: List[str]) -> List[str]

Sorts a list of step identifiers in natural order.

**Parameters:**
- `identifiers`: List of step identifier strings

**Returns:**
- New list with identifiers sorted naturally

**Examples:**
```python
from src.utils.sorting import sort_step_identifiers

identifiers = ["10", "1", "2", "1a", "1b", "10a"]
sorted_ids = sort_step_identifiers(identifiers)
# Returns: ["1", "1a", "1b", "2", "10", "10a"]

# Works with any order
unsorted = ["10a", "2", "1", "1b", "1a", "10"]
sorted_ids = sort_step_identifiers(unsorted)
# Returns: ["1", "1a", "1b", "2", "10", "10a"]
```

**Edge Cases:**
- Empty list: Returns []
- Single element: Returns unchanged
- Duplicates: Preserved in output
- Mixed valid/invalid: Invalid identifiers sort first

---

### 3. is_identifier_before(id1: str, id2: str) -> bool

Checks if one identifier comes before another in natural order.

**Parameters:**
- `id1`: First identifier
- `id2`: Second identifier

**Returns:**
- True if id1 comes before id2, False otherwise

**Examples:**
```python
from src.utils.sorting import is_identifier_before

is_identifier_before("1", "2")     # True
is_identifier_before("1a", "1b")   # True
is_identifier_before("1", "10")    # True
is_identifier_before("10", "2")    # False
is_identifier_before("1", "1")     # False (equal)
```

**Use Cases:**
- Validating step order
- Checking if user is moving forward/backward
- Progress calculations

---

### 4. get_next_identifier(current: str, all_identifiers: List[str]) -> Optional[str]

Finds the next identifier in a naturally sorted sequence.

**Parameters:**
- `current`: Current identifier
- `all_identifiers`: List of all available identifiers

**Returns:**
- Next identifier in sequence, or None if at the end

**Examples:**
```python
from src.utils.sorting import get_next_identifier

identifiers = ["1", "1a", "1b", "2", "10", "10a"]

get_next_identifier("1", identifiers)      # "1a"
get_next_identifier("1a", identifiers)     # "1b"
get_next_identifier("1b", identifiers)     # "2"
get_next_identifier("10a", identifiers)    # None (at end)
get_next_identifier("99", identifiers)     # None (not in list)
```

**Use Cases:**
- Implementing "Next Step" button
- Auto-advancing through steps
- Generating step sequences

---

### 5. get_previous_identifier(current: str, all_identifiers: List[str]) -> Optional[str]

Finds the previous identifier in a naturally sorted sequence.

**Parameters:**
- `current`: Current identifier
- `all_identifiers`: List of all available identifiers

**Returns:**
- Previous identifier in sequence, or None if at the start

**Examples:**
```python
from src.utils.sorting import get_previous_identifier

identifiers = ["1", "1a", "1b", "2", "10", "10a"]

get_previous_identifier("1a", identifiers)     # "1"
get_previous_identifier("2", identifiers)      # "1b"
get_previous_identifier("10a", identifiers)    # "10"
get_previous_identifier("1", identifiers)      # None (at start)
get_previous_identifier("99", identifiers)     # None (not in list)
```

**Use Cases:**
- Implementing "Previous Step" button
- Undo functionality
- Step navigation history

---

## Common Use Cases

### Use Case 1: Displaying Steps in Order

```python
from src.utils.sorting import sort_step_identifiers

# Get all step identifiers from database
steps = get_all_steps()  # Returns unsorted list
step_ids = [step.identifier for step in steps]

# Sort them naturally
sorted_ids = sort_step_identifiers(step_ids)

# Display in correct order
for step_id in sorted_ids:
    display_step(step_id)
```

### Use Case 2: Implementing Step Navigation

```python
from src.utils.sorting import get_next_identifier, get_previous_identifier

class StepNavigator:
    def __init__(self, all_step_ids):
        self.all_step_ids = all_step_ids
        self.current_step = None

    def next(self):
        if self.current_step:
            next_step = get_next_identifier(self.current_step, self.all_step_ids)
            if next_step:
                self.current_step = next_step
                return next_step
        return None

    def previous(self):
        if self.current_step:
            prev_step = get_previous_identifier(self.current_step, self.all_step_ids)
            if prev_step:
                self.current_step = prev_step
                return prev_step
        return None
```

### Use Case 3: Progress Calculation

```python
from src.utils.sorting import sort_step_identifiers, is_identifier_before

def calculate_progress(completed_steps, all_steps):
    """Calculate percentage of steps completed."""
    sorted_all = sort_step_identifiers(all_steps)
    total = len(sorted_all)

    completed_count = 0
    for step in sorted_all:
        if step in completed_steps:
            completed_count += 1

    return (completed_count / total) * 100 if total > 0 else 0

def is_step_unlocked(step_id, completed_steps, all_steps):
    """Check if a step can be accessed based on previous completion."""
    sorted_all = sort_step_identifiers(all_steps)
    step_index = sorted_all.index(step_id)

    # First step is always unlocked
    if step_index == 0:
        return True

    # Check if previous step is completed
    previous_step = sorted_all[step_index - 1]
    return previous_step in completed_steps
```

### Use Case 4: Validating Step Sequences

```python
from src.utils.sorting import is_identifier_before, sort_step_identifiers

def validate_step_order(steps_list):
    """Validate that steps are in correct order."""
    sorted_steps = sort_step_identifiers(steps_list)
    return steps_list == sorted_steps

def can_skip_to_step(from_step, to_step, all_steps):
    """Check if user can skip from one step to another."""
    sorted_all = sort_step_identifiers(all_steps)

    if from_step not in sorted_all or to_step not in sorted_all:
        return False

    from_index = sorted_all.index(from_step)
    to_index = sorted_all.index(to_step)

    # Can only skip forward, not backward
    return to_index > from_index
```

### Use Case 5: API Response Sorting

```python
from src.utils.sorting import sort_step_identifiers

@app.get("/api/guides/{guide_id}/steps")
async def get_guide_steps(guide_id: str):
    """Return steps in natural order."""
    steps = await db.get_steps(guide_id)

    # Sort by identifier
    step_ids = [step.identifier for step in steps]
    sorted_ids = sort_step_identifiers(step_ids)

    # Return in sorted order
    sorted_steps = []
    for step_id in sorted_ids:
        step = next(s for s in steps if s.identifier == step_id)
        sorted_steps.append(step)

    return sorted_steps
```

## Edge Cases to Be Aware Of

### 1. Invalid Identifiers
```python
# Invalid identifiers default to (0, identifier)
sort_step_identifiers(["1", "abc", "2"])
# Returns: ["abc", "1", "2"]  # "abc" sorts first
```

### 2. Duplicate Identifiers
```python
# Duplicates are preserved
sort_step_identifiers(["1", "2", "1", "10"])
# Returns: ["1", "1", "2", "10"]

# Navigation finds first occurrence
get_next_identifier("1", ["1", "2", "1", "10"])  # Returns "2"
```

### 3. Empty Strings
```python
natural_sort_key("")  # Returns (0, "")
sort_step_identifiers(["1", "", "2"])  # Returns ["", "1", "2"]
```

### 4. Case Sensitivity
```python
# Uppercase normalized to lowercase
natural_sort_key("1A")  # Returns (1, "a")
natural_sort_key("1a")  # Returns (1, "a")
```

### 5. Whitespace
```python
# Leading/trailing whitespace is stripped
natural_sort_key("  1a  ")  # Returns (1, "a")
```

## Testing

Comprehensive tests are available in `/backend/tests/test_sorting.py`:

```bash
# Run all sorting tests
pytest tests/test_sorting.py -v

# Run specific test class
pytest tests/test_sorting.py::TestNaturalSortKey -v

# Run with coverage
pytest tests/test_sorting.py --cov=src.utils.sorting
```

Test coverage includes:
- 46 total tests
- All edge cases
- Integration scenarios
- Real-world use cases

## Performance Considerations

- **Time Complexity**: O(n log n) for sorting
- **Space Complexity**: O(n) for creating sorted copy
- **Caching**: Consider caching sorted lists if used frequently
- **Database**: For large datasets, consider sorting at database level with custom SQL

## Best Practices

1. Always use these utilities instead of Python's built-in `sorted()` for step identifiers
2. Cache sorted lists when performing multiple operations
3. Validate identifier format before storing in database
4. Use type hints for better IDE support
5. Handle None returns from get_next/get_previous appropriately

## Integration with API

```python
from fastapi import HTTPException
from src.utils.sorting import (
    sort_step_identifiers,
    get_next_identifier,
    get_previous_identifier
)

@app.get("/api/steps/{step_id}/next")
async def get_next_step(step_id: str, guide_id: str):
    """Get the next step in the guide."""
    all_steps = await db.get_guide_steps(guide_id)
    all_ids = [step.identifier for step in all_steps]

    next_id = get_next_identifier(step_id, all_ids)

    if next_id is None:
        raise HTTPException(status_code=404, detail="No next step available")

    return await db.get_step(guide_id, next_id)
```

## Conclusion

This utility module is essential for maintaining correct step order and navigation throughout the VisGuiAI system. Always use these functions when working with step identifiers to ensure consistent and correct behavior.
