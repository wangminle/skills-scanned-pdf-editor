# skills-scanned-pdf-editor

**Version: V0.1.2** · see [`VERSION`](VERSION) / [`CHANGELOG.md`](CHANGELOG.md)

[English](#english) | [中文](#中文)

---

## English

Local pixel-level editing for **scanned PDFs and scan images**: remove content, move blocks, replace text with native donor patches, or add text with scan-style fusion—without generative redraw of the whole page.

This repository publishes the Agent Skill `scanned-pdf-editor` plus its design notes, scripts, and evaluation scaffolding. For day-to-day CLI recipes and parameter tables, see [`skills/scanned-pdf-editor/README.md`](skills/scanned-pdf-editor/README.md) and [`SKILL.md`](skills/scanned-pdf-editor/SKILL.md).

### Why this exists

Two earlier workflows each solved half of the problem:

| Prior work | Strength | Gap |
| --- | --- | --- |
| Add / fusion pipeline | Font & size ID, scan-style text fusion | No remove / move / replace |
| Delete / move / replace pipeline | Ink-aware inpaint, native pixel migration, verify | Not skill-packaged; no add path |

This repo unifies them into one skill so agents (and humans) can run the full edit set under one methodology: **prefer native scan pixels; fall back to font synthesis only when needed; keep edits local and auditable**.

### Intended use

**Use when** you have the right to edit the document and the change is truthful—for example draft revision, filling your own forms/templates, or restoring internal scanned materials.

**Do not use** to forge, conceal edits, or mislead third parties; on unauthorized documents; or for born-digital PDFs (use a normal PDF editor). Do not redraw entire pages—each pass should touch only target regions.

The skill performs pixel synthesis only. Authorization and legal disclosure remain the user’s responsibility.

### Design principles

1. Local pixel compositing—no generative full-page redraw  
2. Only the target region changes; other pixels stay intact  
3. Native donor patches first; font synthesis second  
4. Sample color/texture from nearby original ink, not guesswork  
5. Small iterations with crop previews  
6. Keep process artifacts for auditability  

Two technical routes share the same goal (“looks like the original scan”):

- **Route A — native pixel migration**: remove / move / replace / compound  
- **Route B — font synthesis + fusion**: add text (`identify_*` → `scan_text_fusion.py`)

### Repository layout

```
.
├── README.md                 # This file (repo overview)
├── VERSION                   # Current version (V0.1.2)
├── CHANGELOG.md              # Release notes
├── LICENSE                   # MIT
├── CLAUDE.md                 # Session conventions for agents
├── task-list.md              # Project task ledger
├── design/                   # Research & skill design analysis
├── docs/                     # Implementation / ops plans
└── skills/
    └── scanned-pdf-editor/   # The publishable Agent Skill
        ├── SKILL.md          # Agent instructions (source of truth for workflow)
        ├── README.md         # Skill-local quick start & script map
        ├── scripts/          # CLI tools & libraries
        ├── references/       # Pipeline methodology
        ├── evals/            # Deterministic checks + real-model eval guide
        └── verify_config.example.json
```

There is **no HTTP/RPC service**. The programmable surface is CLI scripts (and the Python modules they call).

### Install the skill

Copy or symlink the skill into a discoverable skills directory, for example:

```bash
# User-level (Codex / common agent layouts)
ln -s "$(pwd)/skills/scanned-pdf-editor" ~/.agents/skills/scanned-pdf-editor

# Claude Code user skills
ln -s "$(pwd)/skills/scanned-pdf-editor" ~/.claude/skills/scanned-pdf-editor
```

Workspace-level installs (e.g. `<repo>/.agents/skills/`) also work if your agent searches the project tree. Keep the repo’s `skills/` tree as the source of truth.

### Dependencies

```bash
cd skills/scanned-pdf-editor/scripts
pip3 install -r requirements.txt
```

Core stack: OpenCV, Pillow, NumPy, pypdfium2, PyMuPDF, ReportLab (`pytest` / `ruff` for checks).

### CLI overview

All commands below assume `cd skills/scanned-pdf-editor`.

**Unified edit CLI** — `scripts/scan_edit_ops.py`:

| Subcommand | Role |
| --- | --- |
| `remove` | Delete regions (`telea` or `interpolate`) |
| `move` | Shift a native pixel band and clean residue |
| `replace` | Paste a native donor glyph/word patch |
| `compound` | Copy → clear multiple boxes → paste (multi-step move) |
| `package` | Wrap result PNG as PDF (new page or replace embedded image / OCR-preserving) |
| `verify` | Quick pixel checks vs source |

```bash
python3 scripts/scan_edit_ops.py remove \
  --source page.png --boxes "x1,y1,x2,y2" --output out.png

python3 scripts/scan_edit_ops.py move \
  --source page.png --content-x 330,2250 --source-y 1735,3070 \
  --shift-y 265 --output out.png

python3 scripts/scan_edit_ops.py replace \
  --source page.png --donor-box "..." --remove-boxes "..." \
  --destination x,y --reference-box "..." --output out.png

python3 scripts/scan_edit_ops.py package \
  --source page_final.png --output final.pdf --original-pdf source.pdf
```

**Add-text path** (Route B):

```bash
python3 scripts/identify_font.py --source page.png --ref 字=x1,y1,x2,y2
python3 scripts/identify_size.py --source page.png --font <name-or-path> --ref 字=x1,y1,x2,y2
python3 scripts/scan_text_fusion.py --source page.png --text "…" \
  --position x y --font "仿宋" --font-size 32 --scan-style clean
```

**Config-driven verification**:

```bash
python3 scripts/verify_outputs.py --config verify_config.example.json
python3 scripts/verify_outputs.py --config verify_config.example.json --reproduce
```

Full flags and workflow steps: [`skills/scanned-pdf-editor/SKILL.md`](skills/scanned-pdf-editor/SKILL.md).

### Python “API” (library use)

Scripts under `scripts/` are importable modules—there is no separate packaged SDK yet. Typical entry points:

| Module | Use |
| --- | --- |
| `scan_edit_utils.py` | Render, masks, inpaint, move/replace helpers, PDF wrap |
| `scan_edit_ops.py` | CLI orchestration over those helpers |
| `scan_text_fusion.py` | Fusion / halo rendering for added text |
| `font_registry.py` | Cross-platform CJK font resolve |
| `identify_font.py` / `identify_size.py` | Measurement CLIs |
| `verify_outputs.py` | JSON-driven verification |

Prefer calling the CLIs from agents; import helpers only when embedding in your own pipeline.

### Checks & evaluation

```bash
cd skills/scanned-pdf-editor/scripts
./run_checks.sh          # ruff + pytest
python3 -m pytest test_skill.py -v
cd ../evals && python3 run_evals.py   # deterministic keyword/CLI smoke (not a live model)
```

Real with-skill / without-skill model evaluation is documented in [`evals/EVAL.md`](skills/scanned-pdf-editor/evals/EVAL.md) and may require local test PDFs.

### License

[MIT](LICENSE) © 2026 fenix-wangminle

---

## 中文

面向**扫描版 PDF / 扫描件图片**的局部像素级编辑：删除内容、移动正文块、用原生供体替换文字、或补录并做扫描质感融合——**不**对整页做生成式重绘。

本仓库发布 Agent Skill `scanned-pdf-editor`，并附带设计分析、脚本与评测脚手架。日常 CLI 示例与参数表请看 [`skills/scanned-pdf-editor/README.md`](skills/scanned-pdf-editor/README.md) 与 [`SKILL.md`](skills/scanned-pdf-editor/SKILL.md)，本文件只做仓库级说明。

### 设计初衷

此前两条工作流各解一半问题：

| 既有能力 | 长处 | 缺口 |
| --- | --- | --- |
| 增加 / 融合管线 | 字体字号识别、扫描融合 | 无删除 / 移动 / 替换 |
| 删除 / 移动 / 替换管线 | 墨迹修补、原生像素迁移、验证 | 未 skill 化；无补录路径 |

本仓库将其统一为一个 skill，让 Agent（与人工）在同一方法论下覆盖四类操作：**优先迁移原生扫描像素；必要时才字体合成；改动局部、过程可留痕**。

### 适用与不适用

**适用**：你对该文书有编辑权，且修改内容真实——如草稿修订、自有表单/模板填写、内部扫描材料数字化复原。

**不适用**：伪造、隐瞒修改或误导第三方；未获授权的文书；原生电子 PDF（请用常规编辑器）；整页重绘（每轮只改目标区域）。

技能只做像素合成；授权与合规披露由使用者自行负责。

### 设计原则（摘要）

1. 本地像素合成，不做整页生成式重绘  
2. 仅目标区变化，远处像素保持原样  
3. 原生供体优先，字体合成为后备  
4. 颜色/质感从邻近原墨取样  
5. 小步迭代，先看裁剪预览  
6. 过程产物可追溯  

技术上两条路线目标一致（「看起来像原扫描的一部分」）：

- **路线 A — 原生像素迁移**：删除 / 移动 / 替换 / 复合  
- **路线 B — 字体合成 + 融合**：补录文字（`identify_*` → `scan_text_fusion.py`）

### 仓库结构

```
.
├── README.md                 # 本文件（仓库总览）
├── VERSION                   # 当前版本号（V0.1.2）
├── CHANGELOG.md              # 版本说明
├── LICENSE                   # MIT
├── CLAUDE.md                 # Agent 会话约定
├── task-list.md              # 任务台账
├── design/                   # 研究与 skill 设计分析
├── docs/                     # 实施 / 运维计划
└── skills/
    └── scanned-pdf-editor/   # 可发布的 Agent Skill
        ├── SKILL.md          # Agent 工作流说明（权威文档）
        ├── README.md         # Skill 内快速开始与脚本索引
        ├── scripts/          # CLI 与工具库
        ├── references/       # 管线方法论
        ├── evals/            # 确定性自检 + 真实模型评测指南
        └── verify_config.example.json
```

**没有 HTTP/RPC 服务**。可编程面是 CLI 脚本（及其调用的 Python 模块）。

### 安装 Skill

将技能目录拷贝或软链到可发现路径，例如：

```bash
ln -s "$(pwd)/skills/scanned-pdf-editor" ~/.agents/skills/scanned-pdf-editor
ln -s "$(pwd)/skills/scanned-pdf-editor" ~/.claude/skills/scanned-pdf-editor
```

工作区级安装（如 `<repo>/.agents/skills/`）在 Agent 会扫描项目树时同样可用。请以本仓库 `skills/` 为源码真相源。

### 依赖

```bash
cd skills/scanned-pdf-editor/scripts
pip3 install -r requirements.txt
```

核心依赖：OpenCV、Pillow、NumPy、pypdfium2、PyMuPDF、ReportLab（检查用 `pytest` / `ruff`）。

### CLI 概览

以下命令默认在 `skills/scanned-pdf-editor` 目录执行。

**统一编辑 CLI** — `scripts/scan_edit_ops.py`：

| 子命令 | 作用 |
| --- | --- |
| `remove` | 删除区域（`telea` / `interpolate`） |
| `move` | 移动原生像素带并清理残留 |
| `replace` | 粘贴原生供体字块 |
| `compound` | 复制 → 多框清除 → 粘贴（复合上移） |
| `package` | 将结果图封装为 PDF（新建页或替换内嵌图 / 可保留 OCR） |
| `verify` | 相对源图的快速像素检查 |

```bash
python3 scripts/scan_edit_ops.py remove \
  --source page.png --boxes "x1,y1,x2,y2" --output out.png

python3 scripts/scan_edit_ops.py package \
  --source page_final.png --output final.pdf --original-pdf source.pdf
```

**补录文字（路线 B）**：

```bash
python3 scripts/identify_font.py --source page.png --ref 字=x1,y1,x2,y2
python3 scripts/identify_size.py --source page.png --font <名或路径> --ref 字=x1,y1,x2,y2
python3 scripts/scan_text_fusion.py --source page.png --text "…" \
  --position x y --font "仿宋" --font-size 32 --scan-style clean
```

**配置驱动验证**：

```bash
python3 scripts/verify_outputs.py --config verify_config.example.json
python3 scripts/verify_outputs.py --config verify_config.example.json --reproduce
```

完整参数与工作流见 [`SKILL.md`](skills/scanned-pdf-editor/SKILL.md)。

### Python「API」（库用法）

`scripts/` 下模块可直接 import，尚无独立发布的 SDK。常用入口：

| 模块 | 用途 |
| --- | --- |
| `scan_edit_utils.py` | 渲染、蒙版、修补、移动/替换、PDF 封装 |
| `scan_edit_ops.py` | 上述能力的 CLI 编排 |
| `scan_text_fusion.py` | 补录融合 / 晕染 |
| `font_registry.py` | 跨平台 CJK 字体解析 |
| `identify_font.py` / `identify_size.py` | 测量 CLI |
| `verify_outputs.py` | JSON 驱动验证 |

Agent 场景优先调 CLI；嵌入自有管线时再 import 工具函数。

### 检查与评测

```bash
cd skills/scanned-pdf-editor/scripts
./run_checks.sh
python3 -m pytest test_skill.py -v
cd ../evals && python3 run_evals.py   # 确定性自检，不跑真实模型
```

真实 with-skill / without-skill 评测见 [`evals/EVAL.md`](skills/scanned-pdf-editor/evals/EVAL.md)，可能需要本地测试 PDF。

### 许可证

[MIT](LICENSE) © 2026 fenix-wangminle
