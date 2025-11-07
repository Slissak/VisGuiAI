# Unused Code Detection Report

**Generated:** 2025-11-07

**Analyst:** Claude Code
**Codebase:** VisGuiAI Backend (Python/FastAPI)
**Working Directory:** `/Users/sivanlissak/Documents/VisGuiAI/backend`

---

## Summary

- **Total files scanned:** 49 Python files (~10,996 lines of code)
- **Unused imports found:** 8 instances
- **Unused functions/classes:** 3 instances
- **Dead code blocks:** 0 (no significant commented-out blocks)
- **Unused dependencies:** 1 candidate
- **Code duplication issues:** 2 instances

---

## 1. Unused Imports

### File: /backend/src/services/llm_service.py
**Status:** CRITICAL - Import Order Issue

- **Line 5:** `from abc import ABC, abstractmethod`
  - **Issue:** ABC is imported but never used. The `LLMProvider` class (line 19) does not inherit from ABC.
  - **Impact:** Low (benign unused import)
  - **Recommendation:** Remove ABC from import or make LLMProvider inherit from ABC

- **Line 11:** `from shared.schemas.llm_request import LLMProvider`
  - **Issue:** CRITICAL - Name collision! This imports LLMProvider enum from shared schemas
  - **Conflict:** The file defines its own `class LLMProvider` on line 19
  - **Impact:** HIGH - This is shadowing the imported enum with a local class definition
  - **Recommendation:** Rename the local class to `BaseLLMProvider` or `AbstractLLMProvider` to avoid collision

- **Line 7:** `from uuid import uuid4`
  - **Usage:** Not directly used in the file
  - **Recommendation:** Remove if unused

- **Line 1059:** `import asyncio`
  - **Issue:** Import at end of file (should be at top)
  - **Usage:** Used in MockLLMProvider.generate_guide (line 63) and generate_step_alternatives (line 136)
  - **Recommendation:** Move to top of file with other imports

### File: /backend/src/services/guide_service.py

- **Line 12:** `from shared.schemas.step import Step, StepCreate`
  - **Issue:** `StepCreate` is imported but never used
  - **Recommendation:** Remove `StepCreate` from import

- **Line 13:** `from shared.schemas.llm_request import LLMGenerationRequest, LLMGenerationRequestCreate, LLMProvider`
  - **Issue:** `LLMGenerationRequest` and `LLMGenerationRequestCreate` appear to be unused
  - **Usage:** Only `LLMProvider` enum is used in the file
  - **Recommendation:** Remove unused imports

### File: /backend/src/api/admin.py

- **Line 5:** `from uuid import UUID`
  - **Issue:** Imported but UUID is not directly used in the file
  - **Note:** May be used in function signatures implicitly
  - **Recommendation:** Verify usage and remove if unused

- **Line 8:** `from pydantic import BaseModel, Field, EmailStr`
  - **Issue:** `EmailStr` is imported but never used
  - **Recommendation:** Remove `EmailStr` if not needed

---

## 2. Unused Functions and Classes

### File: /backend/src/services/session_service.py

**Function:** `_validate_step_identifier(self, identifier: str) -> bool`
- **Location:** Lines 501-520
- **Description:** Validates step identifier format (digits optionally followed by a letter)
- **Usage:** Not called anywhere in the file or codebase
- **Recommendation:** KEEP - This is a validation utility that should be used. Add it to step identifier validation logic or mark as private utility for future use.

### File: /backend/src/services/session_service.py

**Function:** `_build_session_detail_from_cache(self, cached_data: dict) -> SessionDetailResponse`
- **Location:** Lines 444-448
- **Description:** Build session detail response from cached data
- **Implementation:** Returns None (placeholder implementation)
- **Usage:** Called once on line 180 but always returns None
- **Recommendation:** Either implement properly or remove. Currently non-functional.

### File: /backend/src/services/guide_service.py

**Class:** `GuideValidationError`
- **Location:** Lines 25-33
- **Description:** Exception raised when guide validation fails
- **Usage:** Raised on line 239 but may not be caught specifically anywhere
- **Recommendation:** KEEP - Used for error handling, even if not caught explicitly

---

## 3. Dead Code Blocks

