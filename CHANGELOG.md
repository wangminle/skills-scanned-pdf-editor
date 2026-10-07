# Changelog

本仓库版本号格式：`V主.次.修订`（见根目录 `VERSION`）。发布说明条目可附 Build/日期标签。

## V0.1.7-20261007

修复 2026-10-06 全部 5 个 GitHub issue（BUG-070～074）及其修复过程中发现的 4 项回归（BUG-075～078），
主题是**输入校验与静默失败**：非法坐标/参数一律显式报错，不再"看似成功、实际没删/删错/假绿"。

### 修复与增强

- **BUG-070（#1）**：`remove` 越界/倒置框此前被 numpy 静默截断（完全越界则空切片）、负坐标按负索引绕行，均 rc=0。新增共享守卫 `validate_boxes_in_bounds`，telea/interpolate 两模式统一在入口拦截
- **BUG-071/076（#2）**：`move` 自动清理框改为**按方向**取「原块中未被新块覆盖的残留」（上移清原块底部、下移清原块顶部），并始终钳制在原块 `[y1,y2)` 内——负位移不再因倒置空框漏清原位，位移超过块高也不再擦掉原块之外的保留内容；手动清理框增加空框/倒置守卫
- **BUG-075**：`shift-y 0` 回归为合法无操作——自动清理列表为空（`auto` 返回原图零蒙版），`add` 仍执行手动框；不再误触空框守卫报错
- **BUG-077**：`remove_regions_telea` 先将 `boxes` 物化为列表再复用于校验与蒙版构建——生成器/迭代器输入不再被校验耗尽导致 ink/full 两模式静默零删除
- **BUG-072（#3）**：`scan_text_fusion --fusion-variants` 每档须为有限正数（>0），`nan`/0/负值直接拒绝，不再产出黑图或裸异常
- **BUG-073（#4）**：`verify_outputs` 的 `preserve_box` 非法（负值/倒置）或越出图外直接计入验证错误，消除"非法框假绿"
- **BUG-074（#5）**：干净克隆缺少可选测试夹具/资产时相关用例统一 skip，不再固定三红（无夹具快照 257 passed/6 skipped 验证）
- **BUG-078**：测试注解的 `subprocess` 提至模块作用域（消除 2 处 F821）；`run_checks.sh` 的 ruff 扩展覆盖 `tests/scripts`，并加固 Windows 应用商店 `python3` 占位符探测与 `python -m ruff` 回退
- **BUG-079/081**：PyMuPDF `replace_image` 留下内容相同、未绘制的资源副本时，strict 平局误报阻断 task004/005 封装。现仅在并列图无蒙版、RGB严格相同且能证明只有一个候选实际绘制时放行，选择实际绘制的xref；蒙版、真实双绘制及无法证明的复杂资源结构保持拒绝。修复原“同RGB任选”可能替换无可见效果的问题，共享API与CLI使用相同守卫
- **BUG-082**：task003原15% golden阈值会放过完全未编辑源PDF（10.616612%）；新增真实原样交付负例并校准阈值至9%，正确交付7.670928%继续通过
- **BUG-080**：golden回归同时识别 `taskNNN_result.pdf` 与旧 `final.pdf`，绑定同一最新日期批次（可用 `SCANNED_PDF_RESULTS_BATCH=YYYYMMDD` 显式指定），本批缺任务、缺交付/期望文件及双交付名均失败，不再静默检查历史结果；显式批次下 `run_checks.sh` 缺测试文件/资产也失败。固定300dpi回渲、golden双线性缩放，与复测报告统一口径

### 测试与门禁

- issue原始场景与边界回归均通过，另新增17项 BUG-080/081/082 回归：全套 **267单元 + 23 E2E = 290 passed / 16 subtests**；显式绑定20261007批次的 `run_checks.sh` 全绿
- 五项标准任务已全链复测并独立审计；本轮又重跑提取/封装门禁。task001/004/005与历史交付内嵌图严格差异=0；task002严格不同1992像素（差值大于10的1323像素，约0.0152%），OCR702字符保持；task003严格不同11886像素（差值大于10的265像素，符合清理区钳制）。task001/002为降级字体，只能称基本可用；golden阈值通过不等于像素级一致。详见本地 `tests/results/20261007-对比报告.md`（CHK-048/049）
- 文档同步（DOC-031）：SKILL.md 坐标约定/remove 表/move 自动清理语义/验证表、scripts_reference 对应四处、根 README 与 skill README 版本及门禁描述

