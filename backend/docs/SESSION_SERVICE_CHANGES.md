# Session Service Migration: Integer Index to String Identifier

## Overview
This document details the migration of the session service from using integer-based step indices (`current_step_index`) to string-based step identifiers (`current_step_identifier`). This change enables support for adaptive guide features including sub-steps (e.g., "1a", "1b") and alternative paths.

## Date
2025-10-15

## Changes Made

### 1. Database Model (`backend/src/models/database.py`)
**Status**: Already updated (database migration 002)
- `GuideSessionModel.current_step_index` (Integer) → `GuideSessionModel.current_step_identifier` (String(10))
- Default value: `"0"` (string)
- Supports formats: "0", "1", "2", "1a", "1b", etc.

### 2. Pydantic Schemas

#### 2.1 GuideSession Schemas (`shared/schemas/guide_session.py`)
- **GuideSessionBase.current_step_index** (int) → **current_step_identifier** (str)
  - Type: `str` with max_length=10
  - Default: `"0"`
  - Description: "Current step identifier (e.g., '0', '1', '1a')"

- **GuideSessionUpdate.current_step_index** (Optional[int]) → **current_step_identifier** (Optional[str])
  - Type: `Optional[str]` with max_length=10
  - Allows updating step identifier

#### 2.2 API Response Schemas (`shared/schemas/api_responses.py`)
- **SessionResponse.current_step_index** (int) → **current_step_identifier** (str)
  - Type: `str` with max_length=10
  - Field validation: max_length=10
  - Description: "Current step identifier (e.g., '0', '1', '1a')"

- **ProgressResponse.current_step_index** (Optional[int]) → **current_step_identifier** (Optional[str])
  - Type: `Optional[str]` with max_length=10
  - Description: "Current step identifier"

### 3. Session Service (`backend/src/services/session_service.py`)

#### 3.1 Methods Updated

##### create_session() - Line 45-104
**Before**:
```python
current_step_index=0
# Return SessionResponse with current_step_index=0
```

**After**:
```python
current_step_identifier="0"
# Return SessionResponse with current_step_identifier="0"
```

##### create_session_simple() - Line 106-163
**Before**:
```python
current_step_index=0
# Return SessionResponse with current_step_index=0
```

**After**:
```python
current_step_identifier="0"
# Return SessionResponse with current_step_identifier="0"
```

##### get_session() - Line 165-218
**Before**:
```python
if guide and 0 <= session_model.current_step_index < len(guide.steps):
    current_step = guide.steps[session_model.current_step_index]
# SessionResponse with current_step_index
```

**After**:
```python
if guide and guide.steps:
    current_step = self._find_step_by_identifier(
        guide.steps,
        session_model.current_step_identifier
    )
# SessionResponse with current_step_identifier
```

##### update_session() - Line 226-283
**Before**:
```python
current_step_index=session_model.current_step_index
```

**After**:
```python
current_step_identifier=session_model.current_step_identifier
```

##### get_user_sessions() - Line 285-314
**Before**:
```python
current_step_index=session.current_step_index
```

**After**:
```python
current_step_identifier=session.current_step_identifier
```

##### advance_to_next_step() - Line 316-363
**Major refactor**:

**Before**:
```python
current_index = session_detail.session.current_step_index
if current_index + 1 >= guide.total_steps:
    # Complete session
next_index = current_index + 1
update(...).values(current_step_index=next_index)
```

**After**:
```python
current_identifier = session_detail.session.current_step_identifier
next_identifier = self._get_next_step_identifier(guide.steps, current_identifier)
if not next_identifier:
    # Complete session
update(...).values(current_step_identifier=next_identifier)
```

#### 3.2 SQL Update Queries Modified
- Line 347-352: `update(GuideSessionModel).values(current_step_index=...)` → `values(current_step_identifier=...)`

#### 3.3 Redis Cache Methods Updated

##### _cache_session_data() - Line 376-391
**Before**:
```python
"current_step_index": session.current_step_index
```

**After**:
```python
"current_step_identifier": session.current_step_identifier
```

##### _update_session_cache() - Line 393-405
**Before**:
```python
"current_step_index": session.current_step_index
```

