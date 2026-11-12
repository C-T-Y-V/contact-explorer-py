# Contributing to Contact Explorer

Thank you for your interest in contributing to Contact Explorer! We welcome contributions from developers of all skill levels. To ensure high code quality, security, and architectural consistency, please review this guide before submitting work.

---

## Code of Conduct

All contributors are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). Please report unacceptable behavior to `priyanshuctyv@gmail.com`.

---

## Architectural Principles

Before writing code, understand the core design invariants:
1. **Zero External Runtime Dependencies:** The core package must run exclusively on the Python standard library. Do not add runtime dependencies without architectural discussion.
2. **Offline-First & Privacy Sovereign:** No telemetry, network callbacks, or background cloud syncing.
3. **Decoupled Architecture:** Business logic in `service.py`, persistence in `database.py`, algorithms in `intelligence.py`, formats in `transfer.py`, and presentation in `ui.py`.

---

## Development Setup

### 1. Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13
- Git 2.30+
- (Optional) `make` for running task shortcuts

### 2. Fork & Clone
```bash
git clone https://github.com/priyanshu-ctyv/contact-explorer-py.git
cd contact-explorer-py
```

### 3. Create a Virtual Environment
```bash
# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 4. Install in Editable Mode with Developer Tooling
```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

---

## Development Workflow

### Branching Strategy
Use semantic branch names:
- `feat/feature-name` (New features)
- `fix/bug-description` (Bug fixes)
- `perf/optimization-name` (Performance improvements)
- `docs/documentation-update` (Documentation changes)
- `test/test-addition` (Adding or refactoring tests)

### Running Tests
Execute the automated test suite using `pytest`:
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with test coverage report
pytest --cov=contact_explorer --cov-report=term-missing
```

### Code Formatting & Linting
We enforce strict style standards via [Ruff](https://docs.astral.sh/ruff/) and [Mypy](https://mypy-lang.org/):
```bash
# Check code style with Ruff
ruff check .

# Automatically apply safe fixes
ruff check . --fix

# Format code
ruff format .

# Type checking
mypy contact_explorer
```

---

## Commit Guidelines

We adhere to the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short summary>

[optional body]

[optional footer(s)]
```

### Types
- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `perf`: A code change that improves performance
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to build process, tooling, or CI

### Examples
- `feat(search): add phonetic fuzzy search tokenization`
- `fix(transfer): handle escaped commas in vCard 3.0 addresses`
- `docs(api): update swagger-style endpoints specification`

---

## Submitting a Pull Request (PR)

1. Ensure all tests pass (`pytest`).
2. Verify linting passes with zero errors (`ruff check .`).
3. Ensure no uncommitted debug prints or transient files are left.
4. Push your branch to your GitHub fork:
   ```bash
   git push origin feat/your-branch-name
   ```
5. Open a Pull Request against the `main` branch.
6. Complete the PR template checklist. A maintainer will review your submission promptly.