## V0.1.6-20260816

按 20260816 全套复测（[[TST-028]] [[CHK-042]]）完成扫描件编辑的安全提取、自动测量、封装门禁、逐页审计闭环，并修复模式 D 分辨率、OCR 定位、字体注册表和 BUG-069 缺口。

### 核心增强

- 新增 `extract`：统一用 `fitz.Pixmap(document, xref)` 解码内嵌整页图，PNG 回读必须 diff=0；默认执行替换回封、300dpi 回渲、未修改页哈希三项往返检查；`export-page` 保留为兼容别名
- `package --original-pdf` 改为候选临时文件门禁：内嵌编辑图回读 diff=0、所有未修改页原生 RGB 像素哈希一致、MuPDF 300dpi 掩模双回渲允许区外变化=0 后才覆盖输出
- 新增 `measure_layout.py lines/ink-bbox/gap/shift`，JSON 报告行带、字框、字距、碰撞、基线和移动量
- `replace` 自动输出 `placement_analysis`，并提供碰撞、最小字距和基线偏差可选阻断参数
- 空白残影默认同时检查亮度 180/220/240，JSON 配置支持各阈值独立上限，不再写死 180
- `verify_outputs.py` 默认比较所有未修改页的内嵌整页图像素哈希
- `move --cleanup-mode auto/add/replace` 明确自动框、追加框、替代框语义，拒绝歧义组合

### 质量与兼容性

- 允许区由黑底/白框掩模 PDF 双回渲映射，正确覆盖 `/Rotate` 与非等比 XObject 放置，不靠尺寸比例猜坐标；审计统一使用与 `fitz.Pixmap` 提取同源的 MuPDF，避免 PDFium 对 JPEG/PNG 容器走不同色彩路径造成全页假差异
- Skill frontmatter 仅保留 `name` / `description`，符合技能结构校验规范
- Windows 字体安装目标优先用户级目录；`check_fonts --source-dir` 无论字体是否已安装都验证路径合法性
- 新增 7 项闭环单测，并以真实三页合同 PDF 执行提取、未修改页哈希和回渲回归

### 复测修复与增强

- **BUG-069**：`scan_text_fusion --output` 带路径成分不再静默嵌套落盘到 `output_dir/<原路径>`，CLI 层拒绝（退出码 2，提示改用 --output-dir）
- **字体注册表（ADJ-011）**：新增 `Songti SC Light/Regular`（Songti.ttc 字重索引 3/6）、`STHeiti Light/Medium`、`Noto Sans SC (NotoSansSC.ttf)`；「Songti SC」裸名由 index 0（实为 Black）改指 Regular——macOS 本机可用候选 3→8 个，细笔画文书（仿宋系）识别不再被迫用 Black 字重
- **identify_font --candidates**：支持 `名称=文件名[索引]` 指定 ttc 字重（旧实现硬编码 0，多字重家族坍缩同分）
- **SKILL.md（DOC-027）**：模式 D 增加「分辨率 × 封装」分支表（内嵌非 200dpi 且保 OCR 层 → export-page 原生分辨率融合 + ink-color 压深，堵 200dpi 融合与 package 尺寸校验的死锁）；新增「内容定位（先 OCR 后像素）」章节（tesseract chi_sim 行映射 + locate_content 双证据、短行 min-ink-ratio 降阈值提示）；`--allow-degraded` 三步决策树；验证表改「封装内嵌图 diff=0 为无损判据、300dpi 回渲仅校验朝向版式」；`--crop-box` 示例修正（scan_edit_ops 逗号 / scan_text_fusion 空格）
- **basic-tests-readme**：task002 改内嵌原生分辨率路线（原 200dpi 步骤在封装步必失败）；task001 补 PyMuPDF 渲染替代（无 poppler 环境）；通用注意事项补定位双证据/短行/crop-box 三条
- **scripts_reference**：--output 契约、Songti 多字重映射、--candidates 索引语法
- **文档一致性收尾（DOC-030）**：scripts_reference 补全 remove/move/replace/compound/verify 完整参数表、identify_size 参数表与 verify_outputs 节（`render_backend` 默认 `pymupdf`）；SKILL.md 短行阈值默认值修正（`locate_content --min-ink-ratio` 实为 0.01）、模式 D 分支表改推荐 `extract`、清理 task007 残留引用；scan_edit_ops 模块说明与 CLI 总描述补全全部子命令（含 extract/export-page 别名）；根 README 移除已删除的 verify_config.example.json（目录树 + 示例命令）、中文检查节对齐 run_checks 实际内容；skill README 门禁注释同步

