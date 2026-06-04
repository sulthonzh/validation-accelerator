from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="validation-accelerator",
    version="0.1.0",
    author="Sulthonzh",
    author_email="sulthonzh@example.com",
    description="Optimize validation throughput for AI-generated code",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sulthonzh/validation-accelerator",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "pyyaml>=6.0",
        "click>=8.0",
        "networkx>=2.8",
        "psutil>=5.9",
        "rich>=12.0",
        "pydantic>=1.10",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=22.0",
            "flake8>=5.0",
            "mypy>=0.991",
        ],
        "ci": [
            "pytest-github-actions-annotate-failures>=0.1.7",
        ],
    },
    entry_points={
        "console_scripts": [
            "validation-accelerator=validation_accelerator.cli.main:main",
        ],
    },
    keywords="ai validation testing code-quality parallel ci cd",
    project_urls={
        "Bug Reports": "https://github.com/sulthonzh/validation-accelerator/issues",
        "Source": "https://github.com/sulthonzh/validation-accelerator",
        "Documentation": "https://github.com/sulthonzh/validation-accelerator#readme",
    },
)