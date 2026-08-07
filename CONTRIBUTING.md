# Contributing

ReviewSignal is a portfolio project, but focused fixes and documentation improvements are welcome.

1. Create a branch from `main`.
2. Install the locked Python 3.11 environment with `uv sync --frozen`.
3. Add or update tests before changing behavior.
4. Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest --cov=reviewsignal`.
5. If infrastructure changes, run Terraform formatting and validation for both root and bootstrap modules.
6. Open a pull request describing the observable change and verification performed.

Do not commit raw review data, generated models, credentials, cloud state, personal paths, or submitted demo text.
