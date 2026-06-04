"""
Configuration loader for Validation Accelerator.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from ..core.scheduler import SchedulerStrategy, SchedulerConfig


@dataclass
class ValidationConfig:
    """Main configuration for Validation Accelerator."""
    scheduler: SchedulerConfig
    adapters: Dict[str, Dict[str, Any]]
    phases: Dict[str, list]
    excludes: list
    timeout: int
    working_directory: str
    
    @classmethod
    def default(cls) -> 'ValidationConfig':
        """Create default configuration."""
        return cls(
            scheduler=SchedulerConfig(
                strategy=SchedulerStrategy.RISK_BASED,
                max_concurrent=4,
                timeout=300,
                priority_factors={
                    "api_surface_changes": 3.0,
                    "security_tests": 3.0,
                    "public_interfaces": 2.5,
                    "database_changes": 2.0,
                    "ui_components": 1.5,
                    "utility_functions": 1.0,
                    "tests": 1.0,
                    "documentation": 0.5,
                },
                dependency_groups=[
                    ["lint", "security_scan"],
                    ["unit_tests"],
                    ["integration_tests"],
                    ["e2e_tests"],
                ],
                phase_timeout={
                    "fast_checks": 30,
                    "medium_checks": 300,
                    "slow_checks": 600,
                }
            ),
            adapters={
                "pytest": {
                    "enabled": True,
                    "timeout": 120,
                    "extra_args": ["-x", "--tb=short"],
                    "markers": ["unit", "integration", "e2e"]
                },
                "eslint": {
                    "enabled": True,
                    "timeout": 60,
                    "config_file": ".eslintrc",
                    "extra_args": ["--no-color", "--format=compact"],
                    "extensions": [".js", ".ts", ".jsx", ".tsx"]
                },
                "mock": {
                    "enabled": True,
                    "timeout": 10,
                    "simulate_timeout": False
                }
            },
            phases={
                "fast_checks": ["syntax_check", "import_validation", "type_checking"],
                "medium_checks": ["static_analysis", "unit_tests"],
                "slow_checks": ["integration_tests", "e2e_tests"]
            },
            excludes=["node_modules", ".git", "dist", "build", "__pycache__"],
            timeout=300,
            working_directory="."
        )


class ConfigLoader:
    """Load and validate configuration files."""
    
    def __init__(self):
        self.config_file_paths = [
            ".validation-accelerator.yaml",
            ".validation-accelerator.yml",
            "validation-accelerator.yaml",
            "validation-accelerator.yml",
            ".va-config.yaml",
            ".va-config.yml"
        ]
    
    def load_config(self, config_path: Optional[str] = None) -> ValidationConfig:
        """
        Load configuration from file or use defaults.
        
        Args:
            config_path: Optional path to configuration file
            
        Returns:
            ValidationConfig instance
        """
        if config_path:
            return self._load_from_file(config_path)
        else:
            return self._load_from_default_locations()
    
    def _load_from_file(self, config_path: str) -> ValidationConfig:
        """
        Load configuration from a specific file.
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                config_data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in configuration file: {e}")
        
        return self._parse_config(config_data)
    
    def _load_from_default_locations(self) -> ValidationConfig:
        """
        Load configuration from default locations.
        """
        # Check current directory
        for config_path in self.config_file_paths:
            if os.path.exists(config_path):
                return self._load_from_file(config_path)
        
        # Check parent directories
        current_dir = Path.cwd()
        for parent in current_dir.parents:
            for config_path in self.config_file_paths:
                full_path = parent / config_path
                if full_path.exists():
                    return self._load_from_file(str(full_path))
        
        # No config found, use defaults
        return ValidationConfig.default()
    
    def _parse_config(self, config_data: Dict[str, Any]) -> ValidationConfig:
        """
        Parse configuration data into ValidationConfig.
        """
        # Parse scheduler configuration
        scheduler_config = self._parse_scheduler_config(config_data.get('strategies', {}))
        
        # Parse adapters configuration
        adapters_config = config_data.get('adapters', {})
        
        # Parse phases configuration
        phases_config = config_data.get('phases', {})
        
        # Parse excludes
        excludes = config_data.get('excludes', ValidationConfig.default().excludes)
        
        # Parse timeout
        timeout = config_data.get('timeout', ValidationConfig.default().timeout)
        
        # Parse working directory
        working_directory = config_data.get('working_directory', '.')
        
        return ValidationConfig(
            scheduler=scheduler_config,
            adapters=adapters_config,
            phases=phases_config,
            excludes=excludes,
            timeout=timeout,
            working_directory=working_directory
        )
    
    def _parse_scheduler_config(self, strategies_config: Dict[str, Any]) -> SchedulerConfig:
        """
        Parse scheduler configuration.
        """
        # Get strategy type
        strategy_name = strategies_config.get('strategy', 'risk_based')
        try:
            strategy = SchedulerStrategy(strategy_name)
        except ValueError:
            strategy = SchedulerStrategy.RISK_BASED
        
        # Parse max concurrent
        max_concurrent = strategies_config.get('max_concurrent', 4)
        
        # Parse timeout
        timeout = strategies_config.get('timeout', 300)
        
        # Parse priority factors
        priority_factors = strategies_config.get('priority_factors', 
                                              ValidationConfig.default().scheduler.priority_factors)
        
        # Parse dependency groups
        dependency_groups = strategies_config.get('dependency_groups', 
                                               ValidationConfig.default().scheduler.dependency_groups)
        
        # Parse phase timeout
        phase_timeout = strategies_config.get('phase_timeout', 
                                            ValidationConfig.default().scheduler.phase_timeout)
        
        return SchedulerConfig(
            strategy=strategy,
            max_concurrent=max_concurrent,
            timeout=timeout,
            priority_factors=priority_factors,
            dependency_groups=dependency_groups,
            phase_timeout=phase_timeout
        )
    
    def validate_config(self, config: ValidationConfig) -> bool:
        """
        Validate configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Validate scheduler configuration
            if not isinstance(config.scheduler.max_concurrent, int) or config.scheduler.max_concurrent <= 0:
                return False
            
            if not isinstance(config.scheduler.timeout, int) or config.scheduler.timeout <= 0:
                return False
            
            # Validate adapter configurations
            for adapter_name, adapter_config in config.adapters.items():
                if not isinstance(adapter_config, dict):
                    return False
                
                if 'enabled' in adapter_config and not isinstance(adapter_config['enabled'], bool):
                    return False
                
                if 'timeout' in adapter_config and not isinstance(adapter_config['timeout'], (int, type(None))):
                    return False
            
            # Validate phases
            if not isinstance(config.phases, dict):
                return False
            
            for phase_name, phase_tasks in config.phases.items():
                if not isinstance(phase_tasks, list):
                    return False
            
            # Validate excludes
            if not isinstance(config.excludes, list):
                return False
            
            # Validate working directory
            if not isinstance(config.working_directory, str):
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_config_schema(self) -> Dict[str, Any]:
        """
        Get the configuration schema for validation.
        
        Returns:
            JSON schema for configuration
        """
        return {
            "type": "object",
            "properties": {
                "strategies": {
                    "type": "object",
                    "properties": {
                        "strategy": {
                            "type": "string",
                            "enum": ["risk_based", "parallel", "sequential", "adaptive"],
                            "default": "risk_based"
                        },
                        "max_concurrent": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 16,
                            "default": 4
                        },
                        "timeout": {
                            "type": "integer",
                            "minimum": 1,
                            "default": 300
                        },
                        "priority_factors": {
                            "type": "object",
                            "additionalProperties": {"type": "number"}
                        },
                        "dependency_groups": {
                            "type": "array",
                            "items": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "phase_timeout": {
                            "type": "object",
                            "additionalProperties": {"type": "integer"}
                        }
                    }
                },
                "adapters": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "enabled": {"type": "boolean"},
                            "timeout": {"type": "integer"},
                            "extra_args": {"type": "array", "items": {"type": "string"}},
                            "config_file": {"type": "string"}
                        }
                    }
                },
                "phases": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "excludes": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "timeout": {"type": "integer"},
                "working_directory": {"type": "string"}
            }
        }