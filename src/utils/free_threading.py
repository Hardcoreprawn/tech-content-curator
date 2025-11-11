"""Free-threading detection utilities."""

import os
import sys


def supports_free_threading() -> bool:
    """Check if free-threading is available and enabled.

    Returns:
        True if Python 3.14+ with GIL disabled (PYTHON_GIL=0)
    """
    # Check if GIL control is available
    if not hasattr(sys, "_is_gil_enabled"):
        return False

    # Check if PYTHON_GIL=0 is set and GIL is actually disabled
    return os.getenv("PYTHON_GIL") == "0" and not sys._is_gil_enabled()
