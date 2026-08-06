# 任务跟踪列表

记录本项目所有任务：代码 bug、bug 转需求、新增需求、需求调整、功能开发、代码审查、测试数据、文档维护、配置运维等。

> 说明：本文件是当前项目的任务清单。所有新增事项、状态变更和完成记录都应同步写入本文件。
> 字段说明：动作字段只允许以下 8 个固定枚举：修复、开发、优化、调整、规划、检查、文档、运维。
> 时间说明：发现时间和完成时间分开记录，格式为 YYYY-MM-DD HH:MM，使用机器本地时区的 24 小时制时间；未完成事项的完成时间填 -。
> 状态说明：Bug 未完成用待修复，通用未完成用待办（或待开发），进行中/已完成/已修复/已关闭/已解决按语义选用；条目互引用 [[BUG-001]] 语法。
> 归并规则：审计、复核、核查、审查、验证、评估统一记为“检查”；重构、清理统一记为“优化”；方案、梳理统一记为“规划”；记录类文档事项统一记为“文档”。

## 代码 Bug

| ID | 动作 | 问题描述 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| BUG-001 | 修复 | stroke_shoulder_blend 和 core_alpha_scale 在文档中标注为必需但 scan_text_fusion.py 未实现 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已修复 | 见 [[ADJ-001]]；make_text_mask / render_scan_fusion / render_halo 均加入可选参数 |
| BUG-002 | 修复 | PDF 封装有 save_image_as_pdf / replace_pdf_image 函数但无 CLI 子命令 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已修复 | 见 [[ADJ-002]]；新增 package 子命令支持两种模式 |
| BUG-003 | 修复 | 缺少 requirements.txt 依赖清单文件 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已修复 | 创建 scripts/requirements.txt，README 改为 pip3 install -r 引用 |
| BUG-004 | 修复 | verify_outputs.py --reproduce 语义错误：比的是源 PDF vs 终版，而非「基准图/管线重跑结果 vs 终版回渲」；真实编辑几乎必失败、源≈终又会误报通过 | 2026-08-05 19:40 | 2026-08-05 19:53 | 已修复 | 泛化实现见 [[ADJ-004]]；e2e 验证 pass/fail/command/未配置四条路径；严格像素比对在 --reproduce 模式下跳过 |
| BUG-005 | 修复 | ink_mask_in_boxes 用浮点 luma 阈值化，与原项目 cv2 整数灰度在阈值边界不一致（复现对比 G1），每区域约 2k 蒙版像素差，阻碍旧任务逐像素复现 | 2026-08-05 19:45 | 2026-08-05 19:50 | 已修复 | 改用 cv2.cvtColor(COLOR_RGB2GRAY) 整数灰度；test_skill 29 项仍全过 |
| BUG-006 | 修复 | identify_size.py --font 只接受路径，不接受注册名/文件名；SKILL.md 第 3 步示例在 macOS 报 cannot open resource（复现对比 G4） | 2026-08-05 19:45 | 2026-08-05 19:51 | 已修复 | 走 font_registry.find_font（路径/注册名/文件名三写法）；找不到清晰报错退出码 2；Songti SC 冒烟通过 |
| BUG-007 | 修复 | test_package_cli 只测新建 PDF 模式，未覆盖 --original-pdf 替换内嵌图模式 | 2026-08-05 19:40 | 2026-08-05 19:52 | 已修复 | 见 [[TST-004]] |
| BUG-008 | 修复 | scanned-pdf-editor 放在项目根目录 skills/，未安装到 Codex/Claude 可发现的技能目录，当前会话无法自动触发 | 2026-08-05 20:01 | 2026-08-05 20:11 | 已关闭 | 用户决定暂不安装；可发现路径为 ~/.agents/skills、~/.zcode/skills（用户级）或 <repo>/.agents/skills、<repo>/.zcode/skills（工作区级）。需安装时再处理 |
| BUG-009 | 修复 | identify_size.py 对空白/无墨迹参考框仍返回字号 27 并错误标记“确定” | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | 共识计算前预检最低阈值墨迹，无墨迹参考框报错退出码 3；见 [[TST-005]] |
| BUG-010 | 修复 | replace_pdf_image 未创建输出父目录，--original-pdf 模式写入新建嵌套目录时报 FzErrorSystem | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | 保存前 output_path.parent.mkdir(parents=True)；与 save_image_as_pdf 行为一致；见 [[TST-005]] |
| BUG-011 | 修复 | verify_outputs.py 将终版页数硬编码为 1 且只回渲第 1 页，无法验证 package --page-index 支持的多页 PDF | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | 新增 expected_pages/page_index 配置（默认 1/0 兼容旧配置），按目标页回渲与取尺寸；见 [[TST-005]] |
| BUG-012 | 修复 | ink_mask_in_boxes 在区域内取墨迹后直接膨胀，蒙版和 Telea 修改会越过用户给定 boxes | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | 膨胀后 cv2.bitwise_and(mask, region) 裁回越界部分；框外蒙版/改动归 0、框内仍清理；见 [[TST-005]] |
| BUG-013 | 修复 | replace_pdf_image 对含多张图片的页面静默替换 images[0]，可能替换 logo/印章而非整页扫描图 | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | 新增 _select_page_image_xref 按页面覆盖面积比例选最大图；多图头部并列时 strict 报错；见 [[TST-005]] |
| BUG-014 | 修复 | README 要求用 pytest 自测，但 requirements.txt 未声明 pytest | 2026-08-05 20:01 | 2026-08-05 20:11 | 已修复 | requirements.txt 增 pytest>=7.0（注释标为测试依赖） |
| BUG-015 | 修复 | font_registry.FONT_DIRS 未收录 ~/Library/Fonts（macOS 用户级字体目录），导致 macOS 双击安装 simfang.ttf 后 skill 仍找不到字体，add 路线无法复现（复现对比 task002add 字体 bug） | 2026-08-05 20:15 | 2026-08-05 20:25 | 已修复 | 新增 ~/Library/Fonts + /Network/Library/Fonts；resolve_font 验证可找到该目录下文件；见 [[ADJ-006]] [[CHK-007]] |
| BUG-016 | 修复 | identify_size.py 用最低阈值 min(thresholds)=80 做无墨迹预检，把只有较浅有效墨迹（如灰度 100、在阈值 120 下有效）的参考框误判为空白并退出 | 2026-08-05 20:53 | 2026-08-05 20:55 | 已修复 | 改为 max(thrs) 最宽松阈值预检；注释纠正为”thr 越高越宽松”；ink_dims(crop,80) 无墨迹但 ink_dims(crop,246) 有 1600px 不再误拒；见 [[TST-010]] [[CHK-011]] |
| BUG-017 | 修复 | remove_regions_interpolate 页面边缘采样不足时仍可能读到空平滑窗口，NaN 转 uint8 后把删除区部分填成纯黑 | 2026-08-05 20:53 | 2026-08-06 00:46 | 已修复 | 上下邻域样本行数 ≠ target_h 时用 cv2.resize 线性插值到目标高度再平滑；CHK-012 复现 (0,0,40,80)/(0,5,40,95) 零值通道=0、无 empty-slice 警告；task007 仍 bit-exact；见 [[TST-011]] |
| BUG-018 | 修复 | evals/evals.json 中多处中文引号未做 JSON 转义，文件无法解析，与 CHK-009”符合 schema”结论矛盾 | 2026-08-05 20:53 | 2026-08-05 20:55 | 已修复 | 中文文本内 ASCII 双引号替换为中文引号””；python3 -m json.tool 验证合法；新增 test_evals_json_is_valid 回归测试；见 [[TST-010]] [[CHK-011]] |
| BUG-019 | 修复 | test_skill.py 中 3 个测试用相对路径调用 identify_size.py / verify_outputs.py，从父目录运行 pytest 时找不到脚本文件 | 2026-08-06 01:10 | 2026-08-06 01:10 | 已修复 | 改为 Path(__file__).parent / “脚本名” 绝对路径；58 passed 从任意 CWD 均通过；见 [[CHK-015]] |

