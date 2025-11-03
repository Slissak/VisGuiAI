"""LLM integration service with dual provider support (OpenAI + Anthropic)."""

import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from uuid import uuid4
from pathlib import Path
from datetime import datetime

from shared.schemas.llm_request import LLMProvider
from ..core.config import get_settings
from ..core.cache import CacheManager
from ..utils.logging import get_logger

logger = get_logger(__name__)


class LLMProvider:
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_guide(
        self,
        user_query: str,
        difficulty: str = "beginner",
        format_preference: str = "detailed"
    ) -> Dict[str, Any]:
        """Generate a step-by-step guide."""
        pass

    @abstractmethod
    async def generate_step_alternatives(
        self,
        original_goal: str,
        completed_steps: List[Dict[str, Any]],
        blocked_step: Dict[str, Any],
        problem: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate alternative steps when current step is blocked."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available."""
        pass


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing and development."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name

    async def generate_guide(
        self,
        user_query: str,
        difficulty: str = "beginner",
        format_preference: str = "detailed"
    ) -> Dict[str, Any]:
        """Generate a mock step-by-step guide with sections."""
        # Simulate API call delay
        await asyncio.sleep(0.5)

        # Generate sections with steps based on query complexity
        sections = []

        # Common section types
        section_templates = [
            {"id": "setup", "title": "Setup", "description": "Initial preparation steps"},
            {"id": "configuration", "title": "Configuration", "description": "Settings and adjustments"},
            {"id": "execution", "title": "Execution", "description": "Main action steps"},
            {"id": "validation", "title": "Validation", "description": "Verification and testing"}
        ]

        section_count = 2 if difficulty == "beginner" else 3 if difficulty == "intermediate" else 4
        steps_per_section = 2 if difficulty == "beginner" else 3

        for section_idx in range(section_count):
            section_template = section_templates[section_idx]
            steps = []

            for step_idx in range(steps_per_section):
                global_step_idx = section_idx * steps_per_section + step_idx + 1  # Start from 1, not 0
                steps.append({
                    "step_index": global_step_idx,
                    "title": f"{section_template['title']} Step {step_idx + 1}: {user_query.split()[-1] if user_query.split() else 'Task'}",
                    "description": f"Detailed instructions for {section_template['title'].lower()} step {step_idx + 1} of {user_query}. This step involves specific actions within the {section_template['title'].lower()} phase.",
                    "completion_criteria": f"Successfully complete the {section_template['title'].lower()} actions in step {step_idx + 1}",
                    "assistance_hints": [
                        f"If you're stuck on this {section_template['title'].lower()} step, try checking the documentation",
                        f"This step typically takes 2-5 minutes to complete"
                    ],
                    "estimated_duration_minutes": 3 + step_idx,
                    "requires_desktop_monitoring": global_step_idx % 2 == 0,
                    "visual_markers": [f"button_{global_step_idx}", f"dialog_{global_step_idx}"] if global_step_idx % 2 == 0 else [],
                    "prerequisites": [f"Complete previous {section_template['title'].lower()} steps"] if step_idx > 0 else [],
                    "completed": False,
                    "needs_assistance": False
                })

            sections.append({
                "section_id": section_template["id"],
                "section_title": section_template["title"],
                "section_description": f"{section_template['description']} for {user_query}",
                "section_order": section_idx,
                "steps": steps
            })

        total_duration = sum(step["estimated_duration_minutes"] for section in sections for step in section["steps"])

        return {
            "guide": {
                "title": f"How to {user_query}",
                "description": f"A comprehensive {difficulty}-level guide for: {user_query}",
                "category": "general",
                "difficulty_level": difficulty,
                "estimated_duration_minutes": total_duration,
                "sections": sections
            }
        }

    async def is_available(self) -> bool:
        """Mock provider is always available."""
        return True

    async def generate_step_alternatives(
        self,
        original_goal: str,
        completed_steps: List[Dict[str, Any]],
        blocked_step: Dict[str, Any],
        problem: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate mock alternative steps for blocked step."""
        # Simulate API call delay
        await asyncio.sleep(0.3)

        blocked_title = blocked_step.get("title", "Unknown step")
        problem_desc = problem.get("description", "Unknown problem")

        # Generate 2-3 alternative steps
        alternative_steps = [
            {
                "title": f"Alternative approach 1: {blocked_title}",
                "description": f"Since {problem_desc}, try this alternative approach. Look for similar functionality in a different location.",
                "completion_criteria": "Successfully found and completed the alternative action",
                "assistance_hints": [
                    "Check the main menu or toolbar",
                    "Look for keyboard shortcuts",
                    "Try right-clicking for context menus"
                ],
                "estimated_duration_minutes": 5,
                "requires_desktop_monitoring": True,
                "visual_markers": ["menu_icon", "toolbar_button"],
                "prerequisites": []
            },
            {
                "title": f"Alternative approach 2: {blocked_title}",
                "description": f"Another way to achieve the same goal: use the settings or preferences panel to access this functionality.",
                "completion_criteria": "Successfully completed via alternative method",
                "assistance_hints": [
                    "Open settings/preferences",
                    "Search for the feature name",
                    "Check advanced options"
                ],
                "estimated_duration_minutes": 7,
                "requires_desktop_monitoring": True,
                "visual_markers": ["settings_gear", "preferences_panel"],
                "prerequisites": []
            }
        ]

        return {
            "reason_for_change": f"Original approach blocked: {problem_desc}. Generated {len(alternative_steps)} alternative approaches.",
            "alternative_steps": alternative_steps
        }


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider implementation."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = None

    async def _initialize_client(self):
        """Initialize OpenAI client lazily."""
        if self.client is None:
            try:
                import openai
                self.client = openai.AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("OpenAI package not installed. Run: pip install openai")

    async def generate_guide(
        self,
        user_query: str,
        difficulty: str = "beginner",
        format_preference: str = "detailed"
    ) -> Dict[str, Any]:
        """Generate guide using OpenAI GPT with structured sections."""
        await self._initialize_client()

        system_prompt = f"""You are an expert assistant that creates comprehensive step-by-step guides with logical sectioning.

Create a {difficulty}-level guide for: "{user_query}"

IMPORTANT: Structure your guide with logical sections that group related steps together. For example:
- "Setup" section for preparation steps
- "Configuration" section for settings and adjustments
- "Execution" section for main action steps
- "Validation" section for verification steps

Return ONLY a valid JSON object with this exact structure:
{{
  "guide": {{
    "title": "string",
    "description": "string",
    "category": "string",
    "difficulty_level": "{difficulty}",
    "estimated_duration_minutes": number,
    "sections": [
      {{
        "section_id": "string (lowercase_underscore)",
        "section_title": "string",
        "section_description": "string",
        "section_order": number,
        "steps": [
          {{
            "step_index": number,
            "title": "string",
            "description": "string",
            "completion_criteria": "string",
            "assistance_hints": ["string"],
            "estimated_duration_minutes": number,
            "requires_desktop_monitoring": boolean,
            "visual_markers": ["string"],
            "prerequisites": ["string (optional dependencies)"],
            "completed": false,
            "needs_assistance": false
          }}
        ]
      }}
    ]
  }}
}}

Guidelines:
- Create 2-4 logical sections with 2-4 steps each
- Each step should be clear and actionable within its section
- Include specific completion criteria for each step
- Add helpful hints for each step
- Estimate realistic time requirements
- Mark steps that could use desktop monitoring (UI interactions)
- Provide visual markers for desktop monitoring steps (buttons, dialogs, etc.)
- Add prerequisites for steps that depend on previous steps
- Ensure logical flow between sections and steps
"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            content = response.choices[0].message.content
            parsed_data = json.loads(content)
            # Add raw content to the result for debugging
            parsed_data["_raw_llm_response"] = content
            return parsed_data

        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")

    async def is_available(self) -> bool:
        """Check if OpenAI is available."""
        try:
            await self._initialize_client()
            # Simple test call
            await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            return True
        except Exception:
            return False

    async def generate_step_alternatives(
        self,
        original_goal: str,
        completed_steps: List[Dict[str, Any]],
        blocked_step: Dict[str, Any],
        problem: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate alternative steps using OpenAI GPT."""
        await self._initialize_client()

        # Build completed steps summary
        completed_summary = "\n".join([
            f"- {step.get('title', 'Unknown')}: {step.get('description', '')[:100]}"
            for step in completed_steps
        ])

        system_prompt = f"""You are an expert problem-solver for step-by-step guides.

SITUATION:
- Original Goal: {original_goal}
- Steps Completed Successfully:
{completed_summary}

- Current Blocked Step: {blocked_step.get('title', 'Unknown')}
  Description: {blocked_step.get('description', 'No description')}

- Problem Encountered: {problem.get('description', 'Unknown problem')}
- What User Actually Sees: {problem.get('what_user_sees', 'Not specified')}
- User Attempted Solutions: {', '.join(problem.get('attempted_solutions', []))}

TASK:
Generate 2-3 ALTERNATIVE steps to achieve the same outcome as the blocked step, given the changed circumstances.

Return ONLY valid JSON:
{{
  "reason_for_change": "brief explanation of why alternatives are needed",
  "alternative_steps": [
    {{
      "title": "Alternative step title",
      "description": "Detailed instructions for this alternative approach",
      "completion_criteria": "How to know this step is complete",
      "assistance_hints": ["helpful tip 1", "helpful tip 2"],
      "estimated_duration_minutes": number,
      "requires_desktop_monitoring": boolean,
      "visual_markers": ["UI elements to look for"],
      "prerequisites": []
    }}
  ]
}}

Guidelines:
- Generate 2-3 practical alternatives
- Account for what the user actually sees
- Be specific and actionable
- Achieve the same end goal as the blocked step
"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate alternatives for the blocked step."}
                ],
                temperature=0.7,
                max_tokens=1500
            )

            content = response.choices[0].message.content
            parsed_data = json.loads(content)
            # Add raw content to the result for debugging
            parsed_data["_raw_llm_response"] = content
            return parsed_data

        except Exception as e:
            raise Exception(f"OpenAI API error: {e}")


