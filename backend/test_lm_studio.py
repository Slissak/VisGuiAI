#!/usr/bin/env python3
"""
Simple test script to verify LM Studio integration.

Usage:
    python test_lm_studio.py

Requirements:
    1. LM Studio running on http://localhost:1234
    2. A model loaded in LM Studio
    3. Python dependencies installed
"""

import asyncio
import json
from src.services.llm_service import LMStudioProvider


async def test_lm_studio():
    """Test LM Studio provider connectivity and guide generation."""

    print("🧪 Testing LM Studio Integration...")

    # Initialize provider with default settings
    provider = LMStudioProvider(
        base_url="http://localhost:1234/v1",
        model="local-model"  # This should match your model name in LM Studio
    )

    # Test availability
    print("📡 Checking LM Studio availability...")
    is_available = await provider.is_available()

    if not is_available:
        print("❌ LM Studio is not available. Please ensure:")
        print("   1. LM Studio is running")
        print("   2. A model is loaded")
        print("   3. Server is started on http://localhost:1234")
        return False

    print("✅ LM Studio is available!")

    # Test guide generation
    print("🤖 Testing guide generation...")

    try:
        result = await provider.generate_guide(
            user_query="How to make a peanut butter sandwich",
            difficulty="beginner",
            format_preference="detailed"
        )

        print("✅ Guide generation successful!")
        print(f"📋 Generated guide: {result['guide']['title']}")
        print(f"📊 Number of steps: {len(result['guide']['steps'])}")
        print(f"⏱️  Estimated duration: {result['guide']['estimated_duration_minutes']} minutes")

        # Pretty print the first step as an example
        if result['guide']['steps']:
            first_step = result['guide']['steps'][0]
            print(f"\n📝 First step example:")
            print(f"   Title: {first_step['title']}")
            print(f"   Description: {first_step['description'][:100]}...")

        return True

    except Exception as e:
        print(f"❌ Guide generation failed: {e}")
        return False


async def test_full_llm_service():
    """Test the complete LLM service with LM Studio integration."""

    print("\n🔧 Testing Full LLM Service...")

    from src.services.llm_service import LLMService

    # Initialize service
    llm_service = LLMService()
    await llm_service.initialize()

    # Check provider status
    print("📊 Provider Status:")
    status = await llm_service.get_provider_status()
    for provider, available in status.items():
        status_emoji = "✅" if available else "❌"
        print(f"   {status_emoji} {provider}: {'Available' if available else 'Not Available'}")

    # Test guide generation through service
    print("\n🎯 Testing guide generation through LLM service...")

    try:
        guide_data, provider_used, generation_time = await llm_service.generate_guide(
            user_query="How to setup a new Git repository",
            difficulty="intermediate"
        )

        print(f"✅ Service generation successful!")
        print(f"🏷️  Provider used: {provider_used}")
        print(f"⏱️  Generation time: {generation_time:.2f} seconds")
        print(f"📋 Guide title: {guide_data['guide']['title']}")

        return True

    except Exception as e:
        print(f"❌ Service generation failed: {e}")
        return False


if __name__ == "__main__":
    async def main():
        print("🚀 LM Studio Integration Test Suite\n")

        # Test direct provider
        provider_success = await test_lm_studio()

        # Test full service
        service_success = await test_full_llm_service()

        print("\n📈 Test Results:")
        print(f"   Direct Provider: {'✅ PASS' if provider_success else '❌ FAIL'}")
        print(f"   Full Service: {'✅ PASS' if service_success else '❌ FAIL'}")

        if provider_success and service_success:
            print("\n🎉 All tests passed! LM Studio integration is working correctly.")
        else:
            print("\n⚠️  Some tests failed. Check the error messages above.")
            print("\nTroubleshooting tips:")
            print("1. Ensure LM Studio is running with a loaded model")
            print("2. Check that the server is accessible at http://localhost:1234")
            print("3. Verify your model name matches the configuration")

    # Run the test
    asyncio.run(main())