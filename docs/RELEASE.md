# Release Process

This document describes how to create a new release for pyci-check.

## Prerequisites

1. Ensure all tests pass on CI
2. Update version in `pyproject.toml`
3. Update changelog (if exists)
4. Ensure all documentation is up to date

## Release Steps

### 1. Update Version

Edit `pyproject.toml` and update the version:

```toml
[project]
name = "pyci-check"
version = "0.2.0"  # Update this
```

### 2. Commit Version Bump

```bash
git add pyproject.toml
git commit -m "chore: bump version to 0.2.0"
git push origin main
```

### 3. Create and Push Tag

```bash
# Create annotated tag
git tag -a v0.2.0 -m "Release version 0.2.0"

# Push tag to trigger release workflow
git push origin v0.2.0
```

### 4. Automatic Release Process

Once the tag is pushed, GitHub Actions will automatically:

1. **Build Package** - Build wheel and source distribution
2. **Test Installation** - Test installation on:
   - Ubuntu, macOS, Windows
   - Python 3.11, 3.12, 3.13
3. **Create GitHub Release** - Create release with auto-generated notes
4. **Publish to PyPI** - Upload package to PyPI

### 5. Verify Release

1. Check GitHub Release: https://github.com/coseto6125/pyci-check/releases
2. Check PyPI: https://pypi.org/project/pyci-check/
3. Test installation:
   ```bash
   pip install pyci-check==0.2.0
   pyci-check --help
   ```

## PyPI Setup

### First-time Setup

1. **Create PyPI Account**: https://pypi.org/account/register/

2. **Enable 2FA**: Required for publishing

3. **Create API Token**:
   - Go to https://pypi.org/manage/account/token/
   - Create a new API token
   - Scope: Entire account or specific to pyci-check project
   - Copy the token (starts with `pypi-`)

4. **Add Token to GitHub Secrets**:
   - Go to repository Settings → Secrets and variables → Actions
   - Create new secret: `PYPI_TOKEN`
   - Paste the API token

5. **Configure PyPI Environment** (Optional but recommended):
   - Go to repository Settings → Environments
   - Create environment named `pypi`
   - Add protection rules (e.g., required reviewers)

### Using Trusted Publisher (Recommended)

Instead of API tokens, use GitHub's Trusted Publisher:

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new pending publisher:
   - PyPI Project Name: `pyci-check`
   - Owner: `coseto6125`
   - Repository name: `pyci-check`
   - Workflow name: `release.yml`
   - Environment name: `pypi` (optional)

3. No need to add `PYPI_TOKEN` secret when using Trusted Publisher

## Version Naming Convention

Follow semantic versioning (SemVer):

- **Major** (X.0.0): Breaking changes
- **Minor** (0.X.0): New features, backward compatible
- **Patch** (0.0.X): Bug fixes, backward compatible

Examples:
- `v0.1.0` - Initial release
- `v0.2.0` - Add new features
- `v0.2.1` - Bug fixes
- `v1.0.0` - First stable release

## Pre-release

For beta or release candidate versions:

```bash
git tag -a v0.2.0-beta.1 -m "Release version 0.2.0-beta.1"
git push origin v0.2.0-beta.1
```

The workflow will mark it as a pre-release if the version contains `-alpha`, `-beta`, or `-rc`.

## Troubleshooting

### Build Fails

- Check CI logs on GitHub Actions
- Verify all tests pass
- Ensure dependencies are correctly specified

### PyPI Upload Fails

- Verify `PYPI_TOKEN` secret is correctly set
- Check if version already exists on PyPI
- Ensure package name is available (first release only)

### GitHub Release Not Created

- Verify tag starts with `v` (e.g., `v0.1.0`)
- Check workflow permissions in repository settings
- Ensure `GITHUB_TOKEN` has write permissions

## Manual Release (Emergency)

If automatic release fails:

```bash
# Build package
python -m build

# Check package
twine check dist/*

# Upload to PyPI
twine upload dist/*
```

## Post-Release

1. Announce on social media / forums
2. Update documentation if needed
3. Close related issues/milestones
4. Start working on next version
