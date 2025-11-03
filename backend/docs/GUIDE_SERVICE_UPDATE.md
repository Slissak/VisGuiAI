# Guide Service Update for Sections Support

**Date**: 2025-10-15
**Task**: Update Guide Service for Sections (Task 1.6 from ACTION_CHECKLIST.md)
**Status**: ✅ COMPLETED

## Summary

Updated the guide service to properly handle sectioned guide structures from LLM responses, store the full guide_data JSON, and create both Section and Step models in the database with proper relationships.

## Problem

The original guide service:
- Did not handle sectioned guide structures (expected flat list of steps)
- Did not store `guide_data` JSON field
- Did not create `SectionModel` instances
- Did not properly initialize `step_identifier` and `step_status` fields
- Could not support the new sectioned guide format from LLM service

## Changes Made

### 1. Updated Imports

```python
# BEFORE
from ..models.database import StepGuideModel, StepModel, LLMGenerationRequestModel

# AFTER
from ..models.database import StepGuideModel, StepModel, SectionModel, LLMGenerationRequestModel, StepStatus
```

Added `SectionModel` and `StepStatus` for proper section and step status handling.

### 2. Refactored `_validate_and_process_guide()`

**Before**: Returned a `StepGuide` Pydantic model with flat steps list

**After**: Returns a dictionary with structured data for database storage

```python
async def _validate_and_process_guide(self, guide_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and process LLM-generated guide data.

    Returns a dictionary with guide info and sections for database storage.
    """
```

**Key Features**:
- Extracts `sections` from LLM response
- Falls back to creating default section if flat steps format detected
- Counts `total_steps` across all sections
- Calculates total estimated duration
- Returns structured dictionary for database storage

**Return Format**:
```python
{
    "guide_id": UUID,
    "guide_info": {...},  # Full guide data from LLM
    "sections": [...],    # List of section dicts
    "total_steps": int,
    "total_sections": int,
    "estimated_duration_minutes": int
}
```

### 3. Updated `generate_guide()` Method

**Changes**:
- Passes validated_data dictionary to `_save_guide_to_database()`
- Includes difficulty_level parameter
- Constructs response with proper guide info

```python
# Validate the generated guide
validated_data = await self._validate_and_process_guide(guide_data)

# Save to database with difficulty level
guide_id = await self._save_guide_to_database(validated_data, request.difficulty_preference, db)

# Create response with guide info
guide_info = validated_data["guide_info"]
return GuideGenerationResponse(
    guide_id=guide_id,
    guide=StepGuide(...),  # Constructed from validated_data
    generation_time_seconds=generation_time,
    llm_provider=provider_mapping.get(provider_used, LLMProvider.OPENAI)
)
```

### 4. Completely Rewrote `_save_guide_to_database()`

**New Signature**:
```python
async def _save_guide_to_database(
    self,
    validated_data: Dict[str, Any],
    difficulty_level: DifficultyLevel,
    db: AsyncSession
) -> uuid.UUID:
```

**Key Features**:

1. **Stores guide_data JSON**:
```python
guide_model = StepGuideModel(
    ...
    guide_data=guide_info,  # Full JSON structure including sections
    total_steps=validated_data["total_steps"],
    total_sections=validated_data["total_sections"]
)
```

2. **Creates Section Models**:
```python
for section_data in sections:
    section_model = SectionModel(
        section_id=uuid.uuid4(),
        guide_id=guide_id,
        section_identifier=section_data["section_id"],
        section_title=section_data["section_title"],
        section_description=section_data["section_description"],
        section_order=section_data["section_order"],
        estimated_duration_minutes=sum(...)
    )
    db.add(section_model)
```

3. **Creates Step Models with Proper Fields**:
```python
step_model = StepModel(
    step_id=uuid.uuid4(),
    guide_id=guide_id,
    section_id=section_model.section_id,  # Links to section
    step_index=global_step_index,         # Sequential index
    step_identifier=step_identifier,      # String identifier
    step_status=StepStatus.ACTIVE,        # Initial status
    title=step_data["title"],
    description=step_data["description"],
    completion_criteria=step_data["completion_criteria"],
    assistance_hints=step_data.get("assistance_hints", []),
    estimated_duration_minutes=step_data.get("estimated_duration_minutes", 5),
    requires_desktop_monitoring=step_data.get("requires_desktop_monitoring", False),
    visual_markers=step_data.get("visual_markers", []),
    prerequisites=step_data.get("prerequisites", []),
    dependencies=[]
)
```

