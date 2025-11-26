check_python_command_exist() {
    if ! [ -x "$(command -v uv)" ]; then
        echo "uv not installed. Install it with: pip install uv"
        exit 1
    fi
}


check_all_format() {
    echo "$(date): Checking all Python files with ruff..."
    
    # 檢查環境是否為 CI
    if [ -n "${CI:-}" ] || [ -n "${GITHUB_ACTIONS:-}" ]; then
        # CI 環境：只檢查，不修復
        echo "$(date): Running in CI mode - check only, no auto-fix"
        git ls-files -- "*.py" | grep -v -E "(starlette_app\.py|sanic_app\.py)" | xargs uv run ruff check --config pyproject.toml --ignore E902
        exit_status=$?
        
        if [ $exit_status -ne 0 ]; then
            echo "$(date): Lint errors found in CI. All files should be properly formatted before pushing."
            echo "$(date): Please run 'ruff check --fix' locally and commit the fixes."
            exit $exit_status
        fi
        
        echo "$(date): All files passed lint checks in CI."
    else
        # 本地環境：檢查並修復
        echo "$(date): Running in local mode - check and auto-fix"
        git ls-files -- "*.py" | grep -v -E "(starlette_app\.py|sanic_app\.py)" | xargs uv run ruff check --fix --config pyproject.toml --ignore E902
        exit_status=$?
        
        # 檢查是否有修改的檔案
        if [ -n "$(git status --porcelain)" ]; then
            echo "$(date): Files were auto-fixed by ruff. Please review and commit the changes before pushing."
            echo "Modified files:"
            git status --porcelain
            echo ""
            echo "Run the following commands to commit the fixes:"
            echo "  git add -A"
            echo "  git commit -m 'style: 自動修復程式碼格式 (ruff)'"
            echo "  git push"
            exit 1
        fi
        
        if [ $exit_status -ne 0 ]; then
            echo "$(date): Some lint errors could not be auto-fixed. Please fix them manually."
            exit $exit_status
        fi
        
        echo "$(date): All files checked and no fixes needed."
    fi
}

check_python_imports() {
    echo "$(date): Checking Python import dependencies..."
    # 添加 src 和 test 目錄到 PYTHONPATH，讓導入檢查能找到所有模組
    PYTHONPATH="$PWD/src:$PWD/test:$PYTHONPATH" uv run python3 ci/check_python_import.py
    import_exit_status=$?
    if [ $import_exit_status -ne 0 ]; then
        echo "$(date): Import errors found. Please fix them before committing."
        exit $import_exit_status
    fi
    echo "$(date): Python import dependencies check passed."
}

check_python_syntax() {
    echo "$(date): Checking Python syntax..."
    uv run python3 ci/check_python_syntax.py
    syntax_exit_status=$?
    if [ $syntax_exit_status -ne 0 ]; then
        echo "$(date): Syntax errors found. Please fix them before committing."
        exit $syntax_exit_status
    fi
    echo "$(date): Python syntax check passed."
}

# Check commands exist
check_python_command_exist uv

# Check the format
check_all_format

# # Check Python imports
check_python_imports

# # Check Python syntax
check_python_syntax