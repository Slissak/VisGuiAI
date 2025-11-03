# API Usage Examples

This document provides comprehensive examples for using the VisGuiAI API. All examples use `curl` for demonstration, but the same principles apply to any HTTP client.

## Table of Contents

- [Authentication](#authentication)
- [Quick Start](#quick-start)
- [Guide Generation](#guide-generation)
- [Step Progression](#step-progression)
- [Guide Adaptation](#guide-adaptation)
- [Progress Tracking](#progress-tracking)
- [Error Handling](#error-handling)

---

## Authentication

All API requests require authentication using a Bearer token in the Authorization header.

```bash
export TOKEN="your_jwt_token_here"
export BASE_URL="http://localhost:8000"
```

Include the token in all requests:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  $BASE_URL/api/v1/...
```

---

## Quick Start

### Generate a Guide and Complete First Step

```bash
# 1. Generate a guide
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/instruction-guides/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "deploy a React app to Vercel",
    "difficulty": "beginner",
    "format_preference": "detailed"
  }')

# Extract session_id from response
SESSION_ID=$(echo $RESPONSE | jq -r '.session_id')
echo "Session ID: $SESSION_ID"

# 2. Complete the first step
curl -X POST "$BASE_URL/api/v1/instruction-guides/$SESSION_ID/complete-step" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "completion_notes": "Vercel CLI installed successfully",
    "time_taken_minutes": 3
  }'
```

---

## Guide Generation

### Basic Guide Generation

Generate a beginner-level guide with detailed instructions:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "deploy a React app to Vercel",
    "difficulty": "beginner",
    "format_preference": "detailed"
  }'
```

**Expected Response (201 Created):**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "guide_id": "650e8400-e29b-41d4-a716-446655440000",
  "guide_title": "How to deploy React app to Vercel",
  "message": "Guide generated successfully. Start with the first step below.",
  "first_step": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "active",
    "current_step": {
      "step_identifier": "0",
      "title": "Install Vercel CLI",
      "description": "Install the Vercel CLI tool to enable command-line deployments...",
      "completion_criteria": "Vercel CLI is installed and accessible from terminal",
      "assistance_hints": [
        "Use npm install -g vercel",
        "Verify installation with 'vercel --version'"
      ],
      "estimated_duration_minutes": 5
    },
    "progress": {
      "total_steps": 12,
      "completed_steps": 0,
      "completion_percentage": 0
    }
  }
}
```

### Advanced Guide Generation

Generate an advanced-level guide with concise instructions:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "set up a CI/CD pipeline with GitHub Actions",
    "difficulty": "advanced",
    "format_preference": "concise"
  }'
```

---

## Step Progression

### Complete Current Step

Mark the current step as completed and advance to the next step:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/$SESSION_ID/complete-step" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "completion_notes": "CLI installed successfully",
    "encountered_issues": null,
    "time_taken_minutes": 3
  }'
```

**Expected Response (200 OK):**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "active",
  "current_step": {
    "step_identifier": "1",
    "title": "Configure Vercel project",
    "description": "Link your React app to Vercel project...",
    "completion_criteria": "Vercel project is configured",
    "assistance_hints": ["Run 'vercel' in project directory"],
    "estimated_duration_minutes": 10
  },
  "progress": {
    "total_steps": 12,
    "completed_steps": 1,
    "completion_percentage": 8.33
  }
}
```

### Complete Step with Issues

Document issues encountered during step completion:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/$SESSION_ID/complete-step" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "completion_notes": "Configuration completed but with warnings",
    "encountered_issues": "Got deprecation warnings for old configuration format",
    "time_taken_minutes": 15
  }'
```

### Get Current Step

Retrieve the current step without advancing:

```bash
curl -X GET "$BASE_URL/api/v1/instruction-guides/$SESSION_ID/current-step" \
  -H "Authorization: Bearer $TOKEN"
```

### Navigate to Previous Step

Go back to review a previous step:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/$SESSION_ID/previous-step" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Guide Adaptation

### Report Impossible Step

When a step cannot be completed (e.g., UI has changed), request alternative approaches:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/$SESSION_ID/report-impossible-step" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "completion_notes": "The Deploy button does not exist in the UI anymore",
    "encountered_issues": "I see New Deployment and Import Project buttons instead"
  }'
```

**Expected Response (200 OK):**

```json
{
  "status": "adapted",
  "message": "Generated 2 alternative approaches to work around the blocked step",
  "blocked_step": {
    "identifier": "3",
    "title": "Click the Deploy button",
    "status": "blocked",
    "show_as": "crossed_out",
    "blocked_reason": "UI changed - button doesn't exist"
  },
  "alternative_steps": [
    {
      "identifier": "3-alt-1",
      "title": "Use command-line deployment",
      "description": "Deploy using the Vercel CLI instead of the web UI",
      "completion_criteria": "App deployed successfully via CLI",
      "estimated_duration_minutes": 5
    },
    {
      "identifier": "3-alt-2",
      "title": "Use GitHub integration",
      "description": "Set up automatic deployments via GitHub",
      "completion_criteria": "GitHub integration configured",
      "estimated_duration_minutes": 10
    }
  ],
  "current_step": {
    "identifier": "3-alt-1",
    "title": "Use command-line deployment",
    "description": "Deploy using the Vercel CLI instead of the web UI",
    "completion_criteria": "App deployed successfully via CLI",
    "assistance_hints": ["Run 'vercel --prod' in your project"],
    "visual_markers": []
  }
}
```

### Request Additional Help

Request more hints or assistance for the current step:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/$SESSION_ID/request-help" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "help_type": "hints",
    "context": "Not sure which configuration file to edit"
  }'
