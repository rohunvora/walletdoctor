# WalletDoctor Project Structure

## Overview
This repository contains the WalletDoctor trading analysis tool, organized with a clean structure separating source code, tests, examples, and data.

## Directory Structure

```
walletdoctor/
├── src/                      # Source code
│   └── walletdoctor/        # Main package
│       ├── insights/        # Insight generation modules
│       ├── features/        # Feature extraction and patterns
│       ├── llm/            # LLM integration
│       ├── web/            # Web application
│       │   └── templates/  # HTML templates
│       └── cli/            # Command-line interface
│
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
│
├── scripts/                 # Utility and analysis scripts
│   ├── coach.py            # Main coaching interface
│   ├── harsh_insights.py   # Harsh trading insights
│   ├── blind_spots.py      # Trading blind spot analysis
│   └── ...                 # Other utility scripts
│
├── examples/               # Example usage scripts
│   ├── example.py          # Basic usage example
│   ├── example_full_narrative.py
│   └── ...                 # Other examples
│
├── data/                   # Data files (git-ignored)
│   ├── *.db               # Database files
│   ├── *.csv              # CSV data
│   └── *.parquet          # Parquet files
│
├── web_app.py             # Flask web application
├── setup.py               # Package installation
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
└── .gitignore            # Git ignore rules
```

## Key Components

### Source Code (`src/walletdoctor/`)
- **insights/**: Generates trading insights and analysis
- **features/**: Extracts patterns and behavioral features from trading data
- **llm/**: Handles LLM integration for natural language analysis
- **web/**: Web interface components

### Scripts (`scripts/`)
Standalone scripts for various analysis tasks:
- `coach.py`: Main coaching interface for wallet analysis
- `harsh_insights.py`: Provides direct, unfiltered trading feedback
- `blind_spots.py`: Identifies trading blind spots and weaknesses

### Tests (`tests/`)
- **unit/**: Individual component tests
- **integration/**: End-to-end testing

### Examples (`examples/`)
Demonstration scripts showing how to use the library

### Data (`data/`)
Local data storage (not tracked in git):
- Database files for caching analysis
- CSV exports and imports
- Temporary data files

## Development Guidelines

1. Keep all source code in `src/walletdoctor/`
2. Place new tests in appropriate subdirectory under `tests/`
3. Add example scripts to `examples/` for new features
4. Store data files in `data/` (automatically git-ignored)
5. Utility scripts go in `scripts/`

## Clean Repository Practices

- Virtual environments (`venv/`) are git-ignored
- OS files (`.DS_Store`) are git-ignored
- Log files (`*.log`) are git-ignored
- Database and data files stay in `data/`
- Temporary files are automatically excluded 