**After**:
```python
"current_step_identifier": session.current_step_identifier
```

#### 3.4 New Helper Methods Added

##### _find_step_by_identifier() - Line 431-446
```python
def _find_step_by_identifier(self, steps: List, identifier: str) -> Optional:
    """Find a step by its identifier.

    Args:
        steps: List of Step objects
        identifier: String identifier (e.g., "0", "1", "1a", "2b")

    Returns:
        The matching Step object or None
    """
```
- Searches for step by `step_identifier` attribute
- Falls back to `step_index` for backward compatibility
- Returns matching Step or None

##### _get_next_step_identifier() - Line 448-480
```python
def _get_next_step_identifier(self, steps: List, current_identifier: str) -> Optional[str]:
    """Get the next step identifier after the current one.

    Args:
        steps: List of Step objects
        current_identifier: Current step identifier

    Returns:
        Next step identifier as string, or None if at the end
    """
```
- Finds current step in list
- Returns next step's identifier
- Returns None if at end of guide
- Handles both `step_identifier` and `step_index` attributes

##### _validate_step_identifier() - Line 482-501
```python
def _validate_step_identifier(self, identifier: str) -> bool:
    """Validate step identifier format.

    Valid formats:
    - Simple integers: "0", "1", "2", etc.
    - Sub-indices: "1a", "1b", "2a", etc.
    - Max length: 10 characters
    """
```
- Validates format using regex: `^\d+[a-z]?$`
- Ensures max length of 10 characters
- Allows: "0", "1", "42", "1a", "2b", etc.
- Rejects: "", "abc", "1ab", "1A", "-1", etc.

## Breaking Changes

### API Responses
**Impact**: HIGH - All API consumers must update

#### SessionResponse
```json
// OLD
{
  "session_id": "uuid",
  "current_step_index": 0
}

// NEW
{
  "session_id": "uuid",
  "current_step_identifier": "0"
}
```

#### ProgressResponse
```json
// OLD
{
  "current_step_index": 1
}

// NEW
{
  "current_step_identifier": "1"
}
```

### Session Creation
**Impact**: None - Internal change only
- Sessions still initialize with "0" (string instead of 0 integer)
- Backward compatible with existing behavior

### Session Queries
**Impact**: Medium - Database queries updated
- All queries now use `current_step_identifier` column
- Migration 002 handles data conversion
- Old data automatically converted from "0", "1", "2" etc.

## Migration Notes

### For Frontend/API Clients
1. **Update response parsing**:
   ```javascript
   // OLD
   const currentIndex = session.current_step_index; // number

   // NEW
   const currentIdentifier = session.current_step_identifier; // string
   ```

2. **Handle sub-indices**:
   ```javascript
   // NEW: Support for adaptive steps
   if (currentIdentifier.includes('a') || currentIdentifier.includes('b')) {
     // This is a sub-step (alternative path)
   }
   ```

3. **Update session update requests**:
   ```javascript
   // OLD
   updateSession({ current_step_index: 5 })

   // NEW
   updateSession({ current_step_identifier: "5" })
   ```

### For Backend Services
1. **Use helper methods**:
   - Use `_find_step_by_identifier()` to locate steps
   - Use `_get_next_step_identifier()` to navigate
   - Use `_validate_step_identifier()` to validate input

2. **Update service integrations**:
   - Step disclosure service: Already updated
   - Guide adaptation service: Already updated
   - Progress tracker: Uses step_id (UUID), no changes needed

3. **Database queries**:
   - All queries updated to use `current_step_identifier`
   - No more integer comparisons needed
   - String comparison: `WHERE current_step_identifier = '1a'`

## Progress Tracker Implications

### Current Status
The Progress Tracker already uses UUID-based step tracking:
- `current_step_id` (UUID) - References actual step
- `completed_steps` (Array[UUID])
- `remaining_steps` (Array[UUID])

### No Direct Impact
- Progress tracker doesn't use step indices
- Works with any step identification method
- Compatible with adaptive steps
- No changes needed to progress tracker model