## 调整事项

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| ADJ-001 | 调整 | scan_text_fusion.py 参数化：--stroke-shoulder / --core-alpha-scale 可选参数，默认值保持 add 模式 bit-exact | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 修复 [[BUG-001]]；test_stroke_shoulder_default_preserves_old_behavior 验证一致性 |
| ADJ-002 | 调整 | scan_edit_ops.py 新增 package 子命令（ReportLab 新建 PDF + PyMuPDF replace_image 保留 OCR 层） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 修复 [[BUG-002]]；--original-pdf / --page-size / --dpi / --page-index 参数 |
| ADJ-003 | 调整 | verify_outputs.py 新增 --reproduce 复现模式（内存重渲 + 三阈值容差检查） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 修复 [[BUG-003]] 相关中等缺口；REPRODUCE_MAX_CHANGED_PIXELS=10000 |
| ADJ-004 | 调整 | verify_outputs.py --reproduce 泛化：配置支持 reproduce_command（shell 重跑）+ reproduce_image，缺省回退 expected_image 基准图 | 2026-08-05 19:40 | 2026-08-05 19:53 | 已完成 | 修复 [[BUG-004]]；docstring / 示例配置同步加 reproduce_command / reproduce_image 字段 |
| ADJ-005 | 调整 | 补齐删除项目原脚本中的整矩形 Telea 清理、纯底色偏移归一化、task007 复制后清除复合流程 | 2026-08-05 20:01 | 2026-08-05 20:45 | 已完成 | G2: full_mask_in_boxes + remove_regions_telea(mask_mode="full") + replace_with_donor(mask_mode=) + CLI --mask-mode；G3: normalize_donor_patch(mode="offset") + paste_donor_patch/replace_with_donor(normalize_mode=) + CLI --normalize-mode；G6: move_and_clear() + compound 子命令；SKILL.md 模式 B+ 文档；见 [[TST-008]] [[CHK-008]] |
| ADJ-006 | 调整 | identify_font.py 置信度不足（参考/存疑）且有未安装候选时，提示目标字体可能缺失并给出安装路径；无已装字体时也报错引导 | 2026-08-05 20:15 | 2026-08-05 20:25 | 已完成 | 三路径验证：确定不提示、参考/存疑提示安装路径、无已装字体报错+引导 exit 1；见 [[BUG-015]] |

