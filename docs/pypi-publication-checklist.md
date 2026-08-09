# PyPI Publication Checklist

Publish only after the repository is public and the release candidate has been
tested from a clean environment.

## Package metadata

- [ ] `pyproject.toml` package name is `metagate`.
- [ ] Version is `0.1.0`.
- [ ] README renders correctly as the long description.
- [ ] License is Apache-2.0.
- [ ] Python requirement is `>=3.9`.
- [ ] Console script is `metagate`.
- [ ] Optional dependencies are documented: `dev` and `datahub`.

## Local build

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

## Test install

```bash
python -m venv /tmp/metagate-test
source /tmp/metagate-test/bin/activate
python -m pip install dist/context_gradient-0.1.0-py3-none-any.whl
metagate --help
deactivate
```

## TestPyPI

```bash
python -m twine upload --repository testpypi dist/*
python -m pip install --index-url https://test.pypi.org/simple/ metagate
```

## Production PyPI

```bash
python -m twine upload dist/*
```

## After publication

- [ ] Add the PyPI URL to the Devpost submission.
- [ ] Add an install badge to the README if desired.
- [ ] Verify `pip install metagate` in a clean environment.
