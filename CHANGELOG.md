# Changelog

本仓库版本号格式：`V主.次.修订`（见根目录 `VERSION`）。发布说明条目可附 Build/日期标签。

## V0.1.4-Build0302-20260808

依赖精简、文档同步、测试修复。

### 变更

- **ADJ-009 / OPT-004**：去掉 ReportLab（~8.6M）；`save_image_as_pdf` 改为 PyMuPDF 新建单页 PDF（`new_page` + `insert_image`）；`package` 两种模式均只用 PyMuPDF
- **明确 Python 3.10+**：`requirements.txt` / README / SKILL.md 同步声明；opencv 仍为必装（暂不改为可选）
- **删除 `verify_config.example.json`**：`verify_outputs.py --help` 已内置完整 JSON schema 文档，示例文件冗余且路径来自旧项目结构
- **README 文件结构补全**：补入 V0.1.3 新增的 `align_text.py`、`check_fonts.py`、`scripts_reference.md`；快速开始补入 `check_fonts.py` 和 `align_text.py` 步骤
- **设计文档整理**：合并两份 gitignore 文档（design + implementation）为 `2026-08-06-gitignore加固.md`；新增 `删除移动项目对比分析-2608.md`（手动脚本 vs Skill 逐函数算法对比）

### 测试与门禁

- 修复重复测试方法（`test_render_pdf_page_no_double_rotation` 在两个类中重复定义）；清除 5 处 F401 无用导入 + 3 处 E741 模糊变量名
- 195 passed；ruff 全清；`run_checks.sh` ✅

## V0.1.3-Build0283-20260808

相对 V0.1.2（Build0179）的端到端测试驱动改进：新增工具、字体识别增强、旋转与墨色 Bug 修复、结构调整。

### 新增功能

- **PLN-003 ①**：`align_text.py` 垂直中心对齐工具--按墨迹垂直重心计算对齐 Y，解决不同字体 ascent/descent 差异导致的上下偏移
- **DEV-007**：`check_fonts.py` 字体环境检查与安装引导--检查全部注册 CJK 字体安装状态，对缺失字体提供平台特定安装方法（Windows 字体来源 + 开源替代），支持 `--source-dir` 自动复制；SKILL.md 增加第 1.5 步「检查字体环境」
- **PLN-003 ②**：`identify_font.py` 增加密度交叉验证--额外计算扫描参考字与渲染字的墨迹密度比，NCC 最高但密度差异 >50% 时输出警告（典型场景：仿宋未安装误判为宋体）
- **PLN-003 ③**：`scan_text_fusion.py` 增加 `--preview-ink` 诊断模式--预览最终墨色（含优先级解析：显式 `--ink-color` > `--reference-box` 采样 > 默认）
- **PLN-003 ④**：SKILL.md 增加工具链联动警告--第 2→3 步字体→字号有依赖，不确定的字体结果会级联失败

### 修复

- **BUG-052 / BUG-058**：`render_pdf_page` 旋转问题。BUG-052 初修传入 `page.get_rotation()`，BUG-058 发现这是双重旋转（PDFium `render()` 内部已应用 /Rotate，rotation 参数是附加旋转）→ 改为 `rotation=0`；用真实 Rotate=270 扫描件验证 pypdfium2 与 fitz 方向一致（MAE=3.6）
- **BUG-053**：`scan_text_fusion.py --reference-box` 静默覆盖 `--ink-color` → `--ink-color` default 改为 None，`run()` 实现三级优先（显式 > 采样 > 默认）
- **BUG-054**：根 README.md 残留 evals 引用（目录树、检查命令、死链）→ 全部清除
- **BUG-055**：skill README.md 自测命令相对路径错误（`../../` 少一层）→ 改为 `../../../`
- **BUG-056**：安装目录（`~/.agents/skills`、`~/.claude/skills`）未同步本轮改动 → rsync 镜像同步，diff -rq 校验一致
- **BUG-057**：SKILL.md 膨胀至 579 行超 500 行约束 → 工具参考节下沉至 `references/scripts_reference.md`，SKILL.md 降至 461 行
- **BUG-059**：`font_registry.find_font` 注册名子串匹配过宽（`"Song"` → 仿宋）→ 新增 `_name_tokens()` token 精确/前缀匹配
- **BUG-060**：`scan_text_fusion` 接受 NaN/负数 float 参数 → 渲染前统一校验四参数有限且非负，parser.error 退出码 2
- **BUG-061**：框坐标未校验 ⊂ 图像 → `validate_box` / `parse_box` / `parse_ref` 增加可选 image_size 越界校验
- **BUG-062**：`check_fonts.py --filter` 尾逗号产生空串导致过滤失效 → strip + 滤空段