```

---

## Progress Tracking

### Get Session Progress

Retrieve overall progress for a guide session:

```bash
curl -X GET "$BASE_URL/api/v1/progress/$SESSION_ID" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response (200 OK):**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_steps": 12,
  "completed_steps": 5,
  "current_step_index": 5,
  "completion_percentage": 41.67,
  "estimated_time_remaining_minutes": 35,
  "time_elapsed_minutes": 25,
  "last_updated": "2025-10-26T10:30:00Z"
}
```

### Get Time Estimates

Get updated time estimates based on actual completion times:

```bash
curl -X GET "$BASE_URL/api/v1/progress/$SESSION_ID/estimates" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response (200 OK):**

```json
{
  "estimated_total_minutes": 60,
  "estimated_remaining_minutes": 35,
  "average_step_duration_minutes": 5.2,
  "time_elapsed_minutes": 25
}
```

### Get Session Analytics

Retrieve detailed analytics and insights:

```bash
curl -X GET "$BASE_URL/api/v1/progress/$SESSION_ID/analytics" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response (200 OK):**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_steps": 12,
  "completed_steps": 5,
  "steps_needing_assistance": 1,
  "average_completion_time_minutes": 5.2,
  "fastest_step_minutes": 2,
  "slowest_step_minutes": 12,
  "completion_rate": 0.42,
  "started_at": "2025-10-26T09:00:00Z",
  "last_activity_at": "2025-10-26T10:30:00Z"
}
```

---

## Error Handling

### Invalid Request (400 Bad Request)

Missing required field:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "difficulty": "beginner"
  }'
```

**Expected Response:**

```json
{
  "detail": "instruction field is required"
}
```

### Unauthorized (401 Unauthorized)

Missing or invalid authentication token:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "deploy a React app"
  }'
```

**Expected Response:**

```json
{
  "detail": "Not authenticated"
}
```

### Forbidden (403 Forbidden)

Attempting to access another user's session:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/OTHER_USER_SESSION_ID/complete-step" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Expected Response:**

```json
{
  "detail": "Access denied to this session"
}
```

### Not Found (404 Not Found)

Session doesn't exist:

```bash
curl -X GET "$BASE_URL/api/v1/instruction-guides/00000000-0000-0000-0000-000000000000/current-step" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**

```json
{
  "detail": "Session 00000000-0000-0000-0000-000000000000 not found"
}
```

### Internal Server Error (500)

LLM service unavailable:

```bash
curl -X POST "$BASE_URL/api/v1/instruction-guides/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "deploy a React app"
  }'
```

**Expected Response:**

```json
{
  "detail": "Failed to generate instruction guide: All LLM providers unavailable"
}
```

---

## Complete Workflow Example

Here's a complete example of generating a guide, completing steps, and handling an impossible step:

```bash
#!/bin/bash