class LMStudioProvider(LLMProvider):
    """LM Studio local LLM provider implementation."""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model
        self.client = None
        self.provider_name = "lm_studio"

    async def _initialize_client(self):
        """Initialize OpenAI-compatible client for LM Studio."""
        if self.client is None:
            try:
                import openai
                # Use OpenAI client with custom base URL for LM Studio
                self.client = openai.AsyncOpenAI(
                    base_url=self.base_url,
                    api_key="lm-studio"  # LM Studio doesn't require a real API key
                )
            except ImportError:
                raise ImportError("OpenAI package not installed. Run: pip install openai")

    async def generate_guide(
        self,
        user_query: str,
        difficulty: str = "beginner",
        format_preference: str = "detailed"
    ) -> Dict[str, Any]:
        """Generate guide using LM Studio local LLM with structured sections."""
        await self._initialize_client()

        system_prompt = f"""You are an expert assistant that creates comprehensive step-by-step guides with logical sectioning.

Create a {difficulty}-level guide for: "{user_query}"

IMPORTANT: Structure your guide with logical sections that group related steps together. For example:
- "Setup" section for preparation steps
- "Configuration" section for settings and adjustments
- "Execution" section for main action steps
- "Validation" section for verification steps

Return ONLY a valid JSON object with this exact structure:
{{
  "guide": {{
    "title": "string",
    "description": "string",
    "category": "string",
    "difficulty_level": "{difficulty}",
    "estimated_duration_minutes": number,
    "sections": [
      {{
        "section_id": "string (lowercase_underscore)",
        "section_title": "string",
        "section_description": "string",
        "section_order": number,
        "steps": [
          {{
            "step_index": number,
            "title": "string",
            "description": "string",
            "completion_criteria": "string",
            "assistance_hints": ["string"],
            "estimated_duration_minutes": number,
            "requires_desktop_monitoring": boolean,
            "visual_markers": ["string"],
            "prerequisites": ["string (optional dependencies)"],
            "completed": false,
            "needs_assistance": false
          }}
        ]
      }}
    ]
  }}
}}

Guidelines:
- Create 2-4 logical sections with 2-4 steps each
- Each step should be clear and actionable within its section
- Include specific completion criteria for each step
- Add helpful hints for each step
- Estimate realistic time requirements
- Mark steps that could use desktop monitoring (UI interactions)
- Provide visual markers for desktop monitoring steps (buttons, dialogs, etc.)
- Add prerequisites for steps that depend on previous steps
- Ensure logical flow between sections and steps
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.7,
                max_tokens=2000
            )

            content = response.choices[0].message.content
            parsed_data = json.loads(content)
            # Add raw content to the result for debugging
            parsed_data["_raw_llm_response"] = content
            return parsed_data

        except Exception as e:
            raise Exception(f"LM Studio API error: {e}")

    async def is_available(self) -> bool:
        """Check if LM Studio is available."""
        try:
            await self._initialize_client()
            # Test with a simple request
            await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            return True
        except Exception:
            return False

    async def generate_step_alternatives(
        self,
        original_goal: str,
        completed_steps: List[Dict[str, Any]],
        blocked_step: Dict[str, Any],
        problem: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate alternative steps using LM Studio."""
        await self._initialize_client()

        # Build completed steps summary
        completed_summary = "\n".join([
            f"- {step.get('title', 'Unknown')}: {step.get('description', '')[:100]}"
            for step in completed_steps
        ])

        system_prompt = f"""You are an expert problem-solver for step-by-step guides.

SITUATION:
- Original Goal: {original_goal}
- Steps Completed Successfully:
{completed_summary}

- Current Blocked Step: {blocked_step.get('title', 'Unknown')}
  Description: {blocked_step.get('description', 'No description')}

- Problem Encountered: {problem.get('description', 'Unknown problem')}
- What User Actually Sees: {problem.get('what_user_sees', 'Not specified')}
- User Attempted Solutions: {', '.join(problem.get('attempted_solutions', []))}

TASK:
Generate 2-3 ALTERNATIVE steps to achieve the same outcome as the blocked step.

Return ONLY valid JSON:
{{
  "reason_for_change": "brief explanation",
  "alternative_steps": [
    {{
      "title": "Alternative step title",
      "description": "Detailed instructions",
      "completion_criteria": "How to know complete",
      "assistance_hints": ["tip 1", "tip 2"],
      "estimated_duration_minutes": number,
      "requires_desktop_monitoring": boolean,
      "visual_markers": ["UI elements"],
      "prerequisites": []
    }}
  ]
}}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate alternatives."}
                ],
                temperature=0.7,
                max_tokens=1500
            )

            content = response.choices[0].message.content
            parsed_data = json.loads(content)
            # Add raw content to the result for debugging
            parsed_data["_raw_llm_response"] = content
            return parsed_data

        except Exception as e:
            raise Exception(f"LM Studio API error: {e}")


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider implementation."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = None

    async def _initialize_client(self):
        """Initialize Anthropic client lazily."""
        if self.client is None:
            try:
                import anthropic
                self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("Anthropic package not installed. Run: pip install anthropic")

    async def generate_guide(
        self,
        user_query: str,
        difficulty: str = "beginner",
        format_preference: str = "detailed"
    ) -> Dict[str, Any]:
        """Generate guide using Anthropic Claude."""
        await self._initialize_client()

        prompt = f"""Create a {difficulty}-level step-by-step guide for: "{user_query}"

