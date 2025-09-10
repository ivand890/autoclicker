# Contributing to Clickmate

Thanks for taking the time to contribute!

## Getting started

- Requires Python >= 3.11 and [`uv`](https://docs.astral.sh/uv/).
- clone and install deps:
  ```bash
  uv sync
  ```
- Run the tool:
  ```bash
  uv run clickmate --help
  uv run clickmate
  ```
- Run tests and lint:
  ```bash
  uv run pytest -q
  uv run ruff check src tests
  uv run ruff format --check src tests
  ```

## Development notes

- Module package is `autoclicker`; the published package and CLI are `clickmate`.
- macOS requires Accessibility and Input Monitoring permissions for the terminal.
- Avoid printing in the main loop; use the status renderer and debug toggle.

## Opening a PR

- Write clear commit messages and PR descriptions.
- Ensure CI (lint, tests) passes.
- Add tests for new behavior when practical.

## Release process

- Create a tag `vX.Y.Z` to trigger the GitHub Actions Release workflow.
- Pre-releases with `rc` also publish to TestPyPI.
