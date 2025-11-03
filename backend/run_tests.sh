#!/bin/bash

# Test runner script for Step Guide Backend
# Sets up proper PYTHONPATH and runs tests

# Set PYTHONPATH to include project root for shared module
export PYTHONPATH="/Users/sivanlissak/Documents/VisGuiAI:$PYTHONPATH"

# Activate virtual environment
source venv/bin/activate

# Run tests with provided arguments
python -m pytest "$@"
