"""
Base adapter class for validation tools.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time


class ValidationResultStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class ValidationResult:
    """Result of a validation task execution."""
    task_id: str
    status: ValidationResultStatus
    duration: float
    output: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ValidationTask:
    """A validation task to be executed."""
    id: str
    name: str
    type: str
    command: List[str]
    dependencies: List[str] = None
    timeout: Optional[int] = None
    priority: int = 1
    risk_level: str = "medium"
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class BaseAdapter(ABC):
    """Base class for validation tool adapters."""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
    
    @abstractmethod
    def validate(self, task: ValidationTask) -> ValidationResult:
        """
        Execute a validation task and return the result.
        
        Args:
            task: The validation task to execute
            
        Returns:
            ValidationResult containing execution details
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the validation tool is available/installed.
        
        Returns:
            True if the tool is available, False otherwise
        """
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate the configuration for this adapter.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if configuration is valid, False otherwise
        """
        pass
    
    def can_execute(self, task: ValidationTask) -> bool:
        """
        Check if this adapter can execute the given task.
        
        Args:
            task: The task to check
            
        Returns:
            True if this adapter can execute the task, False otherwise
        """
        return task.type in self.get_supported_types()
    
    @abstractmethod
    def get_supported_types(self) -> List[str]:
        """
        Get list of validation task types this adapter supports.
        
        Returns:
            List of supported validation task types
        """
        pass


class MockAdapter(BaseAdapter):
    """Mock adapter for testing and demonstration purposes."""
    
    def __init__(self, name: str = "mock", config: Dict[str, Any] = None):
        super().__init__(name, config)
        self._available = True
    
    def validate(self, task: ValidationTask) -> ValidationResult:
        """Mock validation that simulates different outcomes."""
        time.sleep(0.1)  # Simulate some work
        
        # Simulate different outcomes based on task name
        if "fail" in task.name.lower():
            return ValidationResult(
                task_id=task.id,
                status=ValidationResultStatus.FAILED,
                duration=0.1,
                error="Mock validation failed",
                metadata={"mock": True}
            )
        elif "timeout" in task.name.lower() and self.config.get("simulate_timeout", False):
            time.sleep(2)  # Simulate timeout
            return ValidationResult(
                task_id=task.id,
                status=ValidationResultStatus.TIMEOUT,
                duration=2.0,
                error="Mock validation timed out",
                metadata={"mock": True}
            )
        else:
            return ValidationResult(
                task_id=task.id,
                status=ValidationResultStatus.SUCCESS,
                duration=0.1,
                output=f"Mock validation passed for {task.name}",
                metadata={"mock": True}
            )
    
    def is_available(self) -> bool:
        return self._available
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        return True
    
    def get_supported_types(self) -> List[str]:
        return ["mock", "test", "lint"]