# Contributing

## Development Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/gianlucapagliara/chronopype.git
cd chronopype
uv sync
```

## Running Tests

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=chronopype --cov-report=term-missing
```

## Code Quality

### Linting and Formatting

```bash
# Check code style
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Type Checking

```bash
uv run mypy chronopype
```

The project uses MyPy in strict mode. All public functions must have type annotations.

### Pre-commit Hooks

Install hooks to run checks automatically before each commit:

```bash
uv run pre-commit install
```

Run all hooks manually:

```bash
uv run pre-commit run --all-files
```

## Project Structure

```
chronopype/
├── chronopype/
│   ├── __init__.py
│   ├── exceptions.py          # Exception hierarchy
│   ├── time.py                # Time constants and timestamp utilities
│   ├── clocks/
│   │   ├── __init__.py        # Clock registry and exports
│   │   ├── modes.py           # ClockMode enum
│   │   ├── config.py          # ClockConfig model
│   │   ├── base.py            # BaseClock abstract class
│   │   ├── realtime.py        # RealtimeClock implementation
│   │   └── backtest.py        # BacktestClock implementation
│   └── processors/
│       ├── __init__.py
│       ├── base.py            # TickProcessor base class
│       ├── models.py          # ProcessorState model
│       └── network.py         # NetworkProcessor abstract class
├── tests/
│   ├── conftest.py
│   ├── test_models.py
│   ├── clocks/
│   │   ├── test_base.py
│   │   ├── test_realtime.py
│   │   ├── test_backtest.py
│   │   ├── test_errors.py
│   │   └── test_performance.py
│   └── processors/
│       ├── test_base.py
│       └── test_network.py
├── docs/                      # Documentation (mkdocs)
├── scripts/
│   └── release.sh             # Release automation
└── pyproject.toml
```

## Releasing

Releases are managed via the release script:

```bash
./scripts/release.sh patch  # or minor, or major
```

This script:

1. Validates you are on the `main` branch with a clean tree
2. Bumps the version in `pyproject.toml`
3. Runs all checks (ruff, mypy, pytest)
4. Commits, tags, and pushes
5. Creates a GitHub release (which triggers PyPI publishing via CI)

## CI/CD

- **CI** runs on every push and PR to `main`: linting, type checking, tests with coverage
- **Publish** runs on GitHub release creation: tests, build, publish to PyPI
