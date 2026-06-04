"""
ESLint adapter for running JavaScript/TypeScript linting.
"""

import os
import subprocess
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path

from .base import BaseAdapter, ValidationTask, ValidationResult, ValidationResultStatus


class ESLintAdapter(BaseAdapter):
    """Adapter for running ESLint."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("eslint", config)
        self._eslint_path = self._find_eslint()
    
    def _find_eslint(self) -> Optional[str]:
        """Find eslint executable in the system."""
        try:
            import eslint
            return eslint.__file__
        except ImportError:
            pass
        
        # Look in node_modules/.bin/eslint
        node_modules = self._find_node_modules()
        if node_modules:
            eslint_path = os.path.join(node_modules, "eslint")
            if os.path.isfile(eslint_path):
                return eslint_path
        
        # Look in PATH
        for path in os.environ.get("PATH", "").split(os.pathsep):
            eslint_path = os.path.join(path, "eslint")
            if os.path.isfile(eslint_path):
                return eslint_path
        
        return None
    
    def _find_node_modules(self) -> Optional[str]:
        """Find node_modules directory starting from current directory."""
        current_dir = Path.cwd()
        
        # Check current directory
        node_modules = current_dir / "node_modules" / ".bin"
        if node_modules.exists():
            return str(node_modules)
        
        # Check parent directories
        for parent in current_dir.parents:
            node_modules = parent / "node_modules" / ".bin"
            if node_modules.exists():
                return str(node_modules)
        
        return None
    
    def validate(self, task: ValidationTask) -> ValidationResult:
        """
        Execute ESLint on the given path.
        """
        start_time = time.time()
        
        try:
            if not self.is_available():
                raise RuntimeError("ESLint is not available")
            
            # Build eslint command
            cmd = [sys.executable, "-m", "eslint"]
            
            # Add task-specific arguments
            if task.command:
                cmd.extend(task.command)
            
            # Add path to lint
            if "path" in task.metadata:
                cmd.append(task.metadata["path"])
            else:
                cmd.append(".")  # Default to current directory
            
            # Add common options
            cmd.extend([
                "--no-color",  # No color output for parsing
                "--format=compact",  # Compact format
            ])
            
            # Add timeout if specified
            timeout = task.timeout or self.config.get("timeout", 60)
            
            # Execute eslint
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
            
            # Count errors if output is available
            error_count = 0
            if result.stdout:
                error_count = result.stdout.count("error")
            
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
                    "error_count": error_count,
                    "eslint_version": self._get_eslint_version()
                }
            )
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ValidationResult(
                task_id=task.id,
                status=ValidationResultStatus.TIMEOUT,
                duration=duration,
                error=f"ESLint timed out after {timeout} seconds",
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
    
    def _get_eslint_version(self) -> str:
        """Get eslint version."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "eslint", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"
    
    def is_available(self) -> bool:
        """Check if eslint is available."""
        return self._eslint_path is not None
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate ESLint configuration."""
        required_keys = []
        optional_keys = ["timeout", "config_file", "extra_args", "extensions"]
        
        for key in config:
            if key not in optional_keys:
                return False
        
        return True
    
    def get_supported_types(self) -> List[str]:
        """Get supported validation task types."""
        return ["eslint", "lint", "javascript", "typescript", "js", "ts"]