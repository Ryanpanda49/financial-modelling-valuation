# Contributing

Contributions should preserve the framework's modular, explainable, and research-oriented
design. Core calculations belong under `src/fmva/`; notebooks and examples should call those
modules rather than duplicate modelling logic.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
ruff check src tests scripts
mypy src/fmva
python scripts/public_release_check.py
```

The test suite is offline by default. Use the pinned public WMT fixture for deterministic
end-to-end work. Live SEC requests require a private `config/model_config.yaml` containing a
valid contact-bearing User-Agent and must respect SEC access policies.

## Pull requests

- Add or update tests for changed calculations, mappings, and validation rules.
- Keep assumptions declarative and outside calculation functions.
- Preserve field-level provenance and disclose derivations or fallback logic.
- Document modelling conventions, limitations, and any company-specific mapping overrides.
- Do not commit private configurations, SEC cache files, generated outputs, paid data, internal
  reference workbooks, or personal contact information.
- Run the complete test suite and public-release audit before opening a pull request.

Changes to the public history JSON schema must increment its schema version and include a
migration or a clear compatibility error.

Mypy is strict by default. Narrow overrides are documented in `pyproject.toml` for the dynamic
pandas/openpyxl boundary modules; those modules require focused numerical and export tests until
their third-party typing is precise enough to remove each override.