# Set environment variables
export TOKEN="your_jwt_token_here"
export BASE_URL="http://localhost:8000"

# 1. Generate a guide
echo "Generating guide..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/instruction-guides/generate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "deploy a React app to Vercel",
    "difficulty": "beginner",
    "format_preference": "detailed"
  }')

SESSION_ID=$(echo $RESPONSE | jq -r '.session_id')
echo "Session ID: $SESSION_ID"
echo "First step: $(echo $RESPONSE | jq -r '.first_step.current_step.title')"

# 2. Complete first step
echo -e "\nCompleting first step..."
curl -s -X POST "$BASE_URL/api/v1/instruction-guides/$SESSION_ID/complete-step" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "completion_notes": "CLI installed",
    "time_taken_minutes": 3
  }' | jq '.current_step.title'

# 3. Complete second step
echo -e "\nCompleting second step..."
curl -s -X POST "$BASE_URL/api/v1/instruction-guides/$SESSION_ID/complete-step" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "completion_notes": "Project configured",
    "time_taken_minutes": 5
  }' | jq '.current_step.title'

# 4. Report impossible step
echo -e "\nReporting impossible step..."
curl -s -X POST "$BASE_URL/api/v1/instruction-guides/$SESSION_ID/report-impossible-step" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "completion_notes": "UI has changed - button not found",
    "encountered_issues": "Deploy button does not exist"
  }' | jq '.message, .alternative_steps[].title'

# 5. Check progress
echo -e "\nChecking progress..."
curl -s -X GET "$BASE_URL/api/v1/progress/$SESSION_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '{
    total_steps,
    completed_steps,
    completion_percentage
  }'
```

---

## Testing with Different Tools

### Using HTTPie

```bash
# Generate guide
http POST $BASE_URL/api/v1/instruction-guides/generate \
  "Authorization: Bearer $TOKEN" \
  instruction="deploy a React app" \
  difficulty=beginner

# Complete step
http POST $BASE_URL/api/v1/instruction-guides/$SESSION_ID/complete-step \
  "Authorization: Bearer $TOKEN" \
  completion_notes="Done" \
  time_taken_minutes:=5
```

### Using Postman

1. Import the OpenAPI specification from `/backend/docs/openapi.json`
2. Set up environment variables:
   - `BASE_URL`: `http://localhost:8000`
   - `TOKEN`: Your JWT token
3. Use the pre-configured requests with example payloads

### Using Python requests

```python
import requests

BASE_URL = "http://localhost:8000"
TOKEN = "your_jwt_token"
headers = {"Authorization": f"Bearer {TOKEN}"}

# Generate guide
response = requests.post(
    f"{BASE_URL}/api/v1/instruction-guides/generate",
    headers=headers,
    json={
        "instruction": "deploy a React app to Vercel",
        "difficulty": "beginner",
        "format_preference": "detailed"
    }
)

session_id = response.json()["session_id"]
print(f"Session ID: {session_id}")

# Complete step
response = requests.post(
    f"{BASE_URL}/api/v1/instruction-guides/{session_id}/complete-step",
    headers=headers,
    json={
        "completion_notes": "CLI installed",
        "time_taken_minutes": 3
    }
)

next_step = response.json()["current_step"]["title"]
print(f"Next step: {next_step}")
```

---

## Rate Limiting and Best Practices

### Rate Limits

- Guide generation: 10 requests per minute per user
- Step completion: 100 requests per minute per user
- Progress queries: 200 requests per minute per user

### Best Practices

1. **Cache session IDs**: Store the session_id locally to avoid repeated guide generation
2. **Handle errors gracefully**: Always check for error responses and handle them appropriately
3. **Use progressive disclosure**: Don't try to fetch all steps at once
4. **Report issues**: Use the `encountered_issues` field to help improve guides
5. **Track time**: Provide accurate `time_taken_minutes` for better estimates
6. **Test adaptation**: Test the impossible-step reporting to ensure your integration handles alternatives

---

## Additional Resources

- [OpenAPI Specification](./openapi.json)
- [API Documentation (HTML)](./api-docs.html)
- [Postman Collection](./postman_collection.json)
- [Integration Tests](../tests/integration/)

For questions or support, please contact the VisGuiAI development team.
