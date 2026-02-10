# Publishing to PyPI

This guide covers publishing Terrarium packages (Vivarium and Treehouse) to PyPI.

## Prerequisites

You need PyPI accounts for both packages:
- https://pypi.org/project/vivarium/
- https://pypi.org/project/treehouse/

### Step 1: Create PyPI Accounts

1. Go to https://pypi.org/account/register/
2. Create two accounts (or use the same account):
   - One for `vivarium` package
   - One for `treehouse` package

(You can use the same PyPI account for both, or separate ones for finer-grained token control)

### Step 2: Create API Tokens

1. Go to https://pypi.org/manage/account/
2. Scroll to "API tokens" section
3. Click "Add API token"
4. Give it a name: `github-terrarium` (or similar)
5. Select "Entire account" or "vivarium" project
6. Copy the token (starts with `pypi-...`)
7. Repeat for treehouse if using separate account

### Step 3: Add Secrets to GitHub

1. Go to https://github.com/ricardokirkner/terrarium/settings/secrets/actions
2. Click "New repository secret"
3. Add two secrets:
   - **Name**: `PYPI_API_TOKEN_VIVARIUM`
     **Value**: (paste your PyPI token for vivarium)
   - **Name**: `PYPI_API_TOKEN_TREEHOUSE`
     **Value**: (paste your PyPI token for treehouse, or same as vivarium if using one account)

> ⚠️ **Keep tokens secret!** Never commit them to Git.

### Step 4: Test the Build Locally (Optional)

```bash
# Test building vivarium
cd vivarium
uv run pip install build
uv run python -m build
ls dist/  # Should show vivarium-0.1.0.tar.gz and vivarium-0.1.0-py3-*.whl

# Test building treehouse
cd ../treehouse
uv run pip install build
uv run python -m build
ls dist/  # Should show treehouse-0.1.0.tar.gz and treehouse-0.1.0-py3-*.whl
```

## Publishing

### Automatic (Recommended)

Trigger publishing automatically by creating a git tag:

```bash
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0
```

This will:
1. Run tests in `.github/workflows/tests.yml`
2. Build packages
3. Publish to PyPI via `.github/workflows/publish.yml`

Watch progress at: https://github.com/ricardokirkner/terrarium/actions

### Manual

If you prefer to publish manually:

```bash
# Build
cd vivarium
uv run python -m build

# Publish (requires twine)
uv run pip install twine
uv run twine upload dist/*

# Repeat for treehouse
cd ../treehouse
uv run python -m build
uv run twine upload dist/*
```

## Verify Publication

After publishing, verify packages appear on PyPI:

```bash
# Test installation from PyPI
pip install vivarium
pip install treehouse[visualizer]

# Check versions
python -c "import vivarium; print(vivarium.__version__)"
python -c "import treehouse; print(treehouse.__version__)"
```

Or check directly:
- https://pypi.org/project/vivarium/
- https://pypi.org/project/treehouse/

## Troubleshooting

### "Invalid or missing PyPI token"
- Verify token is copied correctly (no extra spaces)
- Verify secret names match exactly: `PYPI_API_TOKEN_VIVARIUM`, `PYPI_API_TOKEN_TREEHOUSE`
- Try regenerating the token on PyPI

### "Package already exists"
- Each version can only be published once
- If you need to re-publish, increment the version in pyproject.toml and re-tag

### Build fails locally
- Ensure `build` package is installed: `uv run pip install build`
- Check pyproject.toml has correct metadata (name, version, author, etc.)
- Verify no uncommitted changes in package directories

## Version Management

When preparing a new release:

1. Update version in both `pyproject.toml` files:
   ```toml
   [project]
   version = "0.2.0"
   ```

2. Update `CHANGELOG.md` with release notes

3. Commit changes:
   ```bash
   git add vivarium/pyproject.toml treehouse/pyproject.toml CHANGELOG.md
   git commit -m "chore: bump version to 0.2.0"
   ```

4. Create and push tag:
   ```bash
   git tag -a v0.2.0 -m "Release v0.2.0"
   git push origin main
   git push origin v0.2.0
   ```

## Resources

- [PyPI Help](https://pypi.org/help/)
- [Python Packaging Guide](https://packaging.python.org/)
- [Build Documentation](https://build.pypa.io/)
- [GitHub Actions PyPI Publisher](https://github.com/pypa/gh-action-pypi-publish)
