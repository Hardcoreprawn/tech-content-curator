"""Specialized generators package.

This package contains highly specialized generators for specific content types
or sources that require custom handling beyond general or integrative approaches.
"""

from .self_hosted import SelfHostedGenerator

__all__ = ["SelfHostedGenerator"]
