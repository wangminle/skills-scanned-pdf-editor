#!/usr/bin/env bash
# 将仓库 skills/scanned-pdf-editor 镜像同步到本机 agent 可发现目录。
# 源：仓库内 skills/scanned-pdf-editor（权威版本）
# 目标：~/.agents/skills/scanned-pdf-editor、~/.claude/skills/scanned-pdf-editor
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION_FILE="$(cd "$SCRIPT_DIR/../../.." && pwd)/VERSION"

if [[ ! -f "$SRC/SKILL.md" ]]; then
  echo "ERROR: 源目录缺少 SKILL.md: $SRC" >&2
  exit 1
fi

EXCLUDES=(
  --exclude '.pytest_cache'
  --exclude '.ruff_cache'
  --exclude '__pycache__'
  --exclude '.DS_Store'
  --exclude 'tests'
)

sync_one() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  rsync -a --delete "${EXCLUDES[@]}" "$SRC/" "$dest/"
  echo "synced -> $dest"
}

sync_one "$HOME/.agents/skills/scanned-pdf-editor"
sync_one "$HOME/.claude/skills/scanned-pdf-editor"

if [[ -f "$VERSION_FILE" ]]; then
  echo "repo VERSION: $(tr -d '[:space:]' < "$VERSION_FILE")"
fi
echo "skill version: $(grep -Eo 'V[0-9]+\.[0-9]+\.[0-9]+' "$SRC/SKILL.md" | head -1)"
echo "OK: install copies match repo skill."