### Summary
No significant commented-out code blocks found (>5 lines). The codebase is clean in this regard.

### Debug/Print Statements Found

**File:** /backend/src/services/guide_service.py
- **Lines 264-265:** Debug print statements in production code
```python
print(f"difficulty_level in _save_guide_to_database: {difficulty_level}")
print(f"difficulty_level.value in _save_guide_to_database: {difficulty_level.value}")
```
- **Recommendation:** Remove or convert to logger.debug()

**File:** /backend/src/api/instruction_guides.py
- **Lines 317-318:** Debug print statements
```python
print(f"ERROR in generate_instruction_guide: {error_details}")
```
- **Recommendation:** Already using logger; remove print statement

- **Lines 499-500:** Debug print statements
```python
print(f"complete_current_step: session: {session}")
print(f"complete_current_step: current_user: {current_user}")
```
- **Recommendation:** Convert to logger.debug() or remove

---

## 4. Unused Dependencies

### From pyproject.toml

#### Potentially Unused:

**1. psycopg2-binary>=2.9.9**
- **Purpose:** PostgreSQL adapter (synchronous)
- **Issue:** The codebase uses asyncpg for async PostgreSQL connections
- **Evidence:** No imports of psycopg2 found in codebase
- **Recommendation:** REMOVE if not used by alembic migrations. Check migration scripts first.

#### Dependencies Used Correctly:

- **fastapi[all]** - Used extensively (all API endpoints)
- **uvicorn[standard]** - Server runtime
- **pydantic[email]** - Schema validation throughout
- **pydantic-settings** - Config management in core/config.py
- **sqlalchemy** - Database ORM (all models and queries)
- **alembic** - Database migrations
- **asyncpg** - PostgreSQL async driver (used in core/database.py)
- **redis[hiredis]** - Caching and session store (core/redis.py)
- **openai** - LLM integration (services/llm_service.py)
- **anthropic** - LLM integration (services/llm_service.py)
- **jinja2** - Template rendering (may be used by FastAPI)
- **httpx** - HTTP client (used by LLM services)
- **python-jose[cryptography]** - JWT tokens (auth/middleware.py)
- **passlib[bcrypt]** - Password hashing (api/auth.py)
- **python-multipart** - File upload support (FastAPI dependency)
- **PyJWT** - JWT tokens (auth/middleware.py)

---

## 5. Code Duplication Issues

### Issue 1: LLMProvider Name Collision

**Location:** /backend/src/services/llm_service.py

**Problem:**
```python
# Line 11: Import from shared schemas
from shared.schemas.llm_request import LLMProvider  # This is an ENUM

# Line 19: Local class definition
class LLMProvider:  # This is a BASE CLASS
    """Abstract base class for LLM providers."""
```

**Impact:** HIGH - The local class shadows the imported enum. This causes confusion and potential bugs when trying to use the LLMProvider enum.

**Evidence of Problem:**
- Lines 84-89 and 339-345: The code maps string names to enum values, but has to work around the naming collision
- The imported enum is needed for provider identification, but the local class name conflicts

**Recommendation:**
```python
# Option 1: Rename the local class
class BaseLLMProvider:
    """Abstract base class for LLM providers."""
    # ... rest of implementation

# Option 2: Alias the import
from shared.schemas.llm_request import LLMProvider as LLMProviderEnum
```

### Issue 2: Duplicate import of re module

**Location:** /backend/src/services/session_service.py

**Problem:**
- Line 3: No `import re` at module level
- Line 519: `import re` inside function `_validate_step_identifier()`

**Recommendation:** Move `import re` to top of file with other imports for consistency.

---

## 6. Recommendations by Priority

### HIGH PRIORITY (Fix Immediately)

1. **Fix LLMProvider name collision** in llm_service.py
   - Rename local class to `BaseLLMProvider` or `AbstractLLMProvider`
   - Update all references (MockLLMProvider, OpenAIProvider, etc.)

2. **Move asyncio import to top of file** in llm_service.py (line 1059)
   - Import order matters for linting and code organization

3. **Remove or fix non-functional `_build_session_detail_from_cache()`** in session_service.py
   - Either implement it or remove the call on line 180

### MEDIUM PRIORITY (Clean up soon)