### 测试与门禁

- 新增 TestBugFix069_OutputPathRejected 4 项 + 字体注册表/candidates 索引 2 项；全套 `run_checks.sh` ✅

## V0.1.5-Build0343-20260810

按 basic-tests 复盘优先修复：字体回填、内嵌导出/旋转、质量门禁、定位模块、E2E 门禁；追加独立审查发现的 4 项门禁/正确性缺陷修复。

### 修复与增强

- **BUG-063**：`font_registry.find_font` 支持完整注册名精确匹配与多词 token 全集匹配；`identify_font` 输出 `回填参数: --font "…"` 可直接粘贴
- **export-page**：导出内嵌整页原生像素；`--as-displayed` 按 `/Rotate` 转显示朝向；`package --original-pdf` 自动旋回内嵌朝向，拒绝尺寸不匹配的重采样回封
- **质量门禁**：`identify_font` 密度比超出 `[0.67,1.5]` 或置信度不足时默认退出码 3；`--allow-degraded` 显式降级
- **locate_content.py**：行带 / 字框 / 供体尺寸候选定位
- **版本同步**：`sync_install.sh` + `run_checks.sh` 校验仓库 VERSION 与安装副本一致
- **E2E**：`tests/scripts/test_e2e_basic_tasks.py` 覆盖五项 task 的 export/定位/删除移动供体冒烟
- **BUG-065**：`run_checks.sh` E2E 段改为可选门禁——测试文件/资产缺失（CI、干净克隆）时 skip 而非失败；git add 三个此前未跟踪的 V0.1.5 新文件（`locate_content.py`/`sync_install.sh`/`test_e2e_basic_tasks.py`）
- **BUG-066**：`prepare_image_for_pdf_replace` 新增 `source_orient` 参数（`displayed`/`embedded`/`auto`），停止仅凭尺寸猜朝向——`/Rotate=180` 与正方形图尺寸无法区分朝向时 `auto` 报错（exit 2）而非静默封错方向；CLI `package --source-orient`
- **BUG-067**：`locate_content.find_donor_candidates` 新增行内连通域聚类（`_cluster_into_rows` + 滑动窗口合并），支持「结案」等多字符词块供体搜索；保留单字匹配
- **BUG-068**：`test_e2e_basic_tasks.py` 文档/类名诚实化（结构+合成冒烟门禁），删除假绿 MAE 自比；新增 `TestGoldenRegression`——资产齐备时回渲 final.pdf 与期望 PNG 做 `diff>10` 百分比真实校验（资产缺失 skip）
- **文档**：README 删重复 `verify_outputs.py` 行；SKILL.md / scripts_reference.md 补 `--source-orient` 说明

### 测试与门禁

- 219 单元（+10：BUG-065×2、BUG-066×8）+ 14 e2e（+3：BUG-067 多字符供体；TestGoldenRegression 3/3 subtask 真实跑）；`run_checks.sh` ✅
- **已知限制**：`tests/期望效果/` golden PNG 由未知光栅化器生成，与本仓库 PyMuPDF 渲染存在全页底噪（task003≈11%、task004/005≈4.5%），远大于真实编辑差异；golden 对齐后应收紧 `TestGoldenRegression` 阈值

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
