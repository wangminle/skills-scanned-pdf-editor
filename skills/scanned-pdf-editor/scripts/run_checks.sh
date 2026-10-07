#!/usr/bin/env bash
# scanned-pdf-editor regression gate: lint + unit tests.
# Test file is at project-root tests/scripts/, scripts under test are in this dir.
#
# Usage:
#   cd scripts && ./run_checks.sh
#
# Exits non-zero on any failure for CI / pre-commit use.
set -eu

# Resolve script directory (works on macOS/Linux/Windows-Git-Bash)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Find python executable (python3 preferred, fallback to python for Windows)
# Windows 应用商店的 python3 占位符能被 command -v 找到但一运行就退出（rc=49），
# 必须实际执行一次确认可用，不能只看 PATH 命中。
if command -v python3 >/dev/null 2>&1 && python3 -c "" >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1 && python -c "" >/dev/null 2>&1; then
  PY=python
else
  echo "ERROR: python3/python not found in PATH" >&2
  exit 1
fi

echo "== version consistency =="
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
REPO_VER="$(tr -d '[:space:]' < "$PROJECT_ROOT/VERSION")"
SKILL_VER="$(grep -Eo 'V[0-9]+\.[0-9]+\.[0-9]+' "$SCRIPT_DIR/../SKILL.md" | head -1)"
if [[ "$REPO_VER" != "$SKILL_VER" ]]; then
  echo "ERROR: VERSION ($REPO_VER) != SKILL.md version ($SKILL_VER)" >&2
  exit 1
fi
echo "version: $REPO_VER (VERSION == SKILL.md body marker)"

# 若本机安装副本存在，检查版本漂移（不强制失败于未安装；已安装则必须一致）
for DEST in "$HOME/.agents/skills/scanned-pdf-editor" "$HOME/.claude/skills/scanned-pdf-editor"; do
  if [[ -f "$DEST/SKILL.md" ]]; then
    INST_VER="$(grep -Eo 'V[0-9]+\.[0-9]+\.[0-9]+' "$DEST/SKILL.md" | head -1)"
    if [[ "${INST_VER}" != "${REPO_VER}" ]]; then
      echo "ERROR: install copy version drift: ${DEST} is ${INST_VER}, repo is ${REPO_VER}" >&2
      echo "  run: bash \"${SCRIPT_DIR}/sync_install.sh\"" >&2
      exit 1
    fi
    echo "install ok: ${DEST} (${INST_VER})"
  fi
done

echo
# BUG-078：测试文件也曾出现 F821 而门禁假绿——ruff 需同时覆盖 tests/scripts。
echo "== ruff lint (scripts/ + tests/scripts/) =="
# ruff 可能只有模块形式（pip 安装但未入 PATH，如 Windows），与上面的 PY 探测一致做回退
if command -v ruff >/dev/null 2>&1; then
  ruff check . "$PROJECT_ROOT/tests/scripts"
else
  "$PY" -m ruff check . "$PROJECT_ROOT/tests/scripts"
fi
echo "ruff: OK"

echo
echo "== pytest unit tests =="
"$PY" -m pytest "$PROJECT_ROOT/tests/scripts/test_skill.py" -q
echo "pytest unit: OK"

echo
echo "== pytest e2e basic-tasks =="
# BUG-065：E2E 依赖 tests/测试任务/ 与 tests/期望效果/，二者被 .gitignore 排除
# （大体积二进制夹具）。CI / 干净克隆缺这些资产时可跳过；
# BUG-080：显式指定 SCANNED_PDF_RESULTS_BATCH 时必须完整执行，缺资产不能假绿。
E2E_TEST="$PROJECT_ROOT/tests/scripts/test_e2e_basic_tasks.py"
TASKS_DIR="$PROJECT_ROOT/tests/测试任务"
EXPECT_DIR="$PROJECT_ROOT/tests/期望效果"
if [[ ! -f "$E2E_TEST" ]]; then
  if [[ "${SCANNED_PDF_RESULTS_BATCH+x}" == x ]]; then
    echo "ERROR: 显式复测批次缺少 E2E 测试文件: $E2E_TEST" >&2
    exit 1
  fi
  echo "e2e: skipped (test_e2e_basic_tasks.py not in repo — dev-only file)"
elif [[ ! -d "$TASKS_DIR" || ! -d "$EXPECT_DIR" ]]; then
  if [[ "${SCANNED_PDF_RESULTS_BATCH+x}" == x ]]; then
    echo "ERROR: 显式复测批次缺少 tests/测试任务/ 或 tests/期望效果/ 资产" >&2
    exit 1
  fi
  echo "e2e: skipped (test assets tests/测试任务/ or tests/期望效果/ not present)"
  echo "      本地开发：资产就位后自动启用；CI：单元门禁已足够"
else
  "$PY" -m pytest "$E2E_TEST" -q
  echo "pytest e2e: OK"
fi

echo
echo "All checks passed."
