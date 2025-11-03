# Guide Adaptation Feature

## Overview

The Guide Adaptation feature enables the system to **dynamically adapt guides when steps become impossible** to complete. When a user encounters a step that can't be completed (e.g., UI changed, button missing, feature moved), the system generates alternative approaches using LLM intelligence.

## Key Features

### 1. Real-Time Problem Detection
Users can report when a step is impossible with:
- Problem description
- What they actually see
- What they've tried

### 2. Intelligent Alternative Generation
The LLM:
- Analyzes what's been completed
- Understands the blocked step's goal
- Considers the changed environment
- Generates 2-3 practical alternatives

### 3. Transparent Adaptation
- Original step marked as "blocked" (crossed out)
- Alternatives inserted with sub-indices (1a, 1b)
- Full adaptation history maintained
- User understands what changed and why

## Architecture

### Database Changes

#### StepStatus Enum
```python
class StepStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ALTERNATIVE = "alternative"
```

#### Updated Models
**StepGuideModel:**
- `adaptation_history: JSON` - Track all adaptations
- `last_adapted_at: DateTime` - Last adaptation timestamp

**StepModel:**
- `step_identifier: String(10)` - Support sub-indices like "1a", "1b"
- `step_status: StepStatus` - Current status
- `replaces_step_index: Integer` - For alternative steps
- `blocked_reason: String(500)` - Why step was blocked

**GuideSessionModel:**
- `current_step_identifier: String(10)` - Changed from integer to support sub-indices

### Services

#### GuideAdaptationService (`src/services/guide_adaptation_service.py`)
Core service handling adaptation logic:
- `handle_impossible_step()` - Main entry point
- `build_adaptation_context()` - Gather context for LLM
- `request_alternative_steps()` - Call LLM for alternatives
- `merge_alternatives_into_guide()` - Insert alternatives with sub-indices
- `_update_guide_with_adaptation()` - Persist changes

#### Enhanced LLMService (`src/services/llm_service.py`)
Added to all providers (Mock, OpenAI, LM Studio, Anthropic):
- `generate_step_alternatives()` - Generate alternatives based on context
- Adaptive system prompts with full context
- Fallback support across providers

### API Endpoint

#### POST `/api/v1/instruction-guides/{session_id}/report-impossible-step`

**Request:**
```json
{
  "completion_notes": "The Export button doesn't exist",
  "encountered_issues": "I only see a Download button",
  "time_taken_minutes": 5
}
```

**Response:**
```json
{
  "status": "adapted",
  "message": "Alternative approach generated successfully",
  "blocked_step": {
    "identifier": "5",
    "title": "Click Export button",
    "status": "blocked",
    "show_as": "crossed_out",
    "blocked_reason": "The Export button doesn't exist"
  },
  "alternative_steps": [
    {
      "identifier": "5a",
      "title": "Click Download button instead",
      "description": "...",
      "completion_criteria": "...",
      "estimated_duration_minutes": 5
    },
    {
      "identifier": "5b",
      "title": "Select CSV format from dropdown",
      "description": "...",
      "completion_criteria": "...",
      "estimated_duration_minutes": 3
    }
  ],
  "current_step": {
    "identifier": "5a",
    "title": "Click Download button instead",
    "...": "..."
  }
}
```

## Workflow Example

### Initial Guide
```
Step 1: Open application ✓
Step 2: Navigate to Settings ✓
Step 3: Click Export button ⬅️ USER IS HERE
Step 4: Select format
Step 5: Confirm export
```

### User Reports Problem
```
POST /api/v1/instruction-guides/{session_id}/report-impossible-step
{
  "completion_notes": "Export button doesn't exist",
  "encountered_issues": "Only see Download button"
}
```

### System Response

**Context Built:**
- Goal: Export data
- Completed: Steps 1-2
- Blocked: Step 3 (Export button)
- Problem: Button missing, Download exists

**LLM Generates Alternatives:**
- Step 3a: Click Download button
- Step 3b: Select CSV format

### Updated Guide
```
Step 1: Open application ✓
Step 2: Navigate to Settings ✓
Step 3: ~~Click Export button~~ ❌ BLOCKED (Button not found)
  ↳ Step 3a: Click Download button ⬅️ USER NOW HERE
  ↳ Step 3b: Select CSV format
Step 4: Select format
Step 5: Confirm export
```

## Sub-Index Navigation

### Step Identifier Format
- Base steps: "0", "1", "2", "3"
- Alternatives: "3a", "3b", "3c"
- Natural sorting preserves order

### Navigation Flow
```
0 → 1 → 2 → 3(blocked) → 3a → 3b → 4 → 5
```

### Progress Calculation
- Counts active + alternative steps
- Excludes blocked steps from denominator
- Completion % = (completed / total_active) * 100

## Guide Data Structure

