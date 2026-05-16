# env-doctor 🩺

AI development environment diagnostic and optimization tool.

## Overview

env-doctor is a comprehensive diagnostic tool designed to analyze and optimize AI/ML development environments. It helps developers identify configuration issues, optimize resource usage, and ensure their environment is properly set up for AI development work.

## Features

- **Environment Scanning**: Automatically detect Python installations, CUDA versions, and AI frameworks
- **Dependency Analysis**: Check for compatibility issues and version conflicts
- **VRAM Optimization**: Analyze GPU memory usage and provide optimization recommendations
- **Model Management**: Track and manage AI models from Hugging Face and other sources
- **Reporting**: Generate detailed reports with actionable insights
- **AI Collaboration**: Report incompatibilities to Watsonx Orchestrate and automatically update the database via MCP

## Installation

```bash
pip install env-doctor
```

## Quick Start

```bash
# Run a full environment scan
env-doctor scan

# Check specific components
env-doctor check python
env-doctor check cuda
env-doctor check frameworks

# Analyze VRAM usage
env-doctor vram analyze

# Generate a report
env-doctor report
```

## Requirements

- Python 3.10 or higher
- Operating Systems: Windows, Linux, macOS

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/env-doctor.git
cd env-doctor

# Install in development mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Run linting
ruff check .

# Run type checking
mypy src/env_doctor

# Format code
ruff format .
```

## Project Structure

```
env-doctor/
├── src/env_doctor/
│   ├── cli/           # Command-line interface
│   ├── core/          # Core business logic
│   ├── database/      # Database models and operations
│   ├── scanner/       # Environment scanning
│   ├── vram/          # VRAM analysis
│   ├── reporting/     # Report generation
│   └── utils/         # Utility functions
├── tests/             # Test suite
└── docs/              # Documentation
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Roadmap

- [x] Phase 1: Project foundation and basic structure
- [ ] Phase 2: Core scanning functionality
- [ ] Phase 3: VRAM analysis and optimization
- [ ] Phase 4: Advanced features and reporting
- [ ] Phase 5: Web interface and cloud integration

## Support

For issues and questions, please use the [GitHub issue tracker](https://github.com/yourusername/env-doctor/issues).