### 结构调整

- 移除 `evals/` 目录（确定性 eval 脚手架已由单元测试覆盖）
- `test_skill.py` 迁至 `tests/scripts/`
- `docs/plans` 迁至 `design/plans`
- 新增 `references/scripts_reference.md`（完整工具参数表，从 SKILL.md 下沉）

### 测试与门禁

- 单元测试 195 项（178 原 + 17 新增 BUG-058～062 回归）；`run_checks.sh` ✅；ruff 全清

### 文档

- 版本升至 V0.1.3；SKILL.md 模式 D 流程增加第 1.5 步（字体环境检查）和第 5 步（垂直对齐）；工具链联动警告；density 交叉验证说明

## V0.1.2-Build0179-20260807

相对 V0.1.1（Build0178）的边界硬化与文档同步：

### 修复（边界输入 / 验证器）

- **BUG-036**：`_select_page_image_xref` 按 xref 去重后再评分，避免同图多次放置时 strict 误报
- **BUG-037 / BUG-050 / BUG-051**：`parse_box` / `identify_*` 的 `--ref` / `scan_text_fusion` 框参数拒绝负坐标与倒置框，避免 numpy/PIL 静默回绕
- **BUG-038**：`move_block` / `move_and_clear` 补 x 方向越界校验（与 y 对称）
- **BUG-039**：`verify` 的 blank/preserve 框与图像无交集时失败，不再假绿
- **BUG-040**：`replace_with_donor` 校验 `donor_box` / `reference_box` 完整落在各自图像内
- **BUG-041**：`verify_outputs` 尺寸不一致短路归档；单用例异常不跳过后续用例
- **BUG-042**：evals contrast 对照检查返回码与输出文件，避免 BEH-006 假绿
- **BUG-043**：`identify_font` 仅一个已装候选时判「参考」，不抑制安装提示
- **BUG-044**：`font_registry.find_font` 注册名匹配大小写不敏感
- **BUG-045 / BUG-046**：`render_halo` 退化输入守卫；`feather` 宽/高≤2 返回硬边；CLI 解析错误清晰 exit 2；中位数 `round`；pdfium 句柄关闭等
- **BUG-047**：触发 eval 校验正例 keywords 须出现在 SKILL.md description
- **BUG-048 / BUG-049**：`replace_pdf_image` / `verify_outputs` pymupdf 路径 try/finally 关闭句柄；`page_index` 越界报错

### 测试与门禁

- 单元测试 159 项；`scripts/run_checks.sh`；确定性 evals 17/17

### 文档

- 版本升至 V0.1.2；`SKILL.md` / README 同步非负坐标、move x 越界、donor 框、feather 小尺寸、单候选字体判定、`page-index` 范围等

## V0.1.1-Build0178-20260806

相对 V0.1.0（Build0177）的硬化与文档同步：

### 修复（边界输入）

- **BUG-020～032**：越界移动、零对比度供体、插值框裁剪、贴入越界、`--page-size` 非法、空 ROI / 子目录输出、evals 合约、`ruff` 覆盖 `evals/`、倒置框、`feather<=0`、`page_size` 校验、`smooth_noise` 退化、多图空 rect 等
- **BUG-033**：`move_block` / `move_and_clear` 拒绝倒置或零高 `content_x` / `source_y`；CLI 增加 `parse_ordered_pair`
- **BUG-034**：evals `check_differs_from_contrast` 要求主跑为非 `contrast` 的 `normalize-mode`
- **BUG-035**：`package --dpi <= 0` 清晰报错并退出码 2

### 测试与门禁

- 单元测试约 106 项；`scripts/run_checks.sh`（ruff scripts+evals + pytest）；确定性 evals 17/17

### 文档

- `SKILL.md` / README 同步坐标顺序、`page-size` / `dpi` / `--feather` 行为说明
- 本 changelog 与根目录 `VERSION` 文件

## V0.1.0-Build0177-20260806

首个对外标注版本：四模式编辑 skill、CLI、确定性 eval 脚手架与任务台账。
