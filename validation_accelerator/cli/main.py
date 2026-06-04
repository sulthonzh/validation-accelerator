"""
Command-line interface for Validation Accelerator.
"""

import os
import sys
import click
from typing import List, Optional
from pathlib import Path

from ..config.loader import ConfigLoader, ValidationConfig
from ..core.scheduler import ValidationScheduler, SchedulerConfig, SchedulerStrategy
from ..adapters.base import BaseAdapter
from ..adapters.pytest import PytestAdapter
from ..adapters.eslint import ESLintAdapter
from ..adapters.base import MockAdapter


@click.group()
@click.version_option(version="0.1.0")
@click.option("--config", "-c", help="Path to configuration file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.pass_context
def cli(ctx, config, verbose, dry_run):
    """
    Validation Accelerator - Optimize validation throughput for AI-generated code.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose
    ctx.obj["dry_run"] = dry_run


@cli.command()
@click.option("--path", "-p", default=".", help="Path to validate (default: current directory)")
@click.option("--changed-files", help="Comma-separated list of changed files")
@click.option("--strategy", type=click.Choice(['risk_based', 'parallel', 'sequential', 'adaptive']), 
              default='risk_based', help='Scheduling strategy')
@click.option("--max-concurrent", type=int, default=4, help='Maximum concurrent tasks')
@click.option("--timeout", type=int, default=300, help='Timeout in seconds')
@click.pass_context
def validate(ctx, path, changed_files, strategy, max_concurrent, timeout):
    """
    Run validation on the specified path.
    """
    config_path = ctx.obj["config"]
    verbose = ctx.obj["verbose"]
    dry_run = ctx.obj["dry_run"]
    
    try:
        # Load configuration
        config_loader = ConfigLoader()
        validation_config = config_loader.load_config(config_path)
        
        # Override with command-line options
        validation_config.scheduler.strategy = SchedulerStrategy(strategy)
        validation_config.scheduler.max_concurrent = max_concurrent
        validation_config.scheduler.timeout = timeout
        validation_config.working_directory = path
        
        if dry_run:
            _dry_run_validation(validation_config, path, changed_files, verbose)
            return
        
        # Get changed files
        if changed_files:
            changed_files_list = [f.strip() for f in changed_files.split(",")]
        else:
            changed_files_list = _find_changed_files(path)
        
        if not changed_files_list:
            click.echo("No changed files found.")
            return
        
        if verbose:
            click.echo(f"Found {len(changed_files_list)} changed files:")
            for f in changed_files_list:
                click.echo(f"  - {f}")
        
        # Initialize adapters
        adapters = _create_adapters(validation_config)
        
        # Create scheduler
        scheduler_config = validation_config.scheduler
        scheduler = ValidationScheduler(scheduler_config, adapters)
        
        # Run validation
        import asyncio
        results = asyncio.run(scheduler.schedule_validation(changed_files_list, path))
        
        # Display results
        _display_results(results, verbose)
        
        # Cleanup
        scheduler.cleanup()
        
        # Exit with appropriate code
        if results["summary"]["failed_tasks"] > 0:
            sys.exit(1)
        elif results["summary"]["timeout_tasks"] > 0:
            sys.exit(2)
        else:
            sys.exit(0)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option("--output", "-o", default=".validation-accelerator.yaml", help="Output file path")
def init(output):
    """
    Initialize a new configuration file.
    """
    try:
        config_loader = ConfigLoader()
        default_config = config_loader._parse_config({})
        
        # Create default configuration
        config_data = {
            "strategies": {
                "strategy": "risk_based",
                "max_concurrent": 4,
                "timeout": 300,
                "priority_factors": default_config.scheduler.priority_factors,
                "dependency_groups": default_config.scheduler.dependency_groups,
                "phase_timeout": default_config.scheduler.phase_timeout
            },
            "adapters": default_config.adapters,
            "phases": default_config.phases,
            "excludes": default_config.excludes,
            "timeout": 300,
            "working_directory": "."
        }
        
        # Write to file
        import yaml
        with open(output, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
        
        click.echo(f"Configuration file created: {output}")
        
    except Exception as e:
        click.echo(f"Error creating configuration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--config", "-c", help="Path to configuration file")
@click.pass_context
def check(ctx, config):
    """
    Check configuration file syntax and validity.
    """
    try:
        config_loader = ConfigLoader()
        validation_config = config_loader.load_config(config)
        
        if config_loader.validate_config(validation_config):
            click.echo("✅ Configuration is valid")
        else:
            click.echo("❌ Configuration is invalid", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--path", "-p", default=".", help="Path to analyze")
@click.pass_context
def analyze(ctx, path):
    """
    Analyze changed files and show risk assessment.
    """
    try:
        # Find changed files
        changed_files = _find_changed_files(path)
        
        if not changed_files:
            click.echo("No changed files found.")
            return
        
        # Analyze changes
        from ..core.analyzer import ChangeAnalyzer
        analyzer = ChangeAnalyzer()
        file_changes = analyzer.analyze_changes(changed_files, path)
        
        # Show results
        click.echo(f"📊 Analysis of {len(file_changes)} changed files:")
        click.echo()
        
        total_risk = 0
        for change in file_changes:
            total_risk += change.risk_score
            emoji = _get_risk_emoji(change.risk_score)
            click.echo(f"{emoji} {change.path}")
            click.echo(f"   Type: {change.change_type}")
            click.echo(f"   Lines changed: {change.lines_changed}")
            click.echo(f"   Risk score: {change.risk_score:.2f}")
            if change.risk_factors:
                click.echo(f"   Risk factors: {', '.join(change.risk_factors)}")
            click.echo()
        
        avg_risk = total_risk / len(file_changes) if file_changes else 0
        click.echo(f"📈 Average risk score: {avg_risk:.2f}")
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _find_changed_files(path: str) -> List[str]:
    """
    Find changed files in the specified path.
    """
    changed_files = []
    
    # Simple implementation: check for modified files in the last hour
    # In a real implementation, this would use git diff
    try:
        from datetime import datetime, timedelta
        
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        for root, dirs, files in os.walk(path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
            
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if mod_time > one_hour_ago:
                        # Convert to relative path
                        rel_path = os.path.relpath(file_path, path)
                        changed_files.append(rel_path)
                except:
                    pass
                    
    except Exception as e:
        # Fallback: list all files in path
        try:
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, path)
                    changed_files.append(rel_path)
        except:
            pass
    
    return changed_files[:20]  # Limit to avoid too many files


def _create_adapters(validation_config: ValidationConfig) -> List[BaseAdapter]:
    """
    Create adapters based on configuration.
    """
    adapters = []
    
    for adapter_name, adapter_config in validation_config.adapters.items():
        if not adapter_config.get('enabled', True):
            continue
        
        if adapter_name == 'pytest':
            adapters.append(PytestAdapter(adapter_config))
        elif adapter_name == 'eslint':
            adapters.append(ESLintAdapter(adapter_config))
        elif adapter_name == 'mock':
            adapters.append(MockAdapter('mock', adapter_config))
        else:
            # Add more adapters as needed
            pass
    
    return adapters


def _dry_run_validation(config: ValidationConfig, path: str, changed_files: str, verbose: bool):
    """
    Show what would be done without actually running validation.
    """
    click.echo("🎯 Dry run - What would be executed:")
    click.echo()
    
    if changed_files:
        changed_files_list = [f.strip() for f in changed_files.split(",")]
    else:
        changed_files_list = _find_changed_files(path)
    
    click.echo(f"Path: {path}")
    click.echo(f"Strategy: {config.scheduler.strategy.value}")
    click.echo(f"Max concurrent: {config.scheduler.max_concurrent}")
    click.echo(f"Timeout: {config.scheduler.timeout}s")
    click.echo(f"Changed files: {len(changed_files_list)}")
    
    if verbose:
        for f in changed_files_list:
            click.echo(f"  - {f}")
    
    click.echo()
    click.echo("Adapters that would be used:")
    for adapter_name, adapter_config in config.adapters.items():
        if adapter_config.get('enabled', True):
            click.echo(f"  ✅ {adapter_name}")
    
    click.echo()
    click.echo("Phases that would be executed:")
    for phase_name, phase_tasks in config.phases.items():
        click.echo(f"  📋 {phase_name}: {len(phase_tasks)} tasks")


def _display_results(results: dict, verbose: bool):
    """
    Display validation results.
    """
    summary = results["summary"]
    file_changes = results["file_changes"]
    
    click.echo("🏁 Validation Summary:")
    click.echo(f"  Total tasks: {summary['total_tasks']}")
    click.echo(f"  ✅ Successful: {summary['successful_tasks']}")
    click.echo(f"  ❌ Failed: {summary['failed_tasks']}")
    click.echo(f"  ⏰ Timeout: {summary['timeout_tasks']}")
    click.echo(f"  Success rate: {summary['success_rate']:.1%}")
    click.echo(f"  Total time: {summary['execution_time']:.2f}s")
    click.echo()
    
    # Show risk distribution
    click.echo("📊 Risk Distribution:")
    for risk_level, count in summary["risk_distribution"].items():
        if count > 0:
            emoji = _get_risk_emoji_by_level(risk_level)
            click.echo(f"  {emoji} {risk_level}: {count}")
    click.echo()
    
    # Show high-risk files
    high_risk_files = [f for f in file_changes if f.risk_score >= 2.0]
    if high_risk_files:
        click.echo("⚠️  High-Risk Files:")
        for file_change in high_risk_files[:5]:  # Show top 5
            emoji = _get_risk_emoji(file_change.risk_score)
            click.echo(f"  {emoji} {file_change.path} (score: {file_change.risk_score:.2f})")
        click.echo()
    
    # Show detailed results if verbose
    if verbose:
        click.echo("🔍 Detailed Results:")
        for task_id, result in results["results"].items():
            status_icon = "✅" if result.status.value == "success" else "❌"
            click.echo(f"  {status_icon} {task_id}: {result.duration:.2f}s")
            if result.error:
                click.echo(f"    Error: {result.error}")


def _get_risk_emoji(risk_score: float) -> str:
    """
    Get emoji based on risk score.
    """
    if risk_score >= 3.0:
        return "🔴"
    elif risk_score >= 2.0:
        return "🟡"
    elif risk_score >= 1.0:
        return "🟢"
    else:
        return "⚪"


def _get_risk_emoji_by_level(level: str) -> str:
    """
    Get emoji based on risk level.
    """
    level_emoji = {
        "critical": "🔴",
        "high": "🟡",
        "medium": "🟢",
        "low": "⚪"
    }
    return level_emoji.get(level, "⚪")


if __name__ == "__main__":
    cli()