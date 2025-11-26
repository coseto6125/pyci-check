#!/bin/bash
# 測試虛擬環境偵測優先順序

set -e

export PYTHONPATH="/home/enor/py_pre_check/src:$PYTHONPATH"

echo "=== 測試虛擬環境偵測優先順序 ==="
echo ""

echo "測試 1: 自動偵測 .venv (應該使用 .venv)"
python3 -m pyci_check.cli imports --quiet 2>&1 | grep "虛擬環境" || echo "未偵測到虛擬環境"
echo ""

echo "測試 2: CLI 參數覆蓋 (應該使用 CLI 指定的路徑)"
python3 -m pyci_check.cli imports --venv . --quiet 2>&1 | grep "虛擬環境"
echo ""

echo "測試 3: 顯示完整資訊"
python3 -m pyci_check.cli imports 2>&1 | head -5
echo ""

echo "✓ 所有測試完成"
