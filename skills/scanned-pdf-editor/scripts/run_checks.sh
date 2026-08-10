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
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "ERROR: python3/python not found in PATH" >&2
  exit 1
fi

echo "== version consistency =="
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
REPO_VER="$(tr -d '[:space:]' < "$PROJECT_ROOT/VERSION")"
SKILL_VER="$(grep -E '^version:' "$SCRIPT_DIR/../SKILL.md" | head -1 | awk '{print $2}' | tr -d '[:space:]')"
if [[ "$REPO_VER" != "$SKILL_VER" ]]; then
  echo "ERROR: VERSION ($REPO_VER) != SKILL.md version ($SKILL_VER)" >&2
  exit 1
fi
echo "version: $REPO_VER (VERSION == SKILL.md)"

# 若本机安装副本存在，检查版本漂移（不强制失败于未安装；已安装则必须一致）
for DEST in "$HOME/.agents/skills/scanned-pdf-editor" "$HOME/.claude/skills/scanned-pdf-editor"; do
  if [[ -f "$DEST/SKILL.md" ]]; then
    INST_VER="$(grep -E '^version:' "$DEST/SKILL.md" | head -1 | awk '{print $2}' | tr -d '[:space:]')"
    if [[ "${INST_VER}" != "${REPO_VER}" ]]; then
      echo "ERROR: install copy version drift: ${DEST} is ${INST_VER}, repo is ${REPO_VER}" >&2
      echo "  run: bash \"${SCRIPT_DIR}/sync_install.sh\"" >&2
      exit 1
    fi
    echo "install ok: ${DEST} (${INST_VER})"
  fi
done

echo
echo "== ruff lint (scripts/) =="
ruff check .
echo "ruff: OK"

echo
echo "== pytest unit tests =="
"$PY" -m pytest "$PROJECT_ROOT/tests/scripts/test_skill.py" -q
echo "pytest unit: OK"

echo
echo "== pytest e2e basic-tasks =="
# BUG-065：E2E 依赖 tests/测试任务/ 与 tests/期望效果/，二者被 .gitignore 排除
# （大体积二进制固件）。test_e2e_basic_tasks.py 本身也是 skill 开发态文件，
# 不随仓库分发。CI / 干净克隆缺这些资产时不应让门禁失败，故改为可选门禁：
# 文件与资产都在才跑；否则跳过。
E2E_TEST="$PROJECT_ROOT/tests/scripts/test_e2e_basic_tasks.py"
TASKS_DIR="$PROJECT_ROOT/tests/测试任务"
EXPECT_DIR="$PROJECT_ROOT/tests/期望效果"
if [[ ! -f "$E2E_TEST" ]]; then
  echo "e2e: skipped (test_e2e_basic_tasks.py not in repo — dev-only file)"
elif [[ ! -d "$TASKS_DIR" || ! -d "$EXPECT_DIR" ]]; then
  echo "e2e: skipped (test assets tests/测试任务/ or tests/期望效果/ not present)"
  echo "      本地开发：资产就位后自动启用；CI：单元门禁已足够"
else
  "$PY" -m pytest "$E2E_TEST" -q
  echo "pytest e2e: OK"
fi

echo
echo "All checks passed."
