#!/usr/bin/env bash
# scanned-pdf-editor 回归门禁：静态检查 + 单元测试。
#
# 用法：
#   cd scripts && ./run_checks.sh
#
# 任一步失败即以非零码退出，便于纳入 CI / 提交前自检。
set -euo pipefail

cd "$(dirname "$0")"

echo "── ruff 静态检查（scripts + evals，BUG-027：此前只查 scripts/ 漏掉 evals/）──"
ruff check ..
echo "ruff: 通过"

echo
echo "── pytest 单元测试 ──"
python3 -m pytest test_skill.py -q
echo "pytest: 通过"

echo
echo "✅ 全部检查通过"
