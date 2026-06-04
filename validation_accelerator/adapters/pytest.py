"""
Pytest adapter for running unit tests.
"""

import os
import subprocess
import sys
import time
from typing import Dict, List, Any, Optional
from pathlib import Path
import json

from .base import BaseAdapter, ValidationTask, ValidationResult, ValidationResultStatus


class PytestAdapter(BaseAdapter):
    """Adapter for running Pytest tests."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("pytest", config)
        self._pytest_path = self._find_pytest()
    
    def _find_pytest(self) -> Optional[str]:
        """Find pytest executable in the system."""
        try:
            import pytest
            return pytest.__file__
        except ImportError:
            return None
        
        # Alternative: look in PATH
        for path in os.environ.get("PATH", "").split(os.pathsep):
            pytest_path = os.path.join(path, "pytest")
            if os.path.isfile(pytest_path):
                return pytest_path
        
        return None
    
    def validate(self, task: ValidationTask) -> ValidationResult:
        """
        Execute pytest tests for the given path.
        """
        start_time = time.time()
        
        try:
            # Build pytest command
            cmd = [sys.executable, "-m", "pytest"]
            
            # Add task-specific arguments
            if task.command:
                cmd.extend(task.command)
            
            # Add path to test
            if "path" in task.metadata:
                cmd.append(task.metadata["path"])
            else:
                cmd.append(".")  # Default to current directory
            
            # Add common options
            cmd.extend([
                "--tb=short",  # Short traceback format
                "--strict-markers",  # Strict marker matching
                "--disable-warnings",  # Reduce noise
            ])
            
            # Add timeout if specified
            timeout = task.timeout or self.config.get("timeout", 300)
            
            # Execute pytest
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=task.metadata.get("cwd", ".")
            )
            
            duration = time.time() - start_time
            
            # Parse results
            if result.returncode == 0:
                status = ValidationResultStatus.SUCCESS
                error = None
            else:
                status = ValidationResultStatus.FAILED
                error = result.stderr or result.stdout
            
            return ValidationResult(
                task_id=task.id,
                status=status,
                duration=duration,
                output=result.stdout,
                error=error,
                metadata={
                    "return_code": result.returncode,
                    "cmd": " ".join(cmd),
                    "timeout": timeout,
                    "pytest_version": self._get_pytest_version()
                }
            )
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ValidationResult(
                task_id=task.id,
                status=ValidationResultStatus.TIMEOUT,
                duration=duration,
                error=f"Pytest timed out after {timeout} seconds",
                metadata={"timeout": timeout}
            )
        except Exception as e:
            duration = time.time() - start_time
            return ValidationResult(
                task_id=task.id,
                status=ValidationResultStatus.FAILED,
                duration=duration,
                error=str(e),
                metadata={"exception": str(e)}
            )
    
    def _get_pytest_version(self) -> str:
        """Get pytest version."""
        try:
            import pytest
            return pytest.__version__
        except ImportError:
            return "unknown"
    
    def is_available(self) -> bool:
        """Check if pytest is available."""
        return self._pytest_path is not None
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate pytest configuration."""
        required_keys = []
        optional_keys = ["timeout", "extra_args", "markers"]
        
        for key in config:
            if key not in optional_keys:
                return False
        
        return True
    
    def get_supported_types(self) -> List[str]:
        """Get supported validation task types."""
        return ["pytest", "unit_tests", "tests"]


# Import time here to avoid circular import
import time