"""
Tests for the configuration loader.
"""

import unittest
import tempfile
import os
import yaml

from validation_accelerator.config.loader import ConfigLoader, ValidationConfig
from validation_accelerator.core.scheduler import SchedulerStrategy


class TestConfigLoader(unittest.TestCase):
    """Test cases for ConfigLoader."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.loader = ConfigLoader()
    
    def test_default_config(self):
        """Test default configuration creation."""
        config = ValidationConfig.default()
        
        self.assertEqual(config.scheduler.strategy, SchedulerStrategy.RISK_BASED)
        self.assertEqual(config.scheduler.max_concurrent, 4)
        self.assertEqual(config.scheduler.timeout, 300)
        self.assertIsInstance(config.adapters, dict)
        self.assertIsInstance(config.phases, dict)
        self.assertIsInstance(config.excludes, list)
    
    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        config_data = {
            "strategies": {
                "strategy": "parallel",
                "max_concurrent": 6,
                "timeout": 600
            },
            "adapters": {
                "pytest": {
                    "enabled": True,
                    "timeout": 180
                }
            },
            "phases": {
                "fast_checks": ["syntax_check"],
                "medium_checks": ["unit_tests"]
            },
            "excludes": ["node_modules", ".git"],
            "timeout": 400
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()
            
            config = self.loader._load_from_file(f.name)
            
            self.assertEqual(config.scheduler.strategy, SchedulerStrategy.PARALLEL)
            self.assertEqual(config.scheduler.max_concurrent, 6)
            self.assertEqual(config.scheduler.timeout, 600)
            self.assertEqual(config.adapters["pytest"]["timeout"], 180)
            self.assertEqual(config.excludes, ["node_modules", ".git"])
            self.assertEqual(config.timeout, 400)
            
            os.unlink(f.name)
    
    def test_load_invalid_config(self):
        """Test loading an invalid configuration file."""
        invalid_config = {
            "strategies": {
                "strategy": "invalid_strategy",
                "max_concurrent": "not_a_number"
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(invalid_config, f)
            f.flush()
            
            # Should handle invalid strategy gracefully
            config = self.loader._load_from_file(f.name)
            self.assertEqual(config.scheduler.strategy, SchedulerStrategy.RISK_BASED)  # Default
            
            os.unlink(f.name)
    
    def test_validate_config(self):
        """Test configuration validation."""
        # Valid config
        valid_config = ValidationConfig.default()
        self.assertTrue(self.loader.validate_config(valid_config))
        
        # Invalid config
        invalid_config = ValidationConfig(
            scheduler=None,
            adapters="not_a_dict",
            phases="not_a_dict",
            excludes="not_a_list",
            timeout=300,
            working_directory="."
        )
        self.assertFalse(self.loader.validate_config(invalid_config))
    
    def test_get_config_schema(self):
        """Test getting configuration schema."""
        schema = self.loader.get_config_schema()
        
        self.assertIsInstance(schema, dict)
        self.assertIn("type", schema)
        self.assertEqual(schema["type"], "object")
        self.assertIn("properties", schema)
        self.assertIn("strategies", schema["properties"])
        self.assertIn("adapters", schema["properties"])
        self.assertIn("phases", schema["properties"])


class TestSchedulerConfig(unittest.TestCase):
    """Test cases for SchedulerConfig."""
    
    def test_scheduler_config_creation(self):
        """Test creating a scheduler configuration."""
        config = ValidationConfig.default().scheduler
        
        self.assertEqual(config.strategy, SchedulerStrategy.RISK_BASED)
        self.assertEqual(config.max_concurrent, 4)
        self.assertEqual(config.timeout, 300)
        self.assertIsInstance(config.priority_factors, dict)
        self.assertIsInstance(config.dependency_groups, list)
        self.assertIsInstance(config.phase_timeout, dict)
    
    def test_scheduler_config_custom(self):
        """Test creating a custom scheduler configuration."""
        from validation_accelerator.core.scheduler import SchedulerConfig, SchedulerStrategy
        
        config = SchedulerConfig(
            strategy=SchedulerStrategy.PARALLEL,
            max_concurrent=8,
            timeout=600,
            priority_factors={"critical": 4.0, "high": 3.0},
            dependency_groups=[["lint"], ["tests"]],
            phase_timeout={"fast": 10, "slow": 1200}
        )
        
        self.assertEqual(config.strategy, SchedulerStrategy.PARALLEL)
        self.assertEqual(config.max_concurrent, 8)
        self.assertEqual(config.timeout, 600)
        self.assertEqual(config.priority_factors["critical"], 4.0)
        self.assertEqual(len(config.dependency_groups), 2)
        self.assertEqual(config.phase_timeout["fast"], 10)


if __name__ == '__main__':
    unittest.main()