"""
Root conftest for AI-CFD Knowledge Harness tests.

Sets up Python path for api_server imports.
"""

import sys
from pathlib import Path

# Add project root to path for api_server imports
_project_root = Path(__file__).parent.parent.resolve()
_str_root = str(_project_root)
if _str_root not in sys.path:
    sys.path.insert(0, _str_root)