### Before Adaptation
```json
{
  "sections": [{
    "steps": [
      {"step_identifier": "0", "status": "completed"},
      {"step_identifier": "1", "status": "completed"},
      {"step_identifier": "2", "status": "active"},
      {"step_identifier": "3", "status": "active"}
    ]
  }]
}
```

### After Adaptation
```json
{
  "sections": [{
    "steps": [
      {"step_identifier": "0", "status": "completed"},
      {"step_identifier": "1", "status": "completed"},
      {
        "step_identifier": "2",
        "status": "blocked",
        "blocked_reason": "Button missing",
        "show_as": "crossed_out"
      },
      {
        "step_identifier": "2a",
        "status": "alternative",
        "replaces_step_identifier": "2",
        "title": "Alternative approach 1"
      },
      {
        "step_identifier": "2b",
        "status": "alternative",
        "replaces_step_identifier": "2",
        "title": "Alternative approach 2"
      },
      {"step_identifier": "3", "status": "active"}
    ]
  }],
  "adaptation_history": [{
    "timestamp": "2024-09-29T16:00:00Z",
    "blocked_step_identifier": "2",
    "blocked_reason": "Button missing",
    "alternatives_added": ["2a", "2b"],
    "llm_provider": "openai"
  }]
}
```

## Testing

### Integration Tests
Created comprehensive tests in `tests/test_guide_adaptation.py`:
- Test reporting impossible step
- Test LLM alternative generation
- Test guide structure after adaptation
- Test navigation through alternatives
- Test multiple adaptations in same session

### Manual Testing

1. **Generate a guide:**
```bash
POST /api/v1/instruction-guides/generate
{
  "instruction": "export data to CSV",
  "difficulty": "beginner"
}
```

2. **Progress to a step:**
```bash
POST /api/v1/instruction-guides/{session_id}/complete-step
```

3. **Report step as impossible:**
```bash
POST /api/v1/instruction-guides/{session_id}/report-impossible-step
{
  "completion_notes": "Export button missing",
  "encountered_issues": "Only Download button exists"
}
```

4. **Verify alternatives generated and user on first alternative**

## LLM Prompt Strategy

### Adaptive Prompt Structure
```
SITUATION:
- Original Goal: {what user is trying to achieve}
- Completed Steps: {what worked so far}
- Blocked Step: {what doesn't work}
- Problem: {user's description}
- User Sees: {actual environment}

TASK:
Generate 2-3 alternative approaches that:
1. Achieve the same goal
2. Account for changed environment
3. Are immediately actionable

Return structured JSON with alternatives
```

### Provider Support
- ✅ MockLLMProvider - For testing
- ✅ OpenAIProvider - GPT-4
- ✅ LMStudioProvider - Local models
- ✅ AnthropicProvider - Claude

All providers implement same interface with fallback support.

## Database Migration

### Migration: 002_add_step_adaptation_support.py

**Upgrade:**
- Create StepStatus enum
- Add adaptation_history, last_adapted_at to step_guides
- Add step_identifier, step_status, replaces_step_index, blocked_reason to steps
- Convert current_step_index (int) to current_step_identifier (string)

**Downgrade:**
- Reverse all changes
- Convert string identifiers back to integers (strips letters)

## Benefits

### For Users
- ✅ Never get permanently stuck
- ✅ Real-time problem solving
- ✅ Transparency about changes
- ✅ Multiple solution paths

### For System
- ✅ Guides self-heal
- ✅ Adapts to environment changes
- ✅ Learns from user problems
- ✅ Maintains guide quality

## Future Enhancements

### Possible Improvements
1. **Analytics Dashboard** - Track common adaptation patterns
2. **Proactive Adaptation** - Detect UI changes automatically
3. **Community Alternatives** - Learn from other users' solutions
4. **Confidence Scoring** - Rate alternative likelihood of success
5. **Visual Diff** - Show what changed in screenshots

## Configuration

### Environment Variables
No new configuration needed. Uses existing LLM provider settings:
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `LM_STUDIO_BASE_URL`
- `LM_STUDIO_MODEL`

## Troubleshooting

### Common Issues

**Issue:** Alternatives not generated
- Check LLM provider availability
- Verify API keys are set
- Check logs for LLM errors

**Issue:** Step identifiers incorrect
- Verify session uses string identifiers
- Check migration ran successfully
- Ensure guide_data JSON is valid

**Issue:** Navigation broken after adaptation
- Verify natural sorting in disclosure service
- Check step_identifier format (no special chars)
- Validate guide structure after merge

## Conclusion

The Guide Adaptation feature transforms the system from **static guide delivery** to **dynamic problem-solving assistant**. When steps become impossible, the system intelligently adapts, keeping users productive and guides relevant.

**Status:** ✅ Fully Implemented
- Database models updated
- Services created
- API endpoint added
- LLM integration complete
- Migration ready
- Tests written