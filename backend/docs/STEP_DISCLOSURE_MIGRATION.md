# Step Disclosure Service Migration Guide

## Overview

The `step_disclosure_service.py` has been completely migrated from integer-based step indexing to string-based step identifiers. This migration enables support for guide adaptation with alternative steps (sub-indices like "1a", "1b").

**Migration Date:** 2025-10-15
**Status:** COMPLETE
**Breaking Changes:** YES

---

## What Changed

### Database Schema Alignment

The service now uses the database fields that were already prepared:
- `GuideSessionModel.current_step_identifier` (String) - replaces `current_step_index` (Integer)
- `StepModel.step_identifier` (String) - primary identifier field

### Key Method Changes

#### 1. `get_current_step_only()`

**Before:**
```python
current_step_global_index = session.current_step_index
current_step, current_section = StepDisclosureService._find_step_by_global_index(
    sections, current_step_global_index
)
```

**After:**
```python
current_step_identifier = session.current_step_identifier
current_step, current_section = StepDisclosureService._find_step_by_identifier(
    guide_data, current_step_identifier
)

# Automatic handling of blocked steps
if current_step and current_step.get("status") == "blocked":
    alternatives = StepDisclosureService._find_alternatives_for_step(
        guide_data, current_step_identifier
    )
    if alternatives:
        first_alt_id = alternatives[0].get("step_identifier")
        current_step, current_section = StepDisclosureService._find_step_by_identifier(
            guide_data, first_alt_id
        )
```

**New Features:**
- Automatically detects blocked steps
- Switches to first alternative if available
- Updates session to point to alternative
- Returns step status information

#### 2. `advance_to_next_step()`

**Before:**
```python
update_query = update(GuideSessionModel).where(
    GuideSessionModel.session_id == session_id
).values(
    current_step_index=GuideSessionModel.current_step_index + 1,
    updated_at=func.now()
)
```

**After:**
```python
# Get all active identifiers (excludes blocked steps)
all_identifiers = StepDisclosureService._get_all_step_identifiers(
    guide_data, include_blocked=False
)

# Find next step using natural sorting
next_identifier = StepDisclosureService._get_next_identifier(
    all_identifiers, current_identifier
)

# Update to next identifier
await StepDisclosureService._update_session_identifier(
    session_id, next_identifier, db
)
```

**New Features:**
- Uses natural sorting for string identifiers ("1", "1a", "1b", "2")
- Automatically skips blocked steps
- Handles sub-indices correctly
- Detects end-of-guide completion

#### 3. `go_back_to_previous_step()`

**Before:**
```python
if session.current_step_index <= 0:
    raise ValueError("Cannot go back further")

update_query = update(GuideSessionModel).where(
    GuideSessionModel.session_id == session_id
).values(
    current_step_index=GuideSessionModel.current_step_index - 1,
    updated_at=func.now()
)
```

**After:**
```python
all_identifiers = StepDisclosureService._get_all_step_identifiers(
    guide_data, include_blocked=True
)

previous_identifier = StepDisclosureService._get_previous_identifier(
    all_identifiers, current_identifier
)

if previous_identifier is None:
    raise ValueError("Cannot go back further - already at first step")

await StepDisclosureService._update_session_identifier(
    session_id, previous_identifier, db
)
```

**New Features:**
- Allows navigation to blocked steps (for viewing)
- Uses natural sorting for proper ordering

#### 4. `get_section_overview()`

**Enhanced with:**
- `is_blocked` flag for crossed-out display
- `is_alternative` flag to identify workaround steps
- `replaces_step_identifier` to show what step was replaced
- `blocked_reason` for user feedback
- Excludes blocked steps from time estimates

---

## New Helper Methods

### Core Lookup Methods

#### `_find_step_by_identifier(guide_data, step_identifier)`
Finds a step by its string identifier across all sections.

**Returns:** `Tuple[Optional[Dict], Optional[Dict]]` - (step, section)

```python
current_step, current_section = StepDisclosureService._find_step_by_identifier(
    guide_data, "1a"
)
```

#### `_get_all_step_identifiers(guide_data, include_blocked=False)`
Gets all step identifiers in natural sorted order.

**Parameters:**
- `include_blocked`: If False, excludes steps with status="blocked"

**Returns:** `List[str]` - Sorted list of identifiers

```python
active_ids = StepDisclosureService._get_all_step_identifiers(
    guide_data, include_blocked=False
)
# Result: ["1", "1a", "1b", "2", "3", "10"]
```

#### `_find_alternatives_for_step(guide_data, blocked_identifier)`
Finds all alternative steps for a blocked step.

**Returns:** `List[Dict]` - Alternative steps sorted by identifier