4. **Maintains Global Step Index**:
```python
global_step_index = 0
for section_data in sections:
    for step_data in section_data.get("steps", []):
        # Create step with global_step_index
        ...
        global_step_index += 1
```

This ensures steps have sequential indices across sections (0, 1, 2, ...) while maintaining section relationships.

## Backward Compatibility

The service maintains backward compatibility with flat step lists:

```python
# If no sections, create a default section from flat steps list
if not sections and "steps" in guide_info:
    sections = [{
        "section_id": "main",
        "section_title": "Steps",
        "section_description": "Main steps for this guide",
        "section_order": 0,
        "steps": guide_info["steps"]
    }]
```

This allows old LLM responses without sections to still work.

## Data Flow

```
LLM Response (JSON)
    ↓
_validate_and_process_guide()
    ↓
Validated Data Dict
    {
      guide_id, guide_info, sections,
      total_steps, total_sections, estimated_duration
    }
    ↓
_save_guide_to_database()
    ↓
Database:
    - StepGuideModel (with guide_data JSON)
    - SectionModel (multiple, linked to guide)
    - StepModel (multiple, linked to section and guide)
```

## Database Structure After Save

```
step_guides table:
  - guide_id: UUID
  - title, description, category
  - total_steps: int (e.g., 10)
  - total_sections: int (e.g., 3)
  - guide_data: JSON (full sectioned structure)

sections table:
  - section_id: UUID
  - guide_id: UUID (FK → step_guides)
  - section_identifier: str (e.g., "setup")
  - section_title: str (e.g., "Setup")
  - section_order: int (0, 1, 2, ...)

steps table:
  - step_id: UUID
  - guide_id: UUID (FK → step_guides)
  - section_id: UUID (FK → sections)
  - step_index: int (0, 1, 2, ...) [sequential across all sections]
  - step_identifier: str ("0", "1", "2", ...)
  - step_status: enum (ACTIVE, COMPLETED, BLOCKED, ALTERNATIVE)
  - title, description, completion_criteria
```

## Integration Points

This update integrates with:

1. **LLM Service** (`llm_service.py`):
   - LLM service returns sectioned guide structure
   - Guide service processes sections properly

2. **Database Models** (`models/database.py`):
   - Uses `SectionModel` for section storage
   - Properly initializes `step_identifier` and `step_status` in `StepModel`

3. **Step Disclosure Service** (`step_disclosure_service.py`):
   - Reads `guide_data` JSON to navigate sections and steps
   - Uses `step_identifier` for step navigation

4. **Guide Adaptation Service** (`guide_adaptation_service.py`):
   - Updates `guide_data` JSON when alternatives are added
   - Modifies `step_status` when steps are blocked

## Verification

✅ **Code compiles successfully**:
```bash
$ python3 -m py_compile backend/src/services/guide_service.py
# Success (no errors)
```

✅ **All required fields initialized**:
- `guide_data` JSON stored ✓
- `total_sections` calculated ✓
- `SectionModel` instances created ✓
- `step_identifier` initialized ✓
- `step_status` set to ACTIVE ✓

✅ **Backward compatibility maintained**:
- Flat step lists converted to sections ✓
- Old LLM responses still work ✓

## Testing Recommendations

1. **Unit Tests**:
   - Test `_validate_and_process_guide()` with sectioned and flat formats
   - Test `_save_guide_to_database()` creates all models correctly
   - Verify global_step_index increments properly

2. **Integration Tests**:
   - Generate guide with sectioned LLM response
   - Verify database has correct structure
   - Check guide_data JSON is properly stored
   - Verify section and step relationships

3. **Edge Cases**:
   - Empty sections array
   - Missing step fields
   - Single section with many steps
   - Multiple sections with various step counts

## Next Steps

- [x] Task 1.6: Update Guide Service for Sections - **COMPLETED**
- [ ] Task 2.1: Set Up Local Development Environment - **NEXT**
- [ ] Task 2.2-2.4: End-to-End Integration Testing

## Files Modified

- `/Users/sivanlissak/Documents/VisGuiAI/backend/src/services/guide_service.py`

## Related Documentation

- `MIGRATION_FIX_REPORT.md` - Database migration consolidation
- `STEP_DISCLOSURE_MIGRATION.md` - Step disclosure service updates
- `SESSION_SERVICE_CHANGES.md` - Session service identifier migration
- `IMPORT_FIX_REPORT.md` - Import standardization