## 检查事项

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| CHK-001 | 检查 | 代码审查：文档与实现一致性检查，发现 3 个关键缺口 + 5 个中等缺口 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 关键缺口见 [[BUG-001]] [[BUG-002]] [[BUG-003]]；中等缺口含 --reproduce、示例配置、测试覆盖、文档笔误 |
| CHK-002 | 检查 | 28 项单元测试全部通过验证（原 22 + 新增 6） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | pytest test_skill.py -v -> 28 passed in 0.38s；含 TestScanTextFusionAdvanced 6 项 + test_package_cli |
| CHK-003 | 检查 | 项目全量内容检查：逐文件核对文档/脚本/测试数据/配置，复跑 28 项自测与 CLI/依赖可用性 | 2026-08-05 19:28 | 2026-08-05 19:28 | 已完成 | 28 passed in 0.36s；PyMuPDF 1.27.2 可用；发现 3 处低危卫生问题（parse_boxes 未使用、BytesIO 文件尾导入、__pycache__ 残留），未修复待用户决定 |
| CHK-004 | 检查 | 回归验证：29 项单元测试 + --reproduce e2e（pass/fail/command/未配置四路径）+ identify_size 注册名/错误路径冒烟 | 2026-08-05 19:52 | 2026-08-05 19:53 | 已完成 | 29 passed in 0.59s；reproduce changed=0 pass、40000px fail、command pass、未配置清晰报错；严格像素模式不受影响 |
| CHK-005 | 检查 | 新 skill 二次代码审查：对照两个平行项目，执行单测、静态检查与 4 个边界最小复现 | 2026-08-05 20:01 | 2026-08-05 20:01 | 已完成 | 29 passed；ruff 发现 15 项卫生问题；新增 [[BUG-008]] 至 [[BUG-014]]、[[ADJ-005]]、[[TST-005]]、[[TST-006]]、[[OPT-002]] |
| CHK-006 | 检查 | 修复回归验证：逐个复现 [[BUG-009]] 至 [[BUG-014]] 边界并验证修复，全量测试 37 passed | 2026-08-05 20:11 | 2026-08-05 20:11 | 已完成 | 37 passed（29 原 + 8 新 TestEdgeCaseRegressions）；5 个 PyMuPDF SWIG 弃用警告为既有项；示例配置加载新字段默认值 OK |
| CHK-007 | 检查 | 字体 bug 回归验证：39 项单元测试 + identify_font 三路径功能性验证（确定不提示/参考提示安装/无已装报错引导） | 2026-08-05 20:15 | 2026-08-05 20:25 | 已完成 | 39 passed in 0.75s；确定 NCC=0.978 不提示、参考 NCC=0.965 margin=0.118 提示安装路径、无已装 exit 1+引导 |
| CHK-008 | 检查 | G2/G3/G6 功能 + 行为级 eval 回归验证：48 项单元测试 + 17 项 eval（触发 8 + 行为 6 + 基线 3） | 2026-08-05 20:01 | 2026-08-05 20:45 | 已完成 | 48 passed in 0.88s；17/17 eval 通过；见 [[ADJ-005]] [[TST-006]] [[TST-008]] |
| CHK-009 | 检查 | 6 个 PDF 任务对照验证 + skill-creator 规范合规检查 | 2026-08-05 20:45 | 2026-08-05 20:48 | 已完成 | 6 任务 G1-G6 缺口全部修复；quick_validate.py 通过；SKILL.md 455 行 <500；后二次复查确认 quick_validate 不检查 evals.json，原“符合 schema”结论错误，见 [[BUG-018]] [[CHK-010]] |
| CHK-010 | 检查 | 修复后二次复查：逐项回归 BUG-008～BUG-015、全量单测/eval/静态检查、skill 结构校验与新增边界最小复现 | 2026-08-05 20:53 | 2026-08-05 20:53 | 已完成 | 48 passed、现有 run_evals 17/17、quick_validate 通过；但新增 [[BUG-016]]～[[BUG-018]]，ruff 仍有 19 项，现有”触发/基线 eval”不是真实模型对照，见 [[TST-009]] [[OPT-003]] |
| CHK-011 | 检查 | BUG-016～018 修复后回归验证：全量单测 54 项 + evals 17 项 + evals.json JSON 合法性 + 6 PDF 任务复验 | 2026-08-05 20:55 | 2026-08-05 20:58 | 已完成 | 54 passed（48 原 + 6 新 TestBugFix016_018）；17/17 eval 通过；evals.json json.loads OK；task001/003/004/006/007 像素差 ≤4 无黑块；task002add 仍缺 simfang.ttf（环境限制非代码 bug）；见 [[BUG-016]] [[BUG-017]] [[BUG-018]] [[TST-010]] |
| CHK-012 | 检查 | 第三次修复复查：全量单测、JSON/eval、ruff、skill 校验及 BUG-016～018 扩展边界复现 | 2026-08-05 23:43 | 2026-08-05 23:43 | 已完成 | 54 passed、evals.json 合法、现有确定性 eval 17/17、quick_validate 通过；BUG-016/018 通过，[[BUG-017]] 大面积贴边框复现仍失败（随后在 00:46 关闭）；ruff 19 项，[[TST-009]] [[OPT-003]] 仍待办 |
| CHK-013 | 检查 | BUG-017 完整修复回归：CHK-012 最小复现 + TST-011 + 全量单测 + task007 bit-exact | 2026-08-06 00:46 | 2026-08-06 00:46 | 已完成 | (0,0,40,80)/(0,5,40,95) zero=0、无 empty-slice 警告；58 passed；task007 identical=True；见 [[BUG-017]] [[TST-011]] |
| CHK-014 | 检查 | 收尾验证：ruff 全清 + 回归门禁 run_checks.sh + 确定性 eval + EVAL.md 真实模型评测脚手架 | 2026-08-06 00:59 | 2026-08-06 00:59 | 已完成 | ruff check . → All checks passed（18→0）；run_checks.sh 通过；确定性 eval 17/17；evals/EVAL.md 含 6 用例源/基准映射+with/without-skill 流程+评分记录模板；见 [[OPT-003]] [[TST-009]] |
| CHK-015 | 检查 | 续接会话验证：从父目录运行 pytest 发现 3 个路径相关测试失败，修复后全量回归 | 2026-08-06 01:10 | 2026-08-06 01:10 | 已完成 | 发现 [[BUG-019]]（相对路径改绝对路径）；58 passed 从任意 CWD 通过；ruff All checks passed；BUG-017 复现 zero=0 无警告 |
| CHK-016 | 检查 | 审查 .gitignore 是否齐全：对照仓库垃圾文件、git check-ignore 与 skill 运行产物风险 | 2026-08-06 11:04 | 2026-08-06 11:04 | 已完成 | 现有缓存/系统/IDE/环境规则已生效；缺口含 Agent 安装目录，见 [[OPS-003]]；tmp/tasks/二进制产物为可选预防项 |

