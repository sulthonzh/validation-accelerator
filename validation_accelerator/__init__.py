"""
Validation Accelerator - Optimize validation throughput for AI-generated code.

This package provides tools for smart parallelization and risk-based prioritization
of validation tasks to address the AI code validation bottleneck.
"""

__version__ = "0.1.0"
__author__ = "Sulthonzh"

from .core.scheduler import ValidationScheduler
from .core.analyzer import ChangeAnalyzer
from .config.loader import ConfigLoader
from .adapters.base import BaseAdapter

__all__ = [
    "ValidationScheduler",
    "ChangeAnalyzer", 
    "ConfigLoader",
    "BaseAdapter",
]