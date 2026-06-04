# Contributing to Validation Accelerator

We welcome contributions! This document provides guidelines for contributing to the Validation Accelerator project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/validation-accelerator.git`
3. Set up the development environment: `pip install -e ".[dev]"`
4. Create a new branch: `git checkout -b feature/your-feature-name`

## Development Workflow

### Code Style

We follow these style guidelines:

- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting
- **mypy** for type checking

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=validation_accelerator

# Run specific test file
pytest tests/test_scheduler.py
```

### Before Committing

1. Format code: `black .`
2. Sort imports: `isort .`
3. Run linting: `flake8`
4. Type check: `mypy validation_accelerator/`
5. Run tests: `pytest`

### Pull Request Process

1. Update tests to reflect any changes
2. Ensure all existing tests pass
3. Update documentation as needed
4. Add your name to the CONTRIBUTORS list if you're a new contributor
5. Submit a pull request with a clear description of changes

## Development Environment Setup

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Install pre-commit hooks (optional but recommended)
pre-commit install
```

## Adding New Adapters

If you want to add support for a new validation tool:

1. Create a new adapter file in `validation_accelerator/adapters/`
2. Implement the `BaseAdapter` interface
3. Add tests in `tests/`
4. Update documentation in `README.md`

## Adding New Strategies

To add a new scheduling strategy:

1. Implement the strategy class in `validation_accelerator/core/`
2. Add configuration options to the schema
3. Update the CLI in `validation_accelerator/cli/main.py`
4. Add tests for the new strategy

## Reporting Issues

When reporting bugs, please include:

- Python version
- Operating system
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Any error messages or stack traces

## Getting Help

- Create an issue on GitHub for bugs or feature requests
- Check existing issues before creating new ones
- For general questions, feel free to start a discussion

## Code of Conduct

Please be respectful and constructive in all interactions. We're here to build a helpful tool for the community.

Thank you for contributing!