IMPORTANT: Structure your guide with logical sections that group related steps together. For example:
- "Setup" section for preparation steps
- "Configuration" section for settings and adjustments
- "Execution" section for main action steps
- "Validation" section for verification steps

Return ONLY a valid JSON object with this structure:
{{
  "guide": {{
    "title": "How to {user_query}",
    "description": "A comprehensive guide...",
    "category": "appropriate category",
    "difficulty_level": "{difficulty}",
    "estimated_duration_minutes": total_time,
    "sections": [
      {{
        "section_id": "string (lowercase_underscore)",
        "section_title": "string",
        "section_description": "string",
        "section_order": number,
        "steps": [
          {{
            "step_index": number,
            "title": "Step title",
            "description": "Detailed instructions",
            "completion_criteria": "How to know it's done",
            "assistance_hints": ["helpful tip"],
            "estimated_duration_minutes": minutes,
            "requires_desktop_monitoring": true/false,
            "visual_markers": ["UI elements to look for"],
            "prerequisites": ["string (optional dependencies)"],
            "completed": false,
            "needs_assistance": false
          }}
        ]
      }}
    ]
  }}
}}

Guidelines:
- Create 2-4 logical sections with 2-4 steps each
- Each step should be clear and actionable within its section
- Include specific completion criteria for each step
- Add helpful hints for each step
- Estimate realistic time requirements
- Mark steps that could use desktop monitoring (UI interactions)
- Provide visual markers for desktop monitoring steps (buttons, dialogs, etc.)
- Add prerequisites for steps that depend on previous steps

