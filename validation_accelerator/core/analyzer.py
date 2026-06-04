"""
Change analyzer for identifying high-risk areas in code changes.
"""

import os
import ast
import re
from typing import Dict, List, Any, Set, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import networkx as nx

from ..adapters.base import ValidationTask


class RiskLevel(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class FileChange:
    """Represents a changed file and its characteristics."""
    path: str
    change_type: str  # added, modified, deleted
    lines_changed: int
    risk_score: float
    risk_factors: List[str]


class ChangeAnalyzer:
    """Analyzes code changes to identify high-risk areas."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.risk_weights = self.config.get("risk_weights", {
            "api_surface_changes": 3.0,
            "security_tests": 3.0,
            "public_interfaces": 2.5,
            "database_changes": 2.0,
            "ui_components": 1.5,
            "utility_functions": 1.0,
            "tests": 1.0,
            "documentation": 0.5,
        })
    
    def analyze_changes(self, changed_files: List[str], 
                       base_path: str = ".") -> List[FileChange]:
        """
        Analyze changed files to assess risk levels.
        
        Args:
            changed_files: List of file paths that changed
            base_path: Base directory path
            
        Returns:
            List of FileChange objects with risk assessments
        """
        file_changes = []
        
        for file_path in changed_files:
            full_path = os.path.join(base_path, file_path)
            change = self._analyze_single_file(file_path, full_path)
            file_changes.append(change)
        
        return file_changes
    
    def _analyze_single_file(self, file_path: str, full_path: str) -> FileChange:
        """
        Analyze a single file to determine its risk level.
        """
        # Determine file type and change type
        change_type = self._get_change_type(file_path, full_path)
        file_ext = Path(file_path).suffix.lower()
        
        # Calculate base risk score
        risk_score = 0.0
        risk_factors = []
        
        # File type risk assessment
        if self._is_api_file(file_path):
            risk_score += self.risk_weights.get("api_surface_changes", 3.0)
            risk_factors.append("api_surface_changes")
        
        if self._is_security_file(file_path):
            risk_score += self.risk_weights.get("security_tests", 3.0)
            risk_factors.append("security_tests")
        
        if self._is_public_interface(file_path):
            risk_score += self.risk_weights.get("public_interfaces", 2.5)
            risk_factors.append("public_interfaces")
        
        if self._is_database_file(file_path):
            risk_score += self.risk_weights.get("database_changes", 2.0)
            risk_factors.append("database_changes")
        
        if self._is_ui_file(file_path):
            risk_score += self.risk_weights.get("ui_components", 1.5)
            risk_factors.append("ui_components")
        
        if self._is_test_file(file_path):
            risk_score += self.risk_weights.get("tests", 1.0)
            risk_factors.append("tests")
        
        if self._is_utility_file(file_path):
            risk_score += self.risk_weights.get("utility_functions", 1.0)
            risk_factors.append("utility_functions")
        
        # Additional risk factors based on file content
        if os.path.exists(full_path):
            content_risk = self._analyze_file_content(full_path)
            risk_score += content_risk["score"]
            risk_factors.extend(content_risk["factors"])
        
        # Calculate lines changed
        lines_changed = self._count_lines_changed(full_path)
        risk_score *= (1 + lines_changed / 100)  # Scale by change magnitude
        
        return FileChange(
            path=file_path,
            change_type=change_type,
            lines_changed=lines_changed,
            risk_score=risk_score,
            risk_factors=risk_factors
        )
    
    def _get_change_type(self, file_path: str, full_path: str) -> str:
        """Determine if file was added, modified, or deleted."""
        if not os.path.exists(full_path):
            return "deleted"
        elif self._is_new_file(full_path):
            return "added"
        else:
            return "modified"
    
    def _is_new_file(self, full_path: str) -> bool:
        """Check if a file is newly created (has no git history)."""
        try:
            # Simple check: if file is very small, it might be new
            return os.path.getsize(full_path) < 100
        except:
            return False
    
    def _is_api_file(self, file_path: str) -> bool:
        """Check if file contains API-related code."""
        api_patterns = [
            r'api', r'endpoint', r'route', r'controller',
            r'service', r'handler', r'middleware'
        ]
        return any(re.search(pattern, file_path.lower(), re.IGNORECASE) 
                  for pattern in api_patterns)
    
    def _is_security_file(self, file_path: str) -> bool:
        """Check if file is security-related."""
        security_patterns = [
            r'auth', r'security', r'permission', r'rbac',
            r'oauth', r'jwt', r'hash', r'encrypt'
        ]
        return any(re.search(pattern, file_path.lower(), re.IGNORECASE) 
                  for pattern in security_patterns)
    
    def _is_public_interface(self, file_path: str) -> bool:
        """Check if file defines a public interface."""
        interface_patterns = [
            r'index\.(js|ts|py)$', r'main\.(js|ts|py)$',
            r'public', r'shared', r'core'
        ]
        return any(re.search(pattern, file_path.lower()) 
                  for pattern in interface_patterns)
    
    def _is_database_file(self, file_path: str) -> bool:
        """Check if file is database-related."""
        db_patterns = [
            r'model', r'schema', r'migration', r'seed',
            r'query', r'repository', r'dao'
        ]
        return any(re.search(pattern, file_path.lower(), re.IGNORECASE) 
                  for pattern in db_patterns)
    
    def _is_ui_file(self, file_path: str) -> bool:
        """Check if file is UI-related."""
        ui_patterns = [
            r'component', r'view', r'template', r'style',
            r'css', r'sass', r'jsx', r'tsx', r'vue'
        ]
        return any(re.search(pattern, file_path.lower(), re.IGNORECASE) 
                  for pattern in ui_patterns)
    
    def _is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file."""
        test_patterns = [
            r'test', r'spec', r'__tests__', r'fixture',
            r'unit|integration|e2e', r'\.test\.', r'\.spec\.'
        ]
        return any(re.search(pattern, file_path.lower()) 
                  for pattern in test_patterns)
    
    def _is_utility_file(self, file_path: str) -> bool:
        """Check if file is a utility/helper file."""
        utility_patterns = [
            r'utils', r'helpers', r'lib', r'common',
            r'utility', r'helper'
        ]
        return any(re.search(pattern, file_path.lower(), re.IGNORECASE) 
                  for pattern in utility_patterns)
    
    def _analyze_file_content(self, full_path: str) -> Dict[str, Any]:
        """
        Analyze file content for additional risk factors.
        """
        score = 0.0
        factors = []
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Check for critical patterns
                critical_patterns = [
                    (r'eval\s*\(', 'eval_usage'),
                    (r'exec\s*\(', 'exec_usage'),
                    (r'innerHTML\s*=', 'dom_manipulation'),
                    (r'document\.write\s*\(', 'document_write'),
                    (r'console\.log\s*\(', 'console_log'),
                    (r'TODO|FIXME|HACK', 'unfinished_code'),
                ]
                
                for pattern, factor in critical_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        score += 0.5
                        factors.append(factor)
                
                # Check for SQL injection patterns
                sql_patterns = [
                    r'SELECT\s+.*\+.*FROM',
                    r'INSERT\s+.*\+.*INTO',
                    r'UPDATE\s+.*\+.*SET',
                    r'DELETE\s+.*\+.*FROM'
                ]
                
                for pattern in sql_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        score += 1.0
                        factors.append('sql_injection_risk')
                        break
                
                # Check for error-prone constructs
                error_prone_patterns = [
                    (r'catch\s*\(\s*\w+\s*\)\s*\{', 'bare_catch'),
                    (r'Promise\.resolve\(\s*\)', 'unnecessary_promise'),
                    (r'setTimeout\s*\(\s*,\s*0\s*\)', 'infinite_timeout'),
                ]
                
                for pattern, factor in error_prone_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        score += 0.3
                        factors.append(factor)
        
        except Exception as e:
            # If we can't read the file, assume higher risk
            score += 1.0
            factors.append('unreadable_file')
        
        return {"score": score, "factors": factors}
    
    def _count_lines_changed(self, full_path: str) -> int:
        """Count the number of lines changed in a file."""
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return len(lines)
        except Exception:
            return 0
    
    def get_high_risk_files(self, file_changes: List[FileChange], 
                          threshold: float = 2.0) -> List[FileChange]:
        """
        Get files with high risk scores.
        
        Args:
            file_changes: List of FileChange objects
            threshold: Risk score threshold for "high risk"
            
        Returns:
            List of high-risk FileChange objects
        """
        return [change for change in file_changes if change.risk_score >= threshold]
    
    def sort_by_risk(self, file_changes: List[FileChange]) -> List[FileChange]:
        """
        Sort files by risk score (highest first).
        
        Args:
            file_changes: List of FileChange objects
            
        Returns:
            Sorted list of FileChange objects
        """
        return sorted(file_changes, key=lambda x: x.risk_score, reverse=True)