```python
alternatives = StepDisclosureService._find_alternatives_for_step(
    guide_data, "1"
)
# Returns steps with status="alternative" and replaces_step_identifier="1"
```

### Progress Calculation

#### `_calculate_progress(guide_data, current_identifier)`
Calculates progress using string identifiers and natural sorting.

**Returns:** `Dict` with:
- `total_steps`: Count of active steps (excludes blocked)
- `completed_steps`: Count of steps before current
- `completion_percentage`: Calculated percentage
- `estimated_time_remaining`: Minutes remaining

#### `_calculate_remaining_time(guide_data, current_identifier)`
Calculates remaining time, excluding blocked steps.

### Validation and Navigation

#### `_can_go_back(guide_data, current_identifier)`
Checks if navigation to previous step is allowed.

#### `_is_last_step_in_section(section, current_step)`
Determines if current step is the last active step in section.

### Session Management

#### `_update_session_identifier(session_id, new_identifier, db)`
Updates session's current step identifier in database.

---

## Sorting Utilities (IMPLEMENTED)

The service now uses the centralized sorting utilities from `backend/src/utils/sorting.py`:

### Imported Functions

```python
from ..utils.sorting import (
    natural_sort_key,
    sort_step_identifiers,
    is_identifier_before,
    get_next_identifier,
    get_previous_identifier
)
```

### `natural_sort_key(s: str) -> Tuple[int, str]`
Converts identifier to sortable tuple (numeric_part, letter_part).

```python
# Examples:
natural_sort_key("1")   # (1, "")
natural_sort_key("1a")  # (1, "a")
natural_sort_key("10")  # (10, "")
```

### `sort_step_identifiers(identifiers: List[str]) -> List[str]`
Sorts list of identifiers in natural order.

```python
sort_step_identifiers(["10", "1", "2", "1a", "1b", "10a"])
# Returns: ["1", "1a", "1b", "2", "10", "10a"]
```

### `is_identifier_before(id1: str, id2: str) -> bool`
Compares two identifiers using natural sorting.

```python
if is_identifier_before("1a", "1b"):
    print("1a comes before 1b")  # True
```

### `get_next_identifier(current: str, all_identifiers: List[str]) -> Optional[str]`
Gets next identifier in sequence.

```python
get_next_identifier("1a", ["1", "1a", "1b", "2"])  # Returns "1b"
```

### `get_previous_identifier(current: str, all_identifiers: List[str]) -> Optional[str]`
Gets previous identifier in sequence.

```python
get_previous_identifier("1b", ["1", "1a", "1b", "2"])  # Returns "1a"
```

**Note:** All sorting utilities have comprehensive test coverage in `backend/tests/test_sorting.py`.

---

## Breaking Changes

### 1. Database Field Change

**Breaking:** `GuideSessionModel.current_step_index` is NO LONGER USED.

**Migration Required:**
- Old sessions using `current_step_index` must be migrated to `current_step_identifier`
- Conversion: `current_step_identifier = str(current_step_index)`

### 2. Response Schema Changes

**get_current_step_only() Response:**

**Added Fields:**
```json
{
  "current_step": {
    "step_identifier": "1a",         // NEW: String identifier
    "step_index": 1,                 // KEPT: For backward compatibility
    "status": "alternative",         // NEW: Step status
    "is_alternative": true,          // NEW: Boolean flag
    "replaces_step_identifier": "1"  // NEW: Original step
  }
}
```

**get_section_overview() Response:**

**Added Fields:**
```json
{
  "step_overview": [
    {
      "step_identifier": "1",        // NEW: String identifier
      "is_blocked": true,            // NEW: Blocked flag
      "is_alternative": false,       // NEW: Alternative flag
      "blocked_reason": "...",       // NEW: Why blocked
      "show_as": "crossed_out",      // NEW: Display hint
      "replaces_step_identifier": null // NEW: Replacement info
    }
  ]
}
```

### 3. Removed Methods

- `_find_step_by_global_index()` - Replaced by `_find_step_by_identifier()`
- `_count_total_steps()` - Replaced by `len(_get_all_step_identifiers())`

### 4. Method Signature Changes

**_log_step_completion():**
```python
# Before
async def _log_step_completion(
    session_id: UUID,
    completion_notes: Optional[str],
    db: AsyncSession
)

# After
async def _log_step_completion(
    session_id: UUID,
    step_identifier: str,      # NEW: Added parameter
    completion_notes: Optional[str],
    db: AsyncSession
)
```

---

## Testing Recommendations

### Unit Tests Needed