Make it {format_preference} and practical."""

        try:
            response = await self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            parsed_data = json.loads(content)
            # Add raw content to the result for debugging
            parsed_data["_raw_llm_response"] = content
            return parsed_data

        except Exception as e:
            raise Exception(f"Anthropic API error: {e}")

    async def is_available(self) -> bool:
        """Check if Anthropic is available."""
        try:
            await self._initialize_client()
            # Simple test call
            await self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=5,
                messages=[{"role": "user", "content": "test"}]
            )
            return True
        except Exception:
            return False

    async def generate_step_alternatives(
        self,
        original_goal: str,
        completed_steps: List[Dict[str, Any]],
        blocked_step: Dict[str, Any],
        problem: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate alternative steps using Anthropic Claude."""
        await self._initialize_client()

        # Build completed steps summary
        completed_summary = "\n".join([
            f"- {step.get('title', 'Unknown')}: {step.get('description', '')[:100]}"
            for step in completed_steps
        ])

        prompt = f"""You are an expert problem-solver for step-by-step guides.

SITUATION:
- Original Goal: {original_goal}
- Steps Completed Successfully:
{completed_summary}

- Current Blocked Step: {blocked_step.get('title', 'Unknown')}
  Description: {blocked_step.get('description', 'No description')}

- Problem Encountered: {problem.get('description', 'Unknown problem')}
- What User Actually Sees: {problem.get('what_user_sees', 'Not specified')}
- User Attempted Solutions: {', '.join(problem.get('attempted_solutions', []))}

TASK:
Generate 2-3 ALTERNATIVE steps to achieve the same outcome as the blocked step, given the changed circumstances.

Return ONLY valid JSON:
{{
  "reason_for_change": "brief explanation of why alternatives are needed",
  "alternative_steps": [
    {{
      "title": "Alternative step title",
      "description": "Detailed instructions for this alternative approach",
      "completion_criteria": "How to know this step is complete",
      "assistance_hints": ["helpful tip 1", "helpful tip 2"],
      "estimated_duration_minutes": number,
      "requires_desktop_monitoring": boolean,
      "visual_markers": ["UI elements to look for"],
      "prerequisites": []
    }}
  ]
}}

Guidelines:
- Generate 2-3 practical alternatives
- Account for what the user actually sees
- Be specific and actionable
- Achieve the same end goal as the blocked step"""

        try:
            response = await self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text
            parsed_data = json.loads(content)
            # Add raw content to the result for debugging
            parsed_data["_raw_llm_response"] = content
            return parsed_data

        except Exception as e:
            raise Exception(f"Anthropic API error: {e}")


