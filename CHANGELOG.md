# Changelog

本仓库版本号格式：`V主.次.修订`（见根目录 `VERSION`）。发布说明条目可附 Build/日期标签。

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

### 功能（V0.1.2 后续增量）

- **DEV-007**：`check_fonts.py` 字体环境检查与安装引导脚本 -- 检查全部注册 CJK 字体安装状态，对缺失字体提供平台特定安装方法（Windows 字体来源说明 + 开源替代 Homebrew/apt 命令），支持 `--source-dir` 从挂载的 Windows 分区自动复制字体文件；SKILL.md 增加第 1.5 步「检查字体环境」
- 单元测试 178 项；`run_checks.sh` ✅

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
