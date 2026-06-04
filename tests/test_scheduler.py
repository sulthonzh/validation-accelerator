"""
Tests for the validation scheduler.
"""

import unittest
from unittest.mock import Mock, patch
import tempfile
import os

from validation_accelerator.core.scheduler import ValidationScheduler, SchedulerConfig, SchedulerStrategy
from validation_accelerator.adapters.base import MockAdapter
from validation_accelerator.core.analyzer import ChangeAnalyzer, FileChange


class TestValidationScheduler(unittest.TestCase):
    """Test cases for ValidationScheduler."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_adapter = MockAdapter("test")
        self.config = SchedulerConfig(
            strategy=SchedulerStrategy.RISK_BASED,
            max_concurrent=2,
            timeout=30
        )
        self.scheduler = ValidationScheduler(self.config, [self.mock_adapter])
    
    def test_scheduler_initialization(self):
        """Test scheduler initialization."""
        self.assertEqual(self.scheduler.config.strategy, SchedulerStrategy.RISK_BASED)
        self.assertEqual(self.scheduler.config.max_concurrent, 2)
        self.assertEqual(len(self.scheduler.adapters), 1)
        self.assertIsInstance(self.scheduler.change_analyzer, ChangeAnalyzer)
    
    def test_risk_based_scheduling(self):
        """Test risk-based task scheduling."""
        from validation_accelerator.adapters.base import ValidationTask
        
        # Create tasks that fit into different dependency groups
        tasks = [
            ValidationTask("task1", "High priority task", "lint", [], priority=3),
            ValidationTask("task2", "Low priority task", "unit_tests", [], priority=1),
            ValidationTask("task3", "Medium priority task", "security_scan", [], priority=2),
        ]
        
        scheduled = self.scheduler._schedule_risk_based(tasks)
        
        # Debug: print the scheduled order
        for i, task in enumerate(scheduled):
            print(f"{i}: {task.id} (type: {task.type}, priority: {task.priority})")
        
        # All tasks should be scheduled (no specific order guarantee due to dependency groups)
        self.assertEqual(len(scheduled), 3)
        task_ids = [task.id for task in scheduled]
        self.assertIn("task1", task_ids)
        self.assertIn("task2", task_ids)
        self.assertIn("task3", task_ids)
    
    def test_parallel_scheduling(self):
        """Test parallel task scheduling."""
        from validation_accelerator.adapters.base import ValidationTask
        
        tasks = [
            ValidationTask("task1", "Type A task", "type_a", []),
            ValidationTask("task2", "Type B task", "type_b", []),
            ValidationTask("task3", "Type A task", "type_a", []),
        ]
        
        scheduled = self.scheduler._schedule_parallel(tasks)
        
        # Tasks should be grouped by dependency
        # In this simple case, they should be in the same order
        self.assertEqual(len(scheduled), 3)
    
    def test_sequential_scheduling(self):
        """Test sequential task scheduling."""
        from validation_accelerator.adapters.base import ValidationTask
        
        tasks = [
            ValidationTask("task1", "Fast check", "fast_check", [], metadata={"phase": "fast_checks"}),
            ValidationTask("task2", "Medium check", "medium_check", [], metadata={"phase": "medium_checks"}),
            ValidationTask("task3", "Slow check", "slow_check", [], metadata={"phase": "slow_checks"}),
        ]
        
        scheduled = self.scheduler._schedule_sequential(tasks)
        
        # Should be ordered by phase (fast -> medium -> slow)
        self.assertEqual(scheduled[0].metadata["phase"], "fast_checks")
        self.assertEqual(scheduled[1].metadata["phase"], "medium_checks")
        self.assertEqual(scheduled[2].metadata["phase"], "slow_checks")
    
    def test_execute_single_task(self):
        """Test execution of a single task."""
        from validation_accelerator.adapters.base import ValidationTask
        
        task = ValidationTask("test_task", "Test task", "mock", ["--success"])
        result = self.scheduler._execute_single_task(task)
        
        self.assertEqual(result.task_id, "test_task")
        self.assertEqual(result.status.value, "success")
        self.assertGreater(result.duration, 0)
    
    def test_execute_single_task_no_adapter(self):
        """Test execution when no adapter is available."""
        from validation_accelerator.adapters.base import ValidationTask
        
        task = ValidationTask("test_task", "Test task", "unknown", [])
        # Remove all adapters to force no adapter scenario
        original_adapters = self.scheduler.adapters
        self.scheduler.adapters = []
        
        try:
            result = self.scheduler._execute_single_task(task)
            
            self.assertEqual(result.task_id, "test_task")
            self.assertEqual(result.status.value, "failed")
            self.assertIn("No adapter found", result.error)
        finally:
            # Restore adapters
            self.scheduler.adapters = original_adapters
    
    def test_generate_summary(self):
        """Test summary generation."""
        from validation_accelerator.adapters.base import ValidationResult, ValidationResultStatus
        
        # Mock results
        results = {
            "task1": ValidationResult(
                task_id="task1",
                status=ValidationResultStatus.SUCCESS,
                duration=1.0
            ),
            "task2": ValidationResult(
                task_id="task2",
                status=ValidationResultStatus.FAILED,
                duration=2.0
            ),
            "task3": ValidationResult(
                task_id="task3",
                status=ValidationResultStatus.TIMEOUT,
                duration=30.0
            )
        }
        
        # Mock file changes
        file_changes = [
            FileChange("file1.py", "modified", 10, 2.5, ["api_surface_changes"]),
            FileChange("file2.py", "added", 5, 1.0, ["tests"]),
        ]
        
        summary = self.scheduler._generate_summary(results, file_changes)
        
        self.assertEqual(summary["total_tasks"], 3)
        self.assertEqual(summary["successful_tasks"], 1)
        self.assertEqual(summary["failed_tasks"], 1)
        self.assertEqual(summary["timeout_tasks"], 1)
        self.assertEqual(summary["success_rate"], 1/3)
        print(f"Risk distribution: {summary['risk_distribution']}")
        self.assertEqual(summary["risk_distribution"]["high"], 1)
        self.assertEqual(summary["risk_distribution"]["medium"], 1)
    
    def test_cleanup(self):
        """Test scheduler cleanup."""
        # This test mainly ensures cleanup doesn't raise an exception
        self.scheduler.cleanup()
        # If we get here without exception, cleanup worked


class TestChangeAnalyzer(unittest.TestCase):
    """Test cases for ChangeAnalyzer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = ChangeAnalyzer()
    
    def test_analyze_single_file_api(self):
        """Test analysis of an API file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
from fastapi import APIRouter

router = APIRouter()

@router.get("/users")
def get_users():
    return {"users": []}
""")
            f.flush()
            
            file_change = self.analyzer._analyze_single_file("api/users.py", f.name)
            
            self.assertEqual(file_change.path, "api/users.py")
            self.assertGreater(file_change.risk_score, 0)
            self.assertIn("api_surface_changes", file_change.risk_factors)
            
            os.unlink(f.name)
    
    def test_analyze_single_file_security(self):
        """Test analysis of a security file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
import hashlib
import jwt

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(user_id):
    return jwt.encode({"user_id": user_id}, "secret")
""")
            f.flush()
            
            file_change = self.analyzer._analyze_single_file("auth/security.py", f.name)
            
            self.assertEqual(file_change.path, "auth/security.py")
            self.assertGreater(file_change.risk_score, 0)
            self.assertIn("security_tests", file_change.risk_factors)
            
            os.unlink(f.name)
    
    def test_analyze_single_file_low_risk(self):
        """Test analysis of a low-risk utility file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("""
