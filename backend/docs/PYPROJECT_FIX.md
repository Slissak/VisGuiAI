# pyproject.toml Package Configuration Fix

## Problem

When attempting to install the package in editable mode with `pip install -e .[dev]`, the following error occurred:

```
ValueError: Unable to determine which files to ship inside the wheel using the following heuristics
The most likely cause of this is that there is no directory that matches the name of your project (step_guide_backend).
```

## Root Cause

The `pyproject.toml` file was missing the `[tool.hatch.build.targets.wheel]` section, which is required by Hatchling (the build backend) to identify which directories contain the Python packages to include in the distribution.

Hatchling uses heuristics to auto-detect packages, but in this case:
- The project name in `pyproject.toml` is `step-guide-backend` (with hyphens)
- The source code is located in the `src/` directory (not a directory matching the project name)
- There is no top-level directory named `step_guide_backend` (the normalized Python package name)

Without explicit configuration, Hatchling couldn't determine what to include in the wheel.

## Solution

Added the following section to `pyproject.toml` immediately after the `[build-system]` section:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src"]
```

This explicitly tells Hatchling to include all packages found in the `src/` directory when building the wheel.

## Package Structure

The backend follows a src-layout structure:

```
backend/
├── pyproject.toml
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── guides.py
│   │   ├── instruction_guides.py
│   │   ├── progress.py
│   │   ├── sessions.py
│   │   └── steps.py
│   ├── auth/
│   │   ├── __init__.py
│   │   └── middleware.py
│   ├── cli/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   └── redis.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py
│   ├── services/
│   │   ├── guide_service.py
│   │   ├── step_service.py
│   │   └── ...
│   └── utils/
│       ├── __init__.py
│       └── sorting.py
└── tests/
```

## Benefits of src-layout

The src-layout pattern (placing code in a `src/` directory) is a Python packaging best practice because:

1. **Import Testing**: Ensures you're testing the installed package, not the local directory
2. **Namespace Clarity**: Prevents accidental imports from the development directory
3. **Build Verification**: Forces proper package configuration to work correctly

## Verification

After this fix, the package can be installed in editable mode:

```bash
# Create/activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e .[dev]
```

The installation should now succeed, and all modules in `src/` will be importable:

```python
from src.core.config import settings
from src.api.guides import router
from src.services.guide_service import GuideService
# etc.
```

## Related Documentation

- [Hatchling Build Configuration](https://hatch.pypa.io/latest/config/build/)
- [Python Packaging User Guide - src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [PEP 517 - Build System Interface](https://peps.python.org/pep-0517/)

## Date

Fixed: October 16, 2025
