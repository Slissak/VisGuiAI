# LM Studio Integration Guide

This guide explains how to set up and use LM Studio with the Step Guide Backend API for local LLM inference.

## What is LM Studio?

LM Studio is a desktop application that allows you to run Large Language Models (LLMs) locally on your machine. It provides an OpenAI-compatible API server that can be used as a drop-in replacement for cloud-based LLM services.

## Setup Instructions

### 1. Install LM Studio

1. Download LM Studio from [lmstudio.ai](https://lmstudio.ai/)
2. Install and launch the application
3. Download a model (recommended: Llama 2 7B, CodeLlama, or Mistral 7B)

### 2. Start LM Studio Server

1. In LM Studio, go to the "Local Server" tab
2. Load your chosen model
3. Start the server (default: `http://localhost:1234`)
4. Note the model name shown in the server interface

### 3. Configure Backend

Set the following environment variables or update your `.env` file:

```env
# LM Studio Configuration
ENABLE_LM_STUDIO=true
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=your-model-name-here

# Optional: Disable cloud providers to force local-only
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
```

### 4. Model Recommendations

**For Guide Generation:**
- **Llama 2 7B Chat**: Good balance of speed and quality
- **CodeLlama 7B Instruct**: Excellent for technical guides
- **Mistral 7B Instruct**: Fast and efficient
- **Llama 3 8B**: Latest and most capable (if your hardware supports it)

**Hardware Requirements:**
- Minimum: 8GB RAM, 4GB VRAM
- Recommended: 16GB RAM, 6GB VRAM
- For larger models: 32GB RAM, 8GB+ VRAM

## Usage

Once configured, the backend will automatically:

1. **Prioritize LM Studio**: Local LLM gets first priority when available
2. **Fallback to Cloud**: If LM Studio is unavailable, falls back to OpenAI/Anthropic
3. **Error Handling**: Graceful degradation if local model fails

## API Behavior

### Provider Priority (when all are configured):
1. **LM Studio** (local) - Highest priority
2. **OpenAI** - Cloud fallback
3. **Anthropic** - Secondary cloud fallback
4. **Mock** - Development fallback

### Benefits of Local LLM:
- **Privacy**: No data sent to external servers
- **Cost**: No per-request charges
- **Speed**: Potentially faster for smaller models
- **Control**: Full control over model behavior and updates
- **Offline**: Works without internet connection

### Configuration Examples

#### Development (Local Only)
```env
ENABLE_LM_STUDIO=true
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=llama-2-7b-chat
```

#### Production (Hybrid)
```env
ENABLE_LM_STUDIO=true
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=mistral-7b-instruct
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
```

## Troubleshooting

### Common Issues:

1. **Connection Refused**
   - Ensure LM Studio server is running
   - Check the base URL matches (default: http://localhost:1234)
   - Verify firewall settings

2. **Model Not Found**
   - Check the model name in LM Studio matches `LM_STUDIO_MODEL`
   - Ensure the model is loaded in LM Studio

3. **Slow Performance**
   - Consider using a smaller model (7B instead of 13B+)
   - Check available RAM and VRAM
   - Close other resource-intensive applications

4. **Quality Issues**
   - Try different models optimized for instruction following
   - Adjust temperature settings in LM Studio
   - Ensure model is properly loaded (not just downloaded)

### Debugging

Enable debug mode to see detailed provider information:

```env
DEBUG=true
LOG_LEVEL=DEBUG
```

The backend will log which provider is being used for each request:
```
✅ LLM Service initialized with 3 providers
Primary provider: lm_studio
Fallback provider: openai
```

## Model Recommendations by Use Case

### Technical Guides
- **CodeLlama 7B Instruct**: Excellent for programming and technical content
- **DeepSeek Coder**: Specialized for code-related guides

### General Tutorials
- **Llama 2 7B Chat**: Well-rounded for general instructions
- **Mistral 7B Instruct**: Fast and efficient for step-by-step guides

### Advanced/Complex Guides
- **Llama 3 8B**: Most capable but requires more resources
- **Yi 9B**: Good balance of capability and efficiency

Remember to test your chosen model with representative queries to ensure it produces high-quality step-by-step guides in the expected JSON format.