4. **Remove unused imports:**
   - `ABC` from llm_service.py (line 5) or make LLMProvider inherit from it
   - `uuid4` from llm_service.py (line 7)
   - `StepCreate` from guide_service.py (line 12)
   - `LLMGenerationRequest`, `LLMGenerationRequestCreate` from guide_service.py (line 13)
   - `EmailStr` from admin.py (line 8)

5. **Remove debug print statements** and replace with logger:
   - guide_service.py lines 264-265
   - instruction_guides.py lines 317-318, 499-500

6. **Check and potentially remove psycopg2-binary dependency**
   - Verify it's not used by alembic migrations
   - If not needed, remove from pyproject.toml

### LOW PRIORITY (Consider for future)

7. **Move `import re` to top of session_service.py**
   - Currently imported inside function (line 519)

8. **Consider using `_validate_step_identifier()` in session_service.py**
   - Function is defined but never used
   - Could add validation to improve robustness

9. **Verify UUID import usage in admin.py**
   - May be used implicitly in type hints

---

## 7. Safe to Remove (Confirmed Unused)

Based on analysis, these can be safely removed:

### Imports:
```python
# From llm_service.py line 7
from uuid import uuid4  # Not used

# From guide_service.py line 12
from shared.schemas.step import StepCreate  # Not used

# From guide_service.py line 13
from shared.schemas.llm_request import LLMGenerationRequest, LLMGenerationRequestCreate  # Not used

# From admin.py line 8
from pydantic import EmailStr  # Not used (remove only EmailStr, keep BaseModel and Field)
```

### Code:
```python
# From guide_service.py lines 264-265
print(f"difficulty_level in _save_guide_to_database: {difficulty_level}")
print(f"difficulty_level.value in _save_guide_to_database: {difficulty_level.value}")

# From instruction_guides.py lines 499-500
print(f"complete_current_step: session: {session}")
print(f"complete_current_step: current_user: {current_user}")
```

---

## 8. Investigate Further

These items need human review before removal:

1. **`_validate_step_identifier()` function** in session_service.py
   - Defined but unused
   - Decision: Keep for future use or integrate into validation logic?

2. **`_build_session_detail_from_cache()` function** in session_service.py
   - Called but returns None
   - Decision: Implement fully or remove?

3. **`psycopg2-binary` dependency**
   - Not imported in src/ code
   - Check: Is it used by alembic for migrations?

4. **ABC import** in llm_service.py
   - Imported but not used
   - Decision: Should LLMProvider inherit from ABC for proper abstract class implementation?

---

## 9. Keep (False Positives)

These were flagged but should be kept:

1. **`GuideValidationError` class** - Used for error handling
2. **`abstractmethod` decorator** - Used for abstract methods in base classes
3. **`UUID` type import** - Likely used in type hints
4. **All FastAPI dependencies** - Required for framework functionality

---

## 10. Next Steps

### Immediate Actions (Before removing code):

1. Run full test suite to ensure no hidden dependencies
2. Check import usage with automated tools:
   ```bash
   # Install tools
   pip install autoflake vulture

   # Check for unused imports
   autoflake --check --remove-all-unused-imports backend/src/

   # Find dead code
   vulture backend/src/
   ```

3. Verify psycopg2-binary usage:
   ```bash
   grep -r "psycopg2" backend/
   grep -r "psycopg2" backend/alembic/
   ```

### Recommended Tool Installation:

```bash
# Add to pyproject.toml dev dependencies
[project.optional-dependencies]
dev = [
    # ... existing dev deps ...
    "autoflake>=2.0.0",   # Remove unused imports
    "vulture>=2.0",       # Find dead code
]
```

---

## Appendix: Analysis Methodology

This report was generated through:

1. **Manual code review** of all 49 Python files
2. **Import analysis** using grep patterns
3. **Function call tracing** to identify unused functions
4. **Dependency cross-reference** between pyproject.toml and actual imports
5. **Pattern matching** for common dead code indicators (commented blocks, debug prints)

### Tools Used:
- grep (pattern matching)
- Manual AST analysis
- Dependency graph tracing

### Limitations:
- Dynamic imports (importlib) not analyzed
- Reflection-based usage not detected
- Some type hint imports may be flagged as unused

---

**End of Report**