class LLMService:
    """Main LLM service with dual provider support and fallback."""

    def __init__(self, cache: CacheManager = None):
        self.settings = get_settings()
        self.providers = self._initialize_providers()
        self.primary_provider = None
        self.fallback_provider = None
        self.log_file = None
        self.cache = cache

    def _initialize_providers(self) -> Dict[str, LLMProvider]:
        """Initialize available LLM providers."""
        providers = {}

        # Always include mock provider for testing
        providers["mock"] = MockLLMProvider("mock")

        # Add LM Studio if enabled (highest priority for local development)
        if self.settings.enable_lm_studio:
            providers["lm_studio"] = LMStudioProvider(
                self.settings.lm_studio_base_url,
                self.settings.lm_studio_model
            )

        # Add OpenAI if API key is available
        if self.settings.openai_api_key:
            providers["openai"] = OpenAIProvider(self.settings.openai_api_key)

        # Add Anthropic if API key is available
        if self.settings.anthropic_api_key:
            providers["anthropic"] = AnthropicProvider(self.settings.anthropic_api_key)

        return providers

    async def initialize(self):
        """Initialize the service and determine provider priorities."""
        # Create logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        self.log_file = logs_dir / "llm_requests.jsonl"

        # Test provider availability
        available_providers = []
        for name, provider in self.providers.items():
            if await provider.is_available():
                available_providers.append(name)

        # Set primary and fallback providers (LM Studio gets highest priority)
        if "lm_studio" in available_providers:
            self.primary_provider = self.providers["lm_studio"]
            # Fallback to cloud providers if available, then mock
            if "openai" in available_providers:
                self.fallback_provider = self.providers["openai"]
            elif "anthropic" in available_providers:
                self.fallback_provider = self.providers["anthropic"]
            else:
                self.fallback_provider = self.providers["mock"]
        elif "openai" in available_providers:
            self.primary_provider = self.providers["openai"]
            self.fallback_provider = self.providers.get("anthropic") or self.providers["mock"]
        elif "anthropic" in available_providers:
            self.primary_provider = self.providers["anthropic"]
            self.fallback_provider = self.providers["mock"]
        else:
            self.primary_provider = self.providers["mock"]
            self.fallback_provider = None

        print(f"✅ LLM Service initialized with {len(available_providers)} providers")

    async def generate_guide(
        self,
        user_query: str,
        difficulty: str = "beginner",
        format_preference: str = "detailed"
    ) -> tuple[Dict[str, Any], str, float]:
        """Generate guide with fallback support and caching.

        Returns:
            tuple: (guide_data, provider_used, generation_time)
        """
        # Try to get from cache first (TTL: 24 hours)
        if self.cache:
            cache_key = self.cache.make_llm_key(user_query, difficulty)
            cached_response = await self.cache.get(cache_key)

            if cached_response:
                logger.info(
                    "llm_cache_hit",
                    operation="generate_guide",
                    user_query=user_query[:100],
                    difficulty=difficulty
                )
                return (
                    cached_response.get("guide_data"),
                    cached_response.get("provider_used", "cached"),
                    cached_response.get("generation_time", 0.0)
                )

        start_time = time.time()

        logger.info(
            "llm_request_started",
            operation="generate_guide",
            user_query=user_query,
            difficulty=difficulty,
            format_preference=format_preference
        )

        # Try primary provider first
        try:
            if self.primary_provider:
                result = await self.primary_provider.generate_guide(
                    user_query, difficulty, format_preference
                )
                generation_time = time.time() - start_time
                provider_name = getattr(self.primary_provider, 'provider_name', 'primary')

                logger.info(
                    "llm_request_completed",
                    operation="generate_guide",
                    provider=provider_name,
                    latency_ms=round(generation_time * 1000, 2),
                    user_query=user_query[:100]  # Truncate for logging
                )

                # Cache the result (TTL: 24 hours)
                if self.cache:
                    cache_key = self.cache.make_llm_key(user_query, difficulty)
                    await self.cache.set(
                        cache_key,
                        {
                            "guide_data": result,
                            "provider_used": provider_name,
                            "generation_time": generation_time
                        },
                        ttl=self.cache.TTL_LLM_RESPONSE
                    )

                return result, provider_name, generation_time
        except Exception as e:
            logger.warning(
                "llm_provider_failed",
                provider="primary",
                operation="generate_guide",
                error=str(e),
                error_type=type(e).__name__
            )

        # Fallback to secondary provider
        if self.fallback_provider:
            try:
                result = await self.fallback_provider.generate_guide(
                    user_query, difficulty, format_preference
                )
                generation_time = time.time() - start_time
                provider_name = getattr(self.fallback_provider, 'provider_name', 'fallback')

                logger.info(
                    "llm_request_completed",
                    operation="generate_guide",
                    provider=provider_name,
                    fallback=True,
                    latency_ms=round(generation_time * 1000, 2),
                    user_query=user_query[:100]  # Truncate for logging
                )

                # Cache the fallback result (TTL: 24 hours)
                if self.cache:
                    cache_key = self.cache.make_llm_key(user_query, difficulty)
                    await self.cache.set(
                        cache_key,
                        {
                            "guide_data": result,
                            "provider_used": provider_name,
                            "generation_time": generation_time
                        },
                        ttl=self.cache.TTL_LLM_RESPONSE
                    )

                return result, provider_name, generation_time
            except Exception as e:
                logger.error(
                    "llm_provider_failed",
                    provider="fallback",
                    operation="generate_guide",
                    error=str(e),
                    error_type=type(e).__name__
                )

        logger.error(
            "all_llm_providers_failed",
            operation="generate_guide",
            user_query=user_query[:100]
        )
        raise Exception("All LLM providers failed")

    async def generate_step_alternatives(
        self,
        original_goal: str,
        completed_steps: List[Dict[str, Any]],
        blocked_step: Dict[str, Any],
        problem: Dict[str, Any]
    ) -> tuple[Dict[str, Any], str, float]:
        """Generate alternative steps with fallback support.

        Returns:
            tuple: (alternatives_data, provider_used, generation_time)
        """
        start_time = time.time()

        logger.info(
            "llm_request_started",
            operation="generate_alternatives",
            original_goal=original_goal[:100],  # Truncate for logging
            blocked_step_title=blocked_step.get("title", "Unknown")
        )

        # Try primary provider first
        try:
            if self.primary_provider:
                result = await self.primary_provider.generate_step_alternatives(
                    original_goal, completed_steps, blocked_step, problem
                )
                generation_time = time.time() - start_time
                provider_name = getattr(self.primary_provider, 'provider_name', 'primary')

                logger.info(
                    "llm_request_completed",
                    operation="generate_alternatives",
                    provider=provider_name,
                    latency_ms=round(generation_time * 1000, 2),
                    alternatives_count=len(result.get("alternative_steps", []))
                )

                return result, provider_name, generation_time
        except Exception as e:
            logger.warning(
                "llm_provider_failed",
                provider="primary",
                operation="generate_alternatives",
                error=str(e),
                error_type=type(e).__name__
            )

        # Fallback to secondary provider
        if self.fallback_provider:
            try:
                result = await self.fallback_provider.generate_step_alternatives(
                    original_goal, completed_steps, blocked_step, problem
                )
                generation_time = time.time() - start_time
                provider_name = getattr(self.fallback_provider, 'provider_name', 'fallback')

                logger.info(
                    "llm_request_completed",
                    operation="generate_alternatives",
                    provider=provider_name,
                    fallback=True,
                    latency_ms=round(generation_time * 1000, 2),
                    alternatives_count=len(result.get("alternative_steps", []))
                )

                return result, provider_name, generation_time
            except Exception as e:
                logger.error(
                    "llm_provider_failed",
                    provider="fallback",
                    operation="generate_alternatives",
                    error=str(e),
                    error_type=type(e).__name__
                )

        logger.error(
            "all_llm_providers_failed",
            operation="generate_alternatives",
            original_goal=original_goal[:100]
        )
        raise Exception("All LLM providers failed to generate alternatives")

    async def get_provider_status(self) -> Dict[str, bool]:
        """Get status of all providers."""
        status = {}
        for name, provider in self.providers.items():
            status[name] = await provider.is_available()
        return status


# Global service instance (will be initialized with cache in main.py)
llm_service = None


async def get_llm_service() -> LLMService:
    """Dependency to get LLM service."""
    global llm_service
    if llm_service is None:
        from ..core.cache import cache_manager
        llm_service = LLMService(cache=cache_manager)
        await llm_service.initialize()
    return llm_service


async def init_llm_service():
    """Initialize LLM service."""
    global llm_service
    if llm_service is None:
        from ..core.cache import cache_manager
        llm_service = LLMService(cache=cache_manager)
    await llm_service.initialize()


# Add missing import
import asyncio