## 测试数据

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| TST-001 | 开发 | TestScanTextFusionAdvanced 新增 6 项融合特性测试（字重肩部效果/核心透明度效果/halo 可见变化/区域限制/默认行为一致性） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 验证 stroke_shoulder_blend=0.25 vs 0.0 输出不同；0.965 vs 0.875 输出不同；默认参数=显式默认值 |
| TST-002 | 开发 | verify_config.example.json 示例验证配置（2 个用例：删除并上移 + 替换原生供体） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | SKILL.md 引用的示例配置文件 |
| TST-003 | 开发 | test_package_cli CLI 封装子命令测试 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 验证 package 子命令两种模式可正常调用 |
| TST-004 | 开发 | test_package_cli_replace_image：覆盖 --original-pdf 替换内嵌图模式（PyMuPDF） | 2026-08-05 19:52 | 2026-08-05 19:52 | 已完成 | 修复 [[BUG-007]]；造带内嵌图 PDF→替换→校验页数/页尺寸；无 PyMuPDF 时 skipTest |
| TST-005 | 开发 | 增加无墨迹参考框、多页 PDF、嵌套输出目录、多 XObject、框边缘膨胀等边界回归测试 | 2026-08-05 20:01 | 2026-08-05 20:11 | 已完成 | TestEdgeCaseRegressions 8 项锁定 [[BUG-009]] 至 [[BUG-013]]；总计 37 passed |
| TST-006 | 开发 | 建立确定性 CLI/关键词自检：触发词规则、6 条 CLI 行为、3 组文档覆盖检查 | 2026-08-05 20:01 | 2026-08-05 20:45 | 已完成 | eval_cases.json 17 项全部通过；该测试不运行模型，也不构成真正的 with-skill/without-skill 基线，真实行为评测另见 [[TST-009]] |
| TST-007 | 开发 | test_font_dirs_includes_macos_user_fonts + test_resolve_font_finds_file_in_temp_dir：验证 ~/Library/Fonts 在 FONT_DIRS 且 resolve_font 遍历目录查找 | 2026-08-05 20:15 | 2026-08-05 20:25 | 已完成 | 修复 [[BUG-015]]；39 passed（37 原 + 2 新 TestFontRegistry） |
| TST-008 | 开发 | TestCompoundModes 9 项测试：G2 整矩形蒙版 + G3 offset 归一化 + G6 复合操作 + CLI 集成 | 2026-08-05 20:01 | 2026-08-05 20:45 | 已完成 | 见 [[ADJ-005]]；48 passed（39 原 + 9 新 TestCompoundModes） |
| TST-009 | 开发 | 按 skill-creator 规范建立真实模型 with-skill / without-skill 基线运行、断言评分与可审阅结果 | 2026-08-05 20:53 | 2026-08-06 00:59 | 已解决 | 已澄清 skill-creator 规范本身是交互式（逐 prompt 新会话跑+人工审阅，无 grading.json/benchmark 文件格式）。完成脚手架：run_evals.py docstring 诚实改为「确定性自检、不运行模型」；新增 evals/EVAL.md（6 用例源/基准映射、with/without-skill 运行流程、4 维评分表、记录模板）。真实模型逐条运行需人工在新会话执行，填 EVAL.md 记录表，非脚本可一键完成 |
| TST-010 | 开发 | TestBugFix016_018 新增 6 项回归测试：插值全宽/左边缘/右边缘无黑块 + compound 全宽 + identify_size 浅墨迹接受 + evals.json JSON 合法性 | 2026-08-05 20:55 | 2026-08-05 20:55 | 已完成 | 修复 [[BUG-016]] [[BUG-017]] [[BUG-018]]；54 passed（48 原 + 6 新）；见 [[CHK-011]] |
| TST-011 | 开发 | 增加全宽大面积删除框贴近顶部/底部、上下样本总行数小于目标高度的插值回归测试 | 2026-08-05 23:43 | 2026-08-06 00:46 | 已完成 | TestBugFix017LargeEdge 4 项：top-heavy / bottom-heavy / near-full-height / CHK-012 双复现框；断言无 empty-slice 警告、无 NaN、零值通道=0；全量 58 passed；关闭 [[BUG-017]] |