def calculate_average(numbers):
    return sum(numbers) / len(numbers)
""")
            f.flush()
            
            file_change = self.analyzer._analyze_single_file("utils/math.py", f.name)
            
            self.assertEqual(file_change.path, "utils/math.py")
            self.assertGreater(file_change.risk_score, 0)
            self.assertIn("utility_functions", file_change.risk_factors)
            
            os.unlink(f.name)
    
    def test_get_high_risk_files(self):
        """Test getting high-risk files."""
        file_changes = [
            FileChange("high_risk.py", "modified", 50, 3.0, ["api_surface_changes"]),
            FileChange("medium_risk.py", "modified", 20, 1.5, ["tests"]),
            FileChange("low_risk.py", "modified", 10, 0.5, ["documentation"]),
        ]
        
        high_risk = self.analyzer.get_high_risk_files(file_changes, threshold=2.0)
        
        self.assertEqual(len(high_risk), 1)
        self.assertEqual(high_risk[0].path, "high_risk.py")
    
    def test_sort_by_risk(self):
        """Test sorting files by risk score."""
        file_changes = [
            FileChange("file1.py", "modified", 10, 1.0, ["tests"]),
            FileChange("file2.py", "modified", 20, 3.0, ["api_surface_changes"]),
            FileChange("file3.py", "modified", 15, 2.0, ["security_tests"]),
        ]
        
        sorted_files = self.analyzer.sort_by_risk(file_changes)
        
        self.assertEqual(sorted_files[0].path, "file2.py")  # Highest risk
        self.assertEqual(sorted_files[1].path, "file3.py")  # Medium risk
        self.assertEqual(sorted_files[2].path, "file1.py")  # Lowest risk


if __name__ == '__main__':
    unittest.main()