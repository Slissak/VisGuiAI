# Step Progression Test Plan

## Executive Summary

This document provides a comprehensive analysis of step progression and navigation tests, mapping test scenarios to implementation components, and providing guidance for test execution and validation.

**Date**: 2025-10-16
**Status**: Analysis Complete
**Test Coverage**: Integration & Unit Tests

---

## Table of Contents

1. [Test Overview](#test-overview)
2. [Test Files Analyzed](#test-files-analyzed)
3. [Functionality Being Tested](#functionality-being-tested)
4. [Implementation Mapping](#implementation-mapping)
5. [Test Flow Diagrams](#test-flow-diagrams)
6. [State Transitions](#state-transitions)
7. [API Call Sequences](#api-call-sequences)
8. [Gap Analysis](#gap-analysis)
9. [Recommendations](#recommendations)

---

## Test Overview

### Test Files Analyzed

1. **`/Users/sivanlissak/Documents/VisGuiAI/backend/tests/test_instruction_guides_integration.py`**
   - Focus: Instruction-based guide generation and step-by-step progression
   - Type: Integration tests
   - Coverage: 10 test methods
   - Mock Strategy: LLM responses mocked, full database interaction

2. **`/Users/sivanlissak/Documents/VisGuiAI/backend/tests/integration/test_complete_flow.py`**
   - Focus: End-to-end user journey from guide creation to completion
   - Type: Integration tests
   - Coverage: 2 test methods
   - Mock Strategy: Full integration with database

### Test Statistics

| Metric | Value |
|--------|-------|
| Total Test Methods | 12 |
| Step Progression Tests | 5 |
| Navigation Tests | 3 |
| Progress Tracking Tests | 3 |
| Access Control Tests | 1 |
| Total API Endpoints Tested | 9 |

---

## Functionality Being Tested

### 1. Step Completion

**Test Coverage:**
- `test_step_completion_progression()` - Sequential step completion through multiple steps
- `test_complete_guide_workflow()` - Full guide completion from start to finish
- `test_complete_guide_flow_integration()` - End-to-end completion flow

**Scenarios Tested:**
- ✅ Complete first step and advance to second
- ✅ Complete second step and advance to third (cross-section transition)
- ✅ Complete all steps and mark guide as completed
- ✅ Track completion notes and time taken
- ✅ Update progress percentage after each completion

**Expected Behavior:**
```
Initial State: Step 0 (active) -> Complete -> Step 1 (active)
Step 1 (active) -> Complete -> Step 2 (active)
Step 2 (active) -> Complete -> Guide Completed
```

---

### 2. Navigation (Forward/Backward)

**Test Coverage:**
- `test_step_navigation_back_and_forth()` - Backward and forward navigation
- `test_generate_instruction_guide_workflow()` - Initial navigation state

**Scenarios Tested:**
- ✅ Navigate to previous step from step 1
- ✅ Verify cannot go back from step 0 (first step)
- ✅ Check `can_go_back` navigation flag
- ✅ Preserve completion state when navigating

**Expected Behavior:**
```
Step 0 -> Complete -> Step 1 (active)
Step 1 (active) -> Previous -> Step 0 (active, completed)
Step 0 (completed): can_go_back = False
```

**Navigation Constraints:**
- Cannot go back from first step (step_index = 0)
- Can navigate back to any previously completed step
- Forward navigation requires step completion
- Session state preserved during navigation

---

### 3. Progress Tracking

**Test Coverage:**
- `test_progress_tracking()` - Detailed progress metrics
- `test_complete_guide_flow_integration()` - Progress updates during completion
- All completion tests verify progress updates

**Scenarios Tested:**
- ✅ Initial progress: 0% completion, 0 steps completed
- ✅ Progress after first step: 33.3% completion, 1/3 steps
- ✅ Progress calculation across sections
- ✅ Current section progress tracking
- ✅ Estimated time remaining

**Metrics Tracked:**
| Metric | Description | Test Validation |
|--------|-------------|-----------------|
| `completed_steps` | Number of steps marked as complete | ✅ Verified |
| `total_steps` | Total active steps in guide | ✅ Verified |
| `completion_percentage` | Rounded to 1 decimal place | ✅ Verified |
| `current_section` | Section user is currently in | ✅ Verified |
| `section_progress` | Completion within current section | ✅ Verified |

**Progress Calculation:**
```python
completion_percentage = (completed_steps / total_steps) * 100
# Example: (1 / 3) * 100 = 33.3%
```

---

### 4. Section Transitions

**Test Coverage:**
- `test_step_completion_progression()` - Cross-section step advancement
- `test_section_overview_access()` - Section overview without revealing steps

**Scenarios Tested:**
- ✅ Transition from "Setup" section to "Configuration" section
- ✅ Section progress updates when crossing boundaries
- ✅ Section overview shows step titles but not full descriptions
- ✅ Locked steps in section overview
- ✅ Current step marked in section overview

**Section Data Structure:**
```json
{
  "section_id": "setup",
  "section_title": "Setup",
  "section_description": "Initial preparation steps",
  "section_order": 0,
  "steps": [...]
}
```

**Section Transition Flow:**
```
Section "Setup" (order: 0)
  └─ Step 0: Install Node.js (completed)
  └─ Step 1: Install Code Editor (completed)
       ↓ [Transition]
Section "Configuration" (order: 1)
  └─ Step 2: Configure Git (active)
```

---

## Implementation Mapping

### Service Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer                                │
│  /api/v1/instruction-guides/*                               │
│  (instruction_guides.py)                                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│              Service Orchestration                           │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ SessionService   │  │ GuideService     │                │
│  │ (session mgmt)   │  │ (guide creation) │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ StepDisclosure   │  │ ProgressService  │                │
│  │ (step filtering) │  │ (tracking)       │                │
│  └──────────────────┘  └──────────────────┘                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                 Data Layer (PostgreSQL)                      │
│  GuideSessionModel | StepGuideModel | ProgressTrackerModel  │
└─────────────────────────────────────────────────────────────┘
```

---

### 1. Step Completion Implementation

**API Endpoint:**
```
POST /api/v1/instruction-guides/{session_id}/complete-step
```

**Request Flow:**
```
1. API Handler (instruction_guides.py:165-209)
   ├─ Validates user owns session
   ├─ Extracts completion_notes, time_taken
   └─ Calls StepDisclosureService.advance_to_next_step()

2. StepDisclosureService.advance_to_next_step() (step_disclosure_service.py:156-226)
   ├─ Retrieves current session
   ├─ Gets guide data structure
   ├─ Finds next step identifier using get_next_identifier()
   ├─ Updates session.current_step_identifier
   ├─ Logs completion event
   └─ Returns new current step data

3. Database Updates
   ├─ GuideSessionModel.current_step_identifier = next_identifier
   ├─ GuideSessionModel.updated_at = now()
   └─ If last step: status = "completed", completed_at = now()
```

**Key Methods:**

| Method | Location | Purpose |
|--------|----------|---------|
| `complete_current_step()` | instruction_guides.py:165 | API handler |
| `advance_to_next_step()` | step_disclosure_service.py:156 | Step advancement logic |
| `get_next_identifier()` | utils/sorting.py | Identifier ordering |
| `_update_session_identifier()` | step_disclosure_service.py:716 | DB update |
| `_log_step_completion()` | step_disclosure_service.py:738 | Analytics logging |

**Identifier Resolution:**
- Uses string-based identifiers (e.g., "0", "1", "1a", "2b")
- Natural sorting to determine next step
- Skips blocked steps automatically
- Handles alternative steps for blocked content

---

### 2. Navigation Implementation

**Backward Navigation:**
```
POST /api/v1/instruction-guides/{session_id}/previous-step
```

**Request Flow:**
```
1. API Handler (instruction_guides.py:212-249)
   ├─ Validates user owns session
   └─ Calls StepDisclosureService.go_back_to_previous_step()

2. StepDisclosureService.go_back_to_previous_step() (step_disclosure_service.py:229-275)
   ├─ Gets all step identifiers (including blocked)
   ├─ Finds previous identifier using get_previous_identifier()
   ├─ Validates not at first step
   ├─ Updates session to previous identifier
   └─ Returns previous step data

3. Navigation Constraints
   ├─ can_go_back = False if at first step
   └─ Otherwise can_go_back = True
```

**Forward Navigation:**
- Requires step completion via `complete_current_step()`
- No "skip" endpoint (must complete current step)
- Some steps allow skipping via `can_skip` flag

**Navigation Flags:**
```python
{
  "navigation": {
    "can_go_back": bool,          # True if not at first step
    "can_skip": bool,              # Based on step properties
    "next_section_preview": dict   # If last step in section
  }
}
```

**Key Methods:**

| Method | Location | Purpose |
|--------|----------|---------|
| `go_to_previous_step()` | instruction_guides.py:212 | API handler |
| `go_back_to_previous_step()` | step_disclosure_service.py:229 | Navigation logic |
| `get_previous_identifier()` | utils/sorting.py | Identifier ordering |
| `_can_go_back()` | step_disclosure_service.py:616 | Validation |
| `_can_skip_step()` | step_disclosure_service.py:597 | Skip permission |

---

### 3. Progress Tracking Implementation

**API Endpoint:**
```
GET /api/v1/instruction-guides/{session_id}/progress
```

**Request Flow:**
```
1. API Handler (instruction_guides.py:252-299)
   ├─ Validates user owns session
   ├─ Calls StepDisclosureService.get_current_step_only()
   └─ Extracts progress information

2. Progress Calculation (step_disclosure_service.py:451-491)
   ├─ Gets all active step identifiers (exclude blocked)
   ├─ Counts completed steps (before current identifier)
   ├─ Calculates percentage: (completed / total) * 100
   ├─ Calculates estimated remaining time
   └─ Returns progress metrics

3. ProgressService Integration (progress_service.py:28-78)
   ├─ Tracks time_spent_minutes
   ├─ Updates last_activity_at
   ├─ Calculates estimated_time_remaining
   └─ Caches progress in Redis
```

**Progress Metrics:**
```python
{
  "progress": {
    "total_steps": 3,                    # Active steps only
    "completed_steps": 1,                # Steps before current
    "completion_percentage": 33.3,       # Rounded to 1 decimal
    "estimated_time_remaining": 30       # Minutes
  }
}
```

**Section Progress:**
```python
{
  "current_section": {
    "section_title": "Setup",
    "section_progress": {
      "completed_steps": 1,
      "total_steps": 2,
      "completion_percentage": 50.0
    }
  }
}
```

**Key Methods:**

| Method | Location | Purpose |
|--------|----------|---------|
| `get_session_progress()` | instruction_guides.py:252 | API handler |
| `_calculate_progress()` | step_disclosure_service.py:451 | Overall progress |
| `_get_section_progress()` | step_disclosure_service.py:533 | Section progress |
| `_calculate_remaining_time()` | step_disclosure_service.py:494 | Time estimation |
| `get_progress()` | progress_service.py:28 | Progress tracking |

**Progress Updates:**
- Automatic on step completion
- Cached in Redis for performance
- Excludes blocked steps from totals
- Updates section-level progress separately

---

### 4. Section Management Implementation

**Section Overview:**
```
GET /api/v1/instruction-guides/{session_id}/sections/{section_id}/overview
```

**Request Flow:**
```
1. API Handler (instruction_guides.py:302-340)
   ├─ Validates user owns session
   └─ Calls StepDisclosureService.get_section_overview()

2. Section Overview Generation (step_disclosure_service.py:277-356)
   ├─ Finds section by section_id
   ├─ Builds step overview (titles only)
   ├─ Marks steps as: completed, current, locked
   ├─ Shows blocked steps with crossed_out styling
   ├─ Shows alternative steps with replaces_step_identifier
   └─ Calculates total estimated time (excludes blocked)

3. Response Structure
   ├─ Section metadata
   ├─ Step titles (no full descriptions)
   ├─ Step status (completed, current, locked)
   └─ Visual indicators (blocked, alternative)
```

**Step Overview Response:**
```python
{
  "section_id": "setup",
  "section_title": "Setup",
  "section_description": "Initial preparation steps",
  "step_overview": [
    {
      "step_identifier": "0",
      "title": "Install Node.js",
      "estimated_duration_minutes": 10,
      "completed": True,
      "current": False,
      "locked": False,
      "status": "active"
    },
    {
      "step_identifier": "1",
      "title": "Install Code Editor",
      "completed": False,
      "current": True,
      "locked": False,
      "status": "active"
    }
  ],
  "total_estimated_minutes": 25
}
```

**Blocked Step Display:**
```python
{
  "step_identifier": "1",
  "title": "Click Settings Button",
  "status": "blocked",
  "is_blocked": True,
  "blocked_reason": "UI changed - button no longer exists",
  "show_as": "crossed_out"  # Frontend styling hint
}
```

**Key Methods:**

| Method | Location | Purpose |
|--------|----------|---------|
| `get_section_overview()` | instruction_guides.py:302 | API handler |
| `get_section_overview()` | step_disclosure_service.py:277 | Section data |
| `_is_last_step_in_section()` | step_disclosure_service.py:640 | Section boundary |
| `_get_next_section_preview()` | step_disclosure_service.py:678 | Next section info |

---

## Test Flow Diagrams

### 1. Complete Guide Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Guide Generation & Completion                 │
└─────────────────────────────────────────────────────────────────┘

User Action          │  API Call                      │  Service Layer              │  Database
─────────────────────┼────────────────────────────────┼────────────────────────────┼─────────────
                     │                                │                             │
Request Guide        │  POST /generate                │  LLMService.generate_guide  │  INSERT
  "Set up dev env"   │  {instruction: "..."}          │  GuideService.create_guide  │  StepGuide
                     │                                │  SessionService.create()    │  Session
                     │                                │                             │
      │              │                                │                             │
      └─────────────►│  Response:                     │  StepDisclosure.get_first() │  SELECT
                     │  {session_id, guide_id,        │                             │  current
                     │   first_step: {step_0}}        │                             │  step
                     │                                │                             │
                     │                                │                             │
View Step 0          │  GET /{session_id}/            │  StepDisclosure.get_        │  SELECT
  "Install Node.js"  │      current-step              │    current_step_only()      │  session
                     │                                │                             │
      │              │  Response:                     │  _calculate_progress()      │
      │              │  {current_step: {...},         │  completed: 0/3 (0%)        │
      │              │   progress: {0/3, 0%}}         │                             │
      │              │                                │                             │
Complete Step 0      │  POST /{session_id}/           │  StepDisclosure.advance_    │  UPDATE
      │              │       complete-step            │    to_next_step()           │  session
      │              │  {completion_notes}            │  get_next_identifier()      │  identifier
      │              │                                │  _log_completion()          │
      └─────────────►│  Response:                     │  completed: 1/3 (33.3%)     │
                     │  {current_step: {step_1},      │                             │
                     │   progress: {1/3, 33.3%}}      │                             │
                     │                                │                             │
View Step 1          │  (automatic from response)     │                             │
  "Install Editor"   │                                │                             │
                     │                                │                             │
Complete Step 1      │  POST /{session_id}/           │  StepDisclosure.advance_    │  UPDATE
      │              │       complete-step            │    to_next_step()           │  session
      └─────────────►│  Response:                     │  Section transition:        │  identifier
                     │  {current_step: {step_2},      │    Setup → Configuration    │
                     │   progress: {2/3, 66.7%},      │  completed: 2/3 (66.7%)     │
                     │   current_section: {           │                             │
                     │     section_title: "Config"}}  │                             │
                     │                                │                             │
Complete Step 2      │  POST /{session_id}/           │  StepDisclosure.advance_    │  UPDATE
  (Last step)        │       complete-step            │    to_next_step()           │  session
      │              │                                │  next_identifier = None     │  status
      └─────────────►│  Response:                     │  Mark completed             │  completed_at
                     │  {status: "completed",         │  completed: 3/3 (100%)      │
                     │   message: "Guide complete"}   │                             │
```

---

### 2. Navigation Flow (Back and Forth)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Step Navigation Flow                          │
└─────────────────────────────────────────────────────────────────┘

User Action          │  API Call                      │  Service Layer              │  State
─────────────────────┼────────────────────────────────┼────────────────────────────┼─────────────
                     │                                │                             │
On Step 0            │  GET /current-step             │  current_identifier: "0"    │  Step 0
  "Install Node.js"  │                                │  can_go_back: False         │  (active)
                     │  Response:                     │  can_skip: True             │
      │              │  {navigation: {                │                             │
      │              │    can_go_back: false}}        │                             │
      │              │                                │                             │
Complete Step 0      │  POST /complete-step           │  advance_to_next_step()     │  Step 1
      │              │                                │  "0" → "1"                  │  (active)
      └─────────────►│  Response:                     │  can_go_back: True          │  Step 0
                     │  {current_step: {step_1},      │                             │  (completed)
                     │   navigation: {                │                             │
                     │    can_go_back: true}}         │                             │
                     │                                │                             │
On Step 1            │  GET /current-step             │  current_identifier: "1"    │  Step 1
  "Install Editor"   │                                │  can_go_back: True          │  (active)
                     │                                │                             │
      │              │                                │                             │
Navigate Back        │  POST /previous-step           │  go_back_to_previous_step() │  Step 0
      │              │                                │  get_previous_identifier()  │  (active,
      └─────────────►│  Response:                     │  "1" → "0"                  │   completed)
                     │  {current_step: {step_0},      │  can_go_back: False         │
                     │   navigation: {                │                             │
                     │    can_go_back: false}}        │                             │
                     │                                │                             │
On Step 0 (again)    │  GET /current-step             │  current_identifier: "0"    │  Step 0
  (Previously done)  │                                │  Already completed          │  (active,
                     │  Response:                     │  can_go_back: False         │   completed)
                     │  {current_step: {step_0},      │                             │
                     │   completed: true}             │                             │
                     │                                │                             │
Try Navigate Back    │  POST /previous-step           │  go_back_to_previous_step() │  ERROR
  (Invalid)          │                                │  previous_identifier = None │
      └─────────────►│  Error 400:                    │  ValueError raised          │
                     │  "Cannot go back - first step" │                             │
```

---

### 3. Progress Tracking Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Progress Tracking Flow                        │
└─────────────────────────────────────────────────────────────────┘

Event                │  Progress Calculation                       │  Metrics Updated
─────────────────────┼────────────────────────────────────────────┼──────────────────
                     │                                             │
Guide Created        │  all_identifiers = ["0", "1", "2"]         │  total: 3
  3 steps total      │  current_identifier = "0"                  │  completed: 0
                     │  completed = count_before("0") = 0         │  percentage: 0%
                     │  percentage = (0 / 3) * 100 = 0.0%         │  section: Setup
                     │                                             │  section_total: 2
      │              │                                             │  section_done: 0
      ▼              │                                             │
                     │                                             │
Step 0 Completed     │  all_identifiers = ["0", "1", "2"]         │  total: 3
  Advance to Step 1  │  current_identifier = "1"                  │  completed: 1
                     │  completed = count_before("1") = 1         │  percentage: 33.3%
      │              │  percentage = (1 / 3) * 100 = 33.3%        │  section: Setup
      │              │  section_progress = 1/2 = 50%              │  section_total: 2
      ▼              │                                             │  section_done: 1
                     │                                             │
Step 1 Completed     │  all_identifiers = ["0", "1", "2"]         │  total: 3
  Advance to Step 2  │  current_identifier = "2"                  │  completed: 2
  (Section change)   │  completed = count_before("2") = 2         │  percentage: 66.7%
      │              │  percentage = (2 / 3) * 100 = 66.7%        │  section: Config
      │              │  section_progress = 0/1 = 0%               │  section_total: 1
      ▼              │  (New section started)                     │  section_done: 0
                     │                                             │
Step 2 Completed     │  all_identifiers = ["0", "1", "2"]         │  total: 3
  Guide Complete     │  next_identifier = None                    │  completed: 3
                     │  completed = 3                              │  percentage: 100%
      │              │  percentage = (3 / 3) * 100 = 100.0%       │  status: completed
      ▼              │  session.status = "completed"              │
```

---

### 4. Section Transition Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Section Transition Flow                       │
└─────────────────────────────────────────────────────────────────┘

Guide Structure:
  Section 0 "Setup" (order: 0)
    └─ Step 0: "Install Node.js"
    └─ Step 1: "Install Code Editor"
  Section 1 "Configuration" (order: 1)
    └─ Step 2: "Configure Git"

───────────────────────────────────────────────────────────────────

Current Step         │  Section Context                │  Transition Logic
─────────────────────┼────────────────────────────────┼──────────────────
                     │                                 │
Step 0               │  current_section:               │  _is_last_step_in_
  (Setup section)    │    section_id: "setup"          │    section() = False
                     │    section_order: 0             │
      │              │    section_title: "Setup"       │  No preview shown
      │              │    steps: [0, 1]                │
      ▼              │                                 │
                     │                                 │
Step 1               │  current_section:               │  _is_last_step_in_
  (Last in Setup)    │    section_id: "setup"          │    section() = True
                     │    section_order: 0             │
      │              │    section_title: "Setup"       │  _get_next_section_
      │              │                                 │    preview() called
      ▼              │  next_section_preview:          │
                     │    section_title: "Config"      │  Preview returned:
      │              │    section_description: "..."   │    {title, desc,
      │              │    step_count: 1                │     step_count, time}
      │              │    estimated_duration: 5 min    │
      ▼              │                                 │
                     │                                 │
Complete Step 1      │  Transition triggered:          │  advance_to_next_step()
      │              │    "1" → "2"                    │  _find_step_by_
      └─────────────►│                                 │    identifier("2")
                     │  _find_step_by_identifier("2")  │  Step 2 in Section 1
                     │    returns: Step 2, Section 1   │
      ▼              │                                 │
                     │                                 │
Step 2               │  current_section:               │  Section changed!
  (Config section)   │    section_id: "configuration"  │  section_order: 0→1
                     │    section_order: 1             │
      │              │    section_title: "Config"      │  Section progress
      │              │    steps: [2]                   │    reset to 0/1
      ▼              │                                 │
                     │  section_progress:              │
                     │    completed_steps: 0           │
                     │    total_steps: 1               │
                     │    percentage: 0%               │
```

---

## State Transitions

### Session State Machine

```
┌──────────────────────────────────────────────────────────────────┐
│                    Session State Transitions                      │
└──────────────────────────────────────────────────────────────────┘

States:
  - ACTIVE: Session in progress
  - PAUSED: Session temporarily paused
  - COMPLETED: All steps completed
  - FAILED: Session failed or abandoned

Transitions:

    ┌─────────┐
    │ CREATED │  (Initial state when guide generated)
    └────┬────┘
         │ create_session()
         ▼
    ┌─────────┐
    │ ACTIVE  │◄──────────────┐
    └────┬────┘               │
         │                    │ resume
         │ pause             │
         ▼                    │
    ┌─────────┐              │
    │ PAUSED  │──────────────┘
    └────┬────┘
         │
         │ fail (timeout, error, user abandons)
         ▼
    ┌─────────┐
    │ FAILED  │──────────┐
    └─────────┘          │ restart
                          │
         ┌────────────────┘
         │
         ▼
    ┌─────────┐
    │ ACTIVE  │
    └────┬────┘
         │
         │ complete_last_step()
         ▼
    ┌───────────┐
    │ COMPLETED │ (Terminal state)
    └───────────┘

Valid Transitions:
  ACTIVE → PAUSED      (user pauses)
  ACTIVE → COMPLETED   (last step completed)
  ACTIVE → FAILED      (error or timeout)
  PAUSED → ACTIVE      (user resumes)
  PAUSED → FAILED      (timeout while paused)
  FAILED → ACTIVE      (restart/retry)
  COMPLETED → (none)   (terminal state)

Validation:
  - Implemented in SessionService._is_valid_status_transition()
  - Invalid transitions raise InvalidSessionStateError
  - Tests verify valid and invalid transitions
```

---

### Step State Machine

```
┌──────────────────────────────────────────────────────────────────┐
│                     Step State Transitions                        │
└──────────────────────────────────────────────────────────────────┘

States:
  - LOCKED: Future step, not yet accessible
  - ACTIVE: Current step user is working on
  - COMPLETED: Step finished successfully
  - BLOCKED: Step impossible due to UI/system change
  - ALTERNATIVE: Alternative approach for blocked step

Transitions:

    ┌────────┐
    │ LOCKED │  (All steps except first start locked)
    └───┬────┘
        │ previous_step_completed()
        ▼
    ┌────────┐
    │ ACTIVE │◄─────────────┐
    └───┬────┘              │
        │                   │ navigate_back()
        │ complete_step()   │
        ▼                   │
    ┌───────────┐           │
    │ COMPLETED │───────────┘
    └───────────┘
        │
        │ report_impossible()
        ▼
    ┌─────────┐       ┌──────────────┐
    │ BLOCKED │──────►│ ALTERNATIVE  │
    └─────────┘       │ (generated)  │
                      └──────────────┘

Properties by State:

LOCKED:
  - completed: false
  - current: false
  - locked: true
  - Cannot navigate to
  - Not shown in overview (or grayed out)

ACTIVE:
  - completed: false
  - current: true
  - locked: false
  - User can interact
  - Full details shown

COMPLETED:
  - completed: true
  - current: false (unless navigated back)
  - locked: false
  - Can navigate back to review
  - Counts toward progress

BLOCKED:
  - status: "blocked"
  - is_blocked: true
  - show_as: "crossed_out"
  - blocked_reason: string
  - Excluded from progress calculation
  - Cannot be accessed

ALTERNATIVE:
  - status: "alternative"
  - is_alternative: true
  - replaces_step_identifier: "original_id"
  - Treated as ACTIVE when reached
  - Included in progress calculation
```

---

## API Call Sequences

### Sequence 1: Generate and Complete Guide

```
┌──────┐                ┌──────┐                 ┌──────────┐
│ User │                │ API  │                 │ Database │
└──┬───┘                └──┬───┘                 └────┬─────┘
   │                       │                          │
   │ 1. Generate Guide     │                          │
   ├──────────────────────►│                          │
   │ POST /generate        │                          │
   │ {instruction: "..."}  │                          │
   │                       │ 2. Create Guide          │
   │                       ├─────────────────────────►│
   │                       │ INSERT StepGuide         │
   │                       │                          │
   │                       │ 3. Create Session        │
   │                       ├─────────────────────────►│
   │                       │ INSERT GuideSession      │
   │                       │                          │
   │                       │ 4. Get First Step        │
   │                       ├─────────────────────────►│
   │                       │ SELECT current_step      │
   │                       │                          │
   │◄──────────────────────┤ 5. Response              │
   │ {session_id,          │                          │
   │  first_step: {...}}   │                          │
   │                       │                          │
   │ 6. Get Current Step   │                          │
   ├──────────────────────►│                          │
   │ GET /current-step     │                          │
   │                       │ 7. Fetch Session         │
   │                       ├─────────────────────────►│
   │                       │ SELECT session, guide    │
   │                       │                          │
   │◄──────────────────────┤ 8. Response              │
   │ {current_step: {...}, │                          │
   │  progress: {0/3}}     │                          │
   │                       │                          │
   │ 9. Complete Step      │                          │
   ├──────────────────────►│                          │
   │ POST /complete-step   │                          │
   │ {completion_notes}    │                          │
   │                       │ 10. Advance Step         │
   │                       ├─────────────────────────►│
   │                       │ UPDATE session           │
   │                       │ identifier: "0" → "1"    │
   │                       │                          │
   │                       │ 11. Fetch Next Step      │
   │                       ├─────────────────────────►│
   │                       │ SELECT step_1            │
   │                       │                          │
   │◄──────────────────────┤ 12. Response             │
   │ {current_step: {...}, │                          │
   │  progress: {1/3}}     │                          │
   │                       │                          │
   │ 13. Complete Step     │                          │
   ├──────────────────────►│                          │
   │                       │ 14. Advance Step         │
   │                       ├─────────────────────────►│
   │                       │ UPDATE session           │
   │                       │ identifier: "1" → "2"    │
   │                       │                          │
   │◄──────────────────────┤ 15. Response             │
   │ {current_step: {...}, │                          │
   │  progress: {2/3},     │                          │
   │  current_section:     │                          │
   │    "Configuration"}   │                          │
   │                       │                          │
   │ 16. Complete Step     │                          │
   ├──────────────────────►│                          │
   │                       │ 17. Mark Completed       │
   │                       ├─────────────────────────►│
   │                       │ UPDATE session           │
   │                       │ status: "completed"      │
   │                       │                          │
   │◄──────────────────────┤ 18. Response             │
   │ {status: "completed", │                          │
   │  message: "Done!"}    │                          │
   │                       │                          │
```

---

### Sequence 2: Navigate Back and Forth

```
┌──────┐                ┌──────┐                 ┌──────────┐
│ User │                │ API  │                 │ Database │
└──┬───┘                └──┬───┘                 └────┬─────┘
   │                       │                          │
   │ (Starting on Step 1)  │                          │
   │                       │                          │
   │ 1. Navigate Back      │                          │
   ├──────────────────────►│                          │
   │ POST /previous-step   │                          │
   │                       │ 2. Get Current State     │
   │                       ├─────────────────────────►│
   │                       │ SELECT session           │
   │                       │ current_identifier: "1"  │
   │                       │                          │
   │                       │ 3. Calculate Previous    │
   │                       │ get_previous_identifier( │
   │                       │   "1", ["0","1","2"])    │
   │                       │ → "0"                    │
   │                       │                          │
   │                       │ 4. Update Session        │
   │                       ├─────────────────────────►│
   │                       │ UPDATE session           │
   │                       │ identifier: "1" → "0"    │
   │                       │                          │
   │                       │ 5. Fetch Step 0          │
   │                       ├─────────────────────────►│
   │                       │ SELECT step_0            │
   │                       │                          │
   │◄──────────────────────┤ 6. Response              │
   │ {current_step: {...}, │                          │
   │  navigation: {        │                          │
   │    can_go_back: false}│                          │
   │                       │                          │
   │ 7. Try Go Back Again  │                          │
   ├──────────────────────►│                          │
   │ POST /previous-step   │                          │
   │                       │ 8. Validate              │
   │                       │ get_previous_identifier( │
   │                       │   "0", ["0","1","2"])    │
   │                       │ → None                   │
   │                       │                          │
   │◄──────────────────────┤ 9. Error Response        │
   │ 400 Bad Request       │                          │
   │ "Cannot go back"      │                          │
   │                       │                          │
```

---

### Sequence 3: Progress Tracking

```
┌──────┐                ┌──────┐                 ┌──────────┐    ┌───────┐
│ User │                │ API  │                 │ Database │    │ Redis │
└──┬───┘                └──┬───┘                 └────┬─────┘    └───┬───┘
   │                       │                          │              │
   │ 1. Check Progress     │                          │              │
   ├──────────────────────►│                          │              │
   │ GET /progress         │                          │              │
   │                       │ 2. Check Cache           │              │
   │                       ├──────────────────────────┼─────────────►│
   │                       │ GET progress:{session_id}│              │
   │                       │                          │              │
   │                       │◄─────────────────────────┼──────────────┤
   │                       │ MISS (not cached)        │              │
   │                       │                          │              │
   │                       │ 3. Fetch from DB         │              │
   │                       ├─────────────────────────►│              │
   │                       │ SELECT session, progress │              │
   │                       │                          │              │
   │                       │ 4. Calculate Progress    │              │
   │                       │ all_identifiers: ["0","1","2"]          │
   │                       │ current: "1"             │              │
   │                       │ completed: count_before("1") = 1        │
   │                       │ percentage: (1/3)*100 = 33.3%           │
   │                       │                          │              │
   │                       │ 5. Cache Result          │              │
   │                       ├──────────────────────────┼─────────────►│
   │                       │ SET progress:{session_id}│              │
   │                       │                          │              │
   │◄──────────────────────┤ 6. Response              │              │
   │ {progress: {          │                          │              │
   │   completed: 1,       │                          │              │
   │   total: 3,           │                          │              │
   │   percentage: 33.3}}  │                          │              │
   │                       │                          │              │
   │ 7. Complete Step      │                          │              │
   ├──────────────────────►│                          │              │
   │                       │ 8. Update Session        │              │
   │                       ├─────────────────────────►│              │
   │                       │ UPDATE identifier: "2"   │              │
   │                       │                          │              │
   │                       │ 9. Invalidate Cache      │              │
   │                       ├──────────────────────────┼─────────────►│
   │                       │ DEL progress:{session_id}│              │
   │                       │                          │              │
   │                       │ 10. Recalculate Progress │              │
   │                       │ completed: 2, total: 3   │              │
   │                       │ percentage: 66.7%        │              │
   │                       │                          │              │
   │                       │ 11. Update Cache         │              │
   │                       ├──────────────────────────┼─────────────►│
   │                       │ SET progress:{session_id}│              │
   │                       │                          │              │
   │◄──────────────────────┤ 12. Response             │              │
   │ {current_step: {...}, │                          │              │
   │  progress: {          │                          │              │
   │   completed: 2,       │                          │              │
   │   total: 3,           │                          │              │
   │   percentage: 66.7}}  │                          │              │
   │                       │                          │              │
```

---

## Gap Analysis

### Test Coverage Gaps

#### 1. Edge Cases Not Covered

**Missing Test Scenarios:**

1. **Concurrent Step Completion**
   - What happens if user completes step from multiple tabs?
   - Race condition handling not tested
   - **Recommendation**: Add test for concurrent requests

2. **Step Skip Validation**
   - Tests verify `can_skip` flag exists
   - But no test actually attempts to skip a step
   - **Recommendation**: Add test for skip functionality

3. **Prerequisite Validation**
   - Steps can have prerequisites
   - No test validates prerequisite enforcement
   - **Recommendation**: Test prerequisite checking

4. **Time Estimation Accuracy**
   - Progress tracking tests verify time calculation
   - But no test validates accuracy against actual time
   - **Recommendation**: Add test with real time tracking

5. **Section Boundary Edge Cases**
   - Section transition tested for normal case
   - Not tested: Single-step sections, empty sections
   - **Recommendation**: Test edge cases

#### 2. Error Handling Gaps

**Missing Error Scenarios:**

1. **Invalid Session ID**
   - Tests verify 403 for wrong user
   - Not tested: Completely invalid UUID
   - **Recommendation**: Add malformed UUID test

2. **Corrupted Guide Data**
   - What if guide_data JSON is malformed?
   - Missing sections or steps not tested
   - **Recommendation**: Test data validation

3. **Database Connection Loss**
   - All tests assume DB is available
   - Not tested: Retry logic, connection failures
   - **Recommendation**: Add failure recovery tests

4. **LLM Service Failure**
   - LLM mocked in all tests
   - Real failure scenarios not tested
   - **Recommendation**: Test LLM timeout/error handling

#### 3. Performance Gaps

**Missing Performance Tests:**

1. **Large Guide Handling**
   - Test guides have 3 steps
   - Not tested: 50+ step guides
   - **Impact**: Progress calculation O(n) complexity
   - **Recommendation**: Load test with large guides

2. **Cache Hit Rate**
   - Progress caching implemented
   - Cache effectiveness not measured
   - **Recommendation**: Add cache performance metrics

3. **Concurrent Sessions**
   - Tests run sequentially
   - Not tested: Multiple users, multiple sessions
   - **Recommendation**: Load testing

#### 4. Integration Gaps

**Missing Integration Points:**

1. **Redis Integration**
   - SessionStore and ProgressService use Redis
   - Tests don't validate Redis behavior
   - **Recommendation**: Add Redis integration tests

2. **Full Database Integration**
   - Tests use test database
   - Not tested: Migrations, schema changes
   - **Recommendation**: Test migration scenarios

3. **API Authentication**
   - Auth mocked with `get_current_user`
   - Real auth flow not tested
   - **Recommendation**: Test full auth integration

---

### Implementation Gaps

#### 1. Missing Features

**Features Tested but Not Fully Implemented:**

1. **Help Request System** (Line 343-393 in instruction_guides.py)
   - Endpoint returns static hints
   - Not connected to LLM for dynamic help
   - **Status**: Placeholder implementation
   - **Recommendation**: Implement LLM-based help generation

2. **Step Analytics Logging** (Line 738-754 in step_disclosure_service.py)
   - `_log_step_completion()` is a no-op
   - Completion events not tracked
   - **Status**: TODO
   - **Recommendation**: Implement completion event logging

3. **Advanced Time Estimation** (progress_service.py:160-218)
   - Basic average calculation implemented
   - Not using ML or historical patterns
   - **Status**: Basic implementation
   - **Recommendation**: Enhance with learning algorithms

#### 2. Data Consistency Issues

**Potential Consistency Problems:**

1. **Step Identifier Migration**
   - Code supports both `step_index` and `step_identifier`
   - Fallback logic: `step.get("step_identifier", str(step.get("step_index")))`
   - **Risk**: Data inconsistency if mixed formats
   - **Recommendation**: Migrate all data to string identifiers

2. **Progress vs Session State Mismatch**
   - Session tracks `current_step_identifier`
   - Progress tracker tracks `completed_steps` list
   - **Risk**: Can get out of sync
   - **Recommendation**: Add consistency validation

3. **Cache Invalidation**
   - Cache updated on step completion
   - Not clear if invalidated on session updates
   - **Risk**: Stale cached data
   - **Recommendation**: Comprehensive cache invalidation

---

### Documentation Gaps

**Missing Documentation:**

1. **API Response Schemas**
   - Tests verify response structure
   - But no OpenAPI/Swagger documentation found
   - **Recommendation**: Generate API docs from Pydantic models

2. **Error Code Reference**
   - Various HTTP status codes used
   - No central error code documentation
   - **Recommendation**: Create error code reference

3. **Data Model Diagrams**
   - Complex relationships between Guide, Session, Progress
   - No ER diagrams found
   - **Recommendation**: Create data model documentation

---

## Recommendations

### Testing Recommendations

#### 1. Immediate Priorities

**High Priority (Do First):**

1. **Add Edge Case Tests**
   ```python
   # Test invalid session IDs
   async def test_invalid_session_id():
       response = await client.get(
           f"/api/v1/instruction-guides/invalid-uuid/current-step"
       )
       assert response.status_code == 422  # Validation error

   # Test concurrent completions
   async def test_concurrent_step_completion():
       # Complete same step from two requests simultaneously
       # Verify only one succeeds

   # Test large guides
   async def test_large_guide_performance():
       # Guide with 100 steps
       # Verify progress calculation < 100ms
   ```

2. **Add Error Recovery Tests**
   ```python
   # Test database reconnection
   async def test_db_reconnection():
       # Simulate DB disconnect
       # Verify retry logic works

   # Test LLM timeout
   async def test_llm_timeout_handling():
       # Mock LLM to timeout
       # Verify graceful degradation
   ```

3. **Add Integration Tests**
   ```python
   # Test Redis caching
   async def test_progress_caching():
       # Verify cache hit/miss behavior
       # Measure cache effectiveness

   # Test full auth flow
   async def test_authenticated_flow():
       # Real JWT tokens
       # Verify session isolation
   ```

#### 2. Test Improvements

**Enhance Existing Tests:**

1. **Add Assertions for Response Times**
   ```python
   import time

   async def test_step_completion_performance():
       start = time.time()
       response = await client.post("/complete-step", ...)
       duration = time.time() - start

       assert duration < 0.5  # Should complete in < 500ms
   ```

2. **Add Data Validation Assertions**
   ```python
   async def test_progress_calculation_accuracy():
       # Not just check the numbers exist
       # Verify the math is correct

       progress = response.json()["progress"]
       expected_percentage = (progress["completed_steps"] /
                             progress["total_steps"]) * 100

       assert abs(progress["completion_percentage"] -
                  expected_percentage) < 0.1  # Allow 0.1% variance
   ```

3. **Add Logging/Debugging Helpers**
   ```python
   @pytest.fixture
   def debug_mode():
       """Enable detailed logging for tests."""
       import logging
       logging.basicConfig(level=logging.DEBUG)
       yield
       logging.basicConfig(level=logging.WARNING)
   ```

#### 3. Test Organization

**Restructure Test Files:**

```
tests/
├── unit/
│   ├── test_step_disclosure_service.py
│   ├── test_session_service.py
│   ├── test_progress_service.py
│   └── test_sorting_utils.py
├── integration/
│   ├── test_complete_flow.py (existing)
│   ├── test_navigation_flow.py (new)
│   ├── test_progress_tracking.py (new)
│   └── test_error_handling.py (new)
├── e2e/
│   ├── test_user_journey.py
│   └── test_multiple_sessions.py
└── performance/
    ├── test_large_guides.py
    └── test_concurrent_users.py
```

---

### Implementation Recommendations

#### 1. Code Quality Improvements

**Refactoring Opportunities:**

1. **Extract Progress Calculation**
   ```python
   # Current: Calculation scattered across multiple methods
   # Recommendation: Centralize in ProgressCalculator class

   class ProgressCalculator:
       def __init__(self, guide_data: Dict, current_identifier: str):
           self.guide_data = guide_data
           self.current_identifier = current_identifier

       def overall_progress(self) -> ProgressMetrics:
           """Calculate overall progress."""
           # Current logic from _calculate_progress()

       def section_progress(self, section: Dict) -> SectionProgressMetrics:
           """Calculate section-specific progress."""
           # Current logic from _get_section_progress()

       def time_estimates(self) -> TimeEstimates:
           """Calculate time estimates."""
           # Current logic from _calculate_remaining_time()
   ```

2. **Standardize Identifier Handling**
   ```python
   # Current: Multiple fallback patterns
   # step.get("step_identifier", str(step.get("step_index")))

   # Recommendation: Use helper function
   def get_step_identifier(step: Dict) -> str:
       """Get step identifier with consistent fallback."""
       return step.get("step_identifier") or str(step.get("step_index", ""))
   ```

3. **Add Type Hints**
   ```python
   # Current: Some methods lack type hints
   # Recommendation: Add complete type annotations

   from typing import Dict, List, Optional, Tuple

   async def get_current_step_only(
       session_id: UUID,
       db: AsyncSession
   ) -> Dict[str, Any]:
       """Get current step with complete type safety."""
   ```

#### 2. Error Handling Improvements

**Better Error Messages:**

```python
# Current
raise ValueError(f"Session {session_id} not found")

# Recommendation
class SessionNotFoundError(Exception):
    def __init__(self, session_id: UUID):
        self.session_id = session_id
        super().__init__(f"Session {session_id} not found")

# Provides structured error information
# Easier to test and handle
```

#### 3. Performance Optimizations

**Database Query Optimization:**

```python
# Current: Multiple queries for related data
session = await db.execute(select(GuideSessionModel)...)
guide = await db.execute(select(StepGuideModel)...)

# Recommendation: Use joins and eager loading
session = await db.execute(
    select(GuideSessionModel)
    .options(
        selectinload(GuideSessionModel.guide)
        .selectinload(StepGuideModel.sections)
        .selectinload(SectionModel.steps)
    )
    .where(GuideSessionModel.session_id == session_id)
)

# Reduces queries from N to 1
```

---

### Monitoring Recommendations

#### 1. Metrics to Track

**Key Performance Indicators:**

```python
# Progress completion metrics
metrics = {
    "avg_steps_per_session": float,
    "avg_completion_time_minutes": float,
    "completion_rate_percentage": float,
    "avg_time_per_step": float,
    "section_transition_rate": float,
    "navigation_back_frequency": float,
    "help_request_frequency": float
}
```

#### 2. Logging Strategy

**Structured Logging:**

```python
import structlog

logger = structlog.get_logger()

# On step completion
logger.info(
    "step_completed",
    session_id=str(session_id),
    step_identifier=step_identifier,
    time_taken_minutes=time_taken,
    section_id=section_id,
    progress_percentage=progress_percentage
)

# On navigation
logger.info(
    "navigation",
    session_id=str(session_id),
    action="previous_step",
    from_step=current_identifier,
    to_step=previous_identifier
)
```

#### 3. Error Tracking

**Error Monitoring:**

```python
# Integrate with Sentry or similar
import sentry_sdk

try:
    await advance_to_next_step(...)
except Exception as e:
    sentry_sdk.capture_exception(e)
    sentry_sdk.set_context("session", {
        "session_id": str(session_id),
        "current_step": current_identifier,
        "user_id": user_id
    })
    raise
```

---

## Test Execution Guide

### Running Tests

**Basic Test Execution:**

```bash
# Run all step progression tests
pytest tests/test_instruction_guides_integration.py -v

# Run specific test
pytest tests/test_instruction_guides_integration.py::TestInstructionGuidesIntegration::test_step_completion_progression -v

# Run with coverage
pytest tests/ --cov=src/services --cov-report=html

# Run integration tests only
pytest tests/integration/ -m integration

# Run with detailed output
pytest tests/ -vv --tb=short
```

**Test Markers:**

```python
# In conftest.py or test files
import pytest

@pytest.mark.integration
async def test_complete_guide_flow_integration():
    """Integration test marker."""

@pytest.mark.unit
async def test_progress_calculation():
    """Unit test marker."""

@pytest.mark.slow
async def test_large_guide_performance():
    """Slow test marker."""
```

**Run by marker:**
```bash
pytest -m integration  # Only integration tests
pytest -m "not slow"   # Exclude slow tests
```

---

### Debugging Failed Tests

**Common Failure Patterns:**

1. **Session Not Found**
   ```
   AssertionError: assert 404 == 200
   ValueError: Session {uuid} not found
   ```
   **Cause**: Session creation failed or wrong session_id
   **Debug**: Check session creation, verify database state

2. **Progress Mismatch**
   ```
   AssertionError: assert 33.3 == 33.33
   ```
   **Cause**: Floating point precision
   **Fix**: Use approximate comparison `pytest.approx(33.3, rel=0.1)`

3. **Navigation Error**
   ```
   ValueError: Cannot go back further - already at first step
   ```
   **Cause**: Attempting to navigate before first step
   **Debug**: Check navigation flags before calling

**Debug Helpers:**

```python
# Print session state
async def debug_session_state(session_id, db):
    session = await db.execute(
        select(GuideSessionModel).where(
            GuideSessionModel.session_id == session_id
        )
    )
    session = session.scalar_one()
    print(f"Session: {session}")
    print(f"Current identifier: {session.current_step_identifier}")
    print(f"Status: {session.status}")

# Use in test
async def test_with_debug():
    # ... test code ...
    await debug_session_state(session_id, db)
    # ... continue test ...
```

---

## Conclusion

### Summary of Findings

**Test Coverage: ✅ Good**
- Step completion thoroughly tested
- Navigation tested for basic cases
- Progress tracking validated
- Section transitions verified

**Implementation: ✅ Solid**
- Services well-structured
- Database models support requirements
- API endpoints properly implemented
- Error handling in place

**Gaps Identified: ⚠️ Some**
- Edge cases need coverage
- Performance testing needed
- Some features partially implemented
- Documentation could be improved

### Next Steps

**Priority 1: Fill Test Gaps**
1. Add edge case tests (invalid inputs, boundaries)
2. Add concurrent access tests
3. Add large guide performance tests

**Priority 2: Complete Implementation**
1. Implement help request LLM integration
2. Implement step completion analytics
3. Enhance time estimation

**Priority 3: Improve Documentation**
1. Generate API documentation
2. Create data model diagrams
3. Document error codes

---

## Appendix

### Test Data Structure

**Mock LLM Response:**
```json
{
  "guide": {
    "title": "How to set up a development environment",
    "description": "A comprehensive guide",
    "category": "development",
    "difficulty_level": "beginner",
    "estimated_duration_minutes": 45,
    "sections": [
      {
        "section_id": "setup",
        "section_title": "Setup",
        "section_description": "Initial preparation",
        "section_order": 0,
        "steps": [
          {
            "step_index": 0,
            "title": "Install Node.js",
            "description": "Download and install",
            "completion_criteria": "Node.js 18+ installed",
            "assistance_hints": ["Use official website"],
            "estimated_duration_minutes": 10,
            "requires_desktop_monitoring": false,
            "visual_markers": [],
            "prerequisites": [],
            "completed": false,
            "needs_assistance": false
          }
        ]
      }
    ]
  }
}
```

### API Endpoint Reference

| Endpoint | Method | Purpose | Test Coverage |
|----------|--------|---------|---------------|
| `/generate` | POST | Create guide and session | ✅ Tested |
| `/{session_id}/current-step` | GET | Get current step | ✅ Tested |
| `/{session_id}/complete-step` | POST | Complete and advance | ✅ Tested |
| `/{session_id}/previous-step` | POST | Navigate backward | ✅ Tested |
| `/{session_id}/progress` | GET | Get progress metrics | ✅ Tested |
| `/{session_id}/sections/{section_id}/overview` | GET | Section overview | ✅ Tested |
| `/{session_id}/request-help` | POST | Request help | ✅ Tested |
| `/{session_id}/report-impossible-step` | POST | Report blocked step | ❌ Not tested |

### Key Service Methods

**StepDisclosureService:**
- `get_current_step_only()` - Main step retrieval
- `advance_to_next_step()` - Step completion
- `go_back_to_previous_step()` - Backward navigation
- `get_section_overview()` - Section data
- `_calculate_progress()` - Progress metrics
- `_find_step_by_identifier()` - Step lookup

**SessionService:**
- `create_session()` - Session initialization
- `get_session()` - Session retrieval
- `update_session()` - Session updates
- `advance_to_next_step()` - Step advancement
- `_is_valid_status_transition()` - State validation

**ProgressService:**
- `get_progress()` - Progress retrieval
- `update_progress()` - Progress updates
- `calculate_time_estimates()` - Time estimation
- `get_session_analytics()` - Analytics data

---

**Document Version**: 1.0
**Last Updated**: 2025-10-16
**Maintainer**: Backend Team
**Related Docs**:
- `/Users/sivanlissak/Documents/VisGuiAI/backend/docs/STEP_DISCLOSURE_MIGRATION.md`
- `/Users/sivanlissak/Documents/VisGuiAI/backend/docs/SESSION_SERVICE_CHANGES.md`
- `/Users/sivanlissak/Documents/VisGuiAI/backend/docs/SORTING_UTILITY_GUIDE.md`