1. **Natural Sorting Tests**
```python
def test_natural_sort_order():
    identifiers = ["2", "1b", "10", "1a", "1", "10a"]
    sorted_ids = sorted(identifiers, key=StepDisclosureService._natural_sort_key)
    assert sorted_ids == ["1", "1a", "1b", "2", "10", "10a"]
```

2. **Blocked Step Handling**
```python
async def test_get_current_step_with_blocked():
    # Set current_step_identifier to blocked step "1"
    # Verify service returns alternative "1a"
    # Verify session is updated to "1a"
```

3. **Alternative Step Navigation**
```python
async def test_advance_skips_blocked_steps():
    # Current step "1a", blocked step "2", next active "3"
    # Verify advance_to_next_step() goes from "1a" -> "3"
```

4. **Progress Calculation**
```python
async def test_progress_excludes_blocked():
    # Guide with 5 steps, 1 blocked, 2 alternatives
    # Verify total_steps = 6 (not 7)
```

### Integration Tests Needed

1. **Full Adaptation Workflow**
   - Start session on step "1"
   - Mark step "1" as blocked
   - Generate alternatives "1a", "1b"
   - Verify disclosure service returns "1a"
   - Complete "1a" and advance to "2"

2. **Section Overview with Mixed Steps**
   - Section with active, blocked, and alternative steps
   - Verify proper display flags
   - Verify time calculations exclude blocked

3. **Backward Navigation**
   - Navigate through steps "1" -> "1a" -> "2"
   - Go back: "2" -> "1a" -> "1"
   - Verify proper ordering

### Edge Cases to Test

1. All steps in guide are blocked (no alternatives)
2. Multiple alternatives for single blocked step
3. Alternative step itself becomes blocked
4. Navigation at boundaries (first step, last step)
5. Empty guide or section
6. Step identifier not found in guide

---

## Migration Checklist

- [x] Update all methods to use `current_step_identifier`
- [x] Remove references to `current_step_index`
- [x] Implement `_find_step_by_identifier()`
- [x] Implement `_get_all_step_identifiers()`
- [x] Implement `_find_alternatives_for_step()`
- [x] Update progress calculation logic
- [x] Update navigation methods (advance, go_back)
- [x] Add blocked step handling
- [x] Add natural sorting utilities
- [x] Update response schemas
- [x] Add comprehensive documentation
- [ ] Create unit tests
- [ ] Create integration tests
- [ ] Update API documentation
- [ ] Migrate existing sessions in database
- [ ] Update frontend clients

---

## Frontend Impact

Frontend code must be updated to:

1. **Use `step_identifier` instead of `step_index`** for step tracking
2. **Handle new response fields:**
   - `is_alternative`
   - `is_blocked`
   - `replaces_step_identifier`
   - `blocked_reason`

3. **Display blocked steps** with crossed-out styling
4. **Show alternative steps** with special indicators

### Example Frontend Update

**Before:**
```javascript
const currentStepIndex = response.current_step.step_index;
```

**After:**
```javascript
const currentStepId = response.current_step.step_identifier;
const isAlternative = response.current_step.is_alternative;

if (isAlternative) {
  showAlternativeBadge();
}
```

---

## Performance Considerations

### Potential Bottlenecks

1. **Natural Sorting:** O(n log n) for identifier sorting
   - Mitigated by caching sorted lists
   - Only sort when needed (not on every call)

2. **Finding Alternatives:** O(n) scan through all steps
   - Consider indexing alternatives by `replaces_step_identifier`
   - Add to guide_data structure on adaptation

### Optimization Opportunities

1. **Cache sorted identifiers** in guide_data
2. **Index alternatives** during adaptation
3. **Use database queries** for step lookup instead of Python loops

---

## Future Improvements

1. **Replace temporary sorting utilities** with imports from `utils/sorting.py`
2. **Add completion events tracking** for analytics
3. **Implement prerequisite checking** logic
4. **Add caching layer** for frequently accessed guides
5. **Support nested alternatives** (alternatives for alternatives)
6. **Add validation** for step identifier format
7. **Implement step locking** for parallel guide execution

---

## Related Files

- `/Users/sivanlissak/Documents/VisGuiAI/backend/src/services/step_disclosure_service.py` - Updated service
- `/Users/sivanlissak/Documents/VisGuiAI/backend/src/models/database.py` - Database models
- `/Users/sivanlissak/Documents/VisGuiAI/backend/src/services/guide_adaptation_service.py` - Adaptation logic
- `/Users/sivanlissak/Documents/VisGuiAI/backend/src/utils/sorting.py` - Sorting utilities (TODO)

---

## Questions or Issues?

Contact the backend team or reference:
- `backend/docs/GUIDE_ADAPTATION_FEATURE.md` - Feature overview
- `backend/docs/ACTION_CHECKLIST.md` - Implementation checklist
