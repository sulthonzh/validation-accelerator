"""
Validation scheduler for smart parallelization and risk-based prioritization.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import PriorityQueue

from .analyzer import ChangeAnalyzer, FileChange, RiskLevel
from ..adapters.base import BaseAdapter, ValidationTask, ValidationResult, ValidationResultStatus


class SchedulerStrategy(Enum):
    RISK_BASED = "risk_based"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    ADAPTIVE = "adaptive"


@dataclass
class SchedulerConfig:
    """Configuration for the validation scheduler."""
    strategy: SchedulerStrategy
    max_concurrent: int = 4
    timeout: int = 300
    priority_factors: Dict[str, float] = None
    dependency_groups: List[List[str]] = None
    phase_timeout: Dict[str, int] = None
    
    def __post_init__(self):
        if self.priority_factors is None:
            self.priority_factors = {
                "critical": 3.0,
                "high": 2.5,
                "medium": 1.5,
                "low": 1.0,
            }
        
        if self.dependency_groups is None:
            self.dependency_groups = [
                ["lint", "security_scan"],
                ["unit_tests"],
                ["integration_tests"],
                ["e2e_tests"],
            ]
        
        if self.phase_timeout is None:
            self.phase_timeout = {
                "fast_checks": 30,
                "medium_checks": 300,
                "slow_checks": 600,
            }


class ValidationScheduler:
    """Main scheduler for validation tasks."""
    
    def __init__(self, config: SchedulerConfig, adapters: List[BaseAdapter]):
        self.config = config
        self.adapters = adapters
        self.change_analyzer = ChangeAnalyzer()
        self.execution_history = []
        self.lock = threading.Lock()
        
        # Task queue with priority
        self.task_queue = PriorityQueue()
        
        # Thread pool for parallel execution
        self.executor = ThreadPoolExecutor(max_workers=config.max_concurrent)
        
        # Dependency graph
        self.dependency_graph = {}
        
        # Progress tracking
        self.completed_tasks = 0
        self.total_tasks = 0
        self.start_time = None
        
    async def schedule_validation(self, 
                                changed_files: List[str],
                                base_path: str = ".") -> Dict[str, Any]:
        """
        Main entry point for validation scheduling.
        
        Args:
            changed_files: List of changed file paths
            base_path: Base directory path
            
        Returns:
            Dictionary with validation results and metrics
        """
        self.start_time = time.time()
        
        # 1. Analyze changes to identify risk levels
        file_changes = self.change_analyzer.analyze_changes(changed_files, base_path)
        
        # 2. Create validation tasks based on risk analysis
        validation_tasks = self._create_validation_tasks(file_changes)
        
        # 3. Schedule tasks based on strategy
        scheduled_tasks = self._schedule_tasks(validation_tasks)
        
        # 4. Execute tasks
        results = await self._execute_tasks(scheduled_tasks)
        
        # 5. Generate summary
        summary = self._generate_summary(results, file_changes)
        
        return {
            "results": results,
            "summary": summary,
            "metrics": self._calculate_metrics(),
            "file_changes": file_changes,
        }
    
    def _create_validation_tasks(self, file_changes: List[FileChange]) -> List[ValidationTask]:
        """
        Create validation tasks based on file changes and risk analysis.
        """
        tasks = []
        
        # Fast checks - always run these first
        fast_tasks = self._create_phase_tasks("fast_checks", file_changes)
        tasks.extend(fast_tasks)
        
        # Medium checks - run after fast checks
        medium_tasks = self._create_phase_tasks("medium_checks", file_changes)
        tasks.extend(medium_tasks)
        
        # Slow checks - can run in background
        slow_tasks = self._create_phase_tasks("slow_checks", file_changes)
        tasks.extend(slow_tasks)
        
        self.total_tasks = len(tasks)
        return tasks
    
    def _create_phase_tasks(self, phase: str, file_changes: List[FileChange]) -> List[ValidationTask]:
        """
        Create validation tasks for a specific phase.
        """
        tasks = []
        
        if phase == "fast_checks":
            # Syntax check, import validation, type checking
            for file_change in file_changes:
                # Syntax check
                tasks.append(ValidationTask(
                    id=f"syntax_{file_change.path.replace('/', '_').replace('.', '_')}",
                    name=f"Syntax check: {file_change.path}",
                    type="syntax_check",
                    command=[],
                    dependencies=[],
                    timeout=10,
                    priority=3,
                    risk_level="high" if file_change.risk_score > 2.0 else "medium",
                    metadata={"file_path": file_change.path, "phase": phase}
                ))
                
                # Import validation
                if file_change.path.endswith(('.py', '.js', '.ts')):
                    tasks.append(ValidationTask(
                        id=f"import_{file_change.path.replace('/', '_').replace('.', '_')}",
                        name=f"Import validation: {file_change.path}",
                        type="import_validation",
                        command=[],
                        dependencies=[],
                        timeout=15,
                        priority=3,
                        risk_level="medium",
                        metadata={"file_path": file_change.path, "phase": phase}
                    ))
        
        elif phase == "medium_checks":
            # Static analysis, unit tests
            for file_change in file_changes:
                # Static analysis
                if file_change.path.endswith(('.py', '.js', '.ts')):
                    tasks.append(ValidationTask(
                        id=f"static_{file_change.path.replace('/', '_').replace('.', '_')}",
                        name=f"Static analysis: {file_change.path}",
                        type="static_analysis",
                        command=["--quiet"],
                        dependencies=[],
                        timeout=60,
                        priority=2,
                        risk_level="high",
                        metadata={"file_path": file_change.path, "phase": phase}
                    ))
                
                # Unit tests for changed files
                if file_change.path.endswith(('_test.py', '.test.js', '.test.ts', '.spec.js', '.spec.ts')):
                    tasks.append(ValidationTask(
                        id=f"unit_{file_change.path.replace('/', '_').replace('.', '_')}",
                        name=f"Unit tests: {file_change.path}",
                        type="unit_tests",
                        command=["-x", "--tb=short"],
                        dependencies=[],
                        timeout=120,
                        priority=2,
                        risk_level="medium",
                        metadata={"file_path": file_change.path, "phase": phase}
                    ))
        
        elif phase == "slow_checks":
            # Integration tests, e2e tests
            for file_change in file_changes:
                # Integration tests
                if "integration" in file_change.path.lower():
                    tasks.append(ValidationTask(
                        id=f"integration_{file_change.path.replace('/', '_').replace('.', '_')}",
                        name=f"Integration tests: {file_change.path}",
                        type="integration_tests",
                        command=["--tb=short"],
                        dependencies=[],
                        timeout=300,
                        priority=1,
                        risk_level="low",
                        metadata={"file_path": file_change.path, "phase": phase}
                    ))
                
                # E2E tests
                if "e2e" in file_change.path.lower() or "end_to_end" in file_change.path.lower():
                    tasks.append(ValidationTask(
                        id=f"e2e_{file_change.path.replace('/', '_').replace('.', '_')}",
                        name=f"E2E tests: {file_change.path}",
                        type="e2e_tests",
                        command=["--headless"],
                        dependencies=[],
                        timeout=600,
                        priority=1,
                        risk_level="low",
                        metadata={"file_path": file_change.path, "phase": phase}
                    ))
        
        return tasks
    
    def _schedule_tasks(self, tasks: List[ValidationTask]) -> List[ValidationTask]:
        """
        Schedule tasks based on the configured strategy.
        """
        if self.config.strategy == SchedulerStrategy.RISK_BASED:
            return self._schedule_risk_based(tasks)
        elif self.config.strategy == SchedulerStrategy.PARALLEL:
            return self._schedule_parallel(tasks)
        elif self.config.strategy == SchedulerStrategy.SEQUENTIAL:
            return self._schedule_sequential(tasks)
        elif self.config.strategy == SchedulerStrategy.ADAPTIVE:
            return self._schedule_adaptive(tasks)
        else:
            return tasks  # Default to unscheduled
    
    def _schedule_risk_based(self, tasks: List[ValidationTask]) -> List[ValidationTask]:
        """
        Schedule tasks with risk-based prioritization.
        """
        # Sort by priority (high first)
        priority_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        tasks.sort(key=lambda t: priority_order.get(t.risk_level, 1), reverse=True)
        
        # Apply dependency groups
        scheduled_tasks = []
        processed = set()
        
        for dependency_group in self.config.dependency_groups:
            group_tasks = [t for t in tasks if t.type in dependency_group and t.id not in processed]
            
            # Sort within group by priority
            group_tasks.sort(key=lambda t: t.priority, reverse=True)
            
            for task in group_tasks:
                scheduled_tasks.append(task)
                processed.add(task.id)
        
        # Add remaining tasks
        remaining_tasks = [t for t in tasks if t.id not in processed]
        scheduled_tasks.extend(remaining_tasks)
        
        return scheduled_tasks
    
    def _schedule_parallel(self, tasks: List[ValidationTask]) -> List[ValidationTask]:
        """
        Schedule tasks for maximum parallelization.
        """
        # Group by dependency groups
        scheduled_tasks = []
        processed = set()
        
        for dependency_group in self.config.dependency_groups:
            group_tasks = [t for t in tasks if t.type in dependency_group and t.id not in processed]
            
            # Sort within group by priority
            group_tasks.sort(key=lambda t: t.priority, reverse=True)
            
            for task in group_tasks:
                scheduled_tasks.append(task)
                processed.add(task.id)
        
        # Add remaining tasks
        remaining_tasks = [t for t in tasks if t.id not in processed]
        scheduled_tasks.extend(remaining_tasks)
        
        return scheduled_tasks
    
    def _schedule_sequential(self, tasks: List[ValidationTask]) -> List[ValidationTask]:
        """
        Schedule tasks sequentially.
        """
        # Sort by priority and phase
        phase_order = {"fast_checks": 1, "medium_checks": 2, "slow_checks": 3}
        tasks.sort(key=lambda t: (phase_order.get(t.metadata.get("phase", 1), 1), -t.priority))
        return tasks
    
    def _schedule_adaptive(self, tasks: List[ValidationTask]) -> List[ValidationTask]:
        """
        Adaptive scheduling based on previous performance data.
        """
        # For now, fall back to risk-based scheduling
        # In a real implementation, this would learn from execution patterns
        return self._schedule_risk_based(tasks)
    
    async def _execute_tasks(self, tasks: List[ValidationTask]) -> Dict[str, ValidationResult]:
        """
        Execute scheduled tasks with appropriate concurrency.
        """
        results = {}
        
        if self.config.strategy in [SchedulerStrategy.PARALLEL, SchedulerStrategy.ADAPTIVE]:
            results = await self._execute_parallel(tasks)
        else:
            results = await self._execute_sequential(tasks)
        
        return results
    
    async def _execute_parallel(self, tasks: List[ValidationTask]) -> Dict[str, ValidationResult]:
        """
        Execute tasks in parallel with dependency awareness.
        """
        results = {}
        futures = {}
        
        # Submit tasks to thread pool
        for task in tasks:
            future = self.executor.submit(self._execute_single_task, task)
            futures[future] = task
        
        # Collect results as they complete
        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
                results[task.id] = result
                
                # Update progress
                with self.lock:
                    self.completed_tasks += 1
                    print(f"Progress: {self.completed_tasks}/{self.total_tasks} "
                          f"({self.completed_tasks/self.total_tasks*100:.1f}%)")
            except Exception as e:
                # Handle task execution errors
                results[task.id] = ValidationResult(
                    task_id=task.id,
                    status=ValidationResultStatus.FAILED,
                    duration=0,
                    error=str(e)
                )
                with self.lock:
                    self.completed_tasks += 1
        
        return results
    
    async def _execute_sequential(self, tasks: List[ValidationTask]) -> Dict[str, ValidationResult]:
        """
        Execute tasks sequentially.
        """
        results = {}
        
        for task in tasks:
            print(f"Executing: {task.name}")
            result = self._execute_single_task(task)
            results[task.id] = result
            
            # Update progress
            with self.lock:
                self.completed_tasks += 1
                print(f"Progress: {self.completed_tasks}/{self.total_tasks} "
                      f"({self.completed_tasks/self.total_tasks*100:.1f}%)")
        
        return results
    
    def _execute_single_task(self, task: ValidationTask) -> ValidationResult:
        """
        Execute a single validation task.
        """
        # Find appropriate adapter
        adapter = None
        for adapter in self.adapters:
            if adapter.can_execute(task):
                adapter = adapter
                break
        
        if adapter is None:
            return ValidationResult(
                task_id=task.id,
                status=ValidationResultStatus.FAILED,
                duration=0,
                error=f"No adapter found for task type: {task.type}"
            )
        
        # Execute task
        return adapter.validate(task)
    
    def _generate_summary(self, results: Dict[str, ValidationResult], 
                         file_changes: List[FileChange]) -> Dict[str, Any]:
        """
        Generate a summary of validation results.
        """
        total_tasks = len(results)
        successful_tasks = sum(1 for r in results.values() if r.status == ValidationResultStatus.SUCCESS)
        failed_tasks = sum(1 for r in results.values() if r.status == ValidationResultStatus.FAILED)
        timeout_tasks = sum(1 for r in results.values() if r.status == ValidationResultStatus.TIMEOUT)
        
        total_duration = sum(r.duration for r in results.values())
        avg_duration = total_duration / total_tasks if total_tasks > 0 else 0
        
        # Risk distribution
        risk_distribution = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for file_change in file_changes:
            if file_change.risk_score >= 3.0:
                risk_distribution["critical"] += 1
            elif file_change.risk_score >= 2.0:
                risk_distribution["high"] += 1
            elif file_change.risk_score >= 1.0:
                risk_distribution["medium"] += 1
            else:
                risk_distribution["low"] += 1
        
        return {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": failed_tasks,
            "timeout_tasks": timeout_tasks,
            "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0,
            "total_duration": total_duration,
            "average_duration": avg_duration,
            "risk_distribution": risk_distribution,
            "execution_time": 0.0,  # Will be set by the caller
        }
    
    def _calculate_metrics(self) -> Dict[str, Any]:
        """
        Calculate performance metrics.
        """
        if not self.start_time:
            return {}
        
        execution_time = time.time() - self.start_time
        
        return {
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "execution_time": execution_time,
            "throughput": self.completed_tasks / execution_time if execution_time > 0 else 0,
            "concurrency_level": self.config.max_concurrent,
        }
    
    def cleanup(self):
        """Clean up resources."""
        self.executor.shutdown(wait=True)