## 文档维护

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 文档 | SKILL.md 技能文档：四种模式完整说明、参数表、CLI 示例、PDF 封装节 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 含 --stroke-shoulder / --core-alpha-scale / --reproduce / package 参数说明 |
| DOC-002 | 文档 | README.md 快速开始、文件结构、依赖安装说明 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 依赖改为 pip3 install -r scripts/requirements.txt |
| DOC-003 | 文档 | references/pipeline_methodology.md 管线方法论文档（含实现状态注释） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 字重肩部与核心透明度缩放处加实现状态注释 |
| DOC-004 | 文档 | 研究与 skill 设计分析文档编写（能力矩阵、技术路线、架构设计） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 即《扫描版PDF编辑修改_研究与skill设计分析.md》 |
| DOC-005 | 文档 | 分析文档笔误修复：STROKE_SHODER_BLEND→STROKE_SHOULDER_BLEND；scan_edit_ops.py --remove→remove（3处） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | §8.2 字重肩部合并标记为 ✅ 已完成 |
| DOC-006 | 文档 | SKILL.md 修正：封装示例补 scripts/ 前缀（L324 与 L310 不一致）；--reproduce 注释改为基准图/reproduce_command 语义；identify_size --font 三写法说明 | 2026-08-05 19:40 | 2026-08-05 19:51 | 已完成 | 对应 [[BUG-004]] [[BUG-006]] 的文档侧 |
| DOC-007 | 文档 | 明确 scan_text_fusion.py --output 是 --output-dir 内的文件名（非完整路径）；SKILL.md 参数表补 --output-dir/--output 行 + 脚本 help 同步（复现对比 G5） | 2026-08-05 19:45 | 2026-08-05 19:51 | 已完成 | 第 5 步融合示例与工具参考表均已覆盖 |
| DOC-008 | 文档 | SKILL.md font_registry 节补 macOS ~/Library/Fonts 目录说明 + 字体缺失安装指引 blockquote；identify_font.py docstring 同步置信度不足提示 | 2026-08-05 20:15 | 2026-08-05 20:25 | 已完成 | macOS 仿宋行改为"需自行安装（放入 ~/Library/Fonts）"；新增字体缺失提示说明 |

## 功能开发

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| DEV-001 | 开发 | scan_edit_utils.py 共用工具库：300dpi 回渲、像素块上移、墨迹蒙版、Telea 修补、PDF 封装、差分与中文字体 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | save_image_as_pdf / replace_pdf_image 双模式封装 |
| DEV-002 | 开发 | scan_edit_ops.py 四模式 CLI：remove（telea/interpolate）、move、replace、package | 2026-08-05 19:21 | 2026-08-05 19:52 | 已完成 | 子命令驱动架构；增加文字（add）不在本 CLI，走 scan_text_fusion.py，见 [[DEV-003]] |
| DEV-003 | 开发 | scan_text_fusion.py 扫描融合引擎：字体合成 + alpha 软化 + 蓝灰晕染 + 字重肩部/核心透明度可选参数 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 默认 stroke_shoulder=0.0 / core_alpha=0.965 保持 add 模式 bit-exact 复现 |
| DEV-004 | 开发 | identify_font.py + identify_size.py 字体字号识别（灰度 NCC + 墨迹共识 + 置信度门） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 从增加项目迁移并整合 |
| DEV-005 | 开发 | font_registry.py 字体注册表与跨平台中文字体查找 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 支持 Windows/macOS/Linux 自动选择 |
| DEV-006 | 开发 | verify_outputs.py 验证脚本：严格哈希 + --reproduce 内存复现模式 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 容差：≤10000px / 通道差≤4 / MAE≤0.001 |

## 配置运维

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| OPS-001 | 运维 | 补充项目级 .gitignore，覆盖常规操作系统临时文件、IDE 本地状态、环境变量变体和 Python 打包临时元数据 | 2026-08-06 11:03 | 2026-08-06 11:03 | 已完成 | 保留 .env.example 与依赖锁文件；已执行 git check-ignore 代表性路径验证 |
| OPS-002 | 运维 | 安装 CLAUDE.md 会话结束任务同步规则与 Stop hook，提醒后续 agent 自动维护 task-list | 2026-08-06 11:07 | 2026-08-06 11:07 | 已完成 | 中文规则写入 CLAUDE.md；hook 注册于 .claude/settings.json，脚本为 .claude/hooks/tasklist_sync_reminder.sh；已验证 JSON、可执行权限及单会话去重 |
| OPS-003 | 运维 | .gitignore 增补 Agent 安装目录忽略：.agents/、.claude/、.zcode/ | 2026-08-06 11:09 | 2026-08-06 11:09 | 已完成 | 源码目录 skills/ 不受影响；git check-ignore 验证三条规则生效；见 [[CHK-016]] |

## 规划事项

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| PLN-001 | 规划 | 统一 skill 架构设计：四种操作模式（删除/移动/替换/增加）+ 共用工具层 + 验证层 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | DPI 选择：300 for remove/move/replace，200 for add/fusion；Route A 原生像素迁移 vs Route B 字体合成 |
| PLN-002 | 规划 | 替换优先级链设计：同页词块→同系列页→相同单字→字体合成（含字重肩部） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 优先迁移原生扫描像素，字体合成仅作后备 |

## 优化事项

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| OPT-001 | 优化 | stroke_shoulder / core_alpha_scale 参数化设计：默认值保持 add 模式 bit-exact 复现，替换后备可显式开启 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 避免破坏 seed=20260701 已验证输出；见 [[ADJ-001]] [[BUG-001]] |
| OPT-002 | 优化 | 精简 SKILL.md frontmatter description，只保留触发条件，避免把完整工作流写进描述导致模型跳过正文 | 2026-08-05 20:01 | 2026-08-05 20:11 | 已完成 | description 由约 320 字精简到约 126 字，只留触发条件+授权边界；四模式实现细节仍在正文 |
| OPT-003 | 优化 | 清理 ruff 静态检查问题并把静态检查纳入回归门禁 | 2026-08-05 20:53 | 2026-08-06 00:59 | 已完成 | 清理全部 18 项（E401/E701/E702/F401/F841/E402）；新增 scripts/run_checks.sh（ruff + pytest 回归门禁）；requirements.txt 加 ruff>=0.6；README 文件结构与自测节同步；ruff check . → All checks passed，58 passed |

## 调研事项

| ID | 动作 | 事项 | 发现时间 | 完成时间 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- |
| RES-001 | 规划 | 研究增加项目与删除项目的能力矩阵、技术路线互补性，判断统一 skill 可行性 | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | 两项目操作完全互补无冲突；输出《扫描版PDF编辑修改_研究与skill设计分析.md》 |
| RES-002 | 规划 | 字体粗细失配原因分析与字重肩部补偿参数研究（来源 task005 实验） | 2026-08-05 19:21 | 2026-08-05 19:21 | 已完成 | STROKE_SHOULDER_BLEND=0.25、CORE_ALPHA_SCALE=0.875 为替换后备最佳参数；add 模式用 0.0/0.965 |

## 统计摘要

| 分类 | 总数 | 已完成 | 待开发/待修复 | 完成率 |
| --- | --- | --- | --- | --- |
| 代码 Bug | 19 | 19 | 0 | 100% |
| 调整事项 | 6 | 6 | 0 | 100% |
| 检查事项 | 16 | 16 | 0 | 100% |
| 测试数据 | 11 | 11 | 0 | 100% |
| 文档维护 | 8 | 8 | 0 | 100% |
| 功能开发 | 6 | 6 | 0 | 100% |
| 配置运维 | 3 | 3 | 0 | 100% |
| 规划事项 | 2 | 2 | 0 | 100% |
| 优化事项 | 3 | 3 | 0 | 100% |
| 调研事项 | 2 | 2 | 0 | 100% |
| **总计** | 76 | 76 | 0 | 100% |