### Integration Notes
- Session service manages `current_step_identifier`
- Progress tracker manages `current_step_id` (UUID)
- These are coordinated but independent
- Session identifier is user-facing (display)
- Progress tracker UUID is internal (tracking)

## Validation Added

### Identifier Format Validation
```python
_validate_step_identifier(identifier: str) -> bool
```
- Pattern: `^\d+[a-z]?$`
- Max length: 10 characters
- Examples:
  - Valid: "0", "1", "99", "1a", "2b", "10z"
  - Invalid: "", "abc", "1ab", "1A", "-1", " 1", "1 "

### Usage Recommendations
1. Validate identifiers before database insertion
2. Validate user input when updating sessions
3. Use validation in API endpoint request handlers
4. Add validation to adaptive step generation

## Testing Requirements

### Unit Tests Needed
1. Test `_find_step_by_identifier()` with:
   - Simple indices: "0", "1", "2"
   - Sub-indices: "1a", "1b", "2a"
   - Non-existent identifiers
   - Empty step lists

2. Test `_get_next_step_identifier()` with:
   - Sequential steps: "0" → "1" → "2"
   - Sub-steps: "1" → "1a" → "1b" → "2"
   - Last step returns None
   - Empty/invalid identifiers

3. Test `_validate_step_identifier()` with:
   - Valid formats
   - Invalid formats
   - Edge cases (length, special chars)

### Integration Tests Needed
1. Session creation with string identifier
2. Step advancement through guide
3. Step advancement with sub-steps
4. Cache updates with identifiers
5. Multi-service coordination (session + disclosure + adaptation)

### Contract Tests Needed
1. API response schema validation
2. Session creation response format
3. Session detail response format
4. Progress response format
5. Session list response format

## Rollback Procedure

If rollback is needed:
1. Run migration 002 downgrade
2. Revert schema changes in `shared/schemas/`
3. Revert service changes in `backend/src/services/session_service.py`
4. Restart backend services
5. Clear Redis cache

**Warning**: Rollback will lose sub-step information (1a → 1, 1b → 1)

## Compatibility

### Backward Compatibility
- Old integer indices ("0", "1", "2") work as before
- String representation maintains same values
- No functional change for simple sequential guides

### Forward Compatibility
- Supports adaptive guides with sub-steps
- Enables alternative paths (1a, 1b branches)
- Allows guide restructuring without re-indexing

## Performance Considerations

### No Significant Impact
- String comparison is negligible overhead
- 10-character limit ensures small memory footprint
- Index on `current_step_identifier` column maintains query performance

### Cache Impact
- Redis values change from int to string
- Minimal size difference
- No performance degradation expected

## Related Changes

### Already Updated
- Database migration 002: `current_step_index` → `current_step_identifier`
- Step disclosure service: Uses string identifiers
- Guide adaptation service: Generates sub-step identifiers

### Pending Updates
- API endpoint handlers (if any direct index access)
- Frontend components consuming session API
- Integration test fixtures
- Contract test expectations
- API documentation/OpenAPI spec

## Verification Checklist

- [x] All occurrences of `current_step_index` found and documented
- [x] All methods in session_service.py updated
- [x] All schemas updated (GuideSession, SessionResponse, ProgressResponse)
- [x] SQL update queries modified
- [x] Redis cache methods updated
- [x] Helper methods added for identifier handling
- [x] Validation method added
- [x] Type hints updated (int → str)
- [x] Default values updated (0 → "0")
- [x] Backward compatibility considered
- [x] Breaking changes documented
- [x] Migration notes provided
- [ ] Unit tests written
- [ ] Integration tests updated
- [ ] Contract tests updated
- [ ] API documentation updated

## Status: SUCCESS

All session service code successfully updated to use string identifiers. The service is now compatible with the updated database schema and ready for adaptive guide features.

## Next Steps

1. Update any API endpoint handlers that directly access step indices
2. Write comprehensive unit tests for new helper methods
3. Update integration tests to verify string identifier behavior
4. Update contract tests to expect string identifiers in responses
5. Update API documentation/OpenAPI specification
6. Coordinate with frontend team on API changes
7. Monitor Redis